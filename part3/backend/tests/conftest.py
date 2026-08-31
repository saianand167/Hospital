import pytest
import os
import sys

# Ensure backend root is first on sys.path
_test_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_test_dir, ".."))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import create_engine, JSON, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# ── SQLite ↔ PostgreSQL type compatibility ────────────────────────────────────
# SQLite doesn't support JSONB. We register a compilation hook that renders
# JSONB as plain JSON (which SQLite stores as TEXT) so that
# Base.metadata.create_all works on the in-memory test database.
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

# ── Test engine setup ─────────────────────────────────────────────────────────
import app.database
import app.main

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Monkey-patch app.database so every import sees the test engine
app.database.engine = test_engine
app.database.SessionLocal = TestingSessionLocal

from app.database import Base, get_db
from app import crud, models
from app.main import app as fastapi_app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables and seed essential data once per test session."""
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        crud.seed_default_users(db)
        # Seed test patient PAT-000001 for integration tests
        if not crud.get_patient(db, "PAT-000001"):
            p = models.Patient(
                patient_id="PAT-000001",
                name="Rajesh Kumar",
                age=45,
                gender="MALE",
                contact_phone="+919876543210",
                emergency_contact="+919876543211",
                preferred_language="en",
                abha_id="12-3456-7890-1234",
                address="123 Hospital Lane, Hyderabad",
            )
            db.add(p)
            db.commit()
    yield


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
