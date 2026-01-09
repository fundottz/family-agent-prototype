"""Сервис для отправки уведомлений партнерам о событиях календаря."""

import logging
from enum import Enum
from typing import List, Optional, Callable, Any
from datetime import datetime

from .schemas import CalendarEvent
from .database import get_user_by_telegram_id, mark_partner_notified, DB_FILE

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Типы уведомлений о событиях."""
    CREATED = "created"
    UPDATED = "updated"
    CANCELLED = "cancelled"


class NotificationService:
    """Сервис для отправки уведомлений партнерам."""
    
    def __init__(self, bot: Optional[Any] = None):
        """
        Инициализирует сервис уведомлений.
        
        Args:
            bot: Экземпляр Telegram бота для отправки сообщений (опционально)
        """
        self._bot: Optional[Any] = bot
        self._notification_callback: Optional[Callable[[List[CalendarEvent], int, NotificationType], None]] = None
    
    def set_bot(self, bot: Any) -> None:
        """
        Устанавливает bot instance для отправки уведомлений.
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self._bot = bot
        logger.info("Bot instance установлен для NotificationService")
    
    def set_callback(self, callback: Optional[Callable[[List[CalendarEvent], int, NotificationType], None]]) -> None:
        """
        Устанавливает callback функцию для уведомлений.
        
        Callback будет вызываться для всех типов уведомлений.
        Сигнатура: callback(events: List[CalendarEvent], creator_telegram_id: int, notification_type: NotificationType)
        
        Args:
            callback: Функция callback или None для отключения
        """
        self._notification_callback = callback
        logger.info("Callback установлен для NotificationService")
    
    def _format_event_datetime(self, event_datetime: datetime) -> str:
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
    
    def _get_action_text(self, notification_type: NotificationType) -> str:
        """
        Возвращает текст действия для типа уведомления.
        
        Args:
            notification_type: Тип уведомления
        
        Returns:
            Текст действия (например, "занял(а)", "изменил(а)", "отменил(а)")
        """
        action_map = {
            NotificationType.CREATED: "занял(а)",
            NotificationType.UPDATED: "изменил(а)",
            NotificationType.CANCELLED: "отменил(а)",
        }
        return action_map.get(notification_type, "изменил(а)")
    
    def _format_message(self, events: List[CalendarEvent], creator_name: str, notification_type: NotificationType) -> str:
        """
        Форматирует сообщение для уведомления.
        
        Args:
            events: Список событий
            creator_name: Имя создателя
            notification_type: Тип уведомления
        
        Returns:
            Отформатированное сообщение
        """
        action = self._get_action_text(notification_type)
        
        if len(events) == 1:
            # Одно событие
            event = events[0]
            event_datetime_str = self._format_event_datetime(event.datetime)
            return f"{creator_name} {action} {event_datetime_str}: {event.title}"
        else:
            # Несколько событий
            event_list = []
            for event in events[:5]:  # Ограничиваем до 5 событий
                event_datetime_str = self._format_event_datetime(event.datetime)
                event_list.append(f"{event_datetime_str}: {event.title}")
            
            if len(events) > 5:
                event_list.append(f"... и еще {len(events) - 5}")
            
            events_text = "\n".join(event_list)
            return f"{creator_name} {action} событий:\n{events_text}"
    
    async def notify(
        self,
        events: List[CalendarEvent],
        creator_telegram_id: int,
        notification_type: NotificationType,
    ) -> bool:
        """
        Отправляет уведомление партнеру о событиях.
        
        Args:
            events: Список событий для уведомления
            creator_telegram_id: Telegram ID создателя событий
            notification_type: Тип уведомления
        
        Returns:
            True если уведомление отправлено успешно, False в противном случае
        """
        if not events:
            return False
        
        if self._bot is None:
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
            
            # Формируем сообщение
            message = self._format_message(events, creator.name, notification_type)
            
            # Отправляем сообщение партнеру
            try:
                await self._bot.send_message(
                    chat_id=creator.partner_telegram_id,
                    text=message
                )
                logger.info(
                    f"Уведомление отправлено партнеру {creator.partner_telegram_id} о {len(events)} "
                    f"событии(ях) ({notification_type.value})"
                )
                
                # Для созданных событий устанавливаем флаг уведомления в БД
                if notification_type == NotificationType.CREATED:
                    for event in events:
                        if event.id:
                            mark_partner_notified(DB_FILE, event.id)
                
                # Вызываем callback после успешной отправки
                if self._notification_callback:
                    try:
                        self._notification_callback(events, creator_telegram_id, notification_type)
                    except Exception as e:
                        logger.error(f"Ошибка в callback уведомления: {e}", exc_info=True)
                
                return True
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления партнеру: {e}", exc_info=True)
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при уведомлении партнера: {e}", exc_info=True)
            return False
    
    async def notify_event_created(self, event: CalendarEvent, creator_telegram_id: int) -> bool:
        """
        Уведомляет партнера о создании события.
        
        Args:
            event: Созданное событие
            creator_telegram_id: Telegram ID создателя события
        
        Returns:
            True если уведомление отправлено успешно, False в противном случае
        """
        return await self.notify([event], creator_telegram_id, NotificationType.CREATED)
    
    async def notify_events_updated(self, events: List[CalendarEvent], creator_telegram_id: int) -> bool:
        """
        Уведомляет партнера об изменении событий.
        
        Args:
            events: Список измененных событий
            creator_telegram_id: Telegram ID создателя событий
        
        Returns:
            True если уведомление отправлено успешно, False в противном случае
        """
        return await self.notify(events, creator_telegram_id, NotificationType.UPDATED)
    
    async def notify_events_cancelled(self, events: List[CalendarEvent], creator_telegram_id: int) -> bool:
        """
        Уведомляет партнера об отмене событий.
        
        Args:
            events: Список отмененных событий
            creator_telegram_id: Telegram ID создателя событий
        
        Returns:
            True если уведомление отправлено успешно, False в противном случае
        """
        return await self.notify(events, creator_telegram_id, NotificationType.CANCELLED)


# Глобальный экземпляр сервиса
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    Получает глобальный экземпляр NotificationService.
    
    Returns:
        Экземпляр NotificationService
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service

