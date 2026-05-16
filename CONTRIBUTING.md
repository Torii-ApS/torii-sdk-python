# Contributing

Thanks for your interest in `torii-backend`!

## Reporting bugs

Open an issue with:

- The version of `torii-backend` you're using (`pip show torii-backend`).
- A minimal reproduction — a few lines that exhibit the bug.
- What you expected to happen vs. what actually happened.

For security-sensitive issues (anything that could let an attacker forge or bypass token verification), please email **security@torii.so** instead of filing a public issue.

## Development

```sh
git clone https://github.com/GOOD-Code-ApS/torii-sdk-python
cd torii-sdk-python
uv venv
uv pip install -e ".[dev]"
.venv/bin/pytest -q
```

The REST client under `src/torii_backend/generated/` is produced by [`openapi-generator`](https://openapi-generator.tech/) from `spec/server-v1.json`. Don't hand-edit it. To regenerate after a spec update:

```sh
bunx -y @openapitools/openapi-generator-cli generate \
  -i spec/server-v1.json -g python -o /tmp/python-gen-raw \
  --additional-properties=packageName=torii_backend.generated,projectName=torii-backend-generated,library=urllib3
cp -r /tmp/python-gen-raw/torii_backend/generated src/torii_backend/generated
```

The hand-written surface (`client.py`, `verify.py`, `fastapi.py`, `types.py`, `errors.py`) is where bug reports and PRs typically land.

## Pull requests

1. Open an issue first for non-trivial changes so we can discuss the shape.
2. Branch off `main`, name it `fix/<short>` or `feat/<short>`.
3. Run `.venv/bin/ruff check src/torii_backend tests` and `.venv/bin/pytest -q` before pushing — CI checks both across Python 3.9–3.12.
4. Keep PRs small and focused. One concern per PR.
5. Update `README.md` if you change the public surface.

## Releases

Tagged off `main`. Bump `version` in `pyproject.toml` and any references in `README.md`, then:

```sh
git tag v0.0.2
git push origin v0.0.2
```

Publishing to PyPI is handled by a maintainer; ping in the release PR if you need a cut.

## Code of Conduct

Be kind. Disagreements happen; argue the position, not the person.
