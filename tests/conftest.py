"""Shared test setup.

The DATABASE_URL line MUST run before anything imports `app`, so tests use a
throwaway database file and never touch your real gunpla.db.
"""
import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="polycap-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_lookups  # noqa: E402


@pytest.fixture
def db():
    """A session on a freshly emptied database with the lookup data seeded."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_lookups(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """An HTTP client for the app, on the same empty database as `db`."""
    return TestClient(app)
