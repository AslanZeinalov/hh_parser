"""
Главный файл проекта. Запускает все этапы последовательно,
копирует финальные результаты в results/, удаляет временные файлы.
"""

import os
import shutil
import glob
import time
from datetime import datetime

import config

from stage1_collect_links import collect_links, save_and_filter
from stage2_parse_vacancies import run_parser as run_stage2
from stage3_prepare_text import run_stage3
from stage4_extract_requirements import run_stage4
from stage5_normalize_rankings import run_stage5
from stage6_report_and_projects import run_stage6


RESULTS_DIR = "results"


# Файлы, которые считаются итоговыми (копируются в results/)
FINAL_FILES = [
    config.LINKS_FILE,
    config.RELEVANT_FILE,
    config.STAGE4_RANKED_FILE,
    config.STAGE4_TOOLS_FILE,
    config.STAGE4_METHODS_FILE,
    config.STAGE4_TASKS_FILE,
    config.STAGE5_RANKED_FILE,
    config.STAGE5_TASKS_FILE,
    config.STAGE5_TOOLS_FILE,
    config.STAGE5_METHODS_FILE,
]


# Временные файлы (удаляются после завершения)
TEMP_FILES = [
    config.LINKS_ALL_FILE,
    config.LINKS_REVIEW_FILE,
    config.LINKS_EXCLUDED_FILE,
    config.RAW_FILE,
    config.DEDUP_FILE,
    config.EXCLUDED_FILE,
    config.REVIEW_FILE,
    config.FAILED_FILE,
    getattr(config, "CLEAN_FILE", "vacancies_clean.csv"),
    getattr(config, "CLEAN_REPORT_FILE", "stage3_report.csv"),
    config.STAGE4_ITEMS_FILE,
    config.STAGE4_VACANCIES_FILE,
    config.LLM_CACHE_FILE,
    config.CLUSTER_CACHE_FILE,
    config.STAGE5_MAPPING_FILE,
]


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def copy_final_to_results() -> None:
    """Копирует финальные CSV и содержимое stage6_output/ в results/."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    copied = 0

    for f in FINAL_FILES:
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(RESULTS_DIR, f))
            copied += 1
        else:
            log(f"Файл не найден, пропускаю: {f}", level="WARNING")

    # Копируем всё из stage6_output/ (графики, Excel, markdown, топ-таблицы)
    stage6_dir = "stage6_output"
    if os.path.isdir(stage6_dir):
        for item in os.listdir(stage6_dir):
            src = os.path.join(stage6_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(RESULTS_DIR, item))
                copied += 1

    log(f"Скопировано файлов в {RESULTS_DIR}/: {copied}")


def cleanup_temp() -> None:
    """Удаляет временные файлы и debug-дампы."""
    removed = 0

    for f in TEMP_FILES:
        if os.path.exists(f):
            try:
                os.remove(f)
                removed += 1
            except Exception as e:
                log(f"Не удалось удалить {f}: {e}", level="WARNING")

    for pattern in ["debug_search_page_*.html", "vacancy_debug.html"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                removed += 1
            except Exception:
                pass

    # Удаляем пустую папку stage6_output/ после копирования
    stage6_dir = "stage6_output"
    if os.path.isdir(stage6_dir) and not os.listdir(stage6_dir):
        try:
            os.rmdir(stage6_dir)
        except Exception:
            pass

    log(f"Временных файлов удалено: {removed}")


def check_file_exists(filename: str, stage_name: str) -> bool:
    """Проверяет, что этап успешно создал ожидаемый файл."""
    if not os.path.exists(filename):
        log(f"Этап {stage_name} не создал {filename}. Остановка.", level="ERROR")
        return False
    try:
        size = os.path.getsize(filename)
        if size == 0:
            log(f"Файл {filename} пуст. Остановка.", level="ERROR")
            return False
    except Exception:
        pass
    return True


def main() -> None:
    log("=" * 60)
    log("ЗАПУСК ПОЛНОГО ПАЙПЛАЙНА")
    log("=" * 60)
    start = time.time()

    # --- ЭТАП 1 ---
    log("\n>>> ЭТАП 1: Сбор ссылок")
    items = collect_links()
    if not items:
        log("Этап 1 не собрал ни одной ссылки. Остановка.", level="ERROR")
        return
    save_and_filter(items)

    if not check_file_exists(config.LINKS_FILE, "1"):
        return

    # --- ЭТАП 2 ---
    log("\n>>> ЭТАП 2: Парсинг вакансий")
    run_stage2()

    if not check_file_exists(config.RELEVANT_FILE, "2"):
        return

    # --- ЭТАП 3 ---
    log("\n>>> ЭТАП 3: Очистка текста")
    run_stage3()

    if not check_file_exists(getattr(config, "CLEAN_FILE", "vacancies_clean.csv"), "3"):
        return

    # --- ЭТАП 4 ---
    log("\n>>> ЭТАП 4: Извлечение требований")
    run_stage4()

    if not check_file_exists(config.STAGE4_ITEMS_FILE, "4"):
        return

    # --- ЭТАП 5 ---
    log("\n>>> ЭТАП 5: Нормализация и кластеризация")
    run_stage5()

    if not check_file_exists(config.STAGE5_RANKED_FILE, "5"):
        return

    # --- ЭТАП 6 ---
    log("\n>>> ЭТАП 6: Визуализация и отчёты")
    run_stage6()

    # --- ФИНАЛИЗАЦИЯ ---
    log("\n>>> ФИНАЛИЗАЦИЯ")
    copy_final_to_results()
    cleanup_temp()

    elapsed = (time.time() - start) / 60
    log("=" * 60)
    log(f"ПАЙПЛАЙН ЗАВЕРШЁН за {elapsed:.1f} мин")
    log(f"Все результаты в папке: {RESULTS_DIR}/")
    log("=" * 60)


if __name__ == "__main__":
    main()