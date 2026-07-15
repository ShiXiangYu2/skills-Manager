#!/usr/bin/env python3
"""Collect pure-text course sources and write stable chunk artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "keyframe_candidates",
    "keyframe_selection",
    "keyframes_model_selected",
    "text_distillation",
    "text_sources",
    "transcripts",
    "analysis",
}


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(*parts: object, length: int = 32) -> str:
    raw = "\0".join(str(part) for part in parts)
    return sha256_hex(raw)[:length]


def is_text_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_text_files(paths: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for value in paths:
        path = Path(value).expanduser().resolve()
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(item for item in path.rglob("*") if is_text_file(item))
        else:
            raise FileNotFoundError(str(path))
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate in seen or not is_text_file(candidate) or should_skip(candidate):
                continue
            files.append(candidate)
            seen.add(candidate)
    return files


def relative_path(path: Path, base_dir: Path | None) -> str:
    if base_dir:
        try:
            return path.resolve().relative_to(base_dir.resolve()).as_posix()
        except ValueError:
            pass
    return path.name


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")


def collect_text_sources(paths: list[str | Path], base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    base = Path(base_dir).expanduser().resolve() if base_dir else None
    sources = []
    for path in iter_text_files(paths):
        text = read_text_file(path)
        if not text.strip():
            continue
        rel = relative_path(path, base)
        source_hash = sha256_hex(text)
        sources.append(
            {
                "source_id": stable_id(rel, source_hash),
                "source_path": rel,
                "source_ref": rel,
                "absolute_path": str(path),
                "suffix": path.suffix.lower(),
                "chars": len(text),
                "content_sha256": source_hash,
                "text": text,
            }
        )
    return sources


def paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\s*\Z)", text):
        raw = match.group(0)
        value = raw.strip()
        if not value:
            continue
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        start = match.start() + leading
        end = match.start() + trailing
        spans.append((start, end, text[start:end]))
    return spans


def split_long_span(start: int, value: str, max_chars: int, overlap_chars: int) -> list[tuple[int, int, str]]:
    if len(value) <= max_chars:
        return [(start, start + len(value), value)]
    chunks = []
    cursor = 0
    step = max(1, max_chars - max(0, overlap_chars))
    while cursor < len(value):
        end = min(len(value), cursor + max_chars)
        piece = value[cursor:end].strip()
        if piece:
            leading = len(value[cursor:end]) - len(value[cursor:end].lstrip())
            trailing = len(value[cursor:end].rstrip())
            chunks.append((start + cursor + leading, start + cursor + trailing, piece))
        if end >= len(value):
            break
        cursor += step
    return chunks


def chunk_text(
    text: str,
    *,
    source_id: str,
    source_path: str,
    source_ref: str,
    max_chars: int = 6000,
    overlap_chars: int = 500,
) -> list[dict[str, Any]]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    chunks: list[dict[str, Any]] = []
    for start, end, value in paragraph_spans(text):
        for piece_start, piece_end, piece in split_long_span(start, value, max_chars, overlap_chars):
            chunk_index = len(chunks)
            chunk_id = stable_id(source_id, chunk_index, piece)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "source_path": source_path,
                    "source_ref": source_ref,
                    "chunk_index": chunk_index,
                    "char_start": piece_start,
                    "char_end": piece_end,
                    "chars": len(piece),
                    "approx_tokens": (len(piece) + 3) // 4,
                    "content_sha256": sha256_hex(piece),
                    "text": piece,
                }
            )
    return chunks


def build_chunks(
    sources: list[dict[str, Any]],
    *,
    max_chars: int = 6000,
    overlap_chars: int = 500,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for source in sources:
        chunks.extend(
            chunk_text(
                source["text"],
                source_id=source["source_id"],
                source_path=source["source_path"],
                source_ref=source["source_ref"],
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
        )
    return chunks


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_text_source_artifacts(
    *,
    input_paths: list[str | Path],
    course_dir: str | Path,
    base_dir: str | Path | None = None,
    max_chars: int = 6000,
    overlap_chars: int = 500,
) -> dict[str, Any]:
    course_path = Path(course_dir).expanduser().resolve()
    out = course_path / "text_sources"
    sources = collect_text_sources(input_paths, base_dir=base_dir)
    chunks = build_chunks(sources, max_chars=max_chars, overlap_chars=overlap_chars)
    manifest = {
        "schema_version": "0.1",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
        "sources": [
            {key: value for key, value in source.items() if key != "text"}
            for source in sources
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(out / "chunks.jsonl", chunks)
    return {
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "manifest_path": str(out / "source_manifest.json"),
        "chunks_path": str(out / "chunks.jsonl"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect text course sources and write stable chunk artifacts.")
    parser.add_argument("--input", action="append", required=True, help="Text file or directory. Repeatable.")
    parser.add_argument("--course-name", required=True)
    parser.add_argument("--base-dir", default=".", help="Course workspace root.")
    parser.add_argument("--source-base-dir", help="Base dir used for relative source paths.")
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--overlap-chars", type=int, default=500)
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    result = write_text_source_artifacts(
        input_paths=args.input,
        course_dir=base_dir / args.course_name,
        base_dir=args.source_base_dir or base_dir,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
