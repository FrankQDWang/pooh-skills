# Repo Health Control Plane Hard-Cut Checklist

本清单基于当前仓库的真实约束编写：

- `skills/` 是唯一 source of truth
- `plugins/pooh-skills/internal-skills/` 与公开 bundle 必须保持同步
- 公开入口只有 `repo-health-orchestrator`
- 当前 control plane 固定管理 17 个 child domain 和 4 个 cluster
- 严格 harness 同时检查 catalog 完整性、bundle 同步、wrapper smoke、repo-health 回归和 installer 回归

## 总目标

- [x] P0 期间不改 fleet 拓扑，保持 15 个 domain、4 个 cluster、固定 action ordering 不变
- [x] child summary 统一收口到一个机器契约，不再允许多键 verdict fallback
- [x] 所有 child 工件统一进入 `.repo-harness/skills/<skill-id>/`
- [x] `overall_health` 只由 orchestrator 生成，child 不再声明跨域健康结论
- [x] 严格 harness、bundle sync、repo-health regressions、wrapper smoke、installer regressions 全绿

## P0-0 基线冻结与盘点

- [x] 冻结 `skills/repo-health-orchestrator/scripts/repo_health_catalog.py` 的 15-domain catalog，不在 P0 增删 worker
- [x] 冻结 `skills/repo-health-orchestrator/references/synthesis-policy.md` 的 4 个 cluster 和固定 action ordering
- [x] 盘点 15 个 child 当前 summary schema、输出路径、额外 evidence 路径、wrapper、fixture、renderer、validator
- [x] 列出所有仍使用 flat artifact path 的技能和脚本引用
- [x] 列出所有仍依赖 verdict heuristic 或多键 fallback 的 control-plane 代码和文档

完成指标：

- `repo_health_catalog.py` 在 P0 结束前 domain 数量、domain 顺序、cluster 归属不变
- `synthesis-policy.md` 在 P0 结束前 action ordering 不变
- 已产出一份 15 个 child 的契约差异清单，能明确指出要改哪些 schema、脚本、fixture、文档

## P0-1 统一 Child Summary Envelope

- [x] 为 15 个 child summary schema 统一并强制以下顶层字段：`schema_version`、`skill`、`run_id`、`generated_at`、`repo_root`、`overall_verdict`、`rollup_bucket`、`dependency_status`、`dependency_failures`、`bootstrap_actions`、`severity_counts`、`findings`
- [x] 统一 `rollup_bucket` 枚举为：`blocked`、`red`、`yellow`、`green`、`not-applicable`
- [x] 禁止 child summary 顶层再出现 `overall_health`
- [x] 给 15 个 child 各自新增 `assets/verdict-contract.json`
- [x] 每个 `verdict-contract.json` 只声明两类真相：`overall_verdict` 合法 enum、`overall_verdict -> rollup_bucket` 映射
- [x] 把 `verdict-contract.json` 纳入 `scripts/check_skill_fleet.py --mode strict`
- [x] 为所有 child 补齐或统一 `severity_counts` 和 `findings` 契约，避免 aggregator 再自行猜测

完成指标：

- 15/15 child skill 都有 summary schema 和 `assets/verdict-contract.json`
- 15/15 child summary schema 都要求 `skill` 和 `run_id`
- 15/15 child summary schema 都要求 `overall_verdict` 和 `rollup_bucket`
- strict fleet check 能在字段缺失、enum 不合法、映射不完整时直接失败

## P0-2 重写 Aggregator，删除 Verdict Heuristic

- [x] 重写 `skills/repo-health-orchestrator/scripts/aggregate_repo_health.py`，只读取 child summary 顶层的 `overall_verdict`、`rollup_bucket`、`dependency_status`、`dependency_failures`、`severity_counts`、`skill`、`run_id`
- [x] 删除 `RED_VERDICTS`、`YELLOW_VERDICTS`、`POSITIVE_VERDICTS`
- [x] 删除 `extract_verdict()` 的多键 fallback
- [x] 删除对 `overall_health`、`verdict`、`status`、`audit_mode`、`mode` 的兼容性读取
- [x] 缺字段、错字段、错 `skill`、错 `run_id` 一律记为 `invalid`
- [x] 让 aggregator 只根据 `rollup_bucket`、`dependency_status`、coverage 状态做汇总，不再从 child verdict 字符串反推红黄绿
- [x] 保留 domain-specific 说明文字时，限定为解释层 evidence 注释，不参与机器 bucket 归类
- [x] 同步收口 `verdict-policy.md` 或同类参考文档，删掉“future equivalent red state”这类开放式 heuristic 描述

