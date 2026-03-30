# Synthesis policy

The machine rollup remains the only source of truth for:

- `overall_health`
- `coverage_status`
- `blocked / present / not-applicable / invalid / missing`

The richer synthesis layer must not recompute those states.
It may only organize evidence, explain cross-domain patterns, and prioritize action.

## Fixed cluster model

Do not invent new cluster names per run.
Use exactly these four clusters:

- `governance-and-boundaries`
  - `structure`
  - `contracts`
  - `pythonic-ddd-drift`
  - `module-shape`
  - `schema-governance`
- `runtime-correctness-and-failure-handling`
  - `distributed-side-effects`
  - `durable-agents`
  - `error-governance`
  - `silent-failure`
  - `frontend-regression`
- `engineering-quality-and-security`
  - `python-lint-format`
  - `ts-lint-format`
  - `security-posture`
- `surface-freshness-and-cleanup`
  - `llm-api-freshness`
  - `cleanup`

## Action ordering

Use this fixed priority order:

1. `dependency_status=blocked`
2. domains with `critical` / `high` or clear red verdicts
3. domains with `medium` or watch-level findings
4. trust-gap domains, especially `triage`
5. coverage-gap cleanup only when overall `coverage_status=partial`

Do not let cosmetic cleanup outrank dependency unblock or blocker-level correctness work.

## Trust interpretation

- `blocked` means the domain produced current-run artifacts but cannot be trusted because bootstrap/runtime failed or blocker evidence exists
- `triage` is a trust gap, not a verified clean result
- `not-applicable` is a legitimate child outcome and does not need action
- `missing` / `invalid` are evidence gaps first; treat them as action items only when the overall rollup is already partial

## Reporting stance

- Use child human reports and child agent briefs as supporting evidence, not as replacement truth
- If a child report or child brief is missing, write that down in `unknowns` and fall back to summary-level notes
- Preserve sharp child language where it is evidence-backed; do not flatten everything into generic governance prose
