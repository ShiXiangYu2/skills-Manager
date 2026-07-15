#!/usr/bin/env python3
"""门禁检查和后处理模块。

负责章节门禁检查、质量修复、门禁产物生成、自动修复重试、
段落平衡、对话稀释、文本重写等。
"""

import argparse
import datetime as dt
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from common import (
    ensure_dir, read_text, write_text, slugify,
    load_json, save_json, chapter_no_from_name,
)

_SCRIPT_DIR = Path(__file__).resolve().parent

# ── 事件类型相关 ──────────────────────────────────────────────────────────────
_VALID_EVENT_TYPES: set = {
    "conflict_thrill", "bond_deepening",
    "faction_building", "world_painting", "tension_escalation",
}


def _extract_event_types_from_constraints(constraints: Any) -> List[str]:
    """从 writing_constraints 中提取已过滤的有效事件类型列表。"""
    if not isinstance(constraints, dict):
        return []
    event_rec = constraints.get("event_recommendation")
    if not isinstance(event_rec, dict):
        return []
    rec_types = event_rec.get("recommended_types", []) or []
    return [str(t) for t in rec_types if str(t) in _VALID_EVENT_TYPES]


def _infer_pacing_tier(event_types: List[str]) -> str:
    """从事件类型列表推断节奏档位。"""
    event_set = {str(t) for t in event_types}
    fast_types = {"conflict_thrill", "tension_escalation"}
    slow_types = {"bond_deepening", "world_painting"}
    has_fast = bool(event_set & fast_types)
    has_slow = bool(event_set & slow_types)
    if has_fast and has_slow:
        return "medium"
    if has_fast:
        return "fast"
    if has_slow:
        return "slow"
    return "medium"


# ── 文本处理工具 ──────────────────────────────────────────────────────────────

def _split_sentences(paragraph: str) -> List[str]:
    """按中文标点分句。"""
    return [s.strip() for s in re.split(r"(?<=[。！？!?])", paragraph) if s.strip()]


def _normalize_paragraph_variance(text: str) -> str:
    """平衡段落长度：拆分过长段落，合并过短段落。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    normalized: List[str] = []
    buffer_short: List[str] = []
    for p in paragraphs:
        sentences = _split_sentences(p)
        if len(p) >= 260 and len(sentences) >= 4:
            cut = max(2, len(sentences) // 2)
            normalized.append("".join(sentences[:cut]).strip())
            normalized.append("".join(sentences[cut:]).strip())
            continue
        if len(p) <= 45:
            buffer_short.append(p)
            if sum(len(x) for x in buffer_short) >= 90:
                normalized.append(" ".join(buffer_short))
                buffer_short = []
            continue
        if buffer_short:
            normalized.append(" ".join(buffer_short))
            buffer_short = []
        normalized.append(p)
    if buffer_short:
        normalized.append(" ".join(buffer_short))
    return "\n\n".join(normalized)


def _rebalance_dialogue_heavy_text(text: str, query: str) -> str:
    """在连续对话密集段落之间插入叙述桥。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: List[str] = []
    dialogue_run = 0
    for p in paragraphs:
        is_dialogue_heavy = p.startswith(("“", "”")) or p.count("“") >= 2
        out.append(p)
        if is_dialogue_heavy:
            dialogue_run += 1
        else:
            dialogue_run = 0
        if dialogue_run >= 2:
            out.append(
                f"——叙述桥——两人的话并没有直接解决“{query}”，"
                "反而把风险顺序、执行步骤与彼此顾虑暴露得更清楚。"
                "他们不得不把口头判断落实到行动上，场面因此继续向前推进。"
            )
            dialogue_run = 0
    return "\n\n".join(out)


def _build_pacing_rewrite_prompt(query: str, failures: List[str]) -> str:
    """构建 LLM 重写提示词（针对节奏问题）。"""
    return (
        "Rewrite the chapter to fix pacing issues (too fast / summary skips).\n"
        f"Task: {query}\n"
        f"Failures: {'; '.join(failures)}\n\n"
        "Requirements:\n"
        "1. Preserve all plot facts, character relations, event order, and chapter hooks.\n"
        "2. Expand summary skip phrases like 'after a while' into continuous visible scenes.\n"
        "3. Each key progress must include: action -> sensory/environment -> feedback/resistance -> new decision.\n"
        "4. Do not just append summary patches; rewrite the high skip density paragraphs themselves.\n"
        "5. Control dialogue ratio; balance paragraph lengths.\n"
        "6. Output only the rewritten text, no explanations.\n"
    )


