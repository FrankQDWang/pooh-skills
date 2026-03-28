# Pythonic DDD Drift Audit Report

## 1. Executive summary

- Overall verdict: `{{overall_verdict}}`
- One-line diagnosis: `{{summary_line}}`

## 2. Where the repo is lying about boundaries

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

## 3. Where Python is being forced to imitate Java

- interface inflation:
- abstract base shells:
- pass-through service / manager layers:
- empty CQRS ceremony:

## 4. What is safe to flatten now

- wrapper to collapse
- interface shell to replace
- boundary import to move

## 5. What still needs modeling decisions

- item
- open question
- owner choice

## 6. Ordered action plan

### 现在就做
- ...

### 下一步
- ...

### 之后再做
- ...

## 7. What this repo is teaching AI to do wrong

Examples:

- "Name a folder `domain`, then import SQLAlchemy into it."
- "Wrap every use case in two empty classes so it looks architected."
- "Use CQRS because the diagram looks impressive, not because the read path needs it."
