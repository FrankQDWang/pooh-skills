#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [--doc-evidence-json path] [repo-root] [harness-dir]

Examples:
  bash scripts/run_all.sh .
  bash scripts/run_all.sh --doc-evidence-json .repo-harness/pydantic-temporal-doc-evidence.json .
  bash scripts/run_all.sh . .repo-harness
EOF
}

DOC_EVIDENCE_JSON=""
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --doc-evidence-json)
      [[ $# -ge 2 ]] || { printf '%s\n' "--doc-evidence-json requires a path" >&2; exit 2; }
      DOC_EVIDENCE_JSON="$2"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

REPO_ROOT="${POSITIONAL[0]:-.}"
HARNESS_DIR="${POSITIONAL[1]:-$REPO_ROOT/.repo-harness}"
OUT_DIR="$HARNESS_DIR/skills/pydantic-ai-temporal-hardgate"
SUMMARY_PATH="$OUT_DIR/summary.json"
REPORT_PATH="$OUT_DIR/report.md"
AGENT_BRIEF_PATH="$OUT_DIR/agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"

mkdir -p "$OUT_DIR"

pooh_runtime_prepare \
  "pydantic-ai-temporal-hardgate" \
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

pooh_runtime_update "running" "" "Running pydantic-ai-temporal hardgate scan."

RUN_ARGS=(
  python3
  "$SCRIPT_DIR/run_pydantic_temporal_scan.py"
  --repo "$REPO_ROOT"
  --out-dir "$OUT_DIR"
  --summary-out "$SUMMARY_PATH"
  --report-out "$REPORT_PATH"
  --agent-brief-out "$AGENT_BRIEF_PATH"
)
if [[ -n "$DOC_EVIDENCE_JSON" ]]; then
  RUN_ARGS+=(--doc-evidence-json "$DOC_EVIDENCE_JSON")
fi

"${RUN_ARGS[@]}"

pooh_runtime_inject_summary

python3 "$SCRIPT_DIR/validate_pydantic_temporal_summary.py" \
  --summary "$SUMMARY_PATH"

pooh_runtime_finalize

echo "Pydantic AI + Temporal hardgate baseline complete."
