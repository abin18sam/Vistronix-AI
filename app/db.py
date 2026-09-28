from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _connect_args() -> dict:
    return {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}


engine = create_engine(settings.database_url, connect_args=_connect_args(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            for table, column, definition in (
                ("jobs", "queue_wait_ms", "INTEGER"),
                ("jobs", "duration_ms", "INTEGER"),
                ("module_runs", "retryable", "BOOLEAN NOT NULL DEFAULT 0"),
                ("module_runs", "retry_at", "DATETIME"),
            ):
                columns = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
                if column not in columns:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
