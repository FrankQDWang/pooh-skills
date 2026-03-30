# Evaluation Matrix

Use these state labels consistently.

## Primary states

* `missing` — the repo has no credible in-scope control for this category.
* `theater` — files or configs exist, but there is no proof that they run, gate, or cover the claimed surface.
* `partial` — some real coverage exists, but the control is split, easy to bypass, or missing important surfaces.
* `enforced` — the main control runs in normal developer workflow and CI, and findings can block merges or releases.
* `hardened` — the control is enforced, scoped cleanly, has suppression discipline, and has evidence designed for long-term maintenance.

## Auxiliary states

* `unverified` — local evidence suggests the gate exists, but this run cannot prove remote enforcement.
* `blocked` — the audit cannot reach a fair conclusion because a required runtime dependency, lockfile, or accessible surface is missing.
* `not-applicable` — the repository does not contain the relevant surface.

## Confidence

* `high` — config, lockfiles, scripts, and CI evidence are mutually consistent.
* `medium` — most evidence is credible, but some execution or workspace coverage is incomplete.
* `low` — scanner output is likely distorted by missing config, partial install state, or inaccessible surfaces.

## Overall verdict rule

Use the weakest material in-scope category as the leading narrative, but keep per-category results explicit.

* If every in-scope category is `not-applicable`, the overall verdict is `not-applicable`.
* If one or more required categories are `blocked`, the overall status may be `blocked` even if some local evidence exists.
* Never collapse `blocked` or `unverified` into `enforced` or `hardened`.
