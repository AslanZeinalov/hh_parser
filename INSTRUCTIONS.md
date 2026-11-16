## Системные требования

- Windows 10/11
- Python 3.10 или новее (протестировано на 3.13)
- VPN-клиент для доступа к api.openrouter.ai
- Свободное место: ~1 ГБ (для браузеров Playwright)

## Шаг 1. Установка Python

1. Скачай Python с https://www.python.org/downloads/
2. При установке ОБЯЗАТЕЛЬНО поставь галочку "Add Python to PATH"
3. Должно вывести версию
   
```powershell
python --version
```
## Шаг 2. Создание виртуального окружения

```powershell
# Создаём окружение
python -m venv .venv

# Активируем окружение
.venv\Scripts\Activate.ps1
```

## Шаг 3. Установка зависимостей

```powershell
pip install -r requirements.txt
```

## Шаг 4. Установка браузеров Playwright

```powershell
playwright install chromium
```

## Шаг 5. API-ключ OpenRouter

Этап 4 и 5 используют бесплатную LLM-модель через OpenRouter.

```powershell
setx OPENROUTER_API_KEY "sk-or-v1-твой_ключ"
```

1. Перезапустить PowerShell.
2. Проверить:

```powershell
$env:OPENROUTER_API_KEY
```

Должен вывести ключ.

Если нет:

```powershell
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User")
```

## Шаг 6. Включение VPN

OpenRouter недоступен из России без VPN. Включи VPN-клиент перед запуском.

## Шаг 7. Настройка фильтров в config.py

Открой `config.py` и настрой под свои задачи.

## Шаг 8. Запуск

```powershell
python run_all.py
```

## Шаг 9. Результаты

В папке `results/` появятся:

**Итоговые таблицы:**
- `vacancy_links.csv` — ссылки на вакансии
- `vacancies_relevant.csv` — отфильтрованные вакансии
- `stage4_ranked_all.csv` — полный рейтинг требований
- `stage5_ranked_final.csv` — финальный рейтинг после нормализации
- `stage5_tools_final.csv`, `stage5_methods_final.csv`, `stage5_tasks_final.csv`
- `top_tools.csv`, `top_methods.csv`, `top_tasks.csv`, `top_all.csv`

**Визуализация:**
- `top_tools.png`, `top_methods.png`, `top_tasks.png`

**Отчёты:**
- `stage6_report.xlsx` — Excel со всеми листами
- `stage6_report.md` — markdown-отчёт