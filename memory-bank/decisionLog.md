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