#!/usr/bin/env python3
"""Beat Sheet 生成和扩写模块。

负责 Beat Sheet 骨架生成、逐 Beat 扩写、场景分解、
两阶段写作、草稿生成（模板/LLM）、以及 Beat Sheet 流水线编排。
"""

import argparse
import datetime as dt
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from common import (
    ensure_dir, read_text, write_text,
    load_json, save_json, slugify,
    chapter_no_from_name,
)

_SCRIPT_DIR = Path(__file__).resolve().parent

# ── 标记常量 ──────────────────────────────────────────────────────────────────
STUB_MARKER = "<!-- NOVEL_FLOW_STUB -->"
BEAT_SHEET_STUB_MARKER = "<!-- BEAT_SHEET_STUB -->"
DRAFT_PLACEHOLDER_LINE = re.compile(r"(?m)^\[待写\]\s*$")
MAX_STUB_EFFECTIVE_CHARS = 800

# ── 概括跳过词正则 ──────────────────────────────────────────────────────────
FLOW_PACING_SKIP_PATTERNS = [
    r"(?:此后|随后|转眼|一晃|没过多久|几天后|数日后|几个月后|数月后|又过了)",
    r"(?:经过一番|经过数轮|花了[一二三四五六七八九十百\d两]+[天日月年]|苦修[一二三四五六七八九十百\d两]*[天日月年]?)",
    r"(?:练功大成|很快(?:就|便)|就这样(?:结束|过去)|不知不觉(?:就)?(?:完成|突破|成功))",
]

# ── Claude Code 模式检测 ─────────────────────────────────────────────────────
CLAUDE_CODE_MODE = os.environ.get("CLAUDE_CODE_MODE", "") or os.environ.get("CODEX_MODE", "")

# ── 两阶段写作：场景分解 ─────────────────────────────────────────────────────
_SCENE_DECOMPOSE_SYSTEM = (
    "你是专业小说结构编辑。接收一个 beat（场景片段）的写作任务描述，"
    "将其拆解为 5–7 个连续的「微时刻」，以 JSON 格式输出。"
    "每个微时刻必须包含：action（具体动作，非总结）、sensory（感官细节）、"
    "emotion（情绪/内心状态）、obstacle（遇到的阻力或变化，可为空字符串）。"
    "输出格式严格为：```json\n"
    "{\"moments\": [{\"id\":1,\"action\":\"\",\"sensory\":\"\",\"emotion\":\"\",\"obstacle\":\"\"}]}\n"
    "```\n"
    "禁止使用「经过一番」「很快」「此后」等概括跳过词描述微时刻。"
)

_SCENE_DECOMPOSE_USER_TMPL = (
    "请将以下 beat 写作任务拆解为 5–7 个微时刻（JSON 格式）：\n\n"
    "{beat_summary}\n\n"
    "字数目标：约 {word_target} 字。每个微时刻对应约 {chars_per_moment} 字的散文。"
)


# ── LLM 配置检测 ──────────────────────────────────────────────────────────────

def _has_llm_config(args: argparse.Namespace, project_root: Path) -> bool:
    """检查是否配置了 LLM 写作能力。"""
    if CLAUDE_CODE_MODE:
        return True
    if getattr(args, "llm_provider", None) or getattr(args, "llm_api_key", None):
        return True
    if os.environ.get("NOVEL_LLM_PROVIDER") or os.environ.get("NOVEL_AI_PROVIDER"):
        return True
    return (project_root / ".novel_writer_config.yaml").exists()


def _resolve_draft_provider(args: argparse.Namespace, project_root: Path) -> str:
    """解析草稿生成方式：auto -> llm (if configured) or template。"""
    raw = str(getattr(args, "draft_provider", "auto") or "auto")
    if raw in {"template", "llm"}:
        return raw
    if CLAUDE_CODE_MODE:
        return "llm"
    return "llm" if _has_llm_config(args, project_root) else "template"


# ── 跳过密度与 Beat 校验 ─────────────────────────────────────────────────────

