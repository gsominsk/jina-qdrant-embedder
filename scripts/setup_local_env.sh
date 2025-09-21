#!/bin/bash
set -e

# --- Конфигурация ---
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
PYTHON_VERSION="3.11.9"
VENV_DIR="$PROJECT_ROOT/venv"

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

# --- Основная логика ---

info "Starting local environment setup for macOS..."

# 1. Проверка наличия pyenv
if ! command -v pyenv &>/dev/null; then
  error "pyenv is not installed. Please install it to manage Python versions. See: https://github.com/pyenv/pyenv#installation"
fi

# 2. Установка нужной версии Python
info "Installing Python $PYTHON_VERSION with pyenv (if not already installed)..."
pyenv install -s "$PYTHON_VERSION"

# 3. Создание файла .python-version для автоматической активации
info "Setting project-local Python version to $PYTHON_VERSION..."
(cd "$PROJECT_ROOT" && pyenv local "$PYTHON_VERSION")

# 4. Создание виртуального окружения
if [ -d "$VENV_DIR" ]; then
  info "Virtual environment already exists. Skipping creation."
else
  info "Creating Python virtual environment in $VENV_DIR..."
  info "Creating Python virtual environment using explicit path..."
  # Используем полный путь к python, установленному pyenv, для надежности
  PYENV_PYTHON_PATH="$HOME/.pyenv/versions/$PYTHON_VERSION/bin/python"
  if [ ! -f "$PYENV_PYTHON_PATH" ]; then
    error "Could not find python executable at $PYENV_PYTHON_PATH"
  fi
  (cd "$PROJECT_ROOT" && "$PYENV_PYTHON_PATH" -m venv venv)
fi

# 5. Активация окружения и установка зависимостей
info "Activating virtual environment and installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/embeddings/app/requirements.txt"

info "Local environment setup complete!"
echo "To activate it, run: source $VENV_DIR/bin/activate"