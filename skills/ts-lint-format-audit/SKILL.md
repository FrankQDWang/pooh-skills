---
name: ts-lint-format-audit
description: Audits TypeScript repos for modern Biome-first lint and format governance plus typed-lint discipline on pnpm-managed toolchains. Use for TS lint/format review, Biome adoption, typed ESLint wiring, workspace coverage, and suppression governance. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# TS Lint Format Audit

Use this skill when the repo has a real TypeScript surface and the user wants to know whether lint and format control are modern, consolidated, and believable at workspace scale.

Do not use it for browser regression, schema governance, dependency cleanup, or auto-fixing style debt.

## Core stance

- Scope is TypeScript only. Package-manager assumptions are `pnpm` only.
- Preferred target shape is modern `Biome` for style plus typed ESLint for semantic lint.
- Legacy `ESLint + Prettier` style ownership counts as drift, not the preferred steady-state.
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

1. whether Biome is the clear style-layer truth
2. whether typed lint exists as a separate semantic layer wired to real project types
3. whether workspace-wide coverage is real instead of package-by-package drift
4. whether suppressions are still sparse enough to review directly
5. whether the normal CI path actually enforces the visible lint stack

## Workflow

1. Detect whether the repo has a TypeScript surface. If not, return `not-applicable`.
2. Separate Biome style ownership from typed ESLint semantic checks.
3. Check workspace-scale entrypoints instead of trusting single-package examples.
4. Count `eslint-disable`, `@ts-ignore`, and `@ts-expect-error` before trusting a green baseline.
5. Treat legacy style ownership as partial even when it is still actively used.

## Output rules

- Lead with whether this repo is Biome-first or still split across older style tools.
- Keep typed lint separate from style ownership in both report and brief.
- Use the standard namespaced artifacts under `.repo-harness/skills/ts-lint-format-audit/`.

## Safety rules

- Report only.
- Do not auto-fix code, config, hooks, or workflows.
- Do not treat `tsc` as a replacement for typed lint governance.
- Do not blur style-layer control with browser-test or runtime contract policy.
