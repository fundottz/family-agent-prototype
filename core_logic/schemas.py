"""Pydantic models for data structures."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
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
    telegram_id: int = Field(gt=0, description="Telegram ID должен быть положительным числом")
    name: str = Field(min_length=1, description="Имя не может быть пустым")
    partner_telegram_id: Optional[int] = Field(default=None, gt=0)
    digest_time: str = Field(default="07:00", pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', description="Формат HH:MM")


class CalendarEvent(BaseModel):
    """Модель события календаря."""
    id: Optional[int] = None
    title: str = Field(min_length=1, description="Название не может быть пустым")
    datetime: datetime
    duration_minutes: int = Field(gt=0, description="Продолжительность должна быть положительным числом")
    creator_telegram_id: int = Field(gt=0, description="Telegram ID создателя должен быть положительным числом")
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


class CancelResult(BaseModel):
    """Результат отмены событий."""
    success: bool
    cancelled_count: int = 0
    cancelled_event_ids: List[int] = []
    failed_event_ids: List[int] = []
    message: str = ""

