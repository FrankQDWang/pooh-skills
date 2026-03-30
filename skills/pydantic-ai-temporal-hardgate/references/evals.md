# Evaluation cases

Use these as the minimum regression set for skill triggering and durable-path checks.

## Should trigger

1. "Audit this Python repo for Temporal + pydantic-ai durable execution correctness."
2. "Check whether our workflow path is deterministic and whether our durable-agent wiring follows the official path."
3. "Review replay, time-skipping, and fake-model verification around our TemporalAgent setup."

## Should not trigger

1. "Do a general Python code review."
2. "Scan this monorepo for dependency direction and dead code."
3. "Audit signature-as-contract hard gates."

## False Positive / Regression Cases

1. A workflow uses `asyncio.sleep(...)` in a pattern that maps to a durable timer.  
Expected: do not auto-label it broken without Temporal-specific evidence.
2. Raw `Agent(...)` exists only in non-workflow application code.  
Expected: do not call it a durable-path violation unless it enters workflow semantics.
3. Local docs mention Temporal, but no live-doc evidence was collected.  
Expected: block or mark unverified according to live-doc policy, not emit a confident positive verdict.
