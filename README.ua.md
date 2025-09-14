# Індексація кодової бази за допомогою користувацьких ембедингів

Цей проєкт налаштовує локальне оточення для індексації коду з використанням користувацького сервісу ембедингів та векторної бази даних Qdrant.

## Огляд системи

Система складається з двох основних сервісів, керованих за допомогою Docker Compose:

1.  **Qdrant:** Векторна база даних, що використовується для зберігання та пошуку ембедингів коду. Вона працює у власному контейнері та надає свій API на порту `6333`.
2.  **Сервіс ембедингів:** Користувацький, легковий FastAPI-додаток, що обслуговує модель `jina-code-v2`. Він використовує бібліотеку `transformers` для генерації ембедингів та надає OpenAI-сумісний API на порту `4000`.

## Як це працює

1.  **Конфігурація Roo Code:**
    *   Вказує `embeddingProvider` на `baseUrl` користувацького сервісу: `http://localhost:4000/v1`.
    *   Вказує `vectorStore` як `qdrant` та надає його URL: `http://localhost:6333`.

    Нижче наведено приклад повного, валідного конфігураційного файлу:

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

2.  **Генерація ембедингів:** Коли Roo Code необхідно згенерувати ембединг для фрагмента коду, він надсилає запит на `http://localhost:4000/v1/embeddings`.

3.  **Користувацький сервіс (`embeddings/jina-server`):** Додаток FastAPI отримує запит, використовує модель `jinaai/jina-embeddings-v2-base-code` для генерації векторного ембединга та повертає його у форматі, що імітує API OpenAI.

4.  **Зберігання векторів:** Потім Roo Code бере цей ембединг і зберігає його в локально запущеній базі даних Qdrant.

## Як запустити

Сервіси керуються двома окремими файлами `docker-compose.yml`. Для повної працездатності системи необхідно запустити обидва.

1.  **Запуск бази даних Qdrant:**
    Відкрийте термінал і виконайте таку команду з кореневого каталогу проєкту:
    ```bash
    docker-compose -f qdrant/docker-compose.yml up -d
    ```
    Це запустить контейнер Qdrant і відкриє доступ до його сервісу на порту `6333`.

2.  **Запуск сервісу ембедингів:**
    В іншому терміналі виконайте таку команду з кореневого каталогу проєкту:
    ```bash
    docker-compose -f embeddings/docker-compose.yml up -d
    ```
    Це збере та запустить користувацький додаток FastAPI. Сервіс буде доступний на порту `4000`.

Після запуску обох сервісів система готова до використання Roo Code.

## Глибоке налагодження та оптимізація продуктивності

Під час інтенсивного використання сервісу було виявлено критичну проблему нестабільності: під навантаженням контейнер `jina-openai` аварійно завершував роботу через брак оперативної пам'яті (OOM Kill), що призводило до таймаутів та відмов в обслуговуванні.

Детальне розслідування виявило **дві незалежні витоки пам'яті**. Нижче описано покроковий процес їх виявлення та усунення.

### Етап 1: Інструментарій та діагностика

Для точного аналізу в код програми (`embeddings/app/app.py`) були тимчасово додані інструменти профілювання:
1.  **Моніторинг пам'яті з `psutil`:** Для логування споживання фізичної пам'яті (RSS) в реальному часі.
2.  **Профілювання з `tracemalloc`:** Для відстеження об'єктів Python, які виділяють пам'ять і не звільняються.

Первинний навантажувальний тест підтвердив наявність швидкого витоку, після чого значення семафора (`SEMAPHORE_VALUE`) було тимчасово знижено з `8` до `2` для ізоляції проблеми.

### Етап 2: Усунення критичного витоку (PyTorch Tensors)

Аналіз логів `tracemalloc` показав, що пам'ять стрімко витікала через тензори PyTorch, які не звільнялися після обробки кожного батча. Збирач сміття Python не міг автоматично очистити пам'ять, зайняту на GPU.

**Рішення:**
У код обробки було додано явне очищення ресурсів після їх використання.

```python
# embeddings/app/app.py
# ... всередині функції кодування ...
del batch_embeddings
del tokens
torch.cuda.empty_cache()
```
Цей крок повністю усунув швидкий витік, але залишився другий, повільніший.

### Етап 3: Усунення повільного витоку (FastAPI/Starlette)

Після усунення основної проблеми `tracemalloc` вказав на нову причину: об'єкти, пов'язані з життєвим циклом запиту-відповіді у фреймворках FastAPI та Starlette. Ці об'єкти не завжди коректно прибиралися збирачем сміття в асинхронному середовищі.

**Рішення:**
Було впроваджено глобальний `middleware`, який примусово запускає збирач сміття (`gc.collect()`) після завершення кожного HTTP-запиту.

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
Це рішення повністю усунуло другий витік.

### Етап 4: Фінальне налаштування продуктивності

Після повного усунення обох витоків останнім кроком було відновлення початкової продуктивності.

**Рішення:**
Значення семафора було повернуто до оптимального значення `8`, розрахованого виходячи з доступної RAM.

```python
# embeddings/app/app.py
SEMAPHORE_VALUE = 8
```

### Підсумковий результат

В результаті виконаної роботи сервіс був повністю стабілізований.
-   **Витоки пам'яті усунені:** Споживання RAM знаходиться під контролем.
-   **Продуктивність оптимальна:** Система ефективно використовує ресурси CPU.
-   **Стабільність:** Сервіс успішно справляється з високим навантаженням без збоїв.

