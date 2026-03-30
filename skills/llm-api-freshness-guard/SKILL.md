---
name: llm-api-freshness-guard
description: "Audits code, repos, diffs, or snippets for stale LLM API usage and documentation drift across mainstream provider and wrapper surfaces. Use for LLM API 过时检查、SDK/endpoint drift review、tool/streaming/structured-output drift、compat-layer drift、Context7-backed latest-doc verification. Produces a blunt human report, a concise agent brief, and a machine-readable summary."
---

# LLM API Freshness Guard

## When to use this

Use this skill when the user wants to:

- check whether **mainstream provider or wrapper surfaces** such as **OpenAI / Anthropic / Gemini / Azure OpenAI / OpenRouter / Bedrock / LiteLLM / LangChain / Vercel AI SDK / PydanticAI / Instructor** are stale, deprecated, legacy, renamed, or otherwise drifting from current docs
- audit a repo, code diff, file, or snippet for **LLM SDK freshness**
- verify whether **tool calling**, **structured outputs**, **streaming**, **model names**, **request parameters**, or **client initialization** are still current
- sanity-check AI-generated code that may have used **old docs** or **hallucinated APIs**
- compare a wrapper-based stack (**LiteLLM, LangChain, Vercel AI SDK, PydanticAI, Instructor, etc.**) against the current underlying provider docs
- produce a decision-ready diagnosis instead of vague "this looks old" guesses

Do **not** use this skill for:

- generic code review unrelated to LLM provider APIs
- prompt quality tuning
- model benchmarking
- pricing comparisons
- library docs lookup when there is **no freshness or drift question**
- broad automated refactors when the user only asked whether the current API surface is stale

## Mission

Your job is to **detect, verify, classify, and prioritize** stale or risky LLM API usage.

This skill exists because memory rots fast and vendor docs change constantly. Your standard is simple:

- **Live docs beat memory**
- **Official docs beat third-party summaries**
- **Verified mismatch beats intuition**
- **A legacy surface is not automatically a broken surface**
- **Wrappers do not erase provider-specific risk**

## Required environment

This skill is built around **Context7 MCP** for current, version-aware documentation lookup.

If Context7 is unavailable:

- say so plainly
- stop the official audit flow
- emit blocked summary / report / agent brief artifacts
- mark the run `dependency_status=blocked`
- do **not** pretend a local signal pass is an official freshness verdict

`scripts/collect_llm_api_signals.py` may still be used as an internal triage helper, but `local-scan-only` is no longer the accepted success path when Context7 is missing.

## Reading map

- For the human-readable report, start from [`assets/human-report-template.md`](assets/human-report-template.md).
- For the agent remediation brief, start from [`assets/agent-brief-template.md`](assets/agent-brief-template.md).
- For `.repo-harness/llm-api-freshness-summary.json`, conform to [`assets/llm-api-freshness-summary.schema.json`](assets/llm-api-freshness-summary.schema.json).
- For shared output rules, read [`references/shared-output-contract.md`](references/shared-output-contract.md).
- For shared reporting tone and reader expectations, read [`references/shared-reporting-style.md`](references/shared-reporting-style.md).
- For shared runtime truth and blocked-artifact behavior, read [`references/shared-runtime-artifact-contract.md`](references/shared-runtime-artifact-contract.md).
- For live-doc gating and blocked behavior, read [`references/live-doc-verification.md`](references/live-doc-verification.md).
- For Context7 query composition, read [`references/context7-query-playbook.md`](references/context7-query-playbook.md).
- For live documentation lookup policy, query design, failure mode, and evidence rules, read [`references/context7-usage-policy.md`](references/context7-usage-policy.md).
- For provider detection, wrapper handling, and official-doc precedence, read [`references/provider-resolution-policy.md`](references/provider-resolution-policy.md).
- For concrete Context7 query examples by provider and wrapper, read [`references/provider-query-cheatsheet.md`](references/provider-query-cheatsheet.md).
- For Codex / MCP runtime assumptions, read [`references/context7-runtime-setup.md`](references/context7-runtime-setup.md).
- For provider and wrapper detection rules, read [`assets/provider-registry.json`](assets/provider-registry.json).
- For deterministic runtime bootstrap and blocked-artifact behavior, use `scripts/run_all.sh`.
- For local triage only, use `scripts/collect_llm_api_signals.py` and `scripts/validate_llm_api_freshness_summary.py`.

## Operating stance

