from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from progress import STAGE_ORDER, summarize_artifacts


ROOT = Path(__file__).resolve().parents[1]


def test_progress_tracks_distillation_audit_artifacts(tmp_path: Path) -> None:
    course_dir = tmp_path / "course"
    course_dir.mkdir()
    (course_dir / "distillation_audit.json").write_text("{}", encoding="utf-8")
    (course_dir / "distillation_audit.md").write_text("# audit\n", encoding="utf-8")

    artifacts = summarize_artifacts(course_dir)

    assert artifacts["distillation_audit_json"] is True
    assert artifacts["distillation_audit_markdown"] is True


def test_audit_stage_runs_after_distill_before_package() -> None:
    assert "audit" in STAGE_ORDER
    assert STAGE_ORDER.index("distill") < STAGE_ORDER.index("audit") < STAGE_ORDER.index("package")

    pipeline = (ROOT / "scripts" / "run_course_pipeline.py").read_text(encoding="utf-8")
    assert "--skip-audit" in pipeline
    assert "--audit-mode" in pipeline
    assert "resolve_audit_mode" in pipeline
    assert "build_distillation_audit.py" in pipeline
    assert 'stage="audit"' in pipeline
