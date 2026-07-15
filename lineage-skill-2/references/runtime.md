# Runtime Reference

Use this file only when `SKILL.md` does not contain enough detail for the selected workflow.

## Method

Operational method:

```text
Capture -> Cite -> Compress -> Connect -> Codify -> Evaluate
```

- **Capture**: keep original source order, filenames, lesson numbers, timestamps, screenshots, and OCR outputs when available.
- **Cite**: build evidence before broad summaries. Prefer source paths and lesson IDs over unsupported paraphrase.
- **Compress**: summarize in layers: lesson summary, concepts, topics, cases, methods, quotes, and study paths.
- **Connect**: rebuild relationships across lessons: prerequisites, repeated themes, aliases, examples, and workflows.
- **Codify**: package the course into a Skill with `SKILL.md`, `references/`, `scripts/`, and `agents/`.
- **Evaluate**: check completeness, citation strength, missing fields, and high-stakes boundaries.

Evidence strength:

- Strong: transcript segment, quote index, OCR text, screenshot, or lesson summary all support the claim.
- Strong visual: model-selected keyframe has timestamp, image path, selection reason, and manifest, ideally corroborated by transcript/OCR.
- Medium: one direct source supports the claim.
- Weak: only course-level synthesis supports the claim.
- Unsupported: no packaged reference supports the claim; say what is missing.

## Configuration

Read only the variables needed for the selected workflow.

```bash
# Audio transcription
AUDIO_TRANSCRIBE_API_KEY=
AUDIO_TRANSCRIBE_BASE_URL=https://api.siliconflow.cn/v1
AUDIO_TRANSCRIBE_MODEL=FunAudioLLM/SenseVoiceSmall

# Vision analysis. Use a model with video-understanding support.
LINEAGE_VISION_API_KEY=
LINEAGE_VISION_BASE_URL=https://your-openai-compatible-vision-endpoint/v1
LINEAGE_VISION_MODEL=gemini-3.1-pro-preview
LINEAGE_VISION_TIMEOUT=600

# Text distillation
LINEAGE_TEXT_API_KEY=
LINEAGE_TEXT_BASE_URL=https://api.openai.com/v1
LINEAGE_TEXT_MODEL=gpt5.5
LINEAGE_TEXT_MAX_TOKENS=4096
LINEAGE_TEXT_TIMEOUT=300

# Optional local extractive fallback
DISTILL_USE_LLM=1
DISTILL_CHUNK_SIZE=6000
DISTILL_CHUNK_OVERLAP=500

# Optional MinerU / OCR
MINERU_API_TOKEN=
```

If a provider is missing, continue with the smallest viable workflow:

- Existing transcripts, OCR, notes, or distillation files: skip missing capture stages.
- Raw audio/video without ASR: stop before transcription and list missing variables or tools.
- Raw video without vision: stop before visual analysis, or continue transcript-only if the user accepts.
- PDFs without MinerU: use existing OCR/text sources only and say scanned/image PDF evidence was not included.
- Pure text courses can run without `--input-dir` by using `--text-input`, `--notes-input`, or existing `documents/` with `--include-existing-documents`.

## CoursePackage

`course_package.json` is the normalized middle layer between course materials and generated Skills.

Required top-level shape:

```json
{
  "schema_version": "0.1",
  "manifest": {},
  "lessons": [],
  "concepts": [],
  "topics": [],
  "cases": [],
  "methods": [],
  "learning_checks": [],
  "quotes": [],
  "evidence": [],
  "study_paths": [],
  "boundaries": [],
  "quality": {}
}
```

Minimum generated Skill references:

- `course_digest.md`
- `lesson_index.json`
- `concept_glossary.md`
- `evidence_map.json`
- `quote_index.md`
- `study_paths.md`
- `course_package.json`

## Roles

Default role: `mentor`.

| Role | Use when |
| --- | --- |
| `mentor` | Guided learning, practice, review, progress-aware study, and course-backed application |
| `expert` | Course Q&A, concept explanation, lesson lookup, and source-backed answers |
| `consultant` | Private consulting, scenario diagnosis, option comparison, and course-grounded advice |
| `practitioner` | SOPs, checklists, playbooks, templates, drafts, workflows, and work outputs |
| `custom` | User-defined role or workflow not covered above |

Scope, citation strictness, and learner progress are separate options; do not encode them as fake role names.

## PDF / OCR

Use MinerU only when PDFs, scans, handouts, or slide exports should become evidence.

Workflow:

