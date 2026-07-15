#!/usr/bin/env python3
"""
中文章节字数统计工具
用法: python word_count.py <文件路径> [--target 4500] [--min 4200] [--max 4800]
输出: JSON 格式的字数统计结果

设计原则: AI 负责写和改，程序负责数。
"""
import json
import re
import sys
from pathlib import Path


def clean(text: str) -> str:
    """清洗文本，只保留有效正文字符"""
    # 去代码块
    text = re.sub(r"(?s)```.*?```", "", text)
    # 去 Markdown 标题
    text = re.sub(r"(?m)^#{1,6}\s.*$", "", text)
    # 去章节标题（如"第十一章 深海"）
    text = re.sub(r"(?m)^第.+章.*$", "", text)
    # 去作者有话说
    text = re.sub(r"(?s)作者有话说[:：].*$", "", text)
    # 去分隔符行
    text = re.sub(r"(?m)^\.+$", "", text)
    # 去所有空白
    text = re.sub(r"\s+", "", text)
    return text


def count_chinese(text: str) -> int:
    """只统计中文字符（含中文标点）"""
    return len(re.findall(r"[一-鿿　-〿＀-￯]", text))


def count_all_visible(text: str) -> int:
    """统计所有可见字符（含英文、数字、标点）"""
    return len(text)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="中文章节字数统计")
    parser.add_argument("file", help="章节文件路径")
    parser.add_argument("--target", type=int, default=4500, help="目标字数")
    parser.add_argument("--min", type=int, default=4200, help="合格区间下限")
    parser.add_argument("--max", type=int, default=4800, help="合格区间上限")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--chinese-only", action="store_true", help="只统计中文字符")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"error": f"文件不存在: {args.file}"}, ensure_ascii=False))
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    body = clean(text)

    if args.chinese_only:
        count = count_chinese(body)
    else:
        count = count_all_visible(body)

    delta = count - args.target
    if args.min <= count <= args.max:
        status = "PASS"
    elif count < args.min:
        status = "FAIL_SHORT"
    else:
        status = "FAIL_LONG"

    result = {
        "file": path.name,
        "count": count,
        "target": args.target,
        "range": [args.min, args.max],
        "delta": delta,
        "status": status,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {path.name}: {count} 字 (目标 {args.target}, 范围 {args.min}-{args.max}, 偏差 {delta:+d})")


if __name__ == "__main__":
    main()
