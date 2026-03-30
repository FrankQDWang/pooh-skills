---
name: python-lint-format-audit
description: Audits Python repos for modern Ruff-first lint and format governance on uv-managed toolchains. Use for Python lint/format review, Ruff migration readiness, suppression governance, and CI gate reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# Python Lint Format Audit

Use this skill when the repo has a real Python surface and the user wants to know whether lint and format control are actually modern, unified, and enforceable.

Do not use it for type-system policy, dependency cleanup, or auto-fixing style debt.

## Core stance

- Scope is Python only. Package-manager assumptions are `uv` only.
- Preferred target shape is modern Ruff-first governance.
- Legacy `Black` / `isort` / `Flake8` residue is drift, not an acceptable steady-state target.
- This skill only detects and reports. It does not rewrite config or auto-fix code.

## Read when needed

- [assets/human-report-template.md](assets/human-report-template.md)
- [assets/agent-brief-template.md](assets/agent-brief-template.md)
- [references/shared-output-contract.md](references/shared-output-contract.md)
- [references/shared-reporting-style.md](references/shared-reporting-style.md)
- [references/shared-runtime-artifact-contract.md](references/shared-runtime-artifact-contract.md)
- [references/tooling-policy.md](references/tooling-policy.md)
- [references/evaluation-matrix.md](references/evaluation-matrix.md)
- [references/evals.md](references/evals.md)

## What to judge

Report five things, in this order:

1. whether Ruff is the single visible command-level truth
2. whether config ownership is coherent instead of split across old tools
3. whether `ruff check` and `ruff format --check` are on the normal CI / pre-commit path
4. whether `noqa`, `per-file-ignores`, and broad excludes are still reviewable
5. whether generated or vendor paths are isolated instead of polluting the baseline

## Workflow

1. Detect whether the repo has a Python surface. If not, return `not-applicable`.
2. Find Ruff config and separate it from legacy config residue.
3. Check for real workflow evidence in CI, pre-commit, or task runners.
4. Count suppressions and broad excludes before trusting a “green” baseline.
5. Call out legacy command activity as control-surface drift, not as success.

## Output rules

- Keep the report sharp and evidence-based.
- Lead with whether this is a modern Ruff-governed repo or a split-truth repo.
- Keep the agent brief short: target shape, validation gates, immediate actions.
- Use the standard namespaced artifacts under `.repo-harness/skills/python-lint-format-audit/`.

## Safety rules

- Report only.
- Do not auto-fix code, config, hooks, or workflows.
- Do not treat legacy tool presence as “good enough” just because it still runs.
- Do not confuse lint/format control with type or runtime contract enforcement.
