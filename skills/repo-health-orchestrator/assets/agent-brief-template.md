# Repo Health Orchestrator Agent Brief

Keep this brief short and action-ordered.

## Overall

- overall_health: `{{overall_health}}`
- coverage_status: `{{coverage_status}}`

## Domains

```yaml
- domain: distributed-side-effects
  skill_name: distributed-side-effect-hardgate
  status: present
  child_verdict: unsafe
  top_categories:
    - dual-write-hazard
    - idempotency-gap
  top_action: introduce durable handoff / outbox before broker publish
  merge_gate_bias: block-now
  notes: do not trust retries until idempotency is visible
```

## Action queue

1. `{{action_1}}`
2. `{{action_2}}`
3. `{{action_3}}`
