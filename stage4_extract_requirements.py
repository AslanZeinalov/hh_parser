"""
Этап 4: Извлечение требований, задач и навыков из вакансий.

Гибридный подход:
1. Словарь + регулярки: инструменты, методы, часть задач.
2. LLM API: задачи, soft skills, домен.

Считаем релевантность по числу вакансий, где встретился пункт,
а не по общему числу упоминаний в тексте.
"""

import os
import re
import json
import time
import hashlib
from datetime import datetime

import pandas as pd

try:
    import requests
except ImportError:
    requests = None

import config


INPUT_FILE = getattr(config, "CLEAN_FILE", "vacancies_clean.csv")

USE_LLM = getattr(config, "USE_LLM", True)
LLM_API_KEY_ENV = getattr(config, "LLM_API_KEY_ENV", "OPENROUTER_API_KEY")
LLM_BASE_URL = getattr(config, "LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
LLM_MODEL = getattr(config, "LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
LLM_TIMEOUT = getattr(config, "LLM_TIMEOUT", 60)
LLM_MAX_RETRIES = getattr(config, "LLM_MAX_RETRIES", 3)
LLM_SLEEP_BETWEEN_CALLS = getattr(config, "LLM_SLEEP_BETWEEN_CALLS", 2.0)
LLM_MAX_CHARS = getattr(config, "LLM_MAX_CHARS", 6000)
LLM_CACHE_FILE = getattr(config, "LLM_CACHE_FILE", "llm_cache.json")

ITEMS_FILE = getattr(config, "STAGE4_ITEMS_FILE", "stage4_items_by_vacancy.csv")
RANKED_FILE = getattr(config, "STAGE4_RANKED_FILE", "stage4_ranked_all.csv")
VACANCIES_FILE = getattr(config, "STAGE4_VACANCIES_FILE", "stage4_extracted_by_vacancy.csv")
TOOLS_FILE = getattr(config, "STAGE4_TOOLS_FILE", "stage4_tools_ranked.csv")
METHODS_FILE = getattr(config, "STAGE4_METHODS_FILE", "stage4_methods_ranked.csv")
TASKS_FILE = getattr(config, "STAGE4_TASKS_FILE", "stage4_tasks_ranked.csv")

PROMPT_VERSION = "stage4_v1"

llm_available = True


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


# ============================================================
# СЛОВАРЬ ТРЕБОВАНИЙ
# ============================================================

DICTIONARY = [
    # Languages and libraries
    {"canonical": "SQL", "category": "tool", "aliases": ["sql", "sql-запросы", "запросы sql"]},
    {"canonical": "Python", "category": "tool", "aliases": ["python", "python3", "питон"]},
    {"canonical": "pandas", "category": "tool", "aliases": ["pandas"]},
    {"canonical": "NumPy", "category": "tool", "aliases": ["numpy"]},
    {"canonical": "scikit-learn", "category": "tool", "aliases": ["scikit-learn", "sklearn", "scikit learn"]},
    {"canonical": "Jupyter", "category": "tool", "aliases": ["jupyter", "jupyter notebook"]},
    {"canonical": "Git", "category": "tool", "aliases": ["git", "github", "gitlab"]},
    {"canonical": "Docker", "category": "tool", "aliases": ["docker"]},
    {"canonical": "Linux", "category": "tool", "aliases": ["linux", "unix"]},
    {"canonical": "Bash", "category": "tool", "aliases": ["bash", "shell"]},
    {"canonical": "API", "category": "tool", "aliases": ["api", "rest api", "restful"]},
    {"canonical": "JSON", "category": "tool", "aliases": ["json"]},
    {"canonical": "XML", "category": "tool", "aliases": ["xml"]},

    # BI and Excel
    {"canonical": "Excel", "category": "tool", "aliases": ["excel", "ms excel", "microsoft excel", "эксель"]},
    {"canonical": "Power BI", "category": "tool", "aliases": ["power bi", "powerbi", "power bi desktop", "пауэр би", "павер би"]},
    {"canonical": "Tableau", "category": "tool", "aliases": ["tableau"]},
    {"canonical": "Looker", "category": "tool", "aliases": ["looker"]},
    {"canonical": "Superset", "category": "tool", "aliases": ["superset", "apache superset"]},
    {"canonical": "Metabase", "category": "tool", "aliases": ["metabase"]},
    {"canonical": "Qlik", "category": "tool", "aliases": ["qlik", "qlikview", "qlik sense"]},
    {"canonical": "DataLens", "category": "tool", "aliases": ["datalens", "data lens", "yandex datalens"]},

    # Databases and storage
    {"canonical": "PostgreSQL", "category": "tool", "aliases": ["postgresql", "postgres", "постгрес"]},
    {"canonical": "MySQL", "category": "tool", "aliases": ["mysql"]},
    {"canonical": "ClickHouse", "category": "tool", "aliases": ["clickhouse", "кликхаус"]},
    {"canonical": "MS SQL Server", "category": "tool", "aliases": ["ms sql", "sql server", "mssql", "ms sql server"]},
    {"canonical": "Oracle", "category": "tool", "aliases": ["oracle"]},
    {"canonical": "BigQuery", "category": "tool", "aliases": ["bigquery", "big query"]},
    {"canonical": "Redis", "category": "tool", "aliases": ["redis"]},
    {"canonical": "MongoDB", "category": "tool", "aliases": ["mongodb", "mongo"]},
    {"canonical": "Greenplum", "category": "tool", "aliases": ["greenplum"]},
    {"canonical": "Snowflake", "category": "tool", "aliases": ["snowflake"]},

    # Data engineering
    {"canonical": "Airflow", "category": "tool", "aliases": ["airflow", "apache airflow"]},
    {"canonical": "dbt", "category": "tool", "aliases": ["dbt"]},
    {"canonical": "Spark", "category": "tool", "aliases": ["spark", "apache spark", "pyspark"]},
    {"canonical": "Kafka", "category": "tool", "aliases": ["kafka", "apache kafka"]},
    {"canonical": "Hadoop", "category": "tool", "aliases": ["hadoop"]},
    {"canonical": "ETL", "category": "method", "aliases": ["etl", "elt"]},
    {"canonical": "DWH", "category": "method", "aliases": ["dwh", "data warehouse", "хранилище данных", "витрины данных"]},
    {"canonical": "Data Quality", "category": "method", "aliases": ["data quality", "качество данных"]},
    {"canonical": "Моделирование данных", "category": "method", "aliases": ["моделирование данных", "data modeling", "модель данных"]},

    # Statistics and ML
    {"canonical": "Статистический анализ", "category": "method", "aliases": ["статистика", "статистический анализ", "математическая статистика", "mathematical statistics"]},
    {"canonical": "A/B тестирование", "category": "method", "aliases": ["a/b", "a/b тесты", "a/b тестирование", "аб тесты", "аб-тесты", "сплит-тесты", "split testing"]},
    {"canonical": "Проверка гипотез", "category": "method", "aliases": ["проверка гипотез", "гипотезы", "hypothesis testing"]},
    {"canonical": "Регрессионный анализ", "category": "method", "aliases": ["регрессия", "регрессионный анализ", "regression"]},
    {"canonical": "Классификация", "category": "method", "aliases": ["классификация", "classification"]},
    {"canonical": "Кластеризация", "category": "method", "aliases": ["кластеризация", "clustering"]},
    {"canonical": "Временные ряды", "category": "method", "aliases": ["временные ряды", "time series"]},
    {"canonical": "Прогнозирование", "category": "method", "aliases": ["прогнозирование", "forecasting", "прогноз"]},
    {"canonical": "ML", "category": "method", "aliases": ["ml", "машинное обучение", "machine learning"]},
    {"canonical": "Deep Learning", "category": "method", "aliases": ["deep learning", "глубокое обучение"]},
    {"canonical": "NLP", "category": "method", "aliases": ["nlp", "natural language processing"]},
    {"canonical": "Поиск аномалий", "category": "method", "aliases": ["аномалии", "поиск аномалий", "anomaly detection"]},

    # Product analytics
    {"canonical": "Продуктовые метрики", "category": "method", "aliases": ["продуктовые метрики", "product metrics", "метрики продукта"]},
    {"canonical": "Unit-экономика", "category": "method", "aliases": ["unit-экономика", "юнит-экономика", "unit economics", "юнит экономика"]},
    {"canonical": "Когортный анализ", "category": "method", "aliases": ["когортный анализ", "когорты", "cohort analysis"]},
    {"canonical": "RFM", "category": "method", "aliases": ["rfm", "rfm-анализ"]},
    {"canonical": "Воронки", "category": "method", "aliases": ["воронки", "воронка", "funnel", "funnel analysis"]},
    {"canonical": "Retention", "category": "method", "aliases": ["retention", "удержание"]},
    {"canonical": "Churn", "category": "method", "aliases": ["churn", "отток"]},
    {"canonical": "LTV", "category": "method", "aliases": ["ltv", "lifetime value"]},
    {"canonical": "CAC", "category": "method", "aliases": ["cac", "стоимость привлечения"]},
    {"canonical": "ARPU", "category": "method", "aliases": ["arpu", "arppu"]},
    {"canonical": "DAU/MAU", "category": "method", "aliases": ["dau", "mau", "wau", "dau/mau"]},
    {"canonical": "Сегментация", "category": "method", "aliases": ["сегментация", "segmentation"]},

    # Tasks
    {"canonical": "Построение дашбордов", "category": "task", "aliases": ["дашборды", "dashboards", "построение дашбордов", "разработка дашбордов", "визуализация данных"]},
    {"canonical": "Автоматизация отчетности", "category": "task", "aliases": ["автоматизация отчетности", "автоматизация отчётов", "автоматизировать отчетность"]},
    {"canonical": "Ad-hoc анализ", "category": "task", "aliases": ["ad-hoc", "adhoc", "ad hoc", "точечные исследования", "разовые запросы"]},
    {"canonical": "Подготовка отчетов", "category": "task", "aliases": ["подготовка отчетов", "подготовка отчётов", "формирование отчетности", "отчетность"]},
    {"canonical": "Сбор требований", "category": "task", "aliases": ["сбор требований", "выявление требований", "работа с требованиями"]},
    {"canonical": "Презентация результатов", "category": "task", "aliases": ["презентация результатов", "представление результатов", "защита выводов"]},
    {"canonical": "Мониторинг метрик", "category": "task", "aliases": ["мониторинг метрик", "отслеживание метрик", "контроль метрик"]},
    {"canonical": "Исследование данных", "category": "task", "aliases": ["исследование данных", "exploratory data analysis", "eda", "разведочный анализ"]},
    {"canonical": "Очистка данных", "category": "task", "aliases": ["очистка данных", "data cleaning", "предобработка данных"]},
    {"canonical": "Интеграция данных", "category": "task", "aliases": ["интеграция данных", "data integration", "объединение данных"]},
    {"canonical": "Разработка витрин", "category": "task", "aliases": ["разработка витрин", "создание витрин", "витрины"]},
    {"canonical": "Оптимизация запросов", "category": "task", "aliases": ["оптимизация запросов", "оптимизировать sql", "производительность запросов"]},
    {"canonical": "Взаимодействие с заказчиками", "category": "task", "aliases": ["взаимодействие с заказчиками", "работа с заказчиками", "коммуникация с бизнесом", "бизнес-заказчики"]},

    # Soft skills
    {"canonical": "Английский язык", "category": "soft_skill", "aliases": ["английский", "english", "англ"]},
    {"canonical": "Коммуникация", "category": "soft_skill", "aliases": ["коммуникация", "коммуникабельность", "communication"]},
    {"canonical": "Презентационные навыки", "category": "soft_skill", "aliases": ["презентационные навыки", "навыки презентации", "presentation skills"]},
    {"canonical": "Критическое мышление", "category": "soft_skill", "aliases": ["критическое мышление", "critical thinking"]},
    {"canonical": "Самостоятельность", "category": "soft_skill", "aliases": ["самостоятельность", "самоорганизация"]},
    {"canonical": "Проактивность", "category": "soft_skill", "aliases": ["проактивность", "инициативность"]},
    {"canonical": "Внимание к деталям", "category": "soft_skill", "aliases": ["внимание к деталям", "внимательность"]},
    {"canonical": "Командная работа", "category": "soft_skill", "aliases": ["командная работа", "работа в команде", "teamwork"]},

    # Domain
    {"canonical": "Финтех", "category": "domain", "aliases": ["финтех", "fintech"]},
    {"canonical": "Банки", "category": "domain", "aliases": ["банк", "банковский", "banking"]},
    {"canonical": "E-commerce", "category": "domain", "aliases": ["e-commerce", "ecommerce", "электронная коммерция"]},
    {"canonical": "Маркетплейсы", "category": "domain", "aliases": ["маркетплейс", "marketplace", "wildberries", "ozon"]},
    {"canonical": "Ритейл", "category": "domain", "aliases": ["ритейл", "retail"]},
    {"canonical": "Телеком", "category": "domain", "aliases": ["телеком", "telecom"]},
    {"canonical": "Логистика", "category": "domain", "aliases": ["логистика", "logistics", "доставка"]},
    {"canonical": "Gaming", "category": "domain", "aliases": ["gaming", "igaming", "игры"]},
    {"canonical": "HealthTech", "category": "domain", "aliases": ["healthtech", "медицина", "здравоохранение"]},
    {"canonical": "EdTech", "category": "domain", "aliases": ["edtech", "образование"]},
    {"canonical": "Страхование", "category": "domain", "aliases": ["страхование", "insurance"]},
    {"canonical": "Инвестиции", "category": "domain", "aliases": ["инвестиции", "investment"]},
    {"canonical": "Трейдинг", "category": "domain", "aliases": ["трейдинг", "trading", "алготрейдинг"]},
    {"canonical": "Недвижимость", "category": "domain", "aliases": ["недвижимость", "real estate"]},
    {"canonical": "Реклама", "category": "domain", "aliases": ["реклама", "advertising", "adtech"]},
    {"canonical": "Маркетинг", "category": "domain", "aliases": ["маркетинг", "marketing"]},
]


def build_alias_pattern(aliases: list) -> re.Pattern:
    parts = []
    for alias in aliases:
        a = alias.lower()
        parts.append(r"(?<![a-zа-я0-9_])" + re.escape(a) + r"(?![a-zа-я0-9_])")
    return re.compile("|".join(parts), re.IGNORECASE)


COMPILED_DICTIONARY = [
    (entry, build_alias_pattern(entry["aliases"]))
    for entry in DICTIONARY
]


def extract_dictionary(text: str) -> list:
    """Возвращает список (category, canonical) из словаря."""
    found = set()
    for entry, pattern in COMPILED_DICTIONARY:
        if pattern.search(text):
            found.add((entry["category"], entry["canonical"]))
    return sorted(found)


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

SYNONYMS = {
    "аб тестирование": "a/b тестирование",
    "аб-тестирование": "a/b тестирование",
    "a/b тесты": "a/b тестирование",
    "a/b-тесты": "a/b тестирование",
    "сплит тестирование": "a/b тестирование",
    "питон": "python",
    "пауэр би": "power bi",
    "павер би": "power bi",
    "эксель": "excel",
    "машинное обучение": "ml",
    "machine learning": "ml",
    "дашборды": "построение дашбордов",
    "dashboards": "построение дашбордов",
    "отчетность": "подготовка отчетов",
    "отчётность": "подготовка отчетов",
}


def normalize_item(value: str) -> str:
    s = str(value).lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" \t\n\r\"'«».,;:!()[]{}")
    s = SYNONYMS.get(s, s)
    return s


def canonical_from_dictionary(value: str):
    """Пытается сопоставить LLM-элемент со словарём."""
    s = normalize_item(value)
    if not s:
        return None

    for entry, pattern in COMPILED_DICTIONARY:
        if pattern.search(s):
            return entry["category"], entry["canonical"]
    return None


# ============================================================
# LLM
# ============================================================

SYSTEM_PROMPT = """
Ты аналитик рынка вакансий. Извлекай из текста вакансии только явно указанные требования, задачи и навыки.
Не выдумывай. Не добавляй то, чего нет в тексте.
Возвращай строго JSON без markdown и без пояснений.
""".strip()


def build_user_prompt(title: str, text: str) -> str:
    return f"""
Название вакансии: {title}

Текст вакансии:
{text}

Верни JSON строго такой структуры:
{{
  "tools": ["SQL", "Python", "Power BI"],
  "methods": ["A/B тестирование", "когортный анализ"],
  "tasks": ["строить дашборды", "проводить ad-hoc анализ", "готовить отчеты"],
  "soft_skills": ["коммуникация", "английский язык"],
  "domain": ["финтех"]
}}

Правила:
1. tools: языки, библиотеки, БД, BI-инструменты, платформы.
2. methods: методы анализа, статистика, ML, продуктовые методики.
3. tasks: нормализованные короткие формулировки задач на русском, в инфинитиве, 2-5 слов.
4. soft_skills: только явно указанные soft skills.
5. domain: домен бизнеса, если он явно указан.
6. Если чего-то нет, возвращай пустой список.
7. Не включай условия работы: ДМС, офис, график, зарплату, печеньки.
""".strip()


def extract_json_from_text(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def validate_llm_result(data) -> dict:
    if not isinstance(data, dict):
        return None

    result = {}
    for key in ["tools", "methods", "tasks", "soft_skills", "domain"]:
        value = data.get(key, [])
        if not isinstance(value, list):
            value = []
        cleaned = []
        for item in value:
            if isinstance(item, dict):
                item = item.get("label") or item.get("name") or ""
            item = str(item).strip()
            if item:
                cleaned.append(item)
        result[key] = cleaned

    return result


def cache_key(title: str, text: str) -> str:
    raw = f"{PROMPT_VERSION}|{LLM_MODEL}|{title}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_cache() -> dict:
    if not os.path.exists(LLM_CACHE_FILE):
        return {}
    try:
        with open(LLM_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    try:
        with open(LLM_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Не удалось сохранить LLM-кэш: {e}", level="WARNING")


def call_llm(title: str, text: str):
    global llm_available

    if not USE_LLM or not llm_available:
        return None

    api_key = os.getenv(LLM_API_KEY_ENV, "").strip()
    if not api_key:
        log(f"LLM отключена: не задана переменная окружения {LLM_API_KEY_ENV}", level="WARNING")
        llm_available = False
        return None

    if requests is None:
        log("LLM отключена: не установлен requests. Выполни pip install requests", level="WARNING")
        llm_available = False
        return None

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(title, text)},
        ],
        "temperature": 0.0,
        "max_tokens": 3000,
        "reasoning": {"enabled": False},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "hh-vacancy-analysis",
    }

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = requests.post(
                LLM_BASE_URL,
                headers=headers,
                json=payload,
                timeout=LLM_TIMEOUT,
            )
        except Exception as e:
            log(f"LLM сетевая ошибка, попытка {attempt}/{LLM_MAX_RETRIES}: {e}", level="WARNING")
            time.sleep(2 * attempt)
            continue

        if response.status_code == 200:
            try:
                content = response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                log(f"LLM не вернула ожидаемый JSON-ответ: {e}", level="WARNING")
                return None

            data = extract_json_from_text(content)
            validated = validate_llm_result(data)
            if validated is None:
                log("LLM вернула невалидный JSON, пропускаем LLM для этой вакансии", level="WARNING")
                return None
            return validated

        if response.status_code in (401, 403, 404):
            log(
                f"LLM ошибка {response.status_code}. Проверь API-ключ и модель. "
                f"LLM отключена до конца запуска.",
                level="ERROR",
            )
            llm_available = False
            return None

        if response.status_code in (429, 500, 502, 503, 504):
            wait = 3 * attempt
            log(f"LLM ошибка {response.status_code}, жду {wait} сек, попытка {attempt}/{LLM_MAX_RETRIES}",
                level="WARNING")
            time.sleep(wait)
            continue

        log(f"LLM ошибка {response.status_code}: {response.text[:300]}", level="WARNING")
        return None

    return None


# ============================================================
# ОБЪЕДИНЕНИЕ ИСТОЧНИКОВ
# ============================================================

def merge_items(dict_items: list, llm_items: dict) -> dict:
    """
    Возвращает:
    {
      (category, item): set(sources)
    }
    """
    merged = {}

    for category, item in dict_items:
        merged[(category, item)] = {"dict"}

    if not llm_items:
        return merged

    category_map = {
        "tools": "tool",
        "methods": "method",
        "tasks": "task",
        "soft_skills": "soft_skill",
        "domain": "domain",
    }

    for llm_key, category in category_map.items():
        for raw_item in llm_items.get(llm_key, []):
            if category in ("tool", "method", "task"):
                canonical = canonical_from_dictionary(raw_item)
                if canonical:
                    item = canonical[1]
                    category = canonical[0]
                else:
                    item = normalize_item(raw_item)
            else:
                item = normalize_item(raw_item)

            if not item or len(item) > 120:
                continue

            key = (category, item)
            if key not in merged:
                merged[key] = set()
            merged[key].add("llm")

    return merged


# ============================================================
# АГРЕГАЦИЯ
# ============================================================

def build_rankings(items_df: pd.DataFrame, total_vacancies: int) -> pd.DataFrame:
    if items_df.empty:
        return pd.DataFrame()

    ranked = (
        items_df.groupby(["category", "item"], as_index=False)
        .agg(
            vacancy_count=("vacancy_id", "nunique"),
            dict_hits=("source", lambda s: int(s.str.contains("dict").sum())),
            llm_hits=("source", lambda s: int(s.str.contains("llm").sum())),
            example_titles=("title", lambda s: " | ".join(list(dict.fromkeys(s))[:2])),
            example_ids=("vacancy_id", lambda s: ", ".join(list(dict.fromkeys(s))[:3])),
        )
    )

    ranked["share_pct"] = (ranked["vacancy_count"] / total_vacancies * 100).round(2)
    ranked = ranked.sort_values(
        ["category", "vacancy_count", "item"],
        ascending=[True, False, True]
    ).reset_index(drop=True)

    return ranked


def save_category_ranking(ranked: pd.DataFrame, category: str, filename: str) -> None:
    part = ranked[ranked["category"] == category].copy()
    part.to_csv(filename, index=False, encoding="utf-8-sig")
    log(f"{category}: {len(part)} пунктов -> {filename}")


def log_top(ranked: pd.DataFrame, category: str, n: int = 10) -> None:
    part = ranked[ranked["category"] == category].head(n)
    if part.empty:
        return
    log(f"Топ {category}:")
    for _, row in part.iterrows():
        log(f"  {row['item']}: {row['vacancy_count']} вакансий ({row['share_pct']}%)")


# ============================================================
# ЗАПУСК
# ============================================================

def run_stage4() -> dict:
    log("=" * 60)
    log("ЭТАП 4: ИЗВЛЕЧЕНИЕ ТРЕБОВАНИЙ И РАНЖИРОВАНИЕ")
    log("=" * 60)
    log(f"Входной файл: {INPUT_FILE}")

    if not os.path.exists(INPUT_FILE):
        log("Входной файл не найден. Сначала выполни этап 3.", level="ERROR")
        return {}

    try:
        df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        log("Входной файл пуст. Этап 4 остановлен.", level="WARNING")
        return {}

    if df.empty:
        log("Нет вакансий для анализа.", level="WARNING")
        return {}

    log(f"Вакансий для анализа: {len(df)}")
    log(f"LLM включена: {USE_LLM}")
    if USE_LLM:
        log(f"LLM модель: {LLM_MODEL}")
        log(f"LLM ключ из переменной: {LLM_API_KEY_ENV}")

    cache = load_cache()
    log(f"LLM-кэш: {len(cache)} записей")

    all_records = []
    vacancy_rows = []

    llm_calls = 0
    llm_cache_hits = 0
    llm_success = 0

    for idx, row in df.iterrows():
        vacancy_id = row.get("vacancy_id", "")
        title = row.get("title", "")
        text = row.get("analysis_text", "") or row.get("description_clean", "")
        text = text[:LLM_MAX_CHARS]

        log(f"[{idx + 1}/{len(df)}] {vacancy_id}: {title}")

        dict_items = extract_dictionary(text)
        llm_items = None
        llm_used = False

        if USE_LLM and llm_available and text:
            key = cache_key(title, text)

            if key in cache:
                llm_items = cache[key]
                llm_cache_hits += 1
                llm_used = True
                log("  LLM: взято из кэша")
            else:
                llm_items = call_llm(title, text)
                if llm_items is not None:
                    cache[key] = llm_items
                    llm_calls += 1
                    llm_success += 1
                    llm_used = True
                    log("  LLM: успешно")

                    if llm_calls % 5 == 0:
                        save_cache(cache)

                    time.sleep(LLM_SLEEP_BETWEEN_CALLS)
                else:
                    log("  LLM: не использована, остаётся словарный режим", level="WARNING")

        merged = merge_items(dict_items, llm_items)

        for (category, item), sources in merged.items():
            all_records.append({
                "vacancy_id": vacancy_id,
                "title": title,
                "category": category,
                "item": item,
                "source": ",".join(sorted(sources)),
            })

        vacancy_row = {
            "vacancy_id": vacancy_id,
            "title": title,
            "llm_used": llm_used,
            "tools": [],
            "methods": [],
            "tasks": [],
            "soft_skills": [],
            "domain": [],
        }

        category_to_field = {
            "tool": "tools",
            "method": "methods",
            "task": "tasks",
            "soft_skill": "soft_skills",
            "domain": "domain",
        }

        for (category, item) in merged.keys():
            field = category_to_field.get(category)
            if field:
                vacancy_row[field].append(item)

        for field in ["tools", "methods", "tasks", "soft_skills", "domain"]:
            vacancy_row[field] = "; ".join(sorted(vacancy_row[field]))

        vacancy_rows.append(vacancy_row)

        log(f"  Извлечено пунктов: {len(merged)} | словарь: {len(dict_items)} | LLM: {llm_used}")

    save_cache(cache)

    items_df = pd.DataFrame(all_records)
    vacancies_df = pd.DataFrame(vacancy_rows)

    items_df.to_csv(ITEMS_FILE, index=False, encoding="utf-8-sig")
    vacancies_df.to_csv(VACANCIES_FILE, index=False, encoding="utf-8-sig")

    log(f"Пункты по вакансиям сохранены: {len(items_df)} -> {ITEMS_FILE}")
    log(f"Извлечённые данные по вакансиям сохранены: {len(vacancies_df)} -> {VACANCIES_FILE}")

    ranked = build_rankings(items_df, total_vacancies=len(df))
    ranked.to_csv(RANKED_FILE, index=False, encoding="utf-8-sig")
    log(f"Общий рейтинг сохранён: {len(ranked)} пунктов -> {RANKED_FILE}")

    save_category_ranking(ranked, "tool", TOOLS_FILE)
    save_category_ranking(ranked, "method", METHODS_FILE)
    save_category_ranking(ranked, "task", TASKS_FILE)

    log("-" * 60)
    log("СТАТИСТИКА:")
    log(f"  LLM вызовов: {llm_calls}")
    log(f"  LLM из кэша: {llm_cache_hits}")
    log(f"  LLM успешных: {llm_success}")
    log(f"  Вакансий с LLM: {int(vacancies_df['llm_used'].sum()) if not vacancies_df.empty else 0}")
    log(f"  Всего уникальных пунктов: {len(ranked)}")

    log_top(ranked, "tool", 12)
    log_top(ranked, "method", 12)
    log_top(ranked, "task", 12)

    log("=" * 60)
    log("ЭТАП 4 ЗАВЕРШЕН")
    log("=" * 60)
    log(f"Главные файлы: {RANKED_FILE}, {TOOLS_FILE}, {METHODS_FILE}, {TASKS_FILE}")

    return {
        "vacancies": len(df),
        "items": len(items_df),
        "ranked_items": len(ranked),
        "llm_calls": llm_calls,
        "llm_cache_hits": llm_cache_hits,
    }


if __name__ == "__main__":
    start = time.time()
    run_stage4()
    log(f"Общее время: {(time.time() - start) / 60:.1f} мин")