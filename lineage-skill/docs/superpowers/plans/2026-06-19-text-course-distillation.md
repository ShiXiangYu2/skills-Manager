# Text Course Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a source-grounded pure-text distillation path based on stable chunks and evidence cards.

**Architecture:** Add focused Python modules/scripts for text source collection and text evidence-card distillation, then integrate their artifacts into the existing pipeline and CoursePackage builder. Keep outputs file-based and resumable.

**Tech Stack:** Python standard library, existing `scripts/llm_client.py`, pytest for tests.

---

### Task 1: Text Source Core

**Files:**
- Create: `scripts/text_sources.py`
- Test: `tests/test_text_sources.py`

- [ ] Write tests for deterministic source ids, chunk ids, SHA-256 body hashes, char spans, and manifest generation.
- [ ] Implement source collection for `.md`, `.markdown`, `.txt`, `.text`, and `.json` OCR/manifests when useful.
- [ ] Implement stable paragraph-aware chunking with max character budget and overlap.
- [ ] Verify focused tests pass.

### Task 2: Evidence Card Distiller

**Files:**
- Create: `scripts/distill_text_course.py`
- Test: `tests/test_distill_text_course.py`

- [ ] Write tests for local card extraction from concepts, methods, cases, quotes, boundaries, and tasks.
- [ ] Implement deterministic fallback extraction and JSONL outputs.
- [ ] Add optional LLM enrichment behind existing `DISTILL_USE_LLM` and env checks.
- [ ] Write source summaries, course synthesis, and quality audit.
- [ ] Verify focused tests pass.

### Task 3: CoursePackage Integration

**Files:**
- Modify: `scripts/build_course_package.py`
- Test: `tests/test_build_course_package_text_cards.py`

- [ ] Write tests proving evidence cards populate structured package fields.
- [ ] Implement card loading and merge rules with deduplication.
- [ ] Include text artifacts in package evidence.
- [ ] Verify focused tests pass.

### Task 4: Pipeline Integration

**Files:**
- Modify: `scripts/run_course_pipeline.py`
- Modify: `scripts/distill_course.py`
- Test: `tests/test_run_course_pipeline_text_args.py`

- [ ] Write tests for CLI command assembly with `--text-input` and `--notes-input`.
- [ ] Run text distillation after documents stage when text sources exist.
- [ ] Include text synthesis in course digest prompts and local fallback digest.
- [ ] Verify focused tests pass.

### Task 5: Final Verification

**Files:**
- Documentation touched only if CLI behavior needs README/SKILL updates.

- [ ] Run focused pytest suite.
- [ ] Run `python -m compileall scripts`.
- [ ] Run all `scripts/*.py --help` smoke checks.
- [ ] Review git diff for unintended changes.
