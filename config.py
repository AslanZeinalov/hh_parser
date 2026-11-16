"""
Общие настройки проекта. Меняй параметры здесь, код трогать не нужно.
"""

# ============================================================
# ПОИСКОВЫЕ ЗАПРОСЫ
# ============================================================

SEARCH_QUERIES = [
    "Аналитик данных",
    "Продуктовый аналитик",
    "Data Analyst",
    "Product Analyst",
]

# ============================================================
# ФИЛЬТРЫ ПОИСКА (применяются на этапе 1)
# ============================================================

# Город. Список ID регионов HH. Пустой список [] = вся Россия.
# Примеры: [88] = Казань, [1] = Москва, [1, 2] = Москва + СПб
# Если города нет в справочнике ниже: выбери город на сайте hh.ru
# и посмотри параметр area в адресной строке.
AREA_IDS = []

AREA_NAMES = {
    1: "Москва", 2: "Санкт-Петербург", 88: "Казань",
    3: "Екатеринбург", 4: "Новосибирск", 66: "Нижний Новгород",
    53: "Краснодар", 76: "Ростов-на-Дону", 78: "Самара",
    99: "Уфа", 104: "Челябинск", 72: "Пермь", 26: "Воронеж",
}

# Опыт работы. Пустой список = любой.
# Допустимые значения:
#   "noExperience"  - нет опыта
#   "between1And3"  - от 1 до 3 лет
#   "between3And6"  - от 3 до 6 лет
#   "moreThan6"     - более 6 лет
# Для junior-позиций: ["noExperience", "between1And3"]
EXPERIENCE = ["noExperience", "between1And3"]

# Зарплата: минимальная сумма (число) или None. Валюта: RUR, USD, EUR.
SALARY_FROM = None
CURRENCY = "RUR"
ONLY_WITH_SALARY = False   # True = только вакансии с указанной зарплатой

# Занятость. Пустой список = любая.
# Значения: "full", "part", "project", "volunteer", "probation"
EMPLOYMENT = []

# График работы. Пустой список = любой.
# Значения: "fullDay", "shift", "flexible", "remote", "flyInFlyOut"
# Удалёнка: ["remote"]
SCHEDULE = []

# Давность публикации в днях (например 7, 30). None = за всё время.
PERIOD_DAYS = 15

# Сортировка выдачи: "relevance", "publication_time", "salary_desc", "salary_asc"
ORDER_BY = "relevance"

# ============================================================
# ПАРАМЕТРЫ ПОИСКА И ПАРСИНГА
# ============================================================

SEARCH_FIELD = "name"      # искать только в названии вакансии
NO_MAGIC = True            # отключить синонимы и морфологию
APPLY_TITLE_FILTER = False  # фильтровать ссылки по названию на этапе 1

MAX_PAGES = 50             # максимум страниц выдачи на один запрос
DELAY_STAGE1 = 3           # пауза между страницами поиска, сек
DELAY_STAGE2 = 2.5         # пауза между вакансиями, сек
PAGE_TIMEOUT = 30000       # таймаут загрузки страницы, мс
MAX_RETRIES = 2            # попыток на одну вакансию
CHECKPOINT_EVERY = 25      # сохранять прогресс каждые N вакансий
TEST_LIMIT = None            # тестовый режим этапа 2; None = полный прогон

# ============================================================
# ФАЙЛЫ
# ============================================================

LINKS_ALL_FILE = "vacancy_links_all.csv"
LINKS_FILE = "vacancy_links.csv"
LINKS_REVIEW_FILE = "vacancy_links_review.csv"
LINKS_EXCLUDED_FILE = "vacancy_links_excluded.csv"

RAW_FILE = "vacancies_raw.csv"
DEDUP_FILE = "vacancies_dedup.csv"
RELEVANT_FILE = "vacancies_relevant.csv"
EXCLUDED_FILE = "vacancies_excluded.csv"
REVIEW_FILE = "vacancies_review.csv"
FAILED_FILE = "failed_links.csv"
# ============================================================
# ЭТАП 3: ОЧИСТКА И ПОДГОТОВКА ТЕКСТА
# ============================================================

CLEAN_FILE = "vacancies_clean.csv"
CLEAN_REPORT_FILE = "stage3_report.csv"

# ============================================================
# ЭТАП 4: ИЗВЛЕЧЕНИЕ ТРЕБОВАНИЙ И РАНЖИРОВАНИЕ
# ============================================================

USE_LLM = True

# OpenRouter: https://openrouter.ai
# Ключ берётся из переменной окружения, не храни его в коде.
LLM_API_KEY_ENV = "OPENROUTER_API_KEY"
LLM_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Пример бесплатной модели. Если она недоступна, выбери другую free-модель
# в каталоге OpenRouter и замени значение.
LLM_MODEL = "inclusionai/ling-3.2-flash:free"

LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 3
LLM_SLEEP_BETWEEN_CALLS = 2.0
LLM_MAX_CHARS = 6000
LLM_CACHE_FILE = "llm_cache.json"

STAGE4_ITEMS_FILE = "stage4_items_by_vacancy.csv"
STAGE4_RANKED_FILE = "stage4_ranked_all.csv"
STAGE4_VACANCIES_FILE = "stage4_extracted_by_vacancy.csv"
STAGE4_TOOLS_FILE = "stage4_tools_ranked.csv"
STAGE4_METHODS_FILE = "stage4_methods_ranked.csv"
STAGE4_TASKS_FILE = "stage4_tasks_ranked.csv"

# ============================================================
# ЭТАП 5: НОРМАЛИЗАЦИЯ И КЛАСТЕРИЗАЦИЯ ЗАДАЧ
# ============================================================

USE_LLM_CLUSTERING = True
CLUSTER_CHUNK_SIZE = 40
CLUSTER_CACHE_FILE = "llm_cluster_cache.json"

STAGE5_RANKED_FILE = "stage5_ranked_final.csv"
STAGE5_TASKS_FILE = "stage5_tasks_final.csv"
STAGE5_TOOLS_FILE = "stage5_tools_final.csv"
STAGE5_METHODS_FILE = "stage5_methods_final.csv"
STAGE5_MAPPING_FILE = "stage5_task_mapping.csv"