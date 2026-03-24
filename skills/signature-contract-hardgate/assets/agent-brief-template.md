# Signature Contract Hardgate — Agent Brief

> Use short, patch-oriented statements. No tutorials. No padding.

## Repo profile
- `repo_profile`: {{repo_profile}}
- `languages`: {{languages}}
- `contract_surface`: {{contract_surface}}
- `overall_verdict`: {{overall_verdict}}

## Findings

### {{id_1}} — {{title_1}}
- `domain`: {{domain_1}}
- `gate`: {{gate_1}}
- `severity`: {{severity_1}}
- `confidence`: {{confidence_1}}
- `current_state`: {{current_state_1}}
- `target_state`: {{target_state_1}}
- `evidence_summary`: {{evidence_summary_1}}
- `decision`: {{decision_1}}
- `change_shape`: {{change_shape_1}}
- `validation`: {{validation_1}}
- `merge_gate`: {{merge_gate_1}}
- `autofix_allowed`: {{autofix_allowed_1}}
- `notes`: {{notes_1}}

### {{id_2}} — {{title_2}}
- `domain`: {{domain_2}}
- `gate`: {{gate_2}}
- `severity`: {{severity_2}}
- `confidence`: {{confidence_2}}
- `current_state`: {{current_state_2}}
- `target_state`: {{target_state_2}}
- `evidence_summary`: {{evidence_summary_2}}
- `decision`: {{decision_2}}
- `change_shape`: {{change_shape_2}}
- `validation`: {{validation_2}}
- `merge_gate`: {{merge_gate_2}}
- `autofix_allowed`: {{autofix_allowed_2}}
- `notes`: {{notes_2}}

## Decision rules
- Prefer `adopt` / `harden` over vague “improve later”.
- Use `quarantine` only for legacy debt with owner, path scope, and exit criteria.
- Use `replace` when the current tool exists but is too weak, too cosmetic, or structurally misleading.
- Use `defer` only when the repo cannot absorb the change safely right now **and** the risk is explicitly contained.

## Merge policy shorthand
- `block-now`: make this a required gate immediately
- `block-changed-files`: hard gate new or touched code now; quarantine the rest
- `warn-only`: only acceptable for low-risk or evidence-poor items
- `unverified`: local repo cannot prove remote enforcement exists
