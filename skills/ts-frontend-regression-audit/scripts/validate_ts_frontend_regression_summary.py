#!/usr/bin/env python3
"""Validate the machine-readable summary produced by ts-frontend-regression-audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import validate_standard_summary  # noqa: E402

CATEGORY_IDS = {
    "browser-fidelity",
    "request-boundary-mocking",
    "accessibility-automation",
    "visual-regression",
    "ci-artifacts-and-stability",
}
COVERAGE_KEYS = {
    "files_scanned",
    "frontend_files",
    "browser_test_entries",
    "mock_entries",
    "visual_entries",
    "workflow_entries",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ts-frontend-regression summary JSON")
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    ok, message = validate_standard_summary(
        Path(args.summary),
        skill_name="ts-frontend-regression-audit",
        category_ids=CATEGORY_IDS,
        coverage_keys=COVERAGE_KEYS,
    )
    if not ok:
        print(f"Validation failed: {message}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
