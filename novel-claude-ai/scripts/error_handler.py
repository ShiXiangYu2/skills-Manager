#!/usr/bin/env python3
"""错误处理和恢复模块。

负责构建最终结果字典、异常处理（含回滚）、流程指标记录、缓存管理。
"""

import datetime as dt
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from common import (
    ensure_dir, read_text, write_text, slugify,
    file_sha1, load_json, save_json, chapter_no_from_name,
)

_SCRIPT_DIR = Path(__file__).resolve().parent


def build_lock_error(
    project_root: Path,
    run_id: str,
    lock_holder: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建锁冲突错误结果。"""
    from state_updater import update_flow_metrics

    update_flow_metrics(project_root, {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": False,
        "gate_passed_final": False,
        "runtime_ms": 0,
        "query_length": 0,
        "retrieval_context_chars": 0,
        "retrieval_candidates": 0,
        "auto_retry_actions_count": 0,
        "idempotent_hit": False,
    })
    return {
        "ok": False,
        "command": "continue-write",
        "project_root": str(project_root),
        "error": "another_run_in_progress",
        "lock_holder": lock_holder,
        "next_step": "检测到另一个 /继续写 正在执行，请稍后重试或清理过期锁。",
    }


def build_success_result(
    *,
    project_root: Path,
    chapter_path: Path,
    original_chapter_path: Path,
    query: str,
    q_code: int,
    q_out: str,
    q_err: str,
    q_payload: Optional[Dict[str, Any]],
    writing_constraints: Optional[Dict[str, Any]],
    snapshot_path: Optional[Path],
    created_stub: bool,
    draft_info: Dict[str, Any],
    quality_before: Dict[str, Any],
    quality_after: Dict[str, Any],
    quality_report_path: Path,
    improve_rounds: int,
    gate_result: Dict[str, Any],
    post_gate_updates: Dict[str, Any],
    research_gaps: Optional[Dict[str, Any]],
    retrieval_stats: Dict[str, Any],
    request_id: str,
    chapter_hash_before: str,
    run_id: str,
    started_at: float,
    args: Any,
    flow_dir: Path,
    rollback_applied: bool,
) -> Dict[str, Any]:
    """构建成功结果字典。"""
    from state_updater import update_flow_metrics
    from rag_loader import rebuild_rag_index

    gate_passed = gate_result.get("gate_passed", False)
    is_draft = draft_info.get("is_draft", False)
    ok = (q_code == 0 and (is_draft or gate_passed))

    runtime_ms = round((time.time() - started_at) * 1000, 2)

    result: Dict[str, Any] = {
        "ok": ok,
        "command": "continue-write",
        "project_root": str(project_root),
        "chapter_file": str(chapter_path) if chapter_path else "",
        "pacing_mode": draft_info.get("pacing_mode", "standard"),
        "created_chapter_stub": created_stub,
        "auto_draft_applied": draft_info.get("applied", False),
        "draft_provider_used": draft_info.get("mode", "unknown"),
        "fallback_applied": draft_info.get("fallback", False),
        "llm_error_msg": draft_info.get("error_msg"),
        "awaiting_draft": is_draft,
        "quality_before": quality_before,
        "quality_after": quality_after,
        "quality_report": str(quality_report_path),
        "auto_improve_rounds_used": improve_rounds,
        "query_result": q_payload if q_payload is not None else {"stdout": q_out, "stderr": q_err},
        "gate_result": gate_result.get("gate_payload"),
        "gate_passed_final": gate_passed,
        "auto_retry_actions": gate_result.get("retry_actions", []),
        "repair_result": gate_result.get("repair_payload"),
        "index_result": {"rebuilt": post_gate_updates.get("rag_index_rebuilt", False)},
        "todo_file": gate_result.get("todo_file", ""),
        "run_id": run_id,
        "request_id": request_id,
        "idempotent_hit": False,
        "snapshot_file": str(snapshot_path) if snapshot_path else None,
        "rollback_applied": rollback_applied,
        "runtime_ms": runtime_ms,
        "chapter_hash_before": chapter_hash_before,
        "chapter_hash_after": file_sha1(chapter_path) if chapter_path and chapter_path.exists() else "",
        "research_gaps": research_gaps,
        "writing_constraints": writing_constraints,
        "graph_update_file": post_gate_updates.get("graph_update_file"),
        "batch_review_task": post_gate_updates.get("batch_review_task"),
        "style_update_file": post_gate_updates.get("style_update_file") if gate_passed and chapter_path else None,
    }

    # next_step 判断
    if is_draft and not getattr(args, "auto_draft", True):
        result["next_step"] = "章节仍是占位草稿，请补全正文后再次执行 /继续写，或启用 --auto-draft。"
    elif is_draft:
        result["next_step"] = "已尝试自动成稿但仍检测到占位标记，请手动补全正文后再执行。"
    elif draft_info.get("fallback") and draft_info.get("error_msg"):
        result["next_step"] = (
            f"LLM写作失败({draft_info['error_msg']})，已自动回退到模板模式。"
            "请检查API配置后重试。"
        )
    elif gate_passed:
        result["next_step"] = "章节已通过门禁，可进入下一章。"
    else:
        result["next_step"] = "章节未通过门禁，已生成 repair_plan.md。请执行 /修复本章。"

    # 流程指标
    metrics_summary = update_flow_metrics(project_root, {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "gate_passed_final": gate_passed,
        "runtime_ms": runtime_ms,
        "query_length": len(query),
        "retrieval_context_chars": retrieval_stats.get("estimated_context_chars", 0),
        "retrieval_candidates": retrieval_stats.get("candidate_pool", 0),
        "auto_retry_actions_count": len(gate_result.get("retry_actions", [])),
        "idempotent_hit": False,
    })
    result["metrics_summary"] = metrics_summary

    # 幂等缓存
    if getattr(args, "idempotent_cache", True) and result.get("ok"):
        from novel_flow_executor import load_continue_cache, save_continue_cache
        cache = load_continue_cache(flow_dir)
        entries_raw = cache.get("entries")
        if not isinstance(entries_raw, dict):
            entries_raw = {}
            cache["entries"] = entries_raw
        entries_raw[request_id] = {
            "saved_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chapter_hash_before": chapter_hash_before,
            "result": result,
        }
        save_continue_cache(flow_dir, cache)

    return result


def build_error_result(
    exc: Exception,
    *,
    project_root: Path,
    state: Dict[str, Any],
    args: Any,
    flow_dir: Path,
    run_id: str,
    started_at: float,
    query: str,
) -> Dict[str, Any]:
    """构建异常结果字典（含回滚和指标记录）。"""
    from state_updater import update_flow_metrics
    from novel_flow_executor import restore_snapshot, run_python

    chapter_path = state.get("chapter_path")
    original_chapter_path = state.get("original_chapter_path")
    snapshot_path = state.get("snapshot_path")
    rollback_applied = False

    if getattr(args, "rollback_on_failure", True) and snapshot_path and original_chapter_path and chapter_path:
        restored = restore_snapshot(snapshot_path, original_chapter_path, chapter_path)
        rollback_applied = restored is not None
        if rollback_applied:
            chapter_path = restored

    runtime_ms = round((time.time() - started_at) * 1000, 2)
    metrics_summary = update_flow_metrics(project_root, {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": False,
        "gate_passed_final": False,
        "runtime_ms": runtime_ms,
        "query_length": len(query),
        "retrieval_context_chars": 0,
        "retrieval_candidates": 0,
        "auto_retry_actions_count": 0,
        "idempotent_hit": False,
    })

    return {
        "ok": False,
        "command": "continue-write",
        "project_root": str(project_root),
        "chapter_file": str(chapter_path) if chapter_path else "",
        "error": repr(exc),
        "run_id": run_id,
        "rollback_applied": rollback_applied,
        "metrics_summary": metrics_summary,
        "next_step": "执行发生异常，已尝试回滚章节文件。请检查错误后重试。",
    }


def check_idempotent_cache(
    flow_dir: Path,
    request_id: str,
    chapter_hash: str,
    started_at: float,
    project_root: Path,
    query: str,
    args: Any,
) -> Optional[Dict[str, Any]]:
    """检查幂等缓存，命中则返回缓存结果。"""
    from state_updater import update_flow_metrics
    from novel_flow_executor import load_continue_cache

    if not getattr(args, "idempotent_cache", True) or getattr(args, "force_run", False):
        return None

    cache = load_continue_cache(flow_dir)
    entries_raw = cache.get("entries")
    entries = entries_raw if isinstance(entries_raw, dict) else {}
    entry = entries.get(request_id)

    if not (isinstance(entry, dict) and entry.get("chapter_hash_before") == chapter_hash and entry.get("result")):
        return None

    result = dict(entry["result"])
    result["idempotent_hit"] = True
    result["request_id"] = request_id
    runtime_ms = round((time.time() - started_at) * 1000, 2)

    metrics_summary = update_flow_metrics(project_root, {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": bool(result.get("ok")),
        "gate_passed_final": bool(result.get("gate_passed_final")),
        "runtime_ms": runtime_ms,
        "query_length": len(query),
        "retrieval_context_chars": 0,
        "retrieval_candidates": 0,
        "auto_retry_actions_count": 0,
        "idempotent_hit": True,
    })
    result["metrics_summary"] = metrics_summary
    result["runtime_ms"] = runtime_ms
    return result
