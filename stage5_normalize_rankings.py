"""
Этап 5: Нормализация и кластеризация задач, финальный рейтинг.

Вход:  stage4_items_by_vacancy.csv
Выход: stage5_ranked_final.csv
       stage5_tasks_final.csv / tools / methods
       stage5_task_mapping.csv (аудит)
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
from stage4_extract_requirements import canonical_from_dictionary, normalize_item


INPUT_FILE = getattr(config, "STAGE4_ITEMS_FILE", "stage4_items_by_vacancy.csv")
RANKED_FILE = getattr(config, "STAGE5_RANKED_FILE", "stage5_ranked_final.csv")
TASKS_FILE = getattr(config, "STAGE5_TASKS_FILE", "stage5_tasks_final.csv")
TOOLS_FILE = getattr(config, "STAGE5_TOOLS_FILE", "stage5_tools_final.csv")
METHODS_FILE = getattr(config, "STAGE5_METHODS_FILE", "stage5_methods_final.csv")
MAPPING_FILE = getattr(config, "STAGE5_MAPPING_FILE", "stage5_task_mapping.csv")

USE_LLM_CLUSTERING = getattr(config, "USE_LLM_CLUSTERING", True)
CHUNK_SIZE = getattr(config, "CLUSTER_CHUNK_SIZE", 40)
CACHE_FILE = getattr(config, "CLUSTER_CACHE_FILE", "llm_cluster_cache.json")
LLM_MODEL = getattr(config, "LLM_MODEL", "")
LLM_BASE_URL = getattr(config, "LLM_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
LLM_API_KEY_ENV = getattr(config, "LLM_API_KEY_ENV", "OPENROUTER_API_KEY")

PROMPT_VERSION = "cluster_v1"

# Слишком общие фразы, не являющиеся конкретными требованиями
GENERIC_STOP = {
    "анализ данных", "анализировать данные", "работа с данными",
    "обработка данных", "анализ", "данные", "аналитика",
}

# Дополнительные синонимы задач, которых нет в словаре
EXTRA_TASK_MAP = {
    "писать sql-запросы": "Написание SQL-запросов",
    "писать sql запросы": "Написание SQL-запросов",
    "написание sql-запросов": "Написание SQL-запросов",
    "готовить отчеты": "Подготовка отчетов",
    "формировать отчеты": "Подготовка отчетов",
    "строить дашборды": "Построение дашбордов",
    "разрабатывать дашборды": "Построение дашбордов",
    "автоматизировать отчетность": "Автоматизация отчетности",
    "автоматизировать отчёты": "Автоматизация отчетности",
    "подготовка аналитических отчетов": "Подготовка отчетов",
    "подготовка аналитических отчётов": "Подготовка отчетов",
    "формирование аналитических отчетов": "Подготовка отчетов",
}


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def pretty(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s[:1].upper() + s[1:] if s else s


# ============================================================
# ДЕТЕРМИНИРОВАННАЯ НОРМАЛИЗАЦИЯ
# ============================================================

def deterministic_map(category: str, item: str) -> tuple:
    """Возвращает (canonical_item или None, method)."""
    norm = normalize_item(item)

    if norm in GENERIC_STOP:
        return None, "stoplist"

    if category in ("tool", "method", "task"):
        canonical = canonical_from_dictionary(norm)
        if canonical:
            return canonical[1], "dict"

    if category == "task" and norm in EXTRA_TASK_MAP:
        return EXTRA_TASK_MAP[norm], "synonym"

    return pretty(item), "identity"


# ============================================================
# LLM-КЛАСТЕРИЗАЦИЯ
# ============================================================

CLUSTER_SYSTEM = """
Ты нормализуешь формулировки задач из вакансий аналитика данных.
Объединяй только синонимичные фразы: одна и та же задача, сказанная разными словами.
Разные по смыслу задачи НЕ объединяй.
Возвращай строго JSON без markdown.
"""


def global_consolidate_tasks(df: pd.DataFrame) -> pd.DataFrame:
    """Глобальный проход: сливаем синонимы только среди частых задач."""
    tasks = df[df["category"] == "task"]
    counts = (tasks.groupby("canonical_item")["vacancy_id"]
              .nunique().sort_values(ascending=False))

    # Единичный хвост не трогаем: он не влияет на топ и раздувает запрос
    frequent = counts[counts >= 2]
    label_list = list(frequent.index)[:60]

    log(f"Глобальная консолидация: всего меток {len(counts)}, "
        f"берём частые (2+ вакансий): {len(label_list)}")

    if len(label_list) < 2:
        log("Глобальная консолидация пропущена: мало частых меток")
        return df

    api_key = os.getenv(LLM_API_KEY_ENV, "").strip()
    if not (USE_LLM_CLUSTERING and api_key and requests):
        log("Глобальная консолидация пропущена: LLM отключена или нет ключа")
        return df

    key = hashlib.sha256(
        ("global_v3|" + LLM_MODEL + "|" +
         json.dumps(label_list, ensure_ascii=False, sort_keys=True)).encode("utf-8")
    ).hexdigest()

    cache = load_cache()
    if key in cache:
        mapping = cache[key]
        log("Глобальная консолидация: из кэша")
    else:
        numbered = "\n".join(f"{i+1}. {p}" for i, p in enumerate(label_list))
        user_prompt = (
            "Список канонических формулировок задач:\n" + numbered +
            '\n\nВерни строго JSON: {"mapping": {"метка": "каноническая метка"}}.\n'
            "Каждая метка должна быть ключом. Объединяй только точные синонимы "
            "(одна задача разными словами). Разные по смыслу задачи не объединяй. "
            "Если синонимов нет — значение равно самой метке."
        )
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": CLUSTER_SYSTEM},
                {"role": "user", "content": user_prompt},
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

        log(f"Глобальная консолидация: отправляю запрос к LLM ({len(label_list)} меток)...")
        mapping = {}
        for attempt in range(1, 3):
            try:
                resp = requests.post(LLM_BASE_URL, headers=headers, json=payload, timeout=60)
            except Exception as e:
                log(f"Глобальная консолидация, сетевая ошибка ({attempt}/2): {e}", level="WARNING")
                time.sleep(3 * attempt)
                continue

            if resp.status_code == 200:
                try:
                    content = (resp.json()["choices"][0].get("message") or {}).get("content") or ""
                except Exception:
                    content = ""
                data = extract_json(content)
                if isinstance(data, dict) and isinstance(data.get("mapping"), dict):
                    mapping = data["mapping"]
                else:
                    log("Глобальная консолидация: невалидный mapping", level="WARNING")
                break

            if resp.status_code in (429, 500, 502, 503, 504):
                log(f"Глобальная консолидация: HTTP {resp.status_code}, жду ({attempt}/2)", level="WARNING")
                time.sleep(4 * attempt)
                continue

            log(f"Глобальная консолидация: ошибка {resp.status_code}: {resp.text[:300]}", level="WARNING")
            break

        if mapping:
            cache[key] = mapping
            save_cache(cache)
        else:
            log("Глобальная консолидация: пустой mapping не кэширую", level="WARNING")
        time.sleep(2)

    if not mapping:
        log("Глобальная консолидация: mapping пуст, оставляю как есть", level="WARNING")
        return df

    norm_map = {normalize_item(k): pretty(v) for k, v in mapping.items() if k and v}

    def remap(row):
        if row["category"] == "task":
            n = normalize_item(row["canonical_item"])
            if n in norm_map and norm_map[n]:
                return norm_map[n]
        return row["canonical_item"]

    df["canonical_item"] = df.apply(remap, axis=1)
    log(f"Глобальная консолидация завершена: обработано {len(label_list)} меток")
    return df

def build_cluster_prompt(phrases: list) -> str:
    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(phrases))
    return f"""
