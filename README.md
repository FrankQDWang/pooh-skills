# pooh-skills

`pooh-skills` 用于集中管理可安装到 Codex 和 Claude Code 的 skills。

## 目录结构

```text
skills/
  <skill-id>/
    SKILL.md
    agents/
    assets/
    references/
    scripts/
scripts/
  install.sh
```

## 当前 skill

- `dependency-audit`: 面向 Python / TypeScript / mixed monorepo 的依赖方向、架构边界、循环依赖与 dead-code 信号审计，输出尖锐但可读的人类报告和 agent remediation brief。
- `signature-contract-hardgate`: 面向 Python / TypeScript 仓库的“签名即契约”硬门控审计，检查 compile-time gates、runtime schemas、错误通道、边界规则、逃逸口治理与 merge protections 到底是真门还是摆设。
- `pydantic-ai-temporal-hardgate`: 面向 `Python + Temporal + pydantic-ai` 仓库的 durable execution 硬门控审计，检查 Workflow determinism、sandbox、durable-agent path、tool / deps 契约、replay / time-skipping harness 和 merge gate 到底是真是假。
- `controlled-cleanup-hardgate`: 面向大型仓库的可控清理审计，检查 deprecated surfaces、compatibility shims、stale docs、expired removal targets、feature-flag debt 与 cleanup readiness，输出人类报告、agent brief 和机器可消费 summary。

## 安装

默认同时安装到 `~/.codex/skills` 和 `~/.claude/skills`：

```bash
./scripts/install.sh dependency-audit
./scripts/install.sh signature-contract-hardgate
./scripts/install.sh pydantic-ai-temporal-hardgate
./scripts/install.sh controlled-cleanup-hardgate
```

列出当前仓库可安装的 skills：

```bash
./scripts/install.sh --list
```

安装仓库里的全部 skills：

```bash
./scripts/install.sh --all
```

只安装到单一目标：

```bash
./scripts/install.sh --target codex dependency-audit
./scripts/install.sh --target claude dependency-audit
./scripts/install.sh --target codex signature-contract-hardgate
./scripts/install.sh --target codex pydantic-ai-temporal-hardgate
./scripts/install.sh --target codex controlled-cleanup-hardgate
```

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
- 当前 clone 应设置：`git config core.hooksPath .githooks`
- `.githooks/` 是仓库内文件，但 `core.hooksPath` 是 clone 本地 Git 配置；新 clone 拉下来后需要重新执行一次

推荐初始化：

```bash
git config core.hooksPath .githooks
git config --get core.hooksPath
```
