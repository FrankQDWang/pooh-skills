#!/usr/bin/env python3
"""Render repo-health control-plane state into a terminal dashboard."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
ASCII_SPINNER_FRAMES = ("-", "\\", "|", "/")

ANSI_RESET = "\033[0m"
ANSI_CLEAR = "\033[2J\033[H"
ANSI_HIDE_CURSOR = "\033[?25l"
ANSI_SHOW_CURSOR = "\033[?25h"

COLOR_MAP = {
    "border": "\033[38;5;110m",
    "title": "\033[38;5;153m",
    "text": "\033[38;5;255m",
    "muted": "\033[38;5;245m",
    "running": "\033[38;5;117m",
    "complete": "\033[38;5;120m",
    "blocked": "\033[38;5;203m",
    "invalid": "\033[38;5;215m",
    "missing": "\033[38;5;244m",
    "not-applicable": "\033[38;5;183m",
    "watch": "\033[38;5;151m",
    "healthy": "\033[38;5;120m",
    "quiet": "\033[38;5;183m",
}

STAGE_LABELS = {
    "reset-harness": "RESETTING HARNESS",
    "spawning": "SPAWNING SUBAGENTS",
    "running": "RUNNING (Audits Active)",
    "collecting": "COLLECTING ARTIFACTS",
    "aggregating": "AGGREGATING REPORTS",
    "done": "COMPLETE",
}

ASCII_BOX = {
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "h": "-",
    "v": "|",
}

UNICODE_BOX = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",
    "h": "─",
    "v": "│",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render repo-health control-plane state.")
    parser.add_argument("--state", required=True, help="Path to repo-health-control-plane.json")
    parser.add_argument("--width", type=int, default=None, help="Optional terminal width override")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--no-clear", action="store_true", help="Disable clear-screen redraw")
    parser.add_argument("--final", action="store_true", help="Restore cursor after drawing the frame")
    return parser.parse_args()


def load_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def terminal_width(explicit: int | None) -> int:
    if explicit is not None:
        return max(88, explicit)
    return max(88, shutil.get_terminal_size(fallback=(144, 40)).columns)


def ansi_enabled(args: argparse.Namespace) -> bool:
    if args.no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return sys.stdout.isatty()


def unicode_enabled(args: argparse.Namespace) -> bool:
    term = os.environ.get("TERM", "")
    return term.lower() != "dumb"


def colorize(text: str, role: str, use_ansi: bool) -> str:
    if not use_ansi:
        return text
    color = COLOR_MAP.get(role)
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


def visible_len(text: str) -> int:
    length = 0
    escaped = False
    for char in text:
        if char == "\033":
            escaped = True
            continue
        if escaped:
            if char == "m":
                escaped = False
            continue
        length += 1
    return length


def pad_right(text: str, width: int) -> str:
    padding = max(0, width - visible_len(text))
    return text + (" " * padding)


def truncate_plain(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def progress_bar(ratio: float, width: int, use_ansi: bool, unicode_mode: bool) -> str:
    ratio = max(0.0, min(1.0, ratio))
    width = max(10, width)
    filled = int(round(width * ratio))
    if unicode_mode:
        fill = "█" * filled
        empty = "·" * max(0, width - filled)
    else:
        fill = "#" * filled
        empty = "." * max(0, width - filled)
    fill = colorize(fill, "running", use_ansi) if fill else fill
    empty = colorize(empty, "muted", use_ansi) if empty else empty
    return fill + empty


def status_role(runtime_status: str) -> str:
    return {
        "waiting": "muted",
        "preflight": "running",
        "bootstrapping": "watch",
        "running": "running",
        "complete": "complete",
        "blocked": "blocked",
        "invalid": "invalid",
        "missing": "missing",
        "not-applicable": "not-applicable",
    }.get(runtime_status, "text")


def tone_role(state_tone: str) -> str:
    if state_tone in {"running", "watch", "healthy", "quiet", "blocked"}:
        return state_tone
    return "text"


def status_icon(runtime_status: str, unicode_mode: bool) -> str:
    if runtime_status == "running":
        frames = SPINNER_FRAMES if unicode_mode else ASCII_SPINNER_FRAMES
        index = int(datetime.now().timestamp() * 4) % len(frames)
        return frames[index]
    if runtime_status == "preflight":
        return "◌" if unicode_mode else ".."
    if runtime_status == "bootstrapping":
        return "⇡" if unicode_mode else "++"
    if unicode_mode:
        return {
            "waiting": "⏳",
            "complete": "✓",
            "blocked": "⛔",
            "invalid": "⚠",
            "missing": "✕",
            "not-applicable": "∅",
        }.get(runtime_status, "•")
    return {
        "waiting": "...",
        "complete": "OK",
        "blocked": "!!",
        "invalid": "!!",
        "missing": "XX",
        "not-applicable": "--",
    }.get(runtime_status, "..")


def make_box(title: str, lines: list[str], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    box = UNICODE_BOX if unicode_mode else ASCII_BOX
    inner_width = width - 2
    title_text = f" {title} "
    title_plain = truncate_plain(title_text, inner_width)
    remaining = max(0, inner_width - len(title_plain))
    left = remaining // 2
    right = remaining - left
    border_role = "border"
    top = (
        colorize(box["tl"], border_role, use_ansi)
        + colorize(box["h"] * left, border_role, use_ansi)
        + colorize(title_plain, "title", use_ansi)
        + colorize(box["h"] * right, border_role, use_ansi)
        + colorize(box["tr"], border_role, use_ansi)
    )
    rendered = [top]
    for line in lines:
        rendered.append(
            colorize(box["v"], border_role, use_ansi)
            + pad_right(line, inner_width)
            + colorize(box["v"], border_role, use_ansi)
        )
    rendered.append(
        colorize(box["bl"], border_role, use_ansi)
        + colorize(box["h"] * inner_width, border_role, use_ansi)
        + colorize(box["br"], border_role, use_ansi)
    )
    return rendered


def format_worker(worker: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    inner_width = width - 2
    runtime_status = str(worker.get("runtime_status") or "waiting")
    icon = status_icon(runtime_status, unicode_mode)
    role = status_role(runtime_status)
    title = truncate_plain(f"[ {worker.get('index')} ] SKILL: {worker.get('title')}", inner_width)
    model_line = truncate_plain(f"Model: {worker.get('model_label') or 'Inherited from session'}", inner_width)
    status_line = truncate_plain(
        f"Status: {icon} {worker.get('status_label') or runtime_status.upper()}",
        inner_width,
    )
    detail = str(worker.get("detail") or worker.get("notes") or "")
    detail_line = truncate_plain(f"Detail: {detail or 'No detail'}", inner_width)
    output_label = truncate_plain(
        f"Output: {worker.get('output_label') or 'No artifact'}",
        inner_width,
    )
    notes = str(worker.get("child_verdict") or "")
    if not notes and worker.get("top_categories"):
        notes = ", ".join(worker.get("top_categories") or [])
    notes_line = truncate_plain(f"Notes: {notes or '-'}", inner_width)
    colorized_status = status_line.replace(
        f"{icon} {worker.get('status_label') or runtime_status.upper()}",
        colorize(f"{icon} {worker.get('status_label') or runtime_status.upper()}", role, use_ansi),
    )
    lines = [
        colorize(title, "text", use_ansi),
        colorize(model_line, "muted", use_ansi),
        colorized_status,
        colorize(output_label, "text", use_ansi),
        colorize(detail_line, "muted", use_ansi),
        colorize(notes_line, "muted", use_ansi),
    ]
    return make_box(worker.get("title") or "Worker", lines, width, use_ansi, unicode_mode)


def render_header(state: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    context = state.get("context") or "repo-health-orchestrator"
    run_id = str(state.get("run_id") or "-")
    header = truncate_plain(
        f"ORCHESTRATOR v1.0 | CONTROL PLANE | Run: {run_id} | Context: {context}",
        width,
    )
    divider_char = "═" if unicode_mode else "="
    divider = colorize(divider_char * max(0, width - visible_len(header) - 1), "border", use_ansi)
    return [colorize(header, "title", use_ansi) + " " + divider]


def render_overall_box(state: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    overall = state.get("overall") or {}
    inner_width = width - 2
    bar_width = max(18, inner_width - 28)
    ratio = float(overall.get("progress_ratio", 0.0) or 0.0)
    progress_text = f"{int(round(ratio * 100)):>3}%"
    bar = progress_bar(ratio, bar_width, use_ansi, unicode_mode)
    state_line = f"State: {overall.get('state_label') or STAGE_LABELS.get(overall.get('stage'), 'RUNNING')}"
    summary_line = str(overall.get("summary_line") or "")
    stage = str(overall.get("stage") or "")
    if summary_line:
        summary_line = truncate_plain(f"Summary: {summary_line}", inner_width)
    lines = [
        colorize(
            f"Overall Progress: [{bar}] {progress_text}",
            "text",
            use_ansi,
        ),
        colorize(
            truncate_plain(state_line, inner_width),
            tone_role(str(overall.get("state_tone") or "running")),
            use_ansi,
        ),
        colorize(
            truncate_plain(f"Stage: {stage}", inner_width),
            "muted",
            use_ansi,
        ),
        colorize(
            truncate_plain(f"Model: {overall.get('model_label') or 'Inherited from session'}", inner_width),
            "text",
            use_ansi,
        ),
        colorize(
            truncate_plain(f"run_id: {state.get('run_id') or '-'}", inner_width),
            "text",
            use_ansi,
        ),
        colorize(
            truncate_plain(f"reasoning_effort: {overall.get('reasoning_effort') or 'Inherited'}", inner_width),
            "text",
            use_ansi,
        ),
        colorize(summary_line or "Summary: awaiting final aggregate", "muted", use_ansi),
    ]
    return make_box("MAIN ORCHESTRATOR", lines, width, use_ansi, unicode_mode)


def render_action_box(state: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    inner_width = width - 2
    overall = state.get("overall") or {}
    lines = [
        colorize(
            truncate_plain(f"overall_health: {overall.get('overall_health') or '-'}", inner_width),
            "text",
            use_ansi,
        ),
        colorize(
            truncate_plain(f"coverage_status: {overall.get('coverage_status') or '-'}", inner_width),
            "text",
            use_ansi,
        ),
    ]
    actions = [str(item) for item in state.get("top_actions") or []]
    if actions:
        for index, action in enumerate(actions[:3], start=1):
            lines.append(colorize(truncate_plain(f"{index}. {action}", inner_width), "muted", use_ansi))
    else:
        lines.append(colorize("1. Awaiting aggregated top actions", "muted", use_ansi))
    missing = ", ".join(state.get("missing_skills") or [])
    invalid = ", ".join(state.get("invalid_summaries") or [])
    lines.append(colorize(truncate_plain(f"Missing: {missing or '-'}", inner_width), "muted", use_ansi))
    lines.append(colorize(truncate_plain(f"Invalid: {invalid or '-'}", inner_width), "muted", use_ansi))
    return make_box("ACTION QUEUE", lines, width, use_ansi, unicode_mode)


def join_columns(left: list[str], right: list[str], gap: int) -> list[str]:
    height = max(len(left), len(right))
    left_pad = left + [" " * visible_len(left[0])] * (height - len(left))
    right_pad = right + [" " * visible_len(right[0])] * (height - len(right))
    return [left_pad[index] + (" " * gap) + right_pad[index] for index in range(height)]


def render_workers(state: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> list[str]:
    workers = state.get("workers") or []
    section_title = colorize("CHILD SUBAGENT SKILLS (Workers)", "title", use_ansi)
    lines = [section_title]
    gap = 3
    if width >= 132:
        panel_width = (width - gap) // 2
        for start in range(0, len(workers), 2):
            left_panel = format_worker(workers[start], panel_width, use_ansi, unicode_mode)
            if start + 1 < len(workers):
                right_panel = format_worker(workers[start + 1], panel_width, use_ansi, unicode_mode)
                lines.extend(join_columns(left_panel, right_panel, gap))
            else:
                lines.extend(left_panel)
            lines.append("")
    else:
        panel_width = width
        for worker in workers:
            lines.extend(format_worker(worker, panel_width, use_ansi, unicode_mode))
            lines.append("")
    return lines[:-1] if lines and lines[-1] == "" else lines


def build_frame(state: dict[str, Any], width: int, use_ansi: bool, unicode_mode: bool) -> str:
    sections: list[str] = []
    sections.extend(render_header(state, width, use_ansi, unicode_mode))
    sections.append("")
    sections.extend(render_overall_box(state, width, use_ansi, unicode_mode))
    sections.append("")
    sections.extend(render_workers(state, width, use_ansi, unicode_mode))
    sections.append("")
    sections.extend(render_action_box(state, width, use_ansi, unicode_mode))
    return "\n".join(sections)


def main() -> int:
    args = parse_args()
    state = load_state(Path(args.state).resolve())
    use_ansi = ansi_enabled(args)
    unicode_mode = unicode_enabled(args)
    width = terminal_width(args.width)
    frame = build_frame(state, width, use_ansi, unicode_mode)

    prefix = ""
    suffix = ""
    if not args.no_clear and sys.stdout.isatty():
        prefix += ANSI_HIDE_CURSOR + ANSI_CLEAR
        if args.final:
            suffix = ANSI_SHOW_CURSOR

    sys.stdout.write(prefix)
    sys.stdout.write(frame)
    sys.stdout.write("\n")
    if suffix:
        sys.stdout.write(suffix)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