Фінальне тестування показало, що при значенні семафора `8` споживання пам'яті коливається в безпечному діапазоні 3-5 ГБ.

## Інтеграція з Visual Studio Code

Для максимальної зручності проєкт налаштований для керування прямо з VS Code за допомогою гарячих клавіш. Для цього необхідно налаштувати два файли в конфігурації VS Code.

### 1. Налаштування завдань (`tasks.json`)

Створіть або оновіть файл `tasks.json` у вашій користувацькій директорії налаштувань VS Code.

*   **Шлях на macOS:** `~/Library/Application Support/Code/User/tasks.json`
*   **Шлях на Windows:** `%APPDATA%\Code\User\tasks.json`
*   **Шлях на Linux:** `~/.config/Code/User/tasks.json`

Вставте в нього наступний вміст, **обов'язково замінивши** `$HOME/sandbox/mcp` на актуальний шлях до вашого проєкту:

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
        "\\033[1mJina/Qdrant — гарячі клавіші\\033[0m\\n\\n  ⌘⇧9   startall + warmup      — Запустити Qdrant, Jina та прогріти ембединги\\n  ⌘⇧=   restartall            — Перезапустити всі сервіси\\n  ⌘⇧0   help: embeddings shortcuts  — Показати цей екран\\n  ⌘⇧-   stopall               — Зупинити Jina та Qdrant\\n  ⌘⇧8   qdrant restart        — Перезапустити Qdrant\\n  ⌘⇧7   jina start + warmup   — Запустити Jina та прогріти\\n  ⌘⇧6   jina stop             — Зупинити Jina\\n\\nПідказка: команди налаштовуються в User Tasks та Keyboard Shortcuts (JSON)."
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

### 2. Налаштування гарячих клавіш (`keybindings.json`)

Аналогічно, створіть або оновіть файл `keybindings.json`.

*   **Шлях на macOS:** `~/Library/Application Support/Code/User/keybindings.json`
*   **Шлях на Windows:** `%APPDATA%\Code\User\keybindings.json`
*   **Шлях на Linux:** `~/.config/Code/User/keybindings.json`

Вставте в нього наступний вміст:

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

### Доступні команди (гарячі клавіші)

Після налаштування ви зможете керувати сервісами за допомогою наступних сполучень клавіш (для macOS, замініть `cmd` на `ctrl` для Windows/Linux):

| Гаряча клавіша | Команда                  | Опис                                           |
| --------------- | ------------------------ | -------------------------------------------------- |
| `⌘ + ⇧ + 9`     | `startall + warmup`      | Запустити Qdrant, Jina та прогріти ембединги        |
| `⌘ + ⇧ + =`     | `restartall`             | Перезапустити всі сервіси                          |
| `⌘ + ⇧ + -`     | `stopall`                | Зупинити Jina та Qdrant                           |
| `⌘ + ⇧ + 8`     | `qdrant restart`         | Перезапустити тільки Qdrant                        |
| `⌘ + ⇧ + 7`     | `jina start + warmup`    | Запустити тільки Jina та прогріти                    |
| `⌘ + ⇧ + 6`     | `jina stop`              | Зупинити тільки Jina                             |
| `⌘ + ⇧ + 0`     | `help: embeddings shortcuts` | Показати цю довідку в терміналі VS Code           |

## Діаграма архітектури

Проста ASCII-діаграма, що ілюструє потік даних:

```
+--------------------------+
|      Клієнт Roo Code     |
| (у вашому IDE, налаштований|
| через roo-code-config.json)|
+--------------------------+
           |
           | 1. POST-запит коду для ембединга
           v
+--------------------------+
|  Користувацький сервіс   |
|       FastAPI            |
|  (Docker, Порт 4000)     |
|--------------------------|
|   |                      |
|   | 2. Обробка з ...     |
|   v                      |
| +--------------------+   |
| |   Модель jina-code-v2  |   |
| +--------------------+   |
|   ^                      |
|   | 3. Повернення вектора|
|   |                      |
+--------------------------+
           |
           | 4. Повернення OpenAI-сумісного ембединга
           v
+--------------------------+
|      Клієнт Roo Code     |
| (отримує ембединг)       |
+--------------------------+
           |
           | 5. Збереження ембединга в...
           v
+--------------------------+
|    Векторна БД Qdrant    |
|    (Docker, Порт 6333)   |
+--------------------------+
```

### Пояснення потоку даних:

1.  **Roo Code -> FastAPI:** Ваше IDE, використовуючи налаштування з `roo-code-config.json`, надсилає фрагмент коду в користувацький сервіс FastAPI на порт `4000`.
2.  **FastAPI -> Модель:** Сервіс FastAPI (прошарок) приймає код і передає його моделі `jina-code-v2`, яка працює в тому ж контейнері.
3.  **Модель -> FastAPI:** Модель перетворює код на числовий вектор (ембединг) і надсилає його назад у сервіс.
4.  **FastAPI -> Roo Code:** Сервіс обгортає цей вектор у стандартний JSON-формат і надсилає його назад у ваше IDE.
5.  **Roo Code -> Qdrant:** Ваше IDE отримує ембединг і надсилає його в базу даних Qdrant на порт `6333`, де він зберігається та індексується для майбутніх пошуків.