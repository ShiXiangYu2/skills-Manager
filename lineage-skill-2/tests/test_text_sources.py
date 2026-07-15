from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from text_sources import collect_text_sources, chunk_text, write_text_source_artifacts


def test_chunk_text_preserves_char_spans_and_hashes() -> None:
    text = "第一段讲课程主线。\n\n第二段讲方法步骤。\n\n第三段讲案例边界。"

    chunks = chunk_text(
        text,
        source_id="source-a",
        source_path="notes/course.md",
        source_ref="notes/course.md",
        max_chars=18,
        overlap_chars=0,
    )

    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert chunks[0]["text"] == "第一段讲课程主线。"
    assert chunks[1]["text"] == "第二段讲方法步骤。"
    assert chunks[2]["text"] == "第三段讲案例边界。"
    assert chunks[0]["char_start"] == 0
    assert chunks[0]["char_end"] == len("第一段讲课程主线。")
    assert len(chunks[0]["content_sha256"]) == 64
    assert chunks[0]["chunk_id"] != chunks[1]["chunk_id"]


def test_chunk_text_handles_single_multiline_markdown_block() -> None:
    text = "# 课程讲义\n概念：证据优先。\n方法：先采集来源。\n"

    chunks = chunk_text(
        text,
        source_id="source-a",
        source_path="lesson.md",
        source_ref="lesson.md",
        max_chars=200,
        overlap_chars=0,
    )

    assert len(chunks) == 1
    assert "证据优先" in chunks[0]["text"]


def test_collect_text_sources_reads_markdown_txt_and_skips_generated_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "materials"
    source_dir.mkdir()
    (source_dir / "lesson.md").write_text("# 课一\n\n概念：长期主义", encoding="utf-8")
    (source_dir / "notes.txt").write_text("方法：先诊断，再行动", encoding="utf-8")
    (source_dir / "image.png").write_bytes(b"not text")
    generated = source_dir / "text_distillation"
    generated.mkdir()
    (generated / "text_course_synthesis.md").write_text("旧输出", encoding="utf-8")

    sources = collect_text_sources([source_dir], base_dir=tmp_path)

    rel_paths = [source["source_path"] for source in sources]
    assert rel_paths == ["materials/lesson.md", "materials/notes.txt"]
    assert all(source["text"].strip() for source in sources)
    assert len({source["source_id"] for source in sources}) == 2


def test_write_text_source_artifacts_writes_manifest_and_jsonl(tmp_path: Path) -> None:
    material = tmp_path / "handout.md"
    material.write_text("概念：证据链\n\n步骤：采集、引用、压缩", encoding="utf-8")
    course_dir = tmp_path / "course"

    result = write_text_source_artifacts(
        input_paths=[material],
        course_dir=course_dir,
        base_dir=tmp_path,
        max_chars=40,
        overlap_chars=0,
    )

    manifest = json.loads((course_dir / "text_sources" / "source_manifest.json").read_text(encoding="utf-8"))
    chunk_lines = (course_dir / "text_sources" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()

    assert result["source_count"] == 1
    assert result["chunk_count"] >= 1
    assert manifest["sources"][0]["source_path"] == "handout.md"
    assert len(chunk_lines) == result["chunk_count"]
    first_chunk = json.loads(chunk_lines[0])
    assert first_chunk["source_ref"] == "handout.md"
    assert first_chunk["text"].startswith("概念")
