"""Telegram бот для семейного планировщика."""

import os
import logging
from datetime import datetime
from typing import Optional, Any, Callable, List
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
from agents_wrappers import _set_current_telegram_id, _reset_current_telegram_id
from core_logic.schemas import CalendarEvent
from core_logic.notification_service import NotificationService, NotificationType, get_notification_service
from core_logic.calendar_tools import set_notification_callback

load_dotenv()

# Логирование уже настроено в main.py, просто получаем logger
logger = logging.getLogger(__name__)

# Bot instance теперь управляется через NotificationService


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

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает контекст диалога для пользователя (новая session_id версия)."""
    if not update.message or not update.effective_user:
        return
    telegram_user_id = update.effective_user.id
    session_versions = context.bot_data.setdefault("session_versions", {})
    current = session_versions.get(telegram_user_id, 2)
    session_versions[telegram_user_id] = current + 1
    await update.message.reply_text("Ок, сбросил контекст. Продолжай — я начну как с чистого листа.")


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

    # Устанавливаем текущий Telegram ID для tools (контекст на текущую asyncio-задачу)
    token = _set_current_telegram_id(int(telegram_user_id))
    
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
        session_versions = context.bot_data.setdefault("session_versions", {})
        version = session_versions.get(telegram_user_id, 2)  # v2 отключает старую историю с просьбами ID
        session_id = f"telegram_{telegram_user_id}_v{version}"

        # Усиливаем контекст против "попроси Telegram ID" из старой истории
        context_prefix = (
            "ВАЖНО: мой Telegram ID уже известен системе и доступен в контексте. "
            "Никогда не проси Telegram ID. Если нужен ID для инструмента — не передавай его явно. "
            "Для текущей даты используй get_current_datetime."
        )
        agent_input = f"{context_prefix}\n\nСообщение пользователя: {user_message}"
        
        logger.info(f"Вызываю agent.arun() для пользователя {user_id_str}, сессия {session_id}")
        response = await agent.arun(
            agent_input,
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
    finally:
        # Сбрасываем контекст tg id для текущей asyncio-задачи
        try:
            _reset_current_telegram_id(token)
        except Exception:
            pass


async def error_handler(
    update: Optional[Update], context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик ошибок."""
    logger.error(f"Ошибка: {context.error}", exc_info=True)


# УСТАРЕЛО: Используйте NotificationService напрямую
# Оставляем функции для обратной совместимости, но они делегируют в NotificationService

async def notify_partner_about_event(
    event: CalendarEvent,
    creator_telegram_id: int,
) -> bool:
    """
    Уведомляет партнера о новом событии.
    
    УСТАРЕЛО: Используйте NotificationService.notify_event_created() напрямую.
    
    Args:
        event: Созданное событие
        creator_telegram_id: Telegram ID создателя события
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    notification_service = get_notification_service()
    return await notification_service.notify_event_created(event, creator_telegram_id)


async def notify_partner_about_event_changes(
    events: List[CalendarEvent],
    creator_telegram_id: int,
    action: str = "изменил(а)",
) -> bool:
    """
    Универсальная функция для уведомления партнера об изменениях в событиях.
    
    УСТАРЕЛО: Используйте NotificationService.notify_events_updated() напрямую.
    
    Args:
        events: Список событий, которые были изменены/отменены
        creator_telegram_id: Telegram ID создателя событий
        action: Действие, которое было выполнено (игнорируется, используется тип из NotificationType)
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    notification_service = get_notification_service()
    return await notification_service.notify_events_updated(events, creator_telegram_id)


async def notify_partner_about_event_cancellation(
    events: List[CalendarEvent],
    creator_telegram_id: int,
) -> bool:
    """
    Уведомляет партнера об отмене событий.
    
    УСТАРЕЛО: Используйте NotificationService.notify_events_cancelled() напрямую.
    
    Args:
        events: Список отмененных событий
        creator_telegram_id: Telegram ID создателя событий
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    notification_service = get_notification_service()
    return await notification_service.notify_events_cancelled(events, creator_telegram_id)


def create_notification_callback() -> Optional[Callable[[List[CalendarEvent], int, NotificationType], None]]:
    """
    Создает единый callback для всех типов уведомлений.
    Возвращает синхронную функцию, которая вызывает async методы NotificationService.
    
    Returns:
        Callback функция или None, если bot не установлен
    """
    import asyncio
    
    async def _send_notification(events: List[CalendarEvent], creator_telegram_id: int, notification_type: NotificationType) -> None:
        """Внутренняя async функция для отправки уведомления."""
        notification_service = get_notification_service()
        
        if notification_type == NotificationType.CREATED:
            if events:
                await notification_service.notify_event_created(events[0], creator_telegram_id)
        elif notification_type == NotificationType.UPDATED:
            await notification_service.notify_events_updated(events, creator_telegram_id)
        elif notification_type == NotificationType.CANCELLED:
            await notification_service.notify_events_cancelled(events, creator_telegram_id)
        else:
            logger.warning(f"Неизвестный тип уведомления: {notification_type}")
    
    def notification_callback(events: List[CalendarEvent], creator_telegram_id: int, notification_type: NotificationType) -> None:
        """
        Синхронная обертка для async методов NotificationService.
        """
        try:
            # Проверяем, есть ли активный event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен, создаем задачу (fire and forget)
                asyncio.create_task(_send_notification(events, creator_telegram_id, notification_type))
            except RuntimeError:
                # Если нет активного event loop, создаем новый
                asyncio.run(_send_notification(events, creator_telegram_id, notification_type))
        except Exception as e:
            logger.error(f"Ошибка в callback уведомления: {e}", exc_info=True)
    
    return notification_callback


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
    
    # Настраиваем NotificationService
    notification_service = get_notification_service()
    notification_service.set_bot(application.bot)
    
    # Создаем и регистрируем единый callback для всех типов уведомлений
    notification_callback = create_notification_callback()
    set_notification_callback(notification_callback)
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reset", reset_command))
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