- Default to **verify + report**.
- Keep the deliverable report-only.
- Keep the report **decision-rich and command-light**.
- Write in the **user's language**. Keep provider names, method names, JSON keys, and SDK symbols in their native technical form.
- Treat the built-in registry as the supported detection boundary. It covers mainstream providers and wrappers, and can be extended for other surfaces. Do not pretend zero-config support for every unknown provider.
- Separate:
  - **removed / unsupported**
  - **deprecated but still documented**
  - **legacy but still valid**
  - **wrapper-specific compatibility behavior**
  - **configuration mismatch rather than API mismatch**
- Never call something stale based only on a vague vibe, an old-looking snippet, or memory of how the API used to work.

## Workflow

1. **Profile the target**
   - Determine whether the user provided a repo, a diff, one file, or a code snippet.
   - Detect language, runtime, likely package manager, SDK dependencies, wrappers, base URLs, env vars, and model strings.
   - If you can access a repo, prefer the deterministic baseline collector first:
     ```bash
     python3 scripts/collect_llm_api_signals.py /path/to/repo
     ```
   - Record blockers early: no manifests, generated code only, wrapper indirection, hidden provider selection, or missing runtime config.

2. **Resolve the real LLM surface**
   - Identify the actual provider and transport surface in use:
     - direct provider SDK
     - compatibility layer or gateway
     - orchestration wrapper
     - provider-specific pass-through parameters
   - A repo can legitimately contain multiple providers. Do **not** collapse them into one fake "LLM API" bucket.
   - If the target provider is not covered by the built-in registry, add a registry extension or fall back to `provider-ambiguous`. Do not guess.
   - Use direct runtime evidence first. Treat comments and docs as weak evidence.

3. **Verify current docs with Context7**
   - Use the Context7 policy in [`references/context7-usage-policy.md`](references/context7-usage-policy.md).
   - Resolve the relevant SDK or platform docs **per provider and per surface**.
   - Prefer:
     1. official provider SDK docs
     2. official platform docs
     3. compatibility-layer docs
     4. wrapper docs
   - If a wrapper adds runtime semantics, verify **both** wrapper docs and underlying provider docs.
   - Use specific queries tied to:
     - language and SDK
     - version hint from manifests or lockfiles
     - exact method / endpoint / feature surface
     - suspected drift type

4. **Compare code against current expectations**
   Focus on the surfaces that usually drift first:

   - **SDK initialization**
   - **endpoint family** (`responses`, `chat.completions`, `messages`, `generateContent`, etc.)
   - **request schema**
   - **response shape**
   - **tool / function calling**
   - **streaming events**
   - **structured output / schema binding**
   - **model lifecycle**
   - **base_url / deployment / gateway semantics**
   - **auth and environment configuration**
   - **wrapper pass-through behavior**

5. **Classify the findings**
   Map each issue into one of the shared categories below:

   - `scan-blocker`
   - `provider-ambiguous`
   - `docs-unverified`
   - `local-suspicion`
   - `sdk-stale`
   - `endpoint-stale`
   - `request-schema-drift`
   - `response-shape-drift`
   - `tool-calling-drift`
   - `streaming-drift`
   - `structured-output-drift`
   - `model-stale`
   - `auth-config-drift`
   - `compat-layer-drift`
   - `wrapper-pass-through-risk`

   If multiple files express the same underlying problem, merge them into one root-cause finding.

6. **Prioritize by runtime risk and change leverage**
   Use this default order unless the repo clearly needs another one:

   ### Phase 0 - unblock the verdict
   - provider ambiguity
   - missing manifests / lockfiles
   - no way to identify wrapper vs provider semantics
  - Context7 unavailable or docs could not be resolved

   ### Phase 1 - remove hard breakage or obvious drift
   - removed endpoints
   - removed request fields
   - broken model names
   - wrapper usage that no longer maps cleanly to current provider behavior

   ### Phase 2 - normalize preferred current surfaces
   - migrate from legacy-but-valid surfaces when the current surface is clearly better
   - align tool calling, structured outputs, and streaming with current docs
   - tighten client initialization and config handling

   ### Phase 3 - harden against future drift
   - add version pinning or explicit SDK selection
   - centralize provider adapters
   - add CI or review checks
   - document approved API surfaces

7. **Produce dual-audience outputs**
   Always produce:
   - a human-readable report
   - an agent remediation brief
   - a machine-readable summary JSON

8. **Keep the deliverable report-only**
   - prefer precise findings and a clean handoff brief
   - preserve current behavior in any suggested migration path
   - do not silently rewrite a whole provider integration
   - do not "upgrade everything" just because one field is stale

## Provider handling rules

### Direct provider beats wrapper inference

If the code directly imports or instantiates a provider SDK, that is the primary documentation surface.

### Compatibility layers are real surfaces

Treat these as distinct semantics that need their own doc checks:

