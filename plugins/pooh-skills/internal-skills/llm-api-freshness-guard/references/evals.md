# Evaluation cases

Use these as the minimum regression set for trigger behavior and freshness audit drift.

## Should trigger

1. "Audit this Python repo for stale OpenAI / Anthropic / Gemini API usage."
2. "Check whether this TypeScript wrapper stack still matches the current provider docs."
3. "Review this repo for LLM API freshness drift across tool calling, structured output, and streaming."

## Should not trigger

1. "Tune prompt quality for this agent."
2. "Benchmark models and compare pricing."
3. "Review this general Python bug fix."

## False Positive / Regression Cases

1. A custom gateway exposes OpenAI-compatible paths but does not identify one concrete vendor.  
Expected: emit `family-resolved`, not a fabricated concrete provider.
2. LiteLLM or LangChain is present, but the underlying provider remains hidden.  
Expected: emit `wrapper-resolved` or `ambiguous`, not a fake provider-specific stale verdict.
3. A legacy-looking method name appears only in docs or comments.  
Expected: treat it as weak evidence unless executable code also depends on it.
4. The wrapper runs without Context7.  
Expected: produce `triage`, not `blocked`, because local evidence extraction still succeeded.
5. A verified audit is requested but Context7 cannot resolve the necessary docs.  
Expected: the official verified flow must stay `blocked` or unresolved instead of pretending success.
