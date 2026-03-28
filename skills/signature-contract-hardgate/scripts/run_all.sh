#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

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

python3 "$SCRIPT_DIR/run_contract_hardgate_scan.py" \
  --repo "$REPO_ROOT" \
  --out-dir "$OUT_DIR"

python3 "$SCRIPT_DIR/validate_contract_hardgate_summary.py" \
  --summary "$OUT_DIR/contract-hardgate-summary.json"

echo "Signature contract hardgate baseline complete."
