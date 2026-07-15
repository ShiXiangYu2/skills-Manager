#!/usr/bin/env python3
"""Tiny keyword search over packaged course references."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Search course reference files.")
    parser.add_argument("query", help="Keyword to search for.")
    parser.add_argument("--references-dir", default="../references", help="Reference directory relative to this script.")
    args = parser.parse_args()

    base = (Path(__file__).resolve().parent / args.references_dir).resolve()
    query = args.query.lower()
    matches = []

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if query in line.lower():
                matches.append((path.relative_to(base), line_no, line.strip()))

    for rel_path, line_no, line in matches[:80]:
        print(f"{rel_path}:{line_no}: {line}")

    if len(matches) > 80:
        print(f"... {len(matches) - 80} more matches")


if __name__ == "__main__":
    main()
