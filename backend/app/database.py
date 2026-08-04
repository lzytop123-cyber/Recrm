"""
数据库引擎与会话工厂。
通过 SQLAlchemy 抽象，开发用 SQLite，生产切 PostgreSQL 只需改 DATABASE_URL。
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite 需要 check_same_thread=False，否则 FastAPI 多线程会报错
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.sql_echo,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
