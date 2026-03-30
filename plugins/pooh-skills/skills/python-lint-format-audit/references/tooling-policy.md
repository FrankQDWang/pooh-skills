# Tooling Policy

## Default stance

This audit only judges Python lint / format governance, and the preferred modern shape is:

- `uv` as the package-manager surface
- `ruff check` as the main lint entrypoint
- `ruff format --check` as the main formatting gate
- Ruff-owned import sorting instead of parallel `isort` truth

## Scoring bias

- `hardened`: Ruff is the only visible command-level truth and normal workflows enforce it.
- `enforced`: Ruff owns the main path, but there is still minor cleanup or edge coverage work left.
- `partial`: the repo still depends on legacy Black / isort / Flake8 surfaces, or the Ruff gate chain is incomplete.
- `missing`: no credible modern Python lint / format control surface is visible.

## Evidence to trust

1. `pyproject.toml`, `ruff.toml`, `.ruff.toml`
2. `.pre-commit-config.yaml`
3. CI workflow entries for `ruff check` and `ruff format --check`
4. task-runner entries in `Makefile`, `justfile`, or package scripts
5. `noqa`, `per-file-ignores`, `exclude`, and generated-path handling

## Out of scope

- type-system strictness
- dependency cleanup
- auto-fix policy
- architecture or boundary enforcement
