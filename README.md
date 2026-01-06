# Семейный ИИ-планировщик на Agno

ИИ-ассистент для координации семейных дел через Telegram.

## Быстрый старт

### 1. Настройка окружения

```bash
# Скопируй .env.example в .env
cp .env.example .env

# Заполни переменные в .env:
# - SUPABASE_URL и SUPABASE_KEY (из Supabase Dashboard → Settings → API)
# - DEEPSEEK_API_KEY (из DeepSeek)
# - TELEGRAM_BOT_TOKEN (от @BotFather)
```

### 2. Создание схемы БД в Supabase

1. Открой Supabase Dashboard → SQL Editor
2. Выполни SQL из файла `supabase_schema.sql`

### 3. Установка зависимостей

```bash
# Активируй виртуальное окружение (если используешь)
source langflow-env/bin/activate  # или создай новое: python -m venv venv

# Установи зависимости
pip install -r requirements.txt
```

### 4. Запуск бота

```bash
python main.py
```

## Структура проекта

```
family-agent-prototype/
├── core_logic/          # Чистая бизнес-логика (framework-agnostic)
│   ├── schemas.py       # Pydantic модели
│   ├── calendar_tools.py # Функции работы с календарем
│   └── supabase_client.py # Supabase клиент
├── agents_wrappers.py   # Обертки тулов для Agno
├── telegram_bot.py      # Telegram бот
├── scheduler.py         # Утренние дайджесты
└── main.py             # Точка входа
```

## Получение ключей

### Supabase
1. Открой проект в Supabase Dashboard
2. Settings → API
3. Скопируй:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (для админских операций)

### DeepSeek
1. Зарегистрируйся на https://platform.deepseek.com
2. Создай API ключ
3. Скопируй в `DEEPSEEK_API_KEY`

### Telegram Bot
1. Напиши @BotFather в Telegram
2. `/newbot` → следуй инструкциям
3. Скопируй токен в `TELEGRAM_BOT_TOKEN`

