"""
Этап 3: Очистка и подготовка текста вакансий.

Вход:  vacancies_relevant.csv
Выход: vacancies_clean.csv
       stage3_report.csv

Что делает:
1. Очищает описание от мусора и нормализует пробелы.
2. Делит описание на блоки: задачи, требования, будет плюсом, условия, о компании.
3. Нормализует ключевые навыки.
4. Собирает analysis_text для этапа 4.
5. Добавляет role_group и seniority_hint для будущей сегментации.
"""

import pandas as pd
import re
import os
import html
import time
from datetime import datetime

import config


INPUT_FILE = config.RELEVANT_FILE
OUTPUT_FILE = getattr(config, "CLEAN_FILE", "vacancies_clean.csv")
REPORT_FILE = getattr(config, "CLEAN_REPORT_FILE", "stage3_report.csv")


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


# ============================================================
# ОЧИСТКА ТЕКСТА
# ============================================================

def normalize_text(value) -> str:
    """Базовая нормализация: юникод, пробелы, переносы, маркеры списков."""
    text = "" if value is None else str(value)
    text = html.unescape(text)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\xad", "")

    # Маркеры списков превращаем в обычные строки списка
    text = re.sub(r"[•●▪◦·]", "\n- ", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize_inline(value) -> str:
    """Нормализация одной строки: все пробелы схлопываются в один."""
    return re.sub(r"\s+", " ", normalize_text(value)).strip()


def clean_description(value) -> str:
    """Очистка описания вакансии. Переносы строк сохраняем."""
    text = normalize_text(value)

    # Убираем ссылки и почту, они не нужны для анализа требований
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", " ", text)

    # Убираем служебные фразы, если они попали в описание
    text = re.sub(
        r"(?i)\b(откликнуться|поделиться вакансией|сохранить вакансию)\b",
        " ",
        text
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


# ============================================================
# РАЗДЕЛЕНИЕ ОПИСАНИЯ НА СМЫСЛОВЫЕ БЛОКИ
# ============================================================

SECTION_PATTERNS = [
    ("plus", [
        r"будет плюсом",
        r"плюсом будет",
        r"желательно",
        r"nice to have",
        r"would be a plus",
        r"дополнительно",
    ]),
    ("requirements", [
        r"требован",
        r"что мы ждем",
        r"что мы ожидаем",
        r"наши ожидания",
        r"ожидания от вас",
        r"требования к кандидату",
        r"requirements",
        r"qualifications",
        r"must have",
        r"hard skills",
        r"\bнавыки\b",
        r"что нужно",
        r"что необходимо",
    ]),
    ("tasks", [
        r"обязанност",
        r"\bзадачи\b",
        r"чем предстоит заниматься",
        r"что предстоит делать",
        r"чем будешь заниматься",
        r"ваши задачи",
        r"основные задачи",
        r"responsibilit",
        r"what you will do",
        r"what you'll do",
    ]),
    ("conditions", [
        r"\bусловия\b",
        r"мы предлагаем",
        r"что мы предлагаем",
        r"benefits",
        r"what we offer",
        r"компенсац",
        r"зарплата",
    ]),
    ("about", [
        r"о компании",
        r"о нас",
        r"о проекте",
        r"о команде",
        r"about us",
        r"about the company",
    ]),
]


def detect_section(line: str):
    """Определяет, является ли строка заголовком блока."""
    s = normalize_inline(line).lower().replace("ё", "е")
    s = re.sub(r"[:：]+$", "", s).strip()

    if not s or len(s) > 90:
        return None
    if s.startswith("- "):
        return None

    for section, patterns in SECTION_PATTERNS:
        if any(re.search(p, s) for p in patterns):
            return section

    return None


def split_sections(description: str) -> dict:
    """Делит описание на блоки. Если заголовков нет, текст попадает в other."""
    sections = {
        "tasks": [],
        "requirements": [],
        "plus": [],
        "conditions": [],
        "about": [],
        "other": [],
    }

    current = "other"

    for raw_line in str(description).split("\n"):
        line = normalize_inline(raw_line)
        if not line:
            continue

        section = detect_section(line)
        if section:
            current = section
            continue

        sections[current].append(line)

    return {
        "tasks_text": "\n".join(sections["tasks"]),
        "requirements_text": "\n".join(sections["requirements"]),
        "plus_text": "\n".join(sections["plus"]),
        "conditions_text": "\n".join(sections["conditions"]),
        "about_text": "\n".join(sections["about"]),
        "other_text": "\n".join(sections["other"]),
    }


# ============================================================
# КЛЮЧЕВЫЕ НАВЫКИ
# ============================================================

def split_skills(raw) -> list:
    """Разбивает строку ключевых навыков на список."""
    raw = normalize_inline(raw)
    if not raw:
        return []

    parts = raw.split(";") if ";" in raw else raw.split(",")

    result = []
    seen = set()

    for part in parts:
        skill = normalize_inline(part).strip(" -•\t")
        if not skill or len(skill) > 80:
            continue

        key = skill.lower().replace("ё", "е")
        if key not in seen:
            seen.add(key)
            result.append(skill)

    return result


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ ПРИЗНАКИ
# ============================================================

def parse_experience_min(value) -> int:
    """Минимальный опыт из строки HH. Нет опыта -> 0."""
    s = normalize_inline(value).lower()
    if not s:
        return None
    if "нет опыта" in s:
        return 0

    numbers = re.findall(r"\d+", s)
    return int(numbers[0]) if numbers else None


def classify_role_group(title: str) -> str:
    """Грубая группа роли: data / product / mixed / other."""
    t = normalize_inline(title).lower()

    is_product = bool(re.search(r"продукт|product", t))
    is_data = bool(re.search(r"данн|data|bi|дата", t))

    if is_product and is_data:
        return "mixed"
    if is_product:
        return "product"
    if is_data:
        return "data"
    return "other"


def classify_seniority(title: str, experience: str) -> str:
    """Грубая оценка грейда по названию и опыту."""
    t = normalize_inline(title).lower()
    e = normalize_inline(experience).lower()
    text = f"{t} {e}"

    if re.search(r"руководитель|head|chief|директор|team lead|teamlead", text):
        return "lead"
    if re.search(r"senior|старший|ведущий|principal|lead", text):
        return "senior"
    if re.search(r"junior|младший|intern|стажер|стажёр|без опыта|нет опыта", text):
        return "junior"
    if re.search(r"middle", text):
        return "middle"
    return "unknown"


def build_analysis_text(row) -> str:
    """
    Текст для этапа 4.
    Исключаем conditions и about, чтобы не считать ДМС, офис и печеньки требованиями.
    """
    parts = [
        row.get("key_skills_clean", ""),
        row.get("requirements_text", ""),
        row.get("plus_text", ""),
        row.get("tasks_text", ""),
        row.get("other_text", ""),
    ]
    return "\n".join(p for p in parts if p).strip()


# ============================================================
# ЧТЕНИЕ И ПОДГОТОВКА ДАННЫХ
# ============================================================

def safe_read_csv(filename: str) -> pd.DataFrame:
    if not os.path.exists(filename):
        return pd.DataFrame()
    try:
        return pd.read_csv(filename, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def prepare_dataframe(df: pd.DataFrame) -> tuple:
    df = df.copy().fillna("")

    required_columns = [
        "vacancy_id", "url", "title", "company", "description",
        "key_skills", "experience", "location", "salary_text"
    ]
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df["title"] = df["title"].apply(normalize_inline)
    df["company"] = df["company"].apply(normalize_inline)
    df["location"] = df["location"].apply(normalize_inline)
    df["experience"] = df["experience"].apply(normalize_inline)

    df["description_clean"] = df["description"].apply(clean_description)

    sections_df = pd.DataFrame(
        df["description_clean"].apply(split_sections).tolist(),
        index=df.index
    )
    df = pd.concat([df, sections_df], axis=1)

    skills_lists = df["key_skills"].apply(split_skills)
    df["key_skills_clean"] = skills_lists.apply(lambda x: "; ".join(x))
    df["key_skills_norm"] = skills_lists.apply(
        lambda x: "; ".join(skill.lower().replace("ё", "е") for skill in x)
    )
    df["skills_count"] = skills_lists.apply(len)

    df["experience_min"] = df["experience"].apply(parse_experience_min)
    df["role_group"] = df["title"].apply(classify_role_group)
    df["seniority_hint"] = df.apply(
        lambda row: classify_seniority(row["title"], row["experience"]),
        axis=1
    )

    df["analysis_text"] = df.apply(build_analysis_text, axis=1)
    df["description_len"] = df["description_clean"].str.len()
    df["analysis_len"] = df["analysis_text"].str.len()

    output_columns = [
        "vacancy_id", "url", "title", "company", "salary_text",
        "experience", "experience_min", "location",
        "role_group", "seniority_hint",
        "description_clean",
        "tasks_text", "requirements_text", "plus_text",
        "conditions_text", "about_text", "other_text",
        "key_skills_clean", "key_skills_norm", "skills_count",
        "analysis_text", "description_len", "analysis_len",
    ]

    clean_df = df[output_columns].copy()

    report_df = pd.DataFrame({
        "vacancy_id": clean_df["vacancy_id"],
        "title": clean_df["title"],
        "role_group": clean_df["role_group"],
        "seniority_hint": clean_df["seniority_hint"],
        "description_len": clean_df["description_len"],
        "analysis_len": clean_df["analysis_len"],
        "skills_count": clean_df["skills_count"],
        "has_tasks": clean_df["tasks_text"].str.len() > 0,
        "has_requirements": clean_df["requirements_text"].str.len() > 0,
        "has_plus": clean_df["plus_text"].str.len() > 0,
        "has_conditions": clean_df["conditions_text"].str.len() > 0,
        "has_about": clean_df["about_text"].str.len() > 0,
        "has_other": clean_df["other_text"].str.len() > 0,
    })

    stats = {
        "input_rows": len(df),
        "output_rows": len(clean_df),
        "empty_description": int((clean_df["description_len"] == 0).sum()),
        "avg_description_len": float(clean_df["description_len"].mean()) if len(clean_df) else 0,
        "median_description_len": float(clean_df["description_len"].median()) if len(clean_df) else 0,
        "with_tasks": int((clean_df["tasks_text"].str.len() > 0).sum()),
        "with_requirements": int((clean_df["requirements_text"].str.len() > 0).sum()),
        "with_plus": int((clean_df["plus_text"].str.len() > 0).sum()),
        "with_conditions": int((clean_df["conditions_text"].str.len() > 0).sum()),
        "with_skills": int((clean_df["skills_count"] > 0).sum()),
        "role_groups": clean_df["role_group"].value_counts().to_dict(),
        "seniority": clean_df["seniority_hint"].value_counts().to_dict(),
    }

    return clean_df, report_df, stats


# ============================================================
# ЗАПУСК
# ============================================================

def run_stage3() -> dict:
    log("=" * 60)
    log("ЭТАП 3: ОЧИСТКА И ПОДГОТОВКА ТЕКСТА")
    log("=" * 60)
    log(f"Входной файл: {INPUT_FILE}")

    df = safe_read_csv(INPUT_FILE)
    if df.empty:
        log("Входной файл пуст или не найден. Этап 3 остановлен.", level="WARNING")
        return {}

    log(f"Прочитано вакансий: {len(df)}")

    clean_df, report_df, stats = prepare_dataframe(df)

    clean_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    report_df.to_csv(REPORT_FILE, index=False, encoding="utf-8-sig")

    log(f"Очищенные данные сохранены: {len(clean_df)} -> {OUTPUT_FILE}")
    log(f"Отчёт по качеству сохранён: {REPORT_FILE}")

    log("-" * 60)
    log("СТАТИСТИКА:")
    log(f"  Пустых описаний: {stats['empty_description']}")
    log(f"  Средняя длина описания: {stats['avg_description_len']:.0f} символов")
    log(f"  Медианная длина описания: {stats['median_description_len']:.0f} символов")
    log(f"  Найден блок задач: {stats['with_tasks']}")
    log(f"  Найден блок требований: {stats['with_requirements']}")
    log(f"  Найден блок 'будет плюсом': {stats['with_plus']}")
    log(f"  Найден блок условий: {stats['with_conditions']}")
    log(f"  Есть ключевые навыки: {stats['with_skills']}")
    log(f"  Группы ролей: {stats['role_groups']}")
    log(f"  Грейды: {stats['seniority']}")

    log("=" * 60)
    log("ЭТАП 3 ЗАВЕРШЕН")
    log("=" * 60)
    log(f"Файл для этапа 4: {OUTPUT_FILE}")

    return stats


if __name__ == "__main__":
    start = time.time()
    run_stage3()
    log(f"Общее время: {(time.time() - start):.1f} сек")