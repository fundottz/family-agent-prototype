"""Работа с SQLite базой данных для хранения пользователей и событий."""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional, List
import pytz

from .schemas import User, CalendarEvent, EventStatus, EventCategory

logger = logging.getLogger(__name__)

# Часовой пояс по умолчанию (согласно требованиям)
DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


def get_db_connection(db_file: str) -> sqlite3.Connection:
    """Создает подключение к SQLite базе данных."""
    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Для доступа к полям по имени
    return conn


@contextmanager
def db_connection(db_file: str):
    """
    Context manager для безопасной работы с подключением к БД.
    
    Args:
        db_file: Путь к файлу базы данных
    
    Yields:
        sqlite3.Connection: Подключение к базе данных
    """
    conn = get_db_connection(db_file)
    try:
        yield conn
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def _to_utc_iso(dt: datetime) -> str:
    """
    Конвертирует datetime в UTC ISO строку для хранения в БД.
    
    Args:
        dt: datetime объект (может быть naive или aware)
    
    Returns:
        ISO строка в UTC
    """
    if dt.tzinfo is None:
        # Если naive, считаем что это уже в Europe/Moscow
        dt = DEFAULT_TIMEZONE.localize(dt)
    # Конвертируем в UTC для хранения
    dt_utc = dt.astimezone(pytz.UTC)
    return dt_utc.isoformat()


def _from_utc_iso(iso_str: str) -> datetime:
    """
    Конвертирует UTC ISO строку из БД в datetime в Europe/Moscow.
    
    Args:
        iso_str: ISO строка из БД (в UTC)
    
    Returns:
        datetime объект в Europe/Moscow timezone
    """
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    # Конвертируем в Europe/Moscow
    return dt.astimezone(DEFAULT_TIMEZONE)


def init_database(db_file: str) -> None:
    """
    Инициализирует базу данных: создает таблицы, если их нет.
    
    Args:
        db_file: Путь к файлу базы данных
    """
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        
        try:
            # Таблица users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    partner_telegram_id INTEGER,
                    digest_time TEXT NOT NULL DEFAULT '07:00',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    datetime DATETIME NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    creator_telegram_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'предложено',
                    category TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    partner_notified BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (creator_telegram_id) REFERENCES users(telegram_id)
                )
            """)
            
            # Таблица event_participants
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(event_id, user_id)
                )
            """)
            
            # Индексы для быстрого поиска
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_datetime_creator 
                ON events(datetime, creator_telegram_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id 
                ON users(telegram_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_participants_event_user 
                ON event_participants(event_id, user_id)
            """)
            
            conn.commit()
            logger.info(f"База данных инициализирована: {db_file}")
        except sqlite3.Error as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            conn.rollback()
            raise


# ==================== Работа с пользователями ====================

def create_user(db_file: str, user: User) -> int:
    """
    Создает нового пользователя в базе данных.
    
    Args:
        db_file: Путь к файлу базы данных
        user: Объект User
    
    Returns:
        ID созданного пользователя
    
    Raises:
        ValueError: Если данные пользователя невалидны
        sqlite3.IntegrityError: Если пользователь с таким telegram_id уже существует
    """
    # Валидация входных данных
    if not user.telegram_id or user.telegram_id <= 0:
        raise ValueError("telegram_id должен быть положительным числом")
    if not user.name or not user.name.strip():
        raise ValueError("name не может быть пустым")
    if user.digest_time:
        # Проверка формата времени HH:MM
        try:
            parts = user.digest_time.split(':')
            if len(parts) != 2:
                raise ValueError
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError("digest_time должен быть в формате HH:MM")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (telegram_id, name, partner_telegram_id, digest_time)
                VALUES (?, ?, ?, ?)
            """, (
                user.telegram_id,
                user.name.strip(),
                user.partner_telegram_id,
                user.digest_time
            ))
            user_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Создан пользователь: {user.name} (telegram_id: {user.telegram_id})")
            return user_id
        except sqlite3.IntegrityError as e:
            logger.error(f"Ошибка при создании пользователя: {e}")
            raise


def get_user_by_telegram_id(db_file: str, telegram_id: int) -> Optional[User]:
    """
    Получает пользователя по Telegram ID.
    
    Args:
        db_file: Путь к файлу базы данных
        telegram_id: Telegram ID пользователя
    
    Returns:
        User или None, если пользователь не найден
    
    Raises:
        ValueError: Если telegram_id невалиден
    """
    if not telegram_id or telegram_id <= 0:
        raise ValueError("telegram_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, telegram_id, name, partner_telegram_id, digest_time
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,))
        
        row = cursor.fetchone()
        if row:
            return User(
                id=row['id'],
                telegram_id=row['telegram_id'],
                name=row['name'],
                partner_telegram_id=row['partner_telegram_id'],
                digest_time=row['digest_time']
            )
        return None


