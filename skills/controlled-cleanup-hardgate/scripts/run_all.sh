#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_all.sh [--strict-removal-targets] [repo-root] [out-dir]

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
OUT_DIR="${POSITIONAL[1]:-$REPO_ROOT/.repo-harness}"
SUMMARY_PATH="$OUT_DIR/controlled-cleanup-summary.json"
LINKCHECK_PATH="$OUT_DIR/controlled-cleanup-linkcheck.json"

mkdir -p "$OUT_DIR"

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
    --out "$SUMMARY_PATH"

run_step "summary validation" \
  python3 "$SCRIPT_DIR/validate_cleanup_summary.py" \
    --summary "$SUMMARY_PATH"

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

exit "$OVERALL_STATUS"
