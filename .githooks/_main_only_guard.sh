#!/usr/bin/env bash
set -euo pipefail

branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"

if [[ -z "$branch" ]]; then
  printf '%s\n' "Detached HEAD is blocked in this repository. Only main is allowed." >&2
  exit 1
fi

if [[ "$branch" != "main" ]]; then
  printf '%s\n' "Branch use is blocked in this repository. Current branch: $branch. Only main is allowed." >&2
  exit 1
fi