def update_user(db_file: str, user: User) -> bool:
    """
    Обновляет данные пользователя.
    
    Args:
        db_file: Путь к файлу базы данных
        user: Объект User с заполненным id
    
    Returns:
        True если обновление успешно
    
    Raises:
        ValueError: Если данные невалидны
    """
    if not user.id:
        raise ValueError("User.id должен быть заполнен для обновления")
    if not user.name or not user.name.strip():
        raise ValueError("name не может быть пустым")
    if user.digest_time:
        # Проверка формата времени HH:MM
        try:
            parts = user.digest_time.split(':')
            if len(parts) != 2:
                raise ValueError
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError("digest_time должен быть в формате HH:MM")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users
                SET name = ?, partner_telegram_id = ?, digest_time = ?
                WHERE id = ?
            """, (
                user.name.strip(),
                user.partner_telegram_id,
                user.digest_time,
                user.id
            ))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Обновлен пользователь: {user.name} (id: {user.id})")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            raise


# ==================== Работа с событиями ====================

def count_users(db_file: str) -> int:
    """
    Подсчитывает количество пользователей в базе данных.
    
    Args:
        db_file: Путь к файлу базы данных
    
    Returns:
        Количество пользователей
    """
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        return count


def load_default_users(db_file: str, config_path: str = "config/users.json") -> None:
    """
    Загружает дефолтных пользователей из конфиг-файла, если таблица users пуста.
    
    Args:
        db_file: Путь к файлу базы данных
        config_path: Путь к конфиг-файлу с дефолтными пользователями
    """
    import json
    import os
    
    # Проверяем количество пользователей
    user_count = count_users(db_file)
    if user_count > 0:
        logger.info(f"В базе данных уже есть {user_count} пользователь(ей), пропускаем загрузку дефолтных")
        return
    
    # Проверяем существование конфиг-файла
    if not os.path.exists(config_path):
        logger.warning(f"Конфиг-файл {config_path} не найден, пропускаем загрузку дефолтных пользователей")
        return
    
    try:
        # Загружаем конфиг
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Извлекаем массив пользователей
        users_data = config.get('users', [])
        if not users_data:
            logger.warning(f"Конфиг-файл {config_path} не содержит пользователей")
            return
        
        logger.info(f"Загружаем {len(users_data)} дефолтных пользователей из {config_path}")
        
        # Создаем пользователей
        created_count = 0
        for user_data in users_data:
            try:
                # Используем дефолтное значение digest_time, если не указано
                digest_time = user_data.get('digest_time', '07:00')
                
                user = User(
                    telegram_id=user_data['telegram_id'],
                    name=user_data['name'],
                    partner_telegram_id=user_data.get('partner_telegram_id'),
                    digest_time=digest_time
                )
                
                create_user(db_file, user)
                created_count += 1
                logger.info(f"Создан дефолтный пользователь: {user.name} (telegram_id: {user.telegram_id})")
            except Exception as e:
                logger.error(f"Ошибка при создании пользователя {user_data.get('name', 'unknown')}: {e}")
        
        logger.info(f"Успешно загружено {created_count} дефолтных пользователей")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON файла {config_path}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке дефолтных пользователей: {e}", exc_info=True)




def create_event(db_file: str, event: CalendarEvent) -> int:
    """
    Создает новое событие в базе данных.
    
    Args:
        db_file: Путь к файлу базы данных
        event: Объект CalendarEvent
    
    Returns:
        ID созданного события
    
    Raises:
        ValueError: Если данные события невалидны
    """
    # Валидация входных данных
    if not event.title or not event.title.strip():
        raise ValueError("title не может быть пустым")
    if not event.datetime:
        raise ValueError("datetime обязателен")
    if event.duration_minutes <= 0:
        raise ValueError("duration_minutes должен быть положительным числом")
    if not event.creator_telegram_id or event.creator_telegram_id <= 0:
        raise ValueError("creator_telegram_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO events (
                    title, datetime, duration_minutes, creator_telegram_id,
                    status, category, partner_notified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.title.strip(),
                _to_utc_iso(event.datetime),
                event.duration_minutes,
                event.creator_telegram_id,
                event.status.value,
                event.category.value,
                1 if event.partner_notified else 0
            ))
            event_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Создано событие: {event.title} (id: {event_id})")
            return event_id
        except sqlite3.Error as e:
            logger.error(f"Ошибка при создании события: {e}")
            raise


def get_event_by_id(db_file: str, event_id: int) -> Optional[CalendarEvent]:
    """
    Получает событие по ID.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
    
    Returns:
        CalendarEvent или None, если событие не найдено
    
    Raises:
        ValueError: Если event_id невалиден
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE id = ?
        """, (event_id,))
        
        row = cursor.fetchone()
        if row:
            return CalendarEvent(
                id=row['id'],
                title=row['title'],
                datetime=_from_utc_iso(row['datetime']),
                duration_minutes=row['duration_minutes'],
                creator_telegram_id=row['creator_telegram_id'],
                status=EventStatus(row['status']),
                category=EventCategory(row['category']),
                created_at=_from_utc_iso(row['created_at']) if row['created_at'] else None,
                partner_notified=bool(row['partner_notified'])
            )
        return None


def get_events_by_user(
    db_file: str,
    telegram_id: int,
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None
) -> List[CalendarEvent]:
    """
    Получает события пользователя за указанный период.
    
    Args:
        db_file: Путь к файлу базы данных
        telegram_id: Telegram ID пользователя
        start_datetime: Начало периода (опционально)
        end_datetime: Конец периода (опционально)
    
    Returns:
        Список событий
    
    Raises:
        ValueError: Если telegram_id невалиден
    """
    if not telegram_id or telegram_id <= 0:
        raise ValueError("telegram_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE creator_telegram_id = ?
        """
        params = [telegram_id]
        
        if start_datetime:
            query += " AND datetime >= ?"
            params.append(_to_utc_iso(start_datetime))
        
        if end_datetime:
            query += " AND datetime <= ?"
            params.append(_to_utc_iso(end_datetime))
        
        query += " ORDER BY datetime ASC"
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            events.append(CalendarEvent(
                id=row['id'],
                title=row['title'],
                datetime=_from_utc_iso(row['datetime']),
                duration_minutes=row['duration_minutes'],
                creator_telegram_id=row['creator_telegram_id'],
                status=EventStatus(row['status']),
                category=EventCategory(row['category']),
                created_at=_from_utc_iso(row['created_at']) if row['created_at'] else None,
                partner_notified=bool(row['partner_notified'])
            ))
        
        return events


