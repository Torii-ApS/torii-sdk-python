"""Public auth type for torii_backend.

Data types (``ToriiUser``, ``ToriiSession``, ``CursorPage``) live in
``torii_backend.generated.models`` — produced from ``spec/server-v1.json``
by ``openapi-generator``. They're re-exported under stable ``Torii*``
aliases from ``torii_backend.__init__``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToriiAuth:
    """Subset of fields the backend SDK exposes from a verified torii JWT.

    For full claim access (custom claims, audience, etc.) read ``raw``.
    """

    user_id: str
    """End-user ID (JWT ``sub``)."""

    environment_id: str
    """Environment ID this token was issued in (JWT ``pid``)."""

    issuer: str
    """Issuer (JWT ``iss``) — the canonical FAPI URL for this environment."""

    email_verified: bool
    """True if the end-user has verified at least one of their emails."""

    profile_complete: bool
    """True if all environment-required profile fields are filled."""

    impersonating: bool
    """True if the token is being used for admin impersonation."""

    locale: str | None
    """End-user preferred locale, when set on the profile."""

    raw: dict[str, Any]
    """Raw decoded JWT payload — escape hatch for custom claims, audience checks, etc."""
