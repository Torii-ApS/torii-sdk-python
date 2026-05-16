# torii-backend

Backend SDK for [torii](https://torii.so) — verify end-user JWTs without a per-request round trip, manage users from your Python server, react to events from torii.

> **Status: 0.0.x preview.** Stable for verify + users + sessions. Outbound webhooks (`verify_webhook`) is a stub that raises until torii's webhook subsystem ships (tracked in [GOOD-Code-ApS/torii#424](https://github.com/GOOD-Code-ApS/torii/issues/424) Phase 0.5).

## Install

```sh
pip install torii-backend
# or, with the FastAPI dependency adapter:
pip install "torii-backend[fastapi]"
```

Python 3.9+.

## Verify a JWT

```python
from torii_backend import verify_token

auth = verify_token(token, issuer="https://acme.torii.so")  # or your verified custom domain
print(auth.user_id, auth.environment_id, auth.email_verified)
```

The first call fetches the issuer's JWKS; subsequent calls reuse the cache and rotate keys automatically (handled by [`PyJWT`](https://pyjwt.readthedocs.io/)). No network round trip per request.

## FastAPI

```python
from fastapi import Depends, FastAPI
from torii_backend.fastapi import require_auth

app = FastAPI()
auth_dep = require_auth(issuer="https://acme.torii.so")

@app.get("/me")
def me(auth = Depends(auth_dep)):
    return {"user_id": auth.user_id}
```

## Backend API

```python
import os
from torii_backend import create_torii_client

torii = create_torii_client(secret_key=os.environ["TORII_SECRET_KEY"])

page = torii.users.list(limit=50)
user = torii.users.create(email="x@y.com")
torii.users.ban(user.id)

sessions = torii.sessions.list_for_user(user.id)
torii.sessions.revoke_all_for_user(user.id)
```

Default base URL is `https://api.torii.so`. Override with `api_url` for staging or self-hosted.

## Verify outbound webhooks

```python
from torii_backend import verify_webhook  # currently raises; awaiting Phase 0.5

event = verify_webhook(secret=secret, headers=request.headers, payload=request.body)
```

## License

MIT
