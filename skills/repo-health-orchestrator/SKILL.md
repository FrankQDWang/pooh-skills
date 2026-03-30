---
name: repo-health-orchestrator
description: Coordinates installed pooh-skills audits through subagents, gathers their current-run machine-readable summaries, and produces one unified repository health report plus an agent action queue. Use for 完整仓库体检、multi-skill audit rollup、release gate prep、AI coding治理总报告、quarterly repo health review. Prefer explicit invocation for full-fleet audit runs.
---

# Repo Health Orchestrator

This skill is the coordinator, not the specialist.

Its job is to launch the focused audit skills as parallel subagents, collect their current-run artifacts, and turn them into one executive diagnosis instead of seven unrelated reports.

## When to use this

Use this skill when the user wants:

- one combined repo health report
- a governance rollup across several audit skills
- an AI-coding state-of-the-repo snapshot
- a prioritized action queue across structure, contracts, durable agents, LLM API freshness, distributed consistency, cleanup, and Pythonic drift
- a repeatable whole-repo run that ends in one machine summary, one evidence file, one human report, and one agent brief

## Do not use this

Do not use this skill when the user only needs:

- one narrow audit
- one immediate fix
- one local scan with no rollup need

## Required environment

This skill is Codex subagent-only.

If the Codex runtime cannot spawn subagents, say so plainly and stop.
Do not fall back to shell orchestration.
Do not pretend an old `.repo-harness` directory counts as current coverage.
Write blocked repo-health artifacts when orchestrator preflight itself is blocked.

## Expected child domains

This skill coordinates these seven child audits:

- `dependency-audit` → `.repo-harness/repo-audit-summary.json`
- `signature-contract-hardgate` → `.repo-harness/contract-hardgate-summary.json`
- `pydantic-ai-temporal-hardgate` → `.repo-harness/pydantic-temporal-summary.json`
- `llm-api-freshness-guard` → `.repo-harness/llm-api-freshness-summary.json`
- `controlled-cleanup-hardgate` → `.repo-harness/controlled-cleanup-summary.json`
- `distributed-side-effect-hardgate` → `.repo-harness/distributed-side-effect-summary.json`
- `pythonic-ddd-drift-audit` → `.repo-harness/pythonic-ddd-drift-summary.json`

It is okay if a child domain concludes `not-applicable`.
It is not okay to hide missing or invalid coverage.

## Reading map

Read only what is needed.

- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `assets/repo-health-summary.schema.json`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/integration-matrix.md`
- `references/synthesis-policy.md`
- `references/verdict-policy.md`
- `scripts/aggregate_repo_health.py`
- `scripts/bootstrap_shared_toolchain.py`
- `scripts/control_plane_state.py`
- `scripts/render_control_plane.py`
- `scripts/repo_health_catalog.py`
- `scripts/synthesize_repo_health.py`
- `scripts/validate_repo_health_summary.py`

## Operating stance

- Start from an empty `.repo-harness` every run.
- Treat `.repo-harness` as output-only.
- Maintain `.repo-harness/repo-health-control-plane.json` as the live terminal control-plane state for the current run.
- Treat `.repo-harness/<skill-id>-runtime.json` as the live sidecar for each child skill's `preflight / bootstrapping / running / blocked / complete` state.
- Launch all seven child domains before waiting for results.
- Keep child prompts narrow: one domain, one output contract, no cross-domain judgment.
- Preserve the child skill's judgment; do not sand off sharp findings during aggregation.
- Keep coverage gaps visible.
- Use deterministic helper scripts for final aggregation, evidence synthesis, and validation.

## Subagent contract

Each child audit must run in its own subagent with these defaults:

- `agent_type="worker"`
- `fork_context=false`
- do not set `model`
- do not set `reasoning_effort`

That means every child inherits the current Codex main-session model and reasoning effort automatically.
Do not override those values.

Each child subagent prompt must include:

- repo root
- exact summary path it must write
- its human report path and agent brief path when applicable
- the rule that it owns only its domain and must not make cross-domain conclusions
- the rule that best-effort artifacts are still required on uncertainty, using states like `unverified`, `scan-blocked`, or `not-applicable`
- the rule that dependency bootstrap failures are not ordinary uncertainty: they must emit blocked artifacts with machine-readable dependency failures

Child subagents may call their own deterministic scripts or local wrappers if their skill defines them.
The orchestrator itself must not shell out to child wrappers.

## Terminal control plane contract

The orchestrator must keep one live state file:

- `.repo-harness/repo-health-control-plane.json`

That file is the single source of truth for the terminal dashboard.
Do not fake runtime state from the final repo-health summary.

Use these helper commands:

```bash
python3 scripts/control_plane_state.py init --state /path/to/repo/.repo-harness/repo-health-control-plane.json
python3 scripts/control_plane_state.py update-overall --state /path/to/repo/.repo-harness/repo-health-control-plane.json --stage running --auto-progress
python3 scripts/control_plane_state.py update-worker --state /path/to/repo/.repo-harness/repo-health-control-plane.json --domain structure --runtime-status running --detail "subagent active"
python3 scripts/control_plane_state.py sync-worker-runtime --state /path/to/repo/.repo-harness/repo-health-control-plane.json --domain structure --runtime /path/to/repo/.repo-harness/dependency-audit-runtime.json
python3 scripts/control_plane_state.py finalize-from-summary --state /path/to/repo/.repo-harness/repo-health-control-plane.json --summary /path/to/repo/.repo-harness/repo-health-summary.json
python3 scripts/render_control_plane.py --state /path/to/repo/.repo-harness/repo-health-control-plane.json
python3 scripts/render_control_plane.py --state /path/to/repo/.repo-harness/repo-health-control-plane.json --final
```

Default renderer behavior:

- whole-screen redraw, not snapshot logging
- Unicode box drawing + ANSI color when supported
- ASCII / no-color fallback for `TERM=dumb` or `NO_COLOR=1`
- two columns when the terminal is wide enough, otherwise one column

## Mandatory workflow

### 1) Reset harness

Before doing anything else:

1. delete the repo-root `.repo-harness` directory if it exists
2. recreate it empty
3. initialize `.repo-harness/repo-health-control-plane.json`
4. render the first control-plane frame

Never reuse artifacts from an earlier run.

Example:

```bash
python3 scripts/control_plane_state.py init \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json \
  --context repo-health-orchestrator \
  --model-label "Inherited from session" \
  --reasoning-effort "Inherited"
python3 scripts/render_control_plane.py \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json
```

### 2) Bootstrap the shared toolchain first

Before spawning any child subagents, bootstrap the union of all child `tools[]` and `runtime_features[]`.

The shared `.pooh-runtime` toolchain is a host-side audit environment, not an app runtime:

- Python audit CLIs come only from the `uv` `audit` dependency group
- TS/Node audit CLIs come only from `pnpm` `devDependencies`
- `lychee` and `Vale` remain docs-only hard-dependency exceptions managed by the shared runtime

Use:

```bash
python3 scripts/bootstrap_shared_toolchain.py \
  --repo /path/to/repo \
  --out-json /path/to/repo/.repo-harness/repo-health-shared-bootstrap.json
```

If this shared bootstrap returns blocked failures:

- do not pretend the child domains are missing
- mark the affected domains `blocked`
- surface the failed tool or runtime feature in the control plane
- only spawn child subagents that still have a runnable tool/runtime surface

### 3) Spawn child audits

Launch the seven child subagents in parallel.

Immediately mark the overall stage as `spawning`, then mark each child worker as `running`, and redraw the control plane.

### 4) Track progress live

While the child audits are running, keep the terminal control plane current.

Required progress stages:

- `reset-harness`
- `spawn-subagents`
- `running X/7`
- `collecting`
- `aggregating`
- `done`

For each child, surface only these runtime states:

- `waiting`
- `preflight`
- `bootstrapping`
- `running`
- `complete`
- `blocked`
- `invalid`
- `missing`
- `not-applicable`

If one child fails, keep waiting for the others.
Do not abort the overall run.
Blocked child skills still count as current-run coverage because they produced official blocked artifacts.

On every child completion, timeout poll, or state change:

1. update that worker in `repo-health-control-plane.json`
2. update the overall stage / progress ratio
3. redraw the terminal control plane

Use the current run's real information only:

- do not invent queue states
- do not mark a worker complete before its artifact exists
- do not mark a worker blocked unless the child verdict or severities justify it

### 5) Collect and validate child artifacts

After the subagents finish, check the seven expected summary paths.

For each domain, classify the result as:

- `present` - summary exists and parses
- `blocked` - summary exists, parses, and its `dependency_status` is `blocked`
- `not-applicable` - summary exists and its verdict is `not-applicable`
- `invalid` - file exists but is missing or malformed for aggregation
- `missing` - expected summary was not produced

Then emit a progress update labeled `collecting`.

In practice:

```bash
python3 scripts/control_plane_state.py update-overall \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json \
  --stage collecting