def get_conflicting_events(
    db_file: str,
    event_datetime: datetime,
    duration_minutes: int,
    telegram_id: int
) -> List[CalendarEvent]:
    """
    Находит события, которые конфликтуют по времени с указанным событием.
    
    Args:
        db_file: Путь к файлу базы данных
        event_datetime: Дата и время события
        duration_minutes: Продолжительность события в минутах
        telegram_id: Telegram ID пользователя
    
    Returns:
        Список конфликтующих событий
    
    Raises:
        ValueError: Если параметры невалидны
    """
    from datetime import timedelta
    
    if not event_datetime:
        raise ValueError("event_datetime обязателен")
    if duration_minutes <= 0:
        raise ValueError("duration_minutes должен быть положительным числом")
    if not telegram_id or telegram_id <= 0:
        raise ValueError("telegram_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        event_end = event_datetime + timedelta(minutes=duration_minutes)
        
        # Получаем все события пользователя в широком диапазоне
        # (за день до и после, чтобы не пропустить конфликты)
        search_start = event_datetime - timedelta(days=1)
        search_end = event_end + timedelta(days=1)
        
        cursor.execute("""
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE creator_telegram_id = ?
            AND datetime >= ? AND datetime <= ?
        """, (
            telegram_id,
            _to_utc_iso(search_start),
            _to_utc_iso(search_end)
        ))
        
        # Фильтруем события на конфликты в Python
        conflicting_events = []
        for row in cursor.fetchall():
            existing_event_start = _from_utc_iso(row['datetime'])
            existing_event_end = existing_event_start + timedelta(minutes=row['duration_minutes'])
            
            # Проверяем пересечение интервалов
            if not (event_end <= existing_event_start or event_datetime >= existing_event_end):
                conflicting_events.append(CalendarEvent(
                    id=row['id'],
                    title=row['title'],
                    datetime=existing_event_start,
                    duration_minutes=row['duration_minutes'],
                    creator_telegram_id=row['creator_telegram_id'],
                    status=EventStatus(row['status']),
                    category=EventCategory(row['category']),
                    created_at=_from_utc_iso(row['created_at']) if row['created_at'] else None,
                    partner_notified=bool(row['partner_notified'])
                ))
        
        return conflicting_events


def get_events_in_range(
    db_file: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> List[CalendarEvent]:
    """
    Получает ВСЕ события в указанном диапазоне дат (общий календарь).
    """
    if not start_datetime or not end_datetime:
        raise ValueError("start_datetime и end_datetime обязательны")

    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE datetime >= ? AND datetime <= ?
            ORDER BY datetime ASC
            """,
            (_to_utc_iso(start_datetime), _to_utc_iso(end_datetime)),
        )

        events: List[CalendarEvent] = []
        for row in cursor.fetchall():
            events.append(
                CalendarEvent(
                    id=row["id"],
                    title=row["title"],
                    datetime=_from_utc_iso(row["datetime"]),
                    duration_minutes=row["duration_minutes"],
                    creator_telegram_id=row["creator_telegram_id"],
                    status=EventStatus(row["status"]),
                    category=EventCategory(row["category"]),
                    created_at=_from_utc_iso(row["created_at"]) if row["created_at"] else None,
                    partner_notified=bool(row["partner_notified"]),
                )
            )
        return events


def get_conflicting_events_global(
    db_file: str,
    event_datetime: datetime,
    duration_minutes: int,
) -> List[CalendarEvent]:
    """
    Находит события общего календаря, которые конфликтуют по времени с указанным интервалом.
    """
    from datetime import timedelta

    if not event_datetime:
        raise ValueError("event_datetime обязателен")
    if duration_minutes <= 0:
        raise ValueError("duration_minutes должен быть положительным числом")

    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        event_end = event_datetime + timedelta(minutes=duration_minutes)

        # Берем широкий диапазон, затем фильтруем пересечения в Python
        search_start = event_datetime - timedelta(days=1)
        search_end = event_end + timedelta(days=1)

        cursor.execute(
            """
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE datetime >= ? AND datetime <= ?
            """,
            (_to_utc_iso(search_start), _to_utc_iso(search_end)),
        )

        conflicting_events: List[CalendarEvent] = []
        for row in cursor.fetchall():
            existing_event_start = _from_utc_iso(row["datetime"])
            existing_event_end = existing_event_start + timedelta(minutes=row["duration_minutes"])

            if not (event_end <= existing_event_start or event_datetime >= existing_event_end):
                conflicting_events.append(
                    CalendarEvent(
                        id=row["id"],
                        title=row["title"],
                        datetime=existing_event_start,
                        duration_minutes=row["duration_minutes"],
                        creator_telegram_id=row["creator_telegram_id"],
                        status=EventStatus(row["status"]),
                        category=EventCategory(row["category"]),
                        created_at=_from_utc_iso(row["created_at"]) if row["created_at"] else None,
                        partner_notified=bool(row["partner_notified"]),
                    )
                )

        return conflicting_events


def update_event_status(db_file: str, event_id: int, status: EventStatus) -> bool:
    """
    Обновляет статус события.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
        status: Новый статус
    
    Returns:
        True если обновление успешно
    
    Raises:
        ValueError: Если event_id невалиден
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE events
                SET status = ?
                WHERE id = ?
            """, (status.value, event_id))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Обновлен статус события {event_id}: {status.value}")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении статуса события: {e}")
            raise


def update_event(db_file: str, event_id: int, updates: dict) -> bool:
    """
    Обновляет поля события.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
        updates: Словарь с полями для обновления. Поддерживаемые ключи:
                 - title: str
                 - datetime: datetime
                 - duration_minutes: int
                 - category: EventCategory или str
                 - status: EventStatus или str
                 - partner_notified: bool
    
    Returns:
        True если обновление успешно
    
    Raises:
        ValueError: Если event_id невалиден или updates пуст
        sqlite3.Error: При ошибке БД
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    if not updates:
        raise ValueError("updates не может быть пустым")
    
    # Разрешенные поля для обновления
    allowed_fields = {'title', 'datetime', 'duration_minutes', 'category', 'status', 'partner_notified'}
    
    # Формируем SET часть запроса
    set_parts = []
    params = []
    
    for key, value in updates.items():
        if key not in allowed_fields:
            raise ValueError(f"Поле '{key}' не может быть обновлено")
        
        if key == 'title':
            if not value or not str(value).strip():
                raise ValueError("title не может быть пустым")
            set_parts.append("title = ?")
            params.append(str(value).strip())
        
        elif key == 'datetime':
            if not isinstance(value, datetime):
                raise ValueError("datetime должен быть объектом datetime")
            set_parts.append("datetime = ?")
            params.append(_to_utc_iso(value))
        
        elif key == 'duration_minutes':
            if not isinstance(value, int) or value <= 0:
                raise ValueError("duration_minutes должен быть положительным числом")
            set_parts.append("duration_minutes = ?")
            params.append(value)
        
        elif key == 'category':
            if isinstance(value, EventCategory):
                category_value = value.value
            elif isinstance(value, str):
                category_value = value
            else:
                raise ValueError("category должен быть EventCategory или str")
            set_parts.append("category = ?")
            params.append(category_value)
        
        elif key == 'status':
            if isinstance(value, EventStatus):
                status_value = value.value
            elif isinstance(value, str):
                status_value = value
            else:
                raise ValueError("status должен быть EventStatus или str")
            set_parts.append("status = ?")
            params.append(status_value)
        
        elif key == 'partner_notified':
            set_parts.append("partner_notified = ?")
            params.append(1 if value else 0)
    
    if not set_parts:
        raise ValueError("Нет полей для обновления")
    
    # Добавляем event_id в конец параметров
    params.append(event_id)
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            query = f"""
                UPDATE events
                SET {', '.join(set_parts)}
                WHERE id = ?
            """
            cursor.execute(query, params)
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Обновлено событие {event_id}: {', '.join(updates.keys())}")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении события: {e}")
            raise


def delete_event(db_file: str, event_id: int) -> bool:
    """
    Удаляет событие из базы данных.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
    
    Returns:
        True если удаление успешно
    
    Raises:
        ValueError: Если event_id невалиден
        sqlite3.Error: При ошибке БД
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            # Удаляем участников события (CASCADE должен сработать, но делаем явно)
            cursor.execute("DELETE FROM event_participants WHERE event_id = ?", (event_id,))
            
            # Удаляем само событие
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Удалено событие {event_id}")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении события: {e}")
            raise


def get_events_by_creator_in_range(
    db_file: str,
    creator_telegram_id: int,
    start_date: date,
    end_date: date
) -> List[CalendarEvent]:
    """
    Получает события создателя за указанный период (по датам).
    
    Args:
        db_file: Путь к файлу базы данных
        creator_telegram_id: Telegram ID создателя события
        start_date: Начальная дата (включительно)
        end_date: Конечная дата (включительно)
    
    Returns:
        Список событий создателя за период
    
    Raises:
        ValueError: Если параметры невалидны
    """
    if not creator_telegram_id or creator_telegram_id <= 0:
        raise ValueError("creator_telegram_id должен быть положительным числом")
    if not start_date or not end_date:
        raise ValueError("start_date и end_date обязательны")
    if start_date > end_date:
        raise ValueError("start_date не может быть позже end_date")
    
    # Преобразуем date в datetime для начала и конца дня
    start_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(start_date, datetime.min.time())
    )
    end_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(end_date, datetime.max.time())
    )
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, datetime, duration_minutes, creator_telegram_id,
                   status, category, created_at, partner_notified
            FROM events
            WHERE creator_telegram_id = ?
            AND datetime >= ? AND datetime <= ?
            ORDER BY datetime ASC
        """, (
            creator_telegram_id,
            _to_utc_iso(start_datetime),
            _to_utc_iso(end_datetime)
        ))
        
        events = []
        for row in cursor.fetchall():
            events.append(CalendarEvent(
                id=row['id'],
                title=row['title'],
                datetime=_from_utc_iso(row['datetime']),
                duration_minutes=row['duration_minutes'],
                creator_telegram_id=row['creator_telegram_id'],
                status=EventStatus(row['status']),
                category=EventCategory(row['category']),
                created_at=_from_utc_iso(row['created_at']) if row['created_at'] else None,
                partner_notified=bool(row['partner_notified'])
            ))
        
        return events


