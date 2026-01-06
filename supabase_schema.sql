-- Схема базы данных для семейного планировщика
-- Выполнить в SQL Editor в Supabase Dashboard

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    partner_telegram_id BIGINT,
    digest_time TEXT DEFAULT '07:00' CHECK (digest_time ~ '^[0-9]{2}:[0-9]{2}$'),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс для быстрого поиска по telegram_id
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- Таблица событий
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    datetime TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    creator_telegram_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'предложено' CHECK (status IN ('предложено', 'подтверждено')),
    category TEXT NOT NULL CHECK (category IN ('дети', 'дом', 'ремонт', 'личное')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    partner_notified BOOLEAN DEFAULT FALSE
);

-- Индексы для быстрого поиска событий
CREATE INDEX IF NOT EXISTS idx_events_datetime ON events(datetime);
CREATE INDEX IF NOT EXISTS idx_events_creator ON events(creator_telegram_id);
CREATE INDEX IF NOT EXISTS idx_events_datetime_creator ON events(datetime, creator_telegram_id);

-- Таблица участников событий (для событий с несколькими участниками)
CREATE TABLE IF NOT EXISTS event_participants (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, user_id)
);

-- Индекс для быстрого поиска участников
CREATE INDEX IF NOT EXISTS idx_event_participants_event ON event_participants(event_id);
CREATE INDEX IF NOT EXISTS idx_event_participants_user ON event_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_event_participants_composite ON event_participants(event_id, user_id);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at в users
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

