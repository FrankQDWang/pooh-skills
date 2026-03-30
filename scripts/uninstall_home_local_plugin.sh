#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/uninstall_home_local_plugin.sh
  ./scripts/uninstall_home_local_plugin.sh --home /custom/home
  ./scripts/uninstall_home_local_plugin.sh --purge-legacy-skills

This script removes the home-local Pooh Skills plugin registration and deletes
the installed ~/plugins/pooh-skills path for the selected home directory.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

python3 "$SCRIPT_DIR/manage_home_local_plugin.py" uninstall --repo "$REPO_ROOT" "$@"
