# Distributed Side-Effect Hardgate Report

## 1. Executive summary

- Overall verdict: `{{overall_verdict}}`
- One-line diagnosis: `{{summary_line}}`

## 2. Where production correctness is being gambled

List the highest-severity findings first.

For each finding, use this shape:

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

## 3. What is most likely to duplicate, disappear, or diverge

- duplicate side effects:
- lost messages / writes:
- divergent read / integration state:

## 4. What looks safe to harden now

- low-risk change 1
- low-risk change 2
- low-risk change 3

## 5. What still needs design work

- item
- blocker
- owner question

## 6. Ordered action plan

### 现在就做
- ...

### 下一步
- ...

### 之后再做
- ...

## 7. What this repo is teaching AI to do wrong

State the bad habit in plain language, for example:

- "Do the write and the publish inline and pray."
- "Retry a side effect without proving idempotency."
- "Treat the queue as proof of reliability."
