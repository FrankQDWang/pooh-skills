# Integration matrix

The orchestrator expects the following current-run artifacts in the repo-root `.repo-harness`.

| Domain | Skill name | Expected summary | Expected human report | Expected agent brief |
|---|---|---|---|---|
| structure | `dependency-audit` | `.repo-harness/repo-audit-summary.json` | `.repo-harness/repo-audit-report.md` | `.repo-harness/repo-audit-agent-brief.md` |
| contracts | `signature-contract-hardgate` | `.repo-harness/contract-hardgate-summary.json` | `.repo-harness/contract-hardgate-human-report.md` | `.repo-harness/contract-hardgate-agent-brief.md` |
| durable-agents | `pydantic-ai-temporal-hardgate` | `.repo-harness/pydantic-temporal-summary.json` | `.repo-harness/pydantic-temporal-human-report.md` | `.repo-harness/pydantic-temporal-agent-brief.md` |
| llm-api-freshness | `llm-api-freshness-guard` | `.repo-harness/llm-api-freshness-summary.json` | `.repo-harness/llm-api-freshness-report.md` | `.repo-harness/llm-api-freshness-agent-brief.md` |
| cleanup | `controlled-cleanup-hardgate` | `.repo-harness/controlled-cleanup-summary.json` | `.repo-harness/controlled-cleanup-report.md` | `.repo-harness/controlled-cleanup-agent-brief.md` |
| distributed-side-effects | `distributed-side-effect-hardgate` | `.repo-harness/distributed-side-effect-summary.json` | `.repo-harness/distributed-side-effect-report.md` | `.repo-harness/distributed-side-effect-agent-brief.md` |
| pythonic-ddd-drift | `pythonic-ddd-drift-audit` | `.repo-harness/pythonic-ddd-drift-summary.json` | `.repo-harness/pythonic-ddd-drift-report.md` | `.repo-harness/pythonic-ddd-drift-agent-brief.md` |

## Current-run contract

- The orchestrator deletes and recreates `.repo-harness` before spawning child audits.
- The orchestrator bootstraps the shared `.pooh-runtime` toolchain before spawning child audits.
- The orchestrator maintains `.repo-harness/repo-health-control-plane.json` as the live terminal view for the current run.
- Every child subagent must write fresh artifacts for the current run.
- The orchestrator may aggregate only files produced during the current run.
- The richer synthesis layer may read child human reports and agent briefs, but it must still treat the machine summary as the source of truth for state.
- Child skills may use their own local scripts or wrappers internally, but that is not the orchestrator contract.
- Shared tool versions come only from `.pooh-runtime/python-toolchain/uv.lock` and `.pooh-runtime/node-toolchain/pnpm-lock.yaml`.

## Coverage statuses

Use these statuses during collection and rollup:

- `present` - summary exists and parses
- `not-applicable` - summary exists and clearly declares `not-applicable`
- `invalid` - summary path exists but cannot be parsed or is untrustworthy for aggregation
- `missing` - no summary was produced at the expected path

The orchestrator should never pretend old artifacts count as current coverage.