def _calc_skip_density(text: str, paragraphs: List[str]) -> float:
    """计算概括跳过词密度（hits / paragraphs）。"""
    total = sum(len(re.findall(p, text)) for p in FLOW_PACING_SKIP_PATTERNS)
    return round(total / max(len(paragraphs), 1), 3)


def _validate_beat_text(text: str, word_target: int, max_skip_density: float) -> Dict[str, Any]:
    """校验单个 beat 正文是否达到最低展开要求。"""
    from chapter_assembler import clean_for_stats

    body = clean_for_stats(text)
    pure = re.sub(r"\s+", "", body)
    char_count = len(pure)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    min_chars = max(1, int(word_target * 0.75))
    skip_density = _calc_skip_density(body, paragraphs)

    failures: List[str] = []
    if char_count < min_chars:
        failures.append(f"char_count<{min_chars} (actual:{char_count}, target:{word_target})")
    if skip_density > max_skip_density:
        failures.append(f"skip_density>{max_skip_density:.2f} (actual:{skip_density:.3f})")

    return {
        "passed": len(failures) == 0,
        "char_count": char_count,
        "word_target": word_target,
        "min_chars": min_chars,
        "paragraph_count": len(paragraphs),
        "skip_density": skip_density,
        "max_skip_density": max_skip_density,
        "failures": failures,
    }


def _build_retry_prompt(expand_prompt: str, retry: int, word_target: int) -> str:
    """在重试时在原扩写提示词前追加强化要求。"""
    header = (
        f"【强制重写 - 第{retry}次】上一版本字数不足或使用了概括跳过句，本次必须满足：\n"
        f"1. 字数达到 {word_target} 字\n"
        "2. 每个时间推进都要落到具体行动，禁止使用'此后/经过一番/练功大成'等跳过句\n"
        "3. 至少写出3个具体的场景瞬间（动作-反应-情绪链条）\n"
        "4. 不得出现任何结论先行、省略过程的叙述\n\n"
    )
    return header + expand_prompt


# ── 两阶段写作：场景分解 + 场景锚定 ─────────────────────────────────────────

