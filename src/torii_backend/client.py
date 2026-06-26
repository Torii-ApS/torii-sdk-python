"""ToriiClient — entry point for the REST surface.

Wraps the openapi-generator output under ``torii_backend.generated``
behind a thin, hand-written facade so callers see ergonomic methods
instead of the generator's verbose ``_request_timeout``/``_headers``/...
parameter sprawl.

Types and endpoints come from the OpenAPI spec via ``openapi-generator``;
only the wrapper + auth helpers are hand-written. When the spec grows,
regenerate and add a one-line wrapper method per new endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from torii_backend.errors import ToriiApiError
from torii_backend.generated import (
    ApiClient,
    ApiException,
    Configuration,
    ServerSessionsApi,
    ServerUsersApi,
)
from torii_backend.generated.models import (
    CreateUserRequest,
    CursorPageResponseServerUserResponse,
    ServerUserResponse,
    ServerUserSearchRequest,
    UpdateUserRequest,
    UserSessionResponse,
)

DEFAULT_API_URL = "https://api.torii.so"


class UsersClient:
    def __init__(self, api: ServerUsersApi) -> None:
        self._api = api

    def list(
        self,
        *,
        limit: int | None = None,
        cursor: str | UUID | None = None,
        name: str | None = None,
        email: str | None = None,
        statuses: list[str] | None = None,
        created_after: str | datetime | None = None,
        created_before: str | datetime | None = None,
    ) -> CursorPageResponseServerUserResponse:
        """Search users. Server-side cursor-paginated; loop with the
        returned ``next_cursor`` until ``has_more`` is False."""
        search = ServerUserSearchRequest.from_dict(
            {
                "name": name,
                "email": email,
                "statuses": statuses,
                "createdAfter": created_after,
                "createdBefore": created_before,
            }
        )
        with _translate_api_error():
            return self._api.search_users(
                limit=limit,
                cursor=_coerce_uuid(cursor),
                server_user_search_request=search,
            )

    def get(self, user_id: str | UUID) -> ServerUserResponse:
        with _translate_api_error():
            return self._api.get_user(_coerce_uuid(user_id))

    def create(self, body: CreateUserRequest | dict[str, Any]) -> ServerUserResponse:
        """Create a user.

        Pass a ``CreateUserRequest`` or an equivalent ``dict`` (camelCase keys).
        Accepting the generated request type directly means a new spec field
        flows through with zero hand edits. Metadata bags are optional; omit
        them and the server defaults each to ``{}`` (never clobbered).
        """
        model = body if isinstance(body, CreateUserRequest) else CreateUserRequest.from_dict(body)
        with _translate_api_error():
            return self._api.create_user(model)

    def update(
        self,
        user_id: str | UUID,
        body: UpdateUserRequest | dict[str, Any],
    ) -> ServerUserResponse:
        """Patch a user.

        Tri-state PATCH semantics, driven entirely by the request model's
        ``model_fields_set`` — there are no per-field kwargs to maintain, so a
        new spec field flows through with zero hand edits:
          * a field not set on the model → omitted from the body → server leaves it alone
          * a field set to ``None``       → emitted as ``null``    → server clears it
          * a field set to a value        → emitted with the value → server updates it

        Pass an ``UpdateUserRequest`` (built with only the fields you want to
        touch) or an equivalent ``dict`` (camelCase keys). Metadata bags are
        2-state (omit vs object); a null-valued key inside a bag deletes it.
        """
        model = body if isinstance(body, UpdateUserRequest) else UpdateUserRequest.model_validate(body)
        # Serialize only the model's explicitly-set fields. We bypass the generated
        # ``update_user`` because its ``@validate_call`` re-coerces via ``to_dict()``
        # (``exclude_none=True``), which would collapse an explicit ``None`` ("clear")
        # into "omit" and break tri-state. ``_patch_user`` sends our dict untouched.
        wire = model.model_dump(exclude_unset=True, by_alias=True)
        with _translate_api_error():
            return self._patch_user(_coerce_uuid(user_id), wire)

    def _patch_user(self, user_id: Any, body: dict[str, Any]) -> ServerUserResponse:
        params = self._api._update_user_serialize(
            user_id=user_id,
            update_user_request=body,
            _request_auth=None,
            _content_type=None,
            _headers=None,
            _host_index=0,
        )
        response = self._api.api_client.call_api(*params)
        response.read()
        return self._api.api_client.response_deserialize(
            response_data=response,
            response_types_map={"200": "ServerUserResponse"},
        ).data

    def delete(self, user_id: str | UUID) -> None:
        with _translate_api_error():
            self._api.delete_user(_coerce_uuid(user_id))

    def ban(self, user_id: str | UUID) -> ServerUserResponse:
        with _translate_api_error():
            return self._api.ban_user(_coerce_uuid(user_id))

    def unban(self, user_id: str | UUID) -> ServerUserResponse:
        with _translate_api_error():
            return self._api.unban_user(_coerce_uuid(user_id))


class SessionsClient:
    def __init__(self, api: ServerSessionsApi) -> None:
        self._api = api

    def list_for_user(self, user_id: str | UUID) -> list[UserSessionResponse]:
        with _translate_api_error():
            return self._api.list_sessions(_coerce_uuid(user_id))

    def revoke_all_for_user(self, user_id: str | UUID) -> None:
        with _translate_api_error():
            self._api.revoke_all_sessions(_coerce_uuid(user_id))

    def revoke(self, user_id: str | UUID, session_id: str | UUID) -> None:
        with _translate_api_error():
            self._api.revoke_session(_coerce_uuid(user_id), _coerce_uuid(session_id))


class ToriiClient:
    """Construct via :func:`create_torii_client`."""

    def __init__(self, api_client: ApiClient) -> None:
        self._api_client = api_client
        self.users = UsersClient(ServerUsersApi(api_client))
        self.sessions = SessionsClient(ServerSessionsApi(api_client))

    def close(self) -> None:
        self._api_client.close()

    def __enter__(self) -> ToriiClient:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def create_torii_client(
    *,
    secret_key: str,
    api_url: str | None = None,
) -> ToriiClient:
    """Build a torii backend client.

    Example::

        torii = create_torii_client(secret_key=os.environ["TORII_SECRET_KEY"])
        user = torii.users.get("user_abc")

    ``api_url`` defaults to ``https://api.torii.so``. Override for staging
    or self-hosted.
    """
    if not secret_key:
        raise ValueError("create_torii_client: secret_key is required")
    config = Configuration(host=(api_url or DEFAULT_API_URL).rstrip("/"))
    # The spec declares a `bearerAuth` HTTP-bearer scheme, so the generated
    # operations apply `Authorization: Bearer <access_token>` automatically.
    config.access_token = secret_key
    api_client = ApiClient(configuration=config)
    return ToriiClient(api_client)


def _coerce_uuid(value: str | UUID | None) -> Any:
    """Generated methods accept UUID for path params. We let callers pass
    either ``str`` or ``UUID`` and coerce here."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(value)


class _translate_api_error:
    """Context manager: re-raise the generator's ``ApiException`` as our
    stable ``ToriiApiError`` so callers don't depend on generator
    internals to catch failures."""

    def __enter__(self) -> _translate_api_error:
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        if exc is None or not isinstance(exc, ApiException):
            return False
        body: Any = exc.body
        if isinstance(body, bytes):
            try:
                body = body.decode("utf-8")
            except UnicodeDecodeError:
                body = None
        if isinstance(body, str):
            try:
                import json

                body = json.loads(body)
            except ValueError:
                pass
        message = _extract_message(body) or f"torii {exc.status} {exc.reason or ''}".strip()
        raise ToriiApiError(message, exc.status or 0, body) from exc


def _extract_message(body: Any) -> str | None:
    if isinstance(body, dict):
        for key in ("detail", "title", "message"):
            value = body.get(key)
            if isinstance(value, str):
                return value
    return None
