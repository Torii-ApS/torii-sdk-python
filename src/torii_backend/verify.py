"""Networkless JWT verification and webhook stub.

``verify_token`` uses PyJWT's PyJWKClient which fetches and caches the
issuer's JWKS, rotates keys via the JWT's ``kid`` header, and verifies
signatures locally. No per-request round-trip to torii.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import jwt
from jwt import PyJWKClient

from torii_backend.errors import ToriiAuthError
from torii_backend.types import ToriiAuth

# Cache one PyJWKClient per issuer. PyJWKClient does its own internal
# JWKS caching with TTL + rotation on kid miss, so we want one long-lived
# instance per issuer rather than re-fetching for every verify call.
_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client_for(issuer: str) -> PyJWKClient:
    normalized = issuer.rstrip("/")
    client = _jwks_clients.get(normalized)
    if client is None:
        # torii's JWKS lives at /_torii/.well-known/jwks.json for every
        # tenant. Stable contract documented in OIDC discovery; we skip
        # the discovery round-trip on the cold path for that reason.
        client = PyJWKClient(
            f"{normalized}/_torii/.well-known/jwks.json",
            cache_keys=True,
            lifespan=300,
        )
        _jwks_clients[normalized] = client
    return client


def verify_token(
    token: str,
    *,
    issuer: str,
    audience: str | list[str] | None = None,
    leeway: float = 30.0,
) -> ToriiAuth:
    """Verify a torii-issued JWT against the issuer's JWKS.

    :param token: Compact JWS as received from the customer's frontend.
    :param issuer: Expected issuer URL (per-tenant), e.g.
        ``https://acme.torii.so`` or ``https://auth.acme.com``.
    :param audience: Optional ``aud`` claim to enforce. torii doesn't set
        ``aud`` today, so leaving this ``None`` skips the check.
    :param leeway: Clock-skew tolerance in seconds for ``exp`` / ``nbf``.
    :raises ToriiAuthError: if signature, issuer, expiry, or required
        claims fail validation.
    """
    if not token or not isinstance(token, str):
        raise ToriiAuthError("verify_token: token must be a non-empty string")
    if not issuer:
        raise ToriiAuthError("verify_token: issuer is required")

    jwks_client = _jwks_client_for(issuer)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            issuer=issuer,
            audience=audience,
            leeway=leeway,
            options={"require": ["sub", "iat", "exp", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise ToriiAuthError(f"JWT verification failed: {exc}", cause=exc) from exc

    user_id = payload.get("sub")
    environment_id = payload.get("pid")
    iss = payload.get("iss")
    if not isinstance(user_id, str) or not isinstance(environment_id, str) or not isinstance(iss, str):
        raise ToriiAuthError(
            "JWT is missing required string claims (sub, pid, iss)",
        )

    locale = payload.get("locale")
    return ToriiAuth(
        user_id=user_id,
        environment_id=environment_id,
        issuer=iss,
        email_verified=bool(payload.get("email_verified", False)),
        profile_complete=payload.get("profile_complete", True) is not False,
        impersonating=bool(payload.get("impersonating", False)),
        locale=locale if isinstance(locale, str) else None,
        raw=payload,
    )


def authenticate_request(
    headers: Mapping[str, Any],
    *,
    issuer: str,
    audience: str | list[str] | None = None,
    leeway: float = 30.0,
    header: str = "authorization",
) -> ToriiAuth:
    """Extract a bearer token from request headers and verify it.

    Works with any framework whose request exposes a header mapping
    (FastAPI ``request.headers``, Django ``request.META`` after
    lower-casing, Flask ``request.headers``, ...).
    """
    raw_value: str | None = None
    target = header.lower()
    for key, value in headers.items():
        if str(key).lower() != target:
            continue
        raw_value = value if isinstance(value, str) else (value[0] if value else None)
        break
    if not raw_value:
        raise ToriiAuthError(f"Missing {header} header")
    parts = raw_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ToriiAuthError(f"{header} header is not in 'Bearer <token>' form")
    return verify_token(
        parts[1].strip(),
        issuer=issuer,
        audience=audience,
        leeway=leeway,
    )


def verify_webhook(
    *,
    secret: str,  # noqa: ARG001  preserved for SDK-stable signature
    headers: Mapping[str, Any],  # noqa: ARG001
    payload: bytes | str,  # noqa: ARG001
) -> dict[str, Any]:
    """Verify an outbound torii webhook signature.

    .. warning::

       torii's outbound webhook subsystem is not yet available. This stub
       reserves the SDK surface so adopting it later won't be a breaking
       change for callers.
    """
    raise ToriiAuthError(
        "verify_webhook: torii's outbound webhook subsystem is not yet available.",
    )


def clear_jwks_cache_for_tests() -> None:
    """Test-only: clear cached JWKS clients. Production code should never
    call this — PyJWKClient handles rotation internally via ``kid``."""
    _jwks_clients.clear()