- Azure OpenAI
- OpenRouter
- Bedrock-hosted provider APIs
- custom `base_url` gateways
- proxies that reinterpret model names or auth

### Wrappers do not remove provider obligations

If the repo uses wrappers like LiteLLM, LangChain, Vercel AI SDK, PydanticAI, or Instructor:

- verify wrapper docs for wrapper-owned behavior
- verify provider docs for provider-owned behavior
- if the wrapper passes raw provider params through, check the raw provider surface too
- if provider cannot be identified confidently, emit `wrapper-pass-through-risk` plus `provider-ambiguous`

### Multiple providers are normal

Split findings by provider and by runtime surface. Do not produce one mushy cross-provider verdict.

### Registry boundary is real

This skill ships with a built-in provider registry for mainstream provider and wrapper surfaces.

- Extend the registry when you need to support an additional provider or gateway.
- Do not claim a provider is supported just because a loose regex happened to match.
- Unknown providers should degrade to `provider-ambiguous` plus `docs-unverified`, not false confidence.

## Human report contract

Use [`assets/human-report-template.md`](assets/human-report-template.md) with [`references/shared-reporting-style.md`](references/shared-reporting-style.md).

This skill adds these freshness-specific requirements:

- clearly say whether this is a **verified**, **blocked**, or internal **local-scan-only** triage artifact
- explain each major finding as **是什么 / 为什么重要 / 建议做什么**
- distinguish hard stale usage, migration candidates, ambiguous cases, and docs-unverified cases
- say which providers / wrappers were checked and which docs were actually verified
- prioritize actions into **现在 / 下一步 / 之后**
- avoid vague “maybe old” hand-waving; every claim must tie back to code evidence or verified doc drift

## Agent brief contract

Use [`assets/agent-brief-template.md`](assets/agent-brief-template.md) with [`references/shared-output-contract.md`](references/shared-output-contract.md).

For each finding, provide:

- `id`
- `provider`
- `kind`
- `severity`
- `confidence`
- `status`
- `scope`
- `title`
- `stale_usage`
- `current_expectation`
- `evidence_summary`
- `decision`
- `recommended_change_shape`
- `validation_checks`
- `docs_verified`
- `autofix_allowed`
- `notes`

## Output contract

Follow [`references/shared-output-contract.md`](references/shared-output-contract.md).
For this skill, the concrete artifact names are:

- `.repo-harness/llm-api-freshness-report.md`
- `.repo-harness/llm-api-freshness-agent-brief.md`
- `.repo-harness/llm-api-freshness-summary.json`

The summary JSON must conform to [`assets/llm-api-freshness-summary.schema.json`](assets/llm-api-freshness-summary.schema.json).

## Severity and confidence model

Use both **severity** and **confidence**.

### Severity

- `critical` - current usage is likely broken now, removed, or blocked by hard provider changes
- `high` - real runtime risk, real migration pressure, or a high-churn surface is clearly drifting
- `medium` - credible drift or compatibility risk, but not obviously a hard failure
- `low` - hygiene, guardrails, or long-tail normalization

### Confidence

- `high` - direct code evidence plus current official docs line up clearly
- `medium` - docs are good, but runtime version or wrapper behavior has some ambiguity
- `low` - provider resolution, wrapper semantics, or live-doc verification is incomplete

Never present a `low`-confidence suspicion as a hard fact.

## Fleet baseline mode

When another skill or CI needs stable artifacts quickly, run:

```bash
bash scripts/run_all.sh /path/to/repo
```

This helper first enforces runtime bootstrap. If Context7 is unavailable, it emits blocked artifacts and exits non-zero. When Context7 is available, it can still emit a **local-scan-only** triage baseline:

- `.repo-harness/llm-api-signals.json`
- `.repo-harness/llm-api-freshness-report.md`
- `.repo-harness/llm-api-freshness-agent-brief.md`
- `.repo-harness/llm-api-freshness-summary.json`

It does **not** pretend that current docs were verified.

## Safety rules

- Default mode is **report-only**.
- Do not silently replace a provider, gateway, or wrapper.
- Do not upgrade SDKs as a side effect of a diagnosis run.
- Do not recommend destructive refactors as the first move.
- Never leak API keys, org IDs, or proprietary prompts into Context7 queries.
- Do not call a gateway or wrapper "OpenAI-compatible" in a way that hides real semantic differences.

## Final reminder

This skill is for **freshness verification, drift detection, and migration planning**.

It is **not** a blind "upgrade the whole LLM stack" skill.

When in doubt:

- identify the real provider surface
- verify against current docs
- say exactly what is known
- mark what is not verified
- keep destructive change opt-in
