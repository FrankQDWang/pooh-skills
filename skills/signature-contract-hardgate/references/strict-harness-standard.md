# 签名即契约硬门控标准（严格版）

这不是“工具大全”。这是默认裁判标准。

## 一条总原则

**配置存在 ≠ 约束存在。  
检查会跑 ≠ 合并会被拦。  
类型存在 ≠ 运行时安全存在。**

## TypeScript 默认标准

### 必须至少满足

- `tsc --noEmit`
- `strict: true`
- `noUncheckedIndexedAccess`
- `exactOptionalPropertyTypes`
- `useUnknownInCatchVariables`
- `noImplicitReturns`
- `noFallthroughCasesInSwitch`
- `noImplicitOverride`

### 主规则层

- 首选：`typescript-eslint typed lint`
- 快层可有：Biome / Oxlint
- 但快层不许冒充主契约门

### 错误契约

优先认可：

- 判别联合
- 显式 `Result` / `Either`
- 穷举处理
- 明确 domain error model

不优先认可：

- 大量 recoverable failure 靠 `throw`
- catch 后统一包成模糊字符串
- 类型签名里完全看不出失败面

### 运行时边界

至少要有一个统一来源：

- OpenAPI
- JSON Schema
- 明确 runtime schema 层

下面这些都算坏味道：

- 只有 TS types，没有 runtime validation
- 手写 type、手写 validator、手写文档三套各玩各的
- 输入在 controller / route / handler 直接穿透业务逻辑

### TS 典型“剧场化”信号

- `strict: true`，但 repo 里 `any` 到处飞
- typed lint 没进 CI required checks
- `@ts-ignore` 没管制
- schema 有，但不是边界真入口在用
- 只有静态类型，没有运行时入口校验

## Python 默认标准

### 主门

优先用：

- `basedpyright` strict

可并存但不建议独自扛主门：

- `pyright` strict
- `mypy --strict`

### 基础规则层

- `Ruff`

### 运行时边界

优先用：

- `Pydantic v2`
- `Annotated[...]`

最看重的不是“模型文件多不多”，而是：

- 外部输入有没有先过模型
- 输出有没有边界形状
- 配置 / 消息 / JSON / webhook / env 有没有被验证

### 架构边界

- `Tach` 应该声明边界并接入 CI
- 只写 `tach.toml` 不执行，等于没有

### 测试标准

- `pytest`
- `coverage --fail-under`
- `Hypothesis`：关键性质
- `Schemathesis`：API schema 边界
- `beartype`：仅开发/测试态补网

### Python 典型“剧场化”信号

- 注解铺满仓库，但没有严格类型门
- `dict[str, Any]` 到处充当边界类型
- Pydantic 只在个别地方点缀
- `except Exception` / `except:` 常态化
- `type: ignore` / `noqa` 大量存在且无说明

## 跨语言标准

### 必看

- `Semgrep`
- `CODEOWNERS`
- required checks
- coverage threshold
- pre-commit（仅快层）
- 变更文件立即硬门 + 遗留债隔离

### 契约层建议范围

下面这些路径通常应该进入人工强审范围：

- `schemas/`
- `contracts/`
- `api/`
- `openapi/`
- `graphql/`
- `models/`（仅边界模型）
- `errors/`
- `interfaces/`
- `public/`
- `tach.toml`
- `pyproject.toml` / `mypy.ini` / `pyrightconfig.json`
- `tsconfig*.json`
- `.github/workflows/`
- `CODEOWNERS`
- `semgrep*`

## 逃逸口零容忍倾向

默认原则：

- `any`：默认不接受
- `@ts-ignore`：默认不接受
- `type: ignore`：默认不接受
- `# noqa`：默认不接受
- 宽泛 `except Exception`：默认不接受

只有同时满足下面条件，才允许算“受控例外”：

- 有明确理由
- 有局部范围
- 有 owner
- 有退出条件
- 不位于契约层 / 边界层 / 核心领域层

## 基线 / 隔离规则

可以隔离遗留债，但必须做到：

- 命名清楚
- 路径清楚
- owner 清楚
- 风险清楚
- 退出条件清楚

下面这种不接受：

- “先全量 baseline，以后再说”
- “历史问题太多，所以先都忽略”
- “等重构时再处理”但没有触发条件

## 结果判定

### `contract-theater`
仓库有规则词汇，但机器不真正拦；AI 仍可轻松绕过。

### `soft-gates`
有些门是真的，但覆盖面不够，关键边界仍暴露。

### `real-gates`
核心路径已有真实门控，AI 的主要捷径被堵住。

### `hard-harness`
契约层、边界层、架构层、合并层都已上锁，例外可追踪，旧债被隔离。
