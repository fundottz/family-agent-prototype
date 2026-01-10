"""Работа с SQLite базой данных для хранения пользователей и событий.

Этот модуль предоставляет функции для работы с БД с обратной совместимостью.
Внутренняя реализация использует SQLAlchemy ORM и репозиторный паттерн.
"""

import logging
from datetime import datetime, date
from typing import Optional, List
import pytz
from sqlalchemy.exc import IntegrityError

from .schemas import User, CalendarEvent, EventStatus, EventCategory
from db.session import get_db_session
from db.repositories import UserRepository, EventRepository, EventParticipantRepository
from db.converters import (
    pydantic_user_to_sqlalchemy,
    pydantic_event_to_sqlalchemy,
    _to_utc_iso
)

logger = logging.getLogger(__name__)

# Часовой пояс по умолчанию (согласно требованиям)
DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


def init_database(db_file: str) -> None:
    """
    Инициализирует базу данных: создает таблицы, если их нет.
    
    Args:
        db_file: Путь к файлу базы данных
    """
    from db.config import create_engine_instance
    from db.models import Base
    
    try:
        engine = create_engine_instance(db_file)
        # Создаем все таблицы и индексы через SQLAlchemy
        Base.metadata.create_all(engine)
        logger.info(f"База данных инициализирована: {db_file}")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


# ==================== Работа с пользователями ====================

