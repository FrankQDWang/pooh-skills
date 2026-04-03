---
name: secrets-and-hardcode-audit
description: Audits repositories for working-tree secret exposure, git-history secret leakage, hardcoded credential material, and ignore discipline. Use for secret hygiene review, leaked token triage, hardcoded credential detection, and repo-health security reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# Secrets and Hardcode Audit

Use this skill when the repo may be leaking secrets, carrying hardcoded credentials, or missing basic ignore discipline.

Do not use it for container scanning, cloud posture, runtime hardening, full application security review, or automatic secret remediation.

## Core stance

- First iteration bias: one repo-local deterministic scanner, not a pile of vendor tools.
- Scope is narrow: working tree, git history, hardcoded credential material, and ignore discipline.
- This skill detects and reports only. It does not rotate keys, rewrite git history, or delete files automatically.
- `python-ts-security-posture-audit` covers baseline dependency and static-security posture. This skill covers secrets and credential material specifically.

## Read when needed

- [assets/human-report-template.md](assets/human-report-template.md)
- [assets/agent-brief-template.md](assets/agent-brief-template.md)
- [references/shared-output-contract.md](references/shared-output-contract.md)
- [references/shared-reporting-style.md](references/shared-reporting-style.md)
- [references/shared-runtime-artifact-contract.md](references/shared-runtime-artifact-contract.md)
- [references/tooling-policy.md](references/tooling-policy.md)
- [references/evaluation-matrix.md](references/evaluation-matrix.md)
- [references/evals.md](references/evals.md)

## What to judge

1. whether high-signal secret material is visible in the current working tree
2. whether git history still shows past secret leakage that needs rotation or rewrite review
3. whether code or config carries hardcoded credential literals that should move behind environment or secret-manager boundaries
4. whether `.gitignore` discipline covers common secret-bearing files instead of relying on luck

## Workflow

1. Scan text and config surfaces for high-signal secret patterns and hardcoded credential literals.
2. Check whether the checkout has accessible git history. If history cannot be inspected, say so as a trust gap instead of pretending the repo is clean.
3. Keep working-tree exposure, history exposure, credential literals, and ignore discipline separate.
4. Prefer high-signal evidence over broad pattern spam. Skip obvious placeholders, examples, and templated values.
5. Use the standard namespaced artifacts under `.repo-harness/skills/secrets-and-hardcode-audit/`.

## Output rules

- Lead with the boundary: this is secret hygiene and credential-material review, not full appsec.
- Separate active working-tree exposure from history-only exposure.
- Treat ignore discipline as a first-class control surface, not a side note.
- If git history is unavailable, keep that uncertainty visible in the report and brief.

## Safety rules

- Report only.
- Do not print full secret values in the artifacts; redact to short previews.
- Do not rewrite git history, rotate credentials, or delete tracked files automatically.
- Do not downgrade a high-signal secret finding just because the repo also has placeholders elsewhere.
- Do not call the repo clean if history coverage is missing and other evidence is weak.
