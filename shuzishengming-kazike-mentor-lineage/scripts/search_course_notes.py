#!/usr/bin/env python3
"""Keyword search over packaged course references and evidence cards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def card_text(card: dict) -> str:
    return " ".join(str(card.get(key) or "") for key in ["card_type", "title", "summary", "quote", "source_ref", "chunk_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Search course reference files.")
    parser.add_argument("query", help="Keyword to search for.")
    parser.add_argument("--references-dir", default="../references", help="Reference directory relative to this script.")
    parser.add_argument("--type", dest="card_type", help="Filter evidence cards by card_type, e.g. method, diagnostic, rubric.")
    args = parser.parse_args()

    base = (Path(__file__).resolve().parent / args.references_dir).resolve()
    query = args.query.lower()
    matches = []

    cards = read_jsonl(base / "text_distillation" / "evidence_cards.jsonl")
    for card in cards:
        if args.card_type and card.get("card_type") != args.card_type:
            continue
        text = card_text(card)
        if query in text.lower():
            source = card.get("source_ref", "")
            chunk = card.get("chunk_id", "")
            title = card.get("title", "")
            summary = card.get("quote") or card.get("summary", "")
            print(f"card:{card.get('card_id', '')}:{card.get('card_type', '')}:{source}:{chunk}: {title} {summary}".strip())

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "evidence_cards.jsonl" and args.card_type:
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
