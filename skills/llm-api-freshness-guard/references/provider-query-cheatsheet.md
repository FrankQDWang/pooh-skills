# Provider Query Cheatsheet

These are example Context7 queries. They are not sacred. Adapt them using the actual language, SDK, version hint, and risky surface from the repo.
The built-in registry covers mainstream provider and wrapper surfaces. For anything outside that boundary, extend the registry before inventing ad hoc provider queries.

## General pattern

Use this shape:

`[language] [official SDK or wrapper] [version hint] [exact surface] [migration or correctness question]`

Bad:
- `openai docs`
- `anthropic api`
- `gemini old sdk`

Good:
- `Node official OpenAI SDK v4 responses API tools structured outputs migration from chat.completions`
- `Python Anthropic SDK current Messages API streaming events and text completion migration`
- `Azure OpenAI current v1 responses API deployment name versus model name Python`

## OpenAI

### Direct SDK
- `Node official OpenAI SDK current responses API tool calling and migration from chat.completions`
- `Python official OpenAI SDK current tool_calls versus function_call current request fields`
- `OpenAI current structured outputs schema JSON response format with official SDK`

### Gateways / compatibility
- `Azure OpenAI current responses API base_url deployment name api version with OpenAI Python`
- `OpenRouter current OpenAI-compatible tool calling and model naming differences`

## Anthropic

### Direct SDK
- `Python Anthropic SDK current messages.create tools streaming and text completion migration`
- `TypeScript Anthropic SDK current Messages API system prompt and tool use`
- `Anthropic current model lifecycle and deprecated model names`

## Gemini

### Direct SDK
- `Python current Google Gen AI SDK content generation function calling migration from older google generative ai package`
- `Node current Google Gen AI SDK generate content tools response parts`
- `Gemini current model names and multimodal request shape`

## Azure OpenAI

- `Azure OpenAI current v1 responses API Python Node deployment name versus model name`
- `Azure OpenAI current chat completions compatibility and responses migration`
- `Azure OpenAI auth base_url api version current guidance`

## LiteLLM

- `LiteLLM current provider specific params pass through and responses versus chat support`
- `LiteLLM current tool calling with OpenAI Anthropic Gemini backends`
- `LiteLLM model routing and current provider compatibility notes`

## LangChain

- `LangChain OpenAI current tool binding structured output and provider param pass through`
- `LangChain Anthropic current chat model tools and response parsing`
- `LangChain Google GenAI current chat model tool calling`

## Vercel AI SDK

- `Vercel AI SDK current generateText streamText tools and provider adapters`
- `AI SDK OpenAI adapter current responses support and structured output`
- `AI SDK Anthropic adapter current streaming and tool behavior`

## PydanticAI / Instructor / custom adapters

- `PydanticAI current provider adapters structured output and tool calling`
- `Instructor current OpenAI Anthropic structured output integration`
- `current adapter docs provider param pass through and response parsing`

## Decision rule

If one query can only answer half the problem, split by surface:

- one query for endpoint / method family
- one query for tools / structured output / streaming
- one query for model lifecycle or compatibility layer

Do not waste queries on generic background reading.
