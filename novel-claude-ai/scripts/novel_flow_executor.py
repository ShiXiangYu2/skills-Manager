#!/usr/bin/env python3
"""小说流程增强执行器。

覆盖目标：
1. /继续写 自动把占位章转成正文并进入后续流程
2. 增加章节质量下限检查
3. 门禁失败后自动最小修复重试

重构说明：
- continue_write() 已拆分为独立模块：rag_loader, constraint_injector,
  beat_pipeline, chapter_assembler, gate_checker, state_updater, error_handler
- continue_write() 本身控制在 100 行以内
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from common import (
    ensure_dir, read_text, write_text, slugify,
    sha1_text, file_sha1, load_json, save_json,
    chapter_no_from_name,
)

# ── 模块导入 ──────────────────────────────────────────────────────────────────
from rag_loader import query_rag_context, extract_rag_lines, build_writing_query
from constraint_injector import collect_and_inject
from beat_pipeline import run_draft_pipeline, chapter_is_draft_stub
from chapter_assembler import evaluate_quality, assess_and_improve
from gate_checker import run_chapter_gate
from state_updater import update_flow_metrics, run_post_gate_updates
from error_handler import (
    build_lock_error, build_success_result, build_error_result,
    check_idempotent_cache, extract_retrieval_stats,
)

# ── 常量 ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
TEMPLATE_DIR = SKILL_ROOT / "templates"
CHAPTER_RE = re.compile(r"^第\d+章.*\.md$")
STUB_MARKER = "<!-- NOVEL_FLOW_STUB -->"
BEAT_SHEET_STUB_MARKER = "<!-- BEAT_SHEET_STUB -->"
FLOW_DIR_NAME = ".flow"
FLOW_LOCK_FILE = "continue_write.lock"
FLOW_CACHE_FILE = "continue_write_cache.json"
FLOW_SNAPSHOT_DIR = "snapshots"
FLOW_CACHE_MAX_ENTRIES = 200

PACING_MODE_PROFILES: Dict[str, Any] = {
    "fast":      {"min_chars": 2500, "beat_pacing_depth": "fast",      "max_skip_density": 0.40},
    "standard":  {"min_chars": 2500, "beat_pacing_depth": "standard",  "max_skip_density": 0.30},
    "immersive": {"min_chars": 4500, "beat_pacing_depth": "immersive", "max_skip_density": 0.15},
}


def _resolve_pacing_mode(value: Optional[str]) -> str:
    return value if value in PACING_MODE_PROFILES else "standard"


# ── 子进程执行 ────────────────────────────────────────────────────────────────

def run_python(script: Path, args: List[str]) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    cmd = [sys.executable, str(script), *args]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    except subprocess.TimeoutExpired:
        return -1, "", "子进程超时 (300s)", None
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    payload = None
    if out:
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            payload = None
    return proc.returncode, out, err, payload


# ── 路径校验 ──────────────────────────────────────────────────────────────────

def validate_chapter_path(project_root: Path, chapter_file: str) -> Tuple[Path, Optional[str]]:
    """解析并校验章节路径，确保路径在项目目录内。"""
    chapter_path = Path(chapter_file)
    if not chapter_path.is_absolute():
        chapter_path = project_root / chapter_path
    chapter_path = chapter_path.resolve()
    try:
        chapter_path.relative_to(project_root.resolve())
    except ValueError:
        return chapter_path, f"安全错误：章节文件必须在项目目录内: {chapter_file}"
    return chapter_path, None


# ── 文件锁 ────────────────────────────────────────────────────────────────────

def _try_create_lock(lock_file: Path, payload: Dict[str, Any]) -> bool:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(lock_file), flags, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return True


def acquire_lock(lock_file: Path, run_id: str, timeout_sec: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
    now = time.time()
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "pid": os.getpid(),
        "ts": now,
        "started_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if _try_create_lock(lock_file, payload):
        return True, None

    if not lock_file.exists():
        return False, None

    existing_stat = lock_file.stat()
    current = load_json(lock_file, {})
    cur = cast(Dict[str, Any], current)
    ts_raw = cur.get("ts", 0)
    ts = float(ts_raw) if isinstance(ts_raw, (int, float, str)) else 0.0
    if ts and (now - ts) < max(1, timeout_sec):
        return False, current

    try:
        latest_stat = lock_file.stat()
    except FileNotFoundError:
        if _try_create_lock(lock_file, payload):
            return True, None
        return False, load_json(lock_file, {})

    if (
        latest_stat.st_ino != existing_stat.st_ino
        or latest_stat.st_mtime_ns != existing_stat.st_mtime_ns
    ):
        return False, load_json(lock_file, {})

    lock_file.unlink(missing_ok=True)
    if _try_create_lock(lock_file, payload):
        return True, None
    return False, load_json(lock_file, {})


def release_lock(lock_file: Path, run_id: str) -> None:
    if not lock_file.exists():
        return
    cur = load_json(lock_file, {})
    if cur.get("run_id") == run_id:
        lock_file.unlink(missing_ok=True)


# ── 快照管理 ──────────────────────────────────────────────────────────────────

def create_snapshot(chapter_path: Path, flow_dir: Path, run_id: str) -> Optional[Path]:
    if not chapter_path.exists():
        return None
    out = flow_dir / FLOW_SNAPSHOT_DIR / slugify(chapter_path.stem) / f"{run_id}.md"
    ensure_dir(out.parent)
    shutil.copy2(str(chapter_path), str(out))
    return out


def restore_snapshot(snapshot_path: Path, original_path: Path, current_path: Path) -> Optional[Path]:
    if not snapshot_path.exists():
        return None
    ensure_dir(original_path.parent)
    shutil.copy2(str(snapshot_path), str(original_path))
    if current_path != original_path and current_path.exists():
        current_path.unlink(missing_ok=True)
    return original_path


# ── 请求 ID 与缓存 ───────────────────────────────────────────────────────────

def make_request_id(args: argparse.Namespace, chapter_path: Path, query: str, chapter_hash_before: str, project_root: Path = None) -> str:
    try:
        if project_root and chapter_path.is_relative_to(project_root):
            path_key = str(chapter_path.relative_to(project_root))
        else:
            path_key = chapter_path.name
    except (ValueError, TypeError):
        path_key = chapter_path.name

    raw = "|".join([
        path_key,
        query.strip(),
        str(args.top_k),
        str(args.min_chars),
        str(args.min_paragraphs),
        str(args.min_dialogue_ratio),
        str(args.max_dialogue_ratio),
        str(args.min_sentences),
        str(args.auto_draft),
        str(args.auto_improve),
        str(args.auto_retry),
        chapter_hash_before,
    ])
    return sha1_text(raw)


def load_continue_cache(flow_dir: Path) -> Dict[str, Any]:
    return load_json(flow_dir / FLOW_CACHE_FILE, {"entries": {}})


def save_continue_cache(flow_dir: Path, cache: Dict[str, Any]) -> None:
    entries = cache.get("entries", {})
    if isinstance(entries, dict) and len(entries) > FLOW_CACHE_MAX_ENTRIES:
        items = sorted(entries.items(), key=lambda kv: kv[1].get("saved_at", ""), reverse=True)
        cache["entries"] = dict(items[:FLOW_CACHE_MAX_ENTRIES])
    save_json(flow_dir / FLOW_CACHE_FILE, cache)


# ── 模板与手稿工具 ────────────────────────────────────────────────────────────

def template(name: str, mapping: Dict[str, str]) -> str:
    txt = read_text(TEMPLATE_DIR / name)
    for k, v in mapping.items():
        txt = txt.replace("{" + k + "}", v)
    return txt


def latest_chapter(manuscript_dir: Path) -> Optional[Path]:
    files = sorted(manuscript_dir.glob("*.md"), key=lambda p: (chapter_no_from_name(p.name), p.name))
    return files[-1] if files else None


def next_chapter_filename(manuscript_dir: Path, title: str = "待写") -> str:
    cur = latest_chapter(manuscript_dir)
    next_no = chapter_no_from_name(cur.name) + 1 if cur else 1
    return f"第{next_no}章-{title}.md"


def write_if_needed(path: Path, content: str, overwrite: bool, changed: List[str], skipped: List[str]) -> None:
    if path.exists() and not overwrite:
        skipped.append(str(path))
        return
    write_text(path, content)
    changed.append(str(path))


def project_structure(project_root: Path) -> None:
    dirs = [
        "00_memory", "00_memory/chapter_summaries", "00_memory/chapter_summaries/archive",
        "00_memory/retrieval", "00_memory/style_profiles",
        "01_analysis", "02_knowledge_base", "03_manuscript",
        "04_editing/gate_artifacts", "05_assets",
    ]
    for d in dirs:
        ensure_dir(project_root / d)


def load_character_names(project_root: Path) -> List[str]:
    p = project_root / "00_memory" / "character_tracker.md"
    if not p.exists():
        return []
    txt = read_text(p)
    names = set()
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and re.fullmatch(r"[一-鿿A-Za-z0-9_·]{2,20}", cells[0] or ""):
                if cells[0] not in {"人物", "角色", "姓名", "---"}:
                    names.add(cells[0])
    for m in re.finditer(r"(?:姓名|角色)\s*[:：]\s*([一-鿿A-Za-z0-9_·]{2,20})", txt):
        names.add(m.group(1))
    return sorted(names)


# ── 项目初始化 ────────────────────────────────────────────────────────────────

def init_project_files(project_root: Path, args: argparse.Namespace, overwrite: bool) -> Dict[str, List[str]]:
    changed: List[str] = []
    skipped: List[str] = []
    now = dt.datetime.now().strftime("%Y-%m-%d")

    mapping = {
        "TITLE": args.title, "GENRE": args.genre, "CORE_HOOK": args.core_hook,
        "TARGET_WORDS": str(args.target_words), "ENDING": args.ending,
        "VOL1_NAME": "起势卷", "VOL1_EVENT": args.core_conflict, "VOL1_END": "120",
        "ACT1_GOAL": "建立主角目标与初始矛盾",
        "ACT2_CONFLICT": "冲突升级并引入多线压力",
        "ACT3_CLIMAX": "卷末反转并埋下跨卷悬念",
        "VOL2_NAME": "扩张卷", "VOL2_EVENT": "主线升级", "VOL2_START": "121", "VOL2_END": "240",
        "PROTAGONIST": args.protagonist,
        "START_STATE": "普通起点", "MID_TRANSFORM": "价值观重塑", "FINAL_STATE": "完成角色弧线",
        "HEROINE": "核心配角", "H_START": "初始立场", "H_MID": "立场变化", "H_FINAL": "关系定型",
        "POWER_LEVEL_1": "初阶", "POWER_LEVEL_2": "中阶", "POWER_LEVEL_3": "高阶", "POWER_LEVEL_MAX": "终阶",
        "RULE_1": "角色行为必须符合已建立动机", "RULE_2": "时间线不得自相矛盾",
        "RULE_3": "力量体系不得跳级失控", "DATE": now,
        "MAIN_PLOT": args.core_conflict, "START_LOCATION": "起始地点",
        "START_GOAL": args.protagonist_goal,
        "CHAPTER1_PLAN": "建立主角目标与核心冲突，留下章末钩子",
        "CHAPTER1_CHARACTERS": args.protagonist,
        "PROTAGONIST_NAME": args.protagonist, "POWER_LEVEL": "初阶",
        "LOCATION": "起始地点", "GOAL": args.protagonist_goal,
        "ITEMS": "暂无", "PERSONALITY": "待细化", "APPEARANCE": "待细化",
        "RELATION_1": "与核心配角：待建立", "RELATION_2": "与反派势力：待建立",
        "CHARACTER_A_NAME": "核心配角", "IDENTITY": "待设定",
        "RELATIONSHIP": "待设定", "STATUS": "待设定",
        "TIME_SYSTEM_DESCRIPTION": "以章节推进为主时间轴，可按天/周补充细化。",
        "POWER_SYSTEM_DESCRIPTION": "从初阶到终阶，逐步揭示规则与限制。",
        "PERSPECTIVE": "第三人称有限", "DISTANCE": "中等", "TENSE": "过去式",
        "AVG_SENTENCE_LENGTH": "24", "RATIO": "3:7", "AVG_PARAGRAPH_LENGTH": "4",
        "DIALOGUE_RATIO": "45", "WORD_STYLE": "口语与书面混合",
        "RHETORIC_DENSITY": "中", "SENSORY_PREFERENCE": "视觉为主",
        "HUMOR_LEVEL": "适中", "MAX_CLIMAX": "2", "MIN_BUFFER": "1",
        "RHYTHM_PATTERN": "升-升-爆-缓",
    }

    file_map = {
        "00_memory/idea_seed.md": template("idea_seed.template.md", mapping)
        + f"\n\n## 用户输入补充\n- 剧情种子：{args.idea}\n- 主角目标：{args.protagonist_goal}\n- 核心冲突：{args.core_conflict}\n",
        "00_memory/million_word_blueprint.md": template("million_word_blueprint.template.md", mapping),
        "00_memory/novel_plan.md": template("novel_plan.template.md", mapping),
        "00_memory/novel_state.md": template("novel_state.template.md", mapping),
        "00_memory/novel_findings.md": template("novel_findings.template.md", mapping),
        "00_memory/character_tracker.md": template("character_tracker.template.md", mapping),
        "00_memory/timeline.md": template("timeline.template.md", mapping),
        "00_memory/foreshadowing_tracker.md": template("foreshadowing_tracker.template.md", mapping),
        "00_memory/world_state.md": template("world_state.template.md", mapping),
        "00_memory/style_anchor.md": template("style_anchor.template.md", mapping),
        "00_memory/chapter_summaries/recent.md": template("chapter_summaries_recent.template.md", mapping),
        "02_knowledge_base/12_style_skills.md": "# 风格技能库\n\n- 初始化：待补充项目风格技能。\n",
    }

    for rel, content in file_map.items():
        write_if_needed(project_root / rel, content, overwrite, changed, skipped)

    first_chapter = project_root / "03_manuscript" / "第1章-开篇待写.md"
    first_stub = f"""# 第1章 开篇

