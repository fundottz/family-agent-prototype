"""Тесты для telegram_bot.py."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, Chat, User, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram_bot import (
    start_command, handle_message, run_bot, error_handler,
    notify_partner_about_event, set_notification_bot, create_notify_callback,
    create_quick_query_keyboard, keyboard_command
)
from core_logic.schemas import CalendarEvent, EventStatus, EventCategory
from core_logic.database import init_database, create_user, get_user_by_telegram_id
from datetime import datetime
import pytz


@pytest.fixture
def mock_update():
    """Создает mock Update для тестов."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.chat = MagicMock(spec=Chat)
    update.message.chat.type = "private"
    update.message.text = "Привет"
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.first_name = "TestUser"
    return update


@pytest.fixture
def mock_context():
    """Создает mock Context для тестов."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {}
    return context


@pytest.fixture
def mock_agent():
    """Создает mock Agent для тестов."""
    agent = MagicMock()
    agent.run = MagicMock(return_value=MagicMock(content="Тестовый ответ"))
    return agent


@pytest.mark.asyncio
async def test_start_command_with_agent(mock_update, mock_context, mock_agent):
    """Тест: команда /start с инициализированным агентом."""
    mock_context.bot_data["agent"] = mock_agent
    
    await start_command(mock_update, mock_context)
    
    # Проверяем, что ответ отправлен
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "семейный планировщик" in call_args.lower()


@pytest.mark.asyncio
async def test_start_command_without_agent(mock_update, mock_context):
    """Тест: команда /start без агента должна показать ошибку."""
    mock_context.bot_data = {}
    
    await start_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    assert "ошибка" in mock_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_message_private_chat(mock_update, mock_context, mock_agent):
    """Тест: обработка сообщения в личном чате."""
    mock_context.bot_data["agent"] = mock_agent
    mock_context.bot_data.setdefault("session_versions", {})
    mock_update.message.chat.type = "private"
    
    # Мокаем arun (используется в handle_message)
    mock_agent.arun = AsyncMock(return_value=MagicMock(content="Тестовый ответ"))
    
    # Мокаем reply_text для processing_message
    mock_processing_message = MagicMock()
    mock_processing_message.delete = AsyncMock()
    mock_update.message.reply_text = AsyncMock(return_value=mock_processing_message)
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что агент вызван
    mock_agent.arun.assert_called_once()
    
    # Проверяем, что ответ отправлен
    # reply_text вызывается дважды: для "Обрабатываю..." и для ответа
    assert mock_update.message.reply_text.call_count >= 1
    
    # Проверяем последний вызов (ответ)
    last_call = mock_update.message.reply_text.call_args_list[-1]
    assert last_call[0][0] == "Тестовый ответ"


@pytest.mark.asyncio
async def test_handle_message_group_chat(mock_update, mock_context, mock_agent):
    """Тест: сообщения в группе должны игнорироваться."""
    mock_context.bot_data["agent"] = mock_agent
    mock_update.message.chat.type = "group"
    
    # Мокаем arun
    mock_agent.arun = AsyncMock()
    
    await handle_message(mock_update, mock_context)
    
    # Агент не должен быть вызван
    mock_agent.arun.assert_not_called()
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_without_agent(mock_update, mock_context):
    """Тест: обработка сообщения без агента должна показать ошибку."""
    mock_context.bot_data = {}
    
    await handle_message(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    assert "ошибка" in mock_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_message_agent_error(mock_update, mock_context, mock_agent):
    """Тест: обработка ошибки при вызове агента."""
    mock_context.bot_data["agent"] = mock_agent
    mock_context.bot_data.setdefault("session_versions", {})
    mock_update.message.chat.type = "private"
    
    # Мокаем arun с ошибкой
    mock_agent.arun = AsyncMock(side_effect=Exception("Test error"))
    
    # Мокаем reply_text для processing_message
    mock_processing_message = MagicMock()
    mock_processing_message.delete = AsyncMock()
    mock_processing_message.edit_text = AsyncMock()
    mock_update.message.reply_text = AsyncMock(return_value=mock_processing_message)
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что ошибка обработана и отправлен ответ пользователю
    mock_processing_message.edit_text.assert_called_once()
    assert "ошибка" in mock_processing_message.edit_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_error_handler(mock_context):
    """Тест: обработчик ошибок."""
    mock_context.error = Exception("Test error")
    
    # error_handler не должен падать
    await error_handler(None, mock_context)
    
    # В реальности здесь проверялось бы логирование


@pytest.mark.asyncio
async def test_run_bot_missing_token(mock_agent):
    """Тест: запуск бота без токена должен вызвать ошибку."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            await run_bot(mock_agent)


