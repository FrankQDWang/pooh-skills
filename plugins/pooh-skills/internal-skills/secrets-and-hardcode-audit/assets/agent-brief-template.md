# Secrets and Hardcode Audit Agent Brief

## Objective
Describe active secret exposure, history leakage, hardcoded credential material, and ignore-discipline gaps without printing full secret values.

## Target shape
- secrets move behind env or secret-manager boundaries
- tracked secret-bearing files stop relying on luck or local conventions
- history leakage gets explicit rotate / revoke / rewrite review

## Required checks
```bash
bash scripts/run_all.sh /path/to/repo
```

## Guardrails
- redact secret previews
- do not auto-rotate or auto-rewrite history
- keep working-tree exposure separate from history-only exposure

## Expected output
1. concise summary
2. exact files or commits needing review
3. exact ignore-discipline gaps
4. validation commands and results
5. residual risks
