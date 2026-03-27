#!/usr/bin/env python3
"""Search a repository for forbidden old references using a JSON pattern file."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from typing import Sequence

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", "target",
    "coverage", ".next", ".cache", ".repo-harness", "vendor", "__pycache__",
}

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".go", ".rb", ".php", ".cs", ".cpp",
    ".cc", ".cxx", ".c", ".h", ".hpp", ".scala", ".rs", ".swift",
    ".md", ".mdx", ".rst", ".txt", ".adoc", ".yaml", ".yml", ".json",
    ".toml", ".ini", ".cfg", ".properties", ".gradle", ".sh", ".bash",
    ".zsh", ".sql",
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check for forbidden old references.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--pattern-file", required=True, help="JSON file with patterns.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    return parser.parse_args(argv)


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def iter_files(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            if path.suffix.lower() in TEXT_EXTENSIONS:
                yield path


def matches_globs(rel: str, globs: list[str] | None) -> bool:
    if not globs:
        return True
    return any(fnmatch.fnmatch(rel, pattern) for pattern in globs)


def excluded_by_globs(rel: str, globs: list[str] | None) -> bool:
    if not globs:
        return False
    return any(fnmatch.fnmatch(rel, pattern) for pattern in globs)


def line_number_for(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def preview_for_line(line: str, needle: str) -> str:
    line = line.strip()
    if len(line) <= 160:
        return line
    pos = line.find(needle)
    if pos < 0:
        return line[:157] + "..."
    start = max(0, pos - 60)
    end = min(len(line), pos + len(needle) + 60)
    snippet = line[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(line):
        snippet = snippet + "..."
    return snippet


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    pattern_file = Path(args.pattern_file).resolve()
    out_path = Path(args.out).resolve()

    try:
        config = json.loads(pattern_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"error: could not read pattern file: {exc}", file=sys.stderr)
        return 2

    patterns = config.get("patterns", [])
    compiled = []
    for item in patterns:
        mode = item.get("mode", "literal")
        pattern = item.get("pattern")
        if not pattern:
            continue
        flags = 0 if item.get("case_sensitive", True) else re.IGNORECASE
        regex = re.compile(pattern if mode == "regex" else re.escape(pattern), flags)
        compiled.append((item, regex))

    hits = []
    checked = 0
    for path in iter_files(repo):
        rel = path.relative_to(repo).as_posix()
        text = read_text(path)
        if text is None:
            continue
        checked += 1
        lines = text.splitlines()
        for item, regex in compiled:
            include_globs = item.get("paths")
            exclude_globs = item.get("exclude_paths")
            if not matches_globs(rel, include_globs):
                continue
            if excluded_by_globs(rel, exclude_globs):
                continue
            for match in regex.finditer(text):
                line_no = line_number_for(text, match.start())
                line_text = lines[line_no - 1] if lines else ""
                hits.append({
                    "pattern_id": item.get("id", "unnamed"),
                    "path": rel,
                    "line": line_no,
                    "match": match.group(0),
                    "preview": preview_for_line(line_text, match.group(0)),
                })

    payload = {
        "repo_root": repo.as_posix(),
        "pattern_file": pattern_file.as_posix(),
        "checked_files": checked,
        "hit_count": len(hits),
        "hits": hits,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if hits:
        print(f"forbidden references found: {len(hits)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
