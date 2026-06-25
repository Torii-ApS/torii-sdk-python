#!/usr/bin/env bash
# Set the published package version. Called by the torii release train (and
# `just sdk-release`) right before tagging. The edited value must match what
# this repo's release.yml asserts the tag against (here: pyproject [project].version).
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${1:?usage: ./bump.sh <version>  (e.g. 0.0.5)}"
VERSION="${VERSION#v}"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]]; then
	echo "✗ invalid version: '$VERSION'" >&2
	exit 1
fi

# First top-level `version = "..."` only (the [project] one); build-system
# `requires`/`requires-python` lines are not `version =` so are untouched.
perl -i -pe 'if (!$done && s/^(version\s*=\s*")[^"]*(")/${1}'"$VERSION"'${2}/) { $done = 1 }' pyproject.toml
grep -q "^version = \"$VERSION\"" pyproject.toml || { echo "✗ pyproject.toml not bumped to $VERSION" >&2; exit 1; }
echo "✓ torii-sdk-python -> $VERSION (pyproject.toml)"
