# Project Indexing with Custom Embeddings

This project sets up a local environment for code indexing using a custom embedding service and a Qdrant vector database.

## System Overview

The system consists of two main services, orchestrated with Docker Compose:

1.  **Qdrant:** A vector database used to store and search for code embeddings. It runs in its own container and exposes its API on port `6333`.
2.  **Embeddings Service:** A custom, lightweight FastAPI application that serves the `jina-code-v2` model. It uses the `transformers` library to generate embeddings and exposes an OpenAI-compatible API on port `4000`.

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

1.  **Roo Code to FastAPI:** Your IDE, using settings from `roo-code-config.json`, sends a code snippet to the custom FastAPI service on port `4000`.
2.  **FastAPI to Model:** The FastAPI service (the layer) takes the code and passes it to the `jina-code-v2` model, which runs in the same container.
3.  **Model to FastAPI:** The model converts the code into a numerical vector (the embedding) and returns it to the service.
4.  **FastAPI to Roo Code:** The service wraps this vector in a standard JSON format and sends it back to your IDE.
5.  **Roo Code to Qdrant:** Your IDE receives the embedding and sends it to the Qdrant database on port `6333`, where it is stored and indexed for future searches.

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

## Performance and Semaphore Management

The stability and performance of the service are critically dependent on managing concurrency. This is achieved using an `asyncio.Semaphore`.

### Semaphore Configuration
The semaphore, defined in `embeddings/app/app.py`, limits the number of concurrent requests processed by the model.

**Solution:** The semaphore value was set to the optimal value of `8`, calculated based on available system resources (8GB RAM, 4 CPU cores).

```python
# embeddings/app/app.py
SEMAPHORE_VALUE = 8
```

### Performance Results
- **Optimized Performance:** The system effectively utilizes CPU resources.
- **Memory Stability:** Final testing showed that with a semaphore value of `8`, memory consumption fluctuates within a safe **3-5 GB** range under load, preventing OOM crashes.

### How to Tune the Semaphore
The `SEMAPHORE_VALUE` is the most important parameter for performance tuning.

- **Current Value:** The optimal value is **8** for a system with 8GB RAM.
- **When to Change It:**
  - **More RAM:** You can try cautiously increasing the value (e.g., to `10` or `12`) to potentially increase throughput. Monitor memory usage closely.
  - **Less RAM:** If you experience OOM crashes, you **must** decrease this value (e.g., to `4` or `6`).
- **How to Change It:** Edit the `SEMAPHORE_VALUE` constant directly in the [`embeddings/app/app.py`](embeddings/app/app.py:1) file and restart the service.

## Resource Consumption (Idle)

When the services are running but not actively processing requests, their baseline memory consumption is:

-   **Embeddings Service (Jina):** ~921 MiB
-   **Qdrant Database:** ~261 MiB

## Visual Studio Code Integration

For maximum convenience, the project is configured to be managed directly from VS Code using hotkeys. To do this, you need to configure two files in your VS Code setup.

### 1. Task Configuration (`tasks.json`)

Create or update the `tasks.json` file in your user-level VS Code settings directory.

*   **Path on macOS:** `~/Library/Application Support/Code/User/tasks.json`
*   **Path on Windows:** `%APPDATA%\Code\User\tasks.json`
*   **Path on Linux:** `~/.config/Code/User/tasks.json`

Paste the following content into it, **making sure to replace** `$HOME/sandbox/mcp` with the actual path to your project:

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
        "\\033[1mJina/Qdrant — Hotkeys\\033[0m\\n\\n  ⌘⇧9   startall + warmup      — Start Qdrant, Jina, and warm up embeddings\\n  ⌘⇧=   restartall            — Restart all services\\n  ⌘⇧0   help: embeddings shortcuts  — Show this help screen\\n  ⌘⇧-   stopall               — Stop Jina and Qdrant\\n  ⌘⇧8   qdrant restart        — Restart Qdrant\\n  ⌘⇧7   jina start + warmup   — Start Jina and warm up\\n  ⌘⇧6   jina stop             — Stop Jina\\n\\nHint: Commands are configured in User Tasks and Keyboard Shortcuts (JSON)."
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

### 2. Hotkey Configuration (`keybindings.json`)

Similarly, create or update the `keybindings.json` file.

*   **Path on macOS:** `~/Library/Application Support/Code/User/keybindings.json`
*   **Path on Windows:** `%APPDATA%\Code\User\keybindings.json`
*   **Path on Linux:** `~/.config/Code/User/keybindings.json`

Paste the following content into it:

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

### Available Commands (Hotkeys)

After setup, you can manage the services with the following key combinations (for macOS; replace `cmd` with `ctrl` for Windows/Linux):

| Hotkey          | Command                  | Description                                        |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 9`     | `startall + warmup`      | Start Qdrant, Jina, and warm up embeddings         |
| `⌘ + ⇧ + =`     | `restartall`             | Restart all services                               |
| `⌘ + ⇧ + -`     | `stopall`                | Stop Jina and Qdrant                               |
| `⌘ + ⇧ + 8`     | `qdrant restart`         | Restart only Qdrant                                |
| `⌘ + ⇧ + 7`     | `jina start + warmup`    | Start only Jina and warm up                        |
| `⌘ + ⇧ + 6`     | `jina stop`              | Stop only Jina                                     |
| `⌘ + ⇧ + 0`     | `help: embeddings shortcuts` | Show this help screen in the VS Code terminal      |
