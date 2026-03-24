---
name: dependency-audit
description: "Audit Python / TypeScript / mixed monorepos for dependency direction, boundary leaks, cycles, and dead-code signals with Tach, Dependency Cruiser, and Knip. Use for 仓库依赖巡检、架构边界审计、repo audit、monorepo diagnosis、cleanup planning. Produce a sharp, plain-language human report plus a concise remediation brief for Codex / Claude Code. Default to report-only unless fixes are explicitly requested."
---

# Dependency Audit Skill

## When to use this

Use this skill when the user wants to:

- scan or audit a repository / monorepo for architecture, dependency, or dead-code health
- understand whether and how to use **Tach**, **Dependency Cruiser**, and **Knip** in a real repo
- generate a diagnosis that both a non-programmer and a strong coding agent can act on
- plan gradual normalization, CI guardrails, or cleanup strategy for Python / TypeScript codebases
- turn raw tool output into a decision-ready report instead of a wall of logs

Do **not** use this skill for:

- routine feature implementation
- generic bug fixing unrelated to repo structure, dependency governance, or cleanup
- aggressive auto-cleanup when the user only asked for analysis
- producing long step-by-step command tutorials unless the user explicitly asks for them

## Mission

Your job is to **detect, explain, prioritize, and recommend**.

## Reading map

- When producing the human report, start from [`assets/human-report-template.md`](assets/human-report-template.md).
- When producing the agent remediation brief, start from [`assets/agent-brief-template.md`](assets/agent-brief-template.md).
- When you need guidance on tool interpretation, repair patterns, false-positive handling, or reporting tone, read [`references/tooling-policy.md`](references/tooling-policy.md).

Use some or all of these tools depending on the repo:

- **Tach** for Python module boundaries, public interfaces, declared dependency consistency, and cycles
- **Dependency Cruiser** for JS/TS dependency rules, cycles, forbidden imports, dependency graph governance, and gradual rollout via baseline/ignore-known style workflows
- **Knip** for unused files, unused dependencies, unused exports/types, and optional low-risk cleanup opportunities

The output has **two readers**:

1. **Human reader**: can be non-technical, but still wants a blunt, decision-ready diagnosis. Explain each problem as **是什么 / 为什么重要 / 下一步做什么**.
2. **Coding agent**: Codex, Claude Code, or similar. Give **decision-level repair guidance**, not long tutorials. Assume the agent can handle execution details.

## Operating stance

- Default to **scan + report**.
- Prefer **safe, incremental rollout** over “fix everything now”.
- Prefer **grounded assumptions** over stalling. If something is uncertain, state the assumption and continue.
- Use the **minimum toolset** that matches the repo.
- Merge duplicate findings across tools into a **single root-cause narrative**.
- Avoid dumping raw logs unless they clarify a blocker.
- Keep the report decision-rich and command-light.
- Write in the **user’s language**. Keep tool names, config keys, and issue types in their native technical form when useful.

## Workflow

1. **Profile the repository**
   - Detect whether the repo is Python, JS/TS, or mixed.
   - Detect monorepo/workspace shape, likely package manager, and whether dependencies/config appear complete enough for high-confidence scanning.
   - Note obvious blockers early: missing lockfiles, missing tsconfig, broken workspace layout, missing Python dependency metadata, etc.

2. **Choose the toolset and justify it**
   - Python only → use **Tach**.
   - JS/TS only → use **Dependency Cruiser + Knip**.
   - Mixed repo → use all applicable tools, but keep Python and JS/TS findings separated before synthesizing them.
   - If a tool is skipped, say **why**.

3. **Adopt a conservative configuration posture**
   - Start from the least risky workable setup.
   - Prefer configuration alignment and baseline generation before hard enforcement.
   - Do not tighten rules to the point that the first report becomes unusable noise.

4. **Run the scans and normalize the findings**
   - Prefer structured output when available.
   - Map tool-native output into a shared set of issue categories.
   - Distinguish between **hard problems in the repo** and **scanner-confidence problems** caused by missing configuration.

