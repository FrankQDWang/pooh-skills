# Integration matrix

The orchestrator expects one namespaced child artifact directory per managed audit skill:

- `.repo-harness/skills/<skill-id>/runtime.json`
- `.repo-harness/skills/<skill-id>/summary.json`
- `.repo-harness/skills/<skill-id>/report.md`
- `.repo-harness/skills/<skill-id>/agent-brief.md`

Repo-level rollup artifacts stay at the root of `.repo-harness`:

- `repo-health-control-plane.json`
- `repo-health-shared-bootstrap.json`
- `repo-health-summary.json`
- `repo-health-evidence.json`
- `repo-health-report.md`
- `repo-health-agent-brief.md`

## Managed domains

| Cluster | Domain | Skill name | Child artifact directory |
|---|---|---|---|
| governance-and-boundaries | structure | `dependency-audit` | `.repo-harness/skills/dependency-audit/` |
| governance-and-boundaries | contracts | `signature-contract-hardgate` | `.repo-harness/skills/signature-contract-hardgate/` |
| governance-and-boundaries | pythonic-ddd-drift | `pythonic-ddd-drift-audit` | `.repo-harness/skills/pythonic-ddd-drift-audit/` |
| governance-and-boundaries | module-shape | `module-shape-hardgate` | `.repo-harness/skills/module-shape-hardgate/` |
| runtime-correctness-and-failure-handling | distributed-side-effects | `distributed-side-effect-hardgate` | `.repo-harness/skills/distributed-side-effect-hardgate/` |
| runtime-correctness-and-failure-handling | durable-agents | `pydantic-ai-temporal-hardgate` | `.repo-harness/skills/pydantic-ai-temporal-hardgate/` |
| runtime-correctness-and-failure-handling | error-governance | `error-governance-hardgate` | `.repo-harness/skills/error-governance-hardgate/` |
| runtime-correctness-and-failure-handling | silent-failure | `overdefensive-silent-failure-hardgate` | `.repo-harness/skills/overdefensive-silent-failure-hardgate/` |
| surface-freshness-and-cleanup | llm-api-freshness | `llm-api-freshness-guard` | `.repo-harness/skills/llm-api-freshness-guard/` |
| surface-freshness-and-cleanup | cleanup | `controlled-cleanup-hardgate` | `.repo-harness/skills/controlled-cleanup-hardgate/` |

## Current-run contract

- The orchestrator deletes and recreates `.repo-harness` before spawning child audits.
- The orchestrator bootstraps the shared `.pooh-runtime` toolchain before spawning child audits.
- The orchestrator generates one `run_id` during reset and treats it as the current-run identity.
- Every child runtime sidecar and child summary must carry the current `run_id`.
- The orchestrator maintains `.repo-harness/repo-health-control-plane.json` as the live terminal view for the current run.
- The orchestrator may aggregate only child summaries whose `run_id` matches the current run.
- The richer synthesis layer may read child human reports and agent briefs, but it must still treat the machine summary as the source of truth for state.
- Child skills may use their own local scripts or wrappers internally, but that is not the orchestrator contract.
- Shared tool versions come only from `.pooh-runtime/python-toolchain/uv.lock` and `.pooh-runtime/node-toolchain/pnpm-lock.yaml`.
- Python audit CLIs come only from the shared `uv` `audit` dependency group; TS/Node audit CLIs come only from shared `pnpm` `devDependencies`.
- `lychee` and `Vale` remain docs-only hard-dependency exceptions managed by the shared runtime, not by per-skill package manifests.

## Coverage statuses

Use these statuses during collection and rollup:

- `present` - summary exists, parses, and matches the current run
- `blocked` - summary exists, parses, and its dependency bootstrap was blocked
- `not-applicable` - summary exists and clearly declares `not-applicable`
- `invalid` - summary path exists but cannot be parsed or does not belong to the current run
- `missing` - no summary was produced at the expected path

The orchestrator should never pretend old artifacts count as current coverage.
