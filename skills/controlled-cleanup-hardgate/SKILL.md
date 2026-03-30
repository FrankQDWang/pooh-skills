---
name: controlled-cleanup-hardgate
description: Audits Python / TypeScript repositories for deprecated APIs, compatibility shims, legacy aliases, stale docs, expired removal targets, and removal-readiness gaps. Use for deprecated removal readiness、legacy API migration closure、compat layer retirement review、feature-flag debt、stale docs cleanup readiness. Produces a blunt human report, a concise agent handoff brief, and machine-readable cleanup findings.
---

# Controlled Cleanup Hardgate

This skill is for evidence-based deprecated / removal readiness auditing in Python / TypeScript codebases.

It is not a generic dependency audit, not a contract-hardening skill, and not a Temporal / pydantic-ai hard gate. It focuses on one thing: closing deprecated or legacy surfaces all the way to deletion, without hiding behind compatibility wrappers.

## When to use this

Use this skill when the user wants any of the following:

- delete deprecated APIs, aliases, wrappers, shims, adapters, or old entrypoints
- finish a migration instead of preserving backward compatibility forever
- audit a repo for deprecated / removal readiness before risky deletions
- find expired deprecations, stale docs, or old references that should already be gone
- tighten a removal-readiness workflow with evidence, validation, and rollback thinking
- produce a sharp removal-readiness report for humans and a concise handoff brief for another coding agent

## Do not use this

Do not use this skill as the primary skill when the user mainly wants:

- dependency direction, cycle, or architecture-boundary auditing
- signature-as-contract hard gates for APIs and errors
- Temporal workflow determinism or pydantic-ai durable execution review
- broad framework modernization with no deletion or deprecation angle

## Mission

The objective is to answer five questions with as much deterministic evidence as possible:

1. What deprecated or legacy surfaces still exist?
2. Which of them are probably safe to remove now?
3. Which ones are blocked by dynamic entrypoints, missing tests, rollout risk, or unclear ownership?
4. What docs, examples, links, flags, and config aliases would drift if deletion happened?
5. What is the shortest safe sequence from "replacement exists" to "old thing is physically gone"?

## Reading map

Read only what is needed.

- `assets/human-report-template.md` - exact report shape for humans
- `assets/agent-brief-template.md` - short remediation brief for another coding agent
- `assets/cleanup-summary.schema.json` - JSON output contract
- `references/playbook.md` - full cleanup playbook from scope to deletion to rollout
- `references/failure-modes.md` - common cleanup mistakes and how to avoid them
- `references/marker-policy.md` - recommended deprecation marker format
- `references/tool-selection.md` - fixed Python / TypeScript / docs validation stack used by this skill
- `references/evals.md` - trigger, non-trigger, and false-positive regression cases for manual skill testing

## Operating stance

- Report only. This skill does not perform cleanup, codemods, or automatic deletion.
- Treat `.repo-harness` as output-only. Never put default inputs there.
- Prefer replacement complete -> block new refs by migration discipline -> delete old -> validate -> rollout.
- Do not preserve compatibility wrappers unless the user explicitly asks for that trade-off.
- Treat dynamic entrypoints, reflection, runtime imports, routing strings, config keys, migrations, and public SDK surfaces as high-risk until proven otherwise.
- Be blunt about whether the repo is actually ready for deletion.
- Keep recommendations ordered by impact and reversibility.
- Merge duplicate findings. Do not flood the user with 200 copies of the same smell.
- The scanner proposes candidates. It does not replace language-aware tooling or human confirmation.
- Ordinary prose that merely mentions `legacy`, `compatibility`, `plugin`, or `route` is not a high-confidence cleanup finding by itself.

## Mandatory workflow

### 1) Profile the repo quickly

Identify languages, manifests, docs systems, test layout, CI hints, and likely public surfaces.

### 2) Run the deterministic scan first

From the skill directory, targeting the repository root:

```bash
mkdir -p .repo-harness
python3 scripts/run_cleanup_scan.py \
  --repo /path/to/repo \
  --out .repo-harness/controlled-cleanup-summary.json
python3 scripts/validate_cleanup_summary.py \
  --summary .repo-harness/controlled-cleanup-summary.json
python3 scripts/check_removal_targets.py \
  --summary .repo-harness/controlled-cleanup-summary.json
python3 scripts/check_doc_links.py \
  --repo /path/to/repo \
  --out .repo-harness/controlled-cleanup-linkcheck.json
```

If the user wants a single wrapper command instead, run:

```bash
bash scripts/run_all.sh /path/to/repo
```

Use strict removal metadata enforcement only when that is the point of the run:

```bash
bash scripts/run_all.sh --strict-removal-targets /path/to/repo
```

The wrapper is report-first: it should try to emit all applicable artifacts before returning a non-zero exit code.

### 3) Classify findings

Use the taxonomy below and decide whether each item is:

- Delete now - evidence is strong enough
- Delete after migration - replacement exists but call sites / docs / flags still remain
- Hold - dynamic entrypoints, rollout risk, or ownership ambiguity make deletion unsafe today
- False positive / needs human confirmation - scanner signal is too weak

### 4) Produce dual-audience outputs

Always produce:

