"""Authenticated-user context attached to requests guarded by user auth.

Downstream services and dependencies read this from `request.state.user`
(or from the `get_current_user` dependency) without depending on JWT details.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: Name of the attribute used to expose the user on ``starlette.Request.state``.
USER_STATE_KEY = "user"


class AuthenticatedUser(BaseModel):
    """Identity of an authenticated frontend-facing caller."""

    user_id: str = Field(description="Unique application user id (JWT `sub` claim)")
    email: str | None = None
    name: str | None = None
    role: str | None = None
    is_active: bool = True
    is_authenticated: bool = True
    token: str | None = Field(default=None, description="Raw access token presented by the caller")

    @property
    def display_name(self) -> str:
        return self.name or self.email or self.user_id

    @property
    def is_admin(self) -> bool:
        return (self.role or "").lower() in {"admin", "administrator"}
