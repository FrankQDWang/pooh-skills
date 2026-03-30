#!/usr/bin/env bash
set -euo pipefail

pooh_runtime_prepare() {
  local skill_id="$1"
  local script_dir="$2"
  local repo_root="$3"
  local out_dir="$4"
  local summary_path="$5"
  local report_path="$6"
  local agent_brief_path="$7"
  local manifest_path="$8"

  POOH_RUNTIME_SKILL_ID="$skill_id"
  POOH_RUNTIME_SCRIPT_DIR="$script_dir"
  POOH_RUNTIME_REPO_ROOT="$repo_root"
  POOH_RUNTIME_OUT_DIR="$out_dir"
  POOH_RUNTIME_SUMMARY_PATH="$summary_path"
  POOH_RUNTIME_REPORT_PATH="$report_path"
  POOH_RUNTIME_AGENT_BRIEF_PATH="$agent_brief_path"
  POOH_RUNTIME_MANIFEST_PATH="$manifest_path"
  POOH_RUNTIME_ROOT="$(CDPATH= cd -- "$script_dir/../../.pooh-runtime" && pwd)"
  POOH_RUNTIME_BIN="$POOH_RUNTIME_ROOT/bin/runtime_contract.py"
  POOH_RUNTIME_STATE="$out_dir/${skill_id}-runtime.json"
  POOH_RUNTIME_PY_BIN="$POOH_RUNTIME_ROOT/python-toolchain/.venv/bin"
  POOH_RUNTIME_NODE_BIN="$POOH_RUNTIME_ROOT/node-toolchain/node_modules/.bin"
  POOH_RUNTIME_DOCS_BIN="$POOH_RUNTIME_ROOT/bin"

  [[ -f "$POOH_RUNTIME_BIN" ]] || {
    printf 'Error: shared runtime not found at %s\n' "$POOH_RUNTIME_BIN" >&2
    return 1
  }
  [[ -f "$POOH_RUNTIME_MANIFEST_PATH" ]] || {
    printf 'Error: runtime manifest not found at %s\n' "$POOH_RUNTIME_MANIFEST_PATH" >&2
    return 1
  }
  mkdir -p "$POOH_RUNTIME_OUT_DIR"
}

pooh_runtime_export_path() {
  local segments=()
  [[ -d "$POOH_RUNTIME_PY_BIN" ]] && segments+=("$POOH_RUNTIME_PY_BIN")
  [[ -d "$POOH_RUNTIME_NODE_BIN" ]] && segments+=("$POOH_RUNTIME_NODE_BIN")
  [[ -d "$POOH_RUNTIME_DOCS_BIN" ]] && segments+=("$POOH_RUNTIME_DOCS_BIN")
  if [[ "${#segments[@]}" -gt 0 ]]; then
    export PATH="$(IFS=:; printf '%s' "${segments[*]}"):$PATH"
  fi
}

pooh_runtime_bootstrap_or_block() {
  local exit_code=0
  python3 "$POOH_RUNTIME_BIN" bootstrap \
    --skill-id "$POOH_RUNTIME_SKILL_ID" \
    --manifest "$POOH_RUNTIME_MANIFEST_PATH" \
    --repo "$POOH_RUNTIME_REPO_ROOT" \
    --state "$POOH_RUNTIME_STATE" \
    --summary-path "$POOH_RUNTIME_SUMMARY_PATH" \
    --report-path "$POOH_RUNTIME_REPORT_PATH" \
    --agent-brief-path "$POOH_RUNTIME_AGENT_BRIEF_PATH" || exit_code=$?

  if [[ "$exit_code" -eq 10 ]]; then
    python3 "$POOH_RUNTIME_BIN" blocked-artifacts \
      --skill-id "$POOH_RUNTIME_SKILL_ID" \
      --repo "$POOH_RUNTIME_REPO_ROOT" \
      --state "$POOH_RUNTIME_STATE" \
      --summary-path "$POOH_RUNTIME_SUMMARY_PATH" \
      --report-path "$POOH_RUNTIME_REPORT_PATH" \
      --agent-brief-path "$POOH_RUNTIME_AGENT_BRIEF_PATH"
    return 10
  fi

  pooh_runtime_export_path

  return "$exit_code"
}

pooh_runtime_update() {
  local stage="$1"
  local dependency_status="$2"
  local current_action="$3"

  local cmd=(
    python3
    "$POOH_RUNTIME_BIN"
    update-sidecar
    --state "$POOH_RUNTIME_STATE"
    --summary-path "$POOH_RUNTIME_SUMMARY_PATH"
    --report-path "$POOH_RUNTIME_REPORT_PATH"
    --agent-brief-path "$POOH_RUNTIME_AGENT_BRIEF_PATH"
  )

  if [[ -n "$stage" ]]; then
    cmd+=(--stage "$stage")
  fi
  if [[ -n "$dependency_status" ]]; then
    cmd+=(--dependency-status "$dependency_status")
  fi
  if [[ -n "$current_action" ]]; then
    cmd+=(--current-action "$current_action")
  fi

  "${cmd[@]}"
}

pooh_runtime_inject_summary() {
  python3 "$POOH_RUNTIME_BIN" inject-summary \
    --state "$POOH_RUNTIME_STATE" \
    --summary "$POOH_RUNTIME_SUMMARY_PATH"
}

pooh_runtime_finalize() {
  python3 "$POOH_RUNTIME_BIN" finalize-sidecar \
    --state "$POOH_RUNTIME_STATE" \
    --summary "$POOH_RUNTIME_SUMMARY_PATH"
}
