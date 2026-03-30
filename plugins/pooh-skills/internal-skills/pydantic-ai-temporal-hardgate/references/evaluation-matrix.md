# 评估矩阵：怎么判断 broken、unsafe、fragile、sound、hardened、unverified

## 目录

- [Gate 列表](#gate-列表)
- [状态定义](#状态定义)
- [总评只允许这些值](#总评只允许这些值)
- [严重性默认倾向](#严重性默认倾向)
- [Merge gate shorthand](#merge-gate-shorthand)
- [使用原则](#使用原则)

## Gate 列表

每次审计至少评估这些 gate：

- `workflow-determinism`
- `sandbox-discipline`
- `durable-agent-path`
- `agent-freeze-drift`
- `tool-contracts`
- `dependency-contracts`
- `validation-retry-path`
- `verification-harness`
- `doc-grounding`
- `merge-governance`

## 状态定义

### `not-applicable`
这个 repo 根本不在本 skill 的适用面里。不要硬判。

### `broken`
主路径已经确认写坏。  
常见例子：

- Workflow 中做真实 I/O
- raw agent/model/tool I/O 留在 Workflow
- tool contract 明显写错
- durable agent 配置漂移已出现

### `unsafe`
主路径未必立刻炸，但关键护栏缺失，风险足够高。  
常见例子：

- sandbox escape 在活跃路径存在
- replay 缺失
- time-skipping tests 缺失
- deps 契约很弱，靠运行时碰运气

### `fragile`
已经有一部分真 guardrail，但仍然容易被强 agent 绕过去。  
常见例子：

- 主路径大体走对，但没有 changed-files 硬门
- 测试有，但 fake model / replay / override 不完整
- 文档和代码部分对齐，部分乱写

### `sound`
主路径基本沿着官方 durable path 在走，关键错误没有明显暴露。  
但这不代表已经 hardened。

### `hardened`
不只是主路径走对，而且验证和门控也上锁了：

- replay 有
- time-skipping tests 有
- fake-model harness 有
- changed-files gate 有
- sandbox escape 受控
- 文档不教错规则

### `unverified`
本地仓库看不到关键证据。  
例如：

- 不知道远端是不是 required check
- 不知道 code owners 是否在平台侧强制
- 看得到 workflow 文件，看不到实际分支保护

## 总评只允许这些值

- `not-applicable`
- `workflow-time-bomb`
- `paper-guardrails`
- `partially-contained`
- `durable-harness`

### `workflow-time-bomb`
出现以下任一情况，优先判这个：

- `workflow-determinism = broken`
- `durable-agent-path = broken`
- active path 上有 critical 级 sandbox escape
- replay 相关证据直接显示兼容性已经出问题

### `paper-guardrails`
看起来有规范、有文档、有配置，但实际大多不阻断、不验证。  
换句话说：护栏写在纸上，系统没上锁。

### `partially-contained`
主路径没有明显炸穿，但 guardrail 仍然脆，尤其在：

- replay / tests
- doc grounding
- merge governance
- escape hatch governance

### `durable-harness`
核心 gate 至少 `sound`，关键验证层与 changed-files 门控到位，仓库不会靠运气维持正确。

## 严重性默认倾向

- `critical`：determinism、sandbox、durable path 主路炸穿
- `high`：tool / deps / retry 契约错误，或关键验证层缺失
- `medium`：文档教错、测试不完整、局部边界不清
- `low`：补强与整洁性问题

## Merge gate shorthand

- `block-now`
- `block-changed-files`
- `warn-only`
- `unverified`

## 使用原则

1. 看到“配置存在但不阻断”，优先判 `unsafe` 或 `fragile`，不要心软。
2. 看到“测试存在但不证明 replay / durable path”，不要夸它安全。
3. 看不到远端 enforcement，就写 `unverified`。
4. 解释可以尖锐，判断必须有证据。
