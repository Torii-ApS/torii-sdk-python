"""torii-backend — backend SDK for torii.

Verify JWTs networklessly, call ``/api/server/v1/**`` with a secret key,
and (soon) verify outbound webhook signatures. Framework-agnostic; an
optional FastAPI dependency adapter lives in ``torii_backend.fastapi``.
"""

from torii_backend.client import ToriiClient, create_torii_client
from torii_backend.errors import ToriiApiError, ToriiAuthError

# Generated data types — re-exported under stable Torii* aliases so the
# public surface is independent of the generator's naming.
from torii_backend.generated.models import (
    CreateUserRequest as ToriiCreateUserInput,
)
from torii_backend.generated.models import (
    CursorPageResponseServerUserResponse as ToriiCursorPageUser,
)
from torii_backend.generated.models import (
    ProblemDetail as ToriiProblemDetail,
)
from torii_backend.generated.models import (
    ServerUserResponse as ToriiUser,
)
from torii_backend.generated.models import (
    UpdateUserRequest as ToriiUpdateUserInput,
)
from torii_backend.generated.models import (
    UserSessionResponse as ToriiSession,
)
from torii_backend.types import ToriiAuth
from torii_backend.verify import (
    authenticate_request,
    clear_jwks_cache_for_tests,
    verify_token,
    verify_webhook,
)

__all__ = [
    "ToriiApiError",
    "ToriiAuth",
    "ToriiAuthError",
    "ToriiClient",
    "ToriiCreateUserInput",
    "ToriiCursorPageUser",
    "ToriiProblemDetail",
    "ToriiSession",
    "ToriiUpdateUserInput",
    "ToriiUser",
    "authenticate_request",
    "clear_jwks_cache_for_tests",
    "create_torii_client",
    "verify_token",
    "verify_webhook",
]

__version__ = "0.0.1"
