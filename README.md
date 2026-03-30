# pooh-skills

`pooh-skills` 现在以 repo-local Codex plugin 形态分发，而不是一组单独直装的 skill。

This repository detects and reports only; it does not perform repository cleanup or automated fixes.
It only targets Python / TypeScript repositories and their documentation surfaces.

## 目录结构

```text
.agents/
  plugins/
    marketplace.json
plugins/
  pooh-skills/
    .codex-plugin/
      plugin.json
    skills/          # generated plugin bundle, do not hand-edit
skills/              # source of truth
  <skill-id>/
    SKILL.md
    agents/
    assets/
    references/
    scripts/
scripts/
  sync_plugin_bundle.py
  check_repo_plugin.py
shared/
  *.md  # authoring-time canonical shared refs; not installed as runtime deps
```

## Plugin 入口

- public plugin id: `pooh-skills`
- public plugin display name: `Pooh Skills`
- public plugin entrypoint: `$repo-health-orchestrator`
- the 15 audit skills remain bundled for orchestrator use, but are no longer documented as the primary installation surface

Codex discovers this repo-local plugin through [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json), which points to [`plugins/pooh-skills/.codex-plugin/plugin.json`](plugins/pooh-skills/.codex-plugin/plugin.json).

## Build The Plugin Bundle

Root [`skills/`](skills/) remains the only source of truth.
The plugin bundle under [`plugins/pooh-skills/skills/`](plugins/pooh-skills/skills/) is generated and must stay byte-for-byte synchronized.

Sync the repo-local plugin bundle:

```bash
python3 scripts/sync_plugin_bundle.py
```

Validate the plugin manifest, marketplace entry, bundle sync status, and public docs:

```bash
python3 scripts/check_repo_plugin.py --repo . --json-out .repo-harness/repo-plugin-check.json
```

## Current Skill Fleet

- `dependency-audit`: 面向 Python / TypeScript 仓库与 workspace 的依赖方向、架构边界、循环依赖与 dead-code 信号审计；缺失必需工具时先尝试自举安装，失败则产出 blocked 工件而不是伪装成低置信成功。
- `signature-contract-hardgate`: 面向 Python / TypeScript 仓库的“签名即契约”硬门控审计，检查 compile-time gates、runtime schemas、错误通道、边界规则、逃逸口治理与 merge protections 到底是真门还是摆设。
- `pydantic-ai-temporal-hardgate`: 面向 `Python + Temporal + pydantic-ai` 仓库的 durable execution 硬门控审计，检查 Workflow determinism、sandbox、durable-agent path、tool / deps 契约、replay / time-skipping harness 和 merge gate 到底是真是假。
- `controlled-cleanup-hardgate`: 面向 Python / TypeScript 仓库的 deprecated / removal readiness 审计，检查 deprecated surfaces、compatibility shims、stale docs、expired removal targets 与 feature-flag debt，输出人类报告、agent brief 和机器可消费 summary。
- `distributed-side-effect-hardgate`: 面向消息、worker、webhook 与事件驱动仓库的分布式副作用审计，检查 dual write、outbox、幂等、unsafe retry、事件契约和补偿/可观测性缺口。
- `pythonic-ddd-drift-audit`: 面向 Python-heavy 仓库的 Pythonic 形状债与 DDD 漂移审计，检查 domain boundary leak、cross-context bleed、ABC 过度、thin wrapper 与假 CQRS。
- `llm-api-freshness-guard`: 面向 Python / TypeScript 仓库的 LLM API 新鲜度审计，先做本地 surface triage，再由 agent 按 `provider-resolved / family-resolved / wrapper-resolved / ambiguous` 归因并借助 Context7 做官方 freshness 验证；wrapper 只产出 triage，不再把未查文档的结果包装成 verified。
- `error-governance-hardgate`: 面向 Python / TypeScript 仓库的公共错误契约治理审计，检查 Problem Details、structured error code、OpenAPI / AsyncAPI 对齐、outward leakage、SSOT / codegen drift 与 message-text branching。
- `overdefensive-silent-failure-hardgate`: 面向 Python / TypeScript 仓库的过度防御与静默失败审计，检查 empty catch、swallow / continue、checker suppressions、silent defaults、maybe-value 扩散与 off-camera async loss。
- `module-shape-hardgate`: 面向 Python / TypeScript 仓库的模块形状审计，检查 giant file、god module、低内聚职责混杂、过宽导出面、超长函数、重复热点与 fan-out hub；默认只检测和报告，不做自动重构。
- `python-lint-format-audit`: 面向 Python 仓库的现代 Ruff-first lint / format 审计，检查单一命令真相、CI/pre-commit gate、抑制治理与 generated/vendor 范围隔离。
- `ts-lint-format-audit`: 面向 TypeScript 仓库的现代 Biome-first lint / format 审计，检查 style-layer 收敛、typed lint、workspace 覆盖与 suppression 治理。
- `openapi-jsonschema-governance-audit`: 面向 Python / TypeScript 仓库的 OpenAPI / JSON Schema 治理审计，检查 canonical source、ruleset、lint/bundle/diff 链和 CI publication evidence。
- `ts-frontend-regression-audit`: 面向 TypeScript 前端仓库的浏览器真实回归审计，检查 browser fidelity、boundary mock、a11y、visual evidence 和 CI 工件。
- `python-ts-security-posture-audit`: 面向 Python / TypeScript 仓库的基础安全姿态审计，检查 uv / pnpm 锁文件纪律、依赖审计信号、Bandit 类静态扫描和 ignore governance。
- `repo-health-orchestrator`: 面向整仓体检的汇总 skill，每次先清空 `.repo-harness`，先串行 bootstrap 共享锁定工具链，再并行启动 15 个 child audit subagents，维护一个终端实时 control plane，并在结束时先产出机器 rollup，再合成 cross-domain evidence、最终总报告和 agent brief。要求运行环境支持 Codex subagent，以及当前会话模型与推理强度继承语义。

