---
name: error-governance-hardgate
description: "Audits Python / TypeScript repositories for public error-contract governance, Problem Details alignment, structured error-code discipline, protocol drift, outward leakage, and SSOT/codegen gaps. Use for 全局错误处理审计、业务错误码治理、Problem Details review、OpenAPI/AsyncAPI 错误契约对齐、error catalog drift、message-text branching 检查. Produces a blunt human report, a concise agent brief, and a machine-readable summary."
---

# Error Governance Hardgate

This skill audits whether a repository exposes one coherent, durable, public error contract.

It is report-only by default. It does not implement refactors or rewrite handlers unless the user explicitly asks for code changes after the audit.

## When to use this

Use this skill when the user wants to:

- audit a repo for global error handling and business error-code governance
- check whether HTTP and async/error-message surfaces share one contract
- review Problem Details usage, `application/problem+json`, or shared error-schema discipline
- find message-text branching instead of stable structured keys such as `code`
- check whether error catalogs, generated Python / TypeScript artifacts, docs, and handlers drift apart
- review public leakage risk in outward-facing errors

## Do not use this

Do not use this skill as the primary skill when the user mainly wants:

- one local exception root-cause fix with no public contract question
- generic bug fixing or feature implementation
- broad schema or merge-gate review unrelated to error governance
- documentation-only education about RFC 9457 with no repository surface to inspect

## Inputs and outputs

Deterministic baseline input:

- repository root path

Required outputs:

- `.repo-harness/skills/error-governance-hardgate/summary.json`
- `.repo-harness/skills/error-governance-hardgate/report.md`
- `.repo-harness/skills/error-governance-hardgate/agent-brief.md`

Final checks:

- summary shape validates
- runtime sidecar is updated truthfully
- blocked prerequisites emit blocked artifacts instead of a fake success verdict

## Reading map

Read only what you need.

- `assets/human-report-template.md`
- `assets/agent-brief-template.md`
- `assets/error-governance-summary.schema.json`
- `references/shared-output-contract.md`
- `references/shared-reporting-style.md`
- `references/shared-runtime-artifact-contract.md`
- `references/error-governance-standard.md`
- `references/audit-policy.md`
- `references/evals.md`
- `scripts/run_all.sh`
- `scripts/run_error_governance_scan.py`
- `scripts/validate_error_governance_summary.py`

## Operating stance

- Prefer runtime code, shared schemas, contracts, catalogs, generated artifacts, and tests over comments and prose.
- Keep evidence separate from inference.
- Treat message-text branching, outward leakage, split public shapes, and no-SSOT setups as the highest-signal problems.
- Keep recommendations structural and reversible.
- Mark `not-applicable`, `unverified`, or blocked states honestly when evidence is weak.

## Deterministic workflow

Run the wrapper from the skill directory:

```bash
bash scripts/run_all.sh /path/to/repo
```

Or run the underlying pieces directly:

```bash
python3 scripts/run_error_governance_scan.py \
  --repo /path/to/repo \
  --out .repo-harness/skills/error-governance-hardgate/summary.json

python3 scripts/validate_error_governance_summary.py \
  --summary .repo-harness/skills/error-governance-hardgate/summary.json
```

The scanner is a conservative baseline. It should:

- discover OpenAPI / AsyncAPI / schema / catalog / generated-type / handler surfaces
- identify credible Problem Details and structured-code evidence
- detect high-signal governance drift such as message-text branching, outward leakage, and missing SSOT/codegen discipline
- produce gate states, findings, top actions, and dual-audience artifacts

## Finding taxonomy

Use these categories where possible:

- `scan-blocker`
- `universal-problem-gap`
- `field-pattern-gap`
- `numeric-or-vague-code`
- `text-branching`
- `type-code-drift`
- `http-mapping-gap`
- `async-contract-gap`
- `traceability-gap`
- `retry-semantics-gap`
- `validation-shape-gap`
- `leakage-risk`
- `no-global-handler`
- `ssot-missing`
- `codegen-drift`
- `ci-gate-missing`
- `docs-runtime-drift`

Merge duplicate symptoms into one root-cause finding.

## Gate model

The summary must include gate states for at least:

- universal problem shape
- stable business codes
- protocol alignment
- boundary safety
- SSOT and code generation

Each gate must use one of:

- `pass`
- `watch`
- `fail`
- `not-applicable`
- `unverified`

## Quality bar

A good result from this skill does all of the following:

- states whether the repo has one public error contract or several conflicting ones
- identifies whether clients can branch on stable keys instead of prose
- distinguishes runtime truth from contract/docs truth
- names the smallest structural hardening move with the highest leverage
- gives one short human report and one short agent brief without tutorial bloat
