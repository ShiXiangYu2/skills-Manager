#!/usr/bin/env python3
"""写前约束注入模块。

负责收集大纲配额、反向刹车、事件推荐、知识图谱上下文等约束，
并将其转换为可注入写作查询的提示行。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import chapter_no_from_name

_SCRIPT_DIR = Path(__file__).resolve().parent


def collect_writing_constraints(
    project_root: Path,
    chapter_path: Path,
    query: str,
) -> Dict[str, Any]:
    """调用三个辅助脚本，汇总约束信息供后续注入 query。

    包括：大纲锚点检查、反向刹车约束、事件矩阵推荐、知识图谱上下文。

    Args:
        project_root: 项目根目录
        chapter_path: 章节文件路径
        query: 写作意图

    Returns:
        约束信息字典
    """
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    chapter_no = chapter_no_from_name(chapter_path.name)
    constraints: Dict[str, Any] = {"query": query, "chapter": chapter_no}

    if chapter_no <= 0:
        constraints["error"] = f"invalid_chapter_no:{chapter_path.name}"
        return constraints

    # 大纲锚点检查
    o_code, o_out, _o_err, o_payload = run_python(
        _SCRIPT_DIR / "outline_anchor_manager.py",
        ["check", "--project-root", str(project_root), "--chapter", str(chapter_no)],
    )
    # 反向刹车约束
    a_code, a_out, _a_err, a_payload = run_python(
        _SCRIPT_DIR / "anti_resolution_guard.py",
        ["constraint", "--project-root", str(project_root)],
    )
    # 事件矩阵推荐
    e_code, e_out, _e_err, e_payload = run_python(
        _SCRIPT_DIR / "event_matrix_scheduler.py",
        ["recommend", "--project-root", str(project_root), "--chapter", str(chapter_no)],
    )

    constraints["outline_constraints"] = o_payload if o_payload is not None else {"stdout": o_out}
    constraints["anti_resolution_constraints"] = a_payload if a_payload is not None else {"stdout": a_out}
    constraints["event_recommendation"] = e_payload if e_payload is not None else {"stdout": e_out}
    constraints["sources_ok"] = {
        "outline_anchor_manager": o_code == 0,
        "anti_resolution_guard": a_code == 0,
        "event_matrix_scheduler": e_code == 0,
    }

    # 图谱上下文注入（已初始化图谱时生效）
    graph_file = project_root / "00_memory" / "story_graph.json"
    if graph_file.exists():
        g_code, _g_out, _g_err, g_payload = run_python(
            _SCRIPT_DIR / "story_graph_builder.py",
            [
                "generate-context",
                "--project-root", str(project_root),
                "--chapter", str(max(chapter_no, 0)),
                "--max-foreshadows", "5",
                "--max-events", "5",
            ],
        )
        if g_code == 0 and isinstance(g_payload, dict) and g_payload.get("ok"):
            constraints["graph_context"] = g_payload

    return constraints


def build_injection_lines(writing_constraints: Optional[Dict[str, Any]]) -> List[str]:
    """从写作约束中提取可注入的提示行。

    Args:
        writing_constraints: collect_writing_constraints 返回的约束字典

    Returns:
        注入行列表
    """
    lines: List[str] = []
    if not isinstance(writing_constraints, dict):
        return lines

    # 大纲约束
    outline_c = writing_constraints.get("outline_constraints")
    if isinstance(outline_c, dict):
        outline_prompt = outline_c.get("constraints_prompt")
        if isinstance(outline_prompt, str) and outline_prompt.strip():
            lines.append(outline_prompt.strip())

    # 反向刹车约束
    anti_c = writing_constraints.get("anti_resolution_constraints")
    if isinstance(anti_c, dict):
        anti_prompt = anti_c.get("constraint_prompt")
        if isinstance(anti_prompt, str) and anti_prompt.strip():
            lines.append(anti_prompt.strip())

    # 事件推荐
    event_rec = writing_constraints.get("event_recommendation")
    if isinstance(event_rec, dict):
        rec_types = event_rec.get("recommended_types")
        if isinstance(rec_types, list) and rec_types:
            lines.append(
                "本章建议优先事件类型：" + "、".join(str(x) for x in rec_types if str(x).strip())
            )
        notes = event_rec.get("notes")
        if isinstance(notes, list):
            note_lines = [str(n).strip() for n in notes if str(n).strip()]
            lines.extend(note_lines)

    # 知识图谱上下文
    graph_ctx = writing_constraints.get("graph_context")
    if isinstance(graph_ctx, dict):
        ctx_prompt = graph_ctx.get("context_prompt", "")
        if isinstance(ctx_prompt, str) and ctx_prompt.strip():
            lines.append(ctx_prompt.strip())

    return lines


def collect_and_inject(
    project_root: Path,
    chapter_path: Path,
    query: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """收集约束并构建注入行。返回 (constraints, injected_lines)。"""
    constraints = collect_writing_constraints(project_root, chapter_path, query)
    lines = build_injection_lines(constraints)
    return constraints, lines
