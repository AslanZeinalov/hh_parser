"""
Быстрая проверка связи с OpenRouter и выбранной моделью.
"""

import os
import json
import requests

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = "inclusionai/ling-3.2-flash:free"
URL = "https://openrouter.ai/api/v1/chat/completions"

if not API_KEY:
    print("ОШИБКА: переменная OPENROUTER_API_KEY не задана.")
    print('Выполни: $env:OPENROUTER_API_KEY="sk-or-v1-..."')
    raise SystemExit(1)

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": "Ты извлекаешь требования из вакансий. Отвечай строго JSON без markdown.",
        },
        {
            "role": "user",
            "content": (
                'Текст вакансии: "Требуется уверенный SQL и Python, опыт построения дашбордов в Power BI". '
                'Верни JSON формата: {"tools": [...], "tasks": [...]}'
            ),
        },
    ],
    "temperature": 0.0,
    "max_tokens": 1000,
    "reasoning": {"enabled": False},
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost",
    "X-Title": "hh-vacancy-analysis",
}

print(f"Модель: {MODEL}")
print("Отправляю тестовый запрос...")

try:
    response = requests.post(URL, headers=headers, json=payload, timeout=60)
except Exception as e:
    print(f"ОШИБКА сети: {e}")
    raise SystemExit(1)

print(f"HTTP статус: {response.status_code}")

if response.status_code != 200:
    print("Тело ответа:")
    print(response.text[:1000])
    raise SystemExit(1)

data = response.json()
message = data["choices"][0]["message"]

print("Поля в message:", list(message.keys()))
content = message.get("content") or ""
print("-" * 60)
print("Ответ модели:")
print(content)
print("-" * 60)

try:
    parsed = json.loads(content)
    print("JSON успешно распарсен:", parsed)
    print("ВСЁ РАБОТЕТ. Можно запускать этап 4.")
except Exception:
    print("Ответ не является чистым JSON.")
    print("В этапе 4 есть запасной парсер, он попробует извлечь JSON из текста.")
    print("Если content пустой, а в message есть поле reasoning — пришли мне вывод.")

usage = data.get("usage", {})
print("Токены:", usage)