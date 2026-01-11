"""Тесты для memory_utils.py - функции работы с памятью и изоляцией между семьями."""

import os
import pytest
from unittest.mock import patch, MagicMock
from core_logic.memory_utils import get_family_id, get_user_and_family_info
from core_logic.database import init_database, create_user, get_user_by_telegram_id
from core_logic.schemas import User


class TestGetFamilyId:
    """Тесты для функции get_family_id()."""

    def test_family_id_with_partner(self):
        """AC1: Тест: вычисление family_id для пары пользователей."""
        # Проверяем, что оба партнера получают одинаковый family_id
        family_id_1 = get_family_id(123, 456)
        family_id_2 = get_family_id(456, 123)
        
        assert family_id_1 == "family_123_456"
        assert family_id_2 == "family_123_456"
        assert family_id_1 == family_id_2

    def test_family_id_without_partner(self):
        """AC2: Тест: вычисление family_id без партнера."""
        family_id = get_family_id(123, None)
        assert family_id == "family_123"

    def test_family_id_with_zero_partner(self):
        """Тест: вычисление family_id с partner_telegram_id=0 (тоже считается как отсутствие партнера)."""
        family_id = get_family_id(123, 0)
        assert family_id == "family_123"

    def test_family_id_different_order(self):
        """Тест: проверка одинакового результата независимо от порядка вызова."""
        # Когда telegram_id больше partner_telegram_id
        family_id_1 = get_family_id(456, 123)
        # Когда telegram_id меньше partner_telegram_id
        family_id_2 = get_family_id(123, 456)
        
        assert family_id_1 == family_id_2 == "family_123_456"

    def test_family_id_edge_case_large_numbers(self):
        """Тест: edge case с большими числами."""
        family_id = get_family_id(999999, 111111)
        assert family_id == "family_111111_999999"

    def test_family_id_same_ids(self):
        """Тест: edge case когда telegram_id и partner_telegram_id одинаковые (не должно происходить, но проверим)."""
        family_id = get_family_id(123, 123)
        assert family_id == "family_123_123"


@pytest.fixture
def test_db():
    """Создает тестовую БД и возвращает путь к ней."""
    test_db_file = "test_memory_family_calendar.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)
    init_database(test_db_file)
    yield test_db_file
    if os.path.exists(test_db_file):
        os.remove(test_db_file)


@pytest.fixture
def test_user_with_partner(test_db):
    """Создает тестового пользователя с партнером."""
    user1 = User(
        telegram_id=123,
        name="Пользователь 1",
        partner_telegram_id=456,
    )
    user2 = User(
        telegram_id=456,
        name="Пользователь 2",
        partner_telegram_id=123,
    )
    create_user(test_db, user1)
    create_user(test_db, user2)
    return user1


@pytest.fixture
def test_user_without_partner(test_db):
    """Создает тестового пользователя без партнера."""
    user = User(
        telegram_id=789,
        name="Пользователь без партнера",
        partner_telegram_id=None,
    )
    create_user(test_db, user)
    return user


