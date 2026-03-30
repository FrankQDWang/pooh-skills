# Context7 Query Playbook

Use Context7 to resolve the current doc surface with queries that are specific enough to avoid vague “latest” guesses.

Query construction order:

1. provider or gateway
2. language / SDK
3. version hint from the repo when visible
4. exact surface under review
5. suspected drift type

Good examples:

- `OpenAI Python SDK Responses API tool calling structured output latest`
- `Anthropic Messages API TypeScript tool use current docs`
- `Azure OpenAI Python api-version chat responses compatibility`
- `LiteLLM latest provider pass-through tool calling docs`

Evidence expectations:

- store the exact queries used
- record when the docs were checked
- record a stable source handle such as a Context7 library id or official source reference
- if the result is ambiguous, keep the audit blocked or unverified instead of guessing
