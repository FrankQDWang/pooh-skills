# Evaluation cases

Use these as the minimum regression set for skill triggering and freshness audit drift.

## Should trigger

1. "Check whether this repo still uses stale OpenAI / Anthropic / Gemini SDK surfaces."
2. "Audit these diffs for LLM API drift across tool calling, structured outputs, and streaming."
3. "Verify whether this wrapper stack still matches the current provider docs."

## Should not trigger

1. "Tune prompt quality for this agent."
2. "Benchmark models and compare pricing."
3. "Review this general Python bug fix."

## False Positive / Regression Cases

1. A wrapper is present but the underlying provider cannot be resolved.  
Expected: emit provider ambiguity, not a fabricated stale-provider verdict.
2. A legacy-looking method name appears only in docs or comments.  
Expected: keep it as weak evidence until code usage and live docs agree.
3. Context7 is unavailable.  
Expected: block the official audit flow instead of returning a successful local-only verdict.
