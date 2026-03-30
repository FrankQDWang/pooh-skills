---
name: openapi-jsonschema-governance-audit
description: Audits Python and TypeScript repos for modern OpenAPI and JSON Schema governance with explicit source-of-truth, lint, bundle, diff, and CI publication evidence. Use for schema governance review, ruleset ownership, breaking-change gate checks, and artifact-chain reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# OpenAPI JSON Schema Governance Audit

Use this skill when the repo carries OpenAPI or JSON Schema artifacts and the user wants to know whether those artifacts are actually governed instead of merely stored.

Do not use it for runtime validation, GraphQL, protobuf, codegen fixing, or auto-remediation.

## Core stance

- Scope is Python / TypeScript repos only, with `uv` and `pnpm` as the package-manager assumptions.
- Preferred modern governance evidence is a clear source spec plus reproducible lint, bundle, and diff steps.
- `Redocly`, `Spectral`, `ajv-cli`, and `check-jsonschema` are preferred probes, not the only acceptable brands.
- This skill only detects and reports. It does not rewrite specs or configs.

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

1. whether schema artifacts are parseable and governed by a reproducible lint/bundle path
2. whether there is an explicit ruleset layer instead of README-only policy
3. whether the canonical source is distinct from generated bundles or clients
4. whether breaking changes are blocked by a CI-visible diff gate
5. whether CI preserves enough publication or artifact evidence to explain failures later

## Workflow

1. Detect whether the repo has OpenAPI / JSON Schema surface. If not, return `not-applicable`.
2. Separate source specs from generated clients, bundles, and publication outputs.
3. Look for a versioned lint/bundle/ruleset chain.
4. Look for a CI-visible breaking-change detector.
5. Report source-of-truth confusion before tool-brand debates.

## Output rules

- Lead with whether canonical source ownership is clear.
- Keep artifact health, ruleset governance, diff gating, and CI publication as separate categories.
- Use the standard namespaced artifacts under `.repo-harness/skills/openapi-jsonschema-governance-audit/`.

## Safety rules

- Report only.
- Do not auto-fix specs, configs, or generated outputs.
- Do not treat generated clients as the canonical schema source.
- Do not mistake tool presence for enforced governance.
