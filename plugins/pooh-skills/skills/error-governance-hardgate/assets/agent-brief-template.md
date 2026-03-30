# Error Governance Hardgate Agent Brief

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
- id: egh-001
  category: text-branching
  severity: critical
  confidence: high
  scope: services/orders/api.py
  title: Business control flow depends on error message text
  evidence_summary: Client and server code branch on substring checks like "not found" and "expired" instead of stable error codes.
  decision: harden-now
  recommended_change_shape: Replace message-text branching with shared structured `code` handling and generated type definitions.
  validation_checks:
    - Add tests proving the same `code` survives localization or copy changes.
    - Verify no production branch logic reads `title` or `detail`.
  merge_gate: block-now
  notes: Message text is for humans; public branching keys must stay stable.
```
