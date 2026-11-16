"""
Диагностика блока "Ключевые навыки": проверка селекторов и дамп HTML.
"""

from playwright.sync_api import sync_playwright

URL = "https://kazan.hh.ru/vacancy/139270942"  # подставь любую живую вакансию

CANDIDATE_SELECTORS = [
    "span[data-qa='bloko-tag__text']",
    "[data-qa='skills-element']",
    "div[data-qa='skills-table']",
    "span[data-qa='bloko-tag']",
    "[data-qa='vacancy-skill']",
    "li[data-qa='skills-element']",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    print("=" * 60)
    print("ПРОВЕРКА СЕЛЕКТОРОВ")
    for sel in CANDIDATE_SELECTORS:
        elements = page.query_selector_all(sel)
        texts = [e.inner_text().strip() for e in elements[:8]]
        print(f"{sel}: найдено {len(elements)} | {texts}")

    html = page.content()
    with open("vacancy_debug.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML сохранён в vacancy_debug.html")

    idx = html.find("Ключевые навыки")
    print("=" * 60)
    if idx != -1:
        print("ФРАГМЕНТ HTML ВОКРУГ 'Ключевые навыки':")
        print(html[idx - 300: idx + 2000])
    else:
        print("Текст 'Ключевые навыки' на странице не найден")

    browser.close()