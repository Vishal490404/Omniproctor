import pytest
from fastapi import HTTPException

from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import login_user, register_user


def test_register_user_hashes_password_and_persists(db_session):
    payload = RegisterRequest(
        full_name="Alice",
        email="alice@example.com",
        password="password123",
        role="student",
    )

    user = register_user(db_session, payload)

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.hashed_password != "password123"


def test_register_user_duplicate_email_raises_conflict(db_session):
    first = RegisterRequest(
        full_name="Alice",
        email="dup@example.com",
        password="password123",
        role="student",
    )
    second = RegisterRequest(
        full_name="Alice Two",
        email="dup@example.com",
        password="password123",
        role="student",
    )
    register_user(db_session, first)

    with pytest.raises(HTTPException) as exc:
        register_user(db_session, second)

    assert exc.value.status_code == 409


def test_login_user_returns_token_and_user(db_session):
    register_user(
        db_session,
        RegisterRequest(
            full_name="Bob",
            email="bob@example.com",
            password="password123",
            role="teacher",
        ),
    )

    token, user = login_user(
        db_session,
        LoginRequest(email="bob@example.com", password="password123"),
    )

    assert token
    assert user.email == "bob@example.com"


def test_login_user_invalid_password_raises_401(db_session):
    register_user(
        db_session,
        RegisterRequest(
            full_name="Cara",
            email="cara@example.com",
            password="password123",
            role="student",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        login_user(db_session, LoginRequest(email="cara@example.com", password="badpass123"))

    assert exc.value.status_code == 401