5. **Prioritize by risk and leverage**
   - Handle blockers and high-signal architecture issues before cosmetic cleanup.
   - Recommend the smallest set of changes that meaningfully improves repo health.
   - Separate “do now”, “do next”, and “do later”.

6. **Produce dual-audience outputs**
   - Human-first report
   - Agent-first remediation brief
   - Optional summary JSON if helpful

7. **Only if explicitly requested: propose or apply low-risk fixes**
   - Low-risk and mechanical only.
   - Risky or destructive actions stay opt-in.

## Tool selection rules

### Tach policy

Use Tach when Python structure matters.

Priorities:

- forbidden module dependency / wrong dependency direction
- public interface violation
- dependency cycle
- undeclared or mismatched external dependency usage

Guidance:

- Start conservatively; initial Python boundary governance matters more than perfect strictness.
- Infer `source_roots` carefully for common layouts such as `src/`, `backend/`, or multiple package `src/` directories.
- Prefer a permissive initial `root_module` posture unless the user explicitly wants strict full coverage.
- Treat `check-external` style conclusions as lower confidence if the Python environment is obviously incomplete.
- Recommend **config fixes or import-path fixes** before broad rewrites.

### Dependency Cruiser policy

Use Dependency Cruiser when JS/TS dependency structure matters.

Priorities:

- cycles
- forbidden cross-layer / cross-boundary imports
- missing or invalid dependency declarations
- production code depending on dev-only things
- orphaned or structurally isolated files when they reflect real design drift

Guidance:

- Prefer structured output and summarize rule violations instead of restating raw output.
- In legacy repos, recommend a **baseline / ignore-known style rollout** so the team can block new violations without being buried by historical debt.
- Be careful in monorepos: if dependency declarations are centralized at the repo root, account for that in your interpretation.
- Separate “architecture rule problem” from “configuration not yet mature enough”.

### Knip policy

Use Knip when unused code or dependency hygiene matters.

Priorities:

- unused files
- unused dependencies
- unused exports / types
- unlisted or unresolved dependencies

Guidance:

- Treat **unused files** as earlier cleanup than unused dependencies or exports because they often explain follow-on noise.
- Results can be noisy if entry/project/workspace coverage is weak. Say so when confidence is only moderate.
- If the user explicitly asks for autofix, keep it conservative by default: exports, types, dependencies.
- **Never assume file deletion is safe by default.** File removal is opt-in and high caution.
- Explain cascade effects: cleaning unused files can eliminate many secondary warnings.

## Shared finding taxonomy

Map findings into these root categories when possible:

- `scan-blocker` — the tool could not produce reliable results
- `config-gap` — the repo is missing configuration needed for confident scanning
- `architecture-violation` — forbidden boundary or public interface breach
- `cycle` — circular dependency or cyclic module relationship
- `dependency-declaration-gap` — imported/used dependency is not declared correctly, or declaration exists but appears unnecessary
- `unused-file`
- `unused-dependency`
- `unused-export`
- `unresolved-import`
- `orphan-or-isolated-module`

If two tools point at the same root cause, merge them into one finding and mention both sources.

## Prioritization and rollout strategy

Use this default order unless the repo clearly needs a different sequence:

### Phase 0 — unblock the scan

- missing configuration
- missing dependency metadata
- workspace layout ambiguity
- obviously incomplete environment that makes output unreliable

### Phase 1 — remove noise safely

- Knip: unused files first
- then unused dependencies / exports / types
- keep file deletion opt-in

### Phase 2 — freeze structural debt

- Dependency Cruiser: establish rules and a baseline so new violations are blocked even if old ones remain

### Phase 3 — tighten Python boundaries

- Tach: align config, then enforce dependency direction and public interface discipline

### Phase 4 — raise strictness only after the repo stabilizes

- stricter boundary coverage
- external dependency consistency checks
- narrower public APIs

Do **not** recommend “fail CI on everything immediately” for a large legacy repo unless the repo is already close to clean.

