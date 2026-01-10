"""Database configuration and connection management."""

import os
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session


def get_database_url(db_file: Optional[str] = None) -> str:
    """
    Получает URL базы данных из переменной окружения или формирует из db_file.
    
    Args:
        db_file: Путь к файлу SQLite БД (для обратной совместимости)
    
    Returns:
        URL базы данных в формате SQLAlchemy
    """
    if db_file:
        # Конвертируем путь к файлу в SQLite URL формат
        # Если путь относительный, добавляем ./ для явного указания
        if not os.path.isabs(db_file):
            db_file = os.path.join(".", db_file)
        return f"sqlite:///{db_file}"
    
    # Берем из переменной окружения
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Дефолтное значение для SQLite
        default_db_file = os.getenv("DB_FILE", "data/family_calendar.db")
        if not os.path.isabs(default_db_file):
            default_db_file = os.path.join(".", default_db_file)
        return f"sqlite:///{default_db_file}"
    
    return database_url


def create_engine_instance(db_file: Optional[str] = None) -> Engine:
    """
    Создает SQLAlchemy engine с правильными параметрами для разных типов БД.
    
    Args:
        db_file: Путь к файлу SQLite БД (для обратной совместимости)
    
    Returns:
        SQLAlchemy Engine
    """
    database_url = get_database_url(db_file)
    
    # Определяем тип БД по URL
    if database_url.startswith("sqlite"):
        # Для SQLite нужны специальные параметры
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=False  # Можно включить для отладки
        )
    else:
        # Для PostgreSQL и других БД используем стандартные параметры
        engine = create_engine(
            database_url,
            echo=False  # Можно включить для отладки
        )
    
    return engine


def get_session_factory(db_file: Optional[str] = None) -> sessionmaker[Session]:
    """
    Возвращает sessionmaker для создания сессий БД.
    
    Args:
        db_file: Путь к файлу SQLite БД (для обратной совместимости)
    
    Returns:
        sessionmaker для создания сессий
    """
    engine = create_engine_instance(db_file)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
