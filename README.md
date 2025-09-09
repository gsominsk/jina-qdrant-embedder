# Project Indexing with Custom Embeddings

This project sets up a local environment for code indexing using a custom embedding service and a Qdrant vector database.

## System Overview

The system consists of two main services, orchestrated with Docker Compose:

1.  **Qdrant:** A vector database used to store and search for code embeddings. It runs in its own container and exposes its API on port `6333`.
2.  **Embeddings Service:** A custom, lightweight FastAPI application that serves the `jina-code-v2` model. It uses the `transformers` library to generate embeddings and exposes an OpenAI-compatible API on port `4000`.

## How It Works

1.  **Roo Code Configuration:** 
    *   It points the `embeddingProvider` to the custom service's `baseUrl`: `http://localhost:4000/v1`.
    *   It specifies the `vectorStore` as `qdrant` and provides its URL: `http://localhost:6333`.

    Below is an example of a full, valid configuration file:

    ```json
    {
      "embeddingProvider": "openai",
      "baseUrl": "http://localhost:4000/v1",
      "modelId": "jina-code-v2",
      "embeddingDimension": 768,
      "vectorStore": "qdrant",
      "qdrantUrl": "http://localhost:6333"
    }
    ```

2.  **Embedding Generation:** When Roo Code needs to generate an embedding for a piece of code, it sends a request to `http://localhost:4000/v1/embeddings`.

3.  **Custom Service (`embeddings/jina-server`):** The FastAPI application receives the request, uses the `jinaai/jina-embeddings-v2-base-code` model to generate a vector embedding, and returns it in a format that mimics the OpenAI API.

4.  **Vector Storage:** Roo Code then takes this embedding and stores it in the Qdrant database, which is running locally.

## How to Run

The services are managed by two separate `docker-compose.yml` files. You need to start both for the system to be fully operational.

1.  **Start the Qdrant Database:**
    Open a terminal and run the following command from the project root directory:
    ```bash
    docker-compose -f qdrant/docker-compose.yml up -d
    ```
    This will start the Qdrant container and expose its service on port `6333`.

2.  **Start the Embeddings Service:**
    In another terminal, run the following command from the project root directory:
    ```bash
    docker-compose -f embeddings/docker-compose.yml up -d
    ```
    This will build and start the custom FastAPI application. The service will be available on port `4000`.

Once both services are running, the system is ready to be used by Roo Code.

## Интеграция с Visual Studio Code

Для максимального удобства проект настроен для управления прямо из VS Code с помощью горячих клавиш. Для этого необходимо настроить два файла в конфигурации VS Code.

### 1. Настройка задач (`tasks.json`)

Создайте или обновите файл `tasks.json` в вашей пользовательской директории настроек VS Code.

*   **Путь на macOS:** `~/Library/Application Support/Code/User/tasks.json`
*   **Путь на Windows:** `%APPDATA%\Code\User\tasks.json`
*   **Путь на Linux:** `~/.config/Code/User/tasks.json`

