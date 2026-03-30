# Repo Health Report

## 1. Executive summary

- run_id: `{{run_id}}`
- overall_health: `{{overall_health}}`
- coverage_status: `{{coverage_status}}`
- one-line diagnosis: `{{summary_line}}`

## 2. Coverage and trust

| Domain | Status | Dependency | Child verdict | Evidence gaps |
|---|---|---|---|---|
| structure | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| contracts | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| pythonic-ddd-drift | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| module-shape | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| schema-governance | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| distributed-side-effects | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| durable-agents | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| error-governance | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| silent-failure | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| frontend-regression | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| python-lint-format | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| ts-lint-format | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| security-posture | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| llm-api-freshness | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |
| cleanup | {{status}} | {{dependency_status}} | {{verdict}} | {{evidence_gaps}} |

## 3. Root cause clusters

### {{cluster_title}}

- status: `{{status}}`
- top categories: `{{top_categories}}`
- member domains: `{{domains}}`

**是什么**

{{cluster_summary}}

**为什么重要**

{{why_cluster_matters}}

**建议做什么**

{{cluster_action}}

## 4. Highest-risk domains

### {{domain}}

- skill: `{{skill_name}}`
- status: `{{status}}`
- dependency_status: `{{dependency_status}}`
- child verdict: `{{child_verdict}}`
- top categories: `{{top_categories}}`

**关键证据**

{{report_excerpt}}

**为什么现在要做**

{{why_now}}

**直接动作**

{{top_action}}

## 5. Ordered action queue

### 现在就做
- {{now_action}}

### 下一步
- {{next_action}}

### 之后再做
- {{later_action}}

## 6. Unknowns / evidence gaps

- missing skill
- invalid summary
- missing child human report
- missing child agent brief
- trust-gap domains such as `triage`

## 7. What this repo is teaching AI to do wrong overall

State the recurring system habit, not personal blame.
