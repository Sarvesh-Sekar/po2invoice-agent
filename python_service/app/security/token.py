"""Access-token verification for frontend-facing requests.

The verifier is deliberately free of FastAPI, routers, agents, and repository
knowledge: it decodes a signed access token, checks its cryptographic
integrity/claims, and maps the result onto an :class:`AuthenticatedUser`.
HTTP plumbing lives in ``app/dependencies/auth.py``.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt

from app.config.settings import Settings
from app.exceptions.auth_exceptions import UnauthorizedError
from app.models.context.authenticated_user import AuthenticatedUser

logger = logging.getLogger("app.security.token")


class TokenVerificationError(Exception):
    """Internal signal that a token failed verification (never leaks details)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class JwtTokenVerifier:
    """Validates application access tokens (HS256 by default).

    Tokens are produced by the Go service with the same ``JWT_SECRET``;
    environmental `iss`/`aud` values are enforced when configured.
    """

    def __init__(
        self,
        secret: str | None,
        *,
        algorithm: str = "HS256",
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_settings(cls, settings: Settings) -> JwtTokenVerifier:
        return cls(
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )

    @staticmethod
    def new_anonymous() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id="anonymous",
            is_authenticated=False,
            is_active=True,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        """Verify a raw access token and return the mapped user.

        Raises:
            UnauthorizedError: when the token is missing/expired/invalid or the
                service is not configured to verify signatures.
        """
        if not token:
            raise UnauthorizedError(details={"reason": "missing access token"})
        if not self._secret:
            logger.error("jwt_secret is not configured; refusing to validate tokens")
            raise UnauthorizedError(details={"reason": "authentication is not configured"})

        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iat"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError(details={"reason": "access token expired"}) from exc
        except UnauthorizedError:
            raise
        except jwt.PyJWTError as exc:
            raise UnauthorizedError(details={"reason": "invalid access token"}) from exc

        return self._payload_to_user(payload, token)

    def _payload_to_user(self, payload: dict[str, Any], token: str) -> AuthenticatedUser:
        user_id = str(payload.get("sub") or "")
        if not user_id:
            raise UnauthorizedError(details={"reason": "invalid access token: missing subject"})
        return AuthenticatedUser(
            user_id=user_id,
            email=_as_optional_str(payload.get("email")),
            name=_as_optional_str(payload.get("name")),
            role=_as_optional_str(payload.get("role")),
            is_active=bool(payload.get("active", True)),
            is_authenticated=True,
            token=token,
        )


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
