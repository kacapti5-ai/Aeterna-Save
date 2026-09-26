#!/usr/bin/env bash
# Sync yunban-h5 (Aeterna Save) → https://github.com/kacapti5-ai/Aeterna-Save.git
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE="https://github.com/kacapti5-ai/Aeterna-Save.git"
MSG="${1:-chore: sync Aeterna Save site}"

is_git_repo() {
  git rev-parse --git-dir >/dev/null 2>&1
}

if ! is_git_repo; then
  git init
  git branch -M main
  git remote add origin "$REMOTE"
elif ! git remote get-url origin &>/dev/null; then
  git remote add origin "$REMOTE"
else
  current_url="$(git remote get-url origin)"
  if [[ "$current_url" != "$REMOTE" && "$current_url" != "${REMOTE%.git}" && "$current_url" != "git@github.com:kacapti5-ai/Aeterna-Save.git" ]]; then
    echo "Warning: origin is $current_url, expected $REMOTE"
    git remote set-url origin "$REMOTE"
  fi
fi

git add -A
git reset HEAD .env 2>/dev/null || true

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "$MSG"

echo "Commit: $(git rev-parse --short HEAD)"

if git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
  git push origin main
else
  git push -u origin main
fi

echo "Pushed to $REMOTE (main) — $(git rev-parse --short HEAD)"
echo "Browse: https://github.com/kacapti5-ai/Aeterna-Save"
