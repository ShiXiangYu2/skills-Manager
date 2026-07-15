from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from distill_course import build_course_digest, load_text_synthesis, local_course_digest
from run_course_pipeline import build_text_distill_command, should_run_media_capture


def test_load_text_synthesis_reads_distillation_artifact(tmp_path: Path) -> None:
    course_dir = tmp_path / "course"
    artifact = course_dir / "text_distillation" / "text_course_synthesis.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Text\n\n## 关键概念\n- 证据优先", encoding="utf-8")

    assert "证据优先" in load_text_synthesis(str(course_dir))


def test_local_course_digest_includes_text_synthesis() -> None:
    transcripts = [{"duration": 60, "full_text": "老师讲了课程主线。", "video": "lesson1"}]
    summaries = [{"video": "lesson1", "summary": "本课讲课程主线。"}]
    text_synthesis = "## 关键概念\n- 证据优先（notes.md#0）"

    digest = local_course_digest(transcripts, summaries, "Demo", text_synthesis=text_synthesis)

    assert "文字资料补充" in digest
    assert "证据优先" in digest


def test_build_course_digest_supports_text_only_course(tmp_path: Path, monkeypatch) -> None:
    course_dir = tmp_path / "course"
    artifact = course_dir / "text_distillation" / "text_course_synthesis.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("## 方法流程\n- 先证据，后综合", encoding="utf-8")
    monkeypatch.setenv("DISTILL_USE_LLM", "0")

    digest = build_course_digest([], [], "Demo", str(course_dir))

    assert digest["total_lessons"] == 0
    assert "先证据，后综合" in digest["distillation_markdown"]


def test_build_text_distill_command_includes_text_and_notes_inputs(tmp_path: Path) -> None:
    args = argparse.Namespace(
        course_name="Demo",
        text_input=["/tmp/handout.md"],
        notes_input=["/tmp/notes"],
        include_existing_documents=True,
        text_max_chars=4000,
        text_overlap_chars=200,
        text_no_llm=True,
    )

    cmd = build_text_distill_command(
        py="python",
        root=tmp_path,
        args=args,
        base_dir=tmp_path / ".lineage" / "courses",
    )

    assert "distill_text_course.py" in " ".join(cmd)
    assert cmd.count("--input") == 2
    assert "--include-existing-documents" in cmd
    assert "--no-llm" in cmd
    assert ["--max-chars", "4000"] == [cmd[cmd.index("--max-chars")], cmd[cmd.index("--max-chars") + 1]]


def test_media_capture_is_optional_for_text_only_pipeline() -> None:
    args = argparse.Namespace(input_dir=None)

    assert should_run_media_capture(args) is False
