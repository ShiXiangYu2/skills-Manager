#!/usr/bin/env python3
"""RAG检索和历史剧情加载模块。

负责执行 RAG 查询、提取历史剧情片段、组装最终写作查询。
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import read_text, load_json, chapter_no_from_name

_SCRIPT_DIR = Path(__file__).resolve().parent


def query_rag_context(
    project_root: Path,
    query: str,
    top_k: int,
    candidate_k: int,
    force_retrieval: bool,
) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    """执行 RAG 检索查询，返回 (exit_code, stdout, stderr, payload)。"""
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    cmd = [
        "query",
        "--project-root", str(project_root),
        "--query", query,
        "--top-k", str(top_k),
        "--candidate-k", str(candidate_k),
        "--auto-build",
    ]
    if force_retrieval:
        cmd.append("--force")
    return run_python(_SCRIPT_DIR / "plot_rag_retriever.py", cmd)


def extract_rag_lines(q_payload: Optional[Dict[str, Any]], limit: int = 4) -> List[str]:
    """从 RAG 查询结果中提取 top-k 历史剧情片段。

    Args:
        q_payload: RAG 查询返回的 payload
        limit: 最多提取的片段数

    Returns:
        历史剧情文本行列表
    """
    lines: List[str] = []
    if not isinstance(q_payload, dict):
        return lines

    result_obj = q_payload.get("result")
    retrieved = result_obj.get("retrieved", []) if isinstance(result_obj, dict) else []

    for item in retrieved:
        if not isinstance(item, dict):
            continue
        chapter_ref = str(item.get("chapter_file") or "").strip()
        for passage in (item.get("passages") or []):
            if not isinstance(passage, dict):
                continue
            text = str(passage.get("text") or "").strip()
            if text:
                lines.append(f"{chapter_ref}：{text}" if chapter_ref else text)
                if len(lines) >= limit:
                    return lines
        if len(lines) >= limit:
            break
    return lines


def build_writing_query(
    query: str,
    rag_lines: List[str],
    injected_lines: List[str],
) -> str:
    """组装最终写作查询：原始意图 + 相关历史剧情 + 写作约束。

    Args:
        query: 用户原始写作意图
        rag_lines: RAG 检索到的历史剧情片段
        injected_lines: 约束注入的提示行

    Returns:
        拼装后的完整写作查询文本
    """
    sections = [query]
    if rag_lines:
        sections.append(
            "[相关历史剧情]\n" + "\n".join(f"- {line}" for line in rag_lines)
        )
    if injected_lines:
        sections.append(
            "[写作约束]\n" + "\n".join(f"- {line}" for line in injected_lines)
        )
    return "\n\n".join(sections)


def rebuild_rag_index(project_root: Path) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    """重建 RAG 索引。"""
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python

    return run_python(
        _SCRIPT_DIR / "plot_rag_retriever.py",
        ["build", "--project-root", str(project_root)],
    )


def extract_retrieval_stats(q_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 RAG payload 中提取检索统计信息。"""
    if not isinstance(q_payload, dict):
        return {}
    result_obj = q_payload.get("result")
    if isinstance(result_obj, dict):
        rs_obj = result_obj.get("retrieval_stats")
        if isinstance(rs_obj, dict):
            return rs_obj
    return {}
