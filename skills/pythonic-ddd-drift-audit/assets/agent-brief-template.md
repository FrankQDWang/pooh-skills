# Pythonic DDD Drift Audit Agent Brief

Use short, decision-level language.

## Context

- overall_verdict: `{{overall_verdict}}`
- repo_root: `{{repo_root}}`

## Ordered actions

1. `{{action_1}}`
2. `{{action_2}}`
3. `{{action_3}}`

## Findings

```yaml
- id: pdd-001
  category: domain-boundary-leak
  severity: high
  confidence: high
  title: Domain package imports framework / ORM code
  path: src/orders/domain/model.py
  line: 12
  evidence_summary: domain module imports sqlalchemy and fastapi types directly
  decision: harden
  change_shape: move framework dependency behind adapter and keep domain package pure
  validation: rerun pythonic-ddd-drift scan; verify domain package no longer imports infra / transport modules
  merge_gate: block-now
  autofix_allowed: false
  notes: manual restructuring is required; this repository only reports and hands off the work
```
