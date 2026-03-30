---
name: pydantic-ai-temporal-hardgate
description: "Audits Python repos that use Pydantic AI with Temporal for deterministic durable execution. Use for Temporal + pydantic-ai durable-path review、workflow determinism audit、replay/time-skipping verification、AI durable harness hardening. Produces a blunt human report, a concise agent brief, and a machine-readable summary."
---

# Pydantic AI Temporal Hardgate Skill

## 什么时候用

当用户要做下面这些事时，使用这个 skill：

- 审计一个 `Python + Temporal + pydantic-ai` 仓库，判断它到底是在做 durable execution，还是只是在赌运气
- 给 `Codex` 或同级别 code agent 加更硬的 harness，重点压制 Workflow 语义、tool/deps 契约、验证与 merge gate 这些高价值错法
- 检查 repo 是否沿着官方 durable path 在走，而不是自己拼了一套看似聪明、实则脆弱的胶水
- 生成一份双读者报告：
  - 给人类：尖锐、直接、能看懂的审计报告
  - 给 code agent：短、硬、可执行的 remediation brief

不要把这个 skill 用在这些任务上：

- 一般性的 Python code review
- 普通 lint / type check / 格式化建议
- dead code 清理、依赖瘦身、repo 美化
- 泛泛而谈的“签名即契约”审计
- 仓库根本没在用 `Temporal` 或 `pydantic-ai`

如果 repo 与 `Temporal` / `pydantic-ai` 没有实质关系，就明确输出 `not-applicable`，不要为了凑结论硬判。

## Mission

你的任务是 **detect, explain, prioritize, and recommend**。

重点只放在这些面：

- Workflow determinism
- sandbox discipline
- durable-agent wiring
- tool / deps contracts
- validation / retry semantics
- replay / time-skipping / fake-model verification
- doc grounding
- merge governance

默认是 **scan + report**。除非用户明确要求修改，否则不要自动重写大段 Workflow 语义。

## Reading map

- 生成人类报告时，从 [`assets/human-report-template.md`](assets/human-report-template.md) 开始。
- 生成 agent remediation brief 时，从 [`assets/agent-brief-template.md`](assets/agent-brief-template.md) 开始。
- 生成 `.repo-harness/pydantic-temporal-summary.json` 时，必须遵守 [`assets/pydantic-temporal-summary.schema.json`](assets/pydantic-temporal-summary.schema.json)。
- 共享输出契约读取 [`references/shared-output-contract.md`](references/shared-output-contract.md)。
- 共享报告语气与双读者要求读取 [`references/shared-reporting-style.md`](references/shared-reporting-style.md)。
- 共享 runtime truth 与 blocked artifact 语义读取 [`references/shared-runtime-artifact-contract.md`](references/shared-runtime-artifact-contract.md)。
- live-doc 核验与 blocked 规则读取 [`references/live-doc-verification.md`](references/live-doc-verification.md)。
- Context7 查询路径与提问模板读取 [`references/context7-query-playbook.md`](references/context7-query-playbook.md)。
- 判断官方 durable path、hard fail、误报黑名单、证据优先级时，读取 [`references/pydantic-temporal-domain-standard.md`](references/pydantic-temporal-domain-standard.md)。
- 判断 `broken` / `unsafe` / `fragile` / `sound` / `hardened` / `unverified` 的边界，以及总体 verdict 映射时，读取 [`references/evaluation-matrix.md`](references/evaluation-matrix.md)。
- 当另一个 skill 或 CI 需要稳定 baseline 工件时，使用 `scripts/run_pydantic_temporal_scan.py`、`scripts/validate_pydantic_temporal_summary.py` 和 `scripts/run_all.sh`。

只在需要时读取 reference，不要把 reference 原文整段复述进最终报告。  
如果直觉和 reference 冲突，优先相信 reference。

## 双读者输出

始终输出人类报告和 agent brief，但共享 contract 不要在这里重复展开。

- 共享语气、双读者规则、blocked artifact 语义，按 [`references/shared-reporting-style.md`](references/shared-reporting-style.md) 与 [`references/shared-output-contract.md`](references/shared-output-contract.md) 执行。
- 这个 skill 额外要求：人类报告必须写出 **是什么 / 为什么重要 / 建议做什么 / 给非程序员的人话解释**，agent brief 只给决策与目标形状，不写长教程。

## Operating stance

把下面这些当成默认真理：

- Workflow 不是普通 async Python
- “本地跑过一次”不等于 durable execution
- 配置文件存在，不等于 guardrail 已经上锁
- 静态快门先挡最硬的错，验证 harness 再给真相，叙述最后才跟上
- 强 code agent 会优先走最省事的路径，所以你要优先评估它最容易钻的洞

写报告时：

- 优先证据，不要让解释跑在证据前面
- 写用户的语言；工具名、配置键、issue type 保持原技术名词即可
- Applicability 弱时，不要硬套标准，直接写 `not-applicable`
- 合并重复发现，按根因叙事，不要做廉价流水账

## Live Doc Verification

