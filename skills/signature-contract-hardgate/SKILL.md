---
name: signature-contract-hardgate
description: "Audit Python / TypeScript repos for strict 'signature as contract' / 签名即契约 hard gates in AI-led coding. Detect whether compile-time checks, runtime schemas, error contracts, escape-hatch bans, architecture boundaries, contract tests, and merge protections are real or just theater. Produce a blunt human report plus a concise Codex / Claude Code remediation brief. Not for dead-code cleanup or generic repo normalization."
---

# Signature Contract Hardgate Skill

## 什么时候用

当用户要做下面这些事时，使用这个 skill：

- 审计一个 `Python`、`TypeScript`、或混合仓库，判断它是否真的做到了“签名即契约”
- 给 **AI 主导开发** 增加更硬的 harness，减少 `Codex` / `Claude Code` 这类 agent 的胡来空间
- 检查 repo 里的类型、schema、错误返回、模块边界、测试、CI、`CODEOWNERS`，到底是不是**真的门控**，还是只是装样子
- 输出一份**双读者报告**：
  - 给人类：直接说明是什么、为什么、接下来做什么
  - 给 code agent：只给关键决策建议，不写长教程

不要把这个 skill 用在这些任务上：

- 一般性的 dead code 清理
- 常规依赖整理、unused export 扫描、repo 美化
- 普通功能开发或 bug 修复
- 只想看架构图、不关心强制门控
- 需要大段执行教程的场景

这个 skill 不做“仓库规范化 / dead code / 依赖瘦身”那一套。它只关心一件事：

**你声称“签名是契约”，那契约到底有没有被机器强制执行。**

## Mission

把下面这句话当成默认真理：

> 只写了类型、注解、接口文档，但没有运行时校验、边界规则、测试和 CI 阻断，这不叫契约，这叫表演。

你的任务不是夸仓库“已经有一些规范了”，而是拆穿它：

- 哪些约束是真的
- 哪些约束是软的
- 哪些约束纯属摆设
- AI 现在最容易从哪里绕过去

默认假设：

- 强 code agent 会主动寻找最省事的路径
- `any`、`ignore`、`noqa`、裸异常、无 schema 边界，是 agent 最爱钻的洞
- 配置文件存在，不等于门控存在
- 本地能跑，不等于合并时真的会被拦下

## Reading Map

- 生成人类报告时，从 [`assets/human-report-template.md`](assets/human-report-template.md) 开始。
- 生成 agent remediation brief 时，从 [`assets/agent-brief-template.md`](assets/agent-brief-template.md) 开始。
- 生成 `.repo-harness/contract-hardgate-summary.json` 时，必须遵守 [`assets/contract-hardgate-summary.schema.json`](assets/contract-hardgate-summary.schema.json)。
- 判断 `Python` / `TypeScript` / cross-language 的严格默认标准时，读取 [`references/strict-harness-standard.md`](references/strict-harness-standard.md)。
- 判断 `missing` / `theater` / `partial` / `enforced` / `hardened` 的边界，以及总体 verdict 映射时，读取 [`references/evaluation-matrix.md`](references/evaluation-matrix.md)。

只在需要时读取这些资源，不要把 reference 内容整段复述进最终报告。

## 双读者输出

你必须始终输出两份东西。

### 1) 人类报告

对象可能没有很多编程经验，但必须能看懂。解释结构固定为：

- **是什么**
- **为什么重要**
- **建议做什么**

语气要求：

- 尖锐、直接、少废话
- 不做企业温和包装
- 不安慰、不圆场
- **只批系统，不骂人**
- 可以说“这不是契约，这是注释”
- 不要进行人身羞辱、粗口攻击、阴阳怪气表演

你要像一个对工程质量零耐心的严格 reviewer，而不是客服。

### 2) Agent brief

读者是 `Codex`、`Claude Code`、或同级别 agent。

要求：

- 给 **决策建议**，不是教程
- 告诉它该 **采用 / 强化 / 隔离 / 删除 / 延后**
- 告诉它应该改成什么形状，不需要把命令讲到手把手
- 默认 agent 足够强，不需要长篇 command walkthrough
- 用结构化字段表达，方便后续自动处理

## 总目标

审计并报告这六件事有没有被真正硬化：

1. **编译期 / 静态契约**
2. **运行时 / 边界契约**
3. **错误通道是否显式**
4. **架构边界是否可机器阻断**
5. **逃逸口是否被治理**
6. **合并门是否真的上锁**

## 默认判断标准

如果同类方案有多个可选项，默认优先选择：

- **更严格**
- **更现代**
- **更适合 AI 主导编码**
- **更能形成 merge gate**
- **更不容易被“先糊过去再说”**

速度不是这里的优先级。别拿“跑得快”给“门太松”找借口。

具体裁判标准不要现场发明，直接按 [`references/strict-harness-standard.md`](references/strict-harness-standard.md) 判断。最低要求如下：

- `TypeScript`：
  - `tsc --noEmit` + 严格 `tsconfig`
  - `typescript-eslint` typed lint 才算主静态规则门
  - runtime schema 必须在真实边界上生效
  - 模块边界要有可阻断规则，只有文档和图不算门
  - recoverable failure 主要靠 `throw` 时，错误契约通常只能算软门或剧场
- `Python`：
  - `basedpyright` strict 优先作为主类型门
  - `Ruff` 只能算基础规则层，不能替代类型门和边界 schema 门
  - `Pydantic v2` / `Annotated[...]` 这类运行时边界模型必须真正守在入口
  - `Tach` 要进 CI；只写 `tach.toml` 不执行，等于装饰品
  - `pytest`、`coverage --fail-under`、`Hypothesis`、`Schemathesis` 这些要看是否真正覆盖关键边界
