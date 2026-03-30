# Evaluation cases

Use these as the minimum regression set for skill triggering and hardgate drift checks.

## Should trigger

1. "Audit this repo for signature-as-contract hard gates around types, runtime schemas, and merge enforcement."
2. "Check whether our API contracts are real machine gates or just theater for AI-led coding."
3. "Review compile-time, runtime, and CI contract enforcement before the next release."

## Should not trigger

1. "Find dependency cycles and dead code in this monorepo."
2. "Review our event handlers for dual writes and idempotency gaps."
3. "Check if our LLM SDK usage is current."

## False Positive / Regression Cases

1. Local CI config exists but remote branch protection is not visible.  
Expected: mark remote enforcement `unverified`, not `hardened`.
2. Types are strict but runtime validation only exists on ingress boundaries.  
Expected: do not call the whole repo contract theater without boundary context.
3. `CODEOWNERS` exists but no required review rule is observable.  
Expected: keep merge governance below hardened unless remote enforcement is visible.
