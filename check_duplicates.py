"""
Проверка дубликатов в файле ссылок перед этапом 2.
"""

import pandas as pd
import re

import config


def extract_vacancy_id(url: str) -> str:
    match = re.search(r"/vacancy/(\d+)", url)
    return match.group(1) if match else None


def check_duplicates(filename: str) -> dict:
    df = pd.read_csv(filename)
    df["vacancy_id"] = df["vacancy_url"].apply(extract_vacancy_id) if "vacancy_url" in df.columns \
        else df["url"].apply(extract_vacancy_id)
    return {
        "total_links": len(df),
        "url_duplicates": int(df["url"].duplicated().sum()) if "url" in df.columns
                          else int(df["vacancy_url"].duplicated().sum()),
        "id_duplicates": int(df["vacancy_id"].duplicated().sum()),
        "invalid_urls": int(df["vacancy_id"].isna().sum()),
        "unique_vacancies": int(df["vacancy_id"].nunique()),
    }


if __name__ == "__main__":
    stats = check_duplicates(config.LINKS_FILE)
    print("=" * 50)
    print("РЕЗУЛЬТАТ ПРОВЕРКИ ДУБЛИКАТОВ")
    print("=" * 50)
    for key, value in stats.items():
        print(f"{key}: {value}")
    if stats["id_duplicates"] == 0 and stats["invalid_urls"] == 0:
        print("Дубликатов нет. Файл готов к этапу 2.")
    else:
        print("Есть проблемы. Этап 2 отфильтрует их автоматически.")