## Audit Fleet 约定

- `repo-health-orchestrator` 是 Codex subagent-only：它会先清空并重建 repo-root `.repo-harness`，再启动 15 个 child audit subagents
- `pooh-skills` plugin 对用户只公开一个主入口：`$repo-health-orchestrator`
- `.repo-harness` 是纯输出目录，只保存当前 run 的 summary / report / brief / linkcheck / control-plane state 等工件，不放默认输入
- `repo-health-orchestrator` 采用双层汇总：`repo-health-summary.json` 负责机器真相，`repo-health-evidence.json` 负责 cross-domain synthesis，最终 `repo-health-report.md` 与 `repo-health-agent-brief.md` 基于 evidence 生成
- 所有 child skills 统一遵守 fail-fast bootstrap 合约：先 `preflight`，再尝试自动安装缺失依赖；安装失败时停止主审计，但仍写标准 blocked 工件
- installable tools 统一由共享 `.pooh-runtime` 锁定管理：Python CLI 只经 `uv` 的 `audit` 依赖组，TS/Node CLI 只经 `pnpm` 的 `devDependencies`；这些都属于宿主侧共享审计工具链，不是应用运行时依赖
- `lychee` 与 `Vale` 仍是 docs-only 硬依赖例外：由共享 runtime 按官方二进制安装方式统一管理，但不进入 `uv` / `pnpm` 工具链
- 每个 child skill 运行期间都会写 `.repo-harness/skills/<skill-id>/runtime.json`，并把 `summary.json / report.md / agent-brief.md` 放在同一 child namespace 下，供 orchestrator 和终端 control plane 显示 `PREFLIGHT / BOOTSTRAPPING / RUNNING / BLOCKED / COMPLETE / NOT APPLICABLE`
- child skill 自己的 `scripts/run_all.sh` 可以继续作为本地 deterministic helper 独立使用，但不再属于 orchestrator 的公开契约
- 旧 skill 的 wrapper 现在会先走共享 `.pooh-runtime` 合约；缺依赖时不会再伪装成“保守 baseline 成功”
- Python 边界工具的唯一标准是 `Tach`；仓库不引入 `import-linter`
- `repo-health-orchestrator` 是唯一的 full-fleet 总控，统一覆盖 15 个 audit skills；orchestrator 自身不进入 worker 列表

## Skill Authoring Contract

新增或修改 skill 时，统一遵守以下仓库级约束：

