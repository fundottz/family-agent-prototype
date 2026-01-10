"""Преобразование между SQLAlchemy ORM моделями и Pydantic моделями."""

from typing import Optional
from datetime import datetime

from core_logic.schemas import User, CalendarEvent, EventStatus, EventCategory
from db.models import User as SQLUser, Event as SQLEvent, EventParticipant as SQLEventParticipant

# Импортируем функции конвертации timezone из database.py
# Эти функции будут использоваться для конвертации datetime между UTC и Europe/Moscow
import pytz

DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


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


def sqlalchemy_user_to_pydantic(sql_user: SQLUser) -> User:
    """
    Преобразует SQLAlchemy User в Pydantic User.
    
    Args:
        sql_user: SQLAlchemy модель User
    
    Returns:
        Pydantic модель User
    """
    return User(
        id=sql_user.id,
        telegram_id=sql_user.telegram_id,
        name=sql_user.name,
        partner_telegram_id=sql_user.partner_telegram_id,
        digest_time=sql_user.digest_time
    )


def pydantic_user_to_sqlalchemy(pydantic_user: User, sql_user: Optional[SQLUser] = None) -> SQLUser:
    """
    Преобразует Pydantic User в SQLAlchemy User.
    
    Args:
        pydantic_user: Pydantic модель User
        sql_user: Существующая SQLAlchemy модель (для обновления) или None
    
    Returns:
        SQLAlchemy модель User
    """
    if sql_user:
        # Обновляем существующую модель
        sql_user.telegram_id = pydantic_user.telegram_id
        sql_user.name = pydantic_user.name
        sql_user.partner_telegram_id = pydantic_user.partner_telegram_id
        sql_user.digest_time = pydantic_user.digest_time
        return sql_user
    else:
        # Создаем новую модель
        return SQLUser(
            telegram_id=pydantic_user.telegram_id,
            name=pydantic_user.name,
            partner_telegram_id=pydantic_user.partner_telegram_id,
            digest_time=pydantic_user.digest_time
        )


def sqlalchemy_event_to_pydantic(sql_event: SQLEvent) -> CalendarEvent:
    """
    Преобразует SQLAlchemy Event в Pydantic CalendarEvent.
    
    Args:
        sql_event: SQLAlchemy модель Event
    
    Returns:
        Pydantic модель CalendarEvent
    """
    # Конвертируем datetime из БД (хранится как ISO строка в UTC) в datetime объект
    if isinstance(sql_event.datetime, str):
        event_datetime = _from_utc_iso(sql_event.datetime)
    else:
        # Если это уже datetime объект, конвертируем его
        if sql_event.datetime.tzinfo is None:
            # Если naive, считаем что это UTC
            event_datetime = pytz.UTC.localize(sql_event.datetime)
        else:
            event_datetime = sql_event.datetime
        # Конвертируем в Europe/Moscow
        event_datetime = event_datetime.astimezone(DEFAULT_TIMEZONE)
    
    # Конвертируем created_at аналогично
    created_at = None
    if sql_event.created_at:
        if isinstance(sql_event.created_at, str):
            created_at = _from_utc_iso(sql_event.created_at)
        else:
            if sql_event.created_at.tzinfo is None:
                created_at = pytz.UTC.localize(sql_event.created_at)
            else:
                created_at = sql_event.created_at
            created_at = created_at.astimezone(DEFAULT_TIMEZONE)
    
    return CalendarEvent(
        id=sql_event.id,
        title=sql_event.title,
        datetime=event_datetime,
        duration_minutes=sql_event.duration_minutes,
        creator_telegram_id=sql_event.creator_telegram_id,
        status=EventStatus(sql_event.status),
        category=EventCategory(sql_event.category),
        created_at=created_at,
        partner_notified=bool(sql_event.partner_notified)
    )


def pydantic_event_to_sqlalchemy(pydantic_event: CalendarEvent, sql_event: Optional[SQLEvent] = None) -> SQLEvent:
    """
    Преобразует Pydantic CalendarEvent в SQLAlchemy Event.
    
    Args:
        pydantic_event: Pydantic модель CalendarEvent
        sql_event: Существующая SQLAlchemy модель (для обновления) или None
    
    Returns:
        SQLAlchemy модель Event
    """
    # Конвертируем datetime в ISO строку UTC для хранения в БД
    datetime_str = _to_utc_iso(pydantic_event.datetime)
    
    # Конвертируем created_at аналогично, если есть
    created_at_str = None
    if pydantic_event.created_at:
        created_at_str = _to_utc_iso(pydantic_event.created_at)
    
    if sql_event:
        # Обновляем существующую модель
        sql_event.title = pydantic_event.title
        sql_event.datetime = datetime_str
        sql_event.duration_minutes = pydantic_event.duration_minutes
        sql_event.creator_telegram_id = pydantic_event.creator_telegram_id
        sql_event.status = pydantic_event.status.value
        sql_event.category = pydantic_event.category.value
        sql_event.partner_notified = pydantic_event.partner_notified
        if created_at_str:
            sql_event.created_at = created_at_str
        return sql_event
    else:
        # Создаем новую модель
        return SQLEvent(
            title=pydantic_event.title,
            datetime=datetime_str,
            duration_minutes=pydantic_event.duration_minutes,
            creator_telegram_id=pydantic_event.creator_telegram_id,
            status=pydantic_event.status.value,
            category=pydantic_event.category.value,
            partner_notified=pydantic_event.partner_notified,
            created_at=created_at_str
        )
