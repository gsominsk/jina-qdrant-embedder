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

## In-Depth Debugging and Performance Optimization

During intensive use, a critical instability issue was identified: under heavy load, the `jina-openai` container would crash due to an out-of-memory (OOM) error, leading to timeouts and service failures.

A detailed investigation revealed **two independent memory leaks**. The step-by-step process of their detection and resolution is described below.

### Step 1: Tooling and Diagnostics

For an accurate analysis, profiling tools were temporarily added to the application code (`embeddings/app/app.py`):
1.  **Memory Monitoring with `psutil`:** To log real-time physical memory consumption (RSS).
2.  **Profiling with `tracemalloc`:** To track Python objects that allocate memory and are not released.

An initial load test confirmed a fast memory leak, after which the semaphore value (`SEMAPHORE_VALUE`) was temporarily reduced from `8` to `2` to isolate the problem.

### Step 2: Fixing the Critical Leak (PyTorch Tensors)

Analysis of `tracemalloc` logs showed that memory was rapidly leaking due to PyTorch tensors that were not being released after processing each batch. Python's garbage collector could not automatically clear the memory occupied on the GPU.

**Solution:**
Explicit resource cleanup was added to the processing code after use.

```python
# embeddings/app/app.py
# ... inside the encoding function ...
del batch_embeddings
del tokens
torch.cuda.empty_cache()
```
This step completely eliminated the fast leak, but a second, slower one remained.

### Step 3: Fixing the Slow Leak (FastAPI/Starlette)

After fixing the main issue, `tracemalloc` pointed to a new cause: objects related to the request-response lifecycle in the FastAPI and Starlette frameworks. These objects were not always being correctly garbage-collected in the asynchronous environment.

**Solution:**
A global middleware was implemented to forcibly run the garbage collector (`gc.collect()`) after each HTTP request is complete.

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
This solution completely eliminated the second leak.

### Step 4: Final Performance Tuning

After both leaks were fully resolved, the final step was to restore the initial performance.

**Solution:**
The semaphore value was returned to the optimal value of `8`, which was calculated based on the available RAM.

```python
# embeddings/app/app.py
SEMAPHORE_VALUE = 8
```

### Final Result

As a result of this work, the service was fully stabilized.
-   **Memory Leaks Fixed:** RAM consumption is under control.
-   **Performance Optimized:** The system effectively uses CPU resources.
-   **Stability:** The service successfully handles high loads without crashing.

Final testing showed that with a semaphore value of `8`, memory consumption fluctuates within a safe 3-5 GB range.

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