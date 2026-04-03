#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_REPO="${1:-$REPO_ROOT}"
OUT_DIR="${2:-$TARGET_REPO/.repo-harness}"

mkdir -p "$OUT_DIR"
export PYTHONDONTWRITEBYTECODE=1

python3 "$SCRIPT_DIR/check_skill_fleet.py" \
  --repo "$TARGET_REPO" \
  --mode strict \
  --json-out "$OUT_DIR/skill-fleet-strictcheck.json"

python3 "$SCRIPT_DIR/sync_shared_skill_refs.py" --check
python3 "$SCRIPT_DIR/check_repo_plugin.py" \
  --repo "$TARGET_REPO" \
  --json-out "$OUT_DIR/repo-plugin-check.json"
python3 "$SCRIPT_DIR/run_shared_runtime_regressions.py"
python3 "$SCRIPT_DIR/run_module_shape_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_legacy_surface_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_controlled_cleanup_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_secrets_and_hardcode_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_test_quality_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_new_audit_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_repo_health_fixture_regressions.py"
python3 "$SCRIPT_DIR/run_child_wrapper_smoke_matrix.py"
python3 "$SCRIPT_DIR/run_control_plane_renderer_regressions.py"
python3 "$SCRIPT_DIR/run_home_local_plugin_installer_regressions.py"

echo "Skill fleet harness passed."
