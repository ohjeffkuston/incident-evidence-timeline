"""Command-line interface for the incident evidence timeline builder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .engine import TimelineInputError, build_timeline


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Incident evidence JSON file")
    parser.add_argument("--output", type=Path, help="Optional report path")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = build_timeline(payload)
    except (OSError, json.JSONDecodeError, TimelineInputError) as exc:
        parser.exit(2, f"error: {exc}\n")

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if report["decision"] == "REVIEW" else 0

