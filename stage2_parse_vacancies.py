"""
Этап 2: Парсинг карточек вакансий HH.ru через Playwright.
Чекпоинты, возобновление, дедупликация по содержимому,
финальная фильтрация по названию.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
import re
import os
import hashlib
from datetime import datetime

import config
from filter_relevant import classify_title


# Селекторы-кандидаты для блока "Ключевые навыки" (пробуются по очереди)
SKILL_SELECTORS = [
    "div[data-qa='skills-table'] span[data-qa='bloko-tag__text']",
    "span[data-qa='bloko-tag__text']",
    "[data-qa='skills-element']",
    "li[data-qa='skills-element']",
    "div[data-qa='skills-table'] span",
]


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def extract_vacancy_id(url: str) -> str:
    match = re.search(r"/vacancy/(\d+)", url)
    return match.group(1) if match else None


def load_links(filename: str) -> list:
    log(f"Чтение ссылок: {filename}")
    df = pd.read_csv(filename, dtype=str)
    url_col = "url" if "url" in df.columns else "vacancy_url"
    df["vacancy_id"] = df[url_col].apply(extract_vacancy_id)
    invalid = df["vacancy_id"].isna().sum()
    if invalid:
        log(f"Отброшено невалидных URL: {invalid}", level="WARNING")
        df = df.dropna(subset=["vacancy_id"])
    before = len(df)
    df = df.drop_duplicates(subset=["vacancy_id"])
    log(f"Ссылок: {before}, после дедупликации по ID: {len(df)}")
    return [{"vacancy_id": r["vacancy_id"], "url": r[url_col]} for _, r in df.iterrows()]


def load_done_ids(filename: str) -> set:
    if not os.path.exists(filename):
        return set()
    try:
        df = pd.read_csv(filename, dtype={"vacancy_id": str})
        done = set(df["vacancy_id"].astype(str))
        log(f"Найден прогресс: {len(done)} вакансий уже спарсено, будут пропущены")
        return done
    except Exception as e:
        log(f"Не удалось прочитать прогресс: {e}", level="WARNING")
        return set()


def load_existing_rows(filename: str) -> list:
    if not os.path.exists(filename):
        return []
    try:
        return pd.read_csv(filename, dtype={"vacancy_id": str}).to_dict("records")
    except Exception:
        return []


def check_for_captcha(page) -> bool:
    try:
        for selector in ["iframe[src*='captcha']", ".smart-captcha"]:
            if page.query_selector(selector):
                return True
        body_text = page.inner_text("body").lower()
        return any(k in body_text for k in ["подтвердите, что вы не робот", "доступ ограничен"])
    except Exception:
        return False


def safe_text(page, selector: str) -> str:
    try:
        elem = page.query_selector(selector)
        return elem.inner_text().strip() if elem else ""
    except Exception:
        return ""


def extract_key_skills(page) -> tuple:
    """
    Извлекает ключевые навыки. Пробует селекторы-кандидаты,
    затем запасной поиск по заголовку 'Ключевые навыки'.
    Возвращает (список навыков, источник).
    """
    for sel in SKILL_SELECTORS:
        try:
            elements = page.query_selector_all(sel)
            texts = [e.inner_text().strip() for e in elements]
            texts = [t for t in texts if t and len(t) < 60]
            if texts:
                return list(dict.fromkeys(texts)), sel
        except Exception:
            continue

    # Запасной вариант: ищем заголовок блока и берём теги из его контейнера
    try:
        texts = page.evaluate("""() => {
            const all = Array.from(document.querySelectorAll('h2,h3,div,span,p'));
            const header = all.find(el => el.childElementCount === 0
                && el.textContent.trim() === 'Ключевые навыки');
            if (!header) return [];
            let block = header.parentElement;
            for (let i = 0; i < 3 && block; i++) {
                const tags = Array.from(block.querySelectorAll('span,a,li'))
                    .map(e => e.textContent.trim())
                    .filter(t => t && t !== 'Ключевые навыки' && t.length < 60);
                if (tags.length) return [...new Set(tags)];
                block = block.parentElement;
            }
            return [];
        }""")
        if texts:
            return texts, "heading-fallback"
    except Exception:
        pass

    return [], "none"


def parse_vacancy(page, url: str, vacancy_id: str) -> dict:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT)
        page.wait_for_timeout(1500)
    except PlaywrightTimeoutError:
        log(f"  Таймаут: {url}", level="ERROR")
        return None
    except Exception as e:
        log(f"  Ошибка загрузки: {e}", level="ERROR")
        return None

    if check_for_captcha(page):
        log("  КАПЧА!", level="WARNING")
        return {"captcha": True}

    title = safe_text(page, "h1[data-qa='vacancy-title']")
    company = safe_text(page, "[data-qa='vacancy-company-name']")
    salary = safe_text(page, "[data-qa='vacancy-salary']")
    experience = safe_text(page, "[data-qa='vacancy-experience']")
    location = safe_text(page, "[data-qa='vacancy-view-location']")
    description = safe_text(page, "[data-qa='vacancy-description']")

    # Прокрутка вниз, чтобы догрузился блок навыков, если он ленивый
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(700)
    except Exception:
        pass

    skills, skills_source = extract_key_skills(page)

    if not title and not description:
        log(f"  Вакансия {vacancy_id} пуста (удалена или в архиве)", level="WARNING")
        return None

    return {
        "vacancy_id": vacancy_id,
        "url": url,
        "title": title,
        "company": company,
        "salary_text": salary,
        "experience": experience,
        "location": location,
        "description": description,
        "key_skills": "; ".join(skills),
        "skills_source": skills_source,
        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_rows(rows: list, filename: str) -> None:
    pd.DataFrame(rows).to_csv(filename, index=False, encoding="utf-8-sig")


def dedup_by_content(filename_in: str, filename_out: str) -> dict:
    df = pd.read_csv(filename_in, dtype={"vacancy_id": str})
    before = len(df)

    def content_hash(row) -> str:
        text = f"{row['title']}|{row['company']}|{row['description']}".lower()
        text = re.sub(r"\s+", " ", text).strip()
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    df["content_hash"] = df.apply(content_hash, axis=1)
    df = df.drop_duplicates(subset=["content_hash"], keep="first")
    df = df.drop(columns=["content_hash"])
    df.to_csv(filename_out, index=False, encoding="utf-8-sig")
    return {"before": before, "after": len(df), "removed": before - len(df)}


def run_parser() -> None:
    log("=" * 60)
    log("ЭТАП 2: ПАРСИНГ КАРТОЧЕК ВАКАНСИЙ")
    log("=" * 60)

    links = load_links(config.LINKS_FILE)
    done_ids = load_done_ids(config.RAW_FILE)
    all_rows = load_existing_rows(config.RAW_FILE)
    failed = []

    pending = [l for l in links if str(l["vacancy_id"]) not in done_ids]
    if config.TEST_LIMIT is not None:
        pending = pending[:config.TEST_LIMIT]
        log(f"ТЕСТОВЫЙ РЕЖИМ: {len(pending)} вакансий")
    log(f"К обработке: {len(pending)}")
    if pending:
        est = len(pending) * (config.DELAY_STAGE2 + 3) / 60
        log(f"Ориентировочное время: {est:.0f} мин")

    processed = 0
    captcha_streak = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        for idx, link in enumerate(pending, 1):
            url, vid = link["url"], str(link["vacancy_id"])
            log(f"[{idx}/{len(pending)}] Вакансия {vid}")

            result = None
            for attempt in range(1, config.MAX_RETRIES + 1):
                result = parse_vacancy(page, url, vid)
                if result is not None:
                    break
                log(f"  Попытка {attempt}/{config.MAX_RETRIES} не удалась, повтор...",
                    level="WARNING")
                time.sleep(5)

            if result and result.get("captcha"):
                captcha_streak += 1
                failed.append({"vacancy_id": vid, "url": url, "reason": "captcha"})
                if captcha_streak >= 3:
                    log("КАПЧА 3 РАЗА ПОДРЯД. Аварийная остановка, прогресс сохранён.",
                        level="ERROR")
                    break
                time.sleep(30)
                continue
            captcha_streak = 0

            if result is None:
                failed.append({"vacancy_id": vid, "url": url, "reason": "parse_error_or_empty"})
                log(f"  НЕ УДАЛОСЬ спарсить {vid}", level="ERROR")
            else:
                all_rows.append(result)
                n_skills = len(result["key_skills"].split("; ")) if result["key_skills"] else 0
                log(f"  OK: '{result['title']}' | '{result['company']}' | "
                    f"описание {len(result['description'])} симв. | "
                    f"навыков {n_skills} ({result['skills_source']})")

            processed += 1
            if processed % config.CHECKPOINT_EVERY == 0:
                save_rows(all_rows, config.RAW_FILE)
                log(f"--- ЧЕКПОИНТ: сохранено {len(all_rows)} ---")

            time.sleep(config.DELAY_STAGE2)

        browser.close()

    save_rows(all_rows, config.RAW_FILE)
    log(f"Итого сохранено: {len(all_rows)} -> {config.RAW_FILE}")

    if failed:
        pd.DataFrame(failed).to_csv(config.FAILED_FILE, index=False, encoding="utf-8-sig")
        log(f"Не спарсено {len(failed)} ссылок -> {config.FAILED_FILE}", level="WARNING")

    log("Дедупликация по содержимому...")
    stats = dedup_by_content(config.RAW_FILE, config.DEDUP_FILE)
    log(f"Было {stats['before']}, стало {stats['after']}, дублей удалено {stats['removed']}")

    log("Фильтрация по названию...")
    df = pd.read_csv(config.DEDUP_FILE, dtype={"vacancy_id": str})
    df["category"] = df["title"].apply(classify_title)
    for category, filename in [
        ("relevant", config.RELEVANT_FILE),
        ("excluded", config.EXCLUDED_FILE),
        ("review", config.REVIEW_FILE),
    ]:
        part = df[df["category"] == category].drop(columns=["category"])
        part.to_csv(filename, index=False, encoding="utf-8-sig")
        log(f"{category}: {len(part)} -> {filename}")

    log("=" * 60)
    log(f"ЭТАП 2 ЗАВЕРШЕН. Файл для этапа 3: {config.RELEVANT_FILE}")
    log("=" * 60)


if __name__ == "__main__":
    start = time.time()
    run_parser()
    log(f"Общее время: {(time.time() - start) / 60:.1f} мин")