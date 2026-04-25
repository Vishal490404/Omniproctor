import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure app settings use a local SQLite DB while importing app modules.
BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BASE_DIR / f"test_{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DEBUG"] = "false"

from app.api.deps import get_db  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.assignment import TestAssignment  # noqa: E402
from app.models.test import Test  # noqa: E402
from app.models.test_attempt import AttemptStatus, TestAttempt  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        f"sqlite+pysqlite:///{TEST_DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session_local = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session: Session = session_local()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_user(db_session):
    user = User(
        full_name="Admin User",
        email="admin@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def teacher_user(db_session):
    user = User(
        full_name="Teacher User",
        email="teacher@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def student_user(db_session):
    user = User(
        full_name="Student User",
        email="student@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def proctor_user(db_session):
    user = User(
        full_name="Proctor User",
        email="proctor@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.PROCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def sample_test(db_session, teacher_user):
    now = datetime.now(timezone.utc)
    record = Test(
        name="Sample Test",
        description="Initial",
        external_link="https://example.com/test",
        is_active=True,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        created_by=teacher_user.id,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def login_and_get_token(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["token"]["access_token"]


@pytest.fixture(scope="function")
def admin_token(client, admin_user):
    return login_and_get_token(client, admin_user.email, "password123")


@pytest.fixture(scope="function")
def teacher_token(client, teacher_user):
    return login_and_get_token(client, teacher_user.email, "password123")


@pytest.fixture(scope="function")
def student_token(client, student_user):
    return login_and_get_token(client, student_user.email, "password123")


@pytest.fixture(scope="function")
def proctor_token(client, proctor_user):
    return login_and_get_token(client, proctor_user.email, "password123")


@pytest.fixture(scope="function")
def assigned_attempt(db_session, sample_test, student_user):
    """An in-progress attempt for ``student_user`` on ``sample_test``.

    Mirrors what the real /attempts/start flow produces, but bypasses the
    HTTP path so individual tests can grab an attempt id without coupling
    to the attempt-start contract.
    """
    assignment = TestAssignment(test_id=sample_test.id, student_id=student_user.id)
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    attempt = TestAttempt(
        test_id=sample_test.id,
        student_id=student_user.id,
        assignment_id=assignment.id,
        status=AttemptStatus.IN_PROGRESS,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


@pytest.fixture(scope="function")
def other_student_user(db_session):
    user = User(
        full_name="Other Student",
        email="other-student@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def other_student_token(client, other_student_user):
    return login_and_get_token(client, other_student_user.email, "password123")
