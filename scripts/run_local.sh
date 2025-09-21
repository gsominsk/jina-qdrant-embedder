#!/bin/bash
set -e

# --- Конфигурация ---
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
VENV_DIR="$PROJECT_ROOT/venv"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/embeddings_local.log"
APP_DIR="$PROJECT_ROOT/embeddings/app"

# --- Функции ---
info() {
  echo "--- $1 ---"
}

# --- Основная логика ---

# 1. Проверка venv
if [ ! -f "$VENV_DIR/bin/uvicorn" ]; then
  echo "ERROR: uvicorn not found in virtual environment. Please run 'scripts/setup_local_env.sh' first."
  exit 1
fi

# 2. Создание директории для логов
mkdir -p "$LOG_DIR"

# 3. Запуск uvicorn с дублированием вывода в лог-файл и на экран
info "Starting Embeddings service locally..."
info "Logs will be streamed here and also saved to $LOG_FILE"

# --- Конфигурация производительности ---
# SEMAPHORE_VALUE: Ограничивает количество ОДНОВРЕМЕННО ОБРАБАТЫВАЕМЫХ запросов в приложении.
# Это главный параметр для контроля потребления RAM моделью.
# UVICORN_BACKLOG: Ограничивает количество запросов, которые uvicorn держит в ОЧЕРЕДИ ОЖИДАНИЯ.
# Должно быть немного больше, чем SEMAPHORE_VALUE, чтобы всегда был небольшой запас готовых запросов.
export SEMAPHORE_VALUE=${SEMAPHORE_VALUE:-2}
UVICORN_BACKLOG=${UVICORN_BACKLOG:-8}

info "Performance settings: SEMAPHORE_VALUE=$SEMAPHORE_VALUE, UVICORN_BACKLOG=$UVICORN_BACKLOG"

# Запускаем uvicorn из venv.
# --backlog: ограничивает очередь ожидания TCP-соединений на уровне сервера.
# Перенаправляем stderr в stdout (2>&1), чтобы и ошибки, и обычный вывод попали в pipe.
# pipe (|) передает этот объединенный поток команде tee.
# tee -a "$LOG_FILE" добавляет (-a) вывод в лог-файл и одновременно печатает его на свой stdout (в нашу tmux сессию).
"$VENV_DIR/bin/uvicorn" app:app --host 0.0.0.0 --port 4000 --app-dir "$APP_DIR" --backlog "$UVICORN_BACKLOG" 2>&1 | tee -a "$LOG_FILE"