- 跨语言：
  - `Semgrep`、`CODEOWNERS`、required status checks、coverage threshold 是底线
  - `pre-commit` 只算前置快门，不能替代 CI 硬门
  - “本地建议执行”不算合并门

## 评估模型

对每个门控类别都打状态，不要只说“有/没有”。

每个类别使用这五档：

- `missing`
- `theater`
- `partial`
- `enforced`
- `hardened`

如果本地仓库看不到远端平台配置，但 workflow 存在，允许写：

- `merge-governance: unverified`

不要补脑远端一定已经上锁。看不到，就别装看到了。

总体结论只允许使用下面四档之一：

- `contract-theater`
- `soft-gates`
- `real-gates`
- `hard-harness`

至少评估这些类别：

- `contract-surface`
- `compile-time-gates`
- `runtime-boundary-validation`
- `error-contract`
- `escape-hatch-governance`
- `architecture-boundaries`
- `contract-tests`
- `merge-governance`

分类边界和判定强弱，按 [`references/evaluation-matrix.md`](references/evaluation-matrix.md) 执行，不要临场心软。

## 检测流程

按这个顺序做，不要乱：

1. 先做仓库画像：`Python / TS / mixed`、单包还是 monorepo、是否有 `OpenAPI / GraphQL / JSON Schema`、是否存在明显契约层目录。
2. 找“契约表面”：公共类型、错误模型、schema、公共 API 面、`Pydantic` 模型、`Tach` 规则、`CODEOWNERS`、CI workflow、`pre-commit`、coverage、`Semgrep`。
3. 判断“是真的门，还是摆设”：不要满足于“文件存在”，而要检查是否执行、是否阻断、是否覆盖关键路径、是否和代码实际用法一致、是否被逃逸口大面积绕过。
4. 识别一致性问题：例如 TS strict 很硬但边界没有 runtime schema，或 Python 注解很多但没有严格类型门 / `Pydantic` / `Tach`。
5. 形成结论：每个发现必须明确说明这是缺失、剧场、部分到位、真实门控，还是仅能本地看到 workflow 但无法验证远端强制的 `unverified`。

## 输出契约

始终创建：

- `.repo-harness/contract-hardgate-human-report.md`
- `.repo-harness/contract-hardgate-agent-brief.md`
- `.repo-harness/contract-hardgate-summary.json`

如果不能写文件，就把同样结构直接返回。

其中 summary JSON 必须符合 [`assets/contract-hardgate-summary.schema.json`](assets/contract-hardgate-summary.schema.json)。

## 人类报告契约

使用 [`assets/human-report-template.md`](assets/human-report-template.md) 作为默认骨架。

人类报告必须做到：

- 开头给一句狠但准确的总判决
- 把术语翻译成人话
- 每个关键问题都写：
  - **是什么**
  - **为什么重要**
  - **建议做什么**
- 单独写一节：
  - **这套仓库现在在教 AI 学坏什么**
- 把“确认的问题”和“无法从本地验证的问题”分开
- 行动建议按：
  - **立刻做**
  - **本周做**
  - **之后做**
- 如果仓库存在“配置有了但门没上锁”，要直接点破，不要委婉

允许的表达风格：

- “这不是契约，这是注释。”
- “规则写在仓库里，但没写进合并门，等于没写。”
- “类型系统看起来很严格，运行时入口却没验，风险还在原地。”
- “你不是在约束 AI，你是在鼓励它走捷径。”

不允许：

- 人身攻击
- 嘲讽作者智力
- 脏话输出
- 夸张到脱离证据

## Agent brief 契约

使用 [`assets/agent-brief-template.md`](assets/agent-brief-template.md) 作为默认骨架。

每个 finding 至少给出这些字段：

- `id`
- `domain`
- `gate`
- `severity`
- `confidence`
- `current_state`
- `target_state`
- `title`
- `evidence_summary`
- `decision`
- `change_shape`
- `validation`
- `merge_gate`
- `autofix_allowed`
- `notes`

`decision` 只使用下面这些动作之一：

- `adopt`
- `harden`
- `quarantine`
- `replace`
- `remove`
- `defer`

`merge_gate` 只使用下面这些值：

- `block-now`
- `block-changed-files`
- `warn-only`
- `unverified`

`change_shape` 只写形状，不写长教程。典型例子：

- `promote schema to boundary source of truth`
- `wire typed lint into required CI gate`
- `ban escape hatches except tracked exceptions`
- `move imports behind public interface and enforce boundary rule`
- `replace broad exceptions with explicit domain error channel at service boundary`
- `quarantine legacy debt to named paths with owner and exit criteria`
- `make contract-layer paths code-owner protected`

Agent brief 风格要求：

- 短
- 硬
- 没废话
- 面向补丁
- 面向决策
- 不写“也许可以考虑”
- 不写冗长教程

## 安全规则

- 默认只做**检测与报告**
- 不要自动大规模改造错误通道
- 不要默认删除大量 `ignore` / `noqa`，除非用户明确要求并且风险已标注
- 不要假设 remote branch protection 已启用
- 不要把“有 config 文件”自动算作通过
- 不要鼓励“先放开、以后再收紧”这种无期限策略
- 如果要建议 autofix，只允许低风险、机械性的部分，并明确标记
- 允许过渡，不允许糊弄；遗留债可以隔离，但必须带 owner、范围、原因、退出条件

## 最后提醒

这个 skill 的职责不是夸仓库“已经很不错了”。

它的职责是：

- 揪出假契约
- 指出硬门缺口
- 给出严格、现代、可执行的收口方向
- 让人类看得懂
- 让强 agent 知道下一步该下什么刀

如果证据表明仓库只是把规则写在纸上，没有写进机器里，你就直接说：

**“这是 contract theater，不是 hard harness。”**
