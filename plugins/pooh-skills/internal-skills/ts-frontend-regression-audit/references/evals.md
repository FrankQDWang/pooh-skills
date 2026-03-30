# Evaluation cases

Use these as the minimum regression set for skill triggering and drift checks.

## Should trigger

1. “审计这个 TS 前端仓库的回归链，看看真实浏览器、MSW、axe 和视觉回归是不是都到位了。”
2. “检查我们的 Playwright / Vitest Browser Mode 测试到底是不是在守 UI 回归。”
3. “给我一份前端测试治理报告，重点看网络 mock 边界、截图基线和 CI 工件。”

## Should not trigger

1. “看一下 TypeScript lint / format 栈要不要统一到 Biome。”
2. “审计 Python 和 pnpm 依赖的安全漏洞面。”
3. “检查 OpenAPI 文件有没有 breaking changes。”

## False Positive / Regression Cases

1. 仓库有 Playwright，但只跑登录冒烟，不做截图、不做 a11y。期望：判成局部存在，不要夸成完整回归链。
2. 仓库组件测试使用 jsdom，同时关键流程用 Browser Mode / Playwright。期望：按不同层次分开判断，不要因为存在 jsdom 就否定整个测试面。
3. MSW 只在本地开发使用，测试中并未接入。期望：把它记成工具存在但未形成测试证据，而不是算作已上锁。
