#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [repo-root] [out-dir]

Examples:
  bash scripts/run_all.sh .
  bash scripts/run_all.sh . .repo-harness
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

REPO_ROOT="${1:-.}"
OUT_DIR="${2:-$REPO_ROOT/.repo-harness}"
mkdir -p "$OUT_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$SCRIPT_DIR/run_py_drift_scan.py" \
  --repo "$REPO_ROOT" \
  --out "$OUT_DIR/pythonic-ddd-drift-summary.json"

python3 "$SCRIPT_DIR/validate_py_drift_summary.py" \
  --summary "$OUT_DIR/pythonic-ddd-drift-summary.json"

echo "Pythonic DDD drift scan complete."
