# Overdefensive Silent Failure Agent Brief

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
- id: osf-001
  category: exception-swallow
  severity: high
  confidence: high
  language: python
  title: except Exception: pass suppresses the real failure
  path: src/orders/service.py
  line: 42
  evidence_summary: broad handler discards the error instead of surfacing it or making degradation explicit
  decision: restore-contract
  change_shape: catch only the expected exception, emit explicit degrade state if needed, otherwise let the failure surface
  validation: rerun overdefensive scan; verify the path now logs / metrics / fails loudly as intended
  merge_gate: block-changed-files
  autofix_allowed: true
  notes: replacing `pass` with another silent default is not a fix
```
