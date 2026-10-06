"""Authentication dependencies for HTTP access.

Two isolated guards live here:

- ``require_internal_api_key`` — service-to-service auth for Go → Python
  internal endpoints (``X-Internal-API-Key``). Never exposed to the frontend.
- ``get_current_user`` — user-facing Bearer JWT guard for frontend APIs. It
  validates the access token via the isolated :class:`JwtTokenVerifier` and
  attaches the :class:`AuthenticatedUser` to ``request.state.user`` so
  downstream services can read it without JWT knowledge.

Neither guard knows anything about routers, agents, repositories, or business
logic; they only authenticate and authorize requests.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Request, Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.config.logging import get_logger
from app.config.settings import Settings
from app.exceptions.auth_exceptions import UnauthorizedError
from app.models.context.authenticated_user import USER_STATE_KEY, AuthenticatedUser
from app.security.token import JwtTokenVerifier

logger = get_logger(__name__)

#: Bearer credentials are resolved by FastAPI from the Authorization header.
#: ``auto_error=False`` so the missing-header case 401s via our own error shape.
#: ``scheme_name``/``bearerFormat`` keep the served OpenAPI aligned with the
#: documented contract (``bearerAuth`` of type ``http`` + ``bearer``).
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(HTTPBearer(auto_error=False, scheme_name="bearerAuth", bearerFormat="JWT")),
]

#: Service-to-service credential documented as the ``internalApiKey`` scheme.
InternalAPIKeyHeader = APIKeyHeader(
    name="X-Internal-API-Key",
    scheme_name="internalApiKey",
    auto_error=False,
)


def require_internal_api_key(
    request: Request,
    x_internal_api_key: Annotated[str | None, Security(InternalAPIKeyHeader)] = None,
) -> None:
    """Validate the X-Internal-API-Key header for service-to-service endpoints."""
    settings: Settings = request.app.state.settings
    if settings.internal_api_key:
        if not x_internal_api_key or not secrets.compare_digest(x_internal_api_key, settings.internal_api_key):
            raise UnauthorizedError(details={"reason": "invalid or missing X-Internal-API-Key"})
        return
    # No key configured: open only outside production.
    if settings.environment == "production":
        raise UnauthorizedError(details={"reason": "internal_api_key not configured"})
    return None


async def get_current_user(
    request: Request,
    credentials: BearerCredentials,
) -> AuthenticatedUser:
    """Validate the caller's Bearer access token and attach identity to the request.

    - Missing/invalid/expired tokens are rejected with HTTP 401.
    - When ``require_auth`` is disabled the request is allowed through and an
      unauthenticated marker is attached (used for local development).
    """
    settings: Settings = request.app.state.settings

    if not settings.require_auth:
        user = JwtTokenVerifier.new_anonymous()
        setattr(request.state, USER_STATE_KEY, user)
        return user

    if credentials is None or not credentials.scheme.lower().startswith("bearer"):
        raise UnauthorizedError(details={"reason": "missing Authorization Bearer token"})

    token = credentials.credentials
    verifier = JwtTokenVerifier.from_settings(settings)
    user = verifier.verify(token)
    setattr(request.state, USER_STATE_KEY, user)
    logger.debug("authenticated_request: user_id=%s | role=%s", user.user_id, user.role)
    return user