def _decompose_beat_scenes(
    expand_prompt: str,
    word_target: int,
    overrides: Dict[str, Any],
    project_root: Path,
) -> Optional[Dict[str, Any]]:
    """Phase 1：调用 LLM 将 beat 拆解为 5~7 个微时刻 JSON。"""
    import json as _json

    beat_summary = expand_prompt[:600].strip()
    moment_count = 6
    chars_per_moment = max(80, word_target // moment_count)

    user_msg = _SCENE_DECOMPOSE_USER_TMPL.format(
        beat_summary=beat_summary,
        word_target=word_target,
        chars_per_moment=chars_per_moment,
    )

    try:
        from novel_chapter_writer import write_chapter  # type: ignore[import]

        tmp_file = project_root / "00_memory" / "beats" / "_scene_decompose_tmp.md"
        decompose_overrides: Dict[str, Any] = {
            **overrides,
            "writing_prompt": user_msg,
            "writing_system_prompt_override": _SCENE_DECOMPOSE_SYSTEM,
            "max_tokens": 1200,
            "humanizer_enabled": False,
            "auto_update_memory": False,
        }

        result = write_chapter(
            project_root,
            chapter_file=tmp_file,
            config_overrides=decompose_overrides,
            dry_run=False,
        )

        if not result.get("ok"):
            return None

        raw = tmp_file.read_text(encoding="utf-8") if tmp_file.exists() else ""
        tmp_file.unlink(missing_ok=True)

        json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if json_match:
            scene_map: Dict[str, Any] = _json.loads(json_match.group(1))
        else:
            bare = re.search(r'\{[^{}]*"moments"[^{}]*\[.*?\]\s*\}', raw, re.DOTALL)
            if not bare:
                return None
            scene_map = _json.loads(bare.group(0))

        moments = scene_map.get("moments", [])
        if not isinstance(moments, list) or len(moments) < 3:
            return None

        return scene_map

    except Exception as _dbs_err:
        print(f"[警告] 场景分解失败，降级到原始扩写提示词: {_dbs_err}")
        return None


def _build_scene_anchored_prompt(expand_prompt: str, scene_map: Dict[str, Any]) -> str:
    """Phase 2：将场景分解结果嵌入扩写提示词，锁定微时刻序列。"""
    moments: List[Dict[str, Any]] = scene_map.get("moments", [])
    lines: List[str] = []
    for m in moments:
        idx = m.get("id", "?")
        action = m.get("action", "")
        sensory = m.get("sensory", "")
        emotion = m.get("emotion", "")
        obstacle = m.get("obstacle", "")
        line = (
            f"  『微时刻{idx}』动作：{action}"
            f"｜感官：{sensory}"
            f"｜情绪：{emotion}"
        )
        if obstacle:
            line += f"｜阻力：{obstacle}"
        lines.append(line)

    moments_text = "\n".join(lines)
    n = len(moments)
    header = (
        f"【场景分解锁定】以下 {n} 个微时刻已确定，"
        "必须按顺序展开每个微时刻的散文，"
        "每个微时刻至少写 3 段（动作→感官→情绪），"
        "禁止合并、跳过或重排任何微时刻。\n\n"
        f"微时刻序列：\n{moments_text}\n\n"
        "现在开始给每个微时刻写详细的小说散文：\n\n"
    )
    return header + expand_prompt


# ── MCP Codex / LLM 重写 ─────────────────────────────────────────────────────

def _write_with_mcp_codex(
    project_root: Path,
    chapter_path: Path,
    prompt: str,
) -> bool:
    """Write chapter using MCP Codex tool. Returns True on success."""
    signal_file = project_root / ".flow" / "mcp_write_request.json"
    ensure_dir(signal_file.parent)
    signal_data = {
        "chapter_path": str(chapter_path),
        "prompt": prompt,
        "timestamp": dt.datetime.now().isoformat(),
    }
    save_json(signal_file, signal_data)
    return False


def _rewrite_chapter_with_llm(
    project_root: Path,
    chapter_path: Path,
    args: argparse.Namespace,
    prompt: str,
) -> bool:
    """Rewrite chapter using LLM for pacing issues. Returns True on success."""
    if not _has_llm_config(args, project_root):
        return False
    if CLAUDE_CODE_MODE:
        return _write_with_mcp_codex(project_root, chapter_path, prompt)
    try:
        from novel_chapter_writer import write_chapter  # type: ignore[import]
        overrides: Dict[str, Any] = {"writing_prompt": prompt}
        if getattr(args, "llm_provider", None):
            overrides["ai_provider"] = args.llm_provider
        if getattr(args, "llm_model", None):
            overrides["model"] = args.llm_model
        if getattr(args, "llm_api_key", None):
            provider = getattr(args, "llm_provider", "") or "openai"
            if provider == "openai":
                overrides["openai_api_key"] = args.llm_api_key
            elif provider == "anthropic":
                overrides["anthropic_api_key"] = args.llm_api_key
            else:
                overrides["api_key"] = args.llm_api_key
        result = write_chapter(project_root, chapter_file=chapter_path, config_overrides=overrides, dry_run=False)
        return bool(result.get("ok"))
    except Exception:
        return False


# ── 章节占位检测 ──────────────────────────────────────────────────────────────

def chapter_is_draft_stub(path: Path) -> bool:
    """检测章节文件是否为占位草稿。"""
    txt = read_text(path)
    if STUB_MARKER in txt:
        return True
    if BEAT_SHEET_STUB_MARKER in txt:
        return True
    if DRAFT_PLACEHOLDER_LINE.search(txt):
        effective = re.sub(r"\s+", "", txt)
        if len(effective) <= MAX_STUB_EFFECTIVE_CHARS:
            return True
    return False


# ── 角色名加载 ────────────────────────────────────────────────────────────────

def _load_character_names(project_root: Path) -> List[str]:
    """从 character_tracker.md 加载角色名列表。"""
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


# ── Beat Sheet 流水线 ────────────────────────────────────────────────────────

def _generate_beat_draft(
    project_root: Path,
    chapter_path: Path,
    chapter_no: int,
    query: str,
    writing_constraints: Optional[Dict[str, Any]],
    args: argparse.Namespace,
) -> Tuple[bool, str]:
    """Beat Sheet 流水线：generate -> expand -> synthesize。

    Returns (success, mode)。
    """
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(_SCRIPT_DIR))
    from novel_flow_executor import run_python, _resolve_pacing_mode, PACING_MODE_PROFILES

    chapter_goal = query[:200]
    pacing_depth = _resolve_pacing_mode(getattr(args, "pacing_mode", "standard"))

    # 丰富章节目标描述
    enriched_goal = chapter_goal
    if writing_constraints:
        parts: List[str] = [chapter_goal]
        outline_c = writing_constraints.get("outline_constraints", "")
        if outline_c:
            parts.append(f"大纲约束：{str(outline_c)[:120]}")
        event_rec = writing_constraints.get("event_recommendation", "")
        if event_rec:
            parts.append(f"推荐事件：{str(event_rec)[:120]}")
        graph_ctx = writing_constraints.get("graph_context", "")
        if graph_ctx:
            parts.append(f"人物关系：{str(graph_ctx)[:100]}")
        enriched_goal = " | ".join(p for p in parts if p)[:400]

    # Step 1: 生成 Beat Sheet 骨架
    b_code, _b_out, _b_err, b_payload = run_python(
        _SCRIPT_DIR / "beat_sheet_generator.py",
        ["generate",
         "--project-root", str(project_root),
         "--chapter", str(chapter_no),
         "--chapter-goal", enriched_goal,
         "--pacing-depth", pacing_depth,
         "--beat-count", str(getattr(args, "beat_count", 4))],
    )
    if b_code != 0 or not isinstance(b_payload, dict) or not b_payload.get("ok"):
        return False, "beat_generate_failed"

    beat_count = int(b_payload.get("beat_count", 4))

    beats_dir = project_root / "00_memory" / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = beats_dir / f"ch{chapter_no:04d}_beat_sheet.json"
    sheet = load_json(sheet_path, default={})
    beats_meta: List[Dict[str, Any]] = [
        b for b in sheet.get("beats", []) if isinstance(b, dict)
    ]
    pacing_profile = PACING_MODE_PROFILES[pacing_depth]
    max_skip_density = float(pacing_profile.get("max_skip_density", 0.30))

    # Step 2: 逐 Beat 扩写 + Beat 级校验与重试
    draft_provider = _resolve_draft_provider(args, project_root)

    for beat_id in range(1, beat_count + 1):
        e_code, _e_out, _e_err, e_payload = run_python(
            _SCRIPT_DIR / "beat_sheet_generator.py",
            ["expand",
             "--project-root", str(project_root),
             "--chapter", str(chapter_no),
             "--pacing-depth", pacing_depth,
             "--beat-id", str(beat_id)],
        )
        if e_code != 0 or not isinstance(e_payload, dict):
            continue

        expand_prompt = e_payload.get("expand_prompt", "")
        beat_file = beats_dir / f"ch{chapter_no:04d}_beat{beat_id:02d}_expand.md"

        beat_meta = next((b for b in beats_meta if b.get("beat_id") == beat_id), {})
        word_target = int(e_payload.get("word_target") or beat_meta.get("word_target") or 800)

        if draft_provider == "llm" and expand_prompt:
            try:
                from novel_chapter_writer import write_chapter  # type: ignore[import]
                overrides: Dict[str, Any] = {}
                if getattr(args, "llm_provider", None):
                    overrides["ai_provider"] = args.llm_provider
                if getattr(args, "llm_model", None):
                    overrides["model"] = args.llm_model
                if getattr(args, "llm_api_key", None):
                    _llm_prov = getattr(args, "llm_provider", "") or ""
                    if _llm_prov == "openai":
                        overrides["openai_api_key"] = args.llm_api_key
                    elif _llm_prov == "anthropic":
                        overrides["anthropic_api_key"] = args.llm_api_key
                    else:
                        overrides["api_key"] = args.llm_api_key

                # Phase 1: 场景分解
                scene_map = _decompose_beat_scenes(
                    expand_prompt, word_target, overrides, project_root
                )
                base_prompt = (
                    _build_scene_anchored_prompt(expand_prompt, scene_map)
                    if scene_map is not None
                    else expand_prompt
                )

                # Beat 级校验与重试循环（最多 3 次）
                attempt_results: List[Dict[str, Any]] = []
                accepted = False
                final_validation: Optional[Dict[str, Any]] = None

                for attempt in range(3):
                    current_prompt = (
                        base_prompt if attempt == 0
                        else _build_retry_prompt(base_prompt, attempt, word_target)
                    )
                    overrides["writing_prompt"] = current_prompt

                    try:
                        llm_result = write_chapter(
                            project_root,
                            chapter_file=beat_file,
                            config_overrides=overrides,
                            dry_run=False,
                        )
                        llm_ok = bool(llm_result.get("ok"))
                    except Exception as exc:
                        attempt_results.append({
                            "attempt": attempt + 1, "llm_ok": False,
                            "error": repr(exc), "accepted": False,
                        })
                        continue

                    if not llm_ok:
                        attempt_results.append({
                            "attempt": attempt + 1, "llm_ok": False,
                            "error": str(llm_result.get("error", "llm_write_failed")),
                            "accepted": False,
                        })
                        continue

                    beat_text = read_text(beat_file) if beat_file.exists() else ""
                    final_validation = cast(
                        Dict[str, Any],
                        _validate_beat_text(beat_text, word_target, max_skip_density),
                    )
                    attempt_results.append({
                        "attempt": attempt + 1, "llm_ok": True,
                        "accepted": bool(final_validation.get("passed")),
                        "validation": final_validation,
                    })

                    if final_validation.get("passed"):
                        accepted = True
                        break

                # 所有尝试用尽仍未通过：降级写入扩写提示词模板
                if not accepted and (not beat_file.exists() or not read_text(beat_file).strip()):
                    write_text(beat_file, expand_prompt)

                # 将 beat 级校验结果写回 beat sheet
                if beat_meta:
                    beat_meta["generation_meta"] = {
                        "pacing_depth": pacing_depth,
                        "word_target": word_target,
                        "max_skip_density": max_skip_density,
                        "accepted": accepted,
                        "attempt_count": len(attempt_results),
                        "retry_count": max(0, len(attempt_results) - 1),
                        "attempts": attempt_results,
                        "final_validation": final_validation,
                    }
                    save_json(sheet_path, sheet, indent=2)

            except Exception as _beat_err:
                print(f"[警告] Beat {beat_id} LLM 写作异常，降级写入扩写提示词模板: {_beat_err}")
                write_text(beat_file, expand_prompt)
        else:
            write_text(beat_file, expand_prompt)

    # Step 3: chapter_synthesizer 合成
    s_code, _s_out, _s_err, s_payload = run_python(
        _SCRIPT_DIR / "chapter_synthesizer.py",
        ["synthesize",
         "--project-root", str(project_root),
         "--chapter", str(chapter_no)],
    )
    if s_code != 0 or not isinstance(s_payload, dict) or not s_payload.get("ok"):
        return False, "synthesize_failed"

    output_file = s_payload.get("output_file", "")
    mode = s_payload.get("mode", "unknown")

    if mode == "draft_merged" and output_file and Path(output_file).exists():
        synth_text = read_text(Path(output_file))
        write_text(chapter_path, synth_text)
        return True, "beat_sheet_llm"
    elif mode == "prompt_only" and output_file and Path(output_file).exists():
        synth_prompt = read_text(Path(output_file))
        stub = f"# {chapter_path.stem}\n\n{BEAT_SHEET_STUB_MARKER}\n\n{synth_prompt}\n"
        write_text(chapter_path, stub)
        return True, "beat_sheet_template"

    return False, "synthesize_no_output"


