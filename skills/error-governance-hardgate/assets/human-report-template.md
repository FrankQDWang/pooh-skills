# Error Governance Hardgate Report

## 1. Executive summary

- Overall verdict: `{{overall_verdict}}`
- One-line diagnosis: `{{summary_line}}`
- Repo root: `{{repo_root}}`

## 2. Gate map

Repeat this block per gate:

### {{gate_name}}

- Status: `{{gate_status}}`
- Severity bias: `{{gate_severity}}`
- Summary: `{{gate_summary}}`

## 3. Highest-risk findings

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

## 4. Where the contract splits or drifts

- runtime vs OpenAPI:
- runtime vs AsyncAPI:
- shared schema vs generated types:
- catalog vs docs:

## 5. What looks safe to harden now

- low-risk change 1
- low-risk change 2
- low-risk change 3

## 6. What still needs design decisions

- item
- blocker
- owner question

## 7. Ordered action plan

### 现在就做
- ...

### 下一步
- ...

### 之后再做
- ...

## 8. What this repo is teaching AI to do wrong

State the bad habit in plain language, for example:

- “Treat the error message as the API.”
- “Return whatever JSON shape is convenient in this file.”
- “Duplicate the public error code list in three languages and hope they stay aligned.”
- “Leak internal failure detail and call it observability.”
