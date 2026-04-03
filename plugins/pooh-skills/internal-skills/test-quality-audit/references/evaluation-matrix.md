# Evaluation matrix

Category states:

- `clean`: the local evidence does not show the targeted governance problem
- `watch`: the local evidence shows a meaningful governance gap or suspicious habit
- `blocked`: a required local scan surface failed before it could be judged truthfully
- `not-applicable`: the repo does not expose a relevant surface for that category

Confidence levels:

- `high`: the signal is explicit and hard to misread
- `medium`: the signal is good but still heuristic
- `low`: the signal is weak or incomplete and should be treated cautiously

Overall verdict rules:

- `clean` when every in-scope category is `clean`
- `watch` when any in-scope category is `watch`
- `scan-blocked` only when a required local scan surface fails truthfully
- `not-applicable` only when every category is `not-applicable`

Boundary rules:

- Browser fidelity, visual regression, accessibility automation, and CI trace artifacts belong to `ts-frontend-regression-audit`
- Temporal replay, time-skipping, fake-model verification, and durable execution harness quality belong to `pydantic-ai-temporal-hardgate`
- Raw coverage percentages do not change verdicts in this skill
