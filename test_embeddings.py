import requests
import json
import time

# --- Конфигурация ---
URL = "http://localhost:4000/v1/embeddings"
MODEL = "jina-code-v2"
NUM_SENTENCES = 128 # Уменьшаем количество предложений для ускорения теста
NUM_ITERATIONS = 3  # Уменьшаем количество итераций

for i in range(NUM_ITERATIONS):
    print(f"\n--- Итерация {i+1}/{NUM_ITERATIONS} ---")
    # --- Генерация тестовых данных ---
    print(f"[*] Генерируем {NUM_SENTENCES} тестовых предложений...")
    sentences = [f"Это тестовое предложение номер {j} для итерации {i+1}." for j in range(NUM_SENTENCES)]

    # --- Формирование запроса ---
    payload = {
        "model": MODEL,
        "input": sentences
    }

    # --- Отправка запроса и замер времени ---
    print(f"[*] Отправляем запрос на {URL} с {len(sentences)} предложениями...")
    start_time = time.time()

    try:
        response = requests.post(URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=60) # Уменьшаем таймаут
        response.raise_for_status() # Проверка на HTTP ошибки (4xx или 5xx)
        
        end_time = time.time()
        
        # --- Анализ ответа ---
        data = response.json()
        
        print(f"[+] Запрос успешно выполнен за {end_time - start_time:.2f} секунд.")
        
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) == NUM_SENTENCES:
            print(f"[+] Сервер вернул корректное количество эмбеддингов: {len(data['data'])}.")
            first_embedding = data["data"][0]
            if "embedding" in first_embedding and isinstance(first_embedding["embedding"], list):
                print(f"[+] Формат эмбеддинга корректный (длина первого вектора: {len(first_embedding['embedding'])}).")
            else:
                print("[-] ОШИБКА: Некорректный формат эмбеддинга в ответе.")
        else:
            print("[-] ОШИБКА: Ответ от сервера не содержит ожидаемых данных или их количество неверно.")
            print("Ответ сервера:", json.dumps(data, indent=2))

    except requests.exceptions.RequestException as e:
        end_time = time.time()
        print(f"[-] ОШИБКА: Не удалось выполнить запрос за {end_time - start_time:.2f} секунд.")
        print(f"Причина: {e}")
    
    time.sleep(1) # Небольшая пауза между запросами