def create_user(db_file: str, user: User) -> int:
    """
    Создает нового пользователя в базе данных.
    
    Args:
        db_file: Путь к файлу базы данных
        user: Объект User (валидация выполняется Pydantic)
    
    Returns:
        ID созданного пользователя
    
    Raises:
        IntegrityError: Если пользователь с таким telegram_id уже существует
    """
    with get_db_session(db_file) as session:
        try:
            user_repo = UserRepository(session)
            sql_user = pydantic_user_to_sqlalchemy(user)
            created_user = user_repo.create(sql_user)
            logger.info(f"Создан пользователь: {user.name} (telegram_id: {user.telegram_id})")
            return created_user.id
        except IntegrityError as e:
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
    """
    with get_db_session(db_file) as session:
        user_repo = UserRepository(session)
        return user_repo.get_by_telegram_id_pydantic(telegram_id)


def update_user(db_file: str, user: User) -> bool:
    """
    Обновляет данные пользователя.
    
    Args:
        db_file: Путь к файлу базы данных
        user: Объект User с заполненным id (валидация выполняется Pydantic)
    
    Returns:
        True если обновление успешно
    
    Raises:
        ValueError: Если user.id не заполнен
    """
    if not user.id:
        raise ValueError("User.id должен быть заполнен для обновления")
    
    with get_db_session(db_file) as session:
        try:
            user_repo = UserRepository(session)
            sql_user = user_repo.get_by_id(user.id)
            if not sql_user:
                return False
            pydantic_user_to_sqlalchemy(user, sql_user)
            user_repo.update(sql_user)
            logger.info(f"Обновлен пользователь: {user.name} (id: {user.id})")
            return True
        except Exception as e:
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
    with get_db_session(db_file) as session:
        user_repo = UserRepository(session)
        return user_repo.count()


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
        event: Объект CalendarEvent (валидация выполняется Pydantic)
    
    Returns:
        ID созданного события
    """
    with get_db_session(db_file) as session:
        try:
            event_repo = EventRepository(session)
            sql_event = pydantic_event_to_sqlalchemy(event)
            created_event = event_repo.create(sql_event)
            logger.info(f"Создано событие: {event.title} (id: {created_event.id})")
            return created_event.id
        except Exception as e:
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
    """
    with get_db_session(db_file) as session:
        event_repo = EventRepository(session)
        return event_repo.get_by_id_pydantic(event_id)


def get_events_in_range(
    db_file: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> List[CalendarEvent]:
    """
    Получает ВСЕ события в указанном диапазоне дат (общий календарь).
    """
    with get_db_session(db_file) as session:
        event_repo = EventRepository(session)
        return event_repo.get_in_range_pydantic(start_datetime, end_datetime)


def get_conflicting_events_global(
    db_file: str,
    event_datetime: datetime,
    duration_minutes: int,
) -> List[CalendarEvent]:
    """
    Находит события общего календаря, которые конфликтуют по времени с указанным интервалом.
    """
    with get_db_session(db_file) as session:
        event_repo = EventRepository(session)
        return event_repo.get_conflicting_pydantic(event_datetime, duration_minutes, telegram_id=None)


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
        ValueError: Если event_id невалиден, updates пуст или содержит недопустимые поля
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    if not updates:
        raise ValueError("updates не может быть пустым")
    
    # Разрешенные поля для обновления
    allowed_fields = {'title', 'datetime', 'duration_minutes', 'category', 'status', 'partner_notified'}
    
    # Валидация полей
    for key in updates.keys():
        if key not in allowed_fields:
            raise ValueError(f"Поле '{key}' не может быть обновлено")
    
    with get_db_session(db_file) as session:
        try:
            event_repo = EventRepository(session)
            # Получаем текущее событие как Pydantic модель
            current_event = event_repo.get_by_id_pydantic(event_id)
            if not current_event:
                return False
            
            # Получаем SQLAlchemy модель для обновления
            sql_event = event_repo.get_by_id(event_id)
            
            # Применяем обновления напрямую к полям с валидацией
            for key, value in updates.items():
                if key == 'title':
                    if not value or not str(value).strip():
                        raise ValueError("title не может быть пустым")
                    current_event.title = str(value).strip()
                elif key == 'datetime':
                    if not isinstance(value, datetime):
                        raise ValueError("datetime должен быть объектом datetime")
                    current_event.datetime = value
                elif key == 'duration_minutes':
                    if not isinstance(value, int) or value <= 0:
                        raise ValueError("duration_minutes должен быть положительным числом")
                    current_event.duration_minutes = value
                elif key == 'category':
                    current_event.category = EventCategory(value) if isinstance(value, str) else value
                elif key == 'status':
                    current_event.status = EventStatus(value) if isinstance(value, str) else value
                elif key == 'partner_notified':
                    current_event.partner_notified = bool(value)
            
            # Обновляем только измененные поля в SQLAlchemy модели
            if 'title' in updates:
                sql_event.title = current_event.title
            if 'datetime' in updates:
                sql_event.datetime = _to_utc_iso(current_event.datetime)
            if 'duration_minutes' in updates:
                sql_event.duration_minutes = current_event.duration_minutes
            if 'category' in updates:
                sql_event.category = current_event.category.value
            if 'status' in updates:
                sql_event.status = current_event.status.value
            if 'partner_notified' in updates:
                sql_event.partner_notified = current_event.partner_notified
            
            event_repo.update(sql_event)
            logger.info(f"Обновлено событие {event_id}: {', '.join(updates.keys())}")
            return True
        except Exception as e:
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
    """
    if not event_id or event_id <= 0:
        raise ValueError("event_id должен быть положительным числом")
    
    with get_db_session(db_file) as session:
        try:
            event_repo = EventRepository(session)
            deleted = event_repo.delete(event_id)
            if deleted:
                logger.info(f"Удалено событие {event_id}")
            return deleted
        except Exception as e:
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
    if start_date > end_date:
        raise ValueError("start_date не может быть позже end_date")
    
    # Преобразуем date в datetime для начала и конца дня
    start_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(start_date, datetime.min.time())
    )
    end_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(end_date, datetime.max.time())
    )
    
    with get_db_session(db_file) as session:
        event_repo = EventRepository(session)
        return event_repo.get_by_creator_pydantic(creator_telegram_id, start_datetime, end_datetime)


def mark_partner_notified(db_file: str, event_id: int) -> bool:
    """
    Отмечает, что партнер был уведомлен о событии.
    
    Args:
        db_file: Путь к файлу базы данных
        event_id: ID события
    
    Returns:
        True если обновление успешно
    """
    return update_event(db_file, event_id, {"partner_notified": True})


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
    """
    with get_db_session(db_file) as session:
        try:
            participant_repo = EventParticipantRepository(session)
            added = participant_repo.add_participant(event_id, user_id)
            if added:
                logger.info(f"Добавлен участник {user_id} к событию {event_id}")
            return added
        except Exception as e:
            logger.error(f"Ошибка при добавлении участника: {e}")
            raise


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
    """
    with get_db_session(db_file) as session:
        participant_repo = EventParticipantRepository(session)
        return participant_repo.get_events_by_participant_pydantic(telegram_id, start_datetime, end_datetime)

