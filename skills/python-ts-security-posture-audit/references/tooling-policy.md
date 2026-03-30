# Tooling Policy

## Default stance

This audit judges baseline security posture for Python / TypeScript repos with a modern control bias:

- `uv` and `pnpm` are the package-manager assumptions
- lockfiles are part of the security control surface, not optional metadata
- Python code should have a real static-security signal such as Bandit
- dependency-audit and ignore posture must stay reviewable in CI

## Scoring bias

- `hardened`: lockfiles, dependency-audit signals, static scanning, and ignore governance all reinforce each other.
- `enforced`: the modern baseline exists, but one area still needs stronger CI evidence or cleanup.
- `partial`: the repo has some controls, but they are local-only, incomplete, or weakly governed.
- `blocked`: missing lockfiles, private registry opacity, or missing trust prerequisites make the posture unverifiable.
- `missing`: no credible baseline security posture is visible.

## Evidence to trust

1. `uv.lock` and `pnpm-lock.yaml`
2. CI-visible dependency-audit entries
3. Bandit or equivalent Python static-security entries
4. frozen or immutable install paths
5. explicit ignore, allowlist, or baseline governance

## Out of scope

- secret scanning
- container or OS CVEs
- infrastructure or cloud posture
- full application security assessment
