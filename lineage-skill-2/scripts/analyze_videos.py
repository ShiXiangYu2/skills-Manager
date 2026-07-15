#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch course visual analysis with optional supplemental screenshot markers."""

import os
import re
import subprocess
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from llm_client import analyze_video_with_vision_model

load_dotenv()

BASE_DIR = str(Path(__file__).resolve().parents[1])
FFMPEG = os.getenv("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.getenv("FFPROBE") or shutil.which("ffprobe") or "ffprobe"


COURSE_ANALYSIS_PROMPT = """请观看这段课程视频，提取教学内容干货。

## 分析要求

### 一、核心知识点
逐条列出本片段涉及的具体概念、方法论、模型、技巧：
1. ...
2. ...

### 二、补充截图标记

**【截图标记规则 —— 只标实质教学画面】**

只有画面满屏都是实质性知识内容时，才用 `[SCREENSHOT MM:SS]` 标记：

✅ **应该标记**：满屏文字列表（≥3要点）、数据表格/图表、思维导图、公式/模型图、软件操作界面、实物展示细节

❌ **不应标记**：人脸特写、标题/封面页、空白桌面、暖场聊天画面、模糊内容

格式（描述越具体越好）：
```
[SCREENSHOT 05:23] 满屏PPT，标题"核心方法论"，含数据曲线图+三个要点列表
[SCREENSHOT 12:45] 板书手写公式及推导过程，标注了关键变量定义
[SCREENSHOT 28:10] 软件后台数据看板，展示关键指标的变化趋势和漏斗
```

如果完全没有值得截图的内容，写「本段无干货画面」

注意：这些截图标记只是视频分析阶段的补充线索。最终关键帧证据由后续模型精选关键帧流程从候选帧 contact sheet 中选择。

### 三、教学结构
- 本段讲了什么主题
- 内容组织逻辑（怎么展开的）
- 有没有总结

### 四、案例与举例
讲者提到的具体案例、数据、故事（越具体越好）

### 五、金句与核心观点
讲者的重要原话或关键论断

注意：只关注教学内容，不要描述讲者外貌、讲课风格、语速等。基于真实内容，不要虚构。"""


def get_video_duration(video_path: str) -> float:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(r.stdout.strip()) if r.returncode == 0 else 0


def compress_720p(input_path: str, output_path: str) -> bool:
    """压缩到 720p，适合 API 上传"""
    cmd = [
        FFMPEG, "-i", input_path,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k",
        "-y", output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"  压缩失败: {e}")
        return False


def compress_480p(input_path: str, output_path: str) -> bool:
    """激进压缩到 480p，用于超大视频分片"""
    cmd = [
        FFMPEG, "-i", input_path,
        "-vf", "scale=-2:480",
        "-c:v", "libx264", "-preset", "fast", "-crf", "32",
        "-c:a", "aac", "-b:a", "48k",
        "-y", output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"  480p 压缩失败: {e}")
        return False


def split_video_chunks(video_path: str, chunk_secs: int, output_dir: str, video_name: str) -> list:
    """按时间切分视频，返回 [(chunk_path, start_offset_sec), ...]"""
    duration = get_video_duration(video_path)
    if duration == 0 or duration <= chunk_secs * 1.1:
        return [(video_path, 0.0)]

    num = max(1, int(duration / chunk_secs))
    # 最后一片太短就合并
    if duration - (num - 1) * chunk_secs < 120 and num > 1:
        num -= 1
    actual_dur = duration / num

    chunks = []
    for i in range(num):
        start = i * actual_dur
        dur = actual_dur if i < num - 1 else duration - start
        cp = os.path.join(output_dir, f"{video_name}_chunk_{i+1:02d}.mp4")
        cmd = [FFMPEG, "-y", "-ss", str(start), "-i", video_path,
               "-t", str(dur), "-c", "copy",
               "-avoid_negative_ts", "make_zero", cp]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if os.path.exists(cp) and os.path.getsize(cp) > 0:
                chunks.append((cp, start))
                print(f"  片段 {i+1}/{num}: offset={start/60:.0f}min, {os.path.getsize(cp)/(1024*1024):.0f}MB")
        except Exception as e:
            print(f"  切分失败: {e}")

    return chunks if chunks else [(video_path, 0.0)]


def analyze_chunk(chunk_path: str, chunk_idx: int, total: int, offset_sec: float,
                  tmp_dir: str) -> dict:
    """分析单个视频片段，超大时自动二次压缩"""
    label = f"片段 {chunk_idx+1}/{total}" if total > 1 else "完整视频"
    chunk_dur = get_video_duration(chunk_path)
    raw_mb = os.path.getsize(chunk_path) / (1024 * 1024)

    work_path = chunk_path
    temp_result = None

    # 如果原始文件 > 35MB（base64 后约 47MB，可能超 API 限制），二次压缩到 480p
    if raw_mb > 35:
        compressed = os.path.join(tmp_dir, f"chunk_{chunk_idx+1}_480p.mp4")
        print(f"  📦 片段太大 ({raw_mb:.0f}MB)，二次压缩到 480p ...")
        if compress_480p(chunk_path, compressed):
            work_path = compressed
            compressed_mb = os.path.getsize(compressed) / (1024 * 1024)
            print(f"     ✅ {compressed_mb:.0f}MB")
        else:
            print(f"     ⚠️ 二次压缩失败，尝试直接发送")

    prompt = COURSE_ANALYSIS_PROMPT
    if total > 1:
        prompt += f"\n\n（第 {chunk_idx+1}/{total} 片段，约 {chunk_dur/60:.0f} 分钟。SCREENSHOT 时间点为片段内相对时间）"
    else:
        prompt += "\n\n注意：这是完整的视频内容，请尽可能详细地分析。"

    final_mb = os.path.getsize(work_path) / (1024 * 1024)
    print(f"  🤖 {label} ({chunk_dur/60:.0f}min, {final_mb:.0f}MB) ...")

    result = analyze_video_with_vision_model(work_path, prompt)

    content = result.get("content", "")
    if result.get("error"):
        content = f"**错误**: {result['error']}\n\n{content}"

    # 清理临时压缩文件
    if work_path != chunk_path and os.path.exists(work_path):
        try:
            os.remove(work_path)
        except Exception:
            pass

    return {
        "chunk_index": chunk_idx + 1,
        "offset_sec": offset_sec,
        "content": content,
    }


def image_hash(img_path: str) -> str:
    """计算图片的感知哈希（aHash），用于去重"""
    from PIL import Image
    img = Image.open(img_path).convert("L").resize((16, 16), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def hamming_distance(h1: str, h2: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def deduplicate_screenshots(screenshots: list, screenshot_dir: str,
                            threshold: int = 8) -> list:
    """基于感知哈希去重，过滤相似画面（Hamming 距离 < threshold 视为重复）"""
    if len(screenshots) <= 1:
        return screenshots

    # 先提取所有截图的哈希
    hashes = {}
    for s in screenshots:
        # 找到对应的文件
        fname = f"{s['ts'].replace(':', '_')}_{s['desc'][:40].replace('/', '_').replace(' ', '_')}.jpg"
        spath = os.path.join(screenshot_dir, fname)
        if os.path.exists(spath):
            hashes[spath] = image_hash(spath)

    # 贪心去重：按时间顺序保留第一个，移除后续相似的
    kept = []
    for s in screenshots:
        fname = f"{s['ts'].replace(':', '_')}_{s['desc'][:40].replace('/', '_').replace(' ', '_')}.jpg"
        spath = os.path.join(screenshot_dir, fname)
        if spath not in hashes:
            kept.append(s)
            continue

        h = hashes[spath]
        is_dup = False
        for k in kept:
            kfname = f"{k['ts'].replace(':', '_')}_{k['desc'][:40].replace('/', '_').replace(' ', '_')}.jpg"
            kspath = os.path.join(screenshot_dir, kfname)
            if kspath in hashes and hamming_distance(h, hashes[kspath]) < threshold:
                # 删除重复文件
                try:
                    os.remove(spath)
                except Exception:
                    pass
                is_dup = True
                break

        if not is_dup:
            kept.append(s)

    removed = len(screenshots) - len(kept)
    if removed > 0:
        print(f"    🧹 去重: 移除 {removed} 张重复截图")

    return kept


def parse_screenshots(content: str, offset_sec: float = 0) -> list:
    """从分析内容中提取 [SCREENSHOT MM:SS] 时间点，转换为全局时间"""
    pattern = r'\[SCREENSHOT\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.+?)(?=\n|$)'
    screenshots = []
    for m in re.finditer(pattern, content):
        mm = int(m.group(1))
        ss = int(m.group(2))
        rel_sec = mm * 60 + ss
        global_sec = rel_sec + offset_sec
        desc = m.group(4).strip()
        ts_label = f"{int(global_sec//60):02d}:{int(global_sec%60):02d}"
        screenshots.append({"global_sec": global_sec, "rel_sec": rel_sec, "ts": ts_label, "desc": desc[:80]})
    return screenshots


def extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """从视频指定时间提取一帧"""
    cmd = [FFMPEG, "-y", "-ss", str(time_sec), "-i", video_path,
           "-vframes", "1", "-q:v", "2", output_path]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def process_video(video_path: str, output_dir: str, tmp_dir: str,
                  chunk_minutes: int = 12, force: bool = False) -> bool:
    """处理单个视频：压缩 → 分片 → 视觉分析 → 抽取补充截图"""
    video_name = Path(video_path).stem
    analysis_path = os.path.join(output_dir, f"{video_name}_analysis.md")
    screenshot_dir = os.path.join(output_dir, "screenshots", video_name)

    if os.path.exists(analysis_path) and not force:
        print(f"  ⏭ 跳过: {video_name}")
        return True

    print(f"\n{'='*60}")
    print(f"🔍 {video_name}")

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    duration = get_video_duration(video_path)
    print(f"   {file_size_mb:.0f}MB, {duration/60:.1f} 分钟")

    chunk_secs = chunk_minutes * 60
    need_compress = file_size_mb > 400  # 超过 400MB 先压缩
    need_split = duration > chunk_secs * 1.1
    temp_files = []
    work_video = video_path

    # 压缩
    if need_compress:
        print(f"  📦 压缩到 720p ...")
        compressed = os.path.join(tmp_dir, f"{video_name}_720p.mp4")
        if compress_720p(video_path, compressed):
            temp_files.append(compressed)
            work_video = compressed
            new_size = os.path.getsize(compressed) / (1024 * 1024)
            print(f"  ✅ {new_size:.0f}MB")
        else:
            print(f"  ⚠️ 压缩失败，用原视频")

    # 分片
    if need_split:
        print(f"  ✂️ 分片（每段 {chunk_minutes} 分钟）...")
        chunks = split_video_chunks(work_video, chunk_secs, tmp_dir, video_name)
        for cp, _ in chunks:
            if cp != work_video:
                temp_files.append(cp)
    else:
        chunks = [(work_video, 0.0)]

    print(f"  📊 {len(chunks)} 个片段待分析")

    # 分析每个片段
    all_analyses = []
    all_screenshots = []
    for i, (cp, offset) in enumerate(chunks):
        analysis = analyze_chunk(cp, i, len(chunks), offset, tmp_dir)
        all_analyses.append(analysis)

        # 解析截图标记
        shots = parse_screenshots(analysis["content"], offset)
        if shots:
            print(f"    📸 发现 {len(shots)} 个补充截图标记")
            all_screenshots.extend(shots)

    # 去重截图（基于时间戳，相同秒数只保留一个）
    seen_ts = set()
    all_shots_deduped = []
    for s in all_screenshots:
        ts_key = s["ts"]
        if ts_key not in seen_ts:
            seen_ts.add(ts_key)
            all_shots_deduped.append(s)

    # 先提取截图（从原视频，保证画质）
    if all_shots_deduped:
        os.makedirs(screenshot_dir, exist_ok=True)
        print(f"  📸 提取 {len(all_shots_deduped)} 张补充截图 ...")
        extracted = 0
        for s in all_shots_deduped:
            fname = f"{s['ts'].replace(':', '_')}_{s['desc'][:40].replace('/', '_').replace(' ', '_')}.jpg"
            spath = os.path.join(screenshot_dir, fname)
            if extract_frame(video_path, s["global_sec"], spath):
                extracted += 1

        # 感知哈希去重
        all_shots_deduped = deduplicate_screenshots(all_shots_deduped, screenshot_dir)
        final_count = len([f for f in os.listdir(screenshot_dir) if f.endswith('.jpg')])
        print(f"  ✅ {final_count} 张补充截图")
    else:
        final_count = 0

    # 合并分析结果（截图数量用去重后的）
    parts = [
        f"# {video_name} — 视频内容分析\n",
        f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**大小**: {file_size_mb:.0f}MB | **时长**: {duration/60:.1f} 分钟 | **片段**: {len(chunks)}\n",
    ]
    if final_count > 0:
        parts.append(f"**补充截图**: {final_count} 张\n")
    parts.append("\n---\n")

    for a in all_analyses:
        if len(all_analyses) > 1:
            offset_min = a["offset_sec"] / 60
            parts.append(f"\n## 片段 {a['chunk_index']}（偏移 {offset_min:.0f}min）\n")
        parts.append(a["content"] + "\n")

    if all_shots_deduped:
        parts.append("\n---\n\n## 补充截图索引\n\n")
        for s in all_shots_deduped:
            parts.append(f"- `[{s['ts']}]` {s['desc']}\n")

    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"  💾 {analysis_path}")

    # 清理临时文件
    for tf in temp_files:
        try:
            os.remove(tf)
        except Exception:
            pass

    return True


def main():
    parser = argparse.ArgumentParser(description="批量视频画面分析 + 补充截图标记")
    parser.add_argument("--input-dir", required=True, help="视频目录")
    parser.add_argument("--course-name", required=True, help="课程名称")
    parser.add_argument("--base-dir", default=BASE_DIR, help="课程输出根目录，默认当前项目目录")
    parser.add_argument("--chunk-minutes", type=int, default=12, help="分片时长（分钟）")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-at", type=int, default=0)
    args = parser.parse_args()

    output_dir = os.path.join(args.base_dir, args.course_name, "analysis")
    os.makedirs(output_dir, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix="video_analysis_")

    video_files = sorted(
        str(path)
        for path in Path(args.input_dir).rglob("*")
        if path.is_file() and path.suffix.lower() == ".mp4"
    )

    if not video_files:
        print("ℹ️ 未找到 .mp4，跳过视频画面分析")
        return

    if args.start_at > 0:
        video_files = video_files[args.start_at:]
    if args.limit > 0:
        video_files = video_files[:args.limit]

    print(f"📂 {len(video_files)} 个视频 → {output_dir}")
    print(f"⏱️  分片: {args.chunk_minutes} 分钟/段")

    success = failed = 0
    try:
        for vf in video_files:
            if process_video(vf, output_dir, tmp_dir, args.chunk_minutes, args.force):
                success += 1
            else:
                failed += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n✅ {success} / ❌ {failed} / 共 {len(video_files)}")


if __name__ == "__main__":
    main()
