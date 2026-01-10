"""Тесты для database.py - функции обновления и удаления событий."""

import os
import pytest
from datetime import datetime, date, timedelta
import pytz

from core_logic.database import (
    init_database,
    create_user,
    create_event,
    get_event_by_id,
    update_event,
    delete_event,
    get_events_by_creator_in_range,
)
from core_logic.schemas import (
    User,
    CalendarEvent,
    EventStatus,
    EventCategory,
)

DEFAULT_TIMEZONE = pytz.timezone("Europe/Moscow")


@pytest.fixture
def test_db():
    """Создает тестовую БД и возвращает путь к ней."""
    test_db_file = "test_family_calendar.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)
    init_database(test_db_file)
    yield test_db_file
    if os.path.exists(test_db_file):
        os.remove(test_db_file)


@pytest.fixture
def test_user(test_db):
    """Создает тестового пользователя."""
    user = User(
        telegram_id=111,
        name="Тестовый пользователь",
        partner_telegram_id=222,
    )
    create_user(test_db, user)
    return user


@pytest.fixture
def test_event(test_db, test_user):
    """Создает тестовое событие."""
    event = CalendarEvent(
        title="Тестовое событие",
        datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 10, 10, 0)),
        duration_minutes=60,
        creator_telegram_id=test_user.telegram_id,
        status=EventStatus.PROPOSED,
        category=EventCategory.CHILDREN,
    )
    event_id = create_event(test_db, event)
    event.id = event_id
    return event


class TestUpdateEvent:
    """Тесты для функции update_event()."""

    def test_update_event_title(self, test_db, test_event):
        """Тест: обновление названия события."""
        result = update_event(test_db, test_event.id, {"title": "Новое название"})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.title == "Новое название"
        assert updated_event.duration_minutes == test_event.duration_minutes

    def test_update_event_datetime(self, test_db, test_event):
        """Тест: обновление даты и времени события."""
        new_datetime = DEFAULT_TIMEZONE.localize(datetime(2026, 1, 15, 14, 30))
        result = update_event(test_db, test_event.id, {"datetime": new_datetime})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.datetime == new_datetime

    def test_update_event_duration(self, test_db, test_event):
        """Тест: обновление продолжительности события."""
        result = update_event(test_db, test_event.id, {"duration_minutes": 90})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.duration_minutes == 90

    def test_update_event_category(self, test_db, test_event):
        """Тест: обновление категории события."""
        result = update_event(test_db, test_event.id, {"category": EventCategory.HOME})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.category == EventCategory.HOME

    def test_update_event_status(self, test_db, test_event):
        """Тест: обновление статуса события."""
        result = update_event(test_db, test_event.id, {"status": EventStatus.CONFIRMED})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.status == EventStatus.CONFIRMED

    def test_update_event_status_string(self, test_db, test_event):
        """Тест: обновление статуса строкой."""
        result = update_event(test_db, test_event.id, {"status": "подтверждено"})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.status == EventStatus.CONFIRMED

    def test_update_event_partner_notified(self, test_db, test_event):
        """Тест: обновление флага уведомления партнера."""
        result = update_event(test_db, test_event.id, {"partner_notified": True})
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.partner_notified is True

    def test_update_event_multiple_fields(self, test_db, test_event):
        """Тест: обновление нескольких полей одновременно."""
        new_datetime = DEFAULT_TIMEZONE.localize(datetime(2026, 1, 20, 15, 0))
        result = update_event(
            test_db,
            test_event.id,
            {
                "title": "Обновленное событие",
                "datetime": new_datetime,
                "duration_minutes": 120,
                "status": EventStatus.CONFIRMED,
            },
        )
        assert result is True
        
        updated_event = get_event_by_id(test_db, test_event.id)
        assert updated_event is not None
        assert updated_event.title == "Обновленное событие"
        assert updated_event.datetime == new_datetime
        assert updated_event.duration_minutes == 120
        assert updated_event.status == EventStatus.CONFIRMED

    def test_update_event_invalid_id(self, test_db):
        """Тест: обновление несуществующего события."""
        result = update_event(test_db, 99999, {"title": "Новое название"})
        assert result is False

    def test_update_event_invalid_event_id(self, test_db):
        """Тест: обновление с невалидным event_id."""
        with pytest.raises(ValueError, match="event_id должен быть положительным"):
            update_event(test_db, -1, {"title": "Новое название"})

    def test_update_event_empty_updates(self, test_db, test_event):
        """Тест: обновление с пустым словарем."""
        with pytest.raises(ValueError, match="updates не может быть пустым"):
            update_event(test_db, test_event.id, {})

    def test_update_event_invalid_field(self, test_db, test_event):
        """Тест: обновление несуществующего поля."""
        with pytest.raises(ValueError, match="не может быть обновлено"):
            update_event(test_db, test_event.id, {"invalid_field": "value"})

    def test_update_event_empty_title(self, test_db, test_event):
        """Тест: обновление с пустым названием."""
        with pytest.raises(ValueError, match="title не может быть пустым"):
            update_event(test_db, test_event.id, {"title": ""})

    def test_update_event_invalid_datetime(self, test_db, test_event):
        """Тест: обновление с невалидным datetime."""
        with pytest.raises(ValueError, match="datetime должен быть объектом"):
            update_event(test_db, test_event.id, {"datetime": "invalid"})

    def test_update_event_invalid_duration(self, test_db, test_event):
        """Тест: обновление с невалидной продолжительностью."""
        with pytest.raises(ValueError, match="duration_minutes должен быть положительным"):
            update_event(test_db, test_event.id, {"duration_minutes": -10})


