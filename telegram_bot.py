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
from core_logic.database import get_user_by_telegram_id, mark_partner_notified
from core_logic.calendar_tools import DB_FILE, set_notify_partner_callback, set_notify_partner_cancellation_callback

load_dotenv()

# Логирование уже настроено в main.py, просто получаем logger
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения bot instance для отправки уведомлений
_notification_bot: Optional[Any] = None


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


async def notify_partner_about_event(
    event: CalendarEvent,
    creator_telegram_id: int,
) -> bool:
    """
    Уведомляет партнера о новом событии.
    
    Args:
        event: Созданное событие
        creator_telegram_id: Telegram ID создателя события
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    global _notification_bot
    
    if _notification_bot is None:
        logger.warning("Bot instance не установлен, уведомление не отправлено")
        return False
    
    try:
        # Получаем информацию о создателе
        creator = get_user_by_telegram_id(DB_FILE, creator_telegram_id)
        if not creator:
            logger.warning(f"Пользователь с telegram_id={creator_telegram_id} не найден")
            return False
        
        # Проверяем наличие партнера
        if not creator.partner_telegram_id:
            logger.info(f"У пользователя {creator.name} нет партнера, уведомление не требуется")
            return False
        
        # Формируем сообщение в спокойном тоне
        # Используем имя создателя
        creator_name = creator.name
        
        # Форматируем дату и время
        event_datetime_str = _format_event_datetime(event.datetime)
        
        # Формируем сообщение
        message = f"{creator_name} занял(а) {event_datetime_str}: {event.title}"
        
        # Отправляем сообщение партнеру
        try:
            await _notification_bot.send_message(
                chat_id=creator.partner_telegram_id,
                text=message
            )
            logger.info(f"Уведомление отправлено партнеру {creator.partner_telegram_id} о событии {event.id}")
            
            # Устанавливаем флаг уведомления в БД
            if event.id:
                mark_partner_notified(DB_FILE, event.id)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления партнеру: {e}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при уведомлении партнера: {e}", exc_info=True)
        return False


def _format_event_datetime(event_datetime: datetime) -> str:
    """
    Форматирует дату и время события для уведомлений.
    
    Args:
        event_datetime: Дата и время события
    
    Returns:
        Строка вида "понедельник 10:00"
    """
    weekday_names = [
        "понедельник", "вторник", "среда", "четверг",
        "пятница", "суббота", "воскресенье"
    ]
    weekday = weekday_names[event_datetime.weekday()]
    time_str = event_datetime.strftime("%H:%M")
    return f"{weekday} {time_str}"


async def notify_partner_about_event_changes(
    events: List[CalendarEvent],
    creator_telegram_id: int,
    action: str = "изменил(а)",
) -> bool:
    """
    Универсальная функция для уведомления партнера об изменениях в событиях.
    
    Args:
        events: Список событий, которые были изменены/отменены
        creator_telegram_id: Telegram ID создателя событий
        action: Действие, которое было выполнено (например, "отменил(а)", "изменил(а)")
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    global _notification_bot
    
    if _notification_bot is None:
        logger.warning("Bot instance не установлен, уведомление не отправлено")
        return False
    
    if not events:
        return False
    
    try:
        # Получаем информацию о создателе
        creator = get_user_by_telegram_id(DB_FILE, creator_telegram_id)
        if not creator:
            logger.warning(f"Пользователь с telegram_id={creator_telegram_id} не найден")
            return False
        
        # Проверяем наличие партнера
        if not creator.partner_telegram_id:
            logger.info(f"У пользователя {creator.name} нет партнера, уведомление не требуется")
            return False
        
        # Формируем сообщение в спокойном тоне
        creator_name = creator.name
        
        if len(events) == 1:
            # Одно событие
            event = events[0]
            event_datetime_str = _format_event_datetime(event.datetime)
            message = f"{creator_name} {action} {event_datetime_str}: {event.title}"
        else:
            # Несколько событий
            event_list = []
            for event in events[:5]:  # Ограничиваем до 5 событий
                event_datetime_str = _format_event_datetime(event.datetime)
                event_list.append(f"{event_datetime_str}: {event.title}")
            
            if len(events) > 5:
                event_list.append(f"... и еще {len(events) - 5}")
            
            events_text = "\n".join(event_list)
            message = f"{creator_name} {action} событий:\n{events_text}"
        
        # Отправляем сообщение партнеру
        try:
            await _notification_bot.send_message(
                chat_id=creator.partner_telegram_id,
                text=message
            )
            logger.info(f"Уведомление отправлено партнеру {creator.partner_telegram_id} о {len(events)} событии(ях) ({action})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления партнеру: {e}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при уведомлении партнера: {e}", exc_info=True)
        return False