@pytest.mark.asyncio
async def test_run_bot_with_token(mock_agent):
    """Тест: запуск бота с токеном (мок)."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"}):
        with patch('telegram_bot.Application') as mock_app_class:
            mock_app = MagicMock()
            mock_app.builder.return_value.token.return_value.build.return_value = mock_app
            mock_app.run_polling = AsyncMock()
            mock_app_class.builder.return_value.token.return_value.build.return_value = mock_app
            
            # Запускаем бота (будет работать до run_polling)
            try:
                await run_bot(mock_agent)
            except Exception:
                # run_polling будет работать бесконечно, поэтому прерываем
                pass
            
            # Проверяем, что агент сохранен в bot_data
            assert mock_app.bot_data["agent"] == mock_agent


@pytest.mark.asyncio
async def test_notify_partner_about_event_success():
    """Тест: успешная отправка уведомления партнеру."""
    # Настраиваем тестовую БД
    test_db = "test_family_calendar.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    init_database(test_db)
    
    # Создаем пользователей
    from core_logic.schemas import User
    creator = User(telegram_id=111, name="Муж", partner_telegram_id=222)
    partner = User(telegram_id=222, name="Жена", partner_telegram_id=111)
    create_user(test_db, creator)
    create_user(test_db, partner)
    
    # Создаем событие
    event = CalendarEvent(
        id=1,
        title="секция у сына",
        datetime=datetime(2026, 1, 10, 10, 0, tzinfo=pytz.timezone("Europe/Moscow")),
        duration_minutes=60,
        creator_telegram_id=111,
        status=EventStatus.PROPOSED,
        category=EventCategory.CHILDREN,
    )
    
    # Мокаем bot
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    set_notification_bot(mock_bot)
    
    # Вызываем функцию уведомления
    # Временно устанавливаем DB_FILE для теста
    import core_logic.calendar_tools
    original_db = core_logic.calendar_tools.DB_FILE
    core_logic.calendar_tools.DB_FILE = test_db
    
    try:
        result = await notify_partner_about_event(event, 111)
        
        # Проверяем, что уведомление отправлено
        assert result is True
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args[1]["chat_id"] == 222
        assert "секция у сына" in call_args[1]["text"]
    finally:
        core_logic.calendar_tools.DB_FILE = original_db
        if os.path.exists(test_db):
            os.remove(test_db)


@pytest.mark.asyncio
async def test_notify_partner_about_event_no_partner():
    """Тест: уведомление не отправляется, если у пользователя нет партнера."""
    test_db = "test_family_calendar.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    init_database(test_db)
    
    # Создаем пользователя без партнера
    from core_logic.schemas import User
    creator = User(telegram_id=111, name="Муж", partner_telegram_id=None)
    create_user(test_db, creator)
    
    event = CalendarEvent(
        id=1,
        title="секция у сына",
        datetime=datetime(2026, 1, 10, 10, 0, tzinfo=pytz.timezone("Europe/Moscow")),
        duration_minutes=60,
        creator_telegram_id=111,
        status=EventStatus.PROPOSED,
        category=EventCategory.CHILDREN,
    )
    
    mock_bot = AsyncMock()
    set_notification_bot(mock_bot)
    
    import core_logic.calendar_tools
    original_db = core_logic.calendar_tools.DB_FILE
    core_logic.calendar_tools.DB_FILE = test_db
    
    try:
        result = await notify_partner_about_event(event, 111)
        
        # Уведомление не должно быть отправлено
        assert result is True  # Функция возвращает True, но сообщение не отправлено
        mock_bot.send_message.assert_not_called()
    finally:
        core_logic.calendar_tools.DB_FILE = original_db
        if os.path.exists(test_db):
            os.remove(test_db)


@pytest.mark.asyncio
async def test_notify_partner_about_event_no_bot():
    """Тест: уведомление не отправляется, если bot не установлен."""
    set_notification_bot(None)
    
    event = CalendarEvent(
        id=1,
        title="секция у сына",
        datetime=datetime(2026, 1, 10, 10, 0, tzinfo=pytz.timezone("Europe/Moscow")),
        duration_minutes=60,
        creator_telegram_id=111,
        status=EventStatus.PROPOSED,
        category=EventCategory.CHILDREN,
    )
    
    result = await notify_partner_about_event(event, 111)
    
    # Должно вернуть False
    assert result is False


def test_create_quick_query_keyboard():
    """Тест: создание клавиатуры с быстрыми запросами."""
    keyboard = create_quick_query_keyboard()
    
    # Проверяем, что возвращается ReplyKeyboardMarkup
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    
    # Проверяем структуру клавиатуры
    assert keyboard.keyboard is not None
    assert len(keyboard.keyboard) == 2  # 2 ряда
    
    # Проверяем первый ряд (2 кнопки)
    assert len(keyboard.keyboard[0]) == 2
    assert keyboard.keyboard[0][0].text == "Планы на сегодня"
    assert keyboard.keyboard[0][1].text == "Планы на завтра"
    
    # Проверяем второй ряд (2 кнопки)
    assert len(keyboard.keyboard[1]) == 2
    assert keyboard.keyboard[1][0].text == "Планы на неделю"
    assert keyboard.keyboard[1][1].text == "Что на выходных"
    
    # Проверяем resize_keyboard
    assert keyboard.resize_keyboard is True


@pytest.mark.asyncio
async def test_keyboard_command(mock_update, mock_context):
    """Тест: команда /keyboard показывает клавиатуру."""
    await keyboard_command(mock_update, mock_context)
    
    # Проверяем, что ответ отправлен
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    assert "быстрый запрос" in call_args[0][0].lower()
    
    # Проверяем, что передана клавиатура
    assert "reply_markup" in call_args[1]
    assert isinstance(call_args[1]["reply_markup"], ReplyKeyboardMarkup)


@pytest.mark.asyncio
async def test_handle_message_preserves_keyboard(mock_update, mock_context, mock_agent):
    """Тест: handle_message сохраняет клавиатуру в ответах."""
    mock_context.bot_data["agent"] = mock_agent
    mock_context.bot_data.setdefault("session_versions", {})
    mock_update.message.chat.type = "private"
    
    # Мокаем arun вместо run (так как используется async версия)
    mock_agent.arun = AsyncMock(return_value=MagicMock(content="Тестовый ответ"))
    
    # Мокаем reply_text для processing_message
    mock_processing_message = MagicMock()
    mock_processing_message.delete = AsyncMock()
    mock_update.message.reply_text = AsyncMock(return_value=mock_processing_message)
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что ответ отправлен с клавиатурой
    # reply_text вызывается дважды: для "Обрабатываю..." и для ответа
    assert mock_update.message.reply_text.call_count >= 1
    
    # Проверяем последний вызов (ответ с клавиатурой)
    last_call = mock_update.message.reply_text.call_args_list[-1]
    assert "reply_markup" in last_call[1]
    assert isinstance(last_call[1]["reply_markup"], ReplyKeyboardMarkup)


@pytest.mark.asyncio
async def test_handle_message_keyboard_button(mock_update, mock_context, mock_agent):
    """Тест: обработка нажатия кнопки клавиатуры (текст отправляется как обычное сообщение)."""
    mock_context.bot_data["agent"] = mock_agent
    mock_context.bot_data.setdefault("session_versions", {})
    mock_update.message.chat.type = "private"
    mock_update.message.text = "Планы на сегодня"  # Текст с кнопки
    
    # Мокаем arun
    mock_agent.arun = AsyncMock(return_value=MagicMock(content="Сегодня у вас: секция в 10:00"))
    
    # Мокаем reply_text для processing_message
    mock_processing_message = MagicMock()
    mock_processing_message.delete = AsyncMock()
    mock_update.message.reply_text = AsyncMock(return_value=mock_processing_message)
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что агент получил правильный текст
    mock_agent.arun.assert_called_once()
    agent_input = mock_agent.arun.call_args[0][0]
    assert "Планы на сегодня" in agent_input

