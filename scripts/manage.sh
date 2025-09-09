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

# Функция для проверки состояния сервиса
health_check() {
  local url=$1
  local service_name=$2
  echo "--- Waiting for $service_name to be healthy... ---"
  local timeout=$HEALTH_TIMEOUT
  until curl -fsS "$url" >/dev/null; do
    ((timeout--))
    if [ $timeout -le 0 ]; then
      echo "ERROR: $service_name health check timed out."
      exit 1
    fi
    sleep 1
  done
  echo "--- $service_name is healthy. ---"
}

# Функции для управления Qdrant
start_qdrant() {
  echo "--- Starting Qdrant ---"
  docker compose -f "$QDRANT_COMPOSE_FILE" up -d
  health_check "$QDRANT_HEALTH_URL" "Qdrant"
}

stop_qdrant() {
  echo "--- Stopping Qdrant ---"
  docker compose -f "$QDRANT_COMPOSE_FILE" down
}

# Функции для управления Embeddings
start_embeddings() {
  echo "--- Building and starting Embeddings service ---"
  docker compose -f "$EMBEDDINGS_COMPOSE_FILE" up -d --build
  health_check "$EMBEDDINGS_HEALTH_URL" "Embeddings service"
  
  echo "--- Sending warmup request... ---"
  curl -fsS -X POST "$EMBEDDINGS_WARMUP_URL" \
  -H 'Content-Type: application/json' \
  -d '{"model":"jina-code-v2","input":"warmup"}' >/dev/null || true
  echo "--- Warmup request sent. ---"
}

stop_embeddings() {
  echo "--- Stopping Embeddings service ---"
  docker compose -f "$EMBEDDINGS_COMPOSE_FILE" down --remove-orphans
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
        echo "--- Starting all services... ---"
        start_qdrant
        start_embeddings
        echo "--- All services started. ---"
        ;;
      *) echo "Usage: $0 start [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  stop)
    case $SERVICE in
      qdrant) stop_qdrant ;;
      jina|embeddings) stop_embeddings ;;
      all)
        echo "--- Stopping all services... ---"
        stop_embeddings
        stop_qdrant
        echo "--- All services stopped. ---"
        ;;
      *) echo "Usage: $0 stop [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  restart)
    case $SERVICE in
      qdrant) stop_qdrant; start_qdrant ;;
      jina|embeddings) stop_embeddings; start_embeddings ;;
      all)
        echo "--- Restarting all services... ---"
        stop_embeddings
        stop_qdrant
        start_qdrant
        start_embeddings
        echo "--- All services restarted. ---"
        ;;
      *) echo "Usage: $0 restart [qdrant|jina|embeddings|all]" >&2; exit 1 ;;
    esac
    ;;
  *)
    echo "Usage: $0 [start|stop|restart] [qdrant|jina|embeddings|all]" >&2
    exit 1
    ;;
esac