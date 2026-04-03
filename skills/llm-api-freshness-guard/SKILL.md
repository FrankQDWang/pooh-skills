---
name: llm-api-freshness-guard
description: "Audits Python / TypeScript repositories for stale LLM API usage, surface ambiguity, wrapper/provider drift, and outdated integration assumptions. Use for LLM API 新鲜度审计、SDK/endpoint drift review、wrapper/provider mismatch、gateway surface 归因、Context7-backed official verification. Produces a blunt human report, a concise agent brief, a machine-readable summary, and a local evidence bundle."
---

# LLM API Freshness Guard

This skill audits one thing: whether a Python or TypeScript codebase is still aligned with the current LLM API surfaces it actually uses.

It is report-only. It does not rewrite integrations unless the user explicitly asks for fixes after the audit.

## When to use this

Use this skill when the user wants to:

- audit a repo, diff, file, or snippet for stale LLM SDK / endpoint / wrapper usage
- check whether a wrapper stack still matches its underlying provider or protocol surface
- verify tool calling, structured output, streaming, auth, base URL, or model-name usage against current docs
- separate real provider drift from weak clues copied from docs, comments, or old examples
- produce a decision-ready freshness diagnosis instead of vague "this looks old" guesses

## Do not use this

Do not use this skill as the primary skill when the user mainly wants:

- prompt tuning
- model benchmarking or pricing comparison
- generic code review with no LLM surface freshness question
- full automated migration without first verifying the current docs

## Supported scope

Official verified freshness conclusions apply only to Python / TypeScript surfaces.

Other languages may appear as weak evidence, but they must not drive provider-specific verified conclusions in this skill.

## Audit modes

This skill uses four explicit modes:

- `verified`
  - the agent resolved the real runtime surface and checked current docs through Context7
- `triage`
  - the local evidence extractor found candidate surfaces, but current docs were not checked yet
- `blocked`
  - an official verified audit was requested, but runtime or doc verification could not complete truthfully
- `not-applicable`
  - no meaningful Python / TypeScript LLM surface was detected in scope

`triage` is not a success substitute for `verified`.

## Inputs and outputs

Required machine artifacts:

- `.repo-harness/skills/llm-api-freshness-guard/extra/surface-evidence.json`
- `.repo-harness/skills/llm-api-freshness-guard/summary.json`
- `.repo-harness/skills/llm-api-freshness-guard/report.md`
- `.repo-harness/skills/llm-api-freshness-guard/agent-brief.md`

Final checks:

- summary validates against `assets/llm-api-freshness-summary.schema.json`
- every verified finding points to real doc evidence
- family-level conclusions never pretend to be concrete provider resolution
- triage output never pretends current docs were checked

## Reading map

Read only what you need.

- `assets/llm-api-freshness-summary.schema.json`
- `assets/provider-hints.json`
- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/surface-resolution-policy.md`
- `references/context7-usage-policy.md`
- `references/context7-query-playbook.md`
- `references/provider-query-cheatsheet.md`
- `references/live-doc-verification.md`
- `references/context7-runtime-setup.md`
- `references/evals.md`
- `scripts/run_all.sh`
- `scripts/collect_llm_api_signals.py`
- `scripts/finalize_verified_llm_api_audit.py`
- `scripts/validate_llm_api_freshness_summary.py`

## Operating stance

- Live docs beat memory.
- Direct runtime evidence beats comments, docs, and sample code.
- Do not guess the provider when the evidence only supports a family-level conclusion.
- Wrappers do not erase provider or gateway risk.
- A repo can legitimately contain multiple LLM surfaces. Split them.
- High-severity freshness findings require verified docs. Pattern matching alone is not enough.

## Surface resolution contract

Use these resolution levels exactly:

- `provider-resolved`
- `family-resolved`
- `wrapper-resolved`
- `ambiguous`

Use these family labels exactly:

- `openai-compatible`
- `anthropic-messages`
- `google-genai`
- `bedrock-hosted`
- `generic-wrapper`
- `custom-http-llm`
- `unknown`

Rules:

- only use `provider-resolved` when strong runtime evidence identifies one concrete provider
- if the repo only proves a protocol family, stay at `family-resolved`
- if the wrapper is clear but the provider is not, use `wrapper-resolved`
- if evidence is still too weak, use `ambiguous`

## Workflow

### 1. Run local triage first

For repository scope, start with the wrapper:

```bash
bash scripts/run_all.sh /path/to/repo
```

This produces:

- `.repo-harness/skills/llm-api-freshness-guard/extra/surface-evidence.json`
- `.repo-harness/skills/llm-api-freshness-guard/summary.json`
- `.repo-harness/skills/llm-api-freshness-guard/report.md`
- `.repo-harness/skills/llm-api-freshness-guard/agent-brief.md`

That output is always `triage` or `not-applicable`, never `verified`.

### 2. Resolve real surfaces

Read the local evidence bundle and decide, per surface:

- what the real provider or family is
- whether a wrapper owns runtime semantics
- whether a gateway / base URL changes the semantics
- whether ambiguity remains honest and unresolved

Do not collapse everything into one fake global provider.

### 3. Verify docs with Context7

For each surface, use 1 to 3 precise Context7 queries.

Query order:

- `provider-resolved`
  - provider SDK docs first
  - then provider platform docs
  - then wrapper docs if a wrapper also owns behavior
- `family-resolved`
  - family-level upstream or compatibility docs first
  - then wrapper docs when the repo clearly uses a wrapper
- `wrapper-resolved`
  - wrapper docs first
  - provider or family docs only if pass-through behavior is visible
- `ambiguous`
  - do not force a provider-specific verdict

### 4. Finalize verified artifacts

After writing the verified summary draft, finalize with:

```bash
python3 scripts/finalize_verified_llm_api_audit.py \
  --evidence-json .repo-harness/skills/llm-api-freshness-guard/extra/surface-evidence.json \
  --summary-in /path/to/draft-summary.json \
  --summary-out .repo-harness/skills/llm-api-freshness-guard/summary.json \
  --report-out .repo-harness/skills/llm-api-freshness-guard/report.md \
  --brief-out .repo-harness/skills/llm-api-freshness-guard/agent-brief.md
```

If Context7 evidence is stored separately, pass `--doc-evidence-json`.

## Finding contract

Use these finding kinds:

- `stale-surface`
- `deprecated-surface`
- `wrapper-provider-mismatch`
- `gateway-resolution-gap`
- `provider-ambiguous`
- `docs-unverified`
- `legacy-suspicion`

Severity rules:

- triage-only findings may not exceed `low`
- family-resolved findings may not exceed `medium`
- `high` / `critical` requires verified docs and a concrete runtime mismatch

## Quality bar

A good result from this skill:

- says what surface is actually in use instead of guessing from vibes
- keeps `family-resolved` and `provider-resolved` separate
- tells the reader which conclusions are verified and which are still triage-only
- avoids false stale claims from docs, comments, or copied examples
- gives the next verification step, not just a pile of raw clues