完成指标：

- `aggregate_repo_health.py` 不再出现 verdict bucket hardcode 常量
- `aggregate_repo_health.py` 不再出现对 child 多个别名字段的 verdict fallback
- orchestrator machine summary 的 `overall_health`、`coverage_status`、`skill_runs[].status` 只来源于统一机器契约

## P0-3 全量路径硬切到 Skill Namespace

- [x] 把 15 个 child 的 `SKILL.md`、schema、scanner、validator、renderer、`run_all.sh`、fixture、smoke test 一次性切到 namespaced 路径
- [x] 统一 child 标准工件路径为：
- [x] `.repo-harness/skills/<skill-id>/summary.json`
- [x] `.repo-harness/skills/<skill-id>/report.md`
- [x] `.repo-harness/skills/<skill-id>/agent-brief.md`
- [x] `.repo-harness/skills/<skill-id>/runtime.json`
- [x] 统一 child 可选额外工件路径为：`.repo-harness/skills/<skill-id>/extra/*`
- [x] 删除所有 dual-read、dual-write、legacy alias、flat file fallback
- [x] 把 `llm-api-freshness-guard` 的额外 evidence 一并迁到 `extra/`
- [x] 明确 `.repo-harness` 根目录只保留 orchestrator 级工件：
- [x] `repo-health-control-plane.json`
- [x] `repo-health-shared-bootstrap.json`
- [x] `repo-health-summary.json`
- [x] `repo-health-evidence.json`
- [x] `repo-health-report.md`
- [x] `repo-health-agent-brief.md`

完成指标：

- `README.md`、orchestrator integration matrix、15 个 child `SKILL.md` 的路径描述全部一致
- child 公开契约中不再出现 root-level flat artifact path
- 额外 evidence 不再直接落到 `.repo-harness/` 根目录
- wrapper smoke 和 fixture regression 都以 namespaced 路径为唯一真相

## P0-4 修正 controlled-cleanup-hardgate 双层契约

- [x] 在 `controlled-cleanup-hardgate` summary schema 中补齐统一 envelope 字段
- [x] 机器层 `overall_verdict` 统一使用 enum：`not-ready`、`partially-ready`、`ready-for-controlled-deletion`、`not-applicable`、`scan-blocked`
- [x] 人类报告层继续显示自然语言 verdict：`not ready`、`partially ready`、`ready for controlled deletion`
- [x] 把机器 enum 和展示文本彻底分离，避免 renderer 和 schema 混用
- [x] 为该 skill 单独补 fixture / regression，覆盖 verdict 枚举、展示文本、rollup bucket 映射

完成指标：

- `controlled-cleanup-hardgate` summary 不再缺 `overall_verdict`
- renderer 生成的人类报告仍然输出带空格的自然语言 verdict
- aggregator 只消费机器 enum 和 `rollup_bucket`

## P0-5 删掉 Fleet 外 Portability 包袱

- [x] 清理 `SKILL.md`、references、wrapper 文案中“repo 外 portable fallback”承诺
- [x] 删除 repo 外执行时的兼容性兜底逻辑，保留仓库内 deterministic helper 即可
- [x] 把 home-local Codex plugin 作为唯一维护目标写清楚
- [x] 保证 root source of truth 与 bundle 同步脚本的约束描述一致

完成指标：

- 文档中不再承诺 child skill 脱离 `pooh-skills` 生态仍要独立可移植
- 代码中不再保留仅为 repo 外 portability 存在的 fallback 分支
- README 与各 skill 文案对仓库定位一致

## P0-6 Control Plane 文档、回归、同步收口

- [x] 更新 `README.md`、orchestrator `SKILL.md`、integration matrix、manual acceptance checklist
- [x] 更新 public/private bundle 同步后生成的所有对应文档和脚本
- [x] 更新 repo-health fixture 数据，使其符合新的 child summary envelope 和 namespaced 路径
- [x] 更新 child wrapper smoke matrix 期望值
- [x] 更新 installer regression 所需的 bundle 元数据或 contract fixture