- a human report with executive summary, risk, evidence, and ordered action plan
- an agent remediation brief with exact targets, verification commands, and deletion rules

When useful, also write machine-readable outputs under `.repo-harness/`.

### 5) Keep the deliverable report-only

This skill can identify delete-ready surfaces and the validation chain they require.
It must not perform codemods, automatic cleanup, or broad destructive edits from scanner output.

### 6) Close the loop

The final recommendation must state whether the repo currently satisfies this deletion-oriented definition of done:

- replacement path exists and is the intended source of truth
- old code or docs can be physically removed, not merely commented or re-aliased
- validation chain is identified and runnable
- rollback or staged rollout thinking exists for risky changes

## Finding taxonomy

Use these categories exactly where possible:

- `scan-blocker` - repo state prevents trustworthy cleanup assessment
- `evidence-gap` - tests, ownership, CI, or validation chain are too weak
- `deprecated-surface` - explicitly marked deprecated API, class, function, module, route, config key, schema, or doc surface
- `compatibility-shim` - wrapper, alias, adapter, proxy, or bridge kept only for compatibility
- `expired-removal-target` - deprecation marker indicates removal date/version that has already passed
- `marker-gap` - explicitly deprecated item has no replacement, no target, or no owner cue
- `stale-doc-reference` - docs, examples, or nav still point to old surfaces or removed files
- `feature-flag-debt` - migration-complete flag or fallback path is still left around
- `dynamic-entrypoint-risk` - reflection, runtime import, dynamic dispatch, or similar hidden-reference behavior
- `cleanup-opportunity` - likely safe next deletion once blockers are removed

## Prioritization

Use this order unless the repo shows a stronger reason to reorder:

1. expired removal targets
2. stale docs
3. thin compatibility shims with clear replacement paths
4. migration-complete feature flags and fallback branches
5. broader deprecated surfaces that still need call-site migration work
6. ambiguous items with dynamic-entrypoint risk

## Human report contract

The human report should be sharp and decision-oriented.

Required sections:

1. Executive summary
2. What looks safe to delete now
3. What is still blocking deletion
4. Highest-risk hidden-reference areas
5. Required validation chain
6. Ordered cleanup sequence
7. Rollback / canary notes where applicable
8. Final verdict: `not ready`, `partially ready`, or `ready for controlled deletion`

Use the template in `assets/human-report-template.md`.

## Agent remediation brief contract

The agent brief must be short enough to hand to another coding agent without burying the lead.

It must include:

- exact targets to remove or migrate
- explicit "do not preserve wrappers unless asked" rule
- required verification commands
- blocked areas that need human confirmation
- expected output format

Use the template in `assets/agent-brief-template.md`.

## Output contract

When writing machine-readable output, follow `assets/cleanup-summary.schema.json`.

Preferred files:

- `.repo-harness/controlled-cleanup-summary.json`
- `.repo-harness/controlled-cleanup-linkcheck.json`
- `.repo-harness/controlled-cleanup-report.md`
- `.repo-harness/controlled-cleanup-agent-brief.md`

## Safety rules

- Never claim deletion is safe when dynamic entrypoints or public compatibility commitments are still unresolved.
- Never treat "wrapped but still present" as equivalent to deletion.
- Never ignore docs, examples, READMEs, nav files, and generated references.
- Never recommend sweeping destructive edits without a validation path.
- Escalate when the repo lacks tests, owners, or rollout controls for risky surfaces.
- State uncertainty clearly when heuristics, not proofs, are doing the work.

## Strong default language for cleanup work

Use wording like this in the handoff brief:

- The goal is to remove deprecated or legacy surfaces, not preserve compatibility by default.
- Breaking backward compatibility is acceptable only after replacement and migration are complete.
- Any deletion must leave code, docs, and references in a mutually consistent state.
- Old files, symbols, routes, or examples should be physically deleted when evidence is strong enough.
- Validation commands are part of the deliverable, not an afterthought.

## Examples of good final judgments

- "Replacement exists, but docs, examples, and two compatibility adapters still reference the old path. Not ready for deletion."
- "The old alias is only kept by a thin wrapper, all call sites have migrated, and the docs are aligned. Ready for controlled deletion."
- "The scanner found deprecation markers, but runtime indirection makes hidden references plausible. Hold until dynamic-entrypoint risk is mapped."

## Testing the skill itself

Before shipping or revising this skill, run at least these checks:

- trigger cases: cleanup / deprecation / deletion prompts should select this skill
- paraphrase cases: less direct wording should still select this skill
- non-trigger cases: pure dependency audit or contract-hardening prompts should not select this skill
- false-positive regression cases: prose-only mentions should not become high-confidence cleanup findings

Use `references/evals.md` as the starting set.

## Troubleshooting

If the deterministic scripts return too little signal:

- read `references/marker-policy.md` and recommend stronger deprecation markers
- escalate to language-aware tools listed in `references/tool-selection.md`
- separate code cleanup from docs cleanup if the repo is too noisy

If the scanner returns too many false positives:

- narrow scope to one bounded context or package first
- exclude generated / vendor / build directories more aggressively
- require higher confidence before labeling something delete-ready
- push ambiguous items into `needs human confirmation` instead of overclaiming
