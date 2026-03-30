---
name: overdefensive-silent-failure-hardgate
description: "Audits Python / TypeScript repositories for over-defensive coding that turns real failures into silent fallbacks, maybe-values, checker suppressions, or off-camera async loss. Use for 过度防御审计、静默失败巡检、fail-loud hardening、empty catch review、type/lint escape hatch 排查. Produces a sharp human report, a short agent brief, and a machine-readable summary."
---

# Overdefensive Silent Failure Hardgate

This skill audits one failure mode: code that looks safe because it makes failures quieter instead of making recovery explicit.

Deterministic baseline mode audits a repository root. It does not promise diff, single-file, or snippet-specific precision unless the user explicitly narrows scope outside the bundled wrapper.

## When to use this

Use this skill when the user wants to:

- audit a repo for silent fallback or fail-loud problems
- find empty catch / swallow / catch-and-continue / fire-and-forget async patterns
- review whether AI-generated code softened internal contracts into `Optional`, `undefined`, or default-value sludge
- inspect `# type: ignore`, `@ts-ignore`, `eslint-disable`, `as any`, `cast(...)`, or similar escape hatches
- produce one blunt human diagnosis and one short remediation brief

## Do not use this

Do not use this skill as the primary skill when the user mainly wants:

- dependency / cycle / dead-code auditing
- schema or signature governance in general
- distributed side-effect or idempotency review
- generic bug fixing with no silent-failure angle
- trust-boundary validation review where explicit defensive parsing is expected

## Inputs and outputs

Deterministic baseline input:

- repository root path

Required outputs:

- `.repo-harness/overdefensive-silent-failure-summary.json`
- `.repo-harness/overdefensive-silent-failure-report.md`
- `.repo-harness/overdefensive-silent-failure-agent-brief.md`

Final checks:

- summary validates
- runtime sidecar reflects truth
- blocked prerequisites produce blocked artifacts instead of a fake clean verdict

## Reading map

Read only what you need.

- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `assets/overdefensive-silent-failure-summary.schema.json`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/pattern-catalog.md`
- `references/detection-policy.md`
- `references/remediation-playbook.md`
- `references/tooling-map.md`
- `references/evals.md`
- `scripts/run_all.sh`
- `scripts/run_overdefensive_scan.py`
- `scripts/validate_overdefensive_summary.py`
- `scripts/render_reports.py`

## Operating stance

- Default to report-first.
- Be harsher on invisible failure inside internal paths than on explicit, observable degradation.
- Do not confuse trust-boundary validation with internal contract softening.
- Prefer comment/token-aware evidence over raw substring matching when classifying suppressions.
- Keep weak signals weak. `Optional`, `dict.get`, `??`, and optional chaining are not hard facts by themselves.

## Deterministic workflow

Use the wrapper:

```bash
bash scripts/run_all.sh /path/to/repo
```

Or run the pieces directly:

```bash
python3 scripts/run_overdefensive_scan.py \
  --repo /path/to/repo \
  --out .repo-harness/overdefensive-silent-failure-summary.json

python3 scripts/validate_overdefensive_summary.py \
  --summary .repo-harness/overdefensive-silent-failure-summary.json

python3 scripts/render_reports.py \
  --summary .repo-harness/overdefensive-silent-failure-summary.json \
  --report .repo-harness/overdefensive-silent-failure-report.md \
  --brief .repo-harness/overdefensive-silent-failure-agent-brief.md
```

## Finding taxonomy

Use these categories when possible:

- `scan-blocker`
- `exception-swallow`
- `skip-on-error`
- `cause-chain-loss`
- `async-exception-leak`
- `optionality-leak`
- `silent-default`
- `truthiness-fallback`
- `unsafe-optional-chain`
- `type-escape-hatch`
- `lint-escape-hatch`
- `useless-catch-theater`

## Precision rules

The bundled scanner must not treat the following as high-confidence code findings:

- markdown examples
- schema/example payload text
- regex or rule-definition strings
- comment-suppression phrases that only appear inside string literals
- generated or non-executable documentation surfaces

Comment-based suppressions should be detected from real comment tokens, not from arbitrary substring matches.

## Quality bar

A good result from this skill:

- surfaces the strongest silent-failure paths first
- separates real silent failure from explicit degradation
- keeps weak maybe-value signals low confidence
- avoids self-referential false positives from rule strings or templates
- produces a brief that another coding agent can patch from without extra interpretation
