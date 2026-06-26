"""FastAPI dependency adapter.

``fastapi`` is an optional install — depend on ``torii-backend[fastapi]``
to pull it in. Importing this module without FastAPI raises a clear
error so the dependency requirement is obvious.
"""

from __future__ import annotations

from typing import Callable

try:
    from fastapi import HTTPException, Request
except ImportError as e:  # pragma: no cover - import guard
    raise ImportError(
        "torii_backend.fastapi requires fastapi. Install with `pip install torii-backend[fastapi]`."
    ) from e

from torii_backend.errors import ToriiAuthError
from torii_backend.types import ToriiAuth
from torii_backend.verify import authenticate_request


def require_auth(
    *,
    issuer: str,
    audience: str | list[str] | None = None,
    leeway: float = 30.0,
) -> Callable[[Request], ToriiAuth]:
    """Return a FastAPI dependency that authenticates the request.

    Example::

        from fastapi import Depends, FastAPI
        from torii_backend.fastapi import require_auth

        app = FastAPI()

        @app.get("/me")
        def me(auth = Depends(require_auth(issuer="https://acme.torii.so"))):
            return {"user_id": auth.user_id}
    """

    def dependency(request: Request) -> ToriiAuth:
        try:
            return authenticate_request(
                request.headers,
                issuer=issuer,
                audience=audience,
                leeway=leeway,
            )
        except ToriiAuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "authentication_failed", "message": str(exc)},
            ) from exc

    return dependency
