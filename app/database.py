from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Where the database lives. To move to Postgres later, change this string
# (and remove connect_args below).
DATABASE_URL = "sqlite:///./gunpla.db"

# check_same_thread=False is a SQLite-only setting: FastAPI handles requests
# on different threads, which SQLite blocks by default.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

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
