# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. “审计这个 Python / TypeScript 仓库的基础安全姿态，重点看 pip-audit、Bandit、pnpm audit 和锁文件纪律。”
2. “检查我们的 uv / pnpm 安全扫描是不是只是摆设，还是已经进了 CI。”
3. “给我一份 repo 安全面报告，分开说 Python 漏洞、TS 漏洞、Bandit 以及 ignore 治理。”

## Should not trigger

1. “检查 UI 回归测试是不是需要 Playwright 和 MSW。”
2. “看 OpenAPI / JSON Schema 治理面是否齐全。”
3. “审计 Python 代码风格栈要不要统一到 Ruff。”

## False Positive / Regression Cases

1. Monorepo 中只有一部分 package 安装了依赖。期望：按实际 lockfile 与 workspace 覆盖给低置信度或局部结论，不要把未安装区域脑补成安全。
2. 仓库把某些 advisory 忽略了，但没有过期说明。期望：明确记为治理问题，而不是默认接受。
3. 私有 Python index 或私有 npm registry 在当前环境不可访问。期望：输出 `blocked` 或 `unverified`，不要装作零漏洞。
