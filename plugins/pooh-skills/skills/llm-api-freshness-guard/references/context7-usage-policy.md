# Context7 Usage Policy

Context7 is the live-doc source of truth for official freshness verification.

Use it after local surface resolution, not before.

## Required order

1. identify the actual runtime surface from local evidence
2. decide the resolution level honestly
3. ask 1 to 3 concrete queries per surface
4. record the doc evidence in `doc_verification`
5. compare code behavior to current docs

## Query rules

- include provider or family, language, SDK or wrapper, version hint, and risky surface
- prefer provider SDK docs first when `provider-resolved`
- prefer wrapper docs first when only the wrapper is resolved
- prefer family-level docs when only the protocol family is resolved
- never ask vague questions such as "openai docs"

## Evidence rules

A verified finding must say:

- what the code currently does
- what the current docs expect
- whether the gap is breaking, deprecated, or still valid
- which surface owns the difference
- why the confidence is justified

If you cannot say those things, the finding is not verified yet.
