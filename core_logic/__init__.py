"""Core business logic - framework-agnostic pure Python functions."""

from .schemas import (
    User,
    CalendarEvent,
    EventStatus,
    EventCategory,
    ParsedEvent,
    AvailabilityResult,
    ConflictInfo,
    ScheduleResult,
    UpdateResult,
)

from .database import (
    init_database,
    create_user,
    get_user_by_telegram_id,
    update_user,
    create_event,
    get_event_by_id,
    get_events_by_user,
    get_conflicting_events,
    update_event_status,
    mark_partner_notified,
    add_event_participant,
    get_event_participants,
)

__all__ = [
    # Schemas
    "User",
    "CalendarEvent",
    "EventStatus",
    "EventCategory",
    "ParsedEvent",
    "AvailabilityResult",
    "ConflictInfo",
    "ScheduleResult",
    "UpdateResult",
    # Database functions
    "init_database",
    "create_user",
    "get_user_by_telegram_id",
    "update_user",
    "create_event",
    "get_event_by_id",
    "get_events_by_user",
    "get_conflicting_events",
    "update_event_status",
    "mark_partner_notified",
    "add_event_participant",
    "get_event_participants",
]