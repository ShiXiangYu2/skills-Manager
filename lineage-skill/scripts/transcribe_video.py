#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch course video/audio transcription via an OpenAI-compatible audio API."""

import os
import sys
import json
import time
import subprocess
import argparse
import requests
import shutil
import mimetypes
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = str(Path(__file__).resolve().parents[1])

AUDIO_TRANSCRIBE_API_KEY = os.getenv("AUDIO_TRANSCRIBE_API_KEY", "")
AUDIO_TRANSCRIBE_BASE_URL = os.getenv("AUDIO_TRANSCRIBE_BASE_URL", "https://api.openai.com/v1")
AUDIO_TRANSCRIBE_MODEL = os.getenv("AUDIO_TRANSCRIBE_MODEL", "whisper-1")
FFMPEG = os.getenv("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.getenv("FFPROBE") or shutil.which("ffprobe") or "ffprobe"
VIDEO_SUFFIXES = {".mp4"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = [
        FFMPEG, "-i", video_path,
        "-vn", "-acodec", "libmp3lame",
        "-q:a", "2", "-y", audio_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return result.returncode == 0 and os.path.exists(audio_path)
    except Exception as e:
        print(f"  音频提取异常: {e}")
        return False


def get_audio_duration(audio_path: str) -> float:
    cmd = [
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip()) if result.returncode == 0 else 0
    except Exception:
        return 0


def extract_audio_segment(audio_path: str, start: float, duration: float, output_path: str) -> bool:
    cmd = [
        FFMPEG,
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        audio_path,
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        "-y",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"  分段音频提取异常: {e}")
        return False


def transcribe_audio_api(audio_path: str, max_retries: int = 5) -> dict:
    if not AUDIO_TRANSCRIBE_API_KEY:
        raise ValueError("未设置 AUDIO_TRANSCRIBE_API_KEY")

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  音频: {file_size_mb:.1f}MB → {AUDIO_TRANSCRIBE_MODEL}")

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                time.sleep(min(2 ** attempt, 30))
                print(f"  重试 {attempt}/{max_retries} ...")

            with open(audio_path, "rb") as f:
                mime_type = mimetypes.guess_type(audio_path)[0] or "application/octet-stream"
                response = requests.post(
                    f"{AUDIO_TRANSCRIBE_BASE_URL.rstrip('/')}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {AUDIO_TRANSCRIBE_API_KEY}"},
                    files={"file": (os.path.basename(audio_path), f, mime_type)},
                    data={"model": AUDIO_TRANSCRIBE_MODEL},
                    timeout=300,
                )

            if response.status_code == 200:
                text = response.json().get("text", "").strip()
                if text:
                    duration = get_audio_duration(audio_path)
                    return {
                        "full_text": text,
                        "segments": [{"start": 0, "end": round(duration, 2), "text": text}],
                        "language": "zh",
                        "duration": round(duration, 2),
                        "engine": AUDIO_TRANSCRIBE_MODEL,
                    }
                print(f"  ⚠️ API 返回空文本")
            else:
                print(f"  API {response.status_code}: {response.text[:200]}")
        except requests.exceptions.Timeout:
            print(f"  超时 {attempt}/{max_retries}")
        except Exception as e:
            print(f"  异常 {attempt}/{max_retries}: {e}")

    raise Exception("音频转录 API 调用失败")


def transcribe_audio(audio_path: str, media_name: str, segment_minutes: int = 30, temp_dir: str | None = None) -> dict:
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    duration = get_audio_duration(audio_path)
    if file_size_mb <= 80:
        return transcribe_audio_api(audio_path)

    print(f"  音频较大，分段转写: {duration/60:.1f} 分钟, {segment_minutes} 分钟/段")
    segment_seconds = segment_minutes * 60
    segment_dir = temp_dir or os.path.dirname(audio_path)
    parts = []
    segments = []
    start = 0.0
    index = 1
    while start < duration:
        part_duration = min(segment_seconds, duration - start)
        part_path = os.path.join(
            segment_dir,
            f"{media_name}_segment_{index:02d}.mp3",
        )
        print(f"  分段 {index}: {start/60:.1f}-{(start+part_duration)/60:.1f} 分钟")
        if not extract_audio_segment(audio_path, start, part_duration, part_path):
            raise Exception(f"分段音频提取失败: {index}")
        try:
            part = transcribe_audio_api(part_path)
            text = part.get("full_text", "").strip()
            parts.append(text)
            segments.append({
                "start": round(start, 2),
                "end": round(start + part.get("duration", part_duration), 2),
                "text": text,
            })
        finally:
            if os.path.exists(part_path):
                os.remove(part_path)
        start += part_duration
        index += 1

    return {
        "full_text": "\n\n".join(part for part in parts if part),
        "segments": segments,
        "language": "zh",
        "duration": round(duration, 2),
        "engine": f"{AUDIO_TRANSCRIBE_MODEL}_segmented",
    }


def process_video(video_path: str, output_dir: str, media_name: str, force: bool = False) -> bool:
    output_path = os.path.join(output_dir, f"{media_name}_transcript.json")

    if os.path.exists(output_path) and not force:
        print(f"  ⏭ 跳过: {media_name}")
        return True

    print(f"\n{'='*60}")
    print(f"📹 {media_name}")

    audio_path = os.path.join(output_dir, f"{media_name}_temp_audio.mp3")
    print(f"  🎵 提取音频 ...")
    if not extract_audio(video_path, audio_path):
        print(f"  ❌ 音频提取失败")
        return False

    try:
        result = transcribe_audio(audio_path, media_name)
        result["video"] = media_name
        result["video_path"] = str(Path(video_path).absolute())
        result["source_type"] = "video"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  ✅ {len(result['full_text'])} 字, {result['duration']/60:.1f} 分钟")
        return True
    except Exception as e:
        print(f"  ❌ 转录失败: {e}")
        return False
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def process_audio(audio_path: str, output_dir: str, media_name: str, force: bool = False) -> bool:
    output_path = os.path.join(output_dir, f"{media_name}_transcript.json")

    if os.path.exists(output_path) and not force:
        print(f"  ⏭ 跳过: {media_name}")
        return True

    print(f"\n{'='*60}")
    print(f"🎧 {media_name}")

    try:
        result = transcribe_audio(audio_path, media_name, temp_dir=output_dir)
        result["video"] = media_name
        result["audio_path"] = str(Path(audio_path).absolute())
        result["source_type"] = "audio"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  ✅ {len(result['full_text'])} 字, {result['duration']/60:.1f} 分钟")
        return True
    except Exception as e:
        print(f"  ❌ 转录失败: {e}")
        return False


def media_output_name(path: Path, input_dir: Path) -> str:
    rel = path.relative_to(input_dir)
    if len(rel.parts) == 1:
        return path.stem
    prefix = "_".join(rel.parts[:-1])
    return f"{prefix}_{path.stem}"


def main():
    parser = argparse.ArgumentParser(description="批量视频/音频转写")
    parser.add_argument("--input-dir", required=True, help="视频或音频目录路径")
    parser.add_argument("--course-name", required=True, help="课程名称（用于输出子目录）")
    parser.add_argument("--base-dir", default=BASE_DIR, help="课程输出根目录，默认当前项目目录")
    parser.add_argument("--force", action="store_true", help="强制重新处理")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个媒体文件")
    args = parser.parse_args()

    output_dir = os.path.join(args.base_dir, args.course_name, "transcripts")
    os.makedirs(output_dir, exist_ok=True)

    input_dir = Path(args.input_dir).expanduser().resolve()
    media_files = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES
    )

    if not media_files:
        print(f"❌ 在 {args.input_dir} 中未找到支持的媒体文件: {', '.join(sorted(VIDEO_SUFFIXES | AUDIO_SUFFIXES))}")
        sys.exit(1)

    video_count = sum(1 for path in media_files if path.suffix.lower() in VIDEO_SUFFIXES)
    audio_count = sum(1 for path in media_files if path.suffix.lower() in AUDIO_SUFFIXES)

    if not AUDIO_TRANSCRIBE_API_KEY:
        print("❌ 未设置 AUDIO_TRANSCRIBE_API_KEY，请检查 .env")
        sys.exit(1)

    print(f"📂 {len(media_files)} 个媒体文件（视频 {video_count} / 音频 {audio_count}）")
    print(f"📁 {output_dir}")
    print(f"🤖 {AUDIO_TRANSCRIBE_MODEL}")

    if args.limit > 0:
        media_files = media_files[:args.limit]
        print(f"📏 限 {args.limit} 个")

    success = failed = 0
    used_names: dict[str, int] = {}
    for media_path in media_files:
        name = media_output_name(media_path, input_dir)
        count = used_names.get(name, 0)
        used_names[name] = count + 1
        if count:
            name = f"{name}_{count + 1}"

        if media_path.suffix.lower() in VIDEO_SUFFIXES:
            ok = process_video(str(media_path), output_dir, name, args.force)
        else:
            ok = process_audio(str(media_path), output_dir, name, args.force)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n✅ {success} / ❌ {failed} / 共 {len(media_files)}")


if __name__ == "__main__":
    main()
