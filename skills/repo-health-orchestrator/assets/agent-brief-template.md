# Repo Health Orchestrator Agent Brief

Keep this brief short and action-ordered.

## Overall

- overall_health: `{{overall_health}}`
- coverage_status: `{{coverage_status}}`
- summary_line: `{{summary_line}}`

## Domains

```yaml
- domain: distributed-side-effects
  skill_name: distributed-side-effect-hardgate
  status: present
  dependency_status: ready
  child_verdict: unsafe
  top_categories:
    - dual-write-hazard
    - idempotency-gap
  top_action: introduce durable handoff / outbox before broker publish
  why_now: blocker-level reliability risk is already visible
  handoff_notes: do not trust retries until idempotency is visible
```

## Action queue

1. `{{action_1}}`
2. `{{action_2}}`
3. `{{action_3}}`
