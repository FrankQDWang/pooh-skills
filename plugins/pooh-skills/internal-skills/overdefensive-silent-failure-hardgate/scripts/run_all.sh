#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [repo-root] [harness-dir]

Examples:
  bash scripts/run_all.sh .
  bash scripts/run_all.sh . .repo-harness
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

REPO_ROOT="${1:-.}"
HARNESS_DIR="${2:-$REPO_ROOT/.repo-harness}"
OUT_DIR="$HARNESS_DIR/skills/overdefensive-silent-failure-hardgate"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/report.md"
AGENT_BRIEF_PATH="$OUT_DIR/agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"

mkdir -p "$OUT_DIR"

pooh_runtime_prepare \
  "overdefensive-silent-failure-hardgate" \
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

pooh_runtime_update "running" "" "Running overdefensive silent-failure scan."

python3 "$SCRIPT_DIR/run_overdefensive_scan.py" \
  --repo "$REPO_ROOT" \
  --out "$SUMMARY_PATH"

pooh_runtime_inject_summary

python3 "$SCRIPT_DIR/validate_overdefensive_summary.py" \
  --summary "$SUMMARY_PATH"

python3 "$SCRIPT_DIR/render_reports.py" \
  --summary "$SUMMARY_PATH" \
  --report "$REPORT_PATH" \
  --brief "$AGENT_BRIEF_PATH"

pooh_runtime_finalize

echo "Overdefensive silent-failure scan complete."
