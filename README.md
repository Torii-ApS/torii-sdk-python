# torii-backend

Backend SDK for [torii](https://torii.so) — verify end-user JWTs without a per-request round trip and manage users from your Python server.

> **v0.x — API may still change.**

## Setup

1. Sign in to [app.torii.so](https://app.torii.so) and from your dashboard copy:
   - your **issuer URL** (e.g. `https://acme.torii.so`)
   - a **secret key** (`sk_test_…` for development, `sk_live_…` for production)

2. Install the SDK:

   ```sh
   pip install torii-backend
   # or, with the FastAPI dependency adapter:
   pip install "torii-backend[fastapi]"
   ```

   Python 3.9+.

3. Verify an end-user JWT:

   ```python
   from torii_backend import verify_token

   auth = verify_token(token, issuer="https://acme.torii.so")
   print(auth.user_id, auth.environment_id, auth.email_verified)
   ```

   The first call fetches the issuer's JWKS; subsequent calls reuse the cache and rotate keys automatically (handled by [`PyJWT`](https://pyjwt.readthedocs.io/)). No round trip per request.

4. Call the backend REST API:

   ```python
   import os
   from torii_backend import create_torii_client

   torii = create_torii_client(secret_key=os.environ["TORII_SECRET_KEY"])
   user = torii.users.get(user_id)
   ```

   Default base URL is `https://api.torii.so`. Override with `api_url=` for staging or testing environments.

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
page = torii.users.list(limit=50)
user = torii.users.create(email="x@y.com")
torii.users.ban(user.id)

sessions = torii.sessions.list_for_user(user.id)
torii.sessions.revoke_all_for_user(user.id)
```

### PATCH semantics (`users.update`)

`users.update` is a tri-state PATCH: each updatable field can be **set**, **cleared**, or **left alone**. Pass only the kwargs you want on the wire — pydantic v2's `model_fields_set` tracks which fields were explicitly provided, and the SDK serializes via `model_dump(exclude_unset=True)` so untouched fields never appear in the request body.

```python
torii.users.update(
    user_id,
    name="Ada",     # → server updates name
    phone=None,     # → server clears phone (sent as JSON null)
    # address not passed → server leaves alone
)
```

Wire body for the call above:

```json
{ "name": "Ada", "phone": null }
```

| Call                                  | Field on wire     | Server effect      |
| ------------------------------------- | ----------------- | ------------------ |
| `users.update(id, name="Ada")`        | `"name": "Ada"`   | update `name`      |
| `users.update(id, phone=None)`        | `"phone": null`   | clear `phone`      |
| `users.update(id)` (no field kwargs)  | omitted           | leave alone        |

You can also build a request explicitly — useful when assembling the patch dynamically:

```python
from torii_backend import ToriiUpdateUserInput

patch = ToriiUpdateUserInput(name="Ada", phone=None)
torii.users.update(user_id, patch)
```

## License

MIT
