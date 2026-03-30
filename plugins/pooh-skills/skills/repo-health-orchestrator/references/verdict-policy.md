# Verdict normalization policy

Child skills use different verdict vocabularies.
The orchestrator should not erase them.
It should normalize only enough to produce an executive rollup from current-run evidence.

Some child skills expose a trust mode instead of a health verdict.
For example, `llm-api-freshness-guard` may surface `verified` or `triage` in `child_verdict`.
Preserve that signal and let severity plus coverage decide the rollup.
But dependency bootstrap failure outranks trust mode: if `dependency_status=blocked`, that domain is blocked even if its child verdict is otherwise mild.

## Coverage before verdict

First decide whether each domain is `present`, `blocked`, `not-applicable`, `invalid`, or `missing`.

- `invalid` and `missing` are coverage failures, not child verdicts
- `blocked` is current-run coverage with a formal dependency/runtime failure, not missing coverage
- `not-applicable` is a legitimate child outcome
- a domain can be present and still blocked

Do not soften this distinction in the final report.

## Blocked domain

Treat a child domain as effectively blocked when any of the following are true:

- `dependency_status=blocked`
- child severity contains `critical > 0`
- child severity contains `high > 0` and the child status is clearly present
- child verdict is one of: `unsafe`, `broken`, `contract-theater`, `workflow-time-bomb`, `dual-write-gambling` or an equivalent future red state

## Watch domain

Treat a child domain as watch when:

- no blocked condition exists
- medium-severity findings exist, or
- the child summary says the repo is fragile / partial / drifting / ceremonial / baseline-needed / paper-guardrails, or
- the child summary is only `triage` and still needs live-doc verification, or
- coverage is weak

## Healthy domain

Treat a child domain as healthy when:

- the summary exists for the current run
- there are no critical or high findings
- coverage is good enough to trust the scan
- the child verdict is positive or the findings list is empty

## Partial coverage

If too many expected domains are missing or invalid, the overall rollup must stay `partial-coverage` even if present domains look healthy.
