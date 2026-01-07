"""Чистые функции для работы с календарем (framework-agnostic)."""

import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Callable, Any
import pytz

from .schemas import (
    CalendarEvent,
    AvailabilityResult,
    ScheduleResult,
    ConflictInfo,
    EventStatus,
    EventCategory,
    User,
)
from .database import (
    get_user_by_telegram_id,
    get_conflicting_events_global,
    create_event,
    add_event_participant,
    get_events_in_range,
)

# Часовой пояс по умолчанию
DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")

# Получаем путь к БД из переменной окружения
DB_FILE = os.getenv("DB_FILE", "family_calendar.db")

# Глобальная переменная для callback уведомлений партнера
_notify_partner_callback: Optional[Callable[[CalendarEvent, int], Any]] = None


def set_notify_partner_callback(callback: Optional[Callable[[CalendarEvent, int], Any]]) -> None:
    """
    Устанавливает callback функцию для уведомления партнера.
    
    Args:
        callback: Функция, которая принимает (event: CalendarEvent, creator_telegram_id: int)
    """
    global _notify_partner_callback
    _notify_partner_callback = callback


def check_availability(
    start_time: datetime,
    duration_minutes: int,
) -> AvailabilityResult:
    """
    Проверяет доступность пользователя на заданный временной слот.
    
    Args:
        start_time: Начало события (datetime в Europe/Moscow)
        duration_minutes: Продолжительность в минутах
    
    Returns:
        AvailabilityResult с информацией о доступности и конфликтах
    """
    # Убеждаемся, что start_time в правильном timezone
    if start_time.tzinfo is None:
        start_time = DEFAULT_TIMEZONE.localize(start_time)
    elif start_time.tzinfo != DEFAULT_TIMEZONE:
        start_time = start_time.astimezone(DEFAULT_TIMEZONE)
    
    # Получаем конфликтующие события
    conflicting_events = get_conflicting_events_global(DB_FILE, start_time, duration_minutes)
    
    return AvailabilityResult(
        is_available=len(conflicting_events) == 0,
        conflicting_events=conflicting_events
    )


def schedule_event(
    event: CalendarEvent,
    participant_scope: str = "self",
    notify_partner: bool = True,
    notify_callback: Optional[Callable[[CalendarEvent, int], Any]] = None,
) -> ScheduleResult:
    """
    Создает событие в календаре.
    
    Общий календарь: событие блокирует время для всех, вне зависимости от участников.
    participant_scope используется только для информативного поля участников (event_participants).
    
    Args:
        event: Объект CalendarEvent с данными события
        participant_scope: 'self' или 'both' — как заполнять таблицу участников (информативно).
        notify_partner: Если True, отправляет уведомление партнеру (требует notify_callback)
        notify_callback: Опциональная функция для уведомления партнера. 
                        Должна принимать (event: CalendarEvent, creator_telegram_id: int)
    
    Returns:
        ScheduleResult с результатом создания события
    """
    # Убеждаемся, что datetime в правильном timezone
    if event.datetime.tzinfo is None:
        event.datetime = DEFAULT_TIMEZONE.localize(event.datetime)
    elif event.datetime.tzinfo != DEFAULT_TIMEZONE:
        event.datetime = event.datetime.astimezone(DEFAULT_TIMEZONE)
    
    availability = check_availability(event.datetime, event.duration_minutes)
    if not availability.is_available:
        return ScheduleResult(
            success=False,
            conflicts=[
                ConflictInfo(
                    user_id=0,
                    conflicting_event=conflict_event,
                    conflict_type="time_overlap",
                )
                for conflict_event in availability.conflicting_events
            ],
            message="Обнаружены конфликты времени в общем календаре",
        )
    
    # Создаем событие в БД
    try:
        event_id = create_event(DB_FILE, event)
        
        # Добавляем участников (информативно)
        participant_telegram_ids: List[int] = [event.creator_telegram_id]
        if participant_scope == "both":
            creator = get_user_by_telegram_id(DB_FILE, event.creator_telegram_id)
            if creator and creator.partner_telegram_id:
                participant_telegram_ids = [event.creator_telegram_id, creator.partner_telegram_id]

        for participant_telegram_id in participant_telegram_ids:
            user = get_user_by_telegram_id(DB_FILE, participant_telegram_id)
            if user and user.id:
                add_event_participant(DB_FILE, event_id, user.id)
        
        # Обновляем event с полученным id
        event.id = event_id
        
        # Отправляем уведомление партнеру, если требуется
        # Используем переданный callback или глобальный callback
        callback_to_use = notify_callback or _notify_partner_callback
        if notify_partner and callback_to_use:
            try:
                callback_to_use(event, event.creator_telegram_id)
            except Exception as e:
                # Логируем ошибку, но не блокируем создание события
                import logging
                logging.getLogger(__name__).warning(
                    f"Ошибка при уведомлении партнера: {e}"
                )
        
        return ScheduleResult(
            success=True,
            event_id=event_id,
            message="Событие успешно создано"
        )
    except Exception as e:
        return ScheduleResult(
            success=False,
            message=f"Ошибка при создании события: {str(e)}"
        )


def get_today_agenda(
    target_date: Optional[date] = None,
) -> List[CalendarEvent]:
    """
    Получает список событий на указанную дату для пользователя.
    
    Возвращает ВСЕ события общего календаря на указанную дату.
    
    Args:
        target_date: Дата для получения событий (по умолчанию сегодня)
    
    Returns:
        Список событий, отсортированный по времени
    """
    if target_date is None:
        target_date = date.today()
    
    # Преобразуем date в datetime для начала и конца дня
    start_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(target_date, datetime.min.time())
    )
    end_datetime = DEFAULT_TIMEZONE.localize(
        datetime.combine(target_date, datetime.max.time())
    )
    
    events = get_events_in_range(DB_FILE, start_datetime, end_datetime)
    
    # Сортируем по времени (уже отсортированы в БД, но на всякий случай)
    events.sort(key=lambda e: e.datetime)
    
    return events


def get_user_info(telegram_id: int) -> Optional[User]:
    """
    Получает информацию о пользователе по Telegram ID.
    
    Args:
        telegram_id: Telegram ID пользователя
    
    Returns:
        User или None, если пользователь не найден
    """
    return get_user_by_telegram_id(DB_FILE, telegram_id)


def get_joint_today_agenda(
    telegram_id: int,
    target_date: Optional[date] = None,
    include: str = "both",
) -> List[CalendarEvent]:
    """
    УСТАРЕЛО: общий календарь, используйте get_today_agenda().
    
    Args:
        telegram_id: Telegram ID пользователя (текущего собеседника)
        target_date: Дата (по умолчанию сегодня)
        include: 'both' — события, где участвуют оба партнера (пересечение);
                 'any' — объединение событий обоих участников.
    
    Returns:
        Список событий, отсортированный по времени
    """
    return get_today_agenda(target_date)
