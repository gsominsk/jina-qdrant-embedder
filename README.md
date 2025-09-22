# Project Indexing with Custom Embeddings

This project sets up a local environment for code indexing using a custom embedding service and a Qdrant vector database.

## System Overview

The system consists of two main services, orchestrated with Docker Compose:

1.  **Qdrant:** A vector database used to store and search for code embeddings. It runs in its own container and exposes its API on port `6333`.
2.  **Embeddings Service:** A custom, lightweight FastAPI application that serves the `jina-code-v2` model. It uses the `transformers` library to generate embeddings and exposes an OpenAI-compatible API on port `4000`.

## Architecture Diagram

Here is a simple ASCII diagram illustrating the data flow:

```
+---------------------------------+
|        Roo Code Client          |
| (in your IDE, configured via    |
|  roo-code-config.json)          |
+---------------------------------+
            |
            | 1. POST code to be embedded
            v
+---------------------------------+
|    Custom FastAPI Service       |
|    (Docker, Port 4000)          |
|---------------------------------|
|   |        Health: /health      |
|   | 2. Process with...          |
|   v                             |
| +-----------------------------+ |
| | jinaai/jina-embeddings-v2-  | |
| | base-code Model             | |
| +-----------------------------+ |
|   ^                             |
|   | 3. Return vector            |
|   |                             |
+---------------------------------+
            |
            | 4. Return OpenAI-compatible embedding
            v
+---------------------------------+
|        Roo Code Client          |
|    (receives embedding)         |
+---------------------------------+
            |
            | 5. Store embedding in...
            v
+---------------------------------+
|      Qdrant Vector DB           |
|      (Docker, Port 6333)        |
|      Health: /collections       |
+---------------------------------+

Warmup Service: Initializes model on startup
```

### Explanation of the Flow:

1.  **Roo Code to FastAPI:** Your IDE, using settings from `roo-code-config.json`, sends a code snippet to the custom FastAPI service on port `4000`.
2.  **FastAPI to Model:** The FastAPI service (the layer) takes the code and passes it to the `jinaai/jina-embeddings-v2-base-code` model, which runs in the same container.
3.  **Model to FastAPI:** The model converts the code into a numerical vector (the embedding) and returns it to the service.
4.  **FastAPI to Roo Code:** The service wraps this vector in a standard JSON format and sends it back to your IDE.
5.  **Roo Code to Qdrant:** Your IDE receives the embedding and sends it to the Qdrant database on port `6333`, where it is stored and indexed for future searches.

**Additional Services:**
- **Warmup Service:** Automatically initializes the model on container startup by sending a test request.
- **Health Checks:** Both services expose health endpoints (`/health` for embeddings, `/collections` for Qdrant) for monitoring availability.

## How It Works

1.  **Roo Code Configuration:**
    *   It points the `embeddingProvider` to the custom service's `baseUrl`: `http://localhost:4000/v1`.
    *   It specifies the `vectorStore` as `qdrant` and provides its URL: `http://localhost:6333`.

    Below is an example of a full, valid configuration file:

    ```json
    {
      "embeddingProvider": "openai",
      "baseUrl": "http://localhost:4000/v1",
      "modelId": "jinaai/jina-embeddings-v2-base-code",
      "embeddingDimension": 768,
      "vectorStore": "qdrant",
      "qdrantUrl": "http://localhost:6333"
    }
    ```

2.  **Embedding Generation:** When Roo Code needs to generate an embedding for a piece of code, it sends a request to `http://localhost:4000/v1/embeddings`.

3.  **Custom Service (`embeddings/jina-server`):** The FastAPI application receives the request, uses the `jinaai/jina-embeddings-v2-base-code` model to generate a vector embedding, and returns it in a format that mimics the OpenAI API.

4.  **Vector Storage:** Roo Code then takes this embedding and stores it in the Qdrant database, which is running locally.

## How to Run

This project offers two primary methods for running the services, depending on your operating system and performance needs. All operations are centralized through the `./scripts/manage.sh` script.

### Option 1: Docker-Based Environment (CPU / CUDA)

This is the universal, cross-platform method. It's ideal for standard development on any OS and for production environments, especially those with NVIDIA GPUs, as Docker can utilize CUDA for acceleration.

-   **Start All Services:**
    ```bash
    ./scripts/manage.sh start all
    ```

