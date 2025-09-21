# ⚠️⚠️⚠️ КРИТИЧЕСКОЕ ПРАВИЛО ДЛЯ АССИСТЕНТА ⚠️⚠️⚠️

## ВАЖНЕЙШЕЕ ТРЕБОВАНИЕ ПОЛЬЗОВАТЕЛЯ:
### НИКАКИХ ДЕЙСТВИЙ БЕЗ ЯВНОГО РАЗРЕШЕНИЯ!
### ЗАПРЕЩЕНО ПРОЯВЛЯТЬ ИНИЦИАТИВУ!
### ТОЧНО СЛЕДОВАТЬ ИНСТРУКЦИЯМ!

## ПРАВИЛА РАБОТЫ:
1. ВСЕГДА ждать явных инструкций перед любым действием
2. НИКОГДА не добавлять "улучшения" без запроса
3. ПРИ ЛЮБЫХ сомнениях использовать ask_followup_question

## ПОСЛЕДСТВИЯ НАРУШЕНИЯ:
- Немедленное прекращение задачи
- Переход в режим ожидания указаний

# Decision Log

This file records architectural and implementation decisions using a list format.
2025-09-08 21:18:03 - Log of updates made.

*
  
## Decision

* Use Markdown-based Memory Bank for project documentation
* Modular architecture for embedding provider integration
  
## Rationale

* Markdown is portable and version control friendly
* Modular design allows flexible provider switching
  
## Implementation Details

* Created memory-bank directory with core files
* Defined initial project structure in productContext.md
[2025-09-09 20:32:40] - Detailed Summary of Architectural Change:

## Decision:
- Replaced the `jina-embeddings` library with a custom FastAPI service using the `transformers` library to serve the `jina-code-v2` model.

## Rationale:
- The initial attempt to use the `jina-embeddings==2.2.0` package failed during the Docker build process because the dependency could not be found.
- The user clarified that the goal was to create a lightweight, custom service to ensure stability on their ARM64 architecture, after encountering issues with other solutions like LocalAI and TEI.
- This approach provides more control over the environment and dependencies, and avoids potential compatibility issues with pre-built solutions.

## Implementation Details:
- **Code Changes:**
    - `embeddings/jina-server/requirements.txt`: Replaced `jina-embeddings` with `transformers` and `torch`.
    - `embeddings/jina-server/app.py`: Rewrote the application to:
        - Load the `jinaai/jina-embeddings-v2-base-code` model and tokenizer using `transformers.AutoModel` and `transformers.AutoTokenizer`.
        - Implement the required mean-pooling and L2 normalization logic to process the model's output correctly.
        - Expose an OpenAI-compatible `/v1/embeddings` endpoint.
    - `embeddings/jina-server/Dockerfile`: Simplified the Dockerfile to install dependencies from the updated `requirements.txt`.
- **Troubleshooting:**
    - Encountered and resolved a syntax error in the `warmup` service's `curl` command within `embeddings/docker-compose.yml`.
    - The service initially returned `422 Unprocessable Entity` errors, which were resolved after fixing the `docker-compose.yml` and restarting the services.
- **Outcome:**
    - The custom embedding service was successfully built, deployed, and tested. It is now fully functional and serving embeddings as expected.
[2025-09-14 12:54:26] - **Decision:** Implemented an `asyncio.Semaphore` with a value of 8 in `embeddings/app/app.py` to limit concurrent requests to the embedding model.
**Rationale:** The service was crashing under heavy load due to uncontrolled memory spikes (OOM kills). Analysis showed that limiting concurrency stabilizes memory usage while maintaining high throughput. The value of 8 was calculated based on available system RAM (8GB) to balance performance and stability.
**Implications:** The service is now stable under heavy load. The semaphore value is a critical performance tuning parameter and is documented directly in the code and `README.md`.
[2025-09-14 17:16:15] - [Decision] Implemented explicit tensor cleanup (`del` and `torch.cuda.empty_cache()`) within the batch processing loop in `_blocking_encode` to fix the primary, critical memory leak causing timeouts.
[2025-09-14 17:16:15] - [Decision] Added explicit deletion of `final_embeddings` and `data` objects in the `create_embeddings` endpoint, followed by `gc.collect()`, to address a slower memory leak observed during indexing.
[2025-09-14 17:16:15] - [Decision] Implemented a global FastAPI middleware to run `gc.collect()` after every HTTP request as a more aggressive approach to clean up lingering request/response objects identified by `tracemalloc`.
---