class TestGetUserAndFamilyInfo:
    """Тесты для функции get_user_and_family_info()."""

    def test_user_with_partner(self, test_db, test_user_with_partner):
        """AC3: Тест: получение информации о пользователе с партнером."""
        user, family_id = get_user_and_family_info(test_db, 123)
        
        assert user is not None
        assert user.telegram_id == 123
        assert user.name == "Пользователь 1"
        assert user.partner_telegram_id == 456
        assert family_id == "family_123_456"

    def test_user_without_partner(self, test_db, test_user_without_partner):
        """AC11: Тест: получение информации о пользователе без партнера."""
        user, family_id = get_user_and_family_info(test_db, 789)
        
        assert user is not None
        assert user.telegram_id == 789
        assert user.name == "Пользователь без партнера"
        assert user.partner_telegram_id is None
        assert family_id == "family_789"

    def test_user_not_found(self, test_db):
        """AC4: Тест: пользователь не найден в БД."""
        user, family_id = get_user_and_family_info(test_db, 999)
        
        assert user is None
        assert family_id is None

    def test_family_id_consistency_both_partners(self, test_db, test_user_with_partner):
        """Тест: оба партнера получают одинаковый family_id."""
        user1, family_id_1 = get_user_and_family_info(test_db, 123)
        user2, family_id_2 = get_user_and_family_info(test_db, 456)
        
        assert user1 is not None
        assert user2 is not None
        assert family_id_1 == "family_123_456"
        assert family_id_2 == "family_123_456"
        assert family_id_1 == family_id_2

    def test_error_handling_database_error(self, test_db):
        """AC12: Тест: обработка ошибки БД при получении пользователя."""
        # Мокируем get_user_by_telegram_id чтобы выбросить исключение
        with patch('core_logic.memory_utils.get_user_by_telegram_id') as mock_get_user:
            mock_get_user.side_effect = Exception("Database connection error")
            
            # Функция должна вернуть (None, None) без исключения
            user, family_id = get_user_and_family_info(test_db, 123)
            
            assert user is None
            assert family_id is None

    def test_error_handling_database_connection_failure(self, test_db):
        """Тест: обработка ошибки подключения к БД."""
        # Используем несуществующий файл БД (но функция должна обработать ошибку)
        with patch('core_logic.memory_utils.get_user_by_telegram_id') as mock_get_user:
            mock_get_user.side_effect = IOError("Database file not found")
            
            user, family_id = get_user_and_family_info(test_db, 123)
            
            assert user is None
            assert family_id is None

    def test_family_id_with_partner_zero(self, test_db):
        """Тест: функция get_family_id обрабатывает partner_telegram_id=0 как отсутствие партнера."""
        # Примечание: Pydantic не позволяет создать User с partner_telegram_id=0,
        # но функция get_family_id обрабатывает этот случай для защиты
        # Тестируем напрямую функцию get_family_id
        family_id = get_family_id(111, 0)
        assert family_id == "family_111"
        
        # В реальности partner_telegram_id будет None, а не 0
        user = User(
            telegram_id=111,
            name="Пользователь без партнера",
            partner_telegram_id=None,
        )
        create_user(test_db, user)
        
        retrieved_user, family_id_retrieved = get_user_and_family_info(test_db, 111)
        
        assert retrieved_user is not None
        assert family_id_retrieved == "family_111"

    def test_multiple_families_isolation(self, test_db):
        """Тест: изоляция между разными семьями (AC9 частично)."""
        # Семья A: пользователи 123 и 456
        user_a1 = User(telegram_id=123, name="Семья A - Пользователь 1", partner_telegram_id=456)
        user_a2 = User(telegram_id=456, name="Семья A - Пользователь 2", partner_telegram_id=123)
        
        # Семья B: пользователи 789 и 101
        user_b1 = User(telegram_id=789, name="Семья B - Пользователь 1", partner_telegram_id=101)
        user_b2 = User(telegram_id=101, name="Семья B - Пользователь 2", partner_telegram_id=789)
        
        create_user(test_db, user_a1)
        create_user(test_db, user_a2)
        create_user(test_db, user_b1)
        create_user(test_db, user_b2)
        
        # Получаем family_id для обеих семей
        _, family_id_a1 = get_user_and_family_info(test_db, 123)
        _, family_id_a2 = get_user_and_family_info(test_db, 456)
        _, family_id_b1 = get_user_and_family_info(test_db, 789)
        _, family_id_b2 = get_user_and_family_info(test_db, 101)
        
        # Проверяем, что family_id разные для разных семей
        assert family_id_a1 == "family_123_456"
        assert family_id_a2 == "family_123_456"
        assert family_id_b1 == "family_101_789"
        assert family_id_b2 == "family_101_789"
        
        # Проверяем изоляцию
        assert family_id_a1 != family_id_b1
        assert family_id_a2 != family_id_b2
