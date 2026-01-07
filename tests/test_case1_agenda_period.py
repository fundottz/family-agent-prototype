"""Тесты для Кейса 1: Запрос адженды за период."""

import os
import pytest
from datetime import datetime, date
import pytz

from core_logic.database import init_database, create_user, create_event, get_user_by_telegram_id
from core_logic.calendar_tools import get_agenda_for_period
from core_logic.schemas import User, CalendarEvent, EventStatus, EventCategory
from agents_wrappers import get_agenda_for_period as get_agenda_for_period_wrapper

DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


@pytest.fixture
def test_db():
    """Создает тестовую БД и возвращает путь к ней."""
    test_db_file = "test_case1_calendar.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)
    init_database(test_db_file)
    
    # Устанавливаем переменную окружения для calendar_tools
    import core_logic.calendar_tools
    original_db = core_logic.calendar_tools.DB_FILE
    core_logic.calendar_tools.DB_FILE = test_db_file
    
    yield test_db_file
    
    # Восстанавливаем
    core_logic.calendar_tools.DB_FILE = original_db
    if os.path.exists(test_db_file):
        os.remove(test_db_file)


@pytest.fixture
def test_user(test_db):
    """Создает тестового пользователя."""
    user = User(
        telegram_id=111,
        name="Тестовый пользователь",
    )
    create_user(test_db, user)
    return user


class TestGetAgendaForPeriod:
    """Тесты для функции get_agenda_for_period()."""

    def test_get_agenda_for_period_single_day(self, test_db, test_user):
        """Тест: получение событий за один день."""
        # Создаем события в разные дни
        event1 = CalendarEvent(
            title="Событие 1",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 10, 10, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        event2 = CalendarEvent(
            title="Событие 2",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 11, 10, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        create_event(test_db, event1)
        create_event(test_db, event2)
        
        # Получаем события за 11 января
        events = get_agenda_for_period(date(2026, 1, 11), date(2026, 1, 11))
        
        assert len(events) == 1
        assert events[0].title == "Событие 2"

    def test_get_agenda_for_period_multiple_days(self, test_db, test_user):
        """Тест: получение событий за несколько дней."""
        # Создаем события
        for day in range(10, 15):
            event = CalendarEvent(
                title=f"Событие {day}",
                datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, day, 10, 0)),
                duration_minutes=60,
                creator_telegram_id=test_user.telegram_id,
                status=EventStatus.PROPOSED,
                category=EventCategory.CHILDREN,
            )
            create_event(test_db, event)
        
        # Получаем события с 11 по 13 января
        events = get_agenda_for_period(date(2026, 1, 11), date(2026, 1, 13))
        
        assert len(events) == 3
        assert all(e.title in ["Событие 11", "Событие 12", "Событие 13"] for e in events)

    def test_get_agenda_for_period_no_events(self, test_db):
        """Тест: получение событий, когда их нет."""
        events = get_agenda_for_period(date(2026, 1, 20), date(2026, 1, 25))
        assert len(events) == 0

    def test_get_agenda_for_period_invalid_dates(self, test_db):
        """Тест: получение событий с невалидными датами."""
        with pytest.raises(ValueError, match="start_date не может быть позже"):
            get_agenda_for_period(date(2026, 1, 15), date(2026, 1, 10))

    def test_get_agenda_for_period_boundary_dates(self, test_db, test_user):
        """Тест: получение событий на границах диапазона."""
        # Событие в начале диапазона
        event1 = CalendarEvent(
            title="Событие начало",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 10, 0, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        # Событие в конце диапазона
        event2 = CalendarEvent(
            title="Событие конец",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 15, 23, 59)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        # Событие вне диапазона
        event3 = CalendarEvent(
            title="Событие вне",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 9, 23, 59)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        create_event(test_db, event1)
        create_event(test_db, event2)
        create_event(test_db, event3)
        
        events = get_agenda_for_period(date(2026, 1, 10), date(2026, 1, 15))
        
        assert len(events) == 2
        assert all(e.title in ["Событие начало", "Событие конец"] for e in events)


class TestGetAgendaForPeriodWrapper:
    """Тесты для обертки get_agenda_for_period() в agents_wrappers."""

    def test_wrapper_valid_iso_dates(self, test_db, test_user):
        """Тест: обертка с валидными ISO датами."""
        # Создаем событие
        event = CalendarEvent(
            title="Тестовое событие",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 12, 10, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        create_event(test_db, event)
        
        # Устанавливаем DB_FILE для calendar_tools (уже установлен в фикстуре)
        events = get_agenda_for_period_wrapper(
            start_date="2026-01-12",
            end_date="2026-01-12"
        )
        assert len(events) == 1
        assert events[0].title == "Тестовое событие"

    def test_wrapper_invalid_iso_date(self):
        """Тест: обертка с невалидной ISO датой."""
        with pytest.raises(ValueError, match="должен быть ISO строкой даты"):
            get_agenda_for_period_wrapper(
                start_date="invalid",
                end_date="2026-01-12"
            )

    def test_wrapper_invalid_date_order(self):
        """Тест: обертка с неправильным порядком дат."""
        with pytest.raises(ValueError, match="start_date не может быть позже"):
            get_agenda_for_period_wrapper(
                start_date="2026-01-15",
                end_date="2026-01-12"
            )

