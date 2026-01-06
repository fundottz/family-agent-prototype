"""Telegram бот для семейного планировщика."""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from agno.agent import Agent

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    # Проверяем наличие сообщения
    if not update.message:
        return
    
    agent: Agent = context.bot_data.get("agent")
    
    if not agent:
        await update.message.reply_text("❌ Ошибка: агент не инициализирован")
        return
    
    welcome_message = """Привет! Я твой семейный планировщик.

Я помогу тебе:
• Запоминать планы и события
• Согласовывать расписание с партнером
• Находить свободное время
• Напоминать о важных делах

Просто напиши мне, что нужно запланировать, например:
"В субботу в 10 секция у сына"

Или спроси:
"Что у нас сегодня?" """
    
    await update.message.reply_text(welcome_message)


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Обработчик текстовых сообщений.
    Передает сообщение агенту и отправляет ответ пользователю.
    """
    # Проверяем наличие сообщения и чата
    if not update.message or not update.message.chat:
        return
    
    # Проверяем, что это личный чат (не группа)
    if update.message.chat.type != "private":
        return
    
    agent: Agent = context.bot_data.get("agent")
    
    if not agent:
        await update.message.reply_text("❌ Ошибка: агент не инициализирован")
        return
    
    # Проверяем наличие текста сообщения
    if not update.message.text:
        await update.message.reply_text("Извини, я понимаю только текстовые сообщения.")
        return
    
    user_message = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Пользователь"
    
    logger.info(f"Сообщение от {user_name} (ID: {user_id}): {user_message}")
    
    try:
        # Передаем сообщение агенту
        # Используем user_id как идентификатор для истории диалога
        # agent.run - синхронный метод, но в async функции это нормально
        response = agent.run(
            user_message,
            user_id=str(user_id),
        )
        
        # Проверяем, что ответ получен
        if not response or not hasattr(response, 'content'):
            await update.message.reply_text("Извини, не получилось обработать запрос.")
            return
        
        # Отправляем ответ пользователю
        await update.message.reply_text(response.content)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        await update.message.reply_text(
            "Извини, произошла ошибка. Попробуй еще раз."
        )


async def error_handler(
    update: Optional[Update], context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик ошибок."""
    logger.error(f"Ошибка: {context.error}", exc_info=True)


def run_bot(agent: Agent) -> None:
    """
    Запускает Telegram бота.
    
    Args:
        agent: Экземпляр Agno агента для обработки сообщений
    """
    # Получаем токен бота из переменных окружения
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in .env file")
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    
    # Сохраняем агента в bot_data для доступа из handlers
    application.bot_data["agent"] = agent
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    # run_polling() сам управляет event loop, поэтому вызываем напрямую
    logger.info("Бот запущен. Ожидание сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Для тестирования бота отдельно
    import asyncio
    from main import create_family_planner_agent
    
    async def test():
        agent = create_family_planner_agent()
        await run_bot(agent)
    
    asyncio.run(test())

