from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from torii_backend.generated.models import (
    CreateUserRequest,
    ServerUserSearchRequest,
    UpdateUserMetadataRequest,
    UpdateUserRequest,
)

_SCHEMAS = {
    "UpdateUserRequest": UpdateUserRequest,
    "CreateUserRequest": CreateUserRequest,
    "ServerUserSearchRequest": ServerUserSearchRequest,
    "UpdateUserMetadataRequest": UpdateUserMetadataRequest,
}


def _load_fixtures() -> list[dict[str, Any]]:
    raw = (Path(__file__).parent / "patch_wire_fixtures.json").read_text()
    return json.loads(raw)["fixtures"]


@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: f["name"])
def test_patch_wire_parity(fixture: dict[str, Any]) -> None:
    """The SDK must emit the exact wire bytes the shared contract blesses.

    Validate expectedBody into the generated request model, then serialize only
    the explicitly-set fields by alias in JSON mode. The round-trip must be
    identical: a key absent stays absent (leave), an explicit null stays null
    (clear), and nested nulls survive (key delete) — the same fixtures the server
    round-trip test asserts. See contract-tests/fixtures/patch-wire.
    """
    model_cls = _SCHEMAS[fixture["schema"]]
    model = model_cls.model_validate(fixture["expectedBody"])
    wire = model.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert wire == fixture["expectedBody"]
