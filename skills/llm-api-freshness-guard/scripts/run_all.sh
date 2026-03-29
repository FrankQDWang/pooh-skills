#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${2:-${REPO_ROOT}/.repo-harness}"
source "$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

SUMMARY_PATH="${OUT_DIR}/llm-api-freshness-summary.json"
REPORT_PATH="${OUT_DIR}/llm-api-freshness-report.md"
AGENT_BRIEF_PATH="${OUT_DIR}/llm-api-freshness-agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"

mkdir -p "${OUT_DIR}"

pooh_runtime_prepare \
  "llm-api-freshness-guard" \
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

pooh_runtime_update "running" "" "Collecting local LLM API signals for Context7-backed verification."

python3 "${SCRIPT_DIR}/collect_llm_api_signals.py" \
  "${REPO_ROOT}" \
  --json-out "${OUT_DIR}/llm-api-signals.json" \
  --summary-out "$SUMMARY_PATH" \
  --report-out "$REPORT_PATH" \
  --agent-brief-out "$AGENT_BRIEF_PATH"

pooh_runtime_inject_summary

python3 "${SCRIPT_DIR}/validate_llm_api_freshness_summary.py" "$SUMMARY_PATH"

pooh_runtime_finalize

echo "Wrote local-scan-only freshness artifacts to ${OUT_DIR}"
echo "This helper still produces a local triage baseline; the official success path remains a Context7-backed verified run."