1. Check `MINERU_API_TOKEN`.
2. Run the full pipeline with `--documents-input`, or call `scripts/parse_mineru_documents.py`.
3. Confirm `documents/mineru_manifest.json` and `documents/mineru_supplement.md` exist.
4. Rebuild `course_package.json`.
5. Rebuild the target Skill.

Existing OCR output can be reused with `--skip-submit`.

## Pure Text Distillation

Use the text path when Markdown, TXT, OCR Markdown, handouts, or existing notes should become first-class course evidence.

Expected artifacts:

```text
text_sources/
├── source_manifest.json
└── chunks.jsonl
text_distillation/
├── evidence_cards.jsonl
├── source_summaries.json
├── text_course_synthesis.md
└── text_distillation_quality.json
```

Each chunk records source path, `source_ref`, chunk index, character span, and body SHA-256. Evidence cards are structured as concepts, methods, cases, quotes, boundaries, tasks, and open questions. The package builder merges those cards into `course_package.json` so text/PDF/OCR materials are synthesized, not merely copied.

## Model-Selected Keyframes

Do not treat equal-interval frames as final evidence. For video courses, use this two-stage rule:

1. Extract dense candidate frames into `keyframe_candidates/<media>/`.
2. Build labeled contact sheets from candidates.
3. Ask a multimodal vision model to select evidence-worthy frames.
4. Save per-sheet decisions under `keyframe_selection/<media>/`.
5. Save per-media manifest as `keyframe_selection/<media>_model_keyframes_manifest.json`.
6. Copy final selected frames into `keyframes_model_selected/<media>/`.
7. Write `keyframe_selection/model_keyframe_summary.md` and `model_keyframe_index.json`.

Resume behavior:

- If a media manifest exists and `--force` is not passed, skip that media.
- If a sheet decision JSON exists and `--force` is not passed, reuse it.
- Candidate frames are cache artifacts. They can be regenerated from source video and should not be required in generated Skills.
- The generated Skill should package `keyframe_selection/` and `keyframes_model_selected/`, not raw video or dense candidates.

## Final Distillation Audit

After course distillation and before package building, generate final audit files:

```text
distillation_audit.json
distillation_audit.md
```

The audit records per-lesson transcript status, visual-analysis status, document/OCR/text status, selected-keyframe counts, traceability paths, audit policy, cross-source validation flags, terminology risks, and manual-review recommendations.

Cross-source validation is material-aware:

- `--audit-mode auto` validates across sources only when comparable sources are available for a lesson. Transcript-only, audio-only, or text-only materials are not treated as incomplete merely because visual analysis or courseware is absent.
- `--audit-mode strict` requires review of missing or conflicting sources and is selected automatically by the full pipeline when `--evidence strict` is used.
- `--audit-mode off` records inventory, traceability, and extraction quality without cross-source mismatch flags.

If transcripts, video analysis, and courseware/text sources are all present, the audit should mark multi-source support, mismatches, source-only claims, and items requiring human review instead of treating all sources as equivalent.

The package builder reads `distillation_audit.json` when present and writes a compact `quality.distillation_audit` summary into `course_package.json`. Generated Skills should copy both audit files into `references/` and use them before treating a lesson as complete.

## Outputs And Resume

Course build state belongs under `<base-dir>/<course-name>/`; generated Skills belong under `<output-dir>/<skill-name>/`.

Expected course workspace:

```text
<course-name>/
├── transcripts/
├── analysis/
│   └── screenshots/
├── keyframe_candidates/
├── keyframe_selection/
│   ├── model_keyframe_summary.md
│   └── *_model_keyframes_manifest.json
├── keyframes_model_selected/
├── documents/
├── text_sources/
├── text_distillation/
├── index/
├── full_transcript.md
├── lesson_summaries.json
├── course_distillation_<date>.md
├── course_distillation_<date>.json
├── distillation_audit.json
├── distillation_audit.md
├── course_package.json
└── lineage_progress.json
```

Resume rules:

- Reuse existing transcripts, analyses, documents, distillation files, and CoursePackage when present.
- Reuse existing keyframe manifests and per-sheet selection JSON unless `--force` is requested.
- Do not mix multiple source courses in one `<course-name>` directory unless the user explicitly requests a combined package.
- Prefer rerunning the narrow missing stage over rebuilding the whole pipeline.
- Use `lineage_progress.json` to report what exists, what is missing, and what will run next.

Generated Skill evidence layout:

```text
<generated-skill>/references/
├── course_package.json
├── distillation_audit.json
├── distillation_audit.md
├── evidence_map.json
├── keyframe_selection/
├── keyframes_model_selected/
├── transcripts/
├── analysis/
└── documents/
```

The exact modality directories may be absent when the source material did not include that modality.
