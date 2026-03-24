# Tooling policy reference

This reference exists to support the skill, not to be pasted verbatim into the final user report.

## 1. Recommended role of each tool

### Tach

Use Tach to answer: “Is the Python side of the repo respecting intended module boundaries?”

It is best at:

- dependency direction between Python modules
- public interface discipline
- cycle detection
- checking whether imports imply undeclared dependencies

Typical recommendation patterns:

- narrow imports to public APIs instead of internal implementation paths
- add or refine Python module boundary config before strict enforcement
- separate shared utilities from feature modules to break cycles
- add missing dependency declarations only when the import is legitimate

Do not overreact when the repo’s Python roots are ambiguous. In that case, recommend source root clarification first.

### Dependency Cruiser

Use Dependency Cruiser to answer: “Is the JS/TS dependency graph following the repo’s intended structure?”

It is best at:

- cycles
- forbidden cross-boundary imports
- dependency declaration mismatches
- gradual structural governance with a baseline

Typical recommendation patterns:

- create a baseline for a legacy repo so new violations are blocked first
- add or refine forbidden rules for layers, packages, or domains
- break cycles by extracting shared types/interfaces or reversing dependency direction
- align dependency declarations with actual usage

Do not treat every graph oddity as equally important. Prioritize boundaries and runtime-relevant dependency problems first.

### Knip

Use Knip to answer: “What looks unused or over-declared on the JS/TS side?”

It is best at:

- unused files
- unused dependencies
- unused exports and types
- unlisted/unresolved dependency issues

Typical recommendation patterns:

- remove or quarantine unused files first
- then remove unused dependencies that become clearly safe
- then clean exports/types
- harden entry/project/workspace config if the results look suspiciously noisy

Do not suggest broad deletion when the repo has weak configuration coverage or heavy dynamic loading patterns.

## 2. Default maturity model

A healthy normalization sequence usually looks like this:

1. Make the scan trustworthy.
2. Remove obvious dead weight with low risk.
3. Freeze current structural debt so it stops growing.
4. Tighten architecture boundaries once the signal is clean enough.
5. Only then consider strict enforcement everywhere.

This matters because a repo with lots of historical debt usually needs backlog isolation before hard gating.

## 3. Common false-positive patterns

### Tach

Watch for false or distorted conclusions when:

- Python source roots are wrong or incomplete
- namespace/package layout is unusual
- external dependency resolution is incomplete

### Dependency Cruiser

Watch for distorted output when:

- TypeScript config is missing or not picked up
- the monorepo has centralized dependencies but the scan assumes per-package declarations
- path aliases are used but not represented clearly enough to the scanner

### Knip

Watch for false positives when:

- entry points are incomplete
- workspaces are not modeled clearly
- the repo relies heavily on runtime discovery, code generation, or plugin registration
- config files that matter are not included in the effective project surface

When scanner confidence is low, say so explicitly and recommend config hardening before cleanup.

## 4. Repair recommendation patterns

Use these patterns in the agent brief.

### Boundary leak

Decision:

- move imports to the package/module public API
- or deliberately expose a stable API surface if the dependency is valid

Validation:

- scanner violation disappears
- import path now goes through the intended public boundary

### Cycle

Decision:

- extract a shared interface/type/helper into a neutral module
- or invert dependency direction
- or split a mixed-responsibility file

Validation:

- cycle no longer appears in the graph
- dependency direction matches intended layering

### Missing dependency declaration

Decision:

- add the missing runtime dependency if the import is legitimate
- otherwise remove or replace the import

Validation:

- dependency declaration and actual usage match
- install/build/test path remains healthy

### Unused dependency

Decision:

- remove it only after confirming it is not needed by scripts, config, or generated code

Validation:

- package install/build/test still succeeds
- no config or script path still depends on it

### Unused file

Decision:

- verify whether the file is truly unreferenced or is loaded indirectly
- archive, delete, or reconnect intentionally

Validation:

- no legitimate entrypoint depends on it
- repo behavior remains unchanged after removal or relocation

## 5. Reporting tone

### Human report

Aim for calm, plain, non-judgmental language.

Good:

- “这个问题说明模块边界正在变模糊，后续改动会更容易互相牵连。”
- “这不是马上会崩的错误，但会持续增加维护成本。”

Avoid:

- “代码写得很差”
- “必须立刻重构全部结构”

### Agent brief

Aim for concise, high-signal guidance.

Good:

- “Create baseline, block new violations only.”
- “Break cycle by extracting shared type to neutral package.”
- “Remove unused dependency after script/config verification.”

Avoid:

- long how-to tutorials
- motivational filler
- ambiguous advice without validation checks
