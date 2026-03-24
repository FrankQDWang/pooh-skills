# AI Skills

这个仓库用于集中管理可安装到 Codex 和 Claude Code 的 skills。

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

## 安装

默认同时安装到 `~/.codex/skills` 和 `~/.claude/skills`：

```bash
./scripts/install.sh dependency-audit
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
```

## 扩展约定

新增 skill 时，统一放到 `skills/<skill-id>/` 下：

1. 必须包含 `SKILL.md`
2. 可选包含 `agents/openai.yaml`
3. 可选包含 `assets/`、`references/`、`scripts/`

这样根目录可以保持稳定，后续只需要继续往 `skills/` 下增加新的 skill 目录。