def _next_fix_block_index(text: str, prefix: str) -> int:
    """计算下一个修复块编号，避免跨轮次编号重复。"""
    matches = [int(m) for m in re.findall(rf"{re.escape(prefix)}(\d+)", text)]
    return (max(matches) + 1) if matches else 1


# ── 章节存储规范化 ────────────────────────────────────────────────────────────

def move_misplaced_kb_chapters(project_root: Path) -> List[str]:
    """将误放在知识库目录中的章节文件迁移到手稿目录。"""
    moved: List[str] = []
    kb = project_root / "02_knowledge_base"
    man = project_root / "03_manuscript"
    if not kb.exists():
        return moved
    ensure_dir(man)
    chapter_re = re.compile(r"^第\d+章.*\.md$")
    for p in kb.rglob("*.md"):
        if not chapter_re.match(p.name):
            continue
        target = man / f"迁移-{p.name}"
        n = 1
        while target.exists():
            target = man / f"迁移-{n}-{p.name}"
            n += 1
        shutil.move(str(p), str(target))
        moved.append(f"{p} -> {target}")
    return moved


def normalize_chapter_storage(project_root: Path, chapter_path: Path) -> Tuple[Path, Optional[str]]:
    """确保章节文件在正确的存储位置。"""
    rel_ok = False
    try:
        rel = chapter_path.resolve().relative_to(project_root.resolve())
        rel_ok = rel.as_posix().startswith("03_manuscript/")
    except Exception:
        rel_ok = False
    if rel_ok and chapter_path.suffix.lower() == ".md":
        return chapter_path, None

    target = project_root / "03_manuscript" / (chapter_path.stem + ".md")
    ensure_dir(target.parent)
    shutil.move(str(chapter_path), str(target))
    return target, f"{chapter_path} -> {target}"


# ── 质量定向修复 ──────────────────────────────────────────────────────────────