{STUB_MARKER}

## 本章目标
- 建立主角目标：{args.protagonist_goal}
- 落地核心冲突：{args.core_conflict}

## 场景草图
- 起始地点：
- 冲突触发点：
- 章末钩子：

## 正文
[待写]
"""
    write_if_needed(first_chapter, first_stub, overwrite, changed, skipped)

    next_task = project_root / "00_memory" / "next_chapter_task.md"
    next_task_txt = f"""# 下一步写作任务

1. 先执行：`/继续写`
2. 当前建议章节：`{first_chapter.name}`
3. 当前剧情输入：{args.idea}
"""
    write_if_needed(next_task, next_task_txt, overwrite, changed, skipped)

    return {"changed": changed, "skipped": skipped}


# ── continue_write 辅助函数 ───────────────────────────────────────────────────

def _apply_pacing_mode(args: argparse.Namespace) -> None:
    """应用节奏模式到 args。"""
    pacing_mode = _resolve_pacing_mode(getattr(args, "pacing_mode", "standard"))
    args.pacing_mode = pacing_mode
    args.min_chars = max(args.min_chars, int(PACING_MODE_PROFILES[pacing_mode]["min_chars"]))


def _resolve_chapter(project_root: Path, args: argparse.Namespace) -> Tuple[Path, Path, bool]:
    """解析章节路径，不存在则创建占位。返回 (chapter_path, original_path, created)。"""
    manuscript_dir = project_root / "03_manuscript"
    ensure_dir(manuscript_dir)
    if args.chapter_file:
        chapter_path, err = validate_chapter_path(project_root, args.chapter_file)
        if err:
            raise ValueError(err)
    else:
        chapter_path = (manuscript_dir / next_chapter_filename(
            manuscript_dir, title=args.chapter_title)).resolve()
    original = chapter_path
    created = False
    if not chapter_path.exists():
        created = True
        write_text(
            chapter_path,
            f"# {chapter_path.stem.replace('-', ' ')}\n\n{STUB_MARKER}\n\n## 正文\n[待写]\n",
        )
    return chapter_path, original, created


def _detect_research_gaps(
    args: argparse.Namespace, project_root: Path, query: str
) -> Optional[Dict[str, Any]]:
    """自动调研：检测知识缺口。"""
    if not getattr(args, "auto_research", True):
        return None
    try:
        from research_agent import detect_knowledge_gaps
        gaps_result = detect_knowledge_gaps(project_root, query)
        if gaps_result.get("has_gaps"):
            return gaps_result
    except ImportError:
        pass
    return None


# ── continue_write 主函数 ─────────────────────────────────────────────────────

def continue_write(args: argparse.Namespace) -> Dict[str, Any]:
    """继续写：自动将占位章转成正文并进入后续流程。

    重构后控制在 100 行以内，核心逻辑委托给各独立模块。
    """
    # ── 初始化 ──
    project_root = Path(args.project_root).expanduser().resolve()
    project_structure(project_root)
    flow_dir = project_root / FLOW_DIR_NAME
    ensure_dir(flow_dir)
    run_id = dt.datetime.now().strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"
    lock_file = flow_dir / FLOW_LOCK_FILE
    locked, lock_holder = acquire_lock(lock_file, run_id, timeout_sec=args.lock_timeout_sec)
    if not locked:
        return build_lock_error(project_root, run_id, lock_holder)

    started_at = time.time()
    query = (args.query or "推进下一章剧情").strip()
    _apply_pacing_mode(args)

    state: Dict[str, Any] = {"chapter_path": None, "original_chapter_path": None, "snapshot_path": None}

    try:
        # Phase 1: RAG 检索
        q_code, q_out, q_err, q_payload = query_rag_context(
            project_root, query, args.top_k, args.candidate_k, args.force_retrieval)

        # Phase 2: 章节路径解析
        chapter_path, original_path, created_stub = _resolve_chapter(project_root, args)
        state.update(chapter_path=chapter_path, original_chapter_path=original_path)

        # Phase 3: 幂等缓存检查
        chapter_hash = file_sha1(chapter_path)
        request_id = make_request_id(args, chapter_path, query, chapter_hash, project_root)
        cached = check_idempotent_cache(flow_dir, request_id, chapter_hash, started_at, project_root, query, args)
        if cached is not None:
            return cached

        # Phase 4: 快照
        state["snapshot_path"] = create_snapshot(chapter_path, flow_dir, run_id)

        # Phase 5: 约束注入 + 查询组装
        research_gaps = _detect_research_gaps(args, project_root, query)
        writing_constraints, injected_lines = (
            collect_and_inject(project_root, chapter_path, query)
            if args.enable_constraints else (None, [])
        )
        rag_lines = extract_rag_lines(q_payload, args.top_k)
        writing_query = build_writing_query(query, rag_lines, injected_lines)

        # Phase 6: 草稿生成
        draft_info = run_draft_pipeline(project_root, chapter_path, writing_query, writing_constraints, args)

        # Phase 7: 质量评估 + 改进
        is_draft = chapter_is_draft_stub(chapter_path)
        quality_before, quality_after, improve_rounds = assess_and_improve(
            project_root, chapter_path, writing_query, args, is_draft)

        # Phase 8: 门禁检查 + 重试
        gate_result = run_chapter_gate(
            project_root, chapter_path, writing_query, quality_after,
            q_payload, writing_constraints, args, is_draft)

        # Phase 9: 门禁通过后状态更新
        updates = run_post_gate_updates(
            project_root, chapter_path, project_root / "03_manuscript",
            writing_constraints, gate_result["gate_passed"], args)

        # Phase 10: 构建结果
        retrieval_stats = extract_retrieval_stats(q_payload)
        return build_success_result(
            project_root=project_root, chapter_path=chapter_path,
            original_chapter_path=original_path, query=query,
            q_code=q_code, q_out=q_out, q_err=q_err, q_payload=q_payload,
            writing_constraints=writing_constraints, snapshot_path=state["snapshot_path"],
            created_stub=created_stub, draft_info=draft_info,
            quality_before=quality_before, quality_after=quality_after,
            quality_report_path=gate_result["quality_report"],
            improve_rounds=improve_rounds, gate_result=gate_result,
            post_gate_updates=updates, research_gaps=research_gaps,
            retrieval_stats=retrieval_stats, request_id=request_id,
            chapter_hash_before=chapter_hash, run_id=run_id,
            started_at=started_at, args=args, flow_dir=flow_dir,
            rollback_applied=False,
        )

    except Exception as exc:
        return build_error_result(
            exc, project_root=project_root, state=state,
            args=args, flow_dir=flow_dir, run_id=run_id,
            started_at=started_at, query=query)
    finally:
        release_lock(lock_file, run_id)


# ── 一键开书 ──────────────────────────────────────────────────────────────────

def one_click(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    project_structure(project_root)
    files = init_project_files(project_root, args, overwrite=args.overwrite)
    b_code, b_out, b_err, b_payload = run_python(
        SCRIPT_DIR / "plot_rag_retriever.py",
        ["build", "--project-root", str(project_root)],
    )

    story_graph_file = project_root / "00_memory" / "story_graph.json"
    if not story_graph_file.exists():
        run_python(SCRIPT_DIR / "story_graph_builder.py", ["init", "--project-root", str(project_root)])
        if story_graph_file.exists():
            files["changed"].append(str(story_graph_file))

    outline_anchors_file = project_root / "00_memory" / "outline_anchors.json"
    if not outline_anchors_file.exists():
        target_chapters = max(10, int(getattr(args, "target_words", 0) or 0) // 3500)
        run_python(
            SCRIPT_DIR / "outline_anchor_manager.py",
            ["init", "--project-root", str(project_root),
             "--total-chapters-target", str(target_chapters)],
        )
        if outline_anchors_file.exists():
            files["changed"].append(str(outline_anchors_file))

    confirmation_items = [
        ("目标读者", getattr(args, "target_audience", "")),
        ("写作风格", getattr(args, "writing_style", "")),
        ("核心禁区", getattr(args, "core_taboo", "")),
    ]
    confirmation_lines = [
        f"- {label}：{val}" for label, val in confirmation_items if str(val or "").strip()
    ]
    if confirmation_lines:
        idea_seed_file = project_root / "00_memory" / "idea_seed.md"
        original = read_text(idea_seed_file) if idea_seed_file.exists() else "# 创意种子\n"
        addition = "\n\n## 开书前确认\n" + "\n".join(confirmation_lines) + "\n"
        write_text(idea_seed_file, original.rstrip() + addition)
        if str(idea_seed_file) not in files["changed"]:
            files["changed"].append(str(idea_seed_file))

    return {
        "ok": b_code == 0,
        "command": "one-click",
        "project_root": str(project_root),
        "created_or_updated_files": files["changed"],
        "skipped_files": files["skipped"],
        "index_result": b_payload if b_payload is not None else {"stdout": b_out, "stderr": b_err},
        "next_step": "/继续写",
    }


# ── 改纲续写 ──────────────────────────────────────────────────────────────────

def cmd_revise_outline(args: argparse.Namespace) -> Dict[str, Any]:
    """执行 /改纲续写：锚点重算 + 图谱级联标记 + RAG 索引重建。"""
    project_root = Path(args.project_root).expanduser().resolve()
    from_chapter = int(args.from_chapter)
    change_description = str(getattr(args, "change_description", "") or "").strip()

    if from_chapter <= 0:
        return {"ok": False, "command": "revise-outline", "error": "from_chapter_must_be_positive"}

    plan_file = project_root / "00_memory" / "novel_plan.md"
    if not plan_file.exists():
        return {"ok": False, "command": "revise-outline", "error": f"novel_plan_missing:{plan_file}"}

    flow_dir = project_root / FLOW_DIR_NAME
    ensure_dir(flow_dir)
    report_file = project_root / "00_memory" / "revise_outline_report.md"
    anchors_file = project_root / "00_memory" / "outline_anchors.json"
    backup_file: Optional[Path] = None
    backup_created = False

    try:
        if anchors_file.exists():
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = flow_dir / f"backup_anchors_{ts}.json"
            shutil.copy2(str(anchors_file), str(backup_file))
            backup_created = True

        r_code, r_out, _r_err, r_payload = run_python(
            SCRIPT_DIR / "outline_anchor_manager.py",
            ["recalculate", "--project-root", str(project_root)],
        )
        recalc_result = r_payload if isinstance(r_payload, dict) else {"stdout": r_out}
        anchors_recalculated = r_code == 0 and bool(recalc_result.get("ok"))

        cascade_result: Dict[str, Any] = {"ok": False, "skipped": True}
        cascade_ok = False
        graph_file = project_root / "00_memory" / "story_graph.json"
        if anchors_recalculated and graph_file.exists():
            c_code, c_out, _c_err, c_payload = run_python(
                SCRIPT_DIR / "story_graph_updater.py",
                ["cascade", "--project-root", str(project_root),
                 "--from-chapter", str(from_chapter),
                 "--change-description", change_description],
            )
            cascade_result = c_payload if isinstance(c_payload, dict) else {"stdout": c_out}
            cascade_ok = c_code == 0 and bool(cascade_result.get("ok"))

        rag_rebuilt = False
        rag_result: Dict[str, Any] = {"ok": False, "skipped": True}
        if anchors_recalculated:
            b_code, b_out, _b_err, b_payload = run_python(
                SCRIPT_DIR / "plot_rag_retriever.py",
                ["build", "--project-root", str(project_root)],
            )
            rag_result = b_payload if isinstance(b_payload, dict) else {"stdout": b_out}
            rag_rebuilt = b_code == 0 and bool(rag_result.get("ok"))

        report_lines = [
            "# 改纲续写报告", "",
            f"- 时间：{dt.datetime.now().isoformat()}",
            f"- 改纲生效章节：第{from_chapter}章",
            f"- 改纲说明：{change_description or '未提供'}",
            f"- novel_plan.md：{plan_file}",
            f"- 锚点备份：{backup_file if backup_created else '无旧锚点，无需备份'}", "",
            "## 锚点重算",
            f"- 成功：{anchors_recalculated}",
            f"- 卷数：{recalc_result.get('volume_count', 'N/A')}",
            f"- 总章数：{recalc_result.get('total_chapters_target', 'N/A')}", "",
            "## 图谱级联",
            f"- 执行：{'是' if graph_file.exists() else '否（图谱文件不存在，跳过）'}",
            f"- 成功：{cascade_ok}",
            f"- 受影响节点：{cascade_result.get('affected_nodes_count', 'N/A')}",
            f"- 受影响边：{cascade_result.get('affected_edges_count', 'N/A')}", "",
            "## RAG 索引重建",
            f"- 成功：{rag_rebuilt}", "",
            "## 下一步",
            "- 请核对上方卷数/总章数是否与新大纲一致。",
            "- 如不一致，请修正 novel_plan.md 后再次执行 /改纲续写。",
            "- 确认无误后，执行 /继续写 从新剧情方向推进。",
        ]
        report_written = write_text(report_file, "\n".join(report_lines))

        ok = anchors_recalculated and report_written
        error = (
            None if ok
            else "anchor_recalculate_failed" if not anchors_recalculated
            else "report_write_failed"
        )
        next_step = (
            "改纲完成：锚点已重算、图谱已标记、索引已重建。请执行 /继续写 从新方向推进。"
            if (anchors_recalculated and cascade_ok and rag_rebuilt)
            else "改纲流程部分完成，请查看 revise_outline_report.md 确认失败步骤后再执行 /继续写。"
        )

        return {
            "ok": ok, "command": "revise-outline", "project_root": str(project_root),
            "from_chapter": from_chapter, "change_description": change_description,
            "anchors_backup_file": str(backup_file) if backup_file else None,
            "anchors_recalculated": anchors_recalculated, "anchors_result": recalc_result,
            "cascade_ok": cascade_ok, "cascade_result": cascade_result,
            "rag_rebuilt": rag_rebuilt, "rag_result": rag_result,
            "report_file": str(report_file), "next_step": next_step, "error": error,
        }

    except Exception as exc:
        return {"ok": False, "command": "revise-outline", "project_root": str(project_root), "error": repr(exc)}


# ── 脑洞建图 ──────────────────────────────────────────────────────────────────

def cmd_brainstorm(args: argparse.Namespace) -> Dict[str, Any]:
    """执行 /脑洞建图：交互式脑洞引导 -> 生成 idea_seed.md + plan_generation_prompt.md。"""
    project_root = Path(args.project_root).expanduser().resolve()
    project_structure(project_root)

    init_cmd = ["init", "--project-root", str(project_root)]
    if args.genre:
        init_cmd.extend(["--genre", args.genre])
    if args.idea:
        init_cmd.extend(["--title-hint", args.idea])
    i_code, i_out, _i_err, i_payload = run_python(
        SCRIPT_DIR / "interactive_ideation_engine.py", init_cmd,
    )
    if i_code != 0:
        return {
            "ok": False, "command": "brainstorm", "project_root": str(project_root),
            "error": "ideation_init_failed",
            "init_result": i_payload if i_payload is not None else {"stdout": i_out},
        }

    c_payload: Optional[Dict[str, Any]] = None
    if args.genre or args.idea:
        seed_answers: Dict[str, str] = {}
        if args.genre:
            seed_answers["genre"] = args.genre
        if args.idea:
            seed_answers["hook"] = args.idea
            seed_answers["protagonist_goal"] = args.idea
        c_code, _c_out, _c_err, c_payload = run_python(
            SCRIPT_DIR / "interactive_ideation_engine.py",
            ["collect", "--project-root", str(project_root),
             "--round", "1",
             "--answers", json.dumps(seed_answers, ensure_ascii=False),
             "--use-fallback"],
        )
        if c_code == 0:
            run_python(
                SCRIPT_DIR / "interactive_ideation_engine.py",
                ["advance", "--project-root", str(project_root)],
            )

    g_code, _g_out, _g_err, g_payload = run_python(
        SCRIPT_DIR / "interactive_ideation_engine.py",
        ["generate", "--project-root", str(project_root)],
    )

    generate_succeeded = g_code == 0 and isinstance(g_payload, dict) and g_payload.get("ok")
    if not generate_succeeded:
        prompts_for_user = (
            i_payload.get("prompts", []) if isinstance(i_payload, dict) else []
        )
        fallback_opts = (
            i_payload.get("fallback_options", {}) if isinstance(i_payload, dict) else {}
        )
        return {
            "ok": True, "command": "brainstorm", "project_root": str(project_root),
            "session_started": True, "needs_more_input": True,
            "round_prompts": prompts_for_user, "fallback_options": fallback_opts,
            "init_result": i_payload, "generate_result": g_payload,
            "next_step": (
                "脑洞引导会话已初始化。请逐轮回答以下问题（或使用 collect 子命令收集答案），"
                "完成后执行 generate 生成 idea_seed.md。"
            ),
        }

    return {
        "ok": True, "command": "brainstorm", "project_root": str(project_root),
        "session_started": True, "needs_more_input": False,
        "init_result": i_payload, "collect_result": c_payload,
        "generate_result": g_payload,
        "generated_files": g_payload.get("generated_files", []),
        "next_step": "脑洞种子已生成。请审核 idea_seed.md，然后执行 /一键开书 正式开始写作。",
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="小说流程增强执行器：一键开书 / 继续写")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_one = sub.add_parser("one-click", help="执行 /一键开书")
    p_one.add_argument("--project-root", required=True)
    p_one.add_argument("--title", default="未命名小说")
    p_one.add_argument("--genre", default="待定题材")
    p_one.add_argument("--idea", default="待补充剧情种子")
    p_one.add_argument("--protagonist", default="主角")
    p_one.add_argument("--protagonist-goal", default="明确主角核心目标")
    p_one.add_argument("--core-conflict", default="主线冲突待细化")
    p_one.add_argument("--core-hook", default="高概念卖点待补充")
    p_one.add_argument("--ending", default="开放式结局（可后续修改）")
    p_one.add_argument("--target-words", type=int, default=3000000)
    p_one.add_argument("--target-audience", default="", help="目标读者群体")
    p_one.add_argument("--writing-style", default="", help="写作风格")
    p_one.add_argument("--core-taboo", default="", help="核心禁区")
    p_one.add_argument("--overwrite", action="store_true")
    p_one.add_argument("--emit-json")

    p_brain = sub.add_parser("brainstorm", help="执行 /脑洞建图")
    p_brain.add_argument("--project-root", required=True)
    p_brain.add_argument("--genre", default="", help="预设题材")
    p_brain.add_argument("--idea", default="", help="初始故事想法/书名提示")
    p_brain.add_argument("--rounds", type=int, default=5, help="计划引导轮次")
    p_brain.add_argument("--emit-json")

    p_rev = sub.add_parser("revise-outline", help="执行 /改纲续写")
    p_rev.add_argument("--project-root", required=True)
    p_rev.add_argument("--from-chapter", type=int, required=True,
                       help="改纲生效的起始章节号（含该章，必须 >= 1）")
    p_rev.add_argument("--change-description", default="", help="本次改纲说明")
    p_rev.add_argument("--emit-json")

    p_cont = sub.add_parser("continue-write", help="执行 /继续写")
    p_cont.add_argument("--project-root", required=True)
    p_cont.add_argument("--query", default="推进下一章剧情")
    p_cont.add_argument("--chapter-file")
    p_cont.add_argument("--chapter-title", default="待写")
    p_cont.add_argument("--top-k", type=int, default=4)
    p_cont.add_argument("--candidate-k", type=int, default=12)
    p_cont.add_argument("--force-retrieval", action="store_true")
    p_cont.add_argument("--force-run", action="store_true", help="忽略幂等缓存")
    p_cont.add_argument("--auto-draft", dest="auto_draft", action="store_true", default=True)
    p_cont.add_argument("--no-auto-draft", dest="auto_draft", action="store_false")
    p_cont.add_argument("--auto-improve", dest="auto_improve", action="store_true", default=True)
    p_cont.add_argument("--no-auto-improve", dest="auto_improve", action="store_false")
    p_cont.add_argument("--auto-retry", dest="auto_retry", action="store_true", default=True)
    p_cont.add_argument("--no-auto-retry", dest="auto_retry", action="store_false")
    p_cont.add_argument("--auto-fix-quality", dest="auto_fix_quality", action="store_true", default=True)
    p_cont.add_argument("--no-auto-fix-quality", dest="auto_fix_quality", action="store_false")
    p_cont.add_argument("--auto-fix-kb-misplaced", dest="auto_fix_kb_misplaced", action="store_true", default=True)
    p_cont.add_argument("--no-auto-fix-kb-misplaced", dest="auto_fix_kb_misplaced", action="store_false")
    p_cont.add_argument("--auto-improve-rounds", type=int, default=1)
    p_cont.add_argument("--max-auto-retry-rounds", type=int, default=2)
    p_cont.add_argument("--rollback-on-failure", dest="rollback_on_failure", action="store_true", default=True)
    p_cont.add_argument("--no-rollback-on-failure", dest="rollback_on_failure", action="store_false")
    p_cont.add_argument("--idempotent-cache", dest="idempotent_cache", action="store_true", default=True)
    p_cont.add_argument("--no-idempotent-cache", dest="idempotent_cache", action="store_false")
    p_cont.add_argument("--lock-timeout-sec", type=int, default=1800)
    p_cont.add_argument("--min-chars", type=int, default=2500)
    p_cont.add_argument("--min-paragraphs", type=int, default=8)
    p_cont.add_argument("--pacing-mode", choices=["fast", "standard", "immersive"], default="standard",
                        help="章节节奏模式")
    p_cont.add_argument("--min-dialogue-ratio", type=float, default=0.03)
    p_cont.add_argument("--max-dialogue-ratio", type=float, default=0.7)
    p_cont.add_argument("--min-sentences", type=int, default=8)
    p_cont.add_argument("--min-content-density", type=float, default=0.7)
    p_cont.add_argument("--max-chapter-variance", type=float, default=0.3)
    p_cont.add_argument("--max-ai-phrase-density", type=float, default=0.05)
    p_cont.add_argument("--auto-research", dest="auto_research", action="store_true", default=True)
    p_cont.add_argument("--no-research", dest="auto_research", action="store_false")
    p_cont.add_argument("--draft-provider", choices=["auto", "template", "llm"], default="auto")
    p_cont.add_argument("--llm-provider", default=None)
    p_cont.add_argument("--llm-model", default=None)
    p_cont.add_argument("--llm-api-key", default=None)
    p_cont.add_argument("--enable-constraints", dest="enable_constraints", action="store_true", default=True)
    p_cont.add_argument("--no-constraints", dest="enable_constraints", action="store_false")
    p_cont.add_argument("--auto-graph-update", dest="auto_graph_update", action="store_true", default=True)
    p_cont.add_argument("--no-graph-update", dest="auto_graph_update", action="store_false")
    p_cont.add_argument("--auto-batch-review", dest="auto_batch_review", action="store_true", default=True)
    p_cont.add_argument("--no-batch-review", dest="auto_batch_review", action="store_false")
    p_cont.add_argument("--use-beat-sheet", dest="use_beat_sheet", action="store_true", default=True)
    p_cont.add_argument("--no-beat-sheet", dest="use_beat_sheet", action="store_false")
    p_cont.add_argument("--beat-count", type=int, default=4)
    p_cont.add_argument("--auto-style-update", dest="auto_style_update", action="store_true", default=True)
    p_cont.add_argument("--no-style-update", dest="auto_style_update", action="store_false")
    p_cont.add_argument("--style-update-interval", type=int, default=10)
    p_cont.add_argument("--emit-json")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    _dispatch = {
        "one-click": one_click,
        "brainstorm": cmd_brainstorm,
        "revise-outline": cmd_revise_outline,
        "continue-write": continue_write,
    }
    _handler = _dispatch.get(args.cmd)
    if _handler is None:
        payload: Dict[str, Any] = {"ok": False, "error": f"unknown_command:{args.cmd}"}
    else:
        payload = _handler(args)
    if args.emit_json:
        jp = Path(args.emit_json).expanduser().resolve()
        ensure_dir(jp.parent)
        jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
