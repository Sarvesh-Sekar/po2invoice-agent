"""Unit tests for access-token verification + user dependency wiring."""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Request
from fastapi.datastructures import State
from fastapi.security import HTTPAuthorizationCredentials

from app.config.settings import Settings
from app.exceptions.auth_exceptions import UnauthorizedError
from app.models.context.authenticated_user import USER_STATE_KEY, AuthenticatedUser
from app.security.token import JwtTokenVerifier

JWT_SECRET = "unit-test-secret"


def _token(*, secret: str = JWT_SECRET, expires_in: int = 900, claims: dict | None = None) -> str:
    payload = {
        "sub": "u-1",
        "email": "a@b.com",
        "name": "A",
        "role": "admin",
        "iat": 1,
        "exp": int(time.time()) + expires_in,
    }
    if claims is not None:
        payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def _app(settings: Settings | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(settings=settings or Settings(jwt_secret=JWT_SECRET, require_auth=True))
    )


def _request(token: str | None = None) -> Request:
    scope: dict = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [] if token is None else [(b"authorization", f"Bearer {token}".encode())],
        "app": _app(),
        "state": State(),
    }
    return Request(scope)


class TestJwtTokenVerifier:
    def setup_method(self):
        self.verifier = JwtTokenVerifier(JWT_SECRET)

    def test_valid_token_maps_user(self):
        user = self.verifier.verify(_token())
        assert isinstance(user, AuthenticatedUser)
        assert user.user_id == "u-1"
        assert user.email == "a@b.com"
        assert user.name == "A"
        assert user.role == "admin"
        assert user.is_authenticated is True

    def test_missing_secret_fails_closed(self):
        verifier = JwtTokenVerifier(secret=None)
        with pytest.raises(UnauthorizedError) as exc_info:
            verifier.verify(_token())
        assert exc_info.value.details["reason"] == "authentication is not configured"

    def test_wrong_signature_rejects(self):
        with pytest.raises(UnauthorizedError) as exc_info:
            JwtTokenVerifier("other-secret").verify(_token())
        assert "invalid access token" in exc_info.value.details["reason"]

    def test_expired_token_rejects(self):
        token = _token(claims={"exp": int(time.time()) - 10})
        with pytest.raises(UnauthorizedError) as exc_info:
            self.verifier.verify(token)
        assert "expired" in exc_info.value.details["reason"]

    def test_missing_sub_rejects(self):
        # Tokens lacking a `sub` claim are rejected with a clear reason.
        token = jwt.encode({"iat": 1, "exp": int(time.time()) + 900}, JWT_SECRET, algorithm="HS256")
        with pytest.raises(UnauthorizedError) as exc_info:
            self.verifier.verify(token)
        assert "missing subject" in exc_info.value.details["reason"]

    def test_empty_token_rejects(self):
        with pytest.raises(UnauthorizedError):
            self.verifier.verify("")


@pytest.mark.asyncio
async def test_get_current_user_sets_request_state():
    from app.dependencies.auth import get_current_user

    req = _request(_token())
    result = await get_current_user(
        req, credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token())
    )
    assert result.is_authenticated is True
    assert result.user_id == "u-1"
    assert getattr(req.state, USER_STATE_KEY, None) == result


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_token():
    from app.dependencies.auth import get_current_user

    with pytest.raises(UnauthorizedError):
        await get_current_user(_request(None), credentials=None)


@pytest.mark.asyncio
async def test_get_current_user_allows_anonymous_when_auth_disabled():
    from app.dependencies.auth import get_current_user

    scope: dict = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "app": _app(Settings(jwt_secret=JWT_SECRET, require_auth=False)),
        "state": State(),
    }
    req = Request(scope)
    user = await get_current_user(req, credentials=None)
    assert user.is_authenticated is False
    assert user.user_id == "anonymous"
