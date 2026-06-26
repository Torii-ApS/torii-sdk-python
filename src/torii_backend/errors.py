"""Error types raised by torii_backend."""

from __future__ import annotations

from typing import Any


class ToriiApiError(Exception):
    """Raised when ``/api/server/v1/**`` responds non-2xx.

    Inspect ``status``, ``code`` (from the RFC 7807 error body if present),
    and ``support_id`` (echoed from the server's correlation id) for
    diagnostics. ``body`` contains the raw parsed response.
    """

    def __init__(
        self,
        message: str,
        status: int,
        body: Any = None,
    ):
        super().__init__(message)
        self.status = status
        self.body = body
        self.code: str | None = None
        self.support_id: str | None = None
        if isinstance(body, dict):
            code = body.get("code")
            support_id = body.get("supportId") or body.get("support_id")
            if isinstance(code, str):
                self.code = code
            if isinstance(support_id, str):
                self.support_id = support_id


class ToriiAuthError(Exception):
    """Raised by ``verify_token`` / ``authenticate_request`` when a token
    cannot be verified (bad signature, wrong issuer, missing claims, ...)."""

    def __init__(self, message: str, cause: BaseException | None = None):
        super().__init__(message)
        self.cause = cause
