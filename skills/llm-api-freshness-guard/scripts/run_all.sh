#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${REPO_ROOT}/.repo-harness"

mkdir -p "${OUT_DIR}"

python3 "${SCRIPT_DIR}/collect_llm_api_signals.py" "${REPO_ROOT}"   --json-out "${OUT_DIR}/llm-api-signals.json"   --summary-out "${OUT_DIR}/llm-api-freshness-summary.json"   --report-out "${OUT_DIR}/llm-api-freshness-report.md"   --agent-brief-out "${OUT_DIR}/llm-api-freshness-agent-brief.md"

python3 "${SCRIPT_DIR}/validate_llm_api_freshness_summary.py"   "${OUT_DIR}/llm-api-freshness-summary.json"

echo "Wrote local-scan-only freshness artifacts to ${OUT_DIR}"
echo "This wrapper does not verify live docs."
echo "For a real freshness verdict, run the skill with Context7 available."
