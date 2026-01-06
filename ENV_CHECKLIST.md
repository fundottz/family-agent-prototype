# Чеклист готовности окружения

## ✅ A) Для работы бота с Supabase

### 1. Переменные окружения в `.env`

Проверь наличие всех переменных:

```bash
# Supabase (обязательно)
SUPABASE_URL=https://fzwbfrdyyfmtargixzqc.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # anon key
SUPABASE_SERVICE_ROLE_KEY=...  # service_role key (секретный!)

# DeepSeek (обязательно)
DEEPSEEK_API_KEY=...

# Telegram (обязательно)
TELEGRAM_BOT_TOKEN=...

# Timezone (опционально, по умолчанию Europe/Moscow)
TIMEZONE=Europe/Moscow
```

**Статус:**
- ✅ SUPABASE_URL - получен через MCP
- ✅ SUPABASE_KEY (anon) - получен через MCP  
- ⚠️ SUPABASE_SERVICE_ROLE_KEY - нужно получить из Dashboard
- ✅ DEEPSEEK_API_KEY - есть в .env
- ✅ TELEGRAM_BOT_TOKEN - есть в .env

### 2. Схема БД в Supabase

**Статус:** ✅ Готово
- Таблицы созданы: `users`, `events`, `event_participants`
- Индексы настроены
- RLS включен
- Триггеры работают

### 3. Установка зависимостей

```bash
# Проверь виртуальное окружение
source langflow-env/bin/activate  # или создай новое

# Установи зависимости
pip install -r requirements.txt
```

**Проверка:**
```bash
pip list | grep -E "agno|supabase|telegram|pydantic"
```

## ✅ B) Для работы Cursor с проектом

### 1. `.cursorrules` файл

**Статус:** ✅ Готово
- Файл скачан и находится в корне проекта
- Содержит правила для работы с Agno

### 2. MCP для Supabase

**Статус:** ✅ Готово и работает
- MCP сервер подключен
- Можно выполнять SQL: `mcp_supabase_execute_sql`
- Можно применять миграции: `mcp_supabase_apply_migration`
- Можно получать ключи: `mcp_supabase_get_publishable_keys`

### 3. Структура проекта

**Статус:** ✅ Готово
```
family-agent-prototype/
├── .cursorrules          ✅
├── .env                  ⚠️ (нужно добавить SUPABASE_SERVICE_ROLE_KEY)
├── .gitignore            ✅
├── requirements.txt      ✅
├── core_logic/           ✅
│   ├── __init__.py
│   ├── schemas.py
│   └── supabase_client.py
└── README.md            ✅
```

## 🔧 Что осталось сделать

### 1. Получить SUPABASE_SERVICE_ROLE_KEY

1. Открой: https://supabase.com/dashboard
2. Выбери проект
3. Settings → API
4. Скопируй `service_role` key (секретный ключ!)
5. Добавь в `.env`:
   ```bash
   SUPABASE_SERVICE_ROLE_KEY=твой_service_role_key
   ```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Проверить подключение к Supabase

Создай тестовый скрипт `test_supabase.py`:

```python
from core_logic.supabase_client import get_supabase_client

try:
    client = get_supabase_client()
    print("✅ Подключение к Supabase успешно!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
```

Запусти:
```bash
python test_supabase.py
```

## ✅ Финальная проверка

После выполнения всех шагов проверь:

```bash
# 1. Проверка переменных окружения
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('SUPABASE_URL:', '✅' if os.getenv('SUPABASE_URL') else '❌'); print('SUPABASE_KEY:', '✅' if os.getenv('SUPABASE_KEY') else '❌'); print('DEEPSEEK_API_KEY:', '✅' if os.getenv('DEEPSEEK_API_KEY') else '❌'); print('TELEGRAM_BOT_TOKEN:', '✅' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌')"

# 2. Проверка установленных пакетов
pip show agno supabase python-telegram-bot pydantic

# 3. Проверка структуры
ls -la core_logic/
```

## 🚀 Готово к запуску!

После выполнения всех шагов можно переходить к **Итерации 1**: создание базового Telegram-бота.

