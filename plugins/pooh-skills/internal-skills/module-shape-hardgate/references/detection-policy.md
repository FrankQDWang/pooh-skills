# Detection policy

## Supported surface

This skill only audits **Python** (`.py`) and **TypeScript** (`.ts`, `.tsx`) source files.

It is intentionally **report-only**. It does not refactor or auto-fix.

## Core idea

“Low cohesion” must be turned into concrete, inspectable signals. This skill therefore treats the following as the main evidence classes:

- oversized file
- long function
- hub module (very wide fan-out)
- mixed responsibility
- export surface sprawl
- duplication cluster
- composite god-module pressure

## Default thresholds

These are the baseline thresholds used by the deterministic scanner.

| Signal | Warn | Hard-gate pressure | Critical |
|---|---:|---:|---:|
| File code lines | 500 | 900 | 1800 |
| Function code lines | 80 | 120 | 200 |
| Approx. complexity | 15 | 25 | 40 |
| Fan-out imports | 12 | 18 | 25 |
| Export count | 15 | 25 | 40 |

## Strong evidence

Treat these as high-confidence:

- file size far above threshold
- multiple shape signals concentrated in one file
- one or more obviously overlong functions
- very wide import fan-out
- very wide export surface
- repeated duplicate code windows

## Moderate signals

Treat these as report-worthy but not absolute:

- responsibility tags inferred from framework imports, file suffixes, and path segments
- registry/barrel files that are large but narrow in behavior
- large schema definition files
- large test files
- files that look generated but are not trivially classifiable

The scanner should not treat arbitrary identifier text in source bodies as responsibility proof. Generic names such as `next_actions` or `component_count` are not UI evidence by themselves.

## Exemptions and softening rules

The scanner should soften or skip findings for:

- generated or vendored code
- migration history / snapshots
- narrow re-export barrels with little logic
- test-only hotspots where production risk is limited

Softening does **not** mean silence when a file is both exempt-looking and obviously hand-written, logic-heavy, and shape-degrading.

## Composite god-module rule

A file should be considered a `god-module` candidate when it triggers several of the following at once:

- oversized file
- long function pressure
- hub-module pressure
- export sprawl
- mixed responsibilities
- duplication cluster

Do not call a file a god module from one weak signal alone.

## Merge gate posture

- `block-now` for extreme or clearly unacceptable hotspots
- `block-changed-files` for strong evidence that should stop spreading
- `warn-only` for moderate but real pressure
- `unverified` where heuristics suggest risk but evidence is incomplete

## Non-goals

Do not use this skill to answer:

- whether dependency direction is valid in an architectural sense
- whether domain code is truly pure
- whether API/runtime contracts are enforced
- whether Temporal/durable execution is safe
