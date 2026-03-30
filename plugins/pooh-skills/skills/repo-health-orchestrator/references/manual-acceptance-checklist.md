# Manual acceptance checklist

Use this checklist only for runtime behaviors that deterministic regressions cannot prove.

## Goal

Prove one real orchestrator run can:

- generate a fresh `run_id`
- reset `.repo-harness`
- bootstrap the shared toolchain once
- spawn all 15 child subagents in parallel
- redraw the live terminal control plane as workers move through `waiting / preflight / bootstrapping / running / complete / blocked / invalid / missing / not-applicable`
- finalize with one root machine summary, one evidence file, one human report, and one agent brief

## Manual steps

1. Start from a repo root without trusting any existing `.repo-harness`.
2. Explicitly invoke `$repo-health-orchestrator`.
3. Confirm `.repo-harness/repo-health-control-plane.json` appears first and contains a non-empty `run_id`.
4. Confirm `.repo-harness/repo-health-shared-bootstrap.json` appears before child summaries.
5. Confirm every managed skill gets its own child directory under `.repo-harness/skills/<skill-id>/`.
6. During the run, confirm the terminal redraw shows all 15 worker cards and does not collapse into snapshot logging.
7. Confirm each worker card eventually lands in one final state: `complete`, `blocked`, `invalid`, `missing`, or `not-applicable`.
8. Confirm every child directory contains `runtime.json`, `summary.json`, `report.md`, and `agent-brief.md`.
9. Confirm `repo-health-summary.json`, `repo-health-evidence.json`, `repo-health-report.md`, and `repo-health-agent-brief.md` exist at the `.repo-harness` root.
10. Confirm `repo-health-summary.json` `run_id` matches every child `summary.json` and `runtime.json`.
11. Confirm the final control-plane frame shows `overall_health`, `coverage_status`, `Missing`, `Invalid`, and the action queue.

## Expected pass condition

- One current-run `run_id`
- 15 current-run child namespaces under `.repo-harness/skills/`
- 6 repo-level orchestrator artifacts at `.repo-harness/`
- final control-plane frame matches the machine summary instead of stale runtime guesses
