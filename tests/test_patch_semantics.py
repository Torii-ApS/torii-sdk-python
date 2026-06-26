"""Tri-state PATCH semantics via pydantic ``exclude_unset``.

The wire body for ``PATCH /api/server/v1/users/{userId}`` must distinguish:
  * key omitted → server leaves field alone
  * key present with ``null`` → server clears the field
  * key present with value → server updates the field

We rely on pydantic v2's ``model_fields_set`` + ``model_dump(exclude_unset=True)``
as the source of truth — no wrapper class needed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import urllib3

from torii_backend import create_torii_client
from torii_backend.generated.models.update_user_request import UpdateUserRequest


def _dump(model: UpdateUserRequest) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True, by_alias=True)


def test_set() -> None:
    body = _dump(UpdateUserRequest(first_name="Ada"))
    assert body == {"firstName": "Ada"}


def test_clear() -> None:
    body = _dump(UpdateUserRequest(last_name=None))
    assert body == {"lastName": None}


def test_omit() -> None:
    body = _dump(UpdateUserRequest())
    assert body == {}


def test_mixed() -> None:
    body = _dump(UpdateUserRequest(first_name="Ada", last_name=None))
    assert body == {"firstName": "Ada", "lastName": None}


def test_unsafe_metadata_set() -> None:
    body = _dump(UpdateUserRequest(unsafe_metadata={"tier": "pro"}))
    assert body == {"unsafeMetadata": {"tier": "pro"}}


def test_unsafe_metadata_clear() -> None:
    body = _dump(UpdateUserRequest(unsafe_metadata=None))
    assert body == {"unsafeMetadata": None}


def test_model_fields_set_tracks_explicit_only() -> None:
    assert UpdateUserRequest(first_name="Ada").model_fields_set == {"first_name"}
    assert UpdateUserRequest(first_name=None).model_fields_set == {"first_name"}
    assert UpdateUserRequest().model_fields_set == set()


# --- Integration: users.update() actually puts the right JSON on the wire ---


def _fake_user_response(user_id: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "environmentId": str(uuid4()),
        "status": "active",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "publicMetadata": {},
        "privateMetadata": {},
        "unsafeMetadata": {},
    }


def _install_capture(torii) -> dict[str, Any]:
    """Replace the underlying urllib3 PoolManager so calls don't go to the
    network. Capture the JSON body the SDK actually sends."""
    captured: dict[str, Any] = {}
    rest = torii._api_client.rest_client

    def fake_request(method, url, body=None, timeout=None, headers=None, preload_content=False):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        user_id = url.rstrip("/").split("/")[-1]
        payload = json.dumps(_fake_user_response(user_id)).encode("utf-8")
        resp = MagicMock()
        resp.status = 200
        resp.reason = "OK"
        resp.getheaders.return_value = {"content-type": "application/json"}
        resp.headers = {"content-type": "application/json"}
        resp.data = payload
        resp.read.return_value = payload
        resp.release_conn = lambda: None
        return resp

    rest.pool_manager = MagicMock(spec=urllib3.PoolManager)
    rest.pool_manager.request.side_effect = fake_request
    return captured


def test_users_update_wire_body_set() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), first_name="Ada")
    assert json.loads(captured["body"]) == {"firstName": "Ada"}


def test_users_update_wire_body_clear() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), last_name=None)
    assert json.loads(captured["body"]) == {"lastName": None}


def test_users_update_wire_body_omit() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4())
    # No fields touched → empty JSON object on the wire.
    assert json.loads(captured["body"]) == {}


def test_users_update_wire_body_mixed_with_metadata() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), first_name="Ada", last_name=None, unsafe_metadata={"tier": "pro"})
    assert json.loads(captured["body"]) == {
        "firstName": "Ada",
        "lastName": None,
        "unsafeMetadata": {"tier": "pro"},
    }


def test_users_update_accepts_model_positional() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), UpdateUserRequest(first_name="Ada", last_name=None))
    assert json.loads(captured["body"]) == {"firstName": "Ada", "lastName": None}


def test_users_update_accepts_dict_positional() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), {"firstName": "Ada"})
    assert json.loads(captured["body"]) == {"firstName": "Ada"}


def test_users_update_sends_bearer_auth_header() -> None:
    # The secret key must reach the wire as `Authorization: Bearer ...` via the
    # generated bearerAuth scheme — even on the hand-rolled PATCH path, which
    # bypasses the generated update_user wrapper.
    torii = create_torii_client(secret_key="sk_test_abc")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), first_name="Ada")
    assert captured["headers"].get("Authorization") == "Bearer sk_test_abc"
