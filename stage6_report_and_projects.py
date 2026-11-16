"""
Этап 6: Визуализация, Excel-отчёт и ранжирование идей пет-проектов.

Вход:  stage5_ranked_final.csv
Выход: папка stage6_output/ с графиками, Excel, markdown и CSV.
"""

import os
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

import config


INPUT_FILE = getattr(config, "STAGE5_RANKED_FILE", "stage5_ranked_final.csv")
OUTPUT_DIR = "results"

plt.rcParams["font.family"] = "DejaVu Sans"
sns.set_theme(style="whitegrid")


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


# ============================================================
# ИДЕИ ПЕТ-ПРОЕКТОВ
# ============================================================

PROJECTS = [
    {
        "name": "Продуктовый дашборд маркетплейса с A/B тестами",
        "description": (
            "Дашборд продуктовых метрик (воронки, retention, когорты) на данных "
            "маркетплейса + модуль проведения и оценки A/B тестов."
        ),
        "tools": ["SQL", "Python", "Power BI", "pandas", "PostgreSQL", "Git"],
        "methods": ["A/B тестирование", "Статистический анализ", "Проверка гипотез",
                    "Воронки", "Когортный анализ", "Сегментация", "Продуктовые метрики"],
        "tasks": ["Построение дашбордов", "Подготовка отчетов", "Ad-hoc анализ",
                  "Мониторинг метрик", "Создание визуализаций"],
        "deliverables": [
            "SQL-витрины в PostgreSQL",
            "Python-скрипт расчёта метрик и A/B",
            "Дашборд Power BI",
            "README с методологией и выводами",
        ],
    },
    {
        "name": "ETL-пайплайн и витрина данных",
        "description": (
            "Автоматизированный пайплайн: сбор данных из источников, очистка, "
            "загрузка в DWH, построение витрин и контроль качества."
        ),
        "tools": ["SQL", "Python", "Airflow", "ClickHouse", "PostgreSQL", "Git", "Docker", "dbt"],
        "methods": ["ETL", "DWH", "Data Quality", "Моделирование данных"],
        "tasks": ["Сбор данных", "Очистка данных", "Разработка витрин",
                  "Автоматизация отчетности", "Оптимизация запросов"],
        "deliverables": [
            "Airflow DAG",
            "Схема DWH и витрин",
            "Скрипты проверок качества данных",
            "Дашборд поверх витрин",
        ],
    },
    {
        "name": "Когортный анализ и retention для подписочного сервиса",
        "description": (
            "Когортный анализ, RFM-сегментация, расчёт LTV/CAC/retention/churn "
            "и рекомендации по удержанию."
        ),
        "tools": ["SQL", "Python", "pandas", "Power BI", "Excel"],
        "methods": ["Когортный анализ", "RFM", "Сегментация", "Retention",
                    "Churn", "LTV", "CAC", "Продуктовые метрики"],
        "tasks": ["Ad-hoc анализ", "Подготовка отчетов", "Презентация результатов",
                  "Создание визуализаций"],
        "deliverables": [
            "Ноутбук с когортами и RFM",
            "Дашборд retention/LTV",
            "Презентация с рекомендациями",
        ],
    },
    {
        "name": "Поиск аномалий в финансовых транзакциях (финтех)",
        "description": (
            "Система мониторинга транзакций: статистические правила и ML-модель "
            "для поиска аномалий, алерты и дашборд расследований."
        ),
        "tools": ["SQL", "Python", "pandas", "scikit-learn", "ClickHouse", "PostgreSQL"],
        "methods": ["Поиск аномалий", "Статистический анализ", "ML",
                    "Классификация", "Временные ряды"],
        "tasks": ["Мониторинг метрик", "Ad-hoc анализ", "Подготовка отчетов",
                  "Очистка данных"],
        "deliverables": [
            "Ноутбук с baseline и моделью",
            "Скрипт инференса и алертов",
            "Дашборд аномалий",
            "Отчёт о precision/recall",
        ],
    },
    {
        "name": "Прогнозирование спроса или оттока",
        "description": (
            "Модель прогноза временного ряда или оттока клиентов: feature engineering, "
            "валидация, интерпретация и визуализация прогнозов."
        ),
        "tools": ["Python", "pandas", "scikit-learn", "SQL", "Jupyter"],
        "methods": ["Прогнозирование", "Временные ряды", "Регрессионный анализ",
                    "Классификация", "ML"],
        "tasks": ["Очистка данных", "Создание визуализаций", "Презентация результатов",
                  "Подготовка отчетов"],
        "deliverables": [
            "Ноутбук с валидацией",
            "Модель и пайплайн признаков",
            "Графики прогнозов и ошибок",
            "README с метриками",
        ],
    },
    {
        "name": "Автоматизация Excel/Power Query отчётности",
        "description": (
            "Перевод ручной отчётности в автоматизированную: Power Query, модель "
            "данных, дашборд Power BI и регламент обновления."
        ),
        "tools": ["Excel", "Power BI", "SQL", "Power query"],
        "methods": ["Data Quality"],
        "tasks": ["Подготовка отчетов", "Автоматизация отчетности",
                  "Построение дашбордов", "Создание визуализаций"],
        "deliverables": [
            "Power Query шаблон",
            "Модель данных Power BI",
            "Инструкция по обновлению",
        ],
    },
]


# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================

def load_ranked() -> pd.DataFrame:
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Не найден {INPUT_FILE}. Сначала выполни этап 5.")
    df = pd.read_csv(INPUT_FILE)
    df["share_pct"] = pd.to_numeric(df["share_pct"], errors="coerce").fillna(0)
    df["vacancy_count"] = pd.to_numeric(df["vacancy_count"], errors="coerce").fillna(0).astype(int)
    return df


def infer_total_vacancies(df: pd.DataFrame) -> int:
    row = df[df["share_pct"] > 0].iloc[0]
    return int(round(row["vacancy_count"] * 100 / row["share_pct"]))


# ============================================================
# ВИЗУАЛИЗАЦИЯ
# ============================================================

def plot_top(df: pd.DataFrame, category: str, title: str, filename: str, n: int = 15) -> None:
    part = df[df["category"] == category].head(n).copy()
    if part.empty:
        log(f"Нет данных для графика {category}", level="WARNING")
        return

    part = part.iloc[::-1]
    height = max(4, 0.4 * len(part))
    plt.figure(figsize=(11, height))
    sns.barplot(data=part, y="canonical_item", x="share_pct", color="#4C72B0")

    for i, (share, count) in enumerate(zip(part["share_pct"], part["vacancy_count"])):
        plt.text(min(share + 1, 99), i, f"{share:.1f}% ({count})", va="center", fontsize=9)

    plt.xlim(0, 100)
    plt.xlabel("Доля вакансий, %")
    plt.ylabel("")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    log(f"График сохранён: {filename}")


# ============================================================
# ОЦЕНКА ПЕТ-ПРОЕКТОВ
# ============================================================

def score_projects(df: pd.DataFrame) -> tuple:
    share_map = {
        (row["category"], str(row["canonical_item"]).lower()): float(row["share_pct"])
        for _, row in df.iterrows()
    }

    project_rows = []
    coverage_rows = []

    for project in PROJECTS:
        total_score = 0.0
        covered_count = 0

        for category, field in [("tool", "tools"), ("method", "methods"), ("task", "tasks")]:
            for item in project[field]:
                key = (category, item.lower())
                if key in share_map:
                    share = share_map[key]
                    total_score += share
                    covered_count += 1
                    coverage_rows.append({
                        "project": project["name"],
                        "category": category,
                        "requirement": item,
                        "share_pct": share,
                    })

        project_rows.append({
            "name": project["name"],
            "score": round(total_score, 2),
            "covered_requirements": covered_count,
            "description": project["description"],
            "stack": ", ".join(project["tools"]),
            "deliverables": "; ".join(project["deliverables"]),
        })

    projects_df = pd.DataFrame(project_rows).sort_values("score", ascending=False).reset_index(drop=True)
    coverage_df = pd.DataFrame(coverage_rows)
    return projects_df, coverage_df


def find_learning_gaps(df: pd.DataFrame, best_project: dict) -> pd.DataFrame:
    """Топ-требования, которые лучший проект не покрывает — зоны для изучения."""
    covered = set()
    for field, category in [("tools", "tool"), ("methods", "method"), ("tasks", "task")]:
        for item in best_project[field]:
            covered.add((category, item.lower()))

    top = df[df["category"].isin(["tool", "method", "task"])].head(30)
    gaps = top[~top.apply(lambda r: (r["category"], str(r["canonical_item"]).lower()) in covered, axis=1)]
    return gaps.head(10)


# ============================================================
# ОТЧЁТЫ
# ============================================================

