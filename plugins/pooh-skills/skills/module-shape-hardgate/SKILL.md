---
name: module-shape-hardgate
description: "Audits Python / TypeScript repositories for oversized files, god-module sprawl, mixed responsibilities, wide export surfaces, long functions, duplication-heavy modules, and fan-out hubs that teach AI coding the wrong shape. Use for giant-file hard gates、high-cohesion / low-coupling guardrails、AI coding aftercare、merge-readiness review、module split planning. Produces a blunt human report, a concise agent brief, and machine-readable findings. Default to detection-and-report only; do not refactor or auto-fix unless explicitly requested."
---

# Module Shape Hardgate

This skill exists for one very specific Codex failure mode: **the code works, but the module shape is rotting fast**.  
Typical symptoms: one file quietly grows to 800–6000 lines, HTTP + schema + DB + orchestration all get mixed together, exports balloon, functions stop fitting in a screen, and future AI edits keep piling onto the same hotspot.

It is intentionally **report-only**. It detects and explains. It does **not** silently split files, redesign modules, or auto-fix code.

## When to use this

Use this skill when the user wants to:

- audit a Python / TypeScript repo for **giant files**, **god modules**, or **low-cohesion module shape**
- stop AI coding from turning one file into a catch-all dumping ground
- enforce **high cohesion / low coupling** expectations before merge
- generate a decision-ready report about **what should be split**, **what should be narrowed**, and **what is still acceptable**
- create a machine-readable baseline for CI, Codex review flows, or orchestrated repo health checks

## Do not use this

Do **not** use this skill as the primary skill when the user mainly wants:

- dependency direction, cycles, or unused dependency cleanup → use a dependency-focused skill
- compile-time/runtime schema and signature contract gates
- Python DDD boundary purity or fake-CQRS diagnosis as the main question
- durable execution / Temporal / pydantic-ai review
- automatic refactoring without first producing evidence

## Scope lock

- Target languages: **Python** and **TypeScript** only
- Default posture: **detect and report only**
- If the repo is not meaningfully Python / TypeScript, output `overall_verdict: not-applicable`

## Mission

Answer these questions with evidence:

1. Which files are now too large to trust as a healthy unit of change?
2. Which modules are acting like **god modules** rather than coherent modules?
3. Where is one file mixing too many responsibilities?
4. Where will coupling cause future AI edits to keep accumulating in the same hotspot?
5. What is the smallest **structural** next step: split, extract, narrow exports, or freeze growth?

## Reading map

Read only what you need.

- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `assets/module-shape-summary.schema.json`
- `assets/runtime-dependencies.json`
- `references/detection-policy.md`
- `references/tooling-policy.md`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/evals.md`
- `scripts/run_module_shape_scan.py`
- `scripts/validate_module_shape_summary.py`
- `scripts/run_all.sh`

## Operating stance

- Default to **detection + report**
- Prefer **strong structural evidence** over style opinions
- Be stricter on **module shape debt that compounds future AI edits** than on taste-level formatting debates
- Avoid claiming “low cohesion” from naming alone; show the concrete mixed responsibilities
- If parse blockers prevent a truthful official verdict, mark the run `scan-blocked` instead of pretending the repo looks healthy
- Keep the report decision-rich and command-light
- Write in the user's language
- Keep tool names, file names, and category names in their native technical form

## Strong evidence vs. moderate signals

Treat these as **strong evidence**:

- file NLOC far above threshold
- one file simultaneously triggering multiple shape signals
- functions that are obviously too long or too branch-heavy
- very wide fan-out or export surface from one module
- repeated duplicate blocks across the same hotspot file

Treat these as **moderate signals**:

- likely mixed responsibilities inferred from import/content patterns
- barrel / registry files that are wide but mostly mechanical
- large test helpers or fixture modules
- files that are big but isolated and mechanically generated

Do **not** convert moderate signals into fake certainty.

## Mandatory workflow

### 1) Profile the repo quickly

Identify:

- whether the repo contains Python, TypeScript, or both
- where the likely source roots are
- whether giant-file risk appears concentrated in production code, tests, generated code, or registries

If there is no meaningful Python / TypeScript source surface, output `overall_verdict: not-applicable`.

### 2) Run the deterministic baseline first

From the skill directory:

```bash
mkdir -p .repo-harness
python3 scripts/run_module_shape_scan.py --repo /path/to/repo --out-dir .repo-harness
python3 scripts/validate_module_shape_summary.py --summary .repo-harness/module-shape-hardgate-summary.json
```

Or simply:

```bash
bash scripts/run_all.sh /path/to/repo
```

### 3) Classify findings

Use this taxonomy where possible:

- `scan-blocker`
- `oversized-file`
- `long-function`
- `hub-module`
- `mixed-responsibility`
- `export-surface-sprawl`
- `duplication-cluster`
- `god-module`

### 4) Choose the merge gate honestly

Use one of:

- `block-now`
- `block-changed-files`
- `warn-only`
- `unverified`

Rules of thumb:

- `block-now` → truly extreme module shape debt or a clearly unacceptable new hotspot
- `block-changed-files` → strong evidence of shape debt that should stop spreading
- `warn-only` → real signal, but not enough to stop the whole repo
- `unverified` → suspicious, but not locally provable with confidence

### 5) Produce dual-audience outputs

Always produce:

- human report
- agent brief
- machine-readable summary JSON

### 6) Never silently fix structure

Even when the split direction feels obvious, do not auto-refactor unless the user explicitly asks.

## Threshold posture

The default baseline in this skill is intentionally practical rather than academic:

- file NLOC: warn at `500`, block-shaped concern at `900`, critical at `1800`
- function NLOC: warn at `80`, block-shaped concern at `120`
- approximate complexity: warn at `15`, block-shaped concern at `25`
- fan-out imports: warn at `12`, block-shaped concern at `18`
- exports: warn at `15`, block-shaped concern at `25`

These are defaults, not religion. Generated code, migrations, and narrow registry/barrel modules should be handled with care rather than blindly hard-failed.

## Verdict policy

Allowed overall verdicts:

- `scan-blocked`
- `not-applicable`
- `split-before-merge`
- `sprawling`
- `contained`
- `disciplined`

Interpret them like this:

- `scan-blocked` — at least one non-exempt source file could not be parsed, so the official verdict is blocked until parseability is fixed
- `split-before-merge` — at least one hotspot is too large or too composite to keep normalizing
- `sprawling` — the repo is not yet in full failure, but module shape debt is spreading
- `contained` — some hotspots exist, but the repo still has recoverable boundaries
- `disciplined` — no major giant-file / god-module pressure found by the scan

## Human report contract

Required sections:

1. Executive summary
2. Files that are too big to be trusted
3. Where cohesion is broken
4. Where coupling will spread future AI mistakes
5. What can be split mechanically now
6. What still needs design decisions
7. Ordered action plan: now / next / later
8. What this repo is teaching AI to do wrong

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

- `fix-scan`
- `split`
- `extract`
- `narrow`
- `separate`
- `deduplicate`
- `baseline`
- `defer`

`change_shape` should describe the **target module shape**, not a step-by-step tutorial.

## Fleet baseline mode

When another skill or CI needs stable artifacts quickly, run:

```bash
bash scripts/run_all.sh /path/to/repo
```

This wrapper produces:

- `module-shape-hardgate-summary.json`
- `module-shape-hardgate-report.md`
- `module-shape-hardgate-agent-brief.md`

When installed inside `pooh-skills`, the wrapper prefers the shared `.pooh-runtime` contract if present. Outside that repo, it falls back to direct deterministic execution so the skill remains portable.
