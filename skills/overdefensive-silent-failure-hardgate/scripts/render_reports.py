#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


STRONG_CATEGORIES = {
    "exception-swallow",
    "skip-on-error",
    "cause-chain-loss",
    "async-exception-leak",
    "type-escape-hatch",
    "lint-escape-hatch",
    "unsafe-optional-chain",
}
SOFTENING_CATEGORIES = {
    "optionality-leak",
    "silent-default",
    "truthiness-fallback",
    "type-escape-hatch",
    "lint-escape-hatch",
    "unsafe-optional-chain",
}
ASYNC_CATEGORIES = {"async-exception-leak", "exception-swallow", "skip-on-error"}


PLAIN_LANGUAGE = {
    "exception-swallow": "错误发生了，但代码把它吞掉了，系统表面看着没事，实际上只是把问题藏到了后面。",
    "skip-on-error": "代码遇到失败后悄悄跳过这一步，结果会少数据、脏数据，或者状态不完整。",
    "cause-chain-loss": "后来看到的错误不再保留最初原因，排查会更慢、更容易误判。",
    "async-exception-leak": "后台任务失败时不会立刻暴露出来，主流程继续跑，团队很容易误以为一切正常。",
    "optionality-leak": "本来应该确定存在的数据，被改成了“也许有也许没有”，下游只能到处加判空。",
    "silent-default": "缺失或失败被替换成默认值，看起来流程继续了，其实数据已经不可信。",
    "truthiness-fallback": "像 0、空字符串这种合法值，可能被误当成“缺失”而被覆盖。",
    "unsafe-optional-chain": "代码嘴上说“这个值可能没有”，后面又强行当成一定有，这是自相矛盾的漏洞。",
    "type-escape-hatch": "类型系统发出的红线被强行压下去了，问题只是从编译期推迟到了运行期。",
    "lint-escape-hatch": "检查器在提醒你有风险，但代码选择让它闭嘴，而不是把风险拿掉。",
    "useless-catch-theater": "这里看起来像有错误处理，实际上只是摆造型，没有真正改变行为或提升可观测性。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render human report and agent brief from a summary JSON")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--brief", required=True)
    return parser.parse_args()


def load_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def top_findings(summary: dict, categories: set[str], limit: int = 5) -> list[dict]:
    findings = [f for f in summary["findings"] if f["category"] in categories]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), order.get(f["confidence"], 9), f["path"], f["line"]))
    return findings[:limit]


def ordered_actions(summary: dict) -> list[str]:
    category_counts = Counter(f["category"] for f in summary["findings"])
    actions: list[str] = []

    if category_counts["exception-swallow"] or category_counts["skip-on-error"]:
        actions.append("Kill silent swallow paths first: replace empty catch / pass / continue with explicit handling or fail-loud behavior.")
    if category_counts["async-exception-leak"]:
        actions.append("Bring async work back on-camera: await, gather, or explicitly observe background tasks and promises.")
    if category_counts["type-escape-hatch"] or category_counts["lint-escape-hatch"]:
        actions.append("Stop silencing the checker: remove `as any`, `type: ignore`, ts-comments, and broad disables on changed files.")
    if category_counts["silent-default"] or category_counts["truthiness-fallback"] or category_counts["optionality-leak"]:
        actions.append("Restore contracts before spreading maybe-values: move validation to boundaries and make fallbacks explicit.")
    if not actions:
        actions.append("Keep the repo fail-loud: do not reintroduce silent defaults, empty catch blocks, or off-camera async work.")
    while len(actions) < 3:
        actions.append("Treat any future fallback as a real design decision: if it stays, it must be explicit, observable, and documented.")
    return actions[:3]


