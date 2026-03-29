# Provider Resolution Policy

Freshness checks fail when the agent guesses the provider wrong. Do not do that.

This skill ships with a built-in registry for mainstream provider and wrapper surfaces.
If the real integration is outside that registry, extend the registry first or degrade to `provider-ambiguous`.
Do not pretend zero-config support for every unknown provider.

## Evidence ranking

Use evidence in roughly this order:

1. direct SDK imports / client construction
2. provider-specific base URLs or endpoint hosts
3. manifest dependencies and version hints
4. provider-specific env vars or deployment config
5. explicit model strings
6. wrapper imports
7. comments, README text, or sample code copied into docs

The higher-ranked evidence wins.

## Documentation surfaces to verify

For every integration, decide which of these surfaces are real:

- **provider SDK** — direct imports, client init, request / response types
- **provider platform docs** — endpoint families, model lifecycle, auth, transport behavior
- **compatibility layer or gateway** — Azure OpenAI, OpenRouter, Bedrock hosting, custom `base_url`
- **wrapper** — LiteLLM, LangChain, Vercel AI SDK, PydanticAI, Instructor, custom adapter

A freshness verdict is only credible when it checks the surfaces the code actually depends on.

## Provider playbooks

### OpenAI

Verify current behavior for:

- `responses` versus `chat.completions`
- client initialization and auth
- tool calling / tool choice
- structured outputs / schemas
- streaming event shape
- model lifecycle and model names
- audio / image / multimodal surface if present

### Anthropic

Verify current behavior for:

- Messages API versus older completion surfaces
- client initialization and auth
- tools
- system prompt placement
- streaming events
- model lifecycle and model names

### Gemini

Verify current behavior for:

- current SDK package and import path
- content generation surface
- tools / function calling
- response parts / content shape
- model lifecycle and model names

### Azure OpenAI

Verify current behavior for:

- deployment names versus model names
- `base_url` and Azure endpoint shape
- API version handling
- current `responses` / chat support
- auth differences from direct OpenAI usage

### OpenRouter / Bedrock / other gateways

Verify current behavior for:

- gateway-specific model naming
- auth and base URL
- provider pass-through params
- whether underlying provider docs still matter for the current request shape

## Wrapper playbooks

### LiteLLM

Check:

- wrapper-owned model routing
- current provider-specific param pass-through
- whether the code assumes one provider's schema everywhere
- whether current docs still support the chosen response or completion surface

### LangChain

Check both wrapper docs and provider docs when the code uses:

- provider-specific model classes
- bound tools
- structured outputs
- custom client parameters
- raw response fields

### Vercel AI SDK

Check:

- provider adapter package
- current generation / streaming surface
- tool calling and schema helpers
- whether provider-specific settings are passed through cleanly

### PydanticAI / Instructor / custom adapters

Check:

- adapter-owned output parsing or schema binding
- provider-specific response assumptions
- whether the adapter still maps cleanly to current provider behavior

## Ambiguity rules

- If the wrapper is clear but the underlying provider is hidden, emit:
  - `wrapper-pass-through-risk`
  - `provider-ambiguous`
- If multiple providers coexist, split findings by provider and runtime surface.
- If model strings imply one provider but imports imply another, treat that as a real signal conflict.
- If a repo contains both active and dead legacy code, say which one appears live and which one is probably historical.
