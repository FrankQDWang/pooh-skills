---
name: ts-frontend-regression-audit
description: Audits TypeScript frontend repos for modern browser-real regression coverage, boundary mocks, accessibility automation, visual evidence, and CI artifact discipline. Use for frontend regression review, Playwright or browser-mode coverage checks, MSW-style boundary mocking, and test evidence reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# TS Frontend Regression Audit

Use this skill when the repo has a browser-facing TypeScript frontend surface and the user wants to know whether regression control is actually guarding browser behavior.

Do not use it for lint/format policy, schema governance, performance auditing, or auto-fixing tests.

## Core stance

- Scope is browser-facing TypeScript frontend only, with `pnpm` as the package-manager assumption.
- Preferred modern evidence is a real-browser lane plus explicit boundary mocks, accessibility automation, visual baselines, and CI artifacts.
- `Playwright`, browser-mode `Vitest`, `MSW`, and `axe` are preferred probes, not the only acceptable brands.
- This skill only detects and reports. It does not rewrite tests or workflows.

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

1. whether regression control runs in a real browser instead of only jsdom
2. whether request mocking lives at the boundary instead of inside implementation details
3. whether accessibility automation exists in the main browser lane
4. whether visual regression evidence is versioned and reviewable
5. whether CI preserves traces, screenshots, reports, and retry evidence

## Workflow

1. Detect whether the repo has a browser-facing frontend surface. If not, return `not-applicable`.
2. Separate browser-real evidence from jsdom-only evidence.
3. Separate request-boundary mocks from internal function mocking.
4. Look for accessibility and visual signals in the same regression lane.
5. Treat missing CI artifacts as trust erosion even when tests exist locally.

## Output rules

- Lead with whether this is browser-real or still jsdom-dominated.
- Keep browser fidelity, boundary mocks, accessibility, visual evidence, and CI traceability separate.
- Use the standard namespaced artifacts under `.repo-harness/skills/ts-frontend-regression-audit/`.

## Safety rules

- Report only.
- Do not auto-fix tests, workflows, or snapshots.
- Do not treat internal monkey-patching as equivalent to request-boundary control.
- Do not mistake local test commands for durable CI evidence.
