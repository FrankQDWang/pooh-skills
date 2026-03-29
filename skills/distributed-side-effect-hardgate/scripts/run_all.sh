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
source "$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

SUMMARY_PATH="$OUT_DIR/distributed-side-effect-summary.json"
REPORT_PATH="$OUT_DIR/distributed-side-effect-report.md"
AGENT_BRIEF_PATH="$OUT_DIR/distributed-side-effect-agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"

pooh_runtime_prepare \
  "distributed-side-effect-hardgate" \
  "$SCRIPT_DIR" \
  "$REPO_ROOT" \
  "$OUT_DIR" \
  "$SUMMARY_PATH" \
  "$REPORT_PATH" \
  "$AGENT_BRIEF_PATH" \
  "$MANIFEST_PATH"

bootstrap_exit=0
pooh_runtime_bootstrap_or_block || bootstrap_exit=$?
if [[ "$bootstrap_exit" -eq 10 ]]; then
  exit 1
elif [[ "$bootstrap_exit" -ne 0 ]]; then
  exit "$bootstrap_exit"
fi

pooh_runtime_update "running" "" "Running distributed side-effect scan."

python3 "$SCRIPT_DIR/run_side_effect_scan.py" \
  --repo "$REPO_ROOT" \
  --out "$SUMMARY_PATH"

pooh_runtime_inject_summary

python3 "$SCRIPT_DIR/validate_side_effect_summary.py" \
  --summary "$SUMMARY_PATH"

pooh_runtime_finalize

echo "Distributed side-effect scan complete."
