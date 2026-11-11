"""Unit tests for authentication."""

import jwt

from app.config import get_settings
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService


def auth_service(session) -> AuthService:
    return AuthService(UserRepository(session))


def test_login_success(make, session):
    user = make.user(username="bob", password="bobpass", role="regular_user")

    token = auth_service(session).authenticate_user("bob", "bobpass")

    assert token is not None
    payload = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "regular_user"


def test_unknown_username(make, session):
    make.user(username="bob", password="bobpass")

    token = auth_service(session).authenticate_user("nobody", "bobpass")

    assert token is None


def test_wrong_password(make, session):
    make.user(username="bob", password="bobpass")

    token = auth_service(session).authenticate_user("bob", "wrongpass")

    assert token is None
