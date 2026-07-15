#!/usr/bin/env python3
"""共享工具模块 - 消除代码重复

该模块集中管理所有脚本共享的工具函数，避免在多个文件中重复定义。
主要用于支持百万字级别长篇小说的创作流程。
"""

import datetime as dt
import functools
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# =============================================================================
# 预编译的正则表达式（性能优化）
# =============================================================================

_CHAPTER_RE = re.compile(r"^第\d+章.*\.md$")
_SLUGIFY_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff_-]+")
_CHARS_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_ENGLISH_RE = re.compile(r"[A-Za-z]{3,}")
_CHAPTER_NO_RE = re.compile(r"第(\d+)章")

# =============================================================================
# 文件系统操作
# =============================================================================


def ensure_dir(path: Path) -> None:
    """确保目录存在，不存在则递归创建。
    
    Args:
        path: 目录路径
    """
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, default: str = "") -> str:
    """安全读取文本文件。

    Args:
        path: 文件路径
        default: 文件不存在时的默认值

    Returns:
        文件内容，或默认值
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"[WARN] 文件编码问题 {path}: {e}")
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError):
        return default


def write_text(path: Path, content: str) -> bool:
    """安全写入文本文件。
    
    Args:
        path: 文件路径
        content: 写入内容
        
    Returns:
        是否写入成功
    """
    try:
        ensure_dir(path.parent)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return True
    except (IOError, PermissionError) as e:
        # 使用 print 而非 logging，保持与现有代码一致
        print(f"[ERROR] 写入失败 {path}: {e}")
        return False


# =============================================================================
# JSON 操作
# =============================================================================


def load_json(
    path: Path,
    default: Optional[Dict[str, Any]] = None,
    required_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """安全加载 JSON 文件，支持默认值和键校验。
    
    Args:
        path: JSON 文件路径
        default: 加载失败时的默认值
        required_keys: 必须存在的键列表
        
    Returns:
        解析后的字典，或默认值
    """
    if default is None:
        default = {}

    if not path.exists():
        return default.copy()

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)

        if not isinstance(obj, dict):
            return default.copy()

        # 校验必需字段
        if required_keys:
            missing = [k for k in required_keys if k not in obj]
            if missing:
                return default.copy()

        return obj

    except (json.JSONDecodeError, IOError, KeyError):
        return default.copy()


def save_json(
    path: Path, payload: Dict[str, Any], indent: int = 2
) -> bool:
    """安全保存 JSON 文件。
    
    Args:
        path: 文件路径
        payload: 要保存的字典
        indent: 缩进空格数
        
    Returns:
        是否保存成功
    """
    try:
        ensure_dir(path.parent)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
        return True
    except (IOError, TypeError) as e:
        print(f"[ERROR] 保存 JSON 失败 {path}: {e}")
        return False


# =============================================================================
# 文本处理
# =============================================================================


def slugify(text: str) -> str:
    """将文本转换为 URL/文件名友好的 slug。
    
    保留中文字符、字母、数字、下划线和连字符。
    
    Args:
        text: 原始文本
        
    Returns:
        转换后的 slug
    """
    s = _SLUGIFY_RE.sub("-", text).strip("-")
    return s or "chapter"


def normalize_text(text: str) -> str:
    """将连续空白替换为单个空格。"""
    return re.sub(r"\s+", " ", text).strip()


def count_chars(text: str, include_spaces: bool = False) -> int:
    """统计文本字符数（统一方法）。

    对于中文小说，通常统计中文字符数更准确。
    此方法同时支持：
    - 纯中文字符统计（默认）
    - 包含所有非空白字符统计

    Args:
        text: 输入文本
        include_spaces: 是否包含空格和标点

    Returns:
        字符数
    """
    if include_spaces:
        # 统计所有非空白字符
        return len(re.sub(r"\s+", "", text))
    else:
        # 仅统计中文字符（更适合中文小说）
        return len(re.findall(r'[\u4e00-\u9fff]', text))


def sha1_text(text: str) -> str:
    """计算文本的 SHA1 哈希值。
    
    Args:
        text: 输入文本
        
    Returns:
        SHA1 哈希字符串
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def file_sha1(path: Path) -> str:
    """计算文件的 SHA1 哈希值。
    
    Args:
        path: 文件路径
        
    Returns:
        文件内容的 SHA1 哈希，文件不存在返回空字符串
    """
    if not path.exists():
        return ""
    return sha1_text(path.read_text(encoding="utf-8", errors="ignore"))


# =============================================================================
# 章节相关工具
# =============================================================================


def is_chapter_file(filename: str) -> bool:
    """判断文件名是否为章节文件。
    
    章节文件名格式：第XX章[标题].md
    
    Args:
        filename: 文件名
        
    Returns:
        是否为章节文件
    """
    return bool(_CHAPTER_RE.match(filename))


def chapter_no_from_name(filename: str) -> int:
    """从章节文件名提取章节序号。
    
    Args:
        filename: 章节文件名，如 "第15章 突破.md"
        
    Returns:
        章节序号，提取失败返回0
    """
    match = _CHAPTER_NO_RE.search(filename)
    if match:
        return int(match.group(1))
    return 0


