"""Tests for verify_token: spin up an in-process JWKS server, mint
ES256 JWTs against a generated keypair, and cover the success path
plus every documented failure mode. No external network."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    generate_private_key,
)

from torii_backend import (
    ToriiAuthError,
    authenticate_request,
    clear_jwks_cache_for_tests,
    verify_token,
)


class _Fixture:
    def __init__(self, server: HTTPServer, issuer: str, private_key, kid: str):
        self.server = server
        self.issuer = issuer
        self.private_key = private_key
        self.kid = kid


def _make_jwks(public_key, kid: str) -> dict:
    numbers = public_key.public_numbers()
    import base64

    def _b64u(n: int) -> str:
        b = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "EC",
                "crv": "P-256",
                "alg": "ES256",
                "use": "sig",
                "kid": kid,
                "x": _b64u(numbers.x),
                "y": _b64u(numbers.y),
            }
        ]
    }


@pytest.fixture
def fixture() -> Iterator[_Fixture]:
    clear_jwks_cache_for_tests()
    private_key = generate_private_key(SECP256R1())
    public_key = private_key.public_key()
    kid = "test-key-1"
    jwks = _make_jwks(public_key, kid)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/_torii/.well-known/jwks.json":
                body = json.dumps(jwks).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *_args) -> None:  # silence test server logs
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    issuer = f"http://127.0.0.1:{port}"
    try:
        yield _Fixture(server, issuer, private_key, kid)
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _sign_token(private_key, kid: str, claims: dict, issuer: str) -> str:
    now = int(time.time())
    payload = {**claims, "iat": now, "exp": now + 300, "iss": issuer}
    return pyjwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


def test_verifies_well_formed_jwt_and_extracts_claims(fixture: _Fixture) -> None:
    token = _sign_token(
        fixture.private_key,
        fixture.kid,
        {
            "sub": "user_123",
            "pid": "env_abc",
            "email_verified": True,
            "profile_complete": True,
            "locale": "en",
        },
        fixture.issuer,
    )
    auth = verify_token(token, issuer=fixture.issuer)
    assert auth.user_id == "user_123"
    assert auth.environment_id == "env_abc"
    assert auth.issuer == fixture.issuer
    assert auth.email_verified is True
    assert auth.profile_complete is True
    assert auth.impersonating is False
    assert auth.locale == "en"


def test_rejects_jwt_signed_by_different_key(fixture: _Fixture) -> None:
    other_key = generate_private_key(SECP256R1())
    token = _sign_token(other_key, fixture.kid, {"sub": "u", "pid": "e"}, fixture.issuer)
    with pytest.raises(ToriiAuthError):
        verify_token(token, issuer=fixture.issuer)


def test_rejects_jwt_with_wrong_issuer(fixture: _Fixture) -> None:
    token = _sign_token(
        fixture.private_key, fixture.kid, {"sub": "u", "pid": "e"}, "http://wrong-issuer.example"
    )
    with pytest.raises(ToriiAuthError):
        verify_token(token, issuer=fixture.issuer)


def test_rejects_jwt_missing_required_claim(fixture: _Fixture) -> None:
    # no sub
    token = _sign_token(fixture.private_key, fixture.kid, {"pid": "e"}, fixture.issuer)
    with pytest.raises(ToriiAuthError):
        verify_token(token, issuer=fixture.issuer)


def test_rejects_expired_jwt(fixture: _Fixture) -> None:
    now = int(time.time())
    payload = {
        "sub": "u",
        "pid": "e",
        "iss": fixture.issuer,
        "iat": now - 600,
        "exp": now - 300,
    }
    token = pyjwt.encode(
        payload, fixture.private_key, algorithm="ES256", headers={"kid": fixture.kid}
    )
    with pytest.raises(ToriiAuthError):
        verify_token(token, issuer=fixture.issuer)


def test_authenticate_request_reads_bearer_token(fixture: _Fixture) -> None:
    token = _sign_token(fixture.private_key, fixture.kid, {"sub": "u", "pid": "e"}, fixture.issuer)
    auth = authenticate_request({"Authorization": f"Bearer {token}"}, issuer=fixture.issuer)
    assert auth.user_id == "u"


def test_authenticate_request_rejects_missing_header(fixture: _Fixture) -> None:
    with pytest.raises(ToriiAuthError):
        authenticate_request({}, issuer=fixture.issuer)


def test_authenticate_request_rejects_non_bearer(fixture: _Fixture) -> None:
    with pytest.raises(ToriiAuthError):
        authenticate_request({"authorization": "Basic abc"}, issuer=fixture.issuer)
