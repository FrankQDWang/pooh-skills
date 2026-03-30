---
name: distributed-side-effect-hardgate
description: "Audits Python / TypeScript repositories for distributed side-effect hazards: dual writes, pre-commit external effects, outbox gaps, idempotency gaps, unsafe retries, event contract drift, and message-handling reliability holes. Use for 分布式一致性巡检、event-driven reliability audit、outbox / idempotency review、dual-write diagnosis、message consumer hardening、AI 快速编码后的生产级错法排查. Produces a blunt human report, a concise agent handoff brief, and machine-readable findings."
---
# Distributed Side-Effect Hardgate

This skill exists for one class of bugs: code that **looks fine locally but loses correctness once writes, messages, retries, and consumers meet production reality**.

It is not a generic architecture skill, not a pure dependency audit, not a dead-code cleanup tool, and not a broad "event-driven best practices" essay machine.

## When to use this

Use this skill when the user wants to:

- audit a repo for **dual-write hazards**
- check whether event-driven or async workflows are **production-safe** instead of "probably okay"
- verify whether consumers, webhooks, handlers, or workers are **idempotent**
- check whether retries are safe or are just multiplying side effects
- review whether outbox / dead-letter / event versioning / replay safety are actually present
- produce a sharp report for humans and a short remediation brief for a coding agent

## Do not use this

Do **not** use this skill as the primary skill when the user mainly wants:

- dependency direction or cycle auditing
- signature-as-contract or runtime schema hardening in general
- Temporal + pydantic-ai durable execution review
- deprecated API cleanup or deletion planning
- broad framework modernization with no distributed-side-effect angle

## Mission

Answer these questions with as much deterministic evidence as possible:

1. Where does the repo perform a database write and an external side effect in the same flow?
2. Is there a credible outbox / relay / CDC pattern, or is the system gambling on dual writes?
3. Do consumers / handlers / webhooks have real idempotency defenses?
4. Are retries wrapped around non-idempotent operations?
5. Are integration events versioned and shaped like contracts, or are they loose payloads with wishful thinking?
6. If the broker redelivers or the process crashes mid-flight, what breaks first?

## Reading map

Read only what is needed.

- `assets/human-report-template.md` — default human report skeleton
- `assets/agent-brief-template.md` — concise remediation brief for another coding agent
- `assets/distributed-side-effect-summary.schema.json` — machine output contract
- `references/shared-output-contract.md` — shared output contract
- `references/shared-reporting-style.md` — shared reporting and reader rules
- `references/shared-runtime-artifact-contract.md` — shared blocked-artifact and runtime truth rules
- `references/principles.md` — operating principles and reliability baseline
- `references/failure-modes.md` — high-signal anti-pattern catalog
- `references/evals.md` — trigger and false-positive regression cases
- `scripts/run_side_effect_scan.py` — deterministic heuristic scanner
- `scripts/validate_side_effect_summary.py` — summary validation
- `scripts/run_all.sh` — wrapper command

## Operating stance

- Report only.
- Prefer **evidence over doctrine**.
- Prefer **small hardening moves** over fantasy rewrites.
- Do **not** recommend broad distributed redesign unless the evidence forces it.
- Treat "it usually works" as a failure smell, not as reassurance.
- Merge duplicate findings into one root cause.
- Write in the user's language. Keep technical names in their native form when helpful.

## Mandatory workflow

### 1) Profile the repo quickly

Identify:

- main languages and package managers
- broker / queue / webhook / worker surfaces
- data access patterns
- whether the repo even appears to contain distributed side effects

If the repo has no meaningful message, webhook, worker, queue, relay, or cross-process side-effect surfaces, return `overall_verdict: not-applicable` and stop pretending otherwise.

### 2) Run the deterministic scan first

From the skill directory, targeting the repository root:

```bash
mkdir -p .repo-harness
python3 scripts/run_side_effect_scan.py   --repo /path/to/repo   --out .repo-harness/distributed-side-effect-summary.json

python3 scripts/validate_side_effect_summary.py   --summary .repo-harness/distributed-side-effect-summary.json
```

