# Tooling Policy

## Canonical baseline

The canonical baseline for this skill is the deterministic repository-local scanner in `scripts/run_secrets_and_hardcode_scan.py`.

Reason: the first version needs one controlled machine contract across working tree, git history, hardcoded credential literals, and ignore discipline without adding a multi-tool vendor pile.

## Current evidence order

1. high-signal secret material in the working tree
2. git-history matches for the same high-signal patterns
3. hardcoded credential literals in code or config
4. `.gitignore` coverage for common secret-bearing files

## Out of scope

- full appsec
- container or infrastructure secrets posture
- secret rotation or history rewrite automation
- broad generic entropy scanning with high false-positive rates
