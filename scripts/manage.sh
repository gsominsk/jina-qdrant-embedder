#!/bin/bash
set -e

# --- Конфигурация ---
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

QDRANT_COMPOSE_FILE="$PROJECT_ROOT/qdrant/docker-compose.yml"
EMBEDDINGS_COMPOSE_FILE="$PROJECT_ROOT/embeddings/docker-compose.yml"

EMBEDDINGS_HEALTH_URL="http://localhost:4000/health"
EMBEDDINGS_WARMUP_URL="http://localhost:4000/v1/embeddings"
QDRANT_HEALTH_URL="http://localhost:6333/collections"

HEALTH_TIMEOUT=120

# --- Функции ---

# Функция для вывода сообщений
info() {
  echo "--- $1 ---"
}

# Функция для вывода ошибок
error() {
  echo "ERROR: $1" >&2
  exit 1
}

# Функция для проверки состояния сервиса
health_check() {
  local url=$1
  local service_name=$2
  info "Waiting for $service_name to be healthy..."
  local timeout=$HEALTH_TIMEOUT
  until curl -fsS "$url" >/dev/null; do
    ((timeout--))
    if [ $timeout -le 0 ]; then
      error "$service_name health check timed out."
    fi
    sleep 1
  done
  info "$service_name is healthy."
}

# Функции для управления Qdrant
start_qdrant() {
  info "Starting Qdrant"
  docker compose -f "$QDRANT_COMPOSE_FILE" up -d
  health_check "$QDRANT_HEALTH_URL" "Qdrant"
}

stop_qdrant() {
  info "Stopping Qdrant"
  docker compose -f "$QDRANT_COMPOSE_FILE" down
}

# Функции для управления Embeddings (Docker)
start_embeddings() {
  info "Building and starting Embeddings service (Docker)"
  docker compose -f "$EMBEDDINGS_COMPOSE_FILE" up -d --build
  health_check "$EMBEDDINGS_HEALTH_URL" "Embeddings service"
  
  info "Sending warmup request..."
  curl -fsS -X POST "$EMBEDDINGS_WARMUP_URL" \
  -H 'Content-Type: application/json' \
  -d '{"model":"jina-code-v2","input":"warmup"}' >/dev/null || true
  info "Warmup request sent."
}

stop_embeddings() {
  info "Stopping Embeddings service (Docker)"
  docker compose -f "$EMBEDDINGS_COMPOSE_FILE" down --remove-orphans
}

# --- Функции для локального управления (macOS) ---
TMUX_SESSION="mcp-embeddings-local"

setup_local() {
    info "Running local environment setup script..."
    bash "$SCRIPT_DIR/setup_local_env.sh"
}

start_local() {
    if ! command -v tmux &> /dev/null; then
        error "tmux is not installed. Please install it to manage local server sessions (e.g., 'brew install tmux')."
    fi
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        info "Local embeddings service is already running in the background."
        info "To view logs, run: ./scripts/manage.sh local logs"
        return
    fi
    
    info "Starting local embeddings service in the background..."
    tmux new-session -d -s "$TMUX_SESSION" "bash $SCRIPT_DIR/run_local.sh"
    health_check "$EMBEDDINGS_HEALTH_URL" "Local embeddings service"
    info "Service started successfully in the background."
    info "To view live logs, run: ./scripts/manage.sh local logs"
}

stop_local() {
    if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        info "Local embeddings service is not running."
        return
    fi
    info "Stopping local embeddings service (tmux session '$TMUX_SESSION')..."
    tmux kill-session -t "$TMUX_SESSION"
    info "Service stopped."
}

logs_local() {
    local LOG_FILE="$PROJECT_ROOT/logs/embeddings_local.log"
    if [ ! -f "$LOG_FILE" ]; then
        error "Log file not found at '$LOG_FILE'. Start the service at least once to create it."
    fi
    info "Showing live logs from '$LOG_FILE'. Press Ctrl+C to stop."
    # tail -f будет следить за файлом и выводить новые строки
    tail -f "$LOG_FILE"
}


show_status() {
    info "Checking service status..."
    echo

    # Check Qdrant (Docker)
    echo "Docker Services:"
    if docker compose -f "$QDRANT_COMPOSE_FILE" ps --status=running | grep -q "qdrant"; then
        echo "  - Qdrant: Running"
    else
        echo "  - Qdrant: Stopped"
    fi

    # Check Embeddings (Docker)
    if docker compose -f "$EMBEDDINGS_COMPOSE_FILE" ps --status=running | grep -q "embeddings-app"; then
        echo "  - Embeddings (Docker): Running"
    else
        echo "  - Embeddings (Docker): Stopped"
    fi
    echo

    # Check Embeddings (Local)
    echo "Local Services (macOS):"
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        echo "  - Embeddings (Local): Running in tmux session '$TMUX_SESSION'"
    else
        echo "  - Embeddings (Local): Stopped"
    fi
    echo
}


# --- Основная логика ---

CMD=$1
SERVICE=$2

case $CMD in
  start)
    case $SERVICE in
      qdrant) start_qdrant ;;
      jina|embeddings) start_embeddings ;;
      all)
        info "Starting all services..."
        start_qdrant
        start_embeddings
        info "All services started."
        ;;
      *) echo "Usage: $0 start [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  stop)
    case $SERVICE in
      qdrant) stop_qdrant ;;
      jina|embeddings) stop_embeddings ;;
      all)
        info "Stopping all services..."
        stop_embeddings
        stop_qdrant
        info "All services stopped."
        ;;
      *) echo "Usage: $0 stop [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  restart)
    case $SERVICE in
      qdrant) stop_qdrant; start_qdrant ;;
      jina|embeddings) stop_embeddings; start_embeddings ;;
      all)
        info "Restarting all services..."
        stop_embeddings
        stop_qdrant
        start_qdrant
        start_embeddings
        info "All services restarted."
        ;;
      *) echo "Usage: $0 restart [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  local)
    case $SERVICE in
      setup) setup_local ;;
      start) start_local ;;
      stop) stop_local ;;
      restart) stop_local; start_local ;;
      logs) logs_local ;;
      *) echo "Usage: $0 local [setup|start|stop|restart|logs]" >&2; exit 1 ;;
    esac
    ;;
  status)
    show_status
    ;;
  *)
    echo "Usage: $0 [start|stop|restart|status|local] [SERVICE]" >&2
    echo "Docker commands: [start|stop|restart] [qdrant|jina|embeddings|all]" >&2
    echo "Local commands:  local [setup|start|stop|restart|logs]" >&2
    echo "Status command:  status" >&2
    exit 1
    ;;
esac