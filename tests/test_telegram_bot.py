"""Тесты для telegram_bot.py."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes
from telegram_bot import start_command, handle_message, run_bot, error_handler


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
    mock_update.message.chat.type = "private"
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что агент вызван
    mock_agent.run.assert_called_once()
    assert mock_agent.run.call_args[0][0] == "Привет"
    
    # Проверяем, что ответ отправлен
    mock_update.message.reply_text.assert_called_once()
    assert mock_update.message.reply_text.call_args[0][0] == "Тестовый ответ"


@pytest.mark.asyncio
async def test_handle_message_group_chat(mock_update, mock_context, mock_agent):
    """Тест: сообщения в группе должны игнорироваться."""
    mock_context.bot_data["agent"] = mock_agent
    mock_update.message.chat.type = "group"
    
    await handle_message(mock_update, mock_context)
    
    # Агент не должен быть вызван
    mock_agent.run.assert_not_called()
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
    mock_agent.run.side_effect = Exception("Test error")
    
    await handle_message(mock_update, mock_context)
    
    # Проверяем, что ошибка обработана и отправлен ответ пользователю
    mock_update.message.reply_text.assert_called_once()
    assert "ошибка" in mock_update.message.reply_text.call_args[0][0].lower()


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

