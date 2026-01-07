"""Обертки инструментов для Agno агента (СТРОГИЙ режим ввода).

Строгие требования (единый источник правды):
- datetime/время: ISO 8601 строка с таймзоной, например: "2026-01-07T21:00:00+03:00"
- date/дата: ISO строка "YYYY-MM-DD", например: "2026-01-07"

Обертки принимают ТОЛЬКО такие строки и конвертируют в типы Python.
Любые другие форматы → ValueError с понятным сообщением (уйдет пользователю и в логи).
"""

import logging
from contextvars import ContextVar, Token
from datetime import datetime, date
from typing import List, Optional, Any, Dict
from pydantic import Field
import pytz

from core_logic.calendar_tools import (
    check_availability as _check_availability,
    schedule_event as _schedule_event,
    get_today_agenda as _get_today_agenda,
    get_agenda_for_period as _get_agenda_for_period,
    set_notify_partner_callback,
)
from core_logic.schemas import (
    CalendarEvent,
    AvailabilityResult,
    ScheduleResult,
    EventStatus,
    EventCategory,
)

# Часовой пояс по умолчанию (Europe/Moscow)
DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")
logger = logging.getLogger(__name__)

_CURRENT_TG_ID: ContextVar[Optional[int]] = ContextVar("CURRENT_TG_ID", default=None)


def _set_current_telegram_id(telegram_id: int) -> Token:
    """Внутреннее: устанавливает текущий Telegram ID в ContextVar для текущей asyncio-задачи."""
    return _CURRENT_TG_ID.set(int(telegram_id))


def _reset_current_telegram_id(token: Token) -> None:
    """Внутреннее: сбрасывает текущий Telegram ID по token."""
    _CURRENT_TG_ID.reset(token)


def set_current_telegram_id(telegram_id: int) -> bool:
    """
    Устанавливает текущий Telegram ID для вызовов tools без явного параметра.
    Используется ботом до вызова агента, чтобы не заставлять модель просить ID.
    """
    _CURRENT_TG_ID.set(int(telegram_id))
    return True


def _get_current_telegram_id() -> Optional[int]:
    """Внутреннее: получает текущий Telegram ID из ContextVar."""
    return _CURRENT_TG_ID.get()


def _require_iso_datetime(param_name: str, value: Any) -> datetime:
    """
    Строго принимает ТОЛЬКО ISO 8601 строку с timezone, например: "2026-01-07T21:00:00+03:00".
    Конвертирует в datetime и приводит к Europe/Moscow.
    """
    if not isinstance(value, str):
        logger.warning("Invalid datetime type for %s: %r", param_name, value)
        raise ValueError(
            f"{param_name} должен быть ISO строкой datetime с таймзоной, "
            f'например: "2026-01-07T21:00:00+03:00".'
        )
    try:
        iso = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
    except Exception:
        logger.warning("Invalid ISO datetime for %s: %r", param_name, value)
        raise ValueError(
            f"{param_name} должен быть ISO строкой datetime с таймзоной, "
            f'например: "2026-01-07T21:00:00+03:00".'
        )
    if dt.tzinfo is None:
        raise ValueError(
            f"{param_name} должен содержать timezone (например +03:00). "
            f'Пример: "2026-01-07T21:00:00+03:00".'
        )
    return dt.astimezone(DEFAULT_TIMEZONE)


def _require_iso_date(param_name: str, value: Any) -> date:
    """
    Строго принимает ТОЛЬКО ISO строку даты "YYYY-MM-DD".
    """
    if not isinstance(value, str):
        logger.warning("Invalid date type for %s: %r", param_name, value)
        raise ValueError(
            f'{param_name} должен быть ISO строкой даты, например: "2026-01-07".'
        )
    try:
        y, m, d = [int(x) for x in value.split("-")]
        return date(y, m, d)
    except Exception:
        logger.warning("Invalid ISO date for %s: %r", param_name, value)
        raise ValueError(
            f'{param_name} должен быть ISO строкой даты, например: "2026-01-07".'
        )


def check_availability(
    start_time: str = Field(...),
    duration_minutes: int = Field(...),
    telegram_id: Optional[int] = Field(default=None),
) -> AvailabilityResult:
    """
    Проверяет доступность временного слота в общем календаре.
    
    Контракт ввода (строго):
    - start_time: ISO 8601 строка datetime с таймзоной, например: "2026-01-07T21:00:00+03:00"
    - duration_minutes: int > 0
    - telegram_id: игнорируется (общий календарь), автоматически берется из контекста если не передан
    
    Args:
        start_time: Начало события (ISO строка)
        duration_minutes: Продолжительность в минутах
        telegram_id: Игнорируется (для обратной совместимости)
    
    Returns:
        AvailabilityResult с информацией о доступности и конфликтах
    """
    start_dt = _require_iso_datetime("start_time", start_time)
    return _check_availability(start_dt, duration_minutes)