## Human report contract

Always produce a human-readable report. Use `assets/human-report-template.md` as the starting shape.

The human report must:

- avoid unexplained jargon
- explain every major finding with:
  - **是什么**
  - **为什么重要**
  - **建议做什么**
- state which tools were used and why
- separate certain findings from provisional / low-confidence findings
- prioritize actions into **现在 / 下一步 / 之后**
- explain why “baseline first” or “scan first, fix later” may be the right decision
- call out any skipped checks and the reason they were skipped
- stay readable for a non-technical human even when the tone is sharp
- use a direct, Linus-style tone when the design deserves criticism
- tie every harsh statement to concrete technical evidence, risk, or structural damage
- avoid empty insults, vague venting, or emotional language without a next step

For a non-programmer, translate common terms in plain language:

- dependency → “这个代码需要依赖的外部包或内部模块”
- cycle → “两个或多个模块互相绕回来依赖，导致结构纠缠”
- public interface violation → “代码没有从规定的公开入口使用模块，而是绕进去直接拿内部实现”
- unused dependency → “项目声明了这个包，但当前实际代码看起来没有在用”
- unused file → “文件存在，但没有被真正接入到运行路径或构建入口”

## Agent brief contract

Always produce a concise remediation brief for a strong coding agent. Use `assets/agent-brief-template.md` as the starting shape.

For each finding, provide:

- `id`
- `tool`
- `severity`
- `confidence`
- `scope`
- `title`
- `evidence_summary`
- `decision`
- `recommended_change_shape`
- `validation_checks`
- `autofix_allowed`
- `notes`

Agent guidance should be:

- short
- unambiguous
- patch-oriented
- free of long tutorials unless absolutely necessary

Prefer recommendation shapes like:

- create or refine a baseline
- move imports to the public API surface
- add or remove a dependency declaration
- break a cycle by extracting an interface or moving shared code
- tighten workspace / entry / project config
- quarantine known violations and block new ones
- defer high-risk cleanup until scan confidence improves

## Output contract

When you can write files, create:

- `.repo-harness/repo-audit-report.md`
- `.repo-harness/repo-audit-agent-brief.md`
- `.repo-harness/repo-audit-summary.json` (optional but preferred if structured data is available)

If the environment does not allow file creation, present the same structure directly in the response.

## Severity and confidence model

Use both **severity** and **confidence**.

### Severity

- `critical` — structural failures that can break builds, runtime correctness, or major architecture boundaries
- `high` — repeated boundary problems, missing runtime dependency declarations, or widespread cycles / cross-layer leaks
- `medium` — real cleanup opportunities or configuration gaps with moderate impact
- `low` — mostly hygiene improvements or low-risk polish items

### Confidence

- `high` — repo metadata and scanner coverage look credible
- `medium` — mostly credible, but some config coverage is incomplete
- `low` — scanner output is likely distorted by missing config or partial environment

Never present a low-confidence scanner guess as a hard fact.

## Safety rules

- Default mode is **report-only**.
- Do not delete files unless the user explicitly asks for it.
- Do not recommend wide auto-fixes as the first move in a large repo.
- If proposing autofix, clearly mark what is safe, what is risky, and what should stay manual.
- Prefer incremental CI guardrails over sudden full enforcement.
- If the repo is dirty or unstable, say so and recommend report-first.

## What good looks like

A strong result from this skill has all of the following:

- the chosen toolset is justified
- scan blockers are explicit
- duplicate findings are merged into root causes
- the human report is easy to understand while staying sharp
- the agent brief is concise and actionable
- recommendations focus on decisions, not command trivia
- risky automation is clearly gated
- the rollout path is realistic for the repo’s maturity

## Final reminder

This skill is for **detection, explanation, prioritization, and normalization planning**.

It is **not** a “fix everything automatically” skill.

When in doubt:

- be conservative
- explain the tradeoff
- recommend the next best decision
- keep destructive actions opt-in