def write_markdown(df: pd.DataFrame, projects_df: pd.DataFrame,
                   gaps_df: pd.DataFrame, total_vacancies: int, filename: str) -> None:
    lines = [
        "# Анализ требований вакансий аналитика данных",
        "",
        f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Вакансий в выборке: {total_vacancies}",
        "",
        "## Топ инструментов",
        "",
    ]

    for _, row in df[df["category"] == "tool"].head(10).iterrows():
        lines.append(f"- {row['canonical_item']}: {row['share_pct']}% ({row['vacancy_count']})")

    lines += ["", "## Топ методов", ""]
    for _, row in df[df["category"] == "method"].head(10).iterrows():
        lines.append(f"- {row['canonical_item']}: {row['share_pct']}% ({row['vacancy_count']})")

    lines += ["", "## Топ задач", ""]
    for _, row in df[df["category"] == "task"].head(10).iterrows():
        lines.append(f"- {row['canonical_item']}: {row['share_pct']}% ({row['vacancy_count']})")

    lines += ["", "## Рекомендуемые пет-проекты (по покрытию требований)", ""]
    for idx, row in projects_df.head(3).iterrows():
        lines.append(f"### {idx + 1}. {row['name']}")
        lines.append(f"Score покрытия: {row['score']} | закрыто требований: {row['covered_requirements']}")
        lines.append("")
        lines.append(row["description"])
        lines.append("")
        lines.append(f"Стек: {row['stack']}")
        lines.append(f"Артефакты: {row['deliverables']}")
        lines.append("")

    if not gaps_df.empty:
        lines += ["", "## Что доизучить (топ-требования вне лучшего проекта)", ""]
        for _, row in gaps_df.iterrows():
            lines.append(f"- {row['canonical_item']} ({row['category']}): {row['share_pct']}%")

    lines += [
        "",
        "## Ограничения",
        "",
        f"- Выборка {total_vacancies} вакансий; проценты нестабильны при малом n.",
        "- Для финальных выводов расширь выборку до 300-500 вакансий и перезапусти этапы 1-6.",
    ]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"Markdown-отчёт сохранён: {filename}")


def write_excel(df: pd.DataFrame, projects_df: pd.DataFrame,
                coverage_df: pd.DataFrame, total_vacancies: int, filename: str) -> None:
    summary = pd.DataFrame({
        "metric": ["total_vacancies", "unique_requirements", "tools", "methods", "tasks"],
        "value": [
            total_vacancies,
            len(df),
            int((df["category"] == "tool").sum()),
            int((df["category"] == "method").sum()),
            int((df["category"] == "task").sum()),
        ],
    })

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        df[df["category"] == "tool"].to_excel(writer, sheet_name="tools", index=False)
        df[df["category"] == "method"].to_excel(writer, sheet_name="methods", index=False)
        df[df["category"] == "task"].to_excel(writer, sheet_name="tasks", index=False)
        projects_df.to_excel(writer, sheet_name="pet_projects", index=False)
        coverage_df.to_excel(writer, sheet_name="project_coverage", index=False)

    log(f"Excel-отчёт сохранён: {filename}")


# ============================================================
# ЗАПУСК
# ============================================================

def run_stage6() -> dict:
    log("=" * 60)
    log("ЭТАП 6: ВИЗУАЛИЗАЦИЯ И ПЕТ-ПРОЕКТЫ")
    log("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_ranked()
    total_vacancies = infer_total_vacancies(df)
    log(f"Вакансий: {total_vacancies}, уникальных требований: {len(df)}")

    plot_top(df, "tool", "Топ инструментов аналитика данных",
             os.path.join(OUTPUT_DIR, "top_tools.png"))
    plot_top(df, "method", "Топ методов и методологий",
             os.path.join(OUTPUT_DIR, "top_methods.png"))
    plot_top(df, "task", "Топ задач аналитика данных",
             os.path.join(OUTPUT_DIR, "top_tasks.png"))

    projects_df, coverage_df = score_projects(df)
    projects_df.to_csv(os.path.join(OUTPUT_DIR, "pet_projects_ranked.csv"),
                       index=False, encoding="utf-8-sig")
        # Топ-таблицы по категориям (для итогового отчёта)
    for category, filename in [
        ("tool", "top_tools.csv"),
        ("method", "top_methods.csv"),
        ("task", "top_tasks.csv"),
    ]:
        part = df[df["category"] == category].head(30)
        part.to_csv(os.path.join(OUTPUT_DIR, filename),
                    index=False, encoding="utf-8-sig")

    # Общий топ-30 всех требований
    df.head(30).to_csv(os.path.join(OUTPUT_DIR, "top_all.csv"),
                       index=False, encoding="utf-8-sig")
    coverage_df.to_csv(os.path.join(OUTPUT_DIR, "project_coverage.csv"),
                       index=False, encoding="utf-8-sig")

    log("Рейтинг пет-проектов:")
    for _, row in projects_df.iterrows():
        log(f"  {row['name']}: score {row['score']}, требований {row['covered_requirements']}")

    best_project = PROJECTS[[p["name"] for p in PROJECTS].index(projects_df.iloc[0]["name"])]
    gaps_df = find_learning_gaps(df, best_project)

    write_excel(df, projects_df, coverage_df, total_vacancies,
                os.path.join(OUTPUT_DIR, "report.xlsx"))
    write_markdown(df, projects_df, gaps_df, total_vacancies,
                   os.path.join(OUTPUT_DIR, "report.md"))

    log("=" * 60)
    log("ЭТАП 6 ЗАВЕРШЕН")
    log("=" * 60)
    log(f"Все результаты в папке: {OUTPUT_DIR}")
    log(f"Лучший пет-проект: {projects_df.iloc[0]['name']}")

    return {"projects": len(projects_df), "best": projects_df.iloc[0]["name"]}


if __name__ == "__main__":
    run_stage6()