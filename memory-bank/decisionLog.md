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