def mark_partner_notified(db_file: str, event_id: int) -> bool:
    """
    Отмечает, что партнер был уведомлен о событии.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
    
    Returns:
        True если обновление успешно
    
    Raises:
        ValueError: Если event_id невалиден
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE events
                SET partner_notified = 1
                WHERE id = ?
            """, (event_id,))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Отмечено уведомление партнера для события {event_id}")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении флага уведомления: {e}")
            raise


# ==================== Работа с участниками событий ====================

def add_event_participant(db_file: str, event_id: int, user_id: int) -> bool:
    """
    Добавляет участника к событию.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
        user_id: ID пользователя
    
    Returns:
        True если добавление успешно
    
    Raises:
        ValueError: Если параметры невалидны
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    if not user_id or user_id <= 0:
        raise ValueError("user_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO event_participants (event_id, user_id)
                VALUES (?, ?)
            """, (event_id, user_id))
            conn.commit()
            added = cursor.rowcount > 0
            if added:
                logger.info(f"Добавлен участник {user_id} к событию {event_id}")
            return added
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении участника: {e}")
            raise


def get_event_participants(db_file: str, event_id: int) -> List[int]:
    """
    Получает список ID участников события.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
    
    Returns:
        Список ID пользователей
    
    Raises:
        ValueError: Если event_id невалиден
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id
            FROM event_participants
            WHERE event_id = ?
        """, (event_id,))
        
        return [row['user_id'] for row in cursor.fetchall()]