这个 skill 不把“我记得官方现在推荐什么”当成可靠事实。

如果 repo 属于 `Python + Temporal + pydantic-ai`，先做这四步：

1. 从 repo 里提取版本线索、真实 runtime surface、以及 durable path 的实际接线位置。
2. 用 [`references/context7-query-playbook.md`](references/context7-query-playbook.md) 里的方式，通过 `Context7` 查当前官方文档。
3. 用 [`references/live-doc-verification.md`](references/live-doc-verification.md) 里的 blocked 规则决定这次 run 能不能给正式 verdict。
4. 再拿本地静态证据去判断当前实现到底偏离官方 durable path 多远。

不要把下面这些当成主答案：

- “pytest 绿了”
- “README 里写了”
- “本地跑过一次”
- “mypy 没报错应该差不多”

这些都不是 live-doc-grounded durable harness。最多算局部信号。

## 必查 gate

至少评估下面这些 gate。每个 gate 都必须给状态；边界定义和 verdict 映射按 [`references/evaluation-matrix.md`](references/evaluation-matrix.md) 执行。

- `workflow-determinism`
  - 看 Workflow 结构是否符合 Temporal 语义，是否把 I/O、随机性、时间、全局副作用和不稳定顺序逻辑错误地留在 Workflow 中
- `sandbox-discipline`
  - 看是否存在 `sandbox_unrestricted()`、`sandboxed=False`、`UnsandboxedWorkflowRunner`、顶层重副作用导入，以及是否把 passthrough 当垃圾桶而不是受控用于安全、确定性模块
- `durable-agent-path`
  - 看 agent 是否沿官方 durable path 进入 Workflow，而不是把 raw `Agent`、raw model / tool I/O、或不受支持的任意模型实例塞进 Workflow / durable path
- `agent-freeze-drift`
  - 看 durable agent 创建时机是否稳定，包装后是否还在继续改 model / toolsets / config
- `tool-contracts`
  - 看 `@agent.tool` / `@agent.tool_plain` 是否选对，`RunContext` 首参形状、`args_validator` / `ModelRetry` 语义、参数描述与输出约束是否匹配
- `dependency-contracts`
  - 看 `deps_type` 与运行时 `deps=` 是否一致，是否把 bag-of-stuff 冒充依赖契约
- `validation-retry-path`
  - 看验证失败是否进入正确的重试语义，是否被宽泛异常吞掉，是否把 recoverable failure 和 system failure 混成一团
- `verification-harness`
  - 看 replay、time-skipping tests、fake model / override、changed-files gate 是否真实存在并进入 CI
- `doc-grounding`
  - 看 README / AGENTS / docs 是否在教正确的 Temporal / pydantic-ai 规则，而不是用过期经验污染 agent
- `merge-governance`
  - 区分本地能跑、CI 会跑、PR required checks、code owners、远端保护是否可见；看不到远端 enforcement 就写 `unverified`

总体 verdict 只允许使用 [`references/evaluation-matrix.md`](references/evaluation-matrix.md) 里的值。不要临场发明分级。

## 误报防线

下面这些是高频误报点，不能写错：

- `await asyncio.sleep(...)` 在 Workflow 中不一定违规，它可能是合法的 durable timer 用法
- 不要因为看见 `asyncio` 就条件反射判错；抓的是破坏确定性的用法
- 不要把安全、确定性、无副作用的 passthrough modules 一刀切判错；问题是借 passthrough 偷带不确定性或副作用
- Activity 可以做 I/O，Workflow 不行；不要把两者规则混在一起
- raw `Agent` 在普通应用代码里使用，不等于错误；错的是它被错误带进 Workflow 语义
- 有 `pytest` 不代表有 replay 兼容
- 有类型注解不代表有 runtime contract
- 有 CI 文件不代表 required checks 已上锁

## 高信号搜索锚点

做仓库画像时，优先定位这些符号和文件面：

- Temporal 侧：`temporalio.workflow`、`@workflow.defn`、`@workflow.run`、`Worker(`、`sandbox_unrestricted`、`sandboxed=False`、`UnsandboxedWorkflowRunner`、`workflow.now`、`workflow.random`、`workflow.uuid4`、`workflow.sleep`
- pydantic-ai 侧：`Agent(`、`TemporalAgent(`、`PydanticAIPlugin`、`PydanticAIWorkflow`、`@agent.tool`、`@agent.tool_plain`、`RunContext`、`args_validator`、`ModelRetry`、`deps_type`、`TestModel`、`FunctionModel`、`Agent.override`、`ALLOW_MODEL_REQUESTS`
- 文档与门控：`README*`、`AGENTS*`、`.github/workflows/`、`CODEOWNERS`、`pyproject.toml`、`pyrightconfig.json`、`mypy.ini`、`ruff.toml`、`semgrep*`、`tests/`、`docs/`

你不是为了凑搜索结果。  
你是为了先把“代码真相”和“文档自我叙述”分开。

## 检测流程

按这个顺序做，不要乱：