Список формулировок задач:
{numbered}

Верни JSON строго такой структуры:
{{"mapping": {{"исходная фраза": "каноническая фраза"}}}}

Правила:
1. Каждая исходная фраза должна быть ключом в mapping.
2. Каноническая фраза: 2-5 слов, на русском, отглагольное существительное
   ("Построение дашбордов", "Подготовка отчетов", "Проведение A/B тестов").
3. Если у фразы нет синонимов в списке, каноническая = исходная фраза
   (можно слегка нормализовать стиль).
4. Не придумывай задачи, которых нет в списке.
""".strip()


def extract_json(text: str):
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


def load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cluster_key(phrases: list) -> str:
    raw = f"{PROMPT_VERSION}|{LLM_MODEL}|" + json.dumps(phrases, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def call_cluster_llm(phrases: list):
    api_key = os.getenv(LLM_API_KEY_ENV, "").strip()
    if not api_key or requests is None:
        return None

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": CLUSTER_SYSTEM},
            {"role": "user", "content": build_cluster_prompt(phrases)},
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
        "reasoning": {"enabled": False},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "hh-vacancy-analysis",
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(LLM_BASE_URL, headers=headers, json=payload, timeout=90)
        except Exception as e:
            log(f"LLM сетевая ошибка: {e}", level="WARNING")
            time.sleep(3 * attempt)
            continue

        if response.status_code == 200:
            try:
                choice = response.json()["choices"][0]
                content = (choice.get("message") or {}).get("content") or ""
            except Exception:
                return None
            data = extract_json(content)
            if isinstance(data, dict) and isinstance(data.get("mapping"), dict):
                return data["mapping"]
            log("LLM вернула невалидный mapping", level="WARNING")
            return None

        if response.status_code in (429, 500, 502, 503, 504):
            log(f"LLM {response.status_code}, жду и повторяю ({attempt}/3)", level="WARNING")
            time.sleep(4 * attempt)
            continue

        log(f"LLM ошибка {response.status_code}: {response.text[:200]}", level="WARNING")
        return None

    return None


def cluster_tasks(phrases: list) -> dict:
    """Возвращает mapping нормализованная фраза -> каноническая."""
    if not phrases:
        return {}

    cache = load_cache()
    result = {}
    chunks = [phrases[i:i + CHUNK_SIZE] for i in range(0, len(phrases), CHUNK_SIZE)]
    log(f"LLM-кластеризация: {len(phrases)} фраз, {len(chunks)} чанков")

    for idx, chunk in enumerate(chunks, 1):
        key = cluster_key(chunk)
        if key in cache:
            mapping = cache[key]
            log(f"  Чанк {idx}/{len(chunks)}: из кэша")
        else:
            log(f"  Чанк {idx}/{len(chunks)}: запрос к LLM ({len(chunk)} фраз)")
            mapping = call_cluster_llm(chunk)
            if mapping is None:
                log(f"  Чанк {idx}: LLM не справилась, оставляю фразы как есть", level="WARNING")
                mapping = {}
            else:
                cache[key] = mapping
                save_cache(cache)
            time.sleep(2)

        for original, canonical in mapping.items():
            norm_original = normalize_item(original)
            canonical = pretty(canonical)
            if norm_original and canonical:
                result[norm_original] = canonical

    return result


# ============================================================
# АГРЕГАЦИЯ
# ============================================================

def build_rankings(df: pd.DataFrame, total_vacancies: int) -> pd.DataFrame:
    ranked = (
        df.groupby(["category", "canonical_item"], as_index=False)
        .agg(
            vacancy_count=("vacancy_id", "nunique"),
            example_titles=("title", lambda s: " | ".join(list(dict.fromkeys(s))[:2])),
            example_ids=("vacancy_id", lambda s: ", ".join(list(dict.fromkeys(s))[:3])),
        )
    )
    ranked["share_pct"] = (ranked["vacancy_count"] / total_vacancies * 100).round(2)
    ranked = ranked.sort_values(
        ["category", "vacancy_count", "canonical_item"],
        ascending=[True, False, True]
    ).reset_index(drop=True)
    return ranked


def log_top(ranked: pd.DataFrame, category: str, n: int = 12) -> None:
    part = ranked[ranked["category"] == category].head(n)
    if part.empty:
        return
    log(f"Топ {category}:")
    for _, row in part.iterrows():
        log(f"  {row['canonical_item']}: {row['vacancy_count']} вакансий ({row['share_pct']}%)")


# ============================================================
# ЗАПУСК
# ============================================================

def run_stage5() -> dict:
    log("=" * 60)
    log("ЭТАП 5: НОРМАЛИЗАЦИЯ И КЛАСТЕРИЗАЦИЯ")
    log("=" * 60)

    if not os.path.exists(INPUT_FILE):
        log("Файл этапа 4 не найден. Сначала выполни этап 4.", level="ERROR")
        return {}

    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")
    if df.empty:
        log("Нет данных.", level="WARNING")
        return {}

    total_vacancies = df["vacancy_id"].nunique()
    log(f"Записей: {len(df)}, вакансий: {total_vacancies}")

    # Шаг 1: детерминированная нормализация
    mapped = df.apply(
        lambda row: deterministic_map(row["category"], row["item"]),
        axis=1
    )
    df["canonical_item"] = mapped.apply(lambda x: x[0])
    df["map_method"] = mapped.apply(lambda x: x[1])

    dropped = int(df["canonical_item"].isna().sum())
    df = df.dropna(subset=["canonical_item"]).copy()
    log(f"Удалено общих фраз (stoplist): {dropped}")

    # Шаг 2: LLM-кластеризация оставшихся задач
    identity_tasks = (
        df[(df["category"] == "task") & (df["map_method"] == "identity")]
        .groupby("canonical_item")["vacancy_id"].nunique()
        .sort_values(ascending=False)
    )
    phrases = list(identity_tasks.index)
    log(f"Задач до кластеризации (identity): {len(phrases)}")

    llm_mapping = {}
    if USE_LLM_CLUSTERING and phrases:
        llm_mapping = cluster_tasks(phrases)

    if llm_mapping:
        def apply_llm(row):
            if row["category"] == "task" and row["map_method"] == "identity":
                norm = normalize_item(row["canonical_item"])
                if norm in llm_mapping:
                    return llm_mapping[norm], "llm"
            return row["canonical_item"], row["map_method"]

        updated = df.apply(apply_llm, axis=1)
        df["canonical_item"] = updated.apply(lambda x: x[0])
        df["map_method"] = updated.apply(lambda x: x[1])

    df = global_consolidate_tasks(df)
    # Аудит: оригинал -> канонический вид
    audit = (
        df.groupby(["category", "item", "canonical_item", "map_method"], as_index=False)
        .agg(vacancy_count=("vacancy_id", "nunique"))
        .sort_values(["category", "vacancy_count"], ascending=[True, False])
    )
    audit.to_csv(MAPPING_FILE, index=False, encoding="utf-8-sig")
    log(f"Аудит нормализации сохранён: {MAPPING_FILE}")

    # Шаг 3: финальный рейтинг
    ranked = build_rankings(df, total_vacancies)
    ranked.to_csv(RANKED_FILE, index=False, encoding="utf-8-sig")

    for category, filename in [("task", TASKS_FILE), ("tool", TOOLS_FILE), ("method", METHODS_FILE)]:
        part = ranked[ranked["category"] == category]
        part.to_csv(filename, index=False, encoding="utf-8-sig")
        log(f"{category}: {len(part)} пунктов -> {filename}")

    n_tasks_final = int((ranked["category"] == "task").sum())
    log(f"Задач после кластеризации: {n_tasks_final} (было {len(phrases)} identity + словарные)")

    log_top(ranked, "tool")
    log_top(ranked, "method")
    log_top(ranked, "task")

    log("=" * 60)
    log("ЭТАП 5 ЗАВЕРШЕН")
    log("=" * 60)
    log(f"Финальный рейтинг: {RANKED_FILE}")

    return {"ranked_items": len(ranked), "tasks_final": n_tasks_final}


if __name__ == "__main__":
    start = time.time()
    run_stage5()
    log(f"Общее время: {(time.time() - start) / 60:.1f} мин")