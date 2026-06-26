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

from datetime import date, datetime
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

# Sentinel to distinguish "argument not passed" from "explicit None" in the
# keyword-arg flavour of ``users.update`` / ``users.create``. We must NOT use
# ``None`` for this purpose because PATCH semantics require ``None`` to mean
# "clear this field on the server". See README "PATCH semantics".
_UNSET: Any = object()

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

    def create(
        self,
        input: CreateUserRequest | dict[str, Any] | None = None,
        *,
        email: str | None = _UNSET,
        password: str | None = _UNSET,
        first_name: str | None = _UNSET,
        last_name: str | None = _UNSET,
        public_metadata: dict[str, Any] | None = _UNSET,
        private_metadata: dict[str, Any] | None = _UNSET,
        unsafe_metadata: dict[str, Any] | None = _UNSET,
    ) -> ServerUserResponse:
        """Create a user.

        Two call shapes:
          * Pass a ``CreateUserRequest`` / dict positionally; OR
          * Pass keyword args directly (``email=...``, ``first_name=...``, etc.).
        """
        if input is not None:
            body = (
                input
                if isinstance(input, CreateUserRequest)
                else CreateUserRequest.from_dict(input)
            )
        else:
            kwargs = {
                "email": email,
                "password": password,
                "firstName": first_name,
                "lastName": last_name,
            }
            payload = {k: v for k, v in kwargs.items() if v is not _UNSET}
            # The three metadata bags are required; default to {} when omitted
            # (a brand-new user has no metadata to clobber).
            payload["publicMetadata"] = {} if public_metadata is _UNSET else public_metadata
            payload["privateMetadata"] = {} if private_metadata is _UNSET else private_metadata
            payload["unsafeMetadata"] = {} if unsafe_metadata is _UNSET else unsafe_metadata
            body = CreateUserRequest.model_validate(payload)
        with _translate_api_error():
            return self._api.create_user(body)

    def update(
        self,
        user_id: str | UUID,
        input: UpdateUserRequest | dict[str, Any] | None = None,
        *,
        first_name: str | None = _UNSET,
        last_name: str | None = _UNSET,
        locale: str | None = _UNSET,
        unsafe_metadata: dict[str, Any] | None = _UNSET,
    ) -> ServerUserResponse:
        """Patch a user.

        Tri-state PATCH semantics — only fields the caller explicitly set
        are sent to the server:
          * not passed → omitted from the JSON body → server leaves alone
          * ``None``   → emitted as ``null``        → server clears
          * value      → emitted with value         → server updates

        Two call shapes:
          * Pass an ``UpdateUserRequest`` / dict positionally; the request
            model's ``model_fields_set`` drives which keys are sent; OR
          * Pass keyword args directly (``first_name="Ada"``, ``last_name=None``, ...).
            Only the kwargs you pass appear on the wire.
        """
        if input is not None:
            model = (
                input
                if isinstance(input, UpdateUserRequest)
                else UpdateUserRequest.model_validate(input)
            )
        else:
            kwargs = {
                "firstName": first_name,
                "lastName": last_name,
                "locale": locale,
                "unsafeMetadata": unsafe_metadata,
            }
            model = UpdateUserRequest.model_validate(
                {k: v for k, v in kwargs.items() if v is not _UNSET}
            )
        # Build the wire body from the model's *explicitly set* fields only.
        # We must NOT pass the model through the generated ``update_user`` —
        # it's wrapped in pydantic's ``@validate_call`` which would re-coerce
        # the dict back into an ``UpdateUserRequest`` and then serialize via
        # ``to_dict()`` (which uses ``exclude_none=True``). That collapses
        # ``phone=None`` ("clear this field") into "omit", breaking tri-state.
        # Drop down to the serializer + ``call_api`` directly so the dict we
        # built survives untouched.
        body = model.model_dump(exclude_unset=True, by_alias=True)
        with _translate_api_error():
            return self._patch_user(_coerce_uuid(user_id), body)

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
    api_client = ApiClient(configuration=config)
    # Spec doesn't declare a securityScheme, so authorise via a default
    # header on every request rather than the ``access_token`` config slot.
    api_client.set_default_header("Authorization", f"Bearer {secret_key}")
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
