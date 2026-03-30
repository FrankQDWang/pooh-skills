#!/usr/bin/env python3
"""Check local Markdown and simple HTML links inside a repository.

Only local filesystem references are checked. Network URLs are ignored.
"""
from __future__ import annotations

import argparse
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

MARKDOWN_EXTENSIONS = {".md", ".mdx"}
HTML_EXTENSIONS = {".html", ".htm"}

MD_LINK_RE = re.compile(r"!?(?P<all>\[(?P<label>[^\]]*)\]\((?P<target>[^)]+)\))")
HTML_LINK_RE = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local documentation links.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    return parser.parse_args(argv)


def iter_doc_files(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            suffix = path.suffix.lower()
            if suffix in MARKDOWN_EXTENSIONS or suffix in HTML_EXTENSIONS:
                yield path


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


def github_slug(heading: str) -> str:
    heading = heading.strip().lower()
    heading = re.sub(r"[\s]+", "-", heading)
    heading = re.sub(r"[^\w\-\u4e00-\u9fff]", "", heading)
    heading = re.sub(r"-+", "-", heading).strip("-")
    return heading


def anchors_for_markdown(text: str) -> set[str]:
    anchors = set()
    for _, heading in HEADING_RE.findall(text):
        anchors.add(github_slug(heading))
    return anchors


def resolve_target(source: Path, target: str) -> tuple[Path | None, str | None]:
    target = target.strip()
    if target.startswith(("http://", "https://", "mailto:", "tel:")):
        return None, None
    if target.startswith("#"):
        return source, target[1:]
    path_part, _, anchor = target.partition("#")
    path_part = path_part.split("?", 1)[0]
    if not path_part:
        return source, anchor or None
    resolved = (source.parent / path_part).resolve()
    return resolved, anchor or None


def line_number_for(text: str, needle: str) -> int | None:
    idx = text.find(needle)
    if idx < 0:
        return None
    return text.count("\n", 0, idx) + 1


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    out_path = Path(args.out).resolve()

    broken: list[dict[str, object]] = []
    checked = 0

    for path in iter_doc_files(repo):
        text = read_text(path)
        if text is None:
            continue
        suffix = path.suffix.lower()
        rel_source = path.relative_to(repo).as_posix()
        matches = []
        if suffix in MARKDOWN_EXTENSIONS:
            matches.extend(m.group("target") for m in MD_LINK_RE.finditer(text))
        if suffix in HTML_EXTENSIONS:
            matches.extend(m.group(1) for m in HTML_LINK_RE.finditer(text))

        for target in matches:
            checked += 1
            resolved, anchor = resolve_target(path, target)
            if resolved is None:
                continue

            if resolved == path:
                target_exists = True
            else:
                target_exists = resolved.exists()
                if not target_exists and resolved.suffix == "":
                    for fallback in [resolved / "index.md", resolved / "README.md"]:
                        if fallback.exists():
                            resolved = fallback
                            target_exists = True
                            break
            if not target_exists:
                broken.append({
                    "source": rel_source,
                    "target": target,
                    "line": line_number_for(text, target),
                    "reason": "missing-path",
                })
                continue

            if anchor:
                target_text = read_text(resolved)
                if target_text is None:
                    broken.append({
                        "source": rel_source,
                        "target": target,
                        "line": line_number_for(text, target),
                        "reason": "anchor-target-unreadable",
                    })
                    continue
                anchors = anchors_for_markdown(target_text)
                if anchor not in anchors:
                    broken.append({
                        "source": rel_source,
                        "target": target,
                        "line": line_number_for(text, target),
                        "reason": "missing-anchor",
                    })

    out = {
        "repo_root": repo.as_posix(),
        "checked_links": checked,
        "broken_count": len(broken),
        "broken": broken,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if broken:
        print(f"found {len(broken)} broken local doc links", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
