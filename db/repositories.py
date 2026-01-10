"""Repository pattern implementation for database access."""

from typing import Optional, List, TypeVar, Generic, Type
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.exc import IntegrityError

from db.models import Base, User, Event, EventParticipant
from core_logic.schemas import User as PydanticUser, CalendarEvent, EventStatus, EventCategory
from db.converters import (
    sqlalchemy_user_to_pydantic,
    pydantic_user_to_sqlalchemy,
    sqlalchemy_event_to_pydantic,
    pydantic_event_to_sqlalchemy
)

T = TypeVar('T', bound=Base)


class BaseRepository(Generic[T]):
    """Базовый класс репозитория с общими CRUD операциями."""
    
    def __init__(self, session: Session, model: Type[T]):
        """
        Инициализирует репозиторий.
        
        Args:
            session: SQLAlchemy сессия
            model: SQLAlchemy модель класса
        """
        self.session = session
        self.model = model
    
    def create(self, entity: T) -> T:
        """
        Создает новую сущность в БД.
        
        Args:
            entity: SQLAlchemy модель сущности
        
        Returns:
            Созданная сущность с заполненным id
        """
        self.session.add(entity)
        self.session.flush()  # Получаем id без commit
        return entity
    
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Получает сущность по ID.
        
        Args:
            entity_id: ID сущности
        
        Returns:
            Сущность или None, если не найдена
        """
        return self.session.get(self.model, entity_id)
    
    def update(self, entity: T) -> bool:
        """
        Обновляет сущность в БД.
        
        Args:
            entity: SQLAlchemy модель сущности с заполненным id
        
        Returns:
            True если обновление успешно
        """
        self.session.add(entity)
        self.session.flush()
        return True
    
    def delete(self, entity_id: int) -> bool:
        """
        Удаляет сущность по ID.
        
        Args:
            entity_id: ID сущности
        
        Returns:
            True если удаление успешно
        """
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.flush()
            return True
        return False
    
    def list(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """
        Получает список всех сущностей.
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение для пагинации
        
        Returns:
            Список сущностей
        """
        stmt = select(self.model)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = self.session.execute(stmt)
        return list(result.scalars().all())


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями."""
    
    def __init__(self, session: Session):
        super().__init__(session, User)
    
    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получает пользователя по Telegram ID (SQLAlchemy модель).
        
        Args:
            telegram_id: Telegram ID пользователя
        
        Returns:
            SQLAlchemy модель User или None
        """
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    def get_by_telegram_id_pydantic(self, telegram_id: int) -> Optional[PydanticUser]:
        """
        Получает пользователя по Telegram ID (Pydantic модель).
        
        Args:
            telegram_id: Telegram ID пользователя
        
        Returns:
            Pydantic модель User или None
        """
        sql_user = self.get_by_telegram_id(telegram_id)
        return sqlalchemy_user_to_pydantic(sql_user) if sql_user else None
    
    def count(self) -> int:
        """
        Подсчитывает количество пользователей.
        
        Returns:
            Количество пользователей
        """
        result = self.session.execute(select(func.count()).select_from(User))
        return result.scalar() or 0


class EventRepository(BaseRepository[Event]):
    """Репозиторий для работы с событиями."""
    
    def __init__(self, session: Session):
        super().__init__(session, Event)
    
    def get_by_creator(
        self,
        creator_telegram_id: int,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
    ) -> List[Event]:
        """
        Получает события создателя за указанный период (SQLAlchemy модели).
        
        Args:
            creator_telegram_id: Telegram ID создателя
            start_datetime: Начало периода (опционально)
            end_datetime: Конец периода (опционально)
        
        Returns:
            Список SQLAlchemy моделей Event
        """
        stmt = select(Event).where(Event.creator_telegram_id == creator_telegram_id)
        
        if start_datetime:
            # Конвертируем в ISO строку UTC для сравнения
            from db.converters import _to_utc_iso
            stmt = stmt.where(Event.datetime >= _to_utc_iso(start_datetime))
        
        if end_datetime:
            from db.converters import _to_utc_iso
            stmt = stmt.where(Event.datetime <= _to_utc_iso(end_datetime))
        
        stmt = stmt.order_by(Event.datetime.asc())
        result = self.session.execute(stmt)
        return list(result.scalars().all())
    
    def get_by_creator_pydantic(
        self,
        creator_telegram_id: int,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
    ) -> List[CalendarEvent]:
        """
        Получает события создателя за указанный период (Pydantic модели).
        
        Args:
            creator_telegram_id: Telegram ID создателя
            start_datetime: Начало периода (опционально)
            end_datetime: Конец периода (опционально)
        
        Returns:
            Список Pydantic моделей CalendarEvent
        """
        sql_events = self.get_by_creator(creator_telegram_id, start_datetime, end_datetime)
        return [sqlalchemy_event_to_pydantic(event) for event in sql_events]
    
    def get_in_range(
        self,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[Event]:
        """
        Получает все события в указанном диапазоне дат (SQLAlchemy модели).
        
        Args:
            start_datetime: Начало периода
            end_datetime: Конец периода
        
        Returns:
            Список SQLAlchemy моделей Event
        """
        from db.converters import _to_utc_iso
        stmt = select(Event).where(
            and_(
                Event.datetime >= _to_utc_iso(start_datetime),
                Event.datetime <= _to_utc_iso(end_datetime)
            )
        ).order_by(Event.datetime.asc())
        result = self.session.execute(stmt)
        return list(result.scalars().all())
    
    def get_in_range_pydantic(
        self,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[CalendarEvent]:
        """
        Получает все события в указанном диапазоне дат (Pydantic модели).
        
        Args:
            start_datetime: Начало периода
            end_datetime: Конец периода
        
        Returns:
            Список Pydantic моделей CalendarEvent
        """
        sql_events = self.get_in_range(start_datetime, end_datetime)
        return [sqlalchemy_event_to_pydantic(event) for event in sql_events]
    
    def get_conflicting(
        self,
        event_datetime: datetime,
        duration_minutes: int,
        telegram_id: Optional[int] = None
    ) -> List[Event]:
        """
        Находит события, которые конфликтуют по времени с указанным событием (SQLAlchemy модели).
        
        Args:
            event_datetime: Дата и время события
            duration_minutes: Продолжительность события в минутах
            telegram_id: Telegram ID пользователя (опционально, для фильтрации по создателю)
        
        Returns:
            Список конфликтующих SQLAlchemy моделей Event
        """
        from db.converters import _to_utc_iso, _from_utc_iso
        
        event_end = event_datetime + timedelta(minutes=duration_minutes)
        
        # Берем широкий диапазон для поиска
        search_start = event_datetime - timedelta(days=1)
        search_end = event_end + timedelta(days=1)
        
        stmt = select(Event).where(
            and_(
                Event.datetime >= _to_utc_iso(search_start),
                Event.datetime <= _to_utc_iso(search_end)
            )
        )
        
        if telegram_id:
            stmt = stmt.where(Event.creator_telegram_id == telegram_id)
        
        result = self.session.execute(stmt)
        all_events = list(result.scalars().all())
        
        # Фильтруем события на конфликты в Python
        conflicting_events = []
        for existing_event in all_events:
            # Конвертируем datetime из БД
            if isinstance(existing_event.datetime, str):
                existing_event_start = _from_utc_iso(existing_event.datetime)
            else:
                existing_event_start = existing_event.datetime
                if existing_event_start.tzinfo is None:
                    import pytz
                    existing_event_start = pytz.UTC.localize(existing_event_start)
            
            existing_event_end = existing_event_start + timedelta(minutes=existing_event.duration_minutes)
            
            # Проверяем пересечение интервалов
            if not (event_end <= existing_event_start or event_datetime >= existing_event_end):
                conflicting_events.append(existing_event)
        
        return conflicting_events
    
    def get_conflicting_pydantic(
        self,
        event_datetime: datetime,
        duration_minutes: int,
        telegram_id: Optional[int] = None
    ) -> List[CalendarEvent]:
        """
        Находит события, которые конфликтуют по времени с указанным событием (Pydantic модели).
        
        Args:
            event_datetime: Дата и время события
            duration_minutes: Продолжительность события в минутах
            telegram_id: Telegram ID пользователя (опционально, для фильтрации по создателю)
        
        Returns:
            Список конфликтующих Pydantic моделей CalendarEvent
        """
        sql_events = self.get_conflicting(event_datetime, duration_minutes, telegram_id)
        return [sqlalchemy_event_to_pydantic(event) for event in sql_events]
    
    def get_by_id_pydantic(self, event_id: int) -> Optional[CalendarEvent]:
        """
        Получает событие по ID (Pydantic модель).
        
        Args:
            event_id: ID события
        
        Returns:
            Pydantic модель CalendarEvent или None
        """
        sql_event = self.get_by_id(event_id)
        return sqlalchemy_event_to_pydantic(sql_event) if sql_event else None


class EventParticipantRepository(BaseRepository[EventParticipant]):
    """Репозиторий для работы с участниками событий."""
    
    def __init__(self, session: Session):
        super().__init__(session, EventParticipant)
    
    def add_participant(self, event_id: int, user_id: int) -> bool:
        """
        Добавляет участника к событию.
        
        Args:
            event_id: ID события
            user_id: ID пользователя
        
        Returns:
            True если добавление успешно
        """
        try:
            participant = EventParticipant(event_id=event_id, user_id=user_id)
            self.session.add(participant)
            self.session.flush()
            return True
        except IntegrityError:
            # Участник уже существует (UNIQUE constraint)
            self.session.rollback()
            return False
    
    def get_participants(self, event_id: int) -> List[int]:
        """
        Получает список ID участников события.
        
        Args:
            event_id: ID события
        
        Returns:
            Список ID пользователей
        """
        stmt = select(EventParticipant.user_id).where(EventParticipant.event_id == event_id)
        result = self.session.execute(stmt)
        return list(result.scalars().all())
    
    def get_events_by_participant(
        self,
        telegram_id: int,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
    ) -> List[Event]:
        """
        Получает события, где пользователь является участником (SQLAlchemy модели).
        
        Args:
            telegram_id: Telegram ID пользователя
            start_datetime: Начало периода (опционально)
            end_datetime: Конец периода (опционально)
        
        Returns:
            Список SQLAlchemy моделей Event
        """
        from db.converters import _to_utc_iso
        
        # JOIN с таблицей users для поиска по telegram_id
        stmt = (
            select(Event)
            .join(EventParticipant, Event.id == EventParticipant.event_id)
            .join(User, EventParticipant.user_id == User.id)
            .where(User.telegram_id == telegram_id)
        )
        
        if start_datetime:
            stmt = stmt.where(Event.datetime >= _to_utc_iso(start_datetime))
        
        if end_datetime:
            stmt = stmt.where(Event.datetime <= _to_utc_iso(end_datetime))
        
        stmt = stmt.order_by(Event.datetime.asc())
        result = self.session.execute(stmt)
        return list(result.scalars().all())
    
    def get_events_by_participant_pydantic(
        self,
        telegram_id: int,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
    ) -> List[CalendarEvent]:
        """
        Получает события, где пользователь является участником (Pydantic модели).
        
        Args:
            telegram_id: Telegram ID пользователя
            start_datetime: Начало периода (опционально)
            end_datetime: Конец периода (опционально)
        
        Returns:
            Список Pydantic моделей CalendarEvent
        """
        sql_events = self.get_events_by_participant(telegram_id, start_datetime, end_datetime)
        return [sqlalchemy_event_to_pydantic(event) for event in sql_events]