-   **Stop All Services:**
    ```bash
    ./scripts/manage.sh stop all
    ```

-   **Restart All Services:**
    ```bash
    ./scripts/manage.sh restart all
    ```

### Option 2: Hybrid Environment for macOS (Apple Silicon GPU)

This is a specialized, high-performance setup for developers on **macOS with Apple Silicon (M1/M2/M3)**. It is necessary because Docker on macOS cannot access the host's GPU (MPS). This hybrid approach runs the performance-critical `embeddings` service natively on the host to unlock full GPU acceleration, while the `qdrant` database continues to run conveniently in Docker.

#### Prerequisites

You must have [pyenv](https://github.com/pyenv/pyenv#installation) and [tmux](https://github.com/tmux/tmux/wiki/Installing) installed. You can install them via Homebrew:
```bash
brew install pyenv tmux
```

#### One-Time Setup

Before the first run, prepare the local Python environment with a single command:
```bash
./scripts/manage.sh local setup
```
This script automates:
1.  Installation of the correct Python version via `pyenv`.
2.  Creation of a local virtual environment (`./venv`).
3.  Installation of all required Python dependencies.

#### Running the Hybrid Environment

1.  **Start Qdrant (in Docker):**
    ```bash
    ./scripts/manage.sh start qdrant
    ```

2.  **Start Embeddings Service (Locally on macOS):**
    ```bash
    ./scripts/manage.sh local start
    ```
    This starts the service in a background `tmux` session with semaphore value `2` (optimized for MPS GPU) and logs all output to `logs/embeddings_local.log`.

#### Managing the Local Service

-   **View Real-time Logs:**
    Attach to the background session to see the live output from the service.
    ```bash
    ./scripts/manage.sh local logs
    ```
    *(To detach from the log view, press `Ctrl-b` then `d`)*

-   **Stop the Local Service:**
    ```bash
    ./scripts/manage.sh local stop
    ```

-   **Restart the Local Service:**
    ```bash
    ./scripts/manage.sh local restart
    ```

## Performance and Semaphore Management

The stability and performance of the service are critically dependent on managing concurrency. This is achieved using an `asyncio.Semaphore`.

### Semaphore Configuration
The semaphore, defined in `embeddings/app/app.py`, limits the number of concurrent requests processed by the model.

**Default Values:**
- **Docker CPU mode:** Optimal value is `8` (calculated for 8GB RAM, 4 CPU cores)
- **macOS GPU (MPS) mode:** Current default is `2` (suitable for local GPU execution)

```python
# embeddings/app/app.py
SEMAPHORE_VALUE = int(os.environ.get("SEMAPHORE_VALUE", "4"))  # Default 4 for macOS GPU
```

### How to Tune the Semaphore
The `SEMAPHORE_VALUE` is the most important parameter for performance tuning.

- **Docker CPU Mode:** Use `8` for systems with 8GB RAM and 4 CPU cores.
- **macOS GPU Mode:** Use `4` for optimal MPS performance.
- **When to Change It:**
  - **More RAM:** You can try cautiously increasing the value (e.g., to `10` or `12`) to potentially increase throughput. Monitor memory usage closely.
  - **Less RAM:** If you experience OOM crashes, you **must** decrease this value (e.g., to `4` or `6`).
- **How to Change It:** Set the `SEMAPHORE_VALUE` environment variable or edit the constant directly in the [`embeddings/app/app.py`](embeddings/app/app.py:1) file and restart the service.

## Advanced Features

The embeddings service includes several advanced features for optimal performance and monitoring:

### Idle-Based Memory Cleanup

When the service is idle for 60 seconds, it automatically triggers aggressive memory cleanup:
- Python garbage collection (`gc.collect()`)
- PyTorch cache cleanup (MPS/CUDA)
- Memory release back to OS using `malloc_trim` (Linux/macOS)

### Statistics Logging

The service logs aggregated statistics every 30 seconds during active operation:
- Total requests processed
- Average and maximum wait times
- Maximum queue depth

### Memory Profiling

Built-in memory profiling using `tracemalloc` provides detailed memory usage analysis for each request, helping identify and resolve memory issues.

### Health Monitoring

The service exposes a `/health` endpoint for monitoring service availability.

## Resource Consumption

### Idle Consumption

When the services are running but not actively processing requests, their baseline memory consumption is:

-   **Embeddings Service (Jina):** ~921 MiB
-   **Qdrant Database:** ~261 MiB

### Peak Load Consumption

Under high load, memory usage varies by deployment mode:

-   **Docker CPU Mode (semaphore = 8):** Peak memory consumption fluctuates within a safe **3-5 GB** range, preventing OOM crashes.
-   **macOS GPU Mode (semaphore = 2):** Peak memory consumption reaches ~4 GB under load. After initial warmup, stabilizes at ~2.7 GB for ongoing operation.

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
      "label": "local start",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "local", "start"]
    },
    {
      "label": "local stop",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "local", "stop"]
    },
    {
      "label": "local restart",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "local", "restart"]
    },
    {
      "label": "local logs",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "local", "logs"]
    },
    {
      "label": "local setup",
      "type": "shell",
      "command": "bash",
      "args": ["$HOME/sandbox/mcp/scripts/manage.sh", "local", "setup"]
    },
    {
      "label": "help: embeddings shortcuts",
      "type": "shell",
      "command": "echo",
      "args": [
        "-e",
        "\\033[1mJina/Qdrant — Hotkeys\\033[0m\\n\\n\\033[1mDocker Mode:\\033[0m\\n  ⌘⇧9   startall + warmup      — Start Qdrant, Jina, and warm up embeddings\\n  ⌘⇧=   restartall            — Restart all services\\n  ⌘⇧-   stopall               — Stop Jina and Qdrant\\n  ⌘⇧8   qdrant restart        — Restart Qdrant\\n  ⌘⇧7   jina start + warmup   — Start Jina and warm up\\n  ⌘⇧6   jina stop             — Stop Jina\\n\\n\\033[1mLocal Mode (macOS GPU):\\033[0m\\n  ⌘⇧1   local start           — Start local embeddings service\\n  ⌘⇧2   local stop            — Stop local service\\n  ⌘⇧3   local restart         — Restart local service\\n  ⌘⇧4   local logs            — View local service logs\\n  ⌘⇧5   local setup           — Setup local environment\\n\\n  ⌘⇧0   help: embeddings shortcuts  — Show this help screen\\n\\nHint: Commands are configured in User Tasks and Keyboard Shortcuts (JSON)."
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
  },
  {
    "key": "cmd+shift+1",
    "command": "workbench.action.tasks.runTask",
    "args": "local start"
  },
  {
    "key": "cmd+shift+2",
    "command": "workbench.action.tasks.runTask",
    "args": "local stop"
  },
  {
    "key": "cmd+shift+3",
    "command": "workbench.action.tasks.runTask",
    "args": "local restart"
  },
  {
    "key": "cmd+shift+4",
    "command": "workbench.action.tasks.runTask",
    "args": "local logs"
  },
  {
    "key": "cmd+shift+5",
    "command": "workbench.action.tasks.runTask",
    "args": "local setup"
  }
]
```

### Available Commands (Hotkeys)

After setup, you can manage the services with the following key combinations (for macOS; replace `cmd` with `ctrl` for Windows/Linux):

#### Docker Mode Commands
| Hotkey          | Command                  | Description                                        |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 9`     | `startall + warmup`      | Start Qdrant, Jina, and warm up embeddings         |
| `⌘ + ⇧ + =`     | `restartall`             | Restart all services                               |
| `⌘ + ⇧ + -`     | `stopall`                | Stop Jina and Qdrant                               |
| `⌘ + ⇧ + 8`     | `qdrant restart`         | Restart only Qdrant                                |
| `⌘ + ⇧ + 7`     | `jina start + warmup`    | Start only Jina and warm up                        |
| `⌘ + ⇧ + 6`     | `jina stop`              | Stop only Jina                                     |

#### Local Mode Commands (macOS GPU)
| Hotkey          | Command                  | Description                                        |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 1`     | `local start`            | Start local embeddings service                     |
| `⌘ + ⇧ + 2`     | `local stop`             | Stop local service                                 |
| `⌘ + ⇧ + 3`     | `local restart`          | Restart local service                              |
| `⌘ + ⇧ + 4`     | `local logs`             | View local service logs                            |
| `⌘ + ⇧ + 5`     | `local setup`            | Setup local environment                            |

#### General Commands
| Hotkey          | Command                  | Description                                        |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 0`     | `help: embeddings shortcuts` | Show this help screen in the VS Code terminal      |
