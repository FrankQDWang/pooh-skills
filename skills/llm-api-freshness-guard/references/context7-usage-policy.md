# Context7 Usage Policy for LLM API Freshness Guard

This skill exists because memory goes stale and vendor docs move fast. Treat Context7 as the live source of truth when determining whether an LLM API surface is current.

## Required order

1. **Identify the exact runtime surface**
   - provider
   - language / runtime
   - SDK or wrapper package
   - version hint from manifest or lockfile
   - risky surface: endpoint, tools, streaming, model, auth, structured output, response parsing, etc.

2. **Resolve the library ID**
   - Use `resolve-library-id` unless the exact Context7 library ID is already known.
   - Prefer the official provider SDK or platform docs.
   - If the repo uses a wrapper that owns runtime behavior, resolve the wrapper too.

3. **Ask a concrete question**
   Good questions are narrow and falsifiable. Bad questions are vague.

   Good:
   - "Node official OpenAI SDK v4: current Responses API tool calling and migration from chat.completions"
   - "Anthropic Python SDK current Messages API streaming events and text completions migration"
   - "Azure OpenAI current Responses API deployment name versus model name behavior"

   Bad:
   - "openai docs"
   - "how does anthropic work"
   - "gemini api"

4. **Keep query count small**
   - Use at most **three Context7 doc queries per provider surface**.
   - Use fewer when one query answers the real question.
   - Do not spam the docs because you were too lazy to identify the actual surface first.

5. **Capture evidence**
   Record:
   - selected library or library ID
   - language / SDK / version hint
   - exact current method or parameter names
   - whether the old usage is:
     - removed / unsupported
     - deprecated but still documented
     - legacy but valid
     - wrapper-specific
     - config-only mismatch

6. **Compare the code to the docs**
   Freshness is about mismatch, not about aesthetics.
   A current method can look ugly and still be correct.
   A pretty abstraction can still be stale.

## Query design rules

- Include **provider + language + sdk + version hint + risky surface**.
- Use migration queries when the repo clearly uses a legacy-looking surface.
- Use compatibility queries when a gateway or `base_url` might change semantics.
- Prefer "what is the current way to do X" over "tell me about the docs".
- Never include API keys, access tokens, customer data, or proprietary prompts.
- Redact secrets before putting any context into a query.

## Official-doc precedence

Prefer docs in this order:

1. official provider SDK docs
2. official provider platform docs
3. compatibility-layer docs (Azure OpenAI, OpenRouter, Bedrock host surface, etc.)
4. wrapper docs (LiteLLM, LangChain, Vercel AI SDK, PydanticAI, Instructor, etc.)
5. anything else only if the official path is genuinely unavailable

Do not let wrapper docs erase provider semantics. If the code passes provider-native params through a wrapper, verify the provider too.

## Evidence standards

A verified finding should say all of the following:

- what the code currently does
- what the current docs expect
- whether the gap is runtime-breaking, migration pressure, or only hygiene
- which provider surface owns the change
- how confident you are and why

If you cannot answer those points, the finding is not verified yet.

## Failure mode

If Context7 is unavailable, ambiguous, or the docs cannot be resolved with confidence:

- continue with local code signals if available
- label the run `local-scan-only`
- emit `docs-unverified`
- do not bluff a "latest API" answer from memory

## Security rules

- Never paste secrets into Context7 queries.
- Never paste full proprietary code when a specific method name and version hint are enough.
- Prefer minimal, targeted queries over giant code dumps.
