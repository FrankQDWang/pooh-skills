# Surface Resolution Policy

Freshness checks fail when the agent guesses the runtime surface wrong.

This skill does not require a provider to be pre-registered before the audit can begin.
It starts from evidence, then resolves surfaces honestly.

## Resolution levels

Use exactly these labels:

- `provider-resolved`
- `family-resolved`
- `wrapper-resolved`
- `ambiguous`

## Evidence order

Trust evidence in roughly this order:

1. direct SDK imports or client construction
2. provider-specific adapter package
3. provider-specific host, env, or deployment config
4. manifest dependencies and version hints
5. wrapper imports and wrapper construction
6. model strings
7. docs, comments, copied examples

The higher-ranked evidence wins.

## Upgrade rules

- Upgrade to `provider-resolved` only when strong runtime evidence identifies one concrete provider.
- Stay at `family-resolved` when the repo only proves a protocol family such as `openai-compatible`.
- Use `wrapper-resolved` when the wrapper is clear but the provider behind it is still hidden.
- Use `ambiguous` when the evidence is still too weak or contradictory.

## Family taxonomy

Use exactly:

- `openai-compatible`
- `anthropic-messages`
- `google-genai`
- `bedrock-hosted`
- `generic-wrapper`
- `custom-http-llm`
- `unknown`

## Reporting rules

- Do not write "this repo uses OpenAI" when the evidence only proves `openai-compatible`.
- Do not write "current docs are clean" from triage-only output.
- Do not let wrapper docs erase provider risk when the code passes provider-native params through.
