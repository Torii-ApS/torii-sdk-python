#!/usr/bin/env bash
# Regenerate the generated REST client under src/torii_backend/generated/ from
# spec/server-v1.json. The generator emits a standalone project, so we generate
# into a temp dir and sync only the generated subtree. Idempotent; safe to
# re-run after a spec bump. The hand-written surface (client.py, verify.py,
# fastapi.py, types.py, errors.py) is untouched.
set -euo pipefail
cd "$(dirname "$0")"

RAW=$(mktemp -d)
trap 'rm -rf "$RAW"' EXIT

bunx -y @openapitools/openapi-generator-cli generate \
  -i spec/server-v1.json -g python -o "$RAW" \
  --additional-properties=packageName=torii_backend.generated,projectName=torii-backend-generated,library=urllib3

SRC="$RAW/torii_backend/generated"
# Validate the generated subtree exists and is non-empty BEFORE deleting the
# committed one, so a generator that exits 0 with a drifted/empty layout can't
# leave src/ gutted.
if [ ! -d "$SRC" ] || [ -z "$(ls -A "$SRC")" ]; then
  echo "✗ python: generator produced no output at torii_backend/generated; leaving committed tree intact" >&2
  exit 1
fi
rm -rf src/torii_backend/generated
cp -r "$SRC" src/torii_backend/generated

echo "✓ regenerated src/torii_backend/generated/ from spec/server-v1.json"
