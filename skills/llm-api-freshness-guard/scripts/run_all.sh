#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
      printf '%s\n' "Usage: bash scripts/run_all.sh [--doc-evidence-json path] [repo-root] [out-dir]" >&2
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

REPO_ROOT="${POSITIONAL[0]:-.}"
OUT_DIR="${POSITIONAL[1]:-${REPO_ROOT}/.repo-harness}"
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

pooh_runtime_update "running" "" "Collecting local LLM API signals and enforcing Context7-backed freshness verification."

COLLECT_ARGS=(
  python3
  "${SCRIPT_DIR}/collect_llm_api_signals.py"
  "${REPO_ROOT}"
  --json-out "${OUT_DIR}/llm-api-signals.json"
  --summary-out "$SUMMARY_PATH"
  --report-out "$REPORT_PATH"
  --agent-brief-out "$AGENT_BRIEF_PATH"
)
if [[ -n "$DOC_EVIDENCE_JSON" ]]; then
  COLLECT_ARGS+=(--doc-evidence-json "$DOC_EVIDENCE_JSON")
fi

"${COLLECT_ARGS[@]}"

pooh_runtime_inject_summary

python3 "${SCRIPT_DIR}/validate_llm_api_freshness_summary.py" "$SUMMARY_PATH"

pooh_runtime_finalize

echo "Wrote freshness artifacts to ${OUT_DIR}"
echo "Official success requires Context7-backed doc evidence via --doc-evidence-json; otherwise the wrapper emits a blocked result."
