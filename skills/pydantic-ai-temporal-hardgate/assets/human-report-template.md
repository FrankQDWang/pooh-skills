# Pydantic AI + Temporal 审计报告

## 一句话判决
- **总体结论**：{{overall_verdict}}
- **一句狠话**：{{one_line_verdict}}

> 对系统下刀，对人闭嘴。别把“能跑一次”包装成“可持久执行”。

## 这套仓库现在在教 AI 学什么坏习惯
- {{bad_habit_1}}
- {{bad_habit_2}}
- {{bad_habit_3}}

## 为什么这不是普通 Python 代码
- Workflow 要可重放，不是随手写 I/O 的地方
- Agent 能调用工具，不代表它在 Workflow 语义里就合法
- 测试绿过一次，不等于 replay 下不会炸

## 仓库画像
- Workflow 面：{{workflow_surface}}
- Agent 面：{{agent_surface}}
- 已见门控：{{visible_gates}}
- 看不到但关键：{{unverified_surface}}

## 关键问题（已确认）

### 1. {{finding_title_1}}
- **Gate**：{{gate_1}}
- **状态**：{{state_1}}
- **严重性**：{{severity_1}}
- **置信度**：{{confidence_1}}

**是什么**  
{{what_it_is_1}}

**为什么重要**  
{{why_it_matters_1}}

**建议做什么**  
{{what_to_do_1}}

**给非程序员的人话解释**  
{{plain_language_1}}

---

### 2. {{finding_title_2}}
- **Gate**：{{gate_2}}
- **状态**：{{state_2}}
- **严重性**：{{severity_2}}
- **置信度**：{{confidence_2}}

**是什么**  
{{what_it_is_2}}

**为什么重要**  
{{why_it_matters_2}}

**建议做什么**  
{{what_to_do_2}}

**给非程序员的人话解释**  
{{plain_language_2}}

## 别再教错规则
- {{wrong_rule_1}}
- {{wrong_rule_2}}

> 例子：  
> - “把 `asyncio.sleep()` 在 Workflow 中一律当违规”  
> - “把 raw Agent 和 TemporalAgent 混成一个东西”  
> - “把有 CI 文件当成 merge gate 已上锁”

## 无法从本地仓库证明，但必须说清楚的事
- {{unverified_item_1}}
- {{unverified_item_2}}

## 术语翻译成人话
- **determinism / 可确定性**：同样的历史重放回来，代码必须走出同样的结果
- **Replay**：拿历史事件重新跑一遍，看看改过的 Workflow 还兼不兼容
- **Sandbox**：Temporal 给 Workflow 加的一层护栏，防止你顺手写出非确定性代码
- **Tool contract**：工具函数到底怎么收参数、能不能拿上下文、失败时怎么反馈
- **Durable path**：框架官方推荐的、能长期稳定运行的接法，不是临时拼凑的胶水
- **Merge gate**：PR 合并前必须通过的机器检查和人工审批

## 行动顺序

### 现在就做
- {{now_1}}
- {{now_2}}

### 下一步
- {{next_1}}
- {{next_2}}

### 之后再做
- {{later_1}}
- {{later_2}}

## 最后一句
{{closing_line}}

> 好的 closing line 例子：  
> - “Workflow 里顺手写 I/O，不叫快，叫把重放模型写废。”  
> - “你现在不是在防幻觉，你是在训练幻觉怎么骗过你。”  
> - “规则写在 README 不够，写进 replay、测试和合并门才算数。”