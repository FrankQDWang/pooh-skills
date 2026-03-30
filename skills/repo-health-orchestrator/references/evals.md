# Evaluation cases

Use these as the minimum regression set for orchestrator triggering and rollup behavior.

## Should trigger

1. "Run the full pooh-skills audit fleet and give me one repository health report."
2. "I want a multi-skill governance rollup across structure, contracts, durable agents, freshness, cleanup, and distributed correctness."
3. "Give me a quarterly repo-health snapshot with one action queue."

## Should not trigger

1. "Run only the dependency audit."
2. "Fix this one failing test."
3. "Review our OpenAI SDK migration."

## False Positive / Regression Cases

1. Old `.repo-harness` artifacts exist from a previous run.  
Expected: do not treat them as current coverage.
2. One child reports `not-applicable`.  
Expected: keep it visible without calling the whole rollup incomplete.
3. One child is blocked on dependency bootstrap.  
Expected: preserve blocked status instead of silently downgrading it.

## Failure Scenarios

1. Missing child summary file.  
Expected: coverage becomes partial and the gap stays visible.
2. Invalid child summary JSON.  
Expected: coverage becomes partial and the invalid summary stays visible.
3. No subagent runtime support.  
Expected: orchestrator stops plainly and emits blocked repo-health artifacts.