def write_report(summary: dict, out_path: Path) -> None:
    strong = top_findings(summary, STRONG_CATEGORIES, limit=5)
    soft = top_findings(summary, SOFTENING_CATEGORIES, limit=8)
    async_findings = top_findings(summary, ASYNC_CATEGORIES, limit=5)
    actions = ordered_actions(summary)

    lines: list[str] = []
    lines.append("# Overdefensive Silent Failure Report")
    lines.append("")
    lines.append("## 1. Executive summary")
    lines.append(f"- Overall verdict: `{summary['overall_verdict']}`")
    lines.append(f"- One-line diagnosis: {summary['summary_line']}")
    lines.append(f"- Files scanned: `{summary['coverage']['files_scanned']}` "
                 f"(Python `{summary['coverage']['python_files']}`, TS `{summary['coverage']['ts_files']}`, JS `{summary['coverage']['js_files']}`)")
    if summary.get("scan_blockers"):
        lines.append("- Scan blockers:")
        for blocker in summary["scan_blockers"][:5]:
            lines.append(f"  - `{blocker}`")
    lines.append("")
    lines.append("## 2. Where the repo is hiding failure instead of handling it")
    if not strong:
        lines.append("The bundled scan did not find strong high-confidence silent-failure syntax. That is good, but it is not proof of perfect handling.")
    for finding in strong:
        lines.append("")
        lines.append(f"### {finding['title']}")
        lines.append(f"- Category: `{finding['category']}`")
        lines.append(f"- Severity: `{finding['severity']}`")
        lines.append(f"- Confidence: `{finding['confidence']}`")
        lines.append(f"- Evidence: `{finding['path']}:{finding['line']}`")
        lines.append("")
        lines.append("**是什么**")
        lines.append(f"这条路径出现了 `{finding['category']}`：`{finding['evidence'][0]}`")
        lines.append("")
        lines.append("**为什么重要**")
        lines.append(PLAIN_LANGUAGE.get(finding["category"], "这会让真正的失败更晚暴露、更难追踪。"))
        lines.append("")
        lines.append("**建议做什么**")
        lines.append(finding["recommendation"])
        lines.append("")
        lines.append("**给非程序员的人话解释**")
        lines.append(PLAIN_LANGUAGE.get(finding["category"], "系统把原本该明确告诉你的问题，悄悄藏起来了。"))
    lines.append("")
    lines.append("## 3. Where contracts were softened into maybe-values and defaults")
    if not soft:
        lines.append("No obvious bundled-scan evidence of maybe-value / default-value softening was found.")
    else:
        for finding in soft[:8]:
            lines.append(f"- `{finding['category']}` at `{finding['path']}:{finding['line']}` — {finding['evidence'][0]}")
    lines.append("")
    lines.append("## 4. Where async work can fail off-camera")
    if not async_findings:
        lines.append("No strong bundled-scan evidence of off-camera async failure was found.")
    else:
        for finding in async_findings:
            lines.append(f"- `{finding['path']}:{finding['line']}` — {finding['title']}")
    lines.append("")
    lines.append("## 5. What should fail loudly now")
    if strong:
        for finding in strong[:5]:
            lines.append(f"- `{finding['path']}:{finding['line']}` should stop hiding `{finding['category']}`.")
    else:
        lines.append("- Keep current explicit handling paths honest; do not add silent swallow code on changed files.")
    lines.append("")
    lines.append("## 6. What may degrade only if it becomes explicit")
    lines.append("- If a fallback must stay, it needs a named degraded state, logs / metrics, and a caller-visible contract.")
    lines.append("- `return None`, empty catch blocks, or hidden defaults do not count as graceful degradation.")
    lines.append("- Trust-boundary validation is fine. Quietly softening internal invariants is not.")
    lines.append("")
    lines.append("## 7. Ordered action plan")
    lines.append("### 现在")
    lines.append(f"- {actions[0]}")
    lines.append("### 下一步")
    lines.append(f"- {actions[1]}")
    lines.append("### 之后")
    lines.append(f"- {actions[2]}")
    lines.append("")
    lines.append("## 8. What this repo is teaching AI to do wrong")
    lines.append("- \"If the checker complains, use `ignore` instead of narrowing.\"")
    lines.append("- \"If a required value is missing, make it optional and move on.\"")
    lines.append("- \"If async work fails, let it fail somewhere else so the happy path stays green.\"")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dump_yaml_like(findings: list[dict]) -> str:
    lines: list[str] = []
    for finding in findings:
        decision = {
            "exception-swallow": "restore-contract",
            "skip-on-error": "restore-contract",
            "cause-chain-loss": "preserve-cause",
            "async-exception-leak": "await-or-collect",
            "optionality-leak": "tighten-type",
            "silent-default": "make-degrade-explicit",
            "truthiness-fallback": "restore-contract",
            "unsafe-optional-chain": "tighten-type",
            "type-escape-hatch": "tighten-type",
            "lint-escape-hatch": "delete-theater",
            "useless-catch-theater": "delete-theater",
        }.get(finding["category"], "defer")
        change_shape = {
            "exception-swallow": "replace empty swallow with typed handling or explicit degraded state; otherwise let the error surface",
            "skip-on-error": "stop dropping work silently; collect failures or block the batch",
            "cause-chain-loss": "re-raise with preserved cause so the stack keeps the root failure",
            "async-exception-leak": "await, gather, or attach explicit observation to background work",
            "optionality-leak": "keep maybe-values at the boundary and restore a strict internal contract",
            "silent-default": "replace hidden fallback with explicit validation or explicit degraded state",
            "truthiness-fallback": "use nullish / explicit checks instead of blanket truthiness fallback",
            "unsafe-optional-chain": "narrow earlier and remove the optional-chain plus non-null contradiction",
            "type-escape-hatch": "remove assertion / ignore and replace it with real narrowing or schema validation",
            "lint-escape-hatch": "delete the suppression or quarantine the compatibility edge explicitly",
            "useless-catch-theater": "remove the fake handler and keep only behavior-changing error handling",
        }.get(finding["category"], "inspect manually")
        lines.append(f"- id: {finding['id']}")
        lines.append(f"  category: {finding['category']}")
        lines.append(f"  severity: {finding['severity']}")
        lines.append(f"  confidence: {finding['confidence']}")
        lines.append(f"  language: {finding['language']}")
        lines.append(f"  title: {finding['title']}")
        lines.append(f"  path: {finding['path']}")
        lines.append(f"  line: {finding['line']}")
        lines.append(f"  evidence_summary: {json.dumps(finding['evidence'][0], ensure_ascii=False)}")
        lines.append(f"  decision: {decision}")
        lines.append(f"  change_shape: {json.dumps(change_shape, ensure_ascii=False)}")
        lines.append(f"  validation: {json.dumps('rerun bundled scan; verify the path now fails loudly or degrades explicitly', ensure_ascii=False)}")
        lines.append(f"  merge_gate: {finding['merge_gate']}")
        lines.append(f"  autofix_allowed: {'true' if finding['category'] not in {'optionality-leak'} else 'false'}")
        note = finding.get("notes") or ""
        lines.append(f"  notes: {json.dumps(note, ensure_ascii=False)}")
    return "\n".join(lines)