async def notify_partner_about_event_cancellation(
    events: List[CalendarEvent],
    creator_telegram_id: int,
) -> bool:
    """
    Уведомляет партнера об отмене событий.
    
    Использует унифицированную функцию notify_partner_about_event_changes.
    
    Args:
        events: Список отмененных событий
        creator_telegram_id: Telegram ID создателя событий
    
    Returns:
        True если уведомление отправлено успешно, False в противном случае
    """
    return await notify_partner_about_event_changes(events, creator_telegram_id, action="отменил(а)")


def set_notification_bot(bot: Any) -> None:
    """
    Устанавливает bot instance для отправки уведомлений.
    
    Args:
        bot: Экземпляр Telegram Bot для отправки сообщений
    """
    global _notification_bot
    _notification_bot = bot
    logger.info("Bot instance установлен для уведомлений")


def create_notify_callback() -> Optional[Callable[[CalendarEvent, int], None]]:
    """
    Создает callback функцию для уведомления партнера.
    Возвращает синхронную функцию, которая вызывает async notify_partner_about_event.
    
    Returns:
        Callback функция или None, если bot не установлен
    """
    import asyncio
    
    def notify_callback(event: CalendarEvent, creator_telegram_id: int) -> None:
        """
        Синхронная обертка для async notify_partner_about_event.
        """
        try:
            # Проверяем, есть ли активный event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен, создаем задачу (fire and forget)
                asyncio.create_task(notify_partner_about_event(event, creator_telegram_id))
            except RuntimeError:
                # Если нет активного event loop, создаем новый
                asyncio.run(notify_partner_about_event(event, creator_telegram_id))
        except Exception as e:
            logger.error(f"Ошибка в callback уведомления: {e}", exc_info=True)
    
    return notify_callback


def create_notify_cancellation_callback() -> Optional[Callable[[List[CalendarEvent], int], None]]:
    """
    Создает callback функцию для уведомления партнера об отмене событий.
    Возвращает синхронную функцию, которая вызывает async notify_partner_about_event_cancellation.
    
    Returns:
        Callback функция или None, если bot не установлен
    """
    import asyncio
    
    def notify_cancellation_callback(events: List[CalendarEvent], creator_telegram_id: int) -> None:
        """
        Синхронная обертка для async notify_partner_about_event_cancellation.
        """
        try:
            # Проверяем, есть ли активный event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен, создаем задачу (fire and forget)
                asyncio.create_task(notify_partner_about_event_cancellation(events, creator_telegram_id))
            except RuntimeError:
                # Если нет активного event loop, создаем новый
                asyncio.run(notify_partner_about_event_cancellation(events, creator_telegram_id))
        except Exception as e:
            logger.error(f"Ошибка в callback уведомления об отмене: {e}", exc_info=True)
    
    return notify_cancellation_callback


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
    
    # Устанавливаем bot instance для уведомлений
    set_notification_bot(application.bot)
    
    # Регистрируем callback для уведомлений партнера
    notify_callback = create_notify_callback()
    set_notify_partner_callback(notify_callback)
    
    # Регистрируем callback для уведомлений об отмене
    notify_cancellation_callback = create_notify_cancellation_callback()
    set_notify_partner_cancellation_callback(notify_cancellation_callback)
    
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

