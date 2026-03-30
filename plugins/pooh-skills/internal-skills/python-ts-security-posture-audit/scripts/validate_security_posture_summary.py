#!/usr/bin/env python3
"""Validate the machine-readable summary produced by python-ts-security-posture-audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUNTIME_BIN = Path(__file__).resolve().parents[2] / ".pooh-runtime" / "bin"
if str(RUNTIME_BIN) not in sys.path:
    sys.path.insert(0, str(RUNTIME_BIN))

from standard_audit_utils import validate_standard_summary  # noqa: E402

CATEGORY_IDS = {
    "python-known-vulns",
    "ts-known-vulns",
    "python-static-security",
    "lockfile-install-discipline",
    "gate-and-ignore-governance",
}
COVERAGE_KEYS = {
    "files_scanned",
    "python_surface_files",
    "ts_surface_files",
    "lockfiles_present",
    "workflow_security_entries",
    "ignore_entries",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate security-posture summary JSON")
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    ok, message = validate_standard_summary(
        Path(args.summary),
        skill_name="python-ts-security-posture-audit",
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
