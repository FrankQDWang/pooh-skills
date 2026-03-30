# Pydantic AI + Temporal Hardgate — Agent Brief

> Use short, handoff-oriented statements. No tutorials. No padding.

## Repo profile
- `repo_profile`: {{repo_profile}}
- `workflow_surface`: {{workflow_surface}}
- `agent_surface`: {{agent_surface}}
- `overall_verdict`: {{overall_verdict}}

## Findings

### {{id_1}} — {{title_1}}
- `gate`: {{gate_1}}
- `severity`: {{severity_1}}
- `confidence`: {{confidence_1}}
- `current_state`: {{current_state_1}}
- `target_state`: {{target_state_1}}
- `locus`: {{locus_1}}
- `evidence_summary`: {{evidence_summary_1}}
- `decision`: {{decision_1}}
- `change_shape`: {{change_shape_1}}
- `validation`: {{validation_1}}
- `merge_gate`: {{merge_gate_1}}
- `autofix_allowed`: {{autofix_allowed_1}}
- `notes`: {{notes_1}}

### {{id_2}} — {{title_2}}
- `gate`: {{gate_2}}
- `severity`: {{severity_2}}
- `confidence`: {{confidence_2}}
- `current_state`: {{current_state_2}}
- `target_state`: {{target_state_2}}
- `locus`: {{locus_2}}
- `evidence_summary`: {{evidence_summary_2}}
- `decision`: {{decision_2}}
- `change_shape`: {{change_shape_2}}
- `validation`: {{validation_2}}
- `merge_gate`: {{merge_gate_2}}
- `autofix_allowed`: {{autofix_allowed_2}}
- `notes`: {{notes_2}}

## Decision rules
- Prefer the official durable path over clever custom wrappers.
- Use `replace` when raw agent or model I/O leaks into Workflow code.
- Use `quarantine` only for named legacy workflow paths with owner and exit criteria.
- Use `defer` only for low-risk or evidence-poor items.
- `autofix_allowed` should default to `false` for workflow semantics, retry semantics, and sandbox behavior.

## Merge policy shorthand
- `block-now`: make this a required gate immediately
- `block-changed-files`: hard gate changed workflows / contract paths now; quarantine the rest
- `warn-only`: acceptable only for low-risk or evidence-poor items
- `unverified`: local repo cannot prove remote enforcement exists
