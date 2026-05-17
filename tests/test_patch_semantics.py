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
from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import urllib3

from torii_backend import create_torii_client
from torii_backend.generated.models.update_user_request import UpdateUserRequest


def _dump(model: UpdateUserRequest) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True, by_alias=True)


def test_set() -> None:
    body = _dump(UpdateUserRequest(name="Ada"))
    assert body == {"name": "Ada"}


def test_clear() -> None:
    body = _dump(UpdateUserRequest(phone=None))
    assert body == {"phone": None}


def test_omit() -> None:
    body = _dump(UpdateUserRequest())
    assert body == {}


def test_mixed() -> None:
    body = _dump(UpdateUserRequest(name="Ada", phone=None))
    assert body == {"name": "Ada", "phone": None}


def test_alias_emitted_for_date_of_birth() -> None:
    body = _dump(UpdateUserRequest(date_of_birth="1990-01-01"))
    assert body == {"dateOfBirth": date(1990, 1, 1)}


def test_alias_clear_for_date_of_birth() -> None:
    body = _dump(UpdateUserRequest(date_of_birth=None))
    assert body == {"dateOfBirth": None}


def test_model_fields_set_tracks_explicit_only() -> None:
    assert UpdateUserRequest(name="Ada").model_fields_set == {"name"}
    assert UpdateUserRequest(name=None).model_fields_set == {"name"}
    assert UpdateUserRequest().model_fields_set == set()


# --- Integration: users.update() actually puts the right JSON on the wire ---


def _fake_user_response(user_id: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "environmentId": str(uuid4()),
        "status": "active",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
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
    torii.users.update(uuid4(), name="Ada")
    assert json.loads(captured["body"]) == {"name": "Ada"}


def test_users_update_wire_body_clear() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), phone=None)
    assert json.loads(captured["body"]) == {"phone": None}


def test_users_update_wire_body_omit() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4())
    # No fields touched → empty JSON object on the wire.
    assert json.loads(captured["body"]) == {}


def test_users_update_wire_body_mixed_with_alias() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), name="Ada", phone=None, date_of_birth=date(1990, 1, 1))
    assert json.loads(captured["body"]) == {
        "name": "Ada",
        "phone": None,
        "dateOfBirth": "1990-01-01",
    }


def test_users_update_accepts_model_positional() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), UpdateUserRequest(name="Ada", phone=None))
    assert json.loads(captured["body"]) == {"name": "Ada", "phone": None}


def test_users_update_accepts_dict_positional() -> None:
    torii = create_torii_client(secret_key="sk_test")
    captured = _install_capture(torii)
    torii.users.update(uuid4(), {"name": "Ada"})
    assert json.loads(captured["body"]) == {"name": "Ada"}


