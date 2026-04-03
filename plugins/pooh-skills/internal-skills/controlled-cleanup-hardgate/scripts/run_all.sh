#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/../../.pooh-runtime/bin/runtime_wrapper.sh"

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [--strict-removal-targets] [repo-root] [harness-dir]

Examples:
  bash scripts/run_all.sh .
  bash scripts/run_all.sh --strict-removal-targets .
  bash scripts/run_all.sh . .repo-harness
EOF
}

STRICT_REMOVAL_TARGETS=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict-removal-targets)
      STRICT_REMOVAL_TARGETS=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        POSITIONAL+=("$1")
        shift
      done
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

REPO_ROOT="${POSITIONAL[0]:-.}"
HARNESS_DIR="${POSITIONAL[1]:-$REPO_ROOT/.repo-harness}"
OUT_DIR="$HARNESS_DIR/skills/controlled-cleanup-hardgate"
EXTRA_DIR="$OUT_DIR/extra"
SUMMARY_PATH="$OUT_DIR/summary.json"
LINKCHECK_PATH="$EXTRA_DIR/linkcheck.json"
REPORT_PATH="$OUT_DIR/report.md"
AGENT_BRIEF_PATH="$OUT_DIR/agent-brief.md"
MANIFEST_PATH="$SCRIPT_DIR/../assets/runtime-dependencies.json"

mkdir -p "$OUT_DIR" "$EXTRA_DIR"

pooh_runtime_prepare \
  "controlled-cleanup-hardgate" \
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

pooh_runtime_update "running" "" "Running controlled cleanup scan."

OVERALL_STATUS=0

run_step() {
  local label="$1"
  shift
  if "$@"; then
    printf 'ok: %s\n' "$label"
    return 0
  else
    local exit_code=$?
    OVERALL_STATUS=1
    printf 'error: %s (exit %s)\n' "$label" "$exit_code" >&2
    return 0
  fi
}

run_step "cleanup scan" \
  python3 "$SCRIPT_DIR/run_cleanup_scan.py" \
    --repo "$REPO_ROOT" \
    --out "$SUMMARY_PATH" \
    --report-out "$REPORT_PATH" \
    --agent-brief-out "$AGENT_BRIEF_PATH"

if [[ -f "$SUMMARY_PATH" ]]; then
  pooh_runtime_inject_summary
  run_step "summary validation" \
    python3 "$SCRIPT_DIR/validate_cleanup_summary.py" \
      --summary "$SUMMARY_PATH"
fi

REMOVAL_ARGS=(
  python3
  "$SCRIPT_DIR/check_removal_targets.py"
  --summary "$SUMMARY_PATH"
)
if [[ "$STRICT_REMOVAL_TARGETS" -eq 1 ]]; then
  REMOVAL_ARGS+=(--strict)
fi
run_step "removal target checks" "${REMOVAL_ARGS[@]}"

run_step "documentation link checks" \
  python3 "$SCRIPT_DIR/check_doc_links.py" \
    --repo "$REPO_ROOT" \
    --out "$LINKCHECK_PATH"

if [[ -f "$SUMMARY_PATH" ]]; then
  pooh_runtime_finalize
fi

exit "$OVERALL_STATUS"
