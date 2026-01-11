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
    mark_partner_notified,
    add_event_participant,
)

from .memory_utils import (
    get_family_id,
    get_user_and_family_info,
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
    "mark_partner_notified",
    "add_event_participant",
    # Memory utilities
    "get_family_id",
    "get_user_and_family_info",
]