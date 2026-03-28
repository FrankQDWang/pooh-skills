# Repo Health Report

## 1. Executive summary

- overall_health: `{{overall_health}}`
- coverage_status: `{{coverage_status}}`
- one-line diagnosis: `{{summary_line}}`

## 2. Coverage map

| Domain | Skill | Status | Child verdict | Notes |
|---|---|---|---|---|
| structure | dependency-audit | {{status}} | {{verdict}} | {{notes}} |
| contracts | signature-contract-hardgate | {{status}} | {{verdict}} | {{notes}} |
| durable-agents | pydantic-ai-temporal-hardgate | {{status}} | {{verdict}} | {{notes}} |
| distributed-side-effects | distributed-side-effect-hardgate | {{status}} | {{verdict}} | {{notes}} |
| pythonic-ddd-drift | pythonic-ddd-drift-audit | {{status}} | {{verdict}} | {{notes}} |
| cleanup | controlled-cleanup-hardgate | {{status}} | {{verdict}} | {{notes}} |

## 3. Highest-risk domains

For each risky domain:

### {{domain}}

- skill: `{{skill_name}}`
- status: `{{status}}`
- child verdict: `{{child_verdict}}`
- top categories: `{{top_categories}}`

**是什么**

{{what_it_is}}

**为什么重要**

{{why_it_matters}}

**建议做什么**

{{what_to_do}}

## 4. Fastest high-leverage fixes

- fix 1
- fix 2
- fix 3

## 5. Unknowns / missing coverage

- missing skill
- invalid summary
- not-run domain
- remote enforcement not locally verifiable

## 6. Ordered action queue

### 现在就做
- ...

### 下一步
- ...

### 之后再做
- ...

## 7. What this repo is teaching AI to do wrong overall

State the recurring system habit, not personal blame.