def get_events_by_participant_telegram_id(
    db_file: str,
    telegram_id: int,
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None
) -> List[CalendarEvent]:
    """
    Получает события, где пользователь является участником (через event_participants).
    
    Args:
        db_file: Путь к файлу базы данных
        telegram_id: Telegram ID пользователя
        start_datetime: Начало периода (опционально)
        end_datetime: Конец периода (опционально)
    
    Returns:
        Список событий, где пользователь является участником
    
    Raises:
        ValueError: Если telegram_id невалиден
    """
    if not telegram_id or telegram_id <= 0:
        raise ValueError("telegram_id должен быть положительным числом")
    
    # Сначала получаем user_id по telegram_id
    user = get_user_by_telegram_id(db_file, telegram_id)
    if not user or not user.id:
               return []
    
    with db_connection(db_file) as conn:
        cursor = conn.cursor()
        query = """
            SELECT e.id, e.title, e.datetime, e.duration_minutes, e.creator_telegram_id,
                   e.status, e.category, e.created_at, e.partner_notified
            FROM events e
            INNER JOIN event_participants ep ON e.id = ep.event_id
            WHERE ep.user_id = ?
        """
        params = [user.id]
        
        if start_datetime:
            query += " AND e.datetime >= ?"
            params.append(_to_utc_iso(start_datetime))
        
        if end_datetime:
            query += " AND e.datetime <= ?"
            params.append(_to_utc_iso(end_datetime))
        
        query += " ORDER BY e.datetime ASC"
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            events.append(CalendarEvent(
                id=row['id'],
                title=row['title'],
                datetime=_from_utc_iso(row['datetime']),
                duration_minutes=row['duration_minutes'],
                creator_telegram_id=row['creator_telegram_id'],
                status=EventStatus(row['status']),
                category=EventCategory(row['category']),
                created_at=_from_utc_iso(row['created_at']) if row['created_at'] else None,
                partner_notified=bool(row['partner_notified'])
            ))
        
        return events