Вставьте в него следующее содержимое, **обязательно заменив** `$HOME/sandbox/mcp` на актуальный путь к вашему проекту:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "startall + warmup",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "start", "all"]
    },
    {
      "label": "stopall",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "stop", "all"]
    },
    {
      "label": "restartall",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "restart", "all"]
    },
    {
      "label": "qdrant restart",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "restart", "qdrant"]
    },
    {
      "label": "jina start + warmup",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "start", "jina"]
    },
    {
      "label": "jina stop",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "stop", "jina"]
    },
    {
      "label": "help: embeddings shortcuts",
      "type": "shell",
      "command": "echo",
      "args": [
        "-e",
        "\\033[1mJina/Qdrant — горячие клавиши\\033[0m\\n\\n  ⌘⇧9   startall + warmup      — Запустить Qdrant, Jina и прогреть эмбеддинги\\n  ⌘⇧=   restartall            — Перезапустить все сервисы\\n  ⌘⇧0   help: embeddings shortcuts  — Показать этот экран\\n  ⌘⇧-   stopall               — Остановить Jina и Qdrant\\n  ⌘⇧8   qdrant restart        — Перезапустить Qdrant\\n  ⌘⇧7   jina start + warmup   — Запустить Jina и прогреть\\n  ⌘⇧6   jina stop             — Остановить Jina\\n\\nПодсказка: команды настраиваются в User Tasks и Keyboard Shortcuts (JSON)."
      ],
      "presentation": {
        "reveal": "always",
        "panel": "dedicated",
        "clear": true
      },
      "problemMatcher": []
    }
  ]
}
```

### 2. Настройка горячих клавиш (`keybindings.json`)

Аналогично, создайте или обновите файл `keybindings.json`.

*   **Путь на macOS:** `~/Library/Application Support/Code/User/keybindings.json`
*   **Путь на Windows:** `%APPDATA%\Code\User\keybindings.json`
*   **Путь на Linux:** `~/.config/Code/User/keybindings.json`

Вставьте в него следующее содержимое:

```json
[
  {
    "key": "cmd+shift+9",
    "command": "workbench.action.tasks.runTask",
    "args": "startall + warmup"
  },
  {
    "key": "cmd+shift+=",
    "command": "workbench.action.tasks.runTask",
    "args": "restartall"
  },
  {
    "key": "cmd+shift+0",
    "command": "workbench.action.tasks.runTask",
    "args": "help: embeddings shortcuts"
  },
  {
    "key": "cmd+shift+-",
    "command": "workbench.action.tasks.runTask",
    "args": "stopall"
  },
  {
    "key": "cmd+shift+8",
    "command": "workbench.action.tasks.runTask",
    "args": "qdrant restart"
  },
  {
    "key": "cmd+shift+7",
    "command": "workbench.action.tasks.runTask",
    "args": "jina start + warmup"
  },
  {
    "key": "cmd+shift+6",
    "command": "workbench.action.tasks.runTask",
    "args": "jina stop"
  }
]
```

### Доступные команды (горячие клавиши)

После настройки вы сможете управлять сервисами с помощью следующих сочетаний клавиш (для macOS, замените `cmd` на `ctrl` для Windows/Linux):

| Горячая клавиша | Команда                  | Описание                                           |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 9`     | `startall + warmup`      | Запустить Qdrant, Jina и прогреть эмбеддинги        |
| `⌘ + ⇧ + =`     | `restartall`             | Перезапустить все сервисы                          |
| `⌘ + ⇧ + -`     | `stopall`                | Остановить Jina и Qdrant                           |
| `⌘ + ⇧ + 8`     | `qdrant restart`         | Перезапустить только Qdrant                        |
| `⌘ + ⇧ + 7`     | `jina start + warmup`    | Запустить только Jina и прогреть                    |
| `⌘ + ⇧ + 6`     | `jina stop`              | Остановить только Jina                             |
| `⌘ + ⇧ + 0`     | `help: embeddings shortcuts` | Показать эту справку в терминале VS Code           |
## Architecture Diagram

Here is a simple ASCII diagram illustrating the data flow:

```
+--------------------------+
|      Roo Code Client     |
| (in your IDE, configured |
| via roo-code-config.json)|
+--------------------------+
           |
           | 1. POST code to be embedded
           v
+--------------------------+
|  Custom FastAPI Service |
|  (Docker, Port 4000)     |
|--------------------------|
|   |                      |
|   | 2. Process with...   |
|   v                      |
| +--------------------+   |
| | jina-code-v2 Model |   |
| +--------------------+   |
|   ^                      |
|   | 3. Return vector     |
|   |                      |
+--------------------------+
           |
           | 4. Return OpenAI-compatible embedding
           v
+--------------------------+
|      Roo Code Client     |
| (receives embedding)     |
+--------------------------+
           |
           | 5. Store embedding in...
           v
+--------------------------+
|    Qdrant Vector DB      |
|    (Docker, Port 6333)   |
+--------------------------+
```

### Explanation of the Flow:

1.  **Roo Code to FastAPI:** Your IDE, using the settings from `roo-code-config.json`, sends a piece of code to the custom FastAPI service on port `4000`.
2.  **FastAPI to Model:** The FastAPI service (the "прослойка" or layer) takes the code and gives it to the `jina-code-v2` model, which is running inside the same container.
3.  **Model to FastAPI:** The model converts the code into a numerical vector (the embedding) and sends it back to the service.
4.  **FastAPI to Roo Code:** The service wraps this vector in a standard JSON format and sends it back to your IDE.
5.  **Roo Code to Qdrant:** Your IDE receives the embedding and sends it to the Qdrant database on port `6333`, where it is stored and indexed for future searches.