If the user wants a wrapper command instead:

```bash
bash scripts/run_all.sh /path/to/repo
```

The scanner is heuristic and conservative. It finds **high-value failure signals**, not mathematical proofs.

### 3) Classify findings

Use the taxonomy below and decide whether each item is:

- **block-now** — strong evidence of correctness risk
- **block-changed-files** — real risk but should be scoped first
- **warn-only** — credible weakness but not enough evidence for an immediate hard gate
- **unverified** — important but not locally provable

### 4) Produce dual-audience outputs

Always produce:

- a human report
- an agent remediation brief
- a machine-readable summary JSON

If the user did **not** ask for code changes, stop there.

### 5) Keep the deliverable report-only

This skill identifies correctness hazards and the lowest-risk hardening sequence.
It does not rewrite transaction boundaries, retry semantics, or consumer flow control.

## Finding taxonomy

Use these categories exactly where possible:

- `scan-blocker`
- `dual-write-hazard`
- `pre-commit-side-effect`
- `outbox-gap`
- `idempotency-gap`
- `unsafe-retry`
- `event-contract-gap`
- `dead-letter-gap`
- `compensation-gap`
- `observability-gap`

## Severity policy

Default severity mapping:

- `critical` — money / data integrity / duplicate effect / lost event risk is immediate
- `high` — repeated production failure is plausible and the protection is absent or fake
- `medium` — the repo is structurally fragile but no direct blast radius is proven yet
- `low` — hygiene / clarity / observability debt that weakens later hardening

## Prioritization

Use this order unless evidence clearly requires a different sequence:

1. `pre-commit-side-effect`
2. `dual-write-hazard`
3. `outbox-gap`
4. `idempotency-gap`
5. `unsafe-retry`
6. `event-contract-gap`
7. `dead-letter-gap`
8. `compensation-gap`
9. `observability-gap`

## Human report contract

The human report must be blunt and decision-oriented.

Required sections:

1. Executive summary
2. Where production correctness is currently being gambled
3. What is most likely to duplicate, disappear, or diverge
4. What can be hardened now with low risk
5. What still needs design work
6. Ordered action plan: now / next / later
7. What this repo is teaching AI to do wrong

For each major finding, explain:

- **是什么**
- **为什么重要**
- **建议做什么**
- **给非程序员的人话解释**

## Agent brief contract

Use `assets/agent-brief-template.md` as the default skeleton.

Each finding should include at least:

- `id`
- `category`
- `severity`
- `confidence`
- `title`
- `path`
- `line`
- `evidence_summary`
- `decision`
- `change_shape`
- `validation`
- `merge_gate`
- `autofix_allowed`
- `notes`

`decision` should use one of:

- `adopt`
- `harden`
- `replace`
- `quarantine`
- `remove`
- `defer`

`merge_gate` should use one of:

- `block-now`
- `block-changed-files`
- `warn-only`
- `unverified`

`change_shape` should describe the target shape, not a long tutorial. Examples:

- `introduce transactional outbox between persistence and broker publication`
- `move external side effect after durable handoff or outbox write`
- `make handler idempotent with message identity + persistence-backed dedupe`
- `scope retry to transient failures and require idempotency key on side-effect path`
- `version integration events and pin consumers to explicit contract`

## Output contract

When file output is possible, always create:

- `.repo-harness/distributed-side-effect-human-report.md`
- `.repo-harness/distributed-side-effect-agent-brief.md`
- `.repo-harness/distributed-side-effect-summary.json`

If files cannot be written, return the same structure inline.

## Safety rules

- Default to detection and reporting
- Do not invent nonexistent reliability guarantees
- Do not infer that exactly-once exists from marketing words
- Do not assume retries are safe unless idempotency is visible
- Do not call event-driven code "safe" just because there is a queue
- Do not replace nuanced evidence with generic architecture slogans

## Final reminder

This skill is not here to applaud asynchronous code for being modern.

Its job is to answer the only question that matters:

**when the process crashes, the broker redelivers, or the network flakes, does the system still behave correctly — or is it just hoping?**
