"""Утилиты для работы с памятью (Memory) и изоляцией между семьями."""

import logging
from typing import Optional, Tuple
from .schemas import User
from .database import get_user_by_telegram_id

logger = logging.getLogger(__name__)


def get_family_id(telegram_id: int, partner_telegram_id: Optional[int]) -> str:
    """
    Вычисляет family_id на основе telegram_id и partner_telegram_id.
    
    Формат: family_{min_id}_{max_id} для пары, family_{telegram_id} для одного пользователя.
    Это обеспечивает одинаковый family_id у обоих партнеров независимо от порядка вызова.
    
    Args:
        telegram_id: Telegram ID пользователя
        partner_telegram_id: Telegram ID партнера (может быть None)
    
    Returns:
        Строка family_id в формате "family_{min_id}_{max_id}" или "family_{telegram_id}"
    
    Examples:
        >>> get_family_id(123, 456)
        'family_123_456'
        >>> get_family_id(456, 123)
        'family_123_456'
        >>> get_family_id(123, None)
        'family_123'
    """
    if partner_telegram_id is None or partner_telegram_id == 0:
        return f"family_{telegram_id}"
    
    # Используем min и max для обеспечения одинакового family_id у обоих партнеров
    min_id = min(telegram_id, partner_telegram_id)
    max_id = max(telegram_id, partner_telegram_id)
    return f"family_{min_id}_{max_id}"


def get_user_and_family_info(db_file: str, telegram_id: int) -> Tuple[Optional[User], Optional[str]]:
    """
    Получает информацию о пользователе и вычисляет family_id.
    
    Args:
        db_file: Путь к файлу базы данных
        telegram_id: Telegram ID пользователя
    
    Returns:
        Кортеж (User, family_id):
        - Если пользователь найден: (User(...), "family_...")
        - Если пользователь не найден или произошла ошибка: (None, None)
    
    Examples:
        >>> user, family_id = get_user_and_family_info("data/family_calendar.db", 123)
        >>> if user:
        ...     print(f"User: {user.name}, Family ID: {family_id}")
    """
    try:
        user = get_user_by_telegram_id(db_file, telegram_id)
        if user is None:
            logger.debug(f"Пользователь с telegram_id={telegram_id} не найден в БД")
            return (None, None)
        
        # Вычисляем family_id на основе partner_telegram_id
        partner_id = user.partner_telegram_id if user.partner_telegram_id else None
        family_id = get_family_id(telegram_id, partner_id)
        
        logger.debug(f"Пользователь {user.name} (telegram_id={telegram_id}): family_id={family_id}")
        return (user, family_id)
    
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе telegram_id={telegram_id}: {e}", exc_info=True)
        return (None, None)
