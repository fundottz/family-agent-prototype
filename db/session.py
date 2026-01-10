"""Session management for database connections."""

from contextlib import contextmanager
from typing import Optional
from sqlalchemy.orm import Session

from db.config import get_session_factory


@contextmanager
def get_db_session(db_file: Optional[str] = None):
    """
    Context manager для работы с сессией БД.
    
    Автоматически выполняет commit при успехе, rollback при ошибке.
    
    Args:
        db_file: Путь к файлу SQLite БД (для обратной совместимости)
    
    Yields:
        Session: SQLAlchemy сессия
    
    Example:
        with get_db_session("data/test.db") as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_telegram_id(123)
    """
    session_factory = get_session_factory(db_file)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
