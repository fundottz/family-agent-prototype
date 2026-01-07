"""Pydantic models for data structures."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class EventStatus(str, Enum):
    """Статус события."""
    PROPOSED = "предложено"
    CONFIRMED = "подтверждено"
    REJECTED = "отклонено"


class EventCategory(str, Enum):
    """Категория события."""
    CHILDREN = "дети"
    HOME = "дом"
    REPAIR = "ремонт"
    PERSONAL = "личное"


class User(BaseModel):
    """Модель пользователя."""
    id: Optional[int] = None
    telegram_id: int
    name: str
    partner_telegram_id: Optional[int] = None
    digest_time: str = "07:00"  # Формат "HH:MM"


class CalendarEvent(BaseModel):
    """Модель события календаря."""
    id: Optional[int] = None
    title: str
    datetime: datetime
    duration_minutes: int
    creator_telegram_id: int
    status: EventStatus = EventStatus.PROPOSED
    category: EventCategory
    created_at: Optional[datetime] = None
    partner_notified: bool = False


class ParsedEvent(BaseModel):
    """Результат парсинга естественного языка (используется агентом внутренне)."""
    title: str
    datetime: datetime
    category: EventCategory
    duration_minutes: int
    confidence: float = Field(ge=0.0, le=1.0)  # Уверенность в правильности парсинга


class AvailabilityResult(BaseModel):
    """Результат проверки доступности."""
    is_available: bool
    conflicting_events: List[CalendarEvent] = []


class ConflictInfo(BaseModel):
    """Информация о конфликте времени."""
    user_id: int
    conflicting_event: CalendarEvent
    conflict_type: str = "time_overlap"


class ScheduleResult(BaseModel):
    """Результат создания события."""
    success: bool
    event_id: Optional[int] = None
    conflicts: List[ConflictInfo] = []
    alternative_slots: List[datetime] = []
    message: str = ""


class UpdateResult(BaseModel):
    """Результат обновления события."""
    success: bool
    event_id: Optional[int] = None
    conflicts: List[ConflictInfo] = []
    message: str = ""

