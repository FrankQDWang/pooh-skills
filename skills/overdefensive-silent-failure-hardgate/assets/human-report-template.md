# Overdefensive Silent Failure Report

## 1. Executive summary
- Overall verdict: `{{overall_verdict}}`
- One-line diagnosis: `{{summary_line}}`

## 2. Where the repo is hiding failure instead of handling it
For each strong finding:

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

## 3. Where contracts were softened into maybe-values and defaults
- optionality leaks:
- silent defaults:
- truthiness fallbacks:
- type / lint escape hatches:
- boundary-vs-internal confusion:

## 4. Where async work can fail off-camera
- unobserved tasks:
- promise swallow paths:
- catch-and-continue loops:

## 5. What should fail loudly now
- item
- item

## 6. What may degrade only if it becomes explicit
- item
- required log / metric / alert
- required user-visible state if this is a product surface

## 7. Ordered action plan
### 现在
- ...

### 下一步
- ...

### 之后
- ...

## 8. What this repo is teaching AI to do wrong
Examples:
- "Turn required data into maybe-data so nobody has to decide where the contract lives."
- "Swallow the exception, then call the code resilient."
- "Make async work disappear into the background and hope the logs tell the truth."