class TestDeleteEvent:
    """Тесты для функции delete_event()."""

    def test_delete_event_success(self, test_db, test_event):
        """Тест: успешное удаление события."""
        result = delete_event(test_db, test_event.id)
        assert result is True
        
        deleted_event = get_event_by_id(test_db, test_event.id)
        assert deleted_event is None

    def test_delete_event_invalid_id(self, test_db):
        """Тест: удаление несуществующего события."""
        result = delete_event(test_db, 99999)
        assert result is False

    def test_delete_event_invalid_event_id(self, test_db):
        """Тест: удаление с невалидным event_id."""
        with pytest.raises(ValueError, match="event_id должен быть положительным"):
            delete_event(test_db, -1)

    def test_delete_event_with_participants(self, test_db, test_user, test_event):
        """Тест: удаление события с участниками."""
        from core_logic.database import add_event_participant, get_user_by_telegram_id
        
        # Получаем пользователя из БД, чтобы получить его id
        user = get_user_by_telegram_id(test_db, test_user.telegram_id)
        assert user is not None
        assert user.id is not None
        
        # Добавляем участника
        add_event_participant(test_db, test_event.id, user.id)
        
        # Удаляем событие
        result = delete_event(test_db, test_event.id)
        assert result is True
        
        # Проверяем, что событие удалено
        deleted_event = get_event_by_id(test_db, test_event.id)
        assert deleted_event is None


class TestGetEventsByCreatorInRange:
    """Тесты для функции get_events_by_creator_in_range()."""

    def test_get_events_by_creator_in_range_single_day(self, test_db, test_user):
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
        event3 = CalendarEvent(
            title="Событие 3",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 12, 10, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        create_event(test_db, event1)
        create_event(test_db, event2)
        create_event(test_db, event3)
        
        # Получаем события за 11 января
        events = get_events_by_creator_in_range(
            test_db,
            test_user.telegram_id,
            date(2026, 1, 11),
            date(2026, 1, 11),
        )
        
        assert len(events) == 1
        assert events[0].title == "Событие 2"

    def test_get_events_by_creator_in_range_multiple_days(self, test_db, test_user):
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
        events = get_events_by_creator_in_range(
            test_db,
            test_user.telegram_id,
            date(2026, 1, 11),
            date(2026, 1, 13),
        )
        
        assert len(events) == 3
        assert all(e.title in ["Событие 11", "Событие 12", "Событие 13"] for e in events)

    def test_get_events_by_creator_in_range_no_events(self, test_db, test_user):
        """Тест: получение событий, когда их нет."""
        events = get_events_by_creator_in_range(
            test_db,
            test_user.telegram_id,
            date(2026, 1, 20),
            date(2026, 1, 25),
        )
        
        assert len(events) == 0

    def test_get_events_by_creator_in_range_different_creator(self, test_db, test_user):
        """Тест: получение событий только создателя (игнорирование других)."""
        # Создаем пользователя 2
        user2 = User(telegram_id=333, name="Пользователь 2")
        create_user(test_db, user2)
        
        # Событие создателя
        event1 = CalendarEvent(
            title="Событие создателя",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 10, 10, 0)),
            duration_minutes=60,
            creator_telegram_id=test_user.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        # Событие другого пользователя
        event2 = CalendarEvent(
            title="Событие другого",
            datetime=DEFAULT_TIMEZONE.localize(datetime(2026, 1, 10, 11, 0)),
            duration_minutes=60,
            creator_telegram_id=user2.telegram_id,
            status=EventStatus.PROPOSED,
            category=EventCategory.CHILDREN,
        )
        
        create_event(test_db, event1)
        create_event(test_db, event2)
        
        # Получаем события только создателя
        events = get_events_by_creator_in_range(
            test_db,
            test_user.telegram_id,
            date(2026, 1, 10),
            date(2026, 1, 10),
        )
        
        assert len(events) == 1
        assert events[0].title == "Событие создателя"

    def test_get_events_by_creator_in_range_invalid_creator_id(self, test_db):
        """Тест: получение событий с невалидным creator_telegram_id."""
        with pytest.raises(ValueError, match="creator_telegram_id должен быть положительным"):
            get_events_by_creator_in_range(
                test_db,
                -1,
                date(2026, 1, 10),
                date(2026, 1, 15),
            )

    def test_get_events_by_creator_in_range_invalid_dates(self, test_db, test_user):
        """Тест: получение событий с невалидными датами."""
        with pytest.raises(ValueError, match="start_date не может быть позже"):
            get_events_by_creator_in_range(
                test_db,
                test_user.telegram_id,
                date(2026, 1, 15),
                date(2026, 1, 10),
            )

    def test_get_events_by_creator_in_range_boundary_dates(self, test_db, test_user):
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
        
        events = get_events_by_creator_in_range(
            test_db,
            test_user.telegram_id,
            date(2026, 1, 10),
            date(2026, 1, 15),
        )
        
        assert len(events) == 2
        assert all(e.title in ["Событие начало", "Событие конец"] for e in events)