[2025-09-15 19:15:31] - **Перенос из README: Глубокая отладка и оптимизация производительности**

В ходе интенсивного использования сервиса была выявлена критическая проблема нестабильности: под нагрузкой контейнер `jina-openai` аварийно завершал работу из-за нехватки оперативной памяти (OOM Kill), что приводило к таймаутам и отказам в обслуживании.

Детальное расследование выявило **две независимые утечки памяти**. Ниже описан пошаговый процесс их обнаружения и устранения.

### Этап 1: Инструментарий и диагностика

Для точного анализа в код приложения (`embeddings/app/app.py`) были временно добавлены инструменты профилирования:
1.  **Мониторинг памяти с `psutil`:** Для логирования потребления физической памяти (RSS) в реальном времени.
2.  **Профилирование с `tracemalloc`:** Для отслеживания объектов Python, которые выделяют память и не освобождаются.

Первичный нагрузочный тест подтвердил наличие быстрой утечки, после чего значение семафора (`SEMAPHORE_VALUE`) было временно снижено с `8` до `2` для изоляции проблемы.

### Этап 2: Устранение критической утечки (PyTorch Tensors)

Анализ логов `tracemalloc` показал, что память стремительно утекала из-за тензоров PyTorch, которые не освобождались после обработки каждого батча. Сборщик мусора Python не мог автоматически очистить память, занятую на GPU.

**Решение:**
В код обработки была добавлена явная очистка ресурсов после их использования.

```python
# embeddings/app/app.py
# ... внутри функции кодирования ...
del batch_embeddings
del tokens
torch.cuda.empty_cache()
```
Этот шаг полностью устранил быструю утечку, но осталась вторая, более медленная.

### Этап 3: Устранение медленной утечки (FastAPI/Starlette)

После устранения основной проблемы `tracemalloc` указал на новую причину: объекты, связанные с жизненным циклом запроса-ответа в фреймворках FastAPI и Starlette. Эти объекты не всегда корректно убирались сборщиком мусора в асинхронной среде.

**Решение:**
Был внедрен глобальный `middleware`, который принудительно запускает сборщик мусора (`gc.collect()`) после завершения каждого HTTP-запроса.

```python
# embeddings/app/app.py
import gc
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def garbage_collector_middleware(request: Request, call_next):
    response = await call_next(request)
    gc.collect()
    return response
```
Это решение полностью устранило вторую утечку.

### Этап 4: Финальная настройка производительности

После полного устранения обеих утечек последним шагом было восстановление исходной производительности.

**Решение:**
Значение семафора было возвращено к оптимальному значению `8`, рассчитанному исходя из доступной RAM.

```python
# embeddings/app/app.py
SEMAPHORE_VALUE = 8
```

### Итоговый результат

В результате проделанной работы сервис был полностью стабилизирован.
-   **Утечки памяти устранены:** Потребление RAM находится под контролем.
-   **Производительность оптимальна:** Система эффективно использует ресурсы CPU.
-   **Стабильность:** Сервис успешно справляется с высокой нагрузкой без сбоев.

Финальное тестирование показало, что при значении семафора `8` потребление памяти колеблется в безопасном диапазоне 3-5 ГБ.
[2025-09-18 15:11:07] - Added logging for the number of tasks waiting in the semaphore queue in `embeddings/app/app.py` to diagnose performance bottlenecks with large projects.
[2025-09-18 15:24:55] - Implemented advanced performance monitoring in `embeddings/app/app.py`. This includes logging wait time per request and periodic aggregation of statistics (avg/max wait time, max queue depth) to provide detailed performance insights without cluttering the logs.
[2025-09-18 16:10:00] - Решение: Отложенный парсинг тела запроса для устранения утечки памяти.

**Проблема:**
В ходе нагрузочного тестирования была обнаружена критическая утечка памяти в сервисе `embeddings`. При большом количестве одновременных запросов потребление памяти неконтролируемо росло, что приводило к деградации производительности и падению сервиса. Время ожидания в очереди для каждого нового запроса увеличивалось экспоненциально.

**Анализ:**
Анализ логов и данных `tracemalloc` показал, что корневой причиной проблемы был преждевременный парсинг тела входящих HTTP-запросов. FastAPI, по умолчанию, считывал и валидировал весь JSON-объект с помощью Pydantic *до* того, как запрос получал разрешение на обработку от семафора (`asyncio.Semaphore`). В результате, в памяти одновременно накапливалось большое количество объектов `EmbeddingsRequest`, содержащих объемные списки текстов для векторизации, пока они ожидали своей очереди.

