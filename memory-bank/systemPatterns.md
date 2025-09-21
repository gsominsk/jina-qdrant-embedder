# System Patterns

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-09-08 21:18:23 - Log of updates made.

*

## Coding Patterns

* TypeScript for server implementation  
* REST API conventions  

## Architectural Patterns

* Microservices for embedding providers  
* Singleton for configuration management  

## Testing Patterns

* Unit tests with Jest  
* Integration tests for API endpoints  
  
## Tool Usage Patterns  
* Для обновления отдельных строк в файлах используйте инструмент `search_and_replace`, заменяя только одну строку за раз  
[2025-09-18 16:10:34] - Паттерн: Отложенный парсинг запроса (Deferred Request Parsing)

**Контекст:**
Применяется в асинхронных веб-сервисах, которые обрабатывают потенциально "тяжелые" запросы (с большим телом) и используют очередь (например, на основе семафора) для ограничения параллелизма.

**Проблема:**
Стандартное поведение веб-фреймворков (например, FastAPI) может приводить к чтению и валидации всего тела запроса до того, как запрос будет фактически взят в обработку. Если в очереди скапливается много "тяжелых" запросов, это приводит к значительному потреблению памяти.

**Решение:**
Сигнатура обработчика эндпоинта объявляется таким образом, чтобы принимать сырой объект запроса (например, `fastapi.Request`), а не модель данных (например, Pydantic). Чтение, парсинг и валидация тела запроса выполняются явным образом только *после* того, как запрос прошел через механизм очереди (например, получил слот семафора).

**Преимущества:**
-   **Стабильное потребление памяти:** Память расходуется только на активно обрабатываемые запросы, а не на ожидающие в очереди.
-   **Устойчивость к всплескам нагрузки:** Сервис не падает из-за нехватки памяти при большом количестве входящих запросов.
[2025-09-21 13:09:53] - **Pattern:** Two-Level Load Control for High-Throughput Services.
    - **Context:** Used in the `embeddings` service to manage resource consumption under heavy load, especially when a fast component (GPU) is fed by a slower one (network I/O).
    - **Description:** This pattern combines application-level and server-level concurrency limits.
        1.  **Server-Level Limiter (`uvicorn --backlog`):** Acts as a coarse-grained, "front-door" filter. It limits the number of TCP connections the server will queue, preventing it from accepting more requests than the system can hold in memory.
        2.  **Application-Level Limiter (`asyncio.Semaphore`):** Acts as a fine-grained, "processing-gate" filter. It controls how many requests are actively being processed by the most resource-intensive part of the application (e.g., the ML model).
    - **Benefit:** Prevents memory exhaustion by stopping the system from accepting more work than it can handle, creating a predictable and stable processing pipeline.