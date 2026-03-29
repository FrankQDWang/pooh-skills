# Integration matrix

The orchestrator expects the following current-run machine-readable summaries in the repo-root `.repo-harness`.

| Domain | Skill name | Expected summary |
|---|---|---|
| structure | `dependency-audit` | `.repo-harness/repo-audit-summary.json` |
| contracts | `signature-contract-hardgate` | `.repo-harness/contract-hardgate-summary.json` |
| durable-agents | `pydantic-ai-temporal-hardgate` | `.repo-harness/pydantic-temporal-summary.json` |
| llm-api-freshness | `llm-api-freshness-guard` | `.repo-harness/llm-api-freshness-summary.json` |
| cleanup | `controlled-cleanup-hardgate` | `.repo-harness/controlled-cleanup-summary.json` |
| distributed-side-effects | `distributed-side-effect-hardgate` | `.repo-harness/distributed-side-effect-summary.json` |
| pythonic-ddd-drift | `pythonic-ddd-drift-audit` | `.repo-harness/pythonic-ddd-drift-summary.json` |

## Current-run contract

- The orchestrator deletes and recreates `.repo-harness` before spawning child audits.
- The orchestrator maintains `.repo-harness/repo-health-control-plane.json` as the live terminal view for the current run.
- Every child subagent must write fresh artifacts for the current run.
- The orchestrator may aggregate only files produced during the current run.
- Child skills may use their own local scripts or wrappers internally, but that is not the orchestrator contract.

## Coverage statuses

Use these statuses during collection and rollup:

- `present` - summary exists and parses
- `not-applicable` - summary exists and clearly declares `not-applicable`
- `invalid` - summary path exists but cannot be parsed or is untrustworthy for aggregation
- `missing` - no summary was produced at the expected path

The orchestrator should never pretend old artifacts count as current coverage.