def schedule_event(
    title: str = Field(...),
    datetime: str = Field(...),
    duration_minutes: int = Field(...),
    category: str = Field(...),
    status: str = Field(default="предложено"),
    participant_scope: str = Field(default="self"),
    notify_partner: bool = Field(default=True),
    creator_telegram_id: Optional[int] = Field(default=None),
) -> ScheduleResult:
    """
    Создает событие в календаре.
    
    Контракт ввода (строго):
    - title: str (не пустой)
    - datetime: ISO 8601 строка datetime с таймзоной, например: "2026-01-07T21:00:00+03:00"
    - duration_minutes: int > 0
    - category: one of {'дети','дом','ремонт','личное'}
    - status: one of {'предложено','подтверждено'} (по умолчанию 'предложено')
    - participant_scope: 'self'|'both' (информативно, по умолчанию 'self')
    - notify_partner: bool (по умолчанию True) - отправлять ли уведомление партнеру
    - creator_telegram_id: автоматически берется из контекста, не передавай явно
    
    Общий календарь: событие блокирует слот времени для всех.
    participant_scope влияет только на информативный список участников.
    
    Args:
        title: Название события
        datetime: Дата и время события (ISO строка)
        duration_minutes: Продолжительность в минутах
        category: Категория события
        status: Статус события (по умолчанию 'предложено')
        participant_scope: 'self' или 'both' (по умолчанию 'self')
        notify_partner: Отправлять ли уведомление партнеру (по умолчанию True)
        creator_telegram_id: Автоматически берется из контекста, не передавай явно
    
    Returns:
        ScheduleResult с результатом создания события
    """
    # Валидируем datetime (строгий режим)
    event_dt = _require_iso_datetime("datetime", datetime)

    # Преобразуем строки в enum (строгий режим)
    try:
        event_status = EventStatus(status)
    except Exception:
        raise ValueError("status должен быть 'предложено' или 'подтверждено'.")
    try:
        event_category = EventCategory(category)
    except Exception:
        raise ValueError("category должен быть одним из: 'дети', 'дом', 'ремонт', 'личное'.")

    if participant_scope not in ("self", "both"):
        raise ValueError("participant_scope должен быть 'self' или 'both'.")
    
    # Определяем создателя из контекста, если не передан или передан 0
    if creator_telegram_id is None or creator_telegram_id <= 0:
        current = _get_current_telegram_id()
        if current is None:
            raise ValueError("Не удалось определить пользователя. Попробуйте еще раз.")
        creator_telegram_id = current
    event = CalendarEvent(
        title=title,
        datetime=event_dt,
        duration_minutes=duration_minutes,
        creator_telegram_id=creator_telegram_id,
        status=event_status,
        category=event_category,
    )
    
    return _schedule_event(event, participant_scope, notify_partner=notify_partner)


def get_today_agenda(
    telegram_id: Optional[int] = Field(default=None),
    target_date: Optional[str] = Field(default=None),
) -> List[CalendarEvent]:
    """
    Получает список событий на указанную дату для пользователя.
    
    Контракт ввода (строго):
    - target_date: ISO "YYYY-MM-DD" | None (None = сегодня)
    
    Возвращает ВСЕ события общего календаря.
    
    Args:
        target_date: Дата для получения событий (опционально, по умолчанию сегодня)
    
    Returns:
        Список событий, отсортированный по времени
    """
    if target_date is None:
        return _get_today_agenda(None)
    resolved = _require_iso_date("target_date", target_date)
    return _get_today_agenda(resolved)

def get_agenda(
    target_date: Optional[str] = Field(default=None),
    telegram_id: Optional[int] = Field(default=None),
) -> List[CalendarEvent]:
    """
    Тул для получения повестки общего календаря.
    
    Контракт ввода (строго):
    - target_date: ISO "YYYY-MM-DD" | None (None = сегодня)
    - telegram_id: игнорируется (общий календарь), автоматически берется из контекста если не передан
    
    Возвращает ВСЕ события общего календаря на дату.
    """
    resolved_date = None
    if target_date is not None:
        resolved_date = _require_iso_date("target_date", target_date)
    return _get_today_agenda(resolved_date)


## В новой парадигме (общий календарь) личная/общая адженда не разделяются.


def get_agenda_for_period(
    start_date: str = Field(...),
    end_date: str = Field(...),
    telegram_id: Optional[int] = Field(default=None),
) -> List[CalendarEvent]:
    """
    Получает список событий за указанный период.
    
    Контракт ввода (строго):
    - start_date: ISO строка даты "YYYY-MM-DD" (начало периода, включительно)
    - end_date: ISO строка даты "YYYY-MM-DD" (конец периода, включительно)
    - telegram_id: игнорируется (общий календарь), автоматически берется из контекста если не передан
    
    Возвращает ВСЕ события общего календаря в указанном диапазоне дат.
    
    Args:
        start_date: Начальная дата периода (ISO строка)
        end_date: Конечная дата периода (ISO строка)
        telegram_id: Игнорируется (для обратной совместимости)
    
    Returns:
        Список событий, отсортированный по времени
    
    Raises:
        ValueError: Если даты невалидны или start_date > end_date
    """
    start = _require_iso_date("start_date", start_date)
    end = _require_iso_date("end_date", end_date)
    
    if start > end:
        raise ValueError("start_date не может быть позже end_date")
    
    return _get_agenda_for_period(start, end)


def get_current_datetime() -> Dict[str, str]:
    """
    Возвращает текущие дату и время в Europe/Moscow.
    
    Контракт вывода:
    - now_iso: ISO 8601 datetime с таймзоной (+03:00)
    - date_iso: YYYY-MM-DD
    - weekday_ru: название дня недели на русском (понедельник..воскресенье)
    - human_ru: строка вида "вторник, 06 января 2026"
    """
    now = datetime.now(DEFAULT_TIMEZONE)
    weekdays = [
        "понедельник", "вторник", "среда",
        "четверг", "пятница", "суббота", "воскресенье",
    ]
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    weekday_ru = weekdays[now.weekday()]
    human_ru = f"{weekday_ru}, {now.day:02d} {months[now.month - 1]} {now.year}"
    return {
        "now_iso": now.isoformat(),
        "date_iso": now.date().isoformat(),
        "weekday_ru": weekday_ru,
        "human_ru": human_ru,
    }
