#!/usr/bin/env python3
"""Structural validator for contract-hardgate summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_TOP = {"repo_profile", "overall_verdict", "gate_states", "findings"}
REQUIRED_GATE = {"gate", "state", "severity", "confidence", "summary"}
REQUIRED_FINDING = {
    "id",
    "domain",
    "gate",
    "severity",
    "confidence",
    "current_state",
    "target_state",
    "title",
    "evidence_summary",
    "decision",
    "change_shape",
    "validation",
    "merge_gate",
    "autofix_allowed",
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    missing = REQUIRED_TOP - set(data)
    if missing:
        return fail(f"Missing top-level keys: {sorted(missing)}")

    if not isinstance(data["gate_states"], list):
        return fail("gate_states must be a list")
    for idx, gate in enumerate(data["gate_states"]):
        missing_gate = REQUIRED_GATE - set(gate)
        if missing_gate:
            return fail(f"gate_states[{idx}] missing keys: {sorted(missing_gate)}")

    if not isinstance(data["findings"], list):
        return fail("findings must be a list")
    for idx, finding in enumerate(data["findings"]):
        missing_finding = REQUIRED_FINDING - set(finding)
        if missing_finding:
            return fail(f"findings[{idx}] missing keys: {sorted(missing_finding)}")

    print(f"Validated {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
