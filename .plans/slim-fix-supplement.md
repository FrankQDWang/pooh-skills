# pooh-skills 瘦身 / 修复 / 补充计划

## 背景

基于审核发现的三类问题：结构性 bug、检查项缺失、技能重叠。
用户确认：只用 pnpm + uv、只用 Python + TypeScript、pydantic-ai-temporal 保留。

---

## 第一阶段：修复已有 bug（不改技能数量）

### 1.1 修复输出路径不一致

4 个技能的 SKILL.md 中定义的输出路径与编排器期望的路径不匹配：

| 技能 | SKILL.md 中写的路径 | 编排器期望的路径 |
|------|---------------------|------------------|
| error-governance-hardgate | `.repo-harness/error-governance-summary.json` | `.repo-harness/skills/error-governance-hardgate/summary.json` |
| overdefensive-silent-failure-hardgate | `.repo-harness/overdefensive-silent-failure-summary.json` | `.repo-harness/skills/overdefensive-silent-failure-hardgate/summary.json` |
| controlled-cleanup-hardgate | `.repo-harness/controlled-cleanup-summary.json` | `.repo-harness/skills/controlled-cleanup-hardgate/summary.json` |
| pydantic-ai-temporal-hardgate | `.repo-harness/pydantic-temporal-summary.json` | `.repo-harness/skills/pydantic-ai-temporal-hardgate/summary.json` |

**修复方案：** 统一改为编排器期望的 `.repo-harness/skills/<skill-id>/` 命名空间路径。同时更新对应的 scripts 和 schema 引用。

### 1.2 修复 controlled-cleanup-hardgate 缺少 overall_verdict

其 schema.json 中没有 `overall_verdict` 字段，但编排器的 verdict-policy 需要读取它来做 rollup。

**修复方案：** 在 `cleanup-summary.schema.json` 中补充 `overall_verdict` 字段，enum 值参考其 SKILL.md 中已有的 verdict 描述（`not-ready` / `partially-ready` / `ready-for-controlled-deletion` / `not-applicable` / `scan-blocked`）。

### 1.3 补充 verdict 映射文档

当前 verdict-policy.md 中的 RED/YELLOW/POSITIVE 桶是硬编码在 Python 里的，但没有覆盖所有技能的所有 verdict 值。

**修复方案：**
- 在 `verdict-policy.md` 中增加一个显式的 per-skill verdict → bucket 映射表
- 同步更新 `aggregate_repo_health.py` 中的 `RED_VERDICTS` / `YELLOW_VERDICTS` / `POSITIVE_VERDICTS` 常量，确保覆盖所有技能的所有 verdict enum 值

---

## 第二阶段：瘦身合并（减少 2 个技能）

### 2.1 合并 python-lint-format-audit + ts-lint-format-audit → lint-format-audit

理由：两者结构几乎相同，只是目标语言不同。合并后：
- 一个 SKILL.md，内部按语言分支
- 一个 schema，findings 带 `language: "python" | "typescript"` 字段
- 一套 scripts，接受 `--language` 参数或自动检测
- 编排器从 15 个 worker 变为 14 个

### 2.2 合并 pythonic-ddd-drift-audit 进 module-shape-hardgate

理由：两者都在检查代码结构膨胀和职责混乱。DDD drift 的核心检查项（domain boundary leak、cross-context import、thin wrapper、ABC overuse、CQRS ceremony）可以作为 module-shape-hardgate 的一个子类别。合并后：
- module-shape-hardgate 增加 `ddd-drift` finding category
- 保留 DDD 相关的检测逻辑，但作为 module-shape 的一个维度
- 编排器从 14 个 worker 变为 13 个

---

## 第三阶段：补充新技能（增加 3 个技能）

### 3.1 新增 test-quality-audit

**目的：** 检查 vibe coding 最常见的问题——测试看起来存在但实际上什么都没验证。

**检查项：**
- 测试覆盖率是否有 CI gate（不要求具体数字，检查是否有机制）
- 测试是否只有 happy path，缺少 edge case / error path
- 是否存在空测试体、`pass`-only 测试、`assert True` 占位
- 测试与代码的比例是否合理
- 是否有 flaky test 信号（retry、skip、xfail 滥用）
- mock 是否过度（mock 掉了被测逻辑本身）
- fixture 是否膨胀到不可维护

**工具：** pytest + coverage.py（Python）、vitest + c8/istanbul（TypeScript）

### 3.2 新增 secrets-and-hardcode-audit

**目的：** 检查 AI 生成代码中的凭证泄露和硬编码敏感信息。

**检查项：**
- git history 中是否有泄露的 secrets（API key、token、password）
- 当前代码中是否有硬编码凭证
- .env 文件是否被 gitignore
- 是否有 .gitignore 缺失导致的敏感文件暴露风险
- 是否使用了安全的 secret 管理方式（环境变量、vault 引用）

**工具：** gitleaks / trufflehog（git history 扫描）、自定义 pattern matching

### 3.3 新增 ci-pipeline-governance-audit

**目的：** 检查 CI/CD 流水线本身的完整性和安全性。

**检查项：**
- 是否有 required checks / branch protection
- CI 中是否有 lint、test、type-check gate
- 是否有 deployment protection（staging → production）
- workflow 文件是否有不安全的 `pull_request_target` 用法
- 是否有 dependency review / lockfile check
- CI artifacts 是否有保留策略

**工具：** GitHub API（gh cli）、workflow YAML 静态分析

---

## 第四阶段：编排器更新

### 4.1 更新 worker 列表

从 15 → 16 个 worker（-2 合并 +3 新增）：
1. dependency-audit（保留）
2. signature-contract-hardgate（保留）
3. module-shape-hardgate（吸收 pythonic-ddd-drift-audit）
4. openapi-jsonschema-governance-audit（保留）
5. distributed-side-effect-hardgate（保留）
6. pydantic-ai-temporal-hardgate（保留）
7. error-governance-hardgate（保留）
8. overdefensive-silent-failure-hardgate（保留）
9. ts-frontend-regression-audit（保留）
10. lint-format-audit（合并自 python + ts）
11. python-ts-security-posture-audit（保留）
12. llm-api-freshness-guard（保留）
13. controlled-cleanup-hardgate（保留）
14. test-quality-audit（新增）
15. secrets-and-hardcode-audit（新增）
16. ci-pipeline-governance-audit（新增）

### 4.2 增加优先级加权

在编排器的 verdict-policy 和 synthesis-policy 中增加 domain weight：
- critical tier（安全、secrets）：权重最高，任何 red 直接拉低 overall_health
- high tier（契约、分布式一致性、CI）：权重高
- medium tier（模块形状、测试质量、错误治理、清理）：权重中
- low tier（lint 风格、schema 治理、LLM freshness）：权重低

### 4.3 增加 fast mode

在编排器 SKILL.md 中增加 fast mode 支持：
- 只跑 critical + high tier 的 8-9 个技能
- 用户通过参数触发：`--fast` 或在 prompt 中说"快速检查"

---

## 执行顺序

1. 第一阶段（修复 bug）→ 先确保现有系统正确
2. 第二阶段（瘦身合并）→ 减少冗余
3. 第三阶段（补充新技能）→ 填补缺口
4. 第四阶段（编排器更新）→ 整合所有变更

每个阶段完成后可以独立验证，不依赖后续阶段。
