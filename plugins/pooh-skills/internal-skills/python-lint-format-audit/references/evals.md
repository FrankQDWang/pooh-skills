# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. “审计这个 Python 仓库的 lint / format 栈，看看是不是已经该统一到 Ruff。”
2. “检查我们的 `ruff check`、`ruff format --check`、pre-commit 和 CI 到底有没有形成真门。”
3. “给我一份 Python 代码规范栈报告，重点看 suppressions、旧工具残留和 merge gate。”

## Should not trigger

1. “检查这个仓库的类型契约和运行时 schema 是否真的上锁。”
2. “帮我修掉这个接口 bug，然后把测试补上。”
3. “扫描 monorepo 的依赖方向、循环依赖和 dead-code。”

## False Positive / Regression Cases

1. 仓库同时保留 `black` 配置和 `ruff format`，但 CI 只跑 Ruff。期望：标成迁移残留，不要误判为双真相源已生效。
2. 仓库排除了 `generated/` 与 `vendor/`。期望：确认是否范围隔离合理，不要把所有 exclude 一律判成作弊。
3. 仓库只有文档目录里的 Python 示例，没有真实 Python 包。期望：把结论降成 `not-applicable` 或低置信度，而不是硬判缺失。
