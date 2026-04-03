#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="${1:-.}"
HARNESS_DIR="${2:-$REPO_ROOT/.repo-harness}"
OUT_DIR="$HARNESS_DIR/skills/module-shape-hardgate"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/report.md"
AGENT_BRIEF_PATH="$OUT_DIR/agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"
RUNTIME_WRAPPER="$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

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

mkdir -p "$OUT_DIR"

if [[ ! -f "$RUNTIME_WRAPPER" ]]; then
  printf 'error: missing shared runtime wrapper at %s\n' "$RUNTIME_WRAPPER" >&2
  exit 2
fi

# shellcheck source=/dev/null
source "$RUNTIME_WRAPPER"

pooh_runtime_prepare \
  "module-shape-hardgate" \
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

pooh_runtime_update "running" "" "Running module shape hardgate scan."
python3 "$SCRIPT_DIR/run_module_shape_scan.py" \
  --repo "$REPO_ROOT" \
  --out-dir "$OUT_DIR" \
  --summary-out "$SUMMARY_PATH" \
  --report-out "$REPORT_PATH" \
  --agent-brief-out "$AGENT_BRIEF_PATH"
pooh_runtime_inject_summary
python3 "$SCRIPT_DIR/validate_module_shape_summary.py" --summary "$SUMMARY_PATH"
pooh_runtime_finalize

echo "Module shape hardgate baseline complete."