完成指标：

- 根仓库与 bundle 目录中的同源 skill 文档、schema、脚本保持同步
- control plane 最终帧与 machine summary 一致，不再依赖旧 verdict 猜测
- repo-health regressions 覆盖 invalid、missing、blocked、not-applicable、present 各状态

## P0 退出门禁

- [x] 运行 `python3 scripts/sync_shared_skill_refs.py --write`
- [x] 运行 `python3 scripts/sync_plugin_bundle.py`
- [x] 运行 `python3 scripts/check_skill_fleet.py --mode strict`
- [x] 运行 `python3 scripts/check_repo_plugin.py --repo .`
- [x] 运行 `python3 scripts/run_repo_health_fixture_regressions.py`
- [x] 运行 `python3 scripts/run_child_wrapper_smoke_matrix.py`
- [x] 运行 `python3 scripts/run_control_plane_renderer_regressions.py`
- [x] 运行 `python3 scripts/run_home_local_plugin_installer_regressions.py`
- [x] 运行 `bash scripts/run_skill_fleet_harness.sh`

完成指标：

- 上述命令全部通过
- 一次完整 orchestrator run 能稳定产出当前 run 的 `repo-health-summary.json`、`repo-health-evidence.json`、`repo-health-report.md`、`repo-health-agent-brief.md`
- 每个 child `summary.json` 与 `runtime.json` 的 `run_id` 都和当前 orchestrator run 匹配

## P1 新增 secrets-and-hardcode-audit

- [x] 新建 `skills/secrets-and-hardcode-audit/`
- [x] 定义最小 scope：工作树 secrets、git history secrets、硬编码 credential/key material、ignore discipline
- [x] 选定一个主扫描器，并把 blocked/watch/clean 语义写进机器契约
- [x] 提供 summary schema、`verdict-contract.json`、human report template、agent brief template、runtime dependencies
- [x] 把 skill 接入下一版 fleet catalog，并归入 `engineering-quality-and-security`
- [x] 更新 orchestrator 文档、integration matrix、fixture、bundle sync、installer regression

完成指标：

- [x] 新 skill 不与 `python-ts-security-posture-audit` 的职责重叠
- [x] 新 skill 进入 orchestrator 后 fleet 从 15 变 16
- [x] strict fleet check、repo-health regressions、bundle sync、installer regressions 对新增 skill 全绿

## P2 新增 test-quality-audit

- [x] 新建 `skills/test-quality-audit/`
- [x] 只覆盖高信号测试治理问题：真实 CI gate、空测试/占位断言、skip/xfail/retry 滥用、mock 被测逻辑、failure-path 缺失
- [x] 明确排除 `ts-frontend-regression-audit` 和 `pydantic-ai-temporal-hardgate` 已覆盖的 specialist 责任边界
- [x] 提供 summary schema、`verdict-contract.json`、human report template、agent brief template、runtime dependencies
- [x] 将新 skill 接入 orchestrator catalog、cluster、fixture、bundle sync、installer regression

完成指标：

- [x] 新 skill 不吞并现有 specialist domain
- [x] 新 skill 进入 orchestrator 后 fleet 从 16 变 17
- [x] repo-health summary、evidence、report、brief 都能正确呈现新增 domain

## 明确暂不做

- 不合并 `python-lint-format-audit` 和 `ts-lint-format-audit`
- 不把 `pythonic-ddd-drift-audit` 并进 `module-shape-hardgate`
- 不在 child contract 收紧前引入权重层或 fast mode
- 不新增 `ci-pipeline-governance-audit` 这种边界含混的大桶 skill

## 最终完成定义

- [x] 仓库里不再出现 child flat artifact 的公开契约
- [x] 所有 child summary schema 都强制统一 envelope
- [x] aggregator 中不再存在 verdict hardcode bucket 和多键 fallback
- [x] 一次完整 orchestrator run 能稳定产出当前 run 的 repo-health summary、evidence、report、brief
- [x] plugin bundle sync、strict harness、repo-health regressions、wrapper smoke、installer regressions 全绿
