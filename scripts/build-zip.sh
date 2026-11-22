#!/usr/bin/env bash
# Build the release zip from tracked files only.
# Usage: scripts/build-zip.sh <version> <out.zip>
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <version> <out.zip>" >&2
    exit 2
fi
version="$1"
out="$2"

if ! [[ "$version" =~ ^[0-9A-Za-z.+-]+$ ]]; then
    echo "invalid version: $version" >&2
    exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$out" in
    /*) ;;
    *) out="$PWD/$out" ;;
esac

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/dbus-smartevse"

cd "$root"
# Tracked files only. Leave out tests, CI, docs, this script, and dotfiles.
git ls-files -z \
    | grep -zvE '^(tests|\.github|docs|scripts)/|^(mise\.toml|pyproject\.toml)$|(^|/)\.[^/]*$' \
    | xargs -0 -I{} cp --parents {} "$stage/dbus-smartevse/"

# Write the version into the staged copy only.
printf '__version__ = "%s"\n' "$version" > "$stage/dbus-smartevse/smartevse/__init__.py"

rm -f "$out"
(cd "$stage" && zip -qr "$out" dbus-smartevse)
