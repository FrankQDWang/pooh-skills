# Module Shape Hardgate Agent Brief

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
- id: msh-001
  category: god-module
  severity: high
  confidence: high
  title: API module became a catch-all hotspot
  path: app/api/router.py
  line: 1
  evidence_summary: file is 1380 code lines, imports 21 modules, mixes FastAPI routes, Pydantic schemas, DB access, retry logic, and formatting helpers
  decision: split
  change_shape: split route entrypoints, transport/schema shaping, and persistence orchestration into separate modules
  validation:
    - rerun module-shape-hardgate
    - verify route file drops below file NLOC threshold
    - verify handlers no longer import DB/session objects directly if a narrower adapter exists
  merge_gate: block-changed-files
  autofix_allowed: false
  notes: keep the report structural; do not redesign business rules unless the user asks
```
