#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/install.sh
  ./scripts/install.sh --check

This script manages the repo-local Codex plugin bundle at:
  plugins/pooh-skills/
EOF
}

case "${1:-}" in
  -h|--help)
    print_usage
    exit 0
    ;;
  --check)
    python3 "$SCRIPT_DIR/check_repo_plugin.py" \
      --repo "$REPO_ROOT" \
      --json-out "$REPO_ROOT/.repo-harness/repo-plugin-check.json"
    ;;
  "")
    python3 "$SCRIPT_DIR/sync_plugin_bundle.py" --repo "$REPO_ROOT"
    python3 "$SCRIPT_DIR/check_repo_plugin.py" \
      --repo "$REPO_ROOT" \
      --json-out "$REPO_ROOT/.repo-harness/repo-plugin-check.json"
    printf '%s\n' "Repo-local Codex plugin is ready at $REPO_ROOT/plugins/pooh-skills"
    ;;
  *)
    print_usage >&2
    exit 2
    ;;
esac
