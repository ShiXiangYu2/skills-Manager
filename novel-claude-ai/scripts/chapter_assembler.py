#!/usr/bin/env python3
"""章节质量评估与改进模块。

负责章节质量评估、AI词检测、段落多样性分析、自动改进循环。
"""

import argparse
import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import read_text, write_text

# AI高频词黑名单
AI_PHRASE_BLACKLIST = [
    "不禁", "仿佛", "宛如", "宛若", "恍若", "仿若", "好似",
    "映入眼帘", "涌入眼帘", "跃入眼帘",
    "心中暗道", "心中暗想", "暗自思忖", "心中一动", "心中一凛",
    "沉声道", "淡淡地说", "缓缓说道", "淡然道",
    "脸色一变", "神情一凛", "眉头微皱", "身形一顿", "脚步一顿",
    "嘴角微扬", "勾起一抹弧度", "目光如炬",
    "只见", "此时此刻",
    "不由自主", "不由得", "情不自禁",
    "叹为观止", "意义深远", "前所未有", "可谓", "毋庸置疑",
]


def clean_for_stats(text: str) -> str:
    """清理文本用于统计：移除标题和注释标记。"""
    txt = re.sub(r"(?m)^#.*$", "", text)
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.S)
    return txt.strip()


def improve_text_minimally(text: str, query: str) -> str:
    """对文本进行最小化改进：追加推进段落。"""
    extra = (
        f"补充推进：围绕"{query}"再加入一段行动结果、一段对话冲突、一段章末钩子，"
        "确保本章既有情节推进也有角色关系变化。"
    )
    return text.rstrip() + "\n\n" + extra + "\n"