1. `SKILL.md` frontmatter 必须是合法 YAML，且只允许 `name` 与 `description`
2. `description` 必须使用第三人称，且统一写成 `Audits ... Use for ... Produces ...` 或 `Coordinates ... Use for ... Produces ...`
3. `SKILL.md` 正文必须保持精简，默认要求少于 `500` 行
4. 每个 skill 都必须提供可见的 `references/evals.md`，至少覆盖 `Should trigger`、`Should not trigger`、`False positive / regression cases`
5. `repo-health-orchestrator` 额外必须在 `references/evals.md` 中提供 `Failure scenarios`
6. `SKILL.md` 的本地链接必须存在，且必须保持 skill 安装后自包含；不要从一个 skill 直接链接另一个 skill 或仓库根目录文件
7. 跨 skill 复用的通用 contract 统一维护在仓库根目录 `shared/`，再同步到每个 skill 自己的 `references/shared-*.md`
8. 容易过期的生态细节不要写死在 core workflow；应写成“先识别本仓库实际 surface，再去官方最新文档核验”

## Live-Doc Verification

- `llm-api-freshness-guard` 与 `pydantic-ai-temporal-hardgate` 的官方 freshness / live-doc 结论都要求 Context7-backed 文档证据
- `llm-api-freshness-guard` 现在采用双层流程：`scripts/run_all.sh` 只负责本地 triage 和 evidence bundle，官方 verified 结论由 agent-first Context7 流完成
- `pydantic-ai-temporal-hardgate` 仍通过 deterministic wrapper 接收 live-doc / live-surface 验证输入
- 没有 Context7-backed 文档证据时，不得伪造 verified 结论；要么保持 `triage`，要么在官方 verified 流中诚实标成 `blocked`

## Harness

仓库内置了用于防再犯的 fleet harness：

```bash
python3 scripts/check_skill_fleet.py --repo . --mode fast --json-out .repo-harness/skill-fleet-fastcheck.json
python3 scripts/check_skill_fleet.py --repo . --mode strict --json-out .repo-harness/skill-fleet-strictcheck.json
python3 scripts/sync_shared_skill_refs.py --check
python3 scripts/sync_shared_skill_refs.py --write
python3 scripts/check_repo_plugin.py --repo . --json-out .repo-harness/repo-plugin-check.json
python3 scripts/run_module_shape_fixture_regressions.py
python3 scripts/run_new_audit_fixture_regressions.py
python3 scripts/run_repo_health_fixture_regressions.py
python3 scripts/run_child_wrapper_smoke_matrix.py
python3 scripts/run_control_plane_renderer_regressions.py
bash scripts/run_skill_fleet_harness.sh . .repo-harness
```

- `fast` 用于本地快速元检查：frontmatter、description 规范、行数预算、链接存在性、visible eval surface
- `strict` 会额外检查 runtime manifest shape、canonical shared refs、打包噪音、live-doc-sensitive skill 的引用入口，以及 orchestrator catalog completeness
- `check_repo_plugin.py` 负责校验 plugin manifest、marketplace entry、bundle 同步状态，以及 README 中是否残留 legacy skill-install 语义
- `shared/` 是仓库维护期的 canonical source，不是 skill 运行时依赖
- plugin bundle 真正使用的是各自目录下的 `references/shared-*.md`；这些文件由 `shared/` materialize 出来，打包后仍然自包含可用
- 换句话说，`shared/` 负责“单一真相源”，`skills/*/references/shared-*.md` 负责“安装后实际生效的本地副本”
- 修改 `shared/` 后，必须运行 `python3 scripts/sync_shared_skill_refs.py --write`

## 兼容性声明

- 这个仓库当前只维护 Codex plugin 兼容性
- 已存在的 `~/.claude/skills` 副本不再受支持，也不会由本仓库自动清理

## 扩展约定

新增 skill 时，统一放到 `skills/<skill-id>/` 下：

1. 必须包含 `SKILL.md`
2. 可选包含 `agents/openai.yaml`
3. 可选包含 `assets/`、`references/`、`scripts/`

这样根目录可以保持稳定，后续只需要继续往 `skills/` 下增加新的 skill 目录。

## Main-Only 约束

这个仓库只允许使用 `main`。

- 远端 GitHub ruleset 已禁止创建任何非 `main` 分支
- 本仓库提供 `.githooks/`，用于在本地拒绝非 `main` 上的 commit / rebase / merge / push
- `pre-commit` 会先跑 main-only guard，再跑 fleet fast check
- `pre-push` 会先跑 main-only guard，再跑严格版 fleet harness
- 当前 clone 应设置：`git config core.hooksPath .githooks`
- `.githooks/` 是仓库内文件，但 `core.hooksPath` 是 clone 本地 Git 配置；新 clone 拉下来后需要重新执行一次

推荐初始化：

```bash
git config core.hooksPath .githooks
git config --get core.hooksPath
```