def normalize_chapter_filename(chapter_no: int, title: str = "") -> str:
    """生成标准化的章节文件名。
    
    Args:
        chapter_no: 章节序号
        title: 章节标题（可选）
        
    Returns:
        标准化文件名，如 "第15章 突破.md"
    """
    if title:
        # 清理标题中的非法字符
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        return f"第{chapter_no}章 {clean_title}.md"
    return f"第{chapter_no}章.md"


# =============================================================================
# 缓存相关工具
# =============================================================================


def generate_cache_key(*components: str) -> str:
    """生成缓存键。
    
    Args:
        *components: 缓存键组成部分
        
    Returns:
        哈希后的缓存键
    """
    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


# =============================================================================
# 文件锁工具
# =============================================================================


def _try_create_lock_file(lock_path: Path, payload_dict: Dict[str, Any]) -> bool:
    """使用 O_CREAT|O_EXCL 原子创建锁文件，避免 TOCTOU 竞争窗口。

    Args:
        lock_path: 锁文件路径
        payload_dict: 写入锁文件的元数据

    Returns:
        是否成功创建锁文件
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(lock_path), flags, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload_dict, fh, ensure_ascii=False)
    return True


def acquire_file_lock(
    lock_path: Path, owner_id: str, timeout_sec: int = 1800
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """获取排他文件锁。

    使用原子创建 + 过期回收策略，支持超时检测。

    Args:
        lock_path: 锁文件路径
        owner_id: 锁持有者标识（如 run_id）
        timeout_sec: 锁超时时间（秒）

    Returns:
        (是否成功获取锁, 已有锁的元数据 或 None)
    """
    now = time.time()
    payload: Dict[str, Any] = {
        "owner_id": owner_id,
        "pid": os.getpid(),
        "ts": now,
        "started_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if _try_create_lock_file(lock_path, payload):
        return True, None

    if not lock_path.exists():
        return False, None

    existing_stat = lock_path.stat()
    try:
        current = load_json(lock_path, {})
    except Exception:
        current = {}
    ts_raw = current.get("ts", 0)
    ts = float(ts_raw) if isinstance(ts_raw, (int, float, str)) else 0.0
    if ts and (now - ts) < max(1, timeout_sec):
        return False, current

    # 回收过期锁前再次确认文件未被其他进程替换
    try:
        latest_stat = lock_path.stat()
    except FileNotFoundError:
        if _try_create_lock_file(lock_path, payload):
            return True, None
        return False, load_json(lock_path, {})

    if (
        latest_stat.st_ino != existing_stat.st_ino
        or latest_stat.st_mtime_ns != existing_stat.st_mtime_ns
    ):
        return False, load_json(lock_path, {})

    lock_path.unlink(missing_ok=True)
    if _try_create_lock_file(lock_path, payload):
        return True, None
    return False, load_json(lock_path, {})


def release_file_lock(lock_path: Path, owner_id: str) -> None:
    """释放文件锁（仅当当前持有者匹配时）。

    Args:
        lock_path: 锁文件路径
        owner_id: 锁持有者标识
    """
    if not lock_path.exists():
        return
    try:
        cur = load_json(lock_path, {})
    except Exception:
        return
    if cur.get("owner_id") == owner_id or cur.get("run_id") == owner_id:
        lock_path.unlink(missing_ok=True)


def save_json_atomic(
    path: Path, payload: Dict[str, Any], indent: int = 2
) -> bool:
    """原子保存 JSON 文件：先写临时文件，再 rename，避免写入中断导致损坏。

    Args:
        path: 目标文件路径
        payload: 要保存的字典
        indent: 缩进空格数

    Returns:
        是否保存成功
    """
    try:
        ensure_dir(path.parent)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
        # Windows 上 rename 需要先删除目标文件
        if path.exists():
            path.unlink()
        tmp_path.rename(path)
        return True
    except (IOError, TypeError, OSError) as e:
        print(f"[ERROR] 原子保存 JSON 失败 {path}: {e}")
        return False


# =============================================================================
# 版本信息
# =============================================================================

def _read_version() -> str:
    """从项目根目录的 VERSION 文件读取版本号"""
    current = __file__
    for _ in range(10):
        parent = os.path.dirname(current)
        candidate = os.path.join(parent, "VERSION")
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        if parent == current:
            break
        current = parent
    return "8.0.0"


__version__ = _read_version()
__all__ = [
    # 文件系统
    "ensure_dir",
    "read_text",
    "write_text",
    # JSON
    "load_json",
    "save_json",
    "save_json_atomic",
    # 文本处理
    "slugify",
    "normalize_text",
    "sha1_text",
    "file_sha1",
    # 章节相关
    "is_chapter_file",
    "chapter_no_from_name",
    "normalize_chapter_filename",
    # 缓存
    "generate_cache_key",
    # 文件锁
    "acquire_file_lock",
    "release_file_lock",
]