def evaluate_quality(text: str, args: argparse.Namespace) -> Dict[str, Any]:
    """增强版质量评估 - 添加内容密度、AI词密度、段落多样性检查。

    Args:
        text: 章节文本
        args: 包含质量阈值参数的命名空间

    Returns:
        质量评估结果字典
    """
    # 延迟导入避免循环依赖
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from novel_flow_executor import _resolve_pacing_mode, PACING_MODE_PROFILES

    body = clean_for_stats(text)
    pure = re.sub(r"\s+", "", body)
    char_count = len(pure)

    content_density = len(pure) / len(body) if body else 0

    ai_phrase_count = sum(body.count(w) for w in AI_PHRASE_BLACKLIST)
    ai_density = ai_phrase_count / char_count if char_count else 0

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    para_lengths = [len(p) for p in paragraphs]
    para_variance = statistics.variance(para_lengths) if len(para_lengths) > 1 else 0
    paragraph_count = len(paragraphs)

    # 段落重复度检查
    normalized_paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in paragraphs]
    para_counter: Dict[str, int] = {}
    for p in normalized_paragraphs:
        para_counter[p] = para_counter.get(p, 0) + 1

    unique_paragraph_count = len(para_counter)
    paragraph_unique_ratio = unique_paragraph_count / paragraph_count if paragraph_count > 0 else 1.0
    max_duplicate_paragraph_repeat = max(para_counter.values()) if para_counter else 1

    # 对话占比
    dialogue_chars = sum(len(m.group(1)) for m in re.finditer(r"["“"]([^"”"]*)["”"]", body))
    dialogue_ratio = (dialogue_chars / char_count) if char_count else 0.0

    sentence_count = len(re.findall(r"[。！？!?]", body))

    # AI词命中详情
    ai_phrase_hits = []
    for w in AI_PHRASE_BLACKLIST:
        c = body.count(w)
        if c > 0:
            ai_phrase_hits.append({"phrase": w, "count": c})

    # 失败检查
    failures: List[str] = []
    if char_count < args.min_chars:
        failures.append(f"char_count<{args.min_chars} (current: {char_count})")
    if paragraph_count < args.min_paragraphs:
        failures.append(f"paragraph_count<{args.min_paragraphs}")

    min_density = getattr(args, 'min_content_density', 0.7)
    if content_density < min_density:
        failures.append(f"content_density<{min_density:.2f} (current: {content_density:.2f})")

    max_ai_density = getattr(args, 'max_ai_phrase_density', 0.05)
    if ai_density > max_ai_density:
        failures.append(f"ai_phrase_density_too_high ({ai_density:.2%}, max: {max_ai_density:.2%})")

    max_variance = getattr(args, 'max_paragraph_variance', 10000)
    if para_variance > max_variance:
        failures.append(f"paragraph_variance_too_high ({para_variance:.0f}, max: {max_variance})")

    if dialogue_ratio < args.min_dialogue_ratio:
        failures.append(f"dialogue_ratio_too_low ({dialogue_ratio:.2%})")
    if dialogue_ratio > args.max_dialogue_ratio:
        failures.append(f"dialogue_ratio_too_high ({dialogue_ratio:.2%})")
    if sentence_count < args.min_sentences:
        failures.append(f"sentence_count_too_low ({sentence_count})")

    min_unique_ratio = getattr(args, 'min_paragraph_unique_ratio', 0.85)
    max_dup_repeat = getattr(args, 'max_duplicate_paragraph_repeat', 2)
    if paragraph_unique_ratio < min_unique_ratio:
        failures.append(
            f"paragraph_unique_ratio<{min_unique_ratio:.2f} (current: {paragraph_unique_ratio:.2%}, "
            f"unique={unique_paragraph_count}/{paragraph_count})"
        )
    if max_duplicate_paragraph_repeat > max_dup_repeat:
        failures.append(
            f"max_duplicate_paragraph_repeat>{max_dup_repeat} (current: {max_duplicate_paragraph_repeat})"
        )

    # 概括跳过密度检查
    pacing_mode_val = _resolve_pacing_mode(getattr(args, "pacing_mode", "standard"))
    pacing_p = PACING_MODE_PROFILES[pacing_mode_val]
    para_list = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]

    # 概括跳过词正则
    _FLOW_PACING_SKIP_PATTERNS = [
        r"(?:此后|随后|转眼|一晃|没过多久|几天后|数日后|几个月后|数月后|又过了)",
        r"(?:经过一番|经过数轮|花了[一二三四五六七八九十百\d两]+[天日月年]|苦修[一二三四五六七八九十百\d两]*[天日月年]?)",
        r"(?:练功大成|很快(?:就|便)|就这样(?:结束|过去)|不知不觉(?:就)?(?:完成|突破|成功))",
    ]
    total = sum(len(re.findall(p, body)) for p in _FLOW_PACING_SKIP_PATTERNS)
    skip_density = round(total / max(len(para_list), 1), 3)

    max_skip = float(pacing_p.get("max_skip_density", 0.30))
    skip_density_exceeded = skip_density > max_skip
    _STANDARD_HARD_SKIP_THRESHOLD = 0.50

    if skip_density_exceeded:
        if pacing_mode_val == "immersive":
            failures.append(
                f"pacing_skip_density_too_high ({skip_density:.2f}/para, max: {max_skip:.2f}) "
                f"— 检测到概括跳过叙述，immersive 模式须展开每个场景过程"
            )
        elif pacing_mode_val == "standard" and skip_density > _STANDARD_HARD_SKIP_THRESHOLD:
            failures.append(
                f"pacing_skip_density_critical ({skip_density:.2f}/para, hard_limit: {_STANDARD_HARD_SKIP_THRESHOLD:.2f}) "
                f"— 概括跳过密度极高，standard 模式亦不可接受，需展开场景"
            )

    return {
        "char_count": char_count,
        "paragraph_count": paragraph_count,
        "sentence_count": sentence_count,
        "dialogue_chars": dialogue_chars,
        "dialogue_ratio": round(dialogue_ratio, 4),
        "content_density": round(content_density, 4),
        "ai_density": round(ai_density, 4),
        "paragraph_variance": round(para_variance, 2),
        "paragraph_unique_ratio": round(paragraph_unique_ratio, 4),
        "max_duplicate_paragraph_repeat": max_duplicate_paragraph_repeat,
        "unique_paragraph_count": unique_paragraph_count,
        "ai_phrase_hits": ai_phrase_hits,
        "pacing_mode": pacing_mode_val,
        "skip_density": skip_density,
        "skip_density_exceeded": skip_density_exceeded,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def assess_and_improve(
    project_root: Path,
    chapter_path: Path,
    writing_query: str,
    args: argparse.Namespace,
    is_draft: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    """评估章节质量并执行自动改进循环。

    Args:
        project_root: 项目根目录
        chapter_path: 章节文件路径
        writing_query: 写作查询
        args: 参数命名空间
        is_draft: 是否仍为草稿

    Returns:
        (quality_before, quality_after, improve_rounds)
    """
    quality_before = evaluate_quality(read_text(chapter_path), args)
    quality_after = quality_before
    improve_rounds = 0

    if not is_draft and args.auto_improve:
        while (not quality_after["passed"]) and improve_rounds < args.auto_improve_rounds:
            txt = read_text(chapter_path)
            write_text(chapter_path, improve_text_minimally(txt, writing_query))
            quality_after = evaluate_quality(read_text(chapter_path), args)
            improve_rounds += 1

    return quality_before, quality_after, improve_rounds
