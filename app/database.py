import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Where the database lives. Set the DATABASE_URL environment variable to point
# somewhere else (a test database, Postgres later). Defaults to a local file.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gunpla.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# check_same_thread=False is a SQLite-only setting: FastAPI handles requests
# on different threads, which SQLite blocks by default.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)

if IS_SQLITE:
    # SQLite ignores foreign keys unless you turn them on for every connection.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# A factory that makes sessions (one conversation with the database).
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Parent class for all table models."""


def get_db():
    """FastAPI dependency: one session per request, always closed afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
