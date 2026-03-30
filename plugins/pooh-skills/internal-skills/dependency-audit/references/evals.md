# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. "Scan this monorepo for dependency direction problems, cycles, and dead-code signals."
2. "Audit Python / TypeScript repo structure and tell me whether Tach, Dependency Cruiser, and Knip would find real problems."
3. "Give me a repo-health diagnosis for architecture boundaries, dependency leaks, and cleanup candidates."

## Should not trigger

1. "Fix this failing endpoint and write the missing tests."
2. "Review our Temporal workflows for durable execution mistakes."
3. "Check whether our OpenAI SDK usage is stale."

## False Positive / Regression Cases

1. A small repo has incomplete manifests and lockfiles.  
Expected: report scanner-confidence limits, not fake hard findings.
2. A mixed repo has only Python code in one package and TS tooling in another package.  
Expected: keep Python and JS/TS findings separated before synthesis.
3. Knip reports unused exports in generated code.  
Expected: classify conservatively and avoid aggressive cleanup recommendations.
