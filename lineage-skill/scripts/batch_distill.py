#!/usr/bin/env python3
"""批量蒸馏 数字生命卡兹克 所有视频"""
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
VIDEO_DIR = Path("D:/视频下载/数字生命卡兹克")
COURSE_NAME = "shuzishengming-kazike"
PY = sys.executable

# 找到所有 BV 视频文件夹
video_dirs = sorted([
    d for d in VIDEO_DIR.iterdir()
    if d.is_dir() and d.name.startswith("BV")
])

print(f"发现 {len(video_dirs)} 个视频文件夹")
print(f"课程名: {COURSE_NAME}")

# 检查每个文件夹里有没有 mp4
for d in video_dirs:
    mp4s = list(d.glob("*.mp4"))
    if not mp4s:
        print(f"  ⚠️ {d.name}: 无 mp4 文件")

# 构建命令：运行完整流水线
# 先做一遍完整蒸馏，后续可以用 --skip-* 跳过已完成阶段
cmd = [
    PY, str(ROOT / "scripts" / "run_course_pipeline.py"),
    "--input-dir", str(VIDEO_DIR),
    "--course-name", COURSE_NAME,
    "--mode", "mentor,expert,practitioner",
    "--scope", "auto",
    "--evidence", "standard",
    "--chunk-minutes", "12",
    "--keyframe-interval-seconds", "60",
    "--keyframe-frames-per-sheet", "48",
]

print("\n执行命令:")
print(" ".join(cmd))

# 执行
result = subprocess.run(cmd, cwd=str(ROOT))
sys.exit(result.returncode)
