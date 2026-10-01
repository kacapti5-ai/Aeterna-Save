#!/usr/bin/env bash
# Publish data/market.json and data/site.json from the admin server to GitHub Pages.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repo" >&2
  exit 1
fi

git add data/market.json data/site.json

if git diff --cached --quiet; then
  echo "No data changes to publish."
  exit 0
fi

git -c user.name="Aeterna Save Admin" -c user.email="admin@aeternasave.com" \
  commit -m "chore: publish catalog from admin"

git push origin HEAD:main
echo "Published $(git rev-parse --short HEAD)"
