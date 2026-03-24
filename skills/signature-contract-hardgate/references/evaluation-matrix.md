# 评估矩阵：怎么判断是 missing、theater、partial、enforced、hardened

| 类别 | missing | theater | partial | enforced | hardened |
|---|---|---|---|---|---|
| contract-surface | 没有明确契约层 | 有类型/模型文件但边界混乱 | 契约层存在但散乱 | 契约层清晰可定位 | 契约层小而稳，强审、生成链、边界一致 |
| compile-time-gates | 无严格检查 | 有配置但不进 CI 或大量逃逸 | 部分严格，覆盖不全 | 关键路径上阻断有效 | changed files 立刻阻断，遗留区有隔离策略 |
| runtime-boundary-validation | 外部输入直穿 | 少量点缀式校验 | 部分边界有校验 | 主入口基本受控 | 所有关键 ingress/egress 都受统一 schema 管理 |
| error-contract | 失败路径隐身 | 说有 Result/union，实际全靠 throw / broad except | 部分模块显式化 | 服务 / 领域边界显式 | 错误模型稳定、穷举、测试覆盖 |
| escape-hatch-governance | 到处是洞 | 有禁令但无人执行 | 有治理但例外多 | 例外受控且可追踪 | 契约层几乎零逃逸，新增洞会被拦 |
| architecture-boundaries | 无规则 | 有配置文件但不执行 | 部分模块受控 | 主要边界受机器阻断 | 深耦合路径被系统性切断，例外隔离 |
| contract-tests | 只有样例测试或没有 | 口头要求测试 | 关键点有测试但不成体系 | 关键边界有稳定测试 | schema/性质/覆盖率联动成门 |
| merge-governance | 无强制合并门 | 有 workflow 但非 required | 部分检查 required | 关键门已 required + code owners | changed files 立即硬门，契约层强审，遗留债可控 |

## 使用方式

1. 每个类别都必须给状态。
2. 总评只允许四档：`contract-theater` / `soft-gates` / `real-gates` / `hard-harness`。
3. 看到“配置存在但不阻断”，优先判 `theater`，不要心软。
4. 看不到远端平台设置，就写 `unverified`，不要补脑。
