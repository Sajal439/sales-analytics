"""Shared test fixtures — isolated in-memory SQLite DB per test session.

No Supabase, Redis, or external credentials needed for tests.

Uses connection-level transactions that roll back after each test so
committed data in one test never leaks into another.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite for test isolation
TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all data tables between tests for full isolation."""
    yield
    # After each test, delete all rows from data tables
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def db():
    """Provide a database session for each test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_get_db():
    """Override get_db to use the test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def client():
    """HTTP test client."""
    return TestClient(app)


@pytest.fixture()
def test_user(client: TestClient, db) -> dict:
    import uuid
    from app.models.user import User

    username = f"testuser_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    
    user = db.query(User).filter(User.username == username).first()
    return {"token": token, "user_id": user.id}


@pytest.fixture()
def auth_headers(test_user: dict) -> dict:
    """Return Bearer auth headers for the test user."""
    return {"Authorization": f"Bearer {test_user['token']}"}
