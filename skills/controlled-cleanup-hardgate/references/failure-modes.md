# Common cleanup failure modes

## 1. Wrapper preservation instead of deletion
The agent migrates callers but leaves a deprecated wrapper, alias, or shim behind. This creates fake progress.

## 2. Hidden dynamic references
Reflection, plugin loading, string-based routing, config-driven dispatch, and runtime imports make "unused" look safer than it is.

## 3. Docs drift
Code is deleted but README files, examples, nav config, screenshots, or migration guides still point to the old surface.

## 4. Feature-flag debt
Migration-complete fallback code remains because nobody set a hard removal target.

## 5. Evidence theater
A change is called "safe" without clear lint, type, test, coverage, or rollback expectations.

## 6. Prose-triggered false positives
Wide keyword matching turns ordinary documentation or integration notes into fake cleanup findings.

## 7. Incomplete wrapper execution
A fail-fast wrapper exits on the first strict check and leaves link or forbidden-reference artifacts ungenerated.

## Practical response
Escalate ambiguity. Ask for stronger markers, explicit forbidden-pattern files, or language-aware tools when heuristic scanning is not enough.
