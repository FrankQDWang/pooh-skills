# 签名即契约硬门控审计报告

## 一句话判决
- **总体结论**：{{overall_verdict}}
- **一句人话**：{{one_line_verdict}}

> 这里不要端水。结论要狠，但必须基于证据。批系统，不骂人。

## 这套仓库现在在教 AI 学坏什么
- {{bad_habit_1}}
- {{bad_habit_2}}
- {{bad_habit_3}}

## 仓库画像
- 语言 / 形态：{{repo_profile}}
- 契约表面：{{contract_surface_summary}}
- 可见门控：{{visible_gates_summary}}
- 不可见但关键：{{unverified_surface_summary}}

## 关键问题（已确认）

### 1. {{finding_title}}
- **状态**：{{state}}
- **严重性**：{{severity}}
- **置信度**：{{confidence}}

**是什么**  
{{what_it_is}}

**为什么重要**  
{{why_it_matters}}

**建议做什么**  
{{what_to_do}}

**给非程序员的人话解释**  
{{plain_language_explanation}}

---

### 2. {{finding_title_2}}
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
{{plain_language_explanation_2}}

## 无法从本地仓库证明，但必须说清楚的事
- {{unverified_item_1}}
- {{unverified_item_2}}

> 例子：你可以看到 workflow 文件，但看不到 GitHub 的 required checks / branch protection。那就写 **未验证**，别脑补已经上锁。

## 术语翻译成人话
- **编译期门控**：代码还没运行，机器先拦一遍
- **运行时校验**：外部数据真正进系统时，再做一次真检查
- **错误通道显式化**：失败怎么发生、会返回什么，不藏着掖着
- **模块边界**：哪些代码能互相调用，哪些不许
- **逃逸口**：为了图省事绕过规则的洞，比如 `any`、`ignore`、`noqa`
- **合并门**：PR 合并前必须通过的机器检查和人工审批

## 行动顺序

### 立刻做
- {{now_1}}
- {{now_2}}

### 本周做
- {{next_1}}
- {{next_2}}

### 之后做
- {{later_1}}
- {{later_2}}

## 最后一句
{{closing_line}}

> 好的 closing line 例子：
> - “规则写进仓库不够，写进合并门才算数。”
> - “你现在不是在用契约约束 AI，你是在给它留后门。”
> - “类型可以骗人，边界校验和 CI 阻断不会。”
