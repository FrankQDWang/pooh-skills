# LLM API Freshness Audit

## Verdict
- Overall verdict:
- Verification mode: `verified` | `blocked` | `local-scan-only`
- Trust level: `verified` means current docs were actually checked; `blocked` means runtime prerequisites prevented a valid audit; `local-scan-only` means this run is triage, not truth.
- Providers in scope:
- Wrappers / gateways in scope:
- Highest-risk surface:
- What is definitely stale right now:
- What is only a migration candidate:
- What is still ambiguous:

## Executive diagnosis
Write 1 short paragraph. Be blunt. Say whether the repo is genuinely drifting or just carrying one legacy-but-valid surface.

## 现在最该做的事
1.
2.
3.

## What was checked
- Code / repo scope:
- Manifests / lockfiles:
- Current docs checked:
- Current docs not checked:
- Context7 notes:
- Version hints used:

## Main findings

### [finding-id] [title]
- Provider:
- Kind:
- Severity:
- Confidence:
- Status:
- Scope:
- 是什么：
- 为什么重要：
- 建议做什么：
- 代码证据：
- 当前文档期望：
- Notes:

### [finding-id] [title]
- Provider:
- Kind:
- Severity:
- Confidence:
- Status:
- Scope:
- 是什么：
- 为什么重要：
- 建议做什么：
- 代码证据：
- 当前文档期望：
- Notes:

## Blockers and ambiguity
List the reasons a verdict is incomplete, if any. Be honest. Examples:
- provider hidden behind wrapper or config
- Context7 unavailable
- version cannot be determined
- code path appears dead or generated
- multiple gateways with different semantics

## Prioritized plan

### 现在
- hard failures
- removed fields / endpoints
- broken model names
- wrapper/provider mismatches with runtime risk

### 下一步
- migrations from legacy-but-valid surfaces
- tool calling / streaming / structured output normalization
- client init cleanup

### 之后
- adapters, guardrails, CI checks, docs, policy

## Skipped checks
List what you intentionally did not verify and why.
