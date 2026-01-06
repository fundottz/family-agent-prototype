# Настройка окружения

## ✅ Что уже готово

1. **Схема БД создана** через MCP:
   - Таблицы: `users`, `events`, `event_participants`
   - Индексы и триггеры настроены
   - RLS (Row Level Security) включен

2. **Структура проекта** создана:
   - `core_logic/` - бизнес-логика
   - `schemas.py` - Pydantic модели
   - `supabase_client.py` - клиент Supabase

3. **Зависимости** описаны в `requirements.txt`

## 📋 Что нужно сделать

### A) Для работы бота с Supabase

1. **Создать `.env` файл** (скопировать из `.env.example` и заполнить):

```bash
cp .env.example .env
```

2. **Заполнить переменные в `.env`:**

```bash
# Supabase (уже получены через MCP)
SUPABASE_URL=https://fzwbfrdyyfmtargixzqc.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6d2JmcmR5eWZtdGFyZ2l4enFjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc2NzI1MzQsImV4cCI6MjA4MzI0ODUzNH0.lI02sYcvHAIwFdO-iVj1zfYJg2NS4m0wi81HDoLL78Q

# Service Role Key (нужно получить из Supabase Dashboard → Settings → API → service_role)
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# DeepSeek API (получить на https://platform.deepseek.com)
DEEPSEEK_API_KEY=your_deepseek_api_key

# Telegram Bot (получить от @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Timezone
TIMEZONE=Europe/Moscow
```

3. **Установить зависимости:**

```bash
# Активировать виртуальное окружение (если используешь)
source langflow-env/bin/activate

# Или создать новое
python -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### B) Для работы Cursor с проектом

1. **`.cursorrules` файл** - должен быть скачан (проверь наличие)

2. **MCP для Supabase** - уже настроен и работает ✅

3. **Проверить доступность MCP:**
   - MCP сервер Supabase подключен
   - Можно выполнять SQL через `mcp_supabase_execute_sql`
   - Можно применять миграции через `mcp_supabase_apply_migration`

## 🔑 Получение ключей

### Supabase Service Role Key
1. Открой Supabase Dashboard: https://supabase.com/dashboard
2. Выбери проект
3. Settings → API
4. Скопируй `service_role` key (секретный ключ, не публикуй!)

### DeepSeek API Key
1. Зарегистрируйся: https://platform.deepseek.com
2. Создай API ключ в настройках
3. Скопируй в `.env`

### Telegram Bot Token
1. Напиши @BotFather в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям
4. Скопируй токен в `.env`

## ✅ Проверка готовности

После настройки проверь:

```bash
# Проверка Python окружения
python --version  # Должно быть 3.11+

# Проверка установленных пакетов
pip list | grep -E "agno|supabase|telegram"

# Проверка .env (должен существовать)
ls -la .env
```

## 🚀 Следующий шаг

После настройки окружения можно переходить к **Итерации 1**: создание базового Telegram-бота.

