# Detection policy

## Strong evidence

The following should be treated as highly credible:

- `domain` importing framework / transport / ORM / infra libraries
- explicit import from one context's domain into another context's domain
- abstract base shells with only `pass`, `...`, or `NotImplementedError`
- classes whose public methods only forward to an injected collaborator

## Moderate signals

The following should be treated as report-worthy but not absolute:

- many `Command`, `Query`, `Handler` classes with little read-model / projection evidence
- domain classes with almost no behavior plus behavior-heavy services elsewhere
- composition root not obvious, with wiring scattered across application code
- widespread `Service`, `Manager`, `Factory` wrappers that add almost no policy

## Never do this

- never equate naming taste with hard architecture failure
- never treat all classes as bad
- never prescribe DDD where the repo simply does not need it
