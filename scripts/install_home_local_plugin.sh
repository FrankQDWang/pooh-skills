#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/install_home_local_plugin.sh
  ./scripts/install_home_local_plugin.sh --home /custom/home
  ./scripts/install_home_local_plugin.sh --mode copy
  ./scripts/install_home_local_plugin.sh --skip-legacy-cleanup

This script:
  1. syncs the single-entry plugin bundle
  2. validates the bundle and public plugin docs
  3. installs ~/plugins/pooh-skills into a home-local Codex marketplace
  4. removes legacy ~/.codex/skills copies for this fleet by default
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

python3 "$SCRIPT_DIR/sync_plugin_bundle.py" --repo "$REPO_ROOT"
python3 "$SCRIPT_DIR/check_repo_plugin.py" \
  --repo "$REPO_ROOT" \
  --json-out "$REPO_ROOT/.repo-harness/repo-plugin-check.json"
python3 "$SCRIPT_DIR/manage_home_local_plugin.py" install --repo "$REPO_ROOT" "$@"
