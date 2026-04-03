---
name: test-quality-audit
description: Audits Python and TypeScript repos for high-signal test governance problems such as missing CI test gates, placeholder assertions, skip or retry sprawl, internal-logic over-mocking, and missing failure-path evidence. Use for test quality review, CI gate sanity checks, placeholder test detection, mock discipline review, and repo-health reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---

# Test Quality Audit

Use this skill when the repo has Python or TypeScript code and the user wants to know whether the test suite is teaching the right habits instead of just producing a green badge.

Do not use it for browser-real frontend regression quality, CI trace or screenshot artifact review, Temporal replay or time-skipping verification, lint policy, or auto-fixing tests.

## Core stance

- Scope stays narrow: real CI test gate presence, placeholder tests, skip or xfail or retry governance, internal-logic over-mocking, and failure-path evidence.
- This skill does not score coverage percentages and does not pretend test line counts prove quality.
- This skill does not replace `ts-frontend-regression-audit` for browser fidelity or `pydantic-ai-temporal-hardgate` for durable verification semantics.
- This skill only detects and reports. It does not rewrite tests, CI workflows, or mocks.

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

1. whether CI runs a real test gate instead of relying only on local scripts
2. whether the suite contains placeholder or tautological assertions
3. whether skip, xfail, or retry usage is becoming normal instead of exceptional
4. whether tests lean too heavily on internal-logic mocking instead of exercising real behavior
5. whether failure paths are tested explicitly instead of only happy paths

## Workflow

1. Confirm the repo has Python or TypeScript code or tests. If not, return `not-applicable`.
2. Detect whether CI config shows a real automated test gate.
3. Scan test files for placeholder assertions, skip or retry patterns, internal-mock drift, and failure-path evidence.
4. Keep frontend browser fidelity and Temporal verification concerns out of scope; only mention those boundaries when clarifying that another specialist owns them.
5. Produce the standard namespaced artifacts under `.repo-harness/skills/test-quality-audit/`.

## Safety rules

- Report only.
- Do not auto-fix tests or workflows.
- Do not use coverage ratios or raw test counts as verdict shortcuts.
- Do not treat browser-fidelity gaps as this skill's core finding; hand that to `ts-frontend-regression-audit`.
- Do not treat Temporal replay or time-skipping gaps as this skill's finding; hand that to `pydantic-ai-temporal-hardgate`.
