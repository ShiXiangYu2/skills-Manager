# Text Course Distillation Design

## Goal

Add a first-class pure-text distillation path for Markdown, TXT, and OCR output so course notes, PDF OCR, handouts, and transcripts can be distilled into source-grounded evidence cards before building a CoursePackage.

## Architecture

The text path is a lightweight version of OpenHuman's chunk-first memory approach: collect source files, split them into stable source chunks, assign deterministic chunk ids and body hashes, then derive structured evidence cards from each chunk. The output remains local files under the course workspace and does not require SQLite, embeddings, or a long-running service.

The text artifacts are:

- `text_sources/source_manifest.json`: source files, source ids, hashes, and chunk references.
- `text_sources/chunks.jsonl`: immutable chunk records with `source_ref`, `chunk_id`, order, char spans, and `content_sha256`.
- `text_distillation/evidence_cards.jsonl`: structured cards for concepts, methods, cases, quotes, boundaries, tasks, and open questions.
- `text_distillation/source_summaries.json`: per-source coverage and themes.
- `text_distillation/text_course_synthesis.md`: text-source synthesis for the final course digest.
- `text_distillation/text_distillation_quality.json`: coverage audit and fallback/LLM status.

## Behavior

`scripts/distill_text_course.py` handles text-only distillation. It accepts repeatable `--input` paths, plus `--include-existing-documents` to include files under `<course-dir>/documents`. It can run without LLM by using deterministic local extraction; when `DISTILL_USE_LLM=1` and text model configuration exists, it enriches cards through the existing text LLM client.

`scripts/run_course_pipeline.py` gets repeatable `--text-input` and `--notes-input` arguments. After documents are parsed, it runs text distillation when text inputs or documents exist. `scripts/distill_course.py` then includes the text synthesis in its course-level prompt. `scripts/build_course_package.py` reads evidence cards directly so structured concepts, methods, cases, quotes, boundaries, and learning checks do not depend on brittle Markdown bullet parsing.

## Reliability

Chunk ids are deterministic from source id, chunk index, and content. Chunks keep char ranges and SHA-256 body hashes for auditability. LLM failures produce a recorded fallback card set instead of aborting the whole course pipeline. The quality report records source count, chunk count, card count, empty chunks, fallback usage, and field coverage.

## Scope

This implementation does not add embeddings, semantic retrieval, SQLite, PDF parsing beyond existing MinerU output, or a UI. It focuses on making text and OCR materials genuinely participate in distillation and CoursePackage generation.
