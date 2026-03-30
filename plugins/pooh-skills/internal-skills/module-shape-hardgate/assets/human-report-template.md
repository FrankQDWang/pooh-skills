# Module Shape Hardgate Report

## 1. Executive summary

- Overall verdict: `{{overall_verdict}}`
- One-line diagnosis: `{{summary_line}}`

## 2. Files that are too big to be trusted

For each major hotspot:

### {{finding_title}}

- Category: `{{category}}`
- Severity: `{{severity}}`
- Confidence: `{{confidence}}`
- Evidence: `{{path}}:{{line}}`

**是什么**  
{{what_it_is}}

**为什么重要**  
{{why_it_matters}}

**建议做什么**  
{{what_to_do}}

**给非程序员的人话解释**  
{{plain_language}}

## 3. Where cohesion is broken

- mixed responsibilities:
- long-function clusters:
- duplicate logic pressure:

## 4. Where coupling will spread future AI mistakes

- hub modules:
- wide export surfaces:
- hotspots that future edits will keep accumulating into:

## 5. What can be split mechanically now

- extract route handlers / orchestration
- split schema and transport shaping
- narrow public surface
- deduplicate repeated helpers

## 6. What still needs design decisions

- domain ownership questions:
- boundary choices:
- naming / package split choices:

## 7. Ordered action plan

### 现在就做

- ...

### 下一步

- ...

### 之后再做

- ...

## 8. What this repo is teaching AI to do wrong

Examples:

- "Keep adding one more helper to the same giant file."
- "Mix routes, schemas, DB calls, and orchestration because it is faster right now."
- "Export everything from one module so future edits naturally pile up here again."
