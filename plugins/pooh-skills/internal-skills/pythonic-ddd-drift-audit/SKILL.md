---
name: pythonic-ddd-drift-audit
description: Audits Python-heavy repositories for Pythonic abstraction bloat, domain-boundary leaks, fake DDD, ceremony-heavy CQRS signals, cross-context model bleed, and composition-root drift. Use for Pythonic architecture drift、DDD 边界巡检、假 CQRS 诊断、反非 Pythonic 仪式化审计、AI 快速编码后的代码膨胀控制. Produces a blunt human report, a concise agent brief, and machine-readable findings. Default to report-first; treat blockers conservatively and use strong evidence for hard gates.
---
# Pythonic DDD Drift Audit

This skill exists to catch a very specific long-tail failure mode of AI coding:

**the repo still runs, but the codebase is slowly turning into ceremony-heavy, boundary-leaking, fake-DDD sludge.**

It is not a generic style checker, not a dependency-direction replacement, not a framework benchmark, and not a sermon about Clean Architecture purity.

## When to use this

Use this skill when the user wants to:

- audit a Python-heavy repo for **abstraction bloat**
- detect whether `domain/` is actually independent, or just a folder name
- find **cross-context imports**, fake repositories, thin wrappers, or interface inflation
- check whether CQRS is a useful local pattern or empty ceremony
- produce a report that helps a coding agent **remove shape debt** instead of adding more layers

## Do not use this

Do **not** use this skill as the primary skill when the user mainly wants:

- dependency graphs, cycles, or unused dependency cleanup
- strict API / schema / merge-gate contract auditing
- Temporal + pydantic-ai durable execution review
- distributed consistency or outbox / idempotency auditing
- deletion-oriented deprecated API cleanup

## Mission

Answer these questions with evidence:

1. Does `domain` or equivalent core logic import frameworks, ORMs, transport DTOs, or infrastructure details?
2. Are bounded contexts actually bounded, or do models bleed across them?
3. Is the repo using abstraction where it earns its keep, or just manufacturing interfaces and wrappers?
4. Are "services", "managers", and "handlers" carrying real policy, or only forwarding calls?
5. Is CQRS being used where it buys separation, or merely to cosplay complexity?
6. What is the smallest set of changes that removes ceremony without breaking real boundaries?

## Reading map

Read only what you need.

- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `assets/pythonic-ddd-drift-summary.schema.json`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/pythonic-principles.md`
- `references/detection-policy.md`
- `references/evals.md`
- `scripts/run_py_drift_scan.py`
- `scripts/validate_py_drift_summary.py`
- `scripts/run_all.sh`

## Operating stance

- Default to **report-first**.
- Prefer **removing meaningless layers** over adding new ones.
- Prefer **structural typing / light abstractions** over inheritance theater when the repo shape supports it.
- Do not recommend broad rewrites unless the evidence is overwhelming.
- Be stricter on **domain-boundary leaks** than on naming or folder aesthetics.
- Distinguish **strong evidence** from **drift signals**.
- Write in the user's language.

## Evidence classes

Treat these as **strong evidence**:

- domain importing framework / ORM / infra packages
- explicit cross-context domain imports
- base classes that are mostly `NotImplementedError` shells
- thin wrappers that only forward to collaborators

Treat these as **moderate signals**:

- CQRS ceremony counts
- anemic domain model patterns
- missing composition root clues
- broad "service / manager / factory" sprawl

Do **not** turn moderate signals into fake certainty.

## Mandatory workflow

### 1) Profile the repo quickly

Identify:

- whether the repo is meaningfully Python-heavy
- whether it appears to have domain / application / adapters style layering
- whether it contains explicit bounded-context structure such as `contexts/<name>/...`

If the repo is not meaningfully Pythonic or does not expose architecture boundaries this skill can inspect, output `overall_verdict: not-applicable`.

### 2) Run the deterministic scan first

From the skill directory:

```bash
mkdir -p .repo-harness
python3 scripts/run_py_drift_scan.py   --repo /path/to/repo   --out .repo-harness/pythonic-ddd-drift-summary.json

python3 scripts/validate_py_drift_summary.py   --summary .repo-harness/pythonic-ddd-drift-summary.json
```

Or use:

```bash
bash scripts/run_all.sh /path/to/repo
```

### 3) Classify findings

Use the taxonomy below and choose one gate per finding:

- `block-now` — strong boundary breakage
- `block-changed-files` — real architecture drift that should stop spreading
- `warn-only` — moderate signal or likely ceremony debt
- `unverified` — important but not locally provable

### 4) Produce dual-audience outputs

Always produce:

- a human report
- an agent remediation brief
- a machine-readable summary JSON

### 5) Keep the deliverable report-only

This skill identifies where the repo is paying abstraction tax and where boundaries are leaking.
It does not redesign core modeling or split contexts automatically.

## Finding taxonomy

Use these categories exactly where possible:

- `scan-blocker`
- `domain-boundary-leak`
- `cross-context-model-bleed`
- `abc-overuse`
- `protocol-opportunity`
- `thin-wrapper`
- `abstraction-bloat`
- `anemic-domain-model-signal`
- `cqrs-ceremony-signal`
- `composition-root-gap`
- `framework-coupling-signal`

## Prioritization

Use this order by default:

1. `domain-boundary-leak`
2. `cross-context-model-bleed`
3. `framework-coupling-signal`
4. `abc-overuse` / `protocol-opportunity`
5. `thin-wrapper`
6. `abstraction-bloat`
7. `anemic-domain-model-signal`
8. `cqrs-ceremony-signal`
9. `composition-root-gap`

## Verdict policy

Allowed overall verdicts:

- `not-applicable`
- `drifting`
- `ceremonial`
- `contained`
- `disciplined`

Interpret them like this:

- `drifting` — strong boundary leaks or model bleed are visible
- `ceremonial` — the repo is not obviously broken, but it is accumulating abstraction theater fast
- `contained` — some drift exists, but the main shape is recoverable without major surgery
- `disciplined` — no strong leaks and limited ceremony debt was found by the scan

## Human report contract

Required sections:

1. Executive summary
2. Where the repo is lying about boundaries
3. Where Python is being forced into non-Pythonic ceremony
4. What is safe to flatten now
5. What still requires modeling decisions
6. Ordered action plan: now / next / later
7. What this repo is teaching AI to do wrong

For each major finding, explain:

- **是什么**
- **为什么重要**
- **建议做什么**
- **给非程序员的人话解释**

## Agent brief contract

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
- `flatten`
- `quarantine`
- `defer`

`change_shape` should describe the target shape, not the tutorial. Examples:

- `move framework dependency behind adapter and keep domain package pure`
- `replace nominal interface shell with Protocol or direct callable dependency`
- `collapse pass-through service into application function`
- `stop importing other context's domain model; publish an event or define a boundary DTO`
- `keep CQRS only where there is a real read-side payoff`

## Output contract

When file output is possible, always create:

- `.repo-harness/pythonic-ddd-drift-human-report.md`
- `.repo-harness/pythonic-ddd-drift-agent-brief.md`
- `.repo-harness/pythonic-ddd-drift-summary.json`

## Safety rules

- Default to detection and reporting
- Do not confuse a naming preference with a hard architecture failure
- Do not demand DDD everywhere
- Do not call every class smell a blocker
- Do not prescribe CQRS where a simple query path is enough
- Be ruthless about fake boundaries; be conservative about modeling taste

## Final reminder

This skill is here to catch **architecture drift under AI acceleration**.

Not because every repo needs textbook DDD,
but because without a check like this, AI tends to produce code that is simultaneously over-abstracted and under-bounded.
