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

# Логирование уже настроено в main.py, просто получаем logger
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
    telegram_user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Пользователь"
    
    logger.info(f"Сообщение от {user_name} (ID: {telegram_user_id}): {user_message}")
    
    # Показываем пользователю, что бот обрабатывает сообщение
    processing_message = await update.message.reply_text("Обрабатываю...")
    
    try:
        # Передаем сообщение агенту
        # Используем async метод arun() для работы в async контексте
        # Для изоляции сессий используем:
        # - user_id: идентификатор пользователя в системе (telegram_id)
        # - session_id: идентификатор сессии (для Telegram - один чат = одна сессия на пользователя)
        # Используем telegram_id как для user_id, так и для session_id,
        # чтобы каждый пользователь имел свою отдельную сессию
        user_id_str = str(telegram_user_id)
        session_id = f"telegram_{telegram_user_id}"
        
        logger.info(f"Вызываю agent.arun() для пользователя {user_id_str}, сессия {session_id}")
        response = await agent.arun(
            user_message,
            user_id=user_id_str,
            session_id=session_id,
        )
        
        logger.debug(f"Получен ответ от агента: {response}")
        
        # Проверяем, что ответ получен
        if not response:
            logger.error("Агент вернул None")
            await processing_message.edit_text("Извини, не получилось обработать запрос. Попробуй еще раз.")
            return
        
        if not hasattr(response, 'content'):
            logger.error(f"Ответ не имеет атрибута content: {response}")
            await processing_message.edit_text("Извини, не получилось обработать запрос. Попробуй еще раз.")
            return
        
        # Проверяем, что контент не пустой
        if not response.content or not response.content.strip():
            logger.warning("Агент вернул пустой ответ")
            await processing_message.edit_text("Извини, не получилось сформировать ответ. Попробуй переформулировать запрос.")
            return
        
        logger.info(f"Отправляю ответ пользователю: {response.content[:100]}...")
        # Удаляем сообщение "Обрабатываю..." и отправляем ответ
        try:
            await processing_message.delete()
        except Exception:
            pass  # Игнорируем ошибки при удалении
        
        # Отправляем ответ пользователю
        await update.message.reply_text(response.content)
        logger.info("Ответ успешно отправлен")
        
    except ValueError as e:
        # Ошибки валидации - показываем понятное сообщение
        logger.warning(f"Ошибка валидации: {e}")
        await processing_message.edit_text(f"Извини, не могу обработать запрос: {str(e)}")
    except Exception as e:
        # Общие ошибки - логируем полностью, пользователю показываем безопасное сообщение
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        error_type = type(e).__name__
        await processing_message.edit_text(
            f"Извини, произошла ошибка при обработке запроса. "
            f"Попробуй еще раз или обратись к администратору. "
            f"(Ошибка: {error_type})"
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
    print("✅ Бот запущен и готов к работе!")
    print("💬 Напиши боту в Telegram, чтобы начать общение")
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Игнорируем старые обновления при запуске
        )
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
        print("\n🛑 Остановка бота...")
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Для тестирования бота отдельно
    import asyncio
    from main import create_family_planner_agent
    
    async def test():
        agent = create_family_planner_agent()
        await run_bot(agent)
    
    asyncio.run(test())

