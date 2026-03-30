---
name: python-ts-security-posture-audit
description: Audits Python and TypeScript repos for modern baseline security posture across dependency-audit signals, Bandit-style Python scanning, uv and pnpm lockfile discipline, and ignore governance. Use for baseline security review, lockfile policy checks, CI gate reporting, and repo-health security posture reporting. Produces a blunt human report, a concise agent brief, and a machine-readable summary.
---
# Python TS Security Posture Audit

Use this skill when the repo has Python or TypeScript dependency risk and the user wants a baseline security-posture judgment, not a full security assessment.

Do not use it for secrets, containers, cloud posture, infrastructure, runtime hardening, or auto-remediation.

## Core stance

- Scope is Python / TypeScript only. Package-manager assumptions are `uv` and `pnpm`.
- Preferred modern evidence is lockfile-backed installs, reproducible dependency-audit signals, Bandit-style Python scanning, and explicit ignore governance.
- This skill only detects and reports. It does not patch dependencies or rewrite workflows.
- This is baseline posture, not a complete application security audit.

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

1. whether Python dependency risk is assessed in a lockfile-backed, reviewable way
2. whether TS / Node dependency risk is assessed through the pnpm workflow
3. whether Python code receives a real static-security scan
4. whether `uv.lock` and `pnpm-lock.yaml` are treated as real control surfaces
5. whether ignores, baselines, and blocked cases stay explicit instead of being silently normalized

## Workflow

1. Detect whether Python or TypeScript dependency risk exists. If not, return `not-applicable`.
2. Check lockfiles before trusting any vulnerability claims.
3. Separate Python dependency audit posture, TS dependency audit posture, and Python static scan posture.
4. Treat private registry ambiguity and missing lockfiles as trust blockers, not clean bills of health.
5. Keep ignore governance visible as a first-class category.

## Output rules

- Lead with the boundary: this is baseline posture only.
- Keep Python dependency risk, TS dependency risk, static scanning, lock discipline, and ignore governance separate.
- Use the standard namespaced artifacts under `.repo-harness/skills/python-ts-security-posture-audit/`.

## Safety rules

- Report only.
- Do not auto-upgrade dependencies, rewrite lockfiles, or silence findings.
- Do not pretend blocked or registry-limited runs are clean.
- Do not market this as a full security review.