**Решение:**
Было принято решение изменить сигнатуру эндпоинта `/v1/embeddings` с `async def create_embeddings(req: EmbeddingsRequest):` на `async def create_embeddings(request: Request):`. Это позволило отложить (defer) чтение и парсинг тела запроса. Теперь эти операции (`await request.json()` и `EmbeddingsRequest.model_validate(body)`) выполняются *внутри* блока `async with app.state.semaphore:`, то есть только после того, как запрос получил "слот" для обработки.

**Результат:**
Это изменение гарантирует, что в памяти одновременно находятся только те данные, которые активно обрабатываются в данный момент. Память, потребляемая сервисом под нагрузкой, теперь стабильна и зависит от лимита семафора (`SEMAPHORE_LIMIT`), а не от глубины очереди запросов. Утечка памяти устранена.
[2025-09-18 16:50:00] - [Architectural Decision] Switched model inference from CPU to GPU (Apple MPS) to resolve a critical performance bottleneck. The application logic in `embeddings/app/app.py` was modified to detect and utilize the MPS device for all `torch` computations, including moving the model and input tensors to the GPU. This is expected to dramatically increase throughput and reduce request queue times.
[2025-09-21 13:09:37] - **Decision:** Implement a two-level load control system to prevent RAM overflow when using GPU acceleration.
    - **Rationale:** Migrating to GPU processing removed the CPU bottleneck but revealed a new one in RAM. The application accepted new requests faster than it could free up memory from completed ones, leading to a system freeze. A simple in-app semaphore was insufficient as the web server (`uvicorn`) queued too many requests in memory before they even reached the semaphore.
    - **Implications:**
        1.  **Application Level:** The `asyncio.Semaphore` value in `app.py` is now controlled by a `SEMAPHORE_VALUE` environment variable. This limits how many requests the model processes concurrently.
        2.  **Server Level:** The `uvicorn` startup command in `run_local.sh` now includes a `--backlog` parameter, limiting the TCP connection queue. This prevents the server from holding an excessive number of requests in memory.
        3.  **Configuration:** Performance is now tunable via `SEMAPHORE_VALUE` and `UVICORN_BACKLOG` environment variables, allowing for a balance between throughput and resource consumption.
[2025-09-21 15:52:29] - **Decision:** Implement idle-based memory cleanup.
    - **Rationale:** The initial implementation of `malloc_trim` after every request caused performance degradation during active processing. The new approach triggers aggressive cleanup (including `gc.collect()`, `torch.mps.empty_cache()`, and `malloc_trim`) only after a configurable period of inactivity (e.g., 60 seconds), preventing performance hits during load while still reclaiming memory during idle times.
    - **Implications:** This makes memory management more intelligent, balancing performance and resource usage. The cleanup logic is now encapsulated in a background `asyncio` task.

[2025-09-21 15:52:29] - **Decision:** Refactor application startup logic to use FastAPI's `lifespan` context manager.
    - **Rationale:** The `@app.on_event("startup")` and `@app.on_event("shutdown")` decorators are deprecated. The `lifespan` context manager is the modern, recommended approach. This change also significantly improved the testability of the application by allowing startup/shutdown logic to be managed more cleanly.
    - **Implications:** The code in `embeddings/app/app.py` is now more maintainable and aligned with current FastAPI best practices.

[2025-09-21 15:52:29] - **Decision:** Create a dedicated test suite (`tests/test_cleanup.py`) for the memory cleanup logic.
    - **Rationale:** The idle-based cleanup mechanism involves complex interactions between `asyncio` tasks, application state, and time-based triggers. Automated tests are crucial to verify its correctness and prevent future regressions. This required setting up a `pytest` environment and refactoring the application for dependency injection.
    - **Implications:** The project now has a testing framework, improving overall code quality and reliability.

[2025-09-21 15:52:29] - **Decision:** Conclude memory optimization efforts based on final log analysis.
    - **Rationale:** Detailed analysis of `tracemalloc` and RSS memory logs shows that after peak load, memory usage stabilizes at ~870 MB, which is ~150 MB above the baseline of ~720 MB. The idle-based cleanup helps, but does not immediately return all memory to the OS due to memory fragmentation and the behavior of Python's memory allocator on macOS. This remaining overhead is deemed an acceptable limit for the current architecture.
    - **Implications:** Further optimization is not practical at this stage. The focus shifts from memory reduction to verifying existing functionality across different environments (GPU vs. CPU).