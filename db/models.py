"""SQLAlchemy ORM models for database tables."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index, TypeDecorator
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

from core_logic.schemas import EventStatus, EventCategory

Base = declarative_base()


class ISOStringDateTime(TypeDecorator):
    """
    Custom type для хранения datetime как ISO строки в БД (для совместимости с существующей БД).
    """
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Конвертирует datetime в ISO строку при записи в БД."""
        if value is None:
            return None
        if isinstance(value, str):
            return value  # Уже строка
        # Конвертируем datetime в ISO строку UTC
        import pytz
        if value.tzinfo is None:
            value = pytz.timezone("Europe/Moscow").localize(value)
        value_utc = value.astimezone(pytz.UTC)
        return value_utc.isoformat()
    
    def process_result_value(self, value, dialect):
        """Возвращает ISO строку как есть (конвертация в datetime будет в converters)."""
        return value  # Возвращаем строку, конвертация будет в converters


class User(Base):
    """SQLAlchemy модель пользователя."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    partner_telegram_id = Column(Integer, nullable=True)
    digest_time = Column(String, nullable=False, default="07:00")
    created_at = Column(DateTime, nullable=True, default=func.current_timestamp())
    
    # Relationships (опционально, для удобства доступа)
    # events_created = relationship("Event", back_populates="creator", foreign_keys="Event.creator_telegram_id")
    # participant_events = relationship("EventParticipant", back_populates="user")


class Event(Base):
    """SQLAlchemy модель события."""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    datetime = Column(ISOStringDateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    creator_telegram_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    status = Column(String, nullable=False, default=EventStatus.PROPOSED.value)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=True, default=func.current_timestamp())
    partner_notified = Column(Boolean, nullable=False, default=False)
    
    # Relationships (опционально, для удобства доступа)
    # creator = relationship("User", foreign_keys=[creator_telegram_id], back_populates="events_created")
    # participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    
    # Индексы
    __table_args__ = (
        Index('idx_events_datetime_creator', 'datetime', 'creator_telegram_id'),
    )


class EventParticipant(Base):
    """SQLAlchemy модель участника события."""
    __tablename__ = "event_participants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=True, default=func.current_timestamp())
    
    # Relationships (опционально, для удобства доступа)
    # event = relationship("Event", back_populates="participants")
    # user = relationship("User", back_populates="participant_events")
    
    # Уникальное ограничение
    __table_args__ = (
        Index('idx_event_participants_event_user', 'event_id', 'user_id', unique=True),
    )
