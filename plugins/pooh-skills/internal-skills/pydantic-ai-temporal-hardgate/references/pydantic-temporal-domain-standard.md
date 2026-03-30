# Pydantic AI + Temporal 域标准（严格版）

## 目录

- [一条总原则](#一条总原则)
- [官方优先路径](#官方优先路径)
- [Hard fail：一旦命中，就别粉饰](#hard-fail一旦命中就别粉饰)
- [High-signal warnings：不一定立刻爆，但极容易教坏 AI](#high-signal-warnings不一定立刻爆但极容易教坏-ai)
- [Allowed / 别误报](#allowed--别误报)
- [推荐门控栈](#推荐门控栈)
- [证据优先级](#证据优先级)
- [Source basis](#source-basis)

这份 reference 不是用来原样贴给用户看的。  
它是这个 skill 的裁判标准。

## 一条总原则

**Workflow 不是普通 async Python。  
Agent 不是随便塞进 Workflow 的普通对象。  
“能跑一次”不等于 durable。**

如果代码破坏了确定性、绕开了 sandbox、把真实 I/O 留在 Workflow、或者把 pydantic-ai 契约写成“差一点对”，就该被直接点名。

## 官方优先路径

当 repo 要在 Temporal Workflow 中运行 pydantic-ai agent 时，默认优先认可：

- 使用 `TemporalAgent` 承担 durable agent 角色
- 使用 `PydanticAIPlugin` 做必要的接线
- 采用官方 durable execution 思路，让模型请求、工具调用、MCP 通信之类的 I/O 下沉到 Activities
- Workflow、Worker、durable agent 定义保持稳定且可注册，不要在 `run()` 里现造
- 需要运行时选模型时，优先使用可序列化、可重放的模型标识，或在 `TemporalAgent(models={...})` 中预注册模型后再引用
- 如果用了 dynamic toolset，durable execution 需要稳定标识，不要做随缘动态拼装

默认不认可：

- 在 Workflow 中直接跑 raw `Agent`
- 在 Workflow 中直接触发模型请求、工具调用或其他 I/O
- 把任意模型实例直接塞进 `TemporalAgent` / durable path，指望 Temporal 替你处理序列化与 replay
- “为了省事先 unsandboxed”
- “先本地跑通，replay 以后再说”

## Hard fail：一旦命中，就别粉饰

### Workflow 结构错位

- Workflow 形状明显不符合 Temporal Python 的基本定义要求
- `@workflow.run` 缺失、不唯一、或不是 `async def`

### Workflow 中的真实语义违规

- 网络 I/O
- 数据库 I/O
- 文件 I/O
- 子进程 / 外部进程
- 线程
- raw 模型请求
- raw 工具调用
- raw MCP 通信
- 未受控的随机性 / 时间 / UUID
- 全局可变状态突变
- 其他明显破坏重放一致性的行为

### Sandbox 逃逸

- `sandbox_unrestricted()`
- `@workflow.defn(sandboxed=False)`
- `UnsandboxedWorkflowRunner`

除非仓库把它明确隔离、给出 owner、范围和退出条件，否则默认至少 `high`，常常可以直接 `critical`。

### pydantic-ai 契约明显写错

- 需要上下文的工具，没有把 `RunContext` 放在第一个参数
- 不需要上下文的工具，却错误套用 context 形状
- `args_validator` 的可恢复校验失败没有进入 `ModelRetry` 语义，而是被宽泛异常吞掉或改写
- `deps_type` 和实际 `deps=` 明显脱节
- durable agent 包装后还在继续改 model / toolsets，形成配置漂移

## High-signal warnings：不一定立刻爆，但极容易教坏 AI

- 在 Workflow 里直接用 `datetime.now()` / `uuid.uuid4()` / `random.*()`，而不是 workflow-safe API 或 Activities
- Workflow 文件顶层导入重副作用库
- 把 passthrough 当垃圾桶，缺少边界说明，顺手把不确定性或副作用库一起带进来
- 关键 Workflow 没有 time-skipping tests
- 仓库没有 replay gate
- pydantic-ai 测试没有 fake model / override / 禁实网请求的护栏
- README / AGENTS / docs 在教错规则，尤其是把错规则写成“团队标准”
- 工具函数 docstring 和参数描述极弱，让 agent 只能靠猜

## Allowed / 别误报

下面这些事情不能乱报：

- `await asyncio.sleep(...)` 在 Workflow 中**不是天然违规**  
  它可以是合法的 durable timer 用法
- `workflow.sleep(...)` 当然也可以
- 安全、确定性、无副作用的 passthrough modules 可以是合理甚至推荐的优化  
  错的是拿 passthrough 去放行不确定性、I/O、或重副作用模块
- Activity 可以做 I/O，Workflow 不行  
  别把两者混成一锅
- raw `Agent` 在普通应用代码里使用，不等于错误  
  错的是把它带进 Workflow 语义却不走 durable path
- 有 `pytest` 不代表有 replay 兼容
- 有类型注解不代表有 runtime contract
- 有 CI 文件不代表 required checks 已上锁

## 推荐门控栈

### 静态快门

- `Semgrep`
- `Ruff`
- `basedpyright` strict

### Temporal 真验证

- Replay
- time-skipping integration tests

### pydantic-ai 真验证

- `TestModel`
- `FunctionModel`
- `Agent.override`
- `ALLOW_MODEL_REQUESTS=False`

## 证据优先级

按这个顺序相信证据：

1. **代码与测试**
2. **CI 与规则配置**
3. **仓库文档 / AGENTS / README**
4. **推断**

解释永远不能跑在证据前面。

## Source basis

这份 reference 基于用户提供的调研附件整理，并按当前官方文档语义做了收口。  
用途是帮助 skill 避免“用幻觉检查幻觉”。
