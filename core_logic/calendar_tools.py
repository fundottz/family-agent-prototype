"""Чистые функции для работы с календарем (framework-agnostic)."""

import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Callable, Any, Tuple
import pytz

from .schemas import (
    CalendarEvent,
    AvailabilityResult,
    ScheduleResult,
    ConflictInfo,
    EventStatus,
    EventCategory,
    User,
    CancelResult,
)
from .database import (
    get_user_by_telegram_id,
    get_conflicting_events_global,
    create_event,
    add_event_participant,
    get_events_in_range,
    get_events_by_creator_in_range,
    get_event_by_id,
    delete_event,
)

# Часовой пояс по умолчанию
DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")

# Получаем путь к БД из переменной окружения
DB_FILE = os.getenv("DB_FILE", "family_calendar.db")

# Глобальная переменная для callback уведомлений партнера
_notify_partner_callback: Optional[Callable[[CalendarEvent, int], Any]] = None
_notify_partner_cancellation_callback: Optional[Callable[[List[CalendarEvent], int], Any]] = None


def set_notify_partner_callback(callback: Optional[Callable[[CalendarEvent, int], Any]]) -> None:
    """
    Устанавливает callback функцию для уведомления партнера.
    
    Args:
        callback: Функция, которая принимает (event: CalendarEvent, creator_telegram_id: int)
    """
    global _notify_partner_callback
    _notify_partner_callback = callback


def set_notify_partner_cancellation_callback(callback: Optional[Callable[[List[CalendarEvent], int], Any]]) -> None:
    """
    Устанавливает callback функцию для уведомления партнера об отмене событий.
    
    Args:
        callback: Функция, которая принимает (events: List[CalendarEvent], creator_telegram_id: int)
    """
    global _notify_partner_cancellation_callback
    _notify_partner_cancellation_callback = callback


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


def find_events_to_cancel(
    creator_telegram_id: int,
    start_date: date,
    end_date: date,
    title_filter: Optional[str] = None,
    category_filter: Optional[EventCategory] = None,
) -> List[CalendarEvent]:
    """
    Находит события для отмены по заданным критериям.
    
    Args:
        creator_telegram_id: Telegram ID создателя событий
        start_date: Начальная дата диапазона (включительно)
        end_date: Конечная дата диапазона (включительно)
        title_filter: Опциональный фильтр по названию (частичное совпадение)
        category_filter: Опциональный фильтр по категории
    
    Returns:
        Список событий, соответствующих критериям
    """
    # Получаем события создателя за период
    events = get_events_by_creator_in_range(DB_FILE, creator_telegram_id, start_date, end_date)
    
    # Применяем фильтры
    filtered_events = []
    for event in events:
        # Фильтр по категории
        if category_filter and event.category != category_filter:
            continue
        
        # Фильтр по названию
        if title_filter and title_filter.lower() not in event.title.lower():
            continue
        
        filtered_events.append(event)
    
    return filtered_events


def cancel_events(
    event_ids: List[int],
    creator_telegram_id: int,
    notify_partner: bool = True,
) -> CancelResult:
    """
    Отменяет события (удаляет их из календаря).
    
    Проверяет права: только создатель может отменить свои события.
    
    Args:
        event_ids: Список ID событий для отмены
        creator_telegram_id: Telegram ID создателя (для проверки прав)
        notify_partner: Если True, отправляет уведомление партнеру
    
    Returns:
        CancelResult с результатами отмены
    """
    if not event_ids:
        return CancelResult(
            success=False,
            message="Не указаны события для отмены"
        )
    
    cancelled_ids = []
    failed_ids = []
    cancelled_events = []  # Сохраняем события для уведомления
    
    for event_id in event_ids:
        try:
            # Получаем событие для проверки прав
            event = get_event_by_id(DB_FILE, event_id)
            if not event:
                failed_ids.append(event_id)
                continue
            
            # Проверка прав: только создатель может отменить
            if event.creator_telegram_id != creator_telegram_id:
                failed_ids.append(event_id)
                continue
            
            # Удаляем событие
            if delete_event(DB_FILE, event_id):
                cancelled_ids.append(event_id)
                cancelled_events.append(event)
            else:
                failed_ids.append(event_id)
        
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Ошибка при отмене события {event_id}: {e}")
            failed_ids.append(event_id)
    
    # Отправляем уведомление партнеру, если требуется
    if notify_partner and cancelled_events and _notify_partner_cancellation_callback:
        try:
            _notify_partner_cancellation_callback(cancelled_events, creator_telegram_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Ошибка при уведомлении партнера об отмене: {e}"
            )
    
    success = len(cancelled_ids) > 0
    message = ""
    if len(cancelled_ids) > 0:
        message = f"Отменено событий: {len(cancelled_ids)}"
    if len(failed_ids) > 0:
        if message:
            message += f". Не удалось отменить: {len(failed_ids)}"
        else:
            message = f"Не удалось отменить события: {len(failed_ids)}"
    
    return CancelResult(
        success=success,
        cancelled_count=len(cancelled_ids),
        cancelled_event_ids=cancelled_ids,
        failed_event_ids=failed_ids,
        message=message
    )