def write_brief(summary: dict, out_path: Path) -> None:
    actions = ordered_actions(summary)
    findings = summary["findings"][:12]
    lines: list[str] = []
    lines.append("# Overdefensive Silent Failure Agent Brief")
    lines.append("")
    lines.append("Use short, decision-level language.")
    lines.append("")
    lines.append("## Context")
    lines.append(f"- overall_verdict: `{summary['overall_verdict']}`")
    lines.append(f"- repo_root: `{summary['repo_root']}`")
    lines.append("")
    lines.append("## Ordered actions")
    for idx, action in enumerate(actions, start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    lines.append("## Findings")
    lines.append("```yaml")
    if findings:
        lines.append(dump_yaml_like(findings))
    else:
        lines.append("- id: osf-000")
        lines.append("  category: healthy-baseline")
        lines.append("  severity: low")
        lines.append("  confidence: medium")
        lines.append("  language: mixed")
        lines.append("  title: No strong bundled-scan evidence of silent failure was found")
        lines.append("  path: .")
        lines.append("  line: 1")
        lines.append("  evidence_summary: \"keep changed files fail-loud; do not add empty catch, silent defaults, or checker suppressions\"")
        lines.append("  decision: defer")
        lines.append("  change_shape: \"preserve current explicit handling posture\"")
        lines.append("  validation: \"rerun bundled scan after significant changes\"")
        lines.append("  merge_gate: warn-only")
        lines.append("  autofix_allowed: false")
        lines.append("  notes: \"bundled scan is heuristic, not a formal proof\"")
    lines.append("```")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = load_summary(Path(args.summary))
    write_report(summary, Path(args.report))
    write_brief(summary, Path(args.brief))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
