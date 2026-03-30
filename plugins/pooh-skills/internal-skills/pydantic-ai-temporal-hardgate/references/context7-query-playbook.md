# Context7 Query Playbook

Use Context7 to resolve the current official durable path, not to fish for generic framework advice.

Query construction order:

1. library or subsystem
2. language
3. version hint from the repo when visible
4. exact surface under review
5. suspected failure mode

Good examples:

- `Temporal Python workflow determinism sandbox current docs`
- `Temporal Python workflow replay time skipping testing current docs`
- `pydantic-ai TemporalAgent PydanticAIPlugin current durable execution docs`
- `pydantic-ai Agent.override TestModel FunctionModel current testing docs`

Evidence expectations:

- record exact Context7 queries
- store when the docs were checked
- store a stable source handle such as a library id or official source reference
- if the docs do not clearly verify the current path, keep the result blocked or unverified
