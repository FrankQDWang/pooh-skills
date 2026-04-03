# Evaluation Matrix

Use these state labels consistently.

## Category states

- `clean` — no high-signal exposure or discipline gap was found in this category.
- `watch` — credible exposure, trust gap, or discipline weakness needs action.
- `blocked` — the scan could not reach a fair result because the required surface failed to execute truthfully.
- `not-applicable` — the repository does not expose this category in a meaningful way.

## Confidence

- `high` — the evidence is direct and low-noise.
- `medium` — the evidence is credible, but context is incomplete.
- `low` — the signal is weak or the surface is only partially visible.

## Overall verdict

- `clean` when all in-scope categories are `clean`
- `watch` when any in-scope category is `watch`
- `scan-blocked` only when a required scan surface fails to execute truthfully
- `not-applicable` when every category is `not-applicable`