python3 scripts/render_control_plane.py \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json
```

### 6) Aggregate and validate the machine rollup

Use the deterministic helper scripts:

```bash
python3 scripts/aggregate_repo_health.py \
  --repo /path/to/repo \
  --harness-dir /path/to/repo/.repo-harness \
  --out-json /path/to/repo/.repo-harness/repo-health-summary.json \
  --out-md /path/to/repo/.repo-harness/repo-health-report.md

python3 scripts/validate_repo_health_summary.py \
  --summary /path/to/repo/.repo-harness/repo-health-summary.json
```

Before the aggregate runs, move the overall stage to `aggregating` and redraw.
This machine summary remains the single source of truth for `overall_health`, `coverage_status`, coverage classification, and blocked/missing/invalid distinctions.

### 7) Synthesize richer evidence and final outputs

After the machine summary validates, synthesize cross-domain evidence and overwrite the final human-facing outputs:

```bash
python3 scripts/synthesize_repo_health.py \
  --repo /path/to/repo \
  --summary /path/to/repo/.repo-harness/repo-health-summary.json \
  --harness-dir /path/to/repo/.repo-harness \
  --out-evidence /path/to/repo/.repo-harness/repo-health-evidence.json \
  --out-report /path/to/repo/.repo-harness/repo-health-report.md \
  --out-brief /path/to/repo/.repo-harness/repo-health-agent-brief.md
```

The richer synthesis layer must:

- preserve the machine rollup rather than recompute it
- read child human reports and child agent briefs when available
- group domains into fixed clusters instead of inventing new ones
- prioritize dependency-blocked domains before business findings
- keep missing or invalid child artifacts visible as evidence gaps

### 7) Finalize

After synthesis succeeds, project the final repo-health summary back into the control-plane state and render the final frame:

```bash
python3 scripts/control_plane_state.py finalize-from-summary \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json \
  --summary /path/to/repo/.repo-harness/repo-health-summary.json
python3 scripts/render_control_plane.py \
  --state /path/to/repo/.repo-harness/repo-health-control-plane.json \
  --final
```

The final control-plane frame must include:

- overall health
- coverage status
- blocked / missing / invalid domains
- dependency-blocked domains before business findings
- the top action queue

Always keep the difference between coverage failure and audit failure explicit.

## Rollup health states

Use these orchestrator-level states:

- `not-applicable`
- `partial-coverage`
- `blocked`
- `watch`
- `healthy`

Interpretation:

- `blocked` - at least one child domain has blocker evidence or high-severity findings
- `watch` - no blocker domain was found, but medium-severity findings or coverage gaps remain
- `partial-coverage` - too many expected domains are missing or invalid to call the repo healthy
- `healthy` - coverage is good enough and no strong blocker domains were found

## Human report contract

Required sections:

1. Executive summary
2. Coverage and trust
3. Root cause clusters
4. Highest-risk domains
5. Ordered action queue: now / next / later
6. Open unknowns and evidence gaps
7. What this repo is teaching AI to do wrong overall

## Agent brief contract

Keep it short and operational.

Per domain include:

- `domain`
- `skill_name`
- `status`
- `dependency_status`
- `child_verdict`
- `top_categories`
- `top_action`
- `why_now`
- `notes`

## Safety rules

- Do not reuse stale child summaries.
- Do not claim a clean bill of health from partial evidence.
- Do not invent a shell fallback when subagents are unavailable.
- Do not flatten child nuance into generic management language.
- Do not silently skip high-risk domains.

## Final reminder

This skill is the judge's bench only after it has forced every domain to show current-run evidence.
