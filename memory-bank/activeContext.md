# Active Context

This file tracks the project's current status, including recent changes, current goals, and open questions.
2025-09-08 21:17:27 - Log of updates made.

*

## Current Focus

* Initializing Memory Bank structure  
* Defining project scope for MCP server research  

## Recent Changes

* Created productContext.md  
* Switched to Architect mode  

## Open Questions/Issues

* Which embedding providers to prioritize?  
* What vector database to use?  
2025-09-08 21:20:17 - Memory Bank initialization complete. Switching to research phase.
[2025-09-09 20:32:51] - Successfully deployed a custom embedding service using FastAPI and `transformers`. The service is now fully functional.
[2025-09-14 12:56:57] - **Focus:** Finalizing the debugging and optimization of the `jina-openai` embedding service.
**Recent Changes:**
- Identified and resolved OOM kill issue by implementing an `asyncio.Semaphore`.
- Tuned the semaphore value to 8 for optimal performance and stability.
- Confirmed via logs that memory usage is now stable under load (~4.4GB peak).
- Updated `decisionLog.md` with the final resolution.
**Next Steps:** Update the project `README.md` with a summary of the problem and solution.
[2025-09-14 17:16:36] - [Current Focus] Verifying the fix for a persistent, slow memory leak that occurs during indexing. A new middleware for aggressive garbage collection has been implemented. Awaiting final test run.
[2025-09-14 17:16:36] - [Recent Changes] Added a FastAPI middleware to trigger `gc.collect()` after each HTTP request to resolve a memory leak related to request/response objects.
[2025-09-18 16:10:22] - Recent Changes: Устранена утечка памяти в сервисе `embeddings`.

**Контекст:**
Основной задачей была диагностика и исправление серьезной утечки памяти, возникающей при высокой нагрузке на эндпоинт `/v1/embeddings`.

**Выполненные действия:**
1.  Проанализированы логи и `tracemalloc` для выявления причины.
2.  Установлено, что проблема в преждевременном парсинге тел запросов.
3.  Внесены изменения в `embeddings/app/app.py`: парсинг тела запроса перенесен внутрь блока семафора.
4.  Сервис `embeddings` был успешно пересобран и перезапущен с примененным исправлением.
5.  Обновлен `decisionLog.md` с подробным описанием проблемы и решения.

**Текущий фокус:**
Завершение документирования изменений в Memory Bank. Следующий шаг - обновление `systemPatterns.md` и `progress.md`.
[2025-09-18 18:30:00] - [Current Focus] Implement a hybrid local development setup for macOS to enable GPU acceleration.

**Problem:** The `embeddings` service, when run inside Docker on macOS, cannot access the host's GPU (Apple MPS), leading to poor performance.
**Constraint:** The solution must not break the existing Docker-based architecture and should be an additive, optional workflow for macOS developers.

**Plan:**
1.  **Isolate Dependencies:** Create a Python virtual environment (`venv`) to manage dependencies for local execution without affecting the global system.
2.  **Install Dependencies:** Install all packages from `embeddings/app/requirements.txt` into the `venv`.
3.  **Create Local Run Script:** Develop a new script, `scripts/run_local.sh`, to automate the local launch of the `embeddings` service. This script will handle environment activation and start the `uvicorn` server.
4.  **Update Documentation:** Add a new section to `README.md` detailing the setup and execution process for local development with GPU acceleration on macOS.
5.  **Code Modification:** Ensure the Python code in `embeddings/app/app.py` correctly prioritizes MPS, then CUDA, then CPU, to maintain portability. (This step was already completed).

This approach allows the `qdrant` service to continue running in Docker, while the `embeddings` service runs natively on macOS for maximum performance.
[2025-09-21 15:58:19] - **Current Focus:** Project optimization and documentation complete. Ready for Git commit. Next: Verify Docker (CPU) version functionality after code changes.

**Recent Changes:**
- Completed performance and memory optimizations for the embeddings service.
- Implemented idle-based memory cleanup mechanism to reclaim memory during idle periods.
- Refactored application to use FastAPI lifespan context manager and dependency injection for better testability.
- Added pytest test suite for memory cleanup logic.
- Updated Memory Bank files (decisionLog.md, progress.md) with all architectural decisions and progress.
- Confirmed memory usage stabilizes at ~870 MB after load, with idle cleanup helping further.

**Open Questions/Issues:**
- Does the Docker-based CPU version still work after refactoring to lifespan and other changes?
- Any breaking changes in API compatibility?