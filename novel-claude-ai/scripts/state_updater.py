#!/usr/bin/env python3
"""状态更新模块。

负责流程指标更新、门禁通过后的图谱/大纲/事件/风格等状态同步。
"""

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import (
    ensure_dir, load_json, save_json, save_json_atomic,
    chapter_no_from_name,
)

_SCRIPT_DIR = Path(__file__).resolve().parent


def update_flow_metrics(project_root: Path, item: Dict[str, Any]) -> Dict[str, Any]:
    """更新流程运行指标并生成汇总统计。

    Args:
        project_root: 项目根目录
        item: 本次运行的指标数据

    Returns:
        汇总统计字典
    """
    retrieval_dir = project_root / "00_memory" / "retrieval"
    ensure_dir(retrieval_dir)
    metrics_file = retrieval_dir / "flow_metrics.json"
    metrics = load_json(metrics_file, {"runs": []})
    runs = metrics.get("runs", [])
    if not isinstance(runs, list):
        runs = []
    runs.append(item)
    runs = runs[-300:]
    metrics["runs"] = runs
    save_json_atomic(metrics_file, metrics)

    total = len(runs)
    ok_count = sum(1 for r in runs if r.get("ok"))
    gate_ok = sum(1 for r in runs if r.get("gate_passed_final"))
    retry_count = sum(1 for r in runs if (r.get("auto_retry_actions_count", 0) > 0))
    idempotent_hits = sum(1 for r in runs if r.get("idempotent_hit"))
    avg_runtime = round(sum(float(r.get("runtime_ms", 0)) for r in runs) / total, 2) if total else 0.0
    avg_ctx_chars = round(sum(float(r.get("retrieval_context_chars", 0)) for r in runs) / total, 2) if total else 0.0
    avg_candidates = round(sum(float(r.get("retrieval_candidates", 0)) for r in runs) / total, 2) if total else 0.0

    summary = {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_runs": total,
        "ok_rate": round(ok_count / total, 4) if total else 0.0,
        "gate_pass_rate": round(gate_ok / total, 4) if total else 0.0,
        "retry_rate": round(retry_count / total, 4) if total else 0.0,
        "idempotent_hit_rate": round(idempotent_hits / total, 4) if total else 0.0,
        "avg_runtime_ms": avg_runtime,
        "avg_retrieval_context_chars": avg_ctx_chars,
        "avg_retrieval_candidates": avg_candidates,
    }
    save_json_atomic(retrieval_dir / "flow_metrics_summary.json", summary)
    return summary


