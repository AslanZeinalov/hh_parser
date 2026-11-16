"""
Этап 1: Сбор ссылок на вакансии HH.ru через Playwright.
Ищет только по названию, применяет фильтры из config.py,
сохраняет URL + название и сразу фильтрует мусор по названию.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlencode
import pandas as pd
import time
import re
from datetime import datetime

import config
from filter_relevant import classify_title


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def extract_vacancy_id(url: str) -> str:
    match = re.search(r"/vacancy/(\d+)", url)
    return match.group(1) if match else None


def build_search_url(query: str, page_num: int) -> str:
    """Формирует URL поиска со всеми фильтрами из config.py."""
    params = [
        ("text", query),
        ("page", page_num),
        ("search_field", config.SEARCH_FIELD),
        ("hhtmFrom", "vacancy_search_list"),
    ]
    if config.NO_MAGIC:
        params.append(("no_magic", "true"))
    for area in config.AREA_IDS:
        params.append(("area", area))
    for exp in config.EXPERIENCE:
        params.append(("experience", exp))
    if config.SALARY_FROM is not None:
        params.append(("salary", config.SALARY_FROM))
        params.append(("currency", config.CURRENCY))
    if config.ONLY_WITH_SALARY:
        params.append(("only_with_salary", "true"))
    for emp in config.EMPLOYMENT:
        params.append(("employment", emp))
    for sch in config.SCHEDULE:
        params.append(("schedule", sch))
    if config.PERIOD_DAYS is not None:
        params.append(("period", config.PERIOD_DAYS))
    if config.ORDER_BY:
        params.append(("order_by", config.ORDER_BY))

    return "https://hh.ru/search/vacancy?" + urlencode(params)


def log_active_filters() -> None:
    log("Активные фильтры поиска:")
    if config.AREA_IDS:
        names = [config.AREA_NAMES.get(a, str(a)) for a in config.AREA_IDS]
        log(f"  Город: {', '.join(names)}")
    else:
        log("  Город: вся Россия")
    log(f"  Опыт: {config.EXPERIENCE if config.EXPERIENCE else 'любой'}")
    log(f"  Зарплата от: {config.SALARY_FROM if config.SALARY_FROM else 'не задана'}")
    log(f"  Только с зарплатой: {config.ONLY_WITH_SALARY}")
    log(f"  Занятость: {config.EMPLOYMENT if config.EMPLOYMENT else 'любая'}")
    log(f"  График: {config.SCHEDULE if config.SCHEDULE else 'любой'}")
    log(f"  Давность публикации: {config.PERIOD_DAYS if config.PERIOD_DAYS else 'за всё время'} дней")
    log(f"  Поиск только по названию: {config.SEARCH_FIELD == 'name'}")


def check_for_captcha(page) -> bool:
    try:
        for selector in ["iframe[src*='captcha']", ".smart-captcha"]:
            if page.query_selector(selector):
                return True
        body_text = page.inner_text("body").lower()
        return any(k in body_text for k in ["подтвердите, что вы не робот", "доступ ограничен"])
    except Exception:
        return False


def parse_search_page(page, url: str, page_num: int) -> list:
    """Парсит страницу выдачи. Возвращает список dict: vacancy_id, url, title."""
    log(f"  -> Загрузка страницы {page_num}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT)
        page.wait_for_timeout(2000)
    except PlaywrightTimeoutError:
        log(f"Таймаут загрузки страницы {page_num}", level="ERROR")
        return None
    except Exception as e:
        log(f"Ошибка загрузки страницы {page_num}: {e}", level="ERROR")
        return None

    if check_for_captcha(page):
        log("HH.ru показал капчу!", level="WARNING")
        return None

    results = []

    # Основной способ: ссылки с заголовками
    try:
        elements = page.query_selector_all("a[data-qa='vacancy-serp__vacancy-title']")
        for elem in elements:
            href = elem.get_attribute("href") or ""
            title = elem.inner_text().strip()
            if "/vacancy/" in href:
                clean_url = href.split("?")[0]
                if clean_url.startswith("/"):
                    clean_url = "https://hh.ru" + clean_url
                vid = extract_vacancy_id(clean_url)
                if vid:
                    results.append({"vacancy_id": vid, "url": clean_url, "title": title})
    except Exception as e:
        log(f"Ошибка парсинга заголовков: {e}", level="ERROR")

    # Запасной способ: все ссылки с /vacancy/ (без заголовков)
    if not results:
        log("  Основной селектор пуст, пробую запасной...", level="WARNING")
        try:
            for link in page.query_selector_all("a[href*='/vacancy/']"):
                href = link.get_attribute("href") or ""
                clean_url = href.split("?")[0]
                if clean_url.startswith("/"):
                    clean_url = "https://hh.ru" + clean_url
                vid = extract_vacancy_id(clean_url)
                if vid:
                    results.append({"vacancy_id": vid, "url": clean_url, "title": ""})
        except Exception as e:
            log(f"Ошибка запасного парсинга: {e}", level="ERROR")

    log(f"  -> Найдено вакансий на странице: {len(results)}")
    return results


def collect_links() -> list:
    log("=" * 60)
    log("ЭТАП 1: СБОР ССЫЛОК НА ВАКАНСИИ")
    log("=" * 60)
    log(f"Запросы: {config.SEARCH_QUERIES}")
    log_active_filters()

    all_items = {}   # vacancy_id -> dict, автоматическая дедупликация
    captcha_streak = 0
    stop_all = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        for q_idx, query in enumerate(config.SEARCH_QUERIES, 1):
            if stop_all:
                break
            log("-" * 60)
            log(f"Запрос {q_idx}/{len(config.SEARCH_QUERIES)}: '{query}'")
            empty_streak = 0

            for page_num in range(config.MAX_PAGES):
                url = build_search_url(query, page_num)
                items = parse_search_page(page, url, page_num)

                if items is None:
                    captcha_streak += 1
                    if captcha_streak >= 3:
                        log("КАПЧА 3 РАЗА ПОДРЯД. Остановка, собранное будет сохранено.",
                            level="ERROR")
                        stop_all = True
                        break
                    time.sleep(15)
                    continue
                captcha_streak = 0

                if len(items) == 0:
                    empty_streak += 1
                    if empty_streak >= 2:
                        log(f"Конец выдачи для запроса '{query}'")
                        break
                else:
                    empty_streak = 0
                    before = len(all_items)
                    for item in items:
                        all_items[item["vacancy_id"]] = item
                    log(f"Новых уникальных: {len(all_items) - before}, всего: {len(all_items)}")

                time.sleep(config.DELAY_STAGE1)

        browser.close()

    return list(all_items.values())


def save_and_filter(items: list) -> None:
    df = pd.DataFrame(items)
    df.to_csv(config.LINKS_ALL_FILE, index=False, encoding="utf-8-sig")
    log(f"Все ссылки сохранены: {len(df)} -> {config.LINKS_ALL_FILE}")

    if not config.APPLY_TITLE_FILTER:
        df.to_csv(config.LINKS_FILE, index=False, encoding="utf-8-sig")
        log(f"Фильтр по названию отключён, все ссылки идут в {config.LINKS_FILE}")
        return

    df["category"] = df["title"].apply(classify_title)
    # Ссылки без заголовка (запасной селектор) не фильтруем, отправляем в review
    df.loc[df["title"] == "", "category"] = "review"

    for category, filename in [
        ("relevant", config.LINKS_FILE),
        ("review", config.LINKS_REVIEW_FILE),
        ("excluded", config.LINKS_EXCLUDED_FILE),
    ]:
        part = df[df["category"] == category].drop(columns=["category"])
        part.to_csv(filename, index=False, encoding="utf-8-sig")
        log(f"{category}: {len(part)} -> {filename}")
        for title in part["title"].head(5):
            log(f"    пример: {title}")

    log(f"Для этапа 2 готовы {len(df[df['category'] == 'relevant'])} ссылок. "
        f"Проверь {config.LINKS_REVIEW_FILE}: если там есть целевые вакансии, "
        f"скопируй их строки в {config.LINKS_FILE}.")


if __name__ == "__main__":
    start = time.time()
    items = collect_links()
    if items:
        save_and_filter(items)
    else:
        log("Ссылок не найдено.", level="WARNING")
    log(f"Общее время: {(time.time() - start) / 60:.1f} мин")