# ── 模板草稿生成 ──────────────────────────────────────────────────────────────

def generate_draft_text(project_root: Path, chapter_path: Path, query: str, min_chars: int) -> str:
    """兜底模板草稿生成。LLM 不可用时使用。"""
    chapter_no = chapter_no_from_name(chapter_path.name)
    title = chapter_path.stem.replace('-', ' ')
    names = _load_character_names(project_root)
    protagonist = names[0] if names else '主角'
    side = names[1] if len(names) > 1 else '同伴'

    rng = random.Random(chapter_no)

    opening_pool = [
        (protagonist + '没有多说，直接走向了事情发生的地方。'
         + query + '——这一步迈出去，就没有回头的余地。'
         + '他知道自己在做什么，也知道可能付出什么代价。'
         + '但有些事，不做会后悔，做了最多是吃亏，两害相权，他选了前者。'),
        ('事情比预想的复杂。' + protagonist + '站在原地，把已知的信息重新梳理了一遍。'
         + query + '——每一条线索都指向同一个方向，偏偏每一条都差一截才能闭合。'
         + '他不急，急没用，这种事急了只会出错。'
         + side + '在一旁说："你想好了？"他没有回答，因为还在想。'),
        (side + '先开口说："你确定要这样做？"'
         + protagonist + '没有立刻回答，把问题在脑子里转了一圈，才开口："不确定，但现在没有更好的选项。"'
         + '于是两人就这样决定了：' + query + '，就从这里开始做起。'),
        ('清晨的光线还没有彻底亮起来。' + protagonist + '已经起身，站在窗边把今天要做的事理了一遍。'
         + query + '——放在平时，这不算什么大事，但放在现在这个节点，每一步都要踩稳。'
         + '他动作很轻，没有惊动任何人，然后出了门。'),
        ('上一章留下的麻烦没有消失，只是换了一张脸。' + protagonist + '盯着眼前的局面，'
         + '想起某人说过的一句话：问题不会自己消失，它只是在等一个更坏的时机重新出现。'
         + query + '，就是那个时机终于到了。他把手里的东西收好，准备开始。'),
    ]

    closing_pool = [
        (protagonist + '没有立刻离开，在原地停了一会儿。'
         + '事情走到这一步，算是告一段落——但"告一段落"不等于结束，只等于把问题暂时压住了。'
         + '压住的东西，早晚还会冒出来。下一步怎么走，他心里已经有了一个方向，'
         + '只是还没到说出来的时候。'),
        (side + '问："现在怎么办？"'
         + protagonist + '想了想，说："先把今天的事收尾，再说下一步。"'
         + '那句话说得很轻，但两个人都听出来了——这件事还没完，甚至刚刚开始。'
         + side + '没再多问，点了点头，两个人各自散了。'),
        ('夜深了。' + protagonist + '把今天发生的事在脑子里过了一遍，'
         + '有些东西对上了，有些东西还差一块。差的那块，是整件事的关键，也是目前最难拿到的那块。'
         + '他没有急着去找，因为有些东西越找越躲，不如等它自己浮出来。明天还有时间，先休息。'),
        ('结果不算好，也不算坏。' + protagonist + '把事情记下来，合上本子。'
         + '他没有总结，没有下判断，只是记录。判断留到事情彻底结束再做，现在下结论，太早。'
         + side + '看着他说："你总是这样，什么都先记下来再说。"他想了想，回答："记下来，才不会忘。"'),
        ('回去的路上，' + protagonist + '一直没说话。' + side + '也没问。'
         + '有些问题，现在还没有答案，说了也只是给对方添麻烦。沉默有时候比什么都有用。'
         + '走到分叉口，两个人停下来，各自往不同的方向去了。'),
    ]

    middle_pool = [
        (protagonist + '把情况仔细检查了一遍，确认没有遗漏，才继续往下走。'
         + '这种习惯是多次教训换来的——不是天生谨慎，是被逼出来的。'
         + side + '在旁边等着，没有催他，因为知道他有他的节奏。'),
        (side + '说："你有没有想过，事情可能不是我们以为的那样？"'
         + protagonist + '停下来，认真考虑了这个问题。'
         + '不是第一次有人这么说了，但每次被这样问，他还是会重新检查一遍自己的判断。'),
        ('中途出了一个岔子。' + protagonist + '没有慌，先把手头的东西放稳，再来处理新冒出来的问题。'
         + '慌解决不了事情，冷静也不一定能，但至少不会把事情弄得更乱。'
         + side + '问："要我帮忙吗？"他说："先看看再说。"'),
        ('有一个细节一直让' + protagonist + '觉得不对，但说不清楚哪里不对。'
         + '直到这一刻，才突然想明白——不是细节本身有问题，是细节和上下文不搭。'),
        ('事情推进得比预期慢。' + protagonist + '调整了节奏，不再追着进度走，而是等一个合适的时机。'
         + side + '倒是沉得住气："你现在倒想开了。"他说："不是想开了，是想通了。"'),
        (protagonist + '和' + side + '分头行动，各自去处理一件事，约好稍后碰面。'
         + '临分开前，' + protagonist + '说："有情况随时通知我。"' + side + '点头："你也是。"'),
        ('遇到了一个不速之客。' + protagonist + '没有表现出惊讶，只是多看了对方一眼，暗中把情况记在心里。'
         + '对方的来意不明，但来得太巧，巧到不像是偶然。'),
        ('天色开始变暗。还有几件事没有处理完，但有些事急不来，只能等。'
         + protagonist + '把优先级重新排了一遍，把今晚能做的和只能明天做的分开。'),
        (side + '带来了一条新消息。' + protagonist + '听完，沉默了片刻，然后说："这改变了一些事情。"'
         + '不是全部，但是重要的一部分。他把原来的计划在脑子里调整了一遍。'),
        ('这件事牵扯的人比想象中多。' + protagonist + '意识到，自己需要更谨慎一些。'
         + '不是因为怕，是因为一个错误波及的范围会更大。'),
        (protagonist + '回到原地，把之前记录的东西重新看了一遍。'
         + '信息量并不小，但真正有用的不多。'
         + side + '凑过来看了一眼，说："就这些？"他说："就这些，够了。"'),
        ('事情发展到某个节点，开始出现分叉。' + protagonist + '需要做一个选择，而每一条路都有代价。'
         + side + '说："你考虑太多了。"他说："我宁可考虑太多，也不要考虑太少。"'),
    ]

    rng.shuffle(middle_pool)
    opening = rng.choice(opening_pool)
    closing = rng.choice(closing_pool)
    paragraphs = [opening] + middle_pool + [closing]
    text = '# ' + title + '\n\n' + '\n\n'.join(paragraphs)

    # 兜底补充段落
    target_chars = max(min_chars, 2500)
    extra_pool = [
        (protagonist + '把手头的事情暂停了一下，环顾周围。'
         + '他没有急着动，先把能观察到的信息收集完，再决定下一步怎么做。'),
        ('两人之间有一段时间没说话。'
         + side + '最后先开口："你打算怎么处理？"' + protagonist + '想了想，说："先把能确认的部分确认了再说。"'),
        (protagonist + '回头看了一眼来路，然后继续往前走。'
         + '他清楚，这件事从一开始就没有退路，不是因为被逼的，是因为他自己选的。'),
        ('到了某个节点，' + protagonist + '意识到，自己对这件事的判断，和最开始相比，已经变了不少。'
         + '不是被说服了，是被事实改变了。'),
        (side + '问了一个问题，' + protagonist + '没有立刻回答。'
         + '那个问题触到了他一直没想清楚的地方。他说："给我一点时间。"' + side + '点头，没有催。'),
    ]
    pure_len = len(re.sub(r'\s+', '', text))
    for extra_para in extra_pool:
        if pure_len >= target_chars:
            break
        text += '\n\n' + extra_para
        pure_len = len(re.sub(r'\s+', '', text))

    if pure_len > target_chars + 500:
        keep = int(len(text) * ((target_chars + 500) / pure_len))
        clipped = text[:keep]
        cut = max(clipped.rfind('。'), clipped.rfind('！'), clipped.rfind('？'))
        if cut > 0:
            text = clipped[:cut + 1]

    return text