1. **Applicability check**
   - 先确认 repo 是否真的同时涉及 Temporal Workflow / Worker / Client 与 pydantic-ai Agent / Tool / durable execution 接线
   - 如果不适用，输出 `overall_verdict: not-applicable`，说明原因，停止深入扫描，但仍产出三份 `not-applicable` 工件

2. **仓库画像**
   - 判断 Python 版本与项目形态
   - 识别 Workflow / Worker / Activity / Agent / Tool / deps / validator / tests / CI / docs / code owners 的位置

3. **Official-path alignment**
   - 拿代码真实用法对照 [`references/pydantic-temporal-domain-standard.md`](references/pydantic-temporal-domain-standard.md)
   - 判断它走的是官方 durable path，还是自制拼装

4. **Hard-fail static scan**
   - 优先抓 Workflow 非确定性、sandbox escapes、raw agent/model/tool I/O in Workflow、tool signature mismatch、deps 契约漂移、retry path 写坏

5. **Dynamic / verification evidence**
   - 再看 replay、time-skipping tests、fake model / override、CI gate、changed-files strategy、code owners / remote enforcement 是否可见

6. **形成结论**
   - 每个发现都要写清楚：所属 gate、当前状态、证据强度、下一步决策
   - 区分“已确认问题”和“未验证但关键”的东西

7. **输出双报告**
   - 写人类报告、agent brief、summary JSON

## Fleet baseline mode

当需要 headless baseline 或 orchestrator 聚合时，运行：

```bash
bash scripts/run_all.sh /path/to/repo
```

如果仓库没有同时暴露 `Temporal` 和 `pydantic-ai` durable surface，wrapper 会老老实实输出 `not-applicable`，而不是为了凑结论硬判。

## 人类报告契约

使用 [`assets/human-report-template.md`](assets/human-report-template.md) 与 [`references/shared-reporting-style.md`](references/shared-reporting-style.md) 作为默认骨架。

这个 skill 额外要求：

- 开头给一句狠但准确的总判决
- 单独写“这套仓库现在在教 AI 学什么坏习惯”
- 每个关键问题都写 **是什么 / 为什么重要 / 建议做什么 / 给非程序员的人话解释**
- 把已确认问题与无法从本地证明的问题分开
- 行动顺序拆成 **现在就做 / 下一步 / 之后再做**
- 允许尖锐，但不允许脱离证据

## Agent brief 契约

使用 [`assets/agent-brief-template.md`](assets/agent-brief-template.md) 与 [`references/shared-output-contract.md`](references/shared-output-contract.md) 作为默认骨架。

每个 finding 至少给出这些字段：

- `id`
- `gate`
- `severity`
- `confidence`
- `current_state`
- `target_state`
- `locus`
- `title`
- `evidence_summary`
- `decision`
- `change_shape`
- `validation`
- `merge_gate`
- `autofix_allowed`
- `notes`

`decision` 只允许使用这些动作：

- `adopt`
- `harden`
- `replace`
- `quarantine`
- `remove`
- `defer`

`change_shape` 只写目标形状，不写长教程。  
`merge_gate` 只允许 `block-now`、`block-changed-files`、`warn-only`、`unverified`。  
`autofix_allowed` 对 Workflow 语义、sandbox、retry 语义默认应为 `false`。

## 输出契约

按 [`references/shared-output-contract.md`](references/shared-output-contract.md) 产出标准工件。

这个 skill 的具体文件名固定为：

- `.repo-harness/pydantic-temporal-human-report.md`
- `.repo-harness/pydantic-temporal-agent-brief.md`
- `.repo-harness/pydantic-temporal-summary.json`

summary 必须符合 [`assets/pydantic-temporal-summary.schema.json`](assets/pydantic-temporal-summary.schema.json)。

如果 repo 不适用，也照样创建三份产物，但内容应明确标记：

- `overall_verdict: not-applicable`
- `findings: []` 或仅保留适用性说明
- 不要编造风险项凑数

## 旧仓库的默认处理方式

这个 skill 默认严格，但不做蠢事。

如果旧仓库债很多，默认策略是：

- 对新代码 / 变更 Workflow / 契约层文件立即上硬门
- 对遗留烂账做命名隔离
- 每个隔离区都必须有 owner、路径边界、原因、风险说明、退出条件

不接受这种烂策略：

- “先全量 ignore”
- “先关 replay，后面再补”
- “先 unsandboxed 跑通”
- “先允许真模型进测试”
- “先合进去，稳定后再收紧”

允许过渡，不允许糊弄。

## 安全规则

- 默认只做检测与报告
- 不要自动重写大段 Workflow 语义，除非用户明确要求修改
- 不要默认关闭 sandbox、关闭 replay、关闭验证、关闭测试隔离
- 不要推荐“为了通过 CI 先绕开 guardrail”
- 不要自动删除大量异常处理或 ignore，除非风险已标清并得到明确授权
- 如果建议 autofix，只允许低风险、机械性、可验证的部分，并明确标记 `autofix_allowed`
