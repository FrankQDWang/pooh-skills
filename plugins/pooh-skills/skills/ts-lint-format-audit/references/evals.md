# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. “检查这个 pnpm monorepo 的 TypeScript lint / format 栈是不是已经应该收敛到 Biome + typed lint。”
2. “审计我们 repo 里的 `eslint-disable`、`@ts-ignore` 和 CI lint 门是否失控。”
3. “给我一份 TS 规范栈体检，重点看 Biome、typescript-eslint 和 workspace 覆盖。”

## Should not trigger

1. “检查前端 UI 的视觉回归和可访问性自动化。”
2. “审计 OpenAPI 文件的 breaking change 检测。”
3. “看一下 Python 仓库是不是该把 Black / isort 合并到 Ruff。”

## False Positive / Regression Cases

1. 仓库保留 ESLint 只为了 typed lint，样式层已交给 Biome。期望：判成分层合理，而不是简单打成重复工具链。
2. 仓库里有少量 `@ts-expect-error` 用于类型测试。期望：检查是否有解释与边界，不要把测试意图全判成逃逸口。
3. Monorepo 中只有部分 package 是 TypeScript。期望：只对 TS surface 给结论，其他部分标 `not-applicable`。
