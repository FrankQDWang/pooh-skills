#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_REPO="${1:-$REPO_ROOT}"
OUT_DIR="${2:-$TARGET_REPO/.repo-harness}"

mkdir -p "$OUT_DIR"

python3 "$SCRIPT_DIR/check_skill_fleet.py" \
  --repo "$TARGET_REPO" \
  --mode strict \
  --json-out "$OUT_DIR/skill-fleet-strictcheck.json"

python3 "$SCRIPT_DIR/sync_shared_skill_refs.py" --check
python3 "$SCRIPT_DIR/run_module_shape_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_repo_health_fixture_regressions.py"

echo "Skill fleet harness passed."
