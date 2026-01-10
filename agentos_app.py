"""AgentOS приложение для семейного планировщика."""

import os
import logging
from dotenv import load_dotenv
from agno.db.sqlite import AsyncSqliteDb
from agno.os import AgentOS
from main import create_family_planner_agent

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_agentos_agent():
    """
    Создает агента для AgentOS на основе существующего агента из main.py.
    Заменяет SqliteDb на AsyncSqliteDb для лучшей производительности в AgentOS.
    """
    # Создаем агента из main.py
    agent = create_family_planner_agent()
    
    # Заменяем SqliteDb на AsyncSqliteDb для AgentOS
    #db_file = os.getenv("DB_FILE", "data/family_calendar.db")
    #agent.db = AsyncSqliteDb(db_file=db_file)
    
    return agent


def create_agentos() -> AgentOS:
    """
    Создает и настраивает AgentOS экземпляр.
    """
    logger.info("Создание агента для AgentOS...")
    agent = create_agentos_agent()
    logger.info("✅ Агент создан")
    
    # Создаем AgentOS экземпляр
    agent_os = AgentOS(
        id="family-planner-os",
        description="Семейный ИИ-планировщик для координации семейных дел",
        agents=[agent],
    )
    
    logger.info("✅ AgentOS создан")
    return agent_os


# Создаем AgentOS экземпляр
agent_os = create_agentos()

# Получаем FastAPI приложение
app = agent_os.get_app()


if __name__ == "__main__":
    # Запускаем AgentOS сервер
    # По умолчанию порт 7777; можно изменить через port=...
    logger.info("🚀 Запуск AgentOS...")
    print("🚀 Запуск AgentOS...")
    print("📡 AgentOS будет доступен по адресу: http://localhost:7777")
    print("📚 API документация: http://localhost:7777/docs")
    print("⚙️  Конфигурация: http://localhost:7777/config")
    
    agent_os.serve(app="agentos_app:app", reload=True)
