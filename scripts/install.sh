#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"
RUNTIME_DIR="$SKILLS_DIR/.pooh-runtime"

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/install.sh [--all] [--target codex] [skill-id ...]
  ./scripts/install.sh --list

Examples:
  ./scripts/install.sh dependency-audit
  ./scripts/install.sh pydantic-ai-temporal-hardgate
  ./scripts/install.sh controlled-cleanup-hardgate
  ./scripts/install.sh distributed-side-effect-hardgate
  ./scripts/install.sh pythonic-ddd-drift-audit
  ./scripts/install.sh llm-api-freshness-guard
  ./scripts/install.sh error-governance-hardgate
  ./scripts/install.sh overdefensive-silent-failure-hardgate
  ./scripts/install.sh repo-health-orchestrator
  ./scripts/install.sh --all
  ./scripts/install.sh --target codex dependency-audit
EOF
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

list_skills() {
  find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d | sort | while IFS= read -r dir; do
    if [[ -f "$dir/SKILL.md" ]]; then
      basename "$dir"
    fi
  done
}

gather_all_skills() {
  local dir
  while IFS= read -r dir; do
    if [[ -f "$dir/SKILL.md" ]]; then
      SKILLS_TO_INSTALL+=("$(basename "$dir")")
    fi
  done < <(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
}

target_root_for() {
  local target="$1"
  case "$target" in
    codex)
      printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills"
      ;;
    claude)
      fail "Claude target is no longer supported"
      ;;
    *)
      fail "Unsupported target: $target"
      ;;
  esac
}

install_shared_runtime() {
  local target="$1"
  local target_root
  local target_dir

  [[ -d "$RUNTIME_DIR" ]] || fail "Missing shared runtime directory: $RUNTIME_DIR"

  target_root="$(target_root_for "$target")"
  target_dir="$target_root/.pooh-runtime"
  mkdir -p "$target_root"
  rm -rf "$target_dir"
  cp -R "$RUNTIME_DIR" "$target_dir"
  find "$target_dir" \( -type d -name '__pycache__' -o -type f -name '*.pyc' \) -exec rm -rf {} +
  printf 'Installed shared runtime -> %s\n' "$target_dir"
}

install_skill() {
  local skill_id="$1"
  local target="$2"
  local src_dir="$SKILLS_DIR/$skill_id"
  local target_root
  local target_dir

  [[ -d "$src_dir" ]] || fail "Skill not found: $skill_id"
  [[ -f "$src_dir/SKILL.md" ]] || fail "Missing SKILL.md for skill: $skill_id"

  target_root="$(target_root_for "$target")"

  target_dir="$target_root/$skill_id"
  mkdir -p "$target_root"
  rm -rf "$target_dir"
  cp -R "$src_dir" "$target_dir"
  find "$target_dir" \( -type d -name '__pycache__' -o -type f -name '*.pyc' \) -exec rm -rf {} +
  printf 'Installed %s -> %s\n' "$skill_id" "$target_dir"
}

LIST_ONLY=0
INSTALL_ALL=0
TARGETS=()
SKILLS_TO_INSTALL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)
      LIST_ONLY=1
      shift
      ;;
    --all)
      INSTALL_ALL=1
      shift
      ;;
    --target)
      [[ $# -ge 2 ]] || fail "--target requires a value"
      TARGETS+=("$2")
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      SKILLS_TO_INSTALL+=("$1")
      shift
      ;;
  esac
done

if [[ "$LIST_ONLY" -eq 1 ]]; then
  list_skills
  exit 0
fi

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  TARGETS=("codex")
fi

if [[ "$INSTALL_ALL" -eq 1 ]]; then
  if [[ "${#SKILLS_TO_INSTALL[@]}" -ne 0 ]]; then
    fail "--all cannot be combined with explicit skill ids"
  fi
  gather_all_skills
fi

if [[ "${#SKILLS_TO_INSTALL[@]}" -eq 0 ]]; then
  gather_all_skills
fi

if [[ "${#SKILLS_TO_INSTALL[@]}" -eq 0 ]]; then
  fail "No installable skills found under $SKILLS_DIR"
fi

for target in "${TARGETS[@]}"; do
  install_shared_runtime "$target"
  for skill_id in "${SKILLS_TO_INSTALL[@]}"; do
    install_skill "$skill_id" "$target"
  done
done
