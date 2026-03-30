# Distributed Side-Effect Hardgate Agent Brief

Use short, hard, decision-level language. Do not write long tutorials.

## Context

- overall_verdict: `{{overall_verdict}}`
- repo_root: `{{repo_root}}`

## Ordered actions

1. `{{action_1}}`
2. `{{action_2}}`
3. `{{action_3}}`

## Findings

Repeat this block per finding:

```yaml
- id: dsh-001
  category: dual-write-hazard
  severity: critical
  confidence: high
  title: DB commit and broker publish occur in the same flow
  path: services/orders/confirm.py
  line: 84
  evidence_summary: session.commit() is followed by event_bus.publish(...) with no visible outbox handoff
  decision: harden
  change_shape: introduce transactional outbox between persistence and broker publication
  validation: rerun distributed-side-effect scan; add crash-window test or relay test
  merge_gate: block-now
  autofix_allowed: false
  notes: mechanical edits are unsafe until transaction boundary is clarified
```
