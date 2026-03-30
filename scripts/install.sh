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

For a user-facing home-local Codex install, use:
  ./scripts/install_home_local_plugin.sh
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
    printf '%s\n' "Repo-local Codex plugin bundle is ready at $REPO_ROOT/plugins/pooh-skills"
    printf '%s\n' "To install it for one user, run: bash $REPO_ROOT/scripts/install_home_local_plugin.sh"
    ;;
  *)
    print_usage >&2
    exit 2
    ;;
esac
