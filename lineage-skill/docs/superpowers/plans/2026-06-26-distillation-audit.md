# Distillation Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add final distillation audit artifacts that record per-lesson capture quality, cross-source validation, traceability, and manual review guidance.

**Architecture:** Create a focused `scripts/build_distillation_audit.py` module that reads existing course workspace artifacts and writes `distillation_audit.json` plus `distillation_audit.md`. Wire the audit into progress tracking, the full pipeline, `course_package.quality`, and generated Skill references without changing private artifact publishing rules.

**Tech Stack:** Python standard library, existing script-based pipeline, pytest.

---

### Task 1: Audit Builder

**Files:**
- Create: `scripts/build_distillation_audit.py`
- Test: `tests/test_build_distillation_audit.py`

- [ ] **Step 1: Write failing tests**

Add tests that create a fixture course with `transcripts/lesson1_transcript.json`, `analysis/lesson1_analysis.md`, `keyframe_selection/lesson1_model_keyframes_manifest.json`, `documents/lesson1.md`, `text_sources/chunks.jsonl`, and `text_distillation/evidence_cards.jsonl`. Assert that `build_audit("Demo", course_dir)` reports present transcript, visual analysis, documents, keyframes, traceability paths, multi-source support, manual review notes, and Markdown review wording.

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q -c /dev/null tests/test_build_distillation_audit.py`

Expected: import failure because `build_distillation_audit` does not exist.

- [ ] **Step 3: Implement minimal audit builder**

Implement `build_audit(course_name: str, source_dir: Path) -> dict`, `write_audit(course_name: str, source_dir: Path) -> dict`, and CLI args `--course-name`, `--source-dir`. Use deterministic file matching by normalized stems and conservative flags.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q -c /dev/null tests/test_build_distillation_audit.py`

Expected: all tests pass.

### Task 2: Package Quality Summary

**Files:**
- Modify: `scripts/build_course_package.py`
- Test: `tests/test_build_course_package_text_cards.py`

- [ ] **Step 1: Write failing test**

Add a test that writes `distillation_audit.json`, calls `build_package`, and asserts that `package["quality"]["distillation_audit"]` includes JSON/Markdown paths, lesson count, manual-review count, and cross-validation summary.

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q -c /dev/null tests/test_build_course_package_text_cards.py::test_build_package_includes_distillation_audit_summary`

Expected: assertion failure because the quality summary is absent.

- [ ] **Step 3: Implement package summary**

Read `distillation_audit.json` when present. Add a compact `quality.distillation_audit` object without copying all lesson notes into `course_package.json`.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q -c /dev/null tests/test_build_course_package_text_cards.py`

Expected: all tests pass.

### Task 3: Skill Packaging

**Files:**
- Modify: `scripts/build_course_skill.py`
- Test: `tests/test_build_course_skill_capability_rules.py`

- [ ] **Step 1: Write failing test**

Add a test that places both audit files in a fixture course, runs `build_course_skill.py`, and asserts that generated `references/distillation_audit.json`, `references/distillation_audit.md`, `lineage_manifest.json` statuses, and `SKILL.md` reference order include the audit files.

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q -c /dev/null tests/test_build_course_skill_capability_rules.py::test_generated_skill_includes_distillation_audit_references`

Expected: assertion failure because audit files are not copied or referenced.

- [ ] **Step 3: Implement skill packaging**

Copy optional audit files into `references/` with clear statuses and add them to generated `SKILL.md` reference guidance.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q -c /dev/null tests/test_build_course_skill_capability_rules.py`

Expected: all tests pass.

### Task 4: Pipeline and Progress Integration

**Files:**
- Modify: `scripts/progress.py`
- Modify: `scripts/run_course_pipeline.py`
- Test: `tests/test_distillation_audit_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert `summarize_artifacts()` counts audit files and `STAGE_ORDER` includes `audit` after `package` and before `build_skill`.

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q -c /dev/null tests/test_distillation_audit_pipeline.py`

Expected: assertion failure because audit is not represented.

- [ ] **Step 3: Implement integration**

Add `audit` stage to progress, artifact summary fields, `--skip-audit` CLI flag, and a `build_distillation_audit.py` command after package and before build-skill in `run_course_pipeline.py`.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q -c /dev/null tests/test_distillation_audit_pipeline.py`

Expected: all tests pass.

### Task 5: Full Verification and Push

**Files:**
- Verify all modified files

- [ ] **Step 1: Run full tests**

Run: `python -m pytest -q -c /dev/null tests`

Expected: all tests pass.

- [ ] **Step 2: Inspect git diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors and only intentional files changed.

- [ ] **Step 3: Commit and push**

Run: `git add ... && git commit -m "Add final distillation audit stage" && git push origin main`.

Expected: commit succeeds and remote push completes.
