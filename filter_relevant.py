"""
Фильтрация вакансий по названию.
Используется как самостоятельный скрипт и как модуль для этапов 1 и 2.
Три корзины: relevant (целевые), excluded (мусор), review (проверить глазами).
"""

import pandas as pd
import re
import os
from datetime import datetime

import config


RELEVANT_PATTERNS = [
    r"аналитик.{0,30}данн",              # аналитик данных, аналитик по работе с данными
    r"\bdat[ae]\s+analyst\b",            # data analyst + опечатка date analyst
    r"продуктов\w*.{0,10}аналитик",      # продуктовый аналитик
    r"аналитик.{0,20}продукт",           # аналитик продукта
    r"\bproduct\s+analyst\b",
    r"\bbi[\s-]?аналитик",
    r"\bbi\s+analyst\b",
    r"аналитик\s+bi",
]

EXCLUDE_PATTERNS = [
    r"системн\w*\s+аналитик", r"system\s+analyst",
    r"финансов\w*\s+аналитик",
    r"экономист", r"бухгалтер", r"1с",
    r"бизнес[\s-]аналитик", r"business\s+analyst",
    r"архитектор", r"разработчик", r"developer",
    r"инженер", r"engineer", r"devops",
    r"менеджер", r"manager", r"руководитель", r"director",
    r"\bcpo\b", r"product\s+owner", r"владелец\s+продукта",
    r"маркетолог", r"маркетинг", r"юрист", r"рекрутер",
    r"тестиров", r"\bqa\b", r"c\+\+",
    r"аналитик\s+проектов", r"\bwms\b",
]


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [INFO] {message}", flush=True)


def classify_title(title: str) -> str:
    """Возвращает категорию: relevant / excluded / review."""
    t = str(title).lower()
    if any(re.search(p, t) for p in RELEVANT_PATTERNS):
        return "relevant"
    if any(re.search(p, t) for p in EXCLUDE_PATTERNS):
        return "excluded"
    if re.search(r"аналитик|analyst", t):
        return "review"
    return "excluded"


def filter_dataframe(df: pd.DataFrame) -> dict:
    """Раскладывает датафрейм с колонкой title на три корзины, сохраняет файлы."""
    df = df.copy()
    df["category"] = df["title"].apply(classify_title)
    stats = {}
    for category, out_file in [
        ("relevant", config.RELEVANT_FILE),
        ("excluded", config.EXCLUDED_FILE),
        ("review", config.REVIEW_FILE),
    ]:
        part = df[df["category"] == category].drop(columns=["category"])
        part.to_csv(out_file, index=False, encoding="utf-8-sig")
        stats[category] = len(part)
        log(f"{category}: {len(part)} -> {out_file}")
        for title in part["title"].head(7):
            log(f"    пример: {title}")
    return stats


if __name__ == "__main__":
    log("=" * 60)
    log("ФИЛЬТРАЦИЯ ВАКАНСИЙ ПО НАЗВАНИЮ")
    log("=" * 60)
    filename = config.DEDUP_FILE if os.path.exists(config.DEDUP_FILE) else config.RAW_FILE
    log(f"Чтение файла: {filename}")
    df = pd.read_csv(filename, dtype={"vacancy_id": str})
    log(f"Всего вакансий: {len(df)}")
    stats = filter_dataframe(df)
    log("=" * 60)
    log(f"ИТОГ: целевых {stats['relevant']}, мусор {stats['excluded']}, "
        f"на проверку {stats['review']}")
    log("Проверь глазами review и excluded. Если целевые вакансии попали в мусор, "
        "добавь паттерн в RELEVANT_PATTERNS и запусти скрипт снова.")