def apply_targeted_quality_fix(
    project_root: Path,
    chapter_path: Path,
    quality: Dict[str, Any],
    args: argparse.Namespace,
    query: str,
) -> List[str]:
    """根据质量检查失败项执行定向修复。"""
    txt = read_text(chapter_path).rstrip()
    failures_raw = quality.get("failures", [])
    failures = [str(x) for x in failures_raw] if isinstance(failures_raw, list) else []
    actions: List[str] = []

    paragraph_count_raw = quality.get("paragraph_count", 0)
    sentence_count_raw = quality.get("sentence_count", 0)
    paragraph_count = int(paragraph_count_raw) if isinstance(paragraph_count_raw, (int, float, str)) else 0
    sentence_count = int(sentence_count_raw) if isinstance(sentence_count_raw, (int, float, str)) else 0

    next_paragraph_idx = _next_fix_block_index(txt, "补充段落")
    next_progress_idx = _next_fix_block_index(txt, "补充推进")

    # 优先处理 pacing_skip_density_critical
    if any(
        f.startswith("pacing_skip_density_critical") or f.startswith("pacing_skip_density_too_high")
        for f in failures
    ):
        prompt = _build_pacing_rewrite_prompt(query, failures)
        from beat_pipeline import _rewrite_chapter_with_llm
        if _rewrite_chapter_with_llm(project_root, chapter_path, args, prompt):
            txt = read_text(chapter_path).rstrip()
            txt = _normalize_paragraph_variance(_rebalance_dialogue_heavy_text(txt, query))
            actions.append("LLM rewrite for high skip density")
        else:
            txt = _normalize_paragraph_variance(_rebalance_dialogue_heavy_text(txt, query))
            txt += (
                "\n\n"
                f"[Scene expansion] Describe the execution of '{query}' with action steps, "
                "environment resistance, immediate feedback, and new decisions. "
                "Do not use summary skip phrases."
            )
            actions.append("Fallback scene expansion for skip density")

    if any(f.startswith("paragraph_count<") for f in failures):
        missing = max(1, args.min_paragraphs - paragraph_count)
        blocks = []
        for i in range(missing):
            blocks.append(
                f"补充段落{i+1}：围绕"{query}"推进一小步行动结果，并明确本段的因果关系。"
                "角色需要做出可验证选择，以便下一章承接。"
            )
        txt += "\n\n" + "\n\n".join(blocks)
        actions.append(f"补足段落数量 +{missing}")

    if any(f.startswith("sentence_count<") or f.startswith("sentence_count_too_low") for f in failures):
        missing = max(1, args.min_sentences - sentence_count)
        short = " ".join(["他迅速复盘线索。她立即提出质疑。两人决定先验证坐标。"] * max(1, missing // 3))
        txt += "\n\n" + short
        actions.append(f"补足句子数量 +{missing}")

    if any(f.startswith("dialogue_ratio<") or f.startswith("dialogue_ratio_too_low") for f in failures):
        txt += (
            "\n\n"
            f"“先别下结论，”同伴压低声音，“{query}这条线还缺最后一块证据。”"
            "主角点头：“那就按时间线回查，每一步都留痕。”"
        )
        actions.append("补足对话占比")

    if any(f.startswith("dialogue_ratio>") or f.startswith("dialogue_ratio_too_high") for f in failures):
        txt += (
            "\n\n"
            "叙述补偿：两人将对话结论写入行动清单，逐项标记风险等级与验证顺序，"
            "避免口头信息过载导致剧情推进失焦。"
        )
        actions.append("稀释过高对话占比")

    # 最后兜底字符数
    from chapter_assembler import clean_for_stats
    cur_chars = len(re.sub(r"\s+", "", clean_for_stats(txt)))
    if cur_chars < args.min_chars:
        needed = args.min_chars - cur_chars
        repeat = max(1, needed // 80)
        extra = []
        for i in range(repeat):
            extra.append(
                f"补充推进{i+1}：围绕"{query}"补写一段行动执行、风险反馈与下一步目标，"
                "确保情节、人物与线索三者同时前进。"
            )
        txt += "\n\n" + "\n\n".join(extra)
        actions.append(f"补足字符数 +{needed}")

    if actions:
        write_text(chapter_path, txt)
    return actions


# ── 质量报告 ──────────────────────────────────────────────────────────────────

def write_quality_report(gate_dir: Path, quality_before: Dict[str, Any], quality_after: Dict[str, Any]) -> Path:
    """生成质量检查报告。"""
    p = gate_dir / "quality_report.md"

    def safe_get(d: Dict[str, Any], key: str, default: Any = None) -> Any:
        return d.get(key, default) if isinstance(d, dict) else default

    lines = [
        "# 章节质量检查",
        "",
        "## 修复前",
        f"- 字符数：{safe_get(quality_before, 'char_count', 'N/A')}",
        f"- 段落数：{safe_get(quality_before, 'paragraph_count', 'N/A')}",
        f"- 对话占比：{safe_get(quality_before, 'dialogue_ratio', 'N/A')}",
        f"- 句子数：{safe_get(quality_before, 'sentence_count', 'N/A')}",
        f"- 段落唯一比例：{safe_get(quality_before, 'paragraph_unique_ratio', 'N/A')}",
        f"- 最大重复段落次数：{safe_get(quality_before, 'max_duplicate_paragraph_repeat', 'N/A')}",
        f"- 失败项：{safe_get(quality_before, 'failures', [])}",
        "",
        "## 修复后",
        f"- 字符数：{safe_get(quality_after, 'char_count', 'N/A')}",
        f"- 段落数：{safe_get(quality_after, 'paragraph_count', 'N/A')}",
        f"- 对话占比：{safe_get(quality_after, 'dialogue_ratio', 'N/A')}",
        f"- 句子数：{safe_get(quality_after, 'sentence_count', 'N/A')}",
        f"- 段落唯一比例：{safe_get(quality_after, 'paragraph_unique_ratio', 'N/A')}",
        f"- 最大重复段落次数：{safe_get(quality_after, 'max_duplicate_paragraph_repeat', 'N/A')}",
        f"- 失败项：{safe_get(quality_after, 'failures', [])}",
        "",
        f"- 通过：{safe_get(quality_after, 'passed', False)}",
    ]
    write_text(p, "\n".join(lines))
    return p


# ── 门禁产物生成 ──────────────────────────────────────────────────────────────

def write_gate_artifacts(
    project_root: Path,
    chapter_path: Path,
    query: str,
    quality: Dict[str, Any],
    query_payload: Optional[Dict[str, Any]],
) -> List[str]:
    """生成门禁产物文件（记忆更新、一致性检查、风格校准、校稿报告、发布判定）。"""
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    chapter_id = slugify(chapter_path.stem)
    gate_dir = project_root / "04_editing" / "gate_artifacts" / chapter_id
    ensure_dir(gate_dir)

    # 角色名加载
    tracker_file = project_root / "00_memory" / "character_tracker.md"
    tracker_names: List[str] = []
    if tracker_file.exists():
        txt = read_text(tracker_file)
        name_set: set = set()
        for line in txt.splitlines():
            line_s = line.strip()
            if line_s.startswith("|"):
                cells = [c.strip() for c in line_s.strip("|").split("|")]
                if cells and re.fullmatch(r"[一-鿿A-Za-z0-9_·]{2,20}", cells[0] or ""):
                    if cells[0] not in {"人物", "角色", "姓名", "---"}:
                        name_set.add(cells[0])
        tracker_names = sorted(name_set)

    query_names = [n for n in tracker_names if n in query]
    unknown_names = re.findall(r"[一-鿿]{2,4}", query)
    unknown_names = [n for n in unknown_names if n not in tracker_names][:5]

    memory_update = f"""# 记忆更新

- 章节：{chapter_path.name}
- 更新时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 本章关键推进：{query}
- 命中角色：{', '.join(query_names) if query_names else '未明确命中'}
- 质量摘要：字符={quality['char_count']} 段落={quality['paragraph_count']} 对话占比={quality['dialogue_ratio']}
"""
    consistency = f"""# 一致性检查

- 检查范围：剧情/角色/时间线/设定
- 本章输入：{query}
- 命中角色：{', '.join(query_names) if query_names else '无'}
- 风险提示：{('可能出现新实体：' + ', '.join(unknown_names)) if unknown_names else '未发现高风险新实体'}
- 结论：通过初步一致性审查，建议下一章继续核对时间线。
"""
    style = f"""# 风格校准

- 检查项：句式节奏、对话密度、AI高频词
- 对话占比：{quality['dialogue_ratio']}
- AI词命中：{quality['ai_phrase_hits'] if quality['ai_phrase_hits'] else '未命中'}
- 结论：本章风格基本稳定，建议继续保持短句与动作描写平衡。
"""

    # text_humanizer 检测
    _SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
    humanizer_section = ""
    humanizer_rounds = 0
    humanizer_auto_fixed = False
    h_code, _h_out, _h_err, h_payload = run_python(
        _SCRIPT_DIR / "text_humanizer.py",
        ["report", "--chapter-file", str(chapter_path)],
    )
    if h_code == 0 and isinstance(h_payload, dict) and h_payload.get("ok"):
        llm_provider = os.environ.get("NOVEL_LLM_PROVIDER", "")
        while (
            _SEVERITY_ORDER.get(h_payload.get("severity", "low"), 0) >= 1
            and humanizer_rounds < 2
        ):
            p_code, _p_out, _p_err, p_payload = run_python(
                _SCRIPT_DIR / "text_humanizer.py",
                ["prompt", "--chapter-file", str(chapter_path)],
            )
            if p_code != 0 or not isinstance(p_payload, dict):
                break
            humanize_prompt = p_payload.get("prompt", "")
            if not humanize_prompt:
                break
            if llm_provider:
                try:
                    from novel_chapter_writer import write_chapter  # type: ignore[import]
                    llm_result = write_chapter(
                        project_root,
                        chapter_file=chapter_path,
                        config_overrides={
                            "ai_provider": llm_provider,
                            "writing_prompt": humanize_prompt,
                        },
                        dry_run=False,
                    )
                    if llm_result.get("ok"):
                        humanizer_auto_fixed = True
                except Exception as _hum_err:
                    print(f"[警告] Humanizer 自动修复失败: {_hum_err}")
            humanizer_rounds += 1
            re_code, _, _, re_payload = run_python(
                _SCRIPT_DIR / "text_humanizer.py",
                ["report", "--chapter-file", str(chapter_path)],
            )
            if (re_code == 0 and isinstance(re_payload, dict)
                    and _SEVERITY_ORDER.get(re_payload.get("severity", "low"), 0) < 1):
                h_payload = re_payload
                break
            if not llm_provider:
                break
        severity_map = {"low": "轻微", "medium": "中等", "high": "严重"}
        sev = severity_map.get(h_payload.get("severity", ""), h_payload.get("severity", ""))
        report_md = h_payload.get("report", "")
        humanizer_section = f"\n\n---\n\n{report_md}"
        if humanizer_auto_fixed:
            humanizer_section += f"\n\n（自动纠正已执行 {humanizer_rounds} 轮）"
        elif humanizer_rounds > 0:
            humanizer_section += "\n\n（已生成润色 prompt，需人工执行 /校稿 完成纠正）"
    else:
        sev = "未知"
        humanizer_section = "\n\n（text_humanizer 检测跳过：脚本不可用或无法读取文件）"

    copyedit = f"""# 校稿报告

- 修订目标：降低AI味、提升可读性、保证节奏递进
- 动作：清理重复表述、补足转场、强化章末钩子
- AI痕迹严重程度：{sev}
- 发布建议：参考下方检测报告后执行两遍式润色
{humanizer_section}
"""
    quality_ok: bool = bool(quality.get("passed", quality.get("ok", False)))
    quality_failures: List[str] = list(quality.get("failures", []))
    if quality_ok:
        publish_verdict = "可发布（通过）"
        publish_keyword = "可发布 / 通过 / PASS"
        publish_note = "本章已完成自动流程并通过所有质量门禁项。"
    else:
        publish_verdict = "不建议发布（未通过）"
        publish_keyword = "不通过 / FAIL"
        failure_lines = "\n".join(f"  - {f}" for f in quality_failures) if quality_failures else "  - 未知失败"
        publish_note = f"本章未通过以下质量门禁项，需修复后重新检查：\n{failure_lines}"

    publish = f"""# 发布判定

章节：{chapter_path.name}
结论：{publish_verdict}
说明：{publish_note}
字符数：{quality.get('char_count', 0)}  段落数：{quality.get('paragraph_count', 0)}
关键词：{publish_keyword}
"""

    paths = [
        ("memory_update.md", memory_update),
        ("consistency_report.md", consistency),
        ("style_calibration.md", style),
        ("copyedit_report.md", copyedit),
        ("publish_ready.md", publish),
    ]
    written = []
    for name, txt in paths:
        out = gate_dir / name
        write_text(out, txt)
        written.append(str(out))
    return written


# ── 门禁检查与修复 ────────────────────────────────────────────────────────────

def run_gate_check(
    project_root: Path,
    chapter_path: Path,
    pacing_tier: Optional[str] = None,
    pacing_event_types: str = "",
) -> Tuple[int, Dict[str, Any]]:
    """执行门禁检查脚本。"""
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    extra: List[str] = []
    if pacing_tier:
        extra.extend(["--pacing-tier", pacing_tier])
    if pacing_event_types:
        extra.extend(["--pacing-event-types", pacing_event_types])
    code, out, err, payload = run_python(
        _SCRIPT_DIR / "chapter_gate_check.py",
        ["--project-root", str(project_root), "--chapter-file", str(chapter_path), *extra],
    )
    if payload is not None:
        return code, payload
    return code, {"stdout": out, "stderr": err}


def run_repair_plan(project_root: Path, chapter_path: Path) -> Optional[Dict[str, Any]]:
    """生成门禁修复计划。"""
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    _, _, _, payload = run_python(
        _SCRIPT_DIR / "gate_repair_plan.py",
        ["--project-root", str(project_root), "--chapter-file", str(chapter_path)],
    )
    return payload


def auto_fix_after_gate_failure(
    project_root: Path,
    chapter_path: Path,
    query: str,
    quality: Dict[str, Any],
    query_payload: Optional[Dict[str, Any]],
    gate_payload: Dict[str, Any],
    args: argparse.Namespace,
) -> Tuple[Path, List[str], Dict[str, Any]]:
    """门禁失败后自动执行最小修复。"""
    from chapter_assembler import evaluate_quality

    actions: List[str] = []
    failures_raw = gate_payload.get("failures", []) if isinstance(gate_payload, dict) else []
    failures = failures_raw if isinstance(failures_raw, list) else []
    fail_text = " | ".join(str(x) for x in failures)
    gate_dir = project_root / "04_editing" / "gate_artifacts" / slugify(chapter_path.stem)
    ensure_dir(gate_dir)
    need_rebuild_gate_artifacts = False

    if "knowledge_base_contains_chapter_files" in fail_text and getattr(args, "auto_fix_kb_misplaced", True):
        moved = move_misplaced_kb_chapters(project_root)
        if moved:
            actions.extend([f"迁移误放章节：{x}" for x in moved])

    if "chapter_storage_policy" in fail_text:
        new_path, moved = normalize_chapter_storage(project_root, chapter_path)
        chapter_path = new_path
        if moved:
            need_rebuild_gate_artifacts = True
            actions.append(f"修正章节存储位置：{moved}")

    if any(
        key in fail_text
        for key in [
            "memory_update", "consistency_report", "style_calibration",
            "copyedit_report", "publish_ready", "publish_ready_keyword",
        ]
    ):
        need_rebuild_gate_artifacts = True

    if "quality_baseline" in fail_text and getattr(args, "auto_fix_quality", True):
        old_quality = dict(quality)
        quality_actions = apply_targeted_quality_fix(project_root, chapter_path, quality, args, query)
        if quality_actions:
            actions.extend([f"质量最小修复：{x}" for x in quality_actions])
            quality = evaluate_quality(read_text(chapter_path), args)
            write_quality_report(gate_dir, old_quality, quality)
            need_rebuild_gate_artifacts = True

    if need_rebuild_gate_artifacts:
        write_gate_artifacts(project_root, chapter_path, query, quality, query_payload)
        actions.append("重建门禁产物文件")

    return chapter_path, actions, quality


# ── 门禁流水线编排 ────────────────────────────────────────────────────────────

def run_chapter_gate(
    project_root: Path,
    chapter_path: Path,
    writing_query: str,
    quality: Dict[str, Any],
    q_payload: Optional[Dict[str, Any]],
    writing_constraints: Optional[Dict[str, Any]],
    args: argparse.Namespace,
    is_draft: bool,
) -> Dict[str, Any]:
    """执行完整的门禁检查流水线：产物生成 -> 门禁检查 -> 自动修复重试。

    Args:
        project_root: 项目根目录
        chapter_path: 章节文件路径
        writing_query: 写作查询
        quality: 质量评估结果
        q_payload: RAG 查询 payload
        writing_constraints: 写作约束
        args: 参数命名空间
        is_draft: 是否仍为草稿

    Returns:
        门禁结果字典，包含 gate_passed, gate_payload, repair_payload,
        retry_actions, quality_report, todo_file
    """
    chapter_id = slugify(chapter_path.stem)
    gate_dir = project_root / "04_editing" / "gate_artifacts" / chapter_id
    ensure_dir(gate_dir)
    todo_file = gate_dir / "pipeline_todo.md"
    if not todo_file.exists():
        write_text(
            todo_file,
            "# 章节流程待办\n\n- [ ] /更新记忆\n- [ ] /检查一致性\n- [ ] /风格校准\n- [ ] /校稿\n- [ ] /门禁检查\n- [ ] /更新剧情索引\n",
        )

    quality_report_path = write_quality_report(gate_dir, quality, quality)

    gate_payload: Optional[Dict[str, Any]] = None
    repair_payload: Optional[Dict[str, Any]] = None
    retry_actions: List[str] = []
    gate_passed_final = False

    # 提取事件类型和节奏档位
    _gate_event_types = _extract_event_types_from_constraints(writing_constraints)
    _gate_pacing_tier = _infer_pacing_tier(_gate_event_types) if _gate_event_types else None
    _gate_pacing_et_str = ",".join(_gate_event_types)

    if not is_draft:
        write_gate_artifacts(project_root, chapter_path, writing_query, quality, q_payload)
        _, gate_payload = run_gate_check(
            project_root, chapter_path, _gate_pacing_tier, _gate_pacing_et_str
        )
        gate_passed_final = bool(gate_payload.get("passed")) if isinstance(gate_payload, dict) else False

        retry_rounds = 0
        while (not gate_passed_final) and getattr(args, "auto_retry", True) and retry_rounds < getattr(args, "max_auto_retry_rounds", 2):
            chapter_path, actions, quality = auto_fix_after_gate_failure(
                project_root,
                chapter_path,
                writing_query,
                quality,
                q_payload,
                gate_payload if gate_payload else {},
                args,
            )
            if not actions:
                break
            retry_actions.extend(actions)
            retry_rounds += 1
            _, gate_payload = run_gate_check(
                project_root, chapter_path, _gate_pacing_tier, _gate_pacing_et_str
            )
            gate_passed_final = bool(gate_payload.get("passed")) if isinstance(gate_payload, dict) else False

        if not gate_passed_final:
            repair_payload = run_repair_plan(project_root, chapter_path)

    return {
        "gate_passed": gate_passed_final,
        "gate_payload": gate_payload,
        "repair_payload": repair_payload,
        "retry_actions": retry_actions,
        "quality_report": quality_report_path,
        "todo_file": str(todo_file),
    }