# ── Beat Sheet 流水线编排 ─────────────────────────────────────────────────────

def run_draft_pipeline(
    project_root: Path,
    chapter_path: Path,
    writing_query: str,
    writing_constraints: Optional[Dict[str, Any]],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """运行草稿生成流水线：Beat Sheet 优先，回退到普通 draft。

    Args:
        project_root: 项目根目录
        chapter_path: 章节文件路径
        writing_query: 完整写作查询
        writing_constraints: 写作约束
        args: 参数命名空间

    Returns:
        草稿信息字典，包含 applied, mode, is_draft, fallback, error_msg
    """
    auto_draft_applied = False
    draft_provider_used = _resolve_draft_provider(args, project_root)
    fallback_applied = False
    llm_error_msg = None
    query = writing_query[:300] if writing_query else "推进下一章剧情"

    # Beat Sheet 流水线（优先于普通 draft，默认开启）
    if getattr(args, "use_beat_sheet", True) and chapter_is_draft_stub(chapter_path):
        _beat_chapter_no = chapter_no_from_name(chapter_path.name)
        if _beat_chapter_no > 0:
            beat_applied, beat_mode = _generate_beat_draft(
                project_root, chapter_path, _beat_chapter_no,
                writing_query, writing_constraints, args,
            )
            if beat_applied:
                auto_draft_applied = True
                draft_provider_used = beat_mode

    # 普通 draft 回退
    if chapter_is_draft_stub(chapter_path) and getattr(args, "auto_draft", True):
        if draft_provider_used == "llm":
            try:
                from novel_chapter_writer import write_chapter  # type: ignore[import]
                config_overrides = {}
                if getattr(args, "llm_provider", None):
                    config_overrides['ai_provider'] = args.llm_provider
                if getattr(args, "llm_model", None):
                    config_overrides['model'] = args.llm_model
                if getattr(args, "llm_api_key", None):
                    provider = args.llm_provider or 'openai'
                    if provider == 'openai':
                        config_overrides['openai_api_key'] = args.llm_api_key
                    elif provider == 'anthropic':
                        config_overrides['anthropic_api_key'] = args.llm_api_key
                    else:
                        config_overrides['api_key'] = args.llm_api_key

                llm_result = write_chapter(
                    project_root,
                    chapter_file=chapter_path,
                    config_overrides=config_overrides,
                    dry_run=False,
                    context_window=5,
                )

                if llm_result.get("ok"):
                    draft_provider_used = "llm"
                    auto_draft_applied = True
                else:
                    llm_error_msg = llm_result.get("error", "unknown error")
                    draft = generate_draft_text(project_root, chapter_path, query, min_chars=args.min_chars)
                    write_text(chapter_path, draft)
                    draft_provider_used = "template"
                    fallback_applied = True
                    auto_draft_applied = True

            except Exception as e:
                llm_error_msg = str(e)
                draft = generate_draft_text(project_root, chapter_path, query, min_chars=args.min_chars)
                write_text(chapter_path, draft)
                draft_provider_used = "template"
                fallback_applied = True
                auto_draft_applied = True

        elif draft_provider_used == "beat_sheet_template":
            beat_sheet_json = load_json(
                project_root / "00_memory" / "beats"
                / f"ch{chapter_no_from_name(chapter_path.name):04d}_beat_sheet.json",
                default={},
            )
            beat_goal = beat_sheet_json.get("chapter_goal", "") or query
            beat_summaries = [
                str(b.get("summary", ""))
                for b in beat_sheet_json.get("beats", [])
                if isinstance(b, dict) and b.get("summary") and "[待填充]" not in str(b.get("summary", ""))
            ]
            enriched_beat_query = beat_goal
            if beat_summaries:
                enriched_beat_query += "；" + "、".join(beat_summaries[:4])
            draft = generate_draft_text(
                project_root, chapter_path,
                enriched_beat_query[:300],
                min_chars=args.min_chars,
            )
            write_text(chapter_path, draft)
            auto_draft_applied = True
        else:
            draft = generate_draft_text(project_root, chapter_path, query, min_chars=args.min_chars)
            write_text(chapter_path, draft)
            auto_draft_applied = True

    return {
        "applied": auto_draft_applied,
        "mode": draft_provider_used,
        "is_draft": chapter_is_draft_stub(chapter_path),
        "fallback": fallback_applied,
        "error_msg": llm_error_msg,
    }