def run_post_gate_updates(
    project_root: Path,
    chapter_path: Path,
    manuscript_dir: Path,
    writing_constraints: Optional[Dict[str, Any]],
    gate_passed: bool,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """门禁通过后执行所有状态更新。

    包括：图谱更新、批量审核、大纲锚点推进、事件矩阵记录、风格基准更新。

    Args:
        project_root: 项目根目录
        chapter_path: 章节文件路径
        manuscript_dir: 手稿目录
        writing_constraints: 写作约束
        gate_passed: 门禁是否通过
        args: 参数命名空间

    Returns:
        更新结果字典
    """
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python
    from gate_checker import _infer_pacing_tier, _extract_event_types_from_constraints

    result: Dict[str, Any] = {
        "graph_update_file": None,
        "batch_review_task": None,
        "style_update_file": None,
        "rag_index_rebuilt": False,
    }

    if not gate_passed or not chapter_path:
        return result

    _chapter_no = chapter_no_from_name(chapter_path.name)

    # RAG 索引重建（始终执行）
    b_code, b_out, b_err, b_payload = run_python(
        _SCRIPT_DIR / "plot_rag_retriever.py",
        ["build", "--project-root", str(project_root)],
    )
    result["rag_index_rebuilt"] = b_code == 0

    if _chapter_no <= 0:
        return result

    # 图谱更新
    if getattr(args, "auto_graph_update", True):
        _, _g_out, _g_err, _g_payload = run_python(
            _SCRIPT_DIR / "story_graph_updater.py",
            ["extract", "--project-root", str(project_root),
             "--chapter", str(_chapter_no), "--chapter-file", str(chapter_path)],
        )
        if isinstance(_g_payload, dict):
            result["graph_update_file"] = _g_payload.get("update_file")
        if isinstance(_g_payload, dict) and _g_payload.get("ok"):
            run_python(
                _SCRIPT_DIR / "story_graph_updater.py",
                ["apply", "--project-root", str(project_root),
                 "--chapter", str(_chapter_no)],
            )

    # 批量审核（每10章）
    if getattr(args, "auto_batch_review", True):
        _chapter_numbers = sorted({
            chapter_no_from_name(p.name)
            for p in manuscript_dir.glob("*.md")
            if p.is_file() and chapter_no_from_name(p.name) > 0
        })
        _chapter_count = len(_chapter_numbers)
        if _chapter_count > 0 and _chapter_count % 10 == 0:
            _batch_start = _chapter_count - 9
            _batch_end = _chapter_count
            _, _r_out, _r_err, _r_payload = run_python(
                _SCRIPT_DIR / "cross_agent_reviewer.py",
                ["batch-review", "--project-root", str(project_root),
                 "--chapter-start", str(_batch_start), "--chapter-end", str(_batch_end)],
            )
            if isinstance(_r_payload, dict):
                result["batch_review_task"] = _r_payload.get("task_file")

    # 大纲锚点推进
    if getattr(args, "enable_constraints", True):
        run_python(
            _SCRIPT_DIR / "outline_anchor_manager.py",
            ["advance", "--project-root", str(project_root),
             "--to-chapter", str(_chapter_no + 1)],
        )

    # 事件矩阵记录 + 节奏档位记录
    if getattr(args, "enable_constraints", True) and writing_constraints:
        _filtered_types = _extract_event_types_from_constraints(writing_constraints)
        if _filtered_types:
            run_python(
                _SCRIPT_DIR / "event_matrix_scheduler.py",
                ["record", "--project-root", str(project_root),
                 "--chapter", str(_chapter_no),
                 "--types", ",".join(_filtered_types)],
            )
            _pacing_tier = _infer_pacing_tier(_filtered_types)
            run_python(
                _SCRIPT_DIR / "pacing_tracker.py",
                ["record", "--project-root", str(project_root),
                 "--chapter", str(_chapter_no),
                 "--tier", _pacing_tier,
                 "--event-types", ",".join(_filtered_types)],
            )

    # 风格基准自动更新
    if getattr(args, "auto_style_update", True):
        _style_interval = getattr(args, "style_update_interval", 10)
        _all_chapters = sorted({
            chapter_no_from_name(p.name)
            for p in manuscript_dir.glob("*.md")
            if p.is_file() and chapter_no_from_name(p.name) > 0
        })
        _chapter_count = len(_all_chapters)
        if _chapter_count > 0 and _chapter_count % _style_interval == 0:
            recent_chapters = sorted(
                [p for p in manuscript_dir.glob("*.md") if p.is_file()],
                key=lambda p: chapter_no_from_name(p.name),
                reverse=True,
            )[:_style_interval]
            if recent_chapters:
                style_args = (
                    [str(p) for p in recent_chapters]
                    + ["--profile-name", f"auto_ch{_chapter_count}",
                       "--project-root", str(project_root)]
                )
                st_code, _st_out, _st_err, st_payload = run_python(
                    _SCRIPT_DIR / "style_fingerprint.py", style_args
                )
                if st_code == 0 and isinstance(st_payload, dict):
                    _st_outputs = st_payload.get("outputs", {})
                    if isinstance(_st_outputs, dict):
                        result["style_update_file"] = (
                            _st_outputs.get("project_profile")
                            or _st_outputs.get("global_profile")
                            or ""
                        )

    return result
