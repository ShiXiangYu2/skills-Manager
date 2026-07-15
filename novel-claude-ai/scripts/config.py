#!/usr/bin/env python3
"""集中配置管理模块

管理所有硬编码的配置值，支持百万字级别小说的创作流程。
所有配置可通过环境变量覆盖。

本模块通过 ConfigLoader 实现统一配置加载，支持多来源优先级：
环境变量 > YAML配置文件 > 默认值。
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

# 导入统一配置加载器
from config_loader import (
    ConfigLoader, ConfigSchema, ConfigValidator, get_loader,
    load_quality_config, load_retrieval_config, load_flow_config,
)


# =============================================================================
# 版本信息（统一从 VERSION 文件读取）
# =============================================================================

def _read_version() -> str:
    """从项目根目录的 VERSION 文件读取版本号"""
    version_file = None
    # 向上查找 VERSION 文件
    current = __file__
    for _ in range(10):
        parent = os.path.dirname(current)
        candidate = os.path.join(parent, "VERSION")
        if os.path.exists(candidate):
            version_file = candidate
            break
        if parent == current:
            break
        current = parent

    if version_file:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "8.0.0"  # 回退默认值


__version__ = _read_version()


# =============================================================================
# 配置数据类（保持向后兼容）
# =============================================================================

@dataclass
class QualityConfig:
    """质量检查配置"""

    # AI短语黑名单（去AI化检查）
    ai_phrase_blacklist: List[str] = field(default_factory=lambda: [
        "不禁", "仿佛", "映入眼帘", "心中暗道", "宛如",
        "似乎", "好像", "可能", "大概", "也许",
        "不由得", "不禁感到", "内心深处", "默默地",
    ])

    # 占位章检测参数
    max_stub_effective_chars: int = 800
    stub_marker: str = "<!-- NOVEL_FLOW_STUB -->"

    # 质量下限检查
    min_chars: int = 1200
    min_paragraphs: int = 6
    min_dialogue_ratio: float = 0.03

    # 发布判定关键词
    publish_keywords: List[str] = field(default_factory=lambda: [
        "可发布", "通过", "PASS", "审核通过", "质量合格"
    ])

    @classmethod
    def from_env(cls) -> "QualityConfig":
        """从 ConfigLoader 加载配置"""
        values = load_quality_config()
        config = cls()
        config.min_chars = values.get("min_chars", config.min_chars)
        config.min_paragraphs = values.get("min_paragraphs", config.min_paragraphs)
        config.min_dialogue_ratio = values.get("min_dialogue_ratio", config.min_dialogue_ratio)
        config.max_stub_effective_chars = values.get("max_stub_effective_chars", config.max_stub_effective_chars)
        return config


@dataclass
class RetrievalConfig:
    """RAG检索配置"""

    # 停用词表
    stopwords: Set[str] = field(default_factory=lambda: {
        "我们", "你们", "他们", "她们", "它们", "这个", "那个", "一种", "已经", "因为", "所以", "如果",
        "但是", "然后", "自己", "不是", "不会", "就是", "还是", "一个", "一些", "可以", "时候", "什么",
        "怎么", "这样", "那样", "起来", "进去", "出来", "一下", "一样", "以及", "并且", "或者", "然后",
        "这里", "那里", "这些", "那些", "这样", "那样", "如此", "非常", "十分", "相当", "真的",
    })

    # 检索触发关键词
    trigger_keywords: Set[str] = field(default_factory=lambda: {
        "冲突", "反转", "伏笔", "回收", "真相", "背叛", "联盟", "新角色", "时间线", "回忆",
        "穿越", "死亡", "复活", "势力", "升级", "突破", "决战", "危机", "转折", "悬念",
        "揭露", "身份", "秘密", "阴谋", "复仇", "救赎", "牺牲", "传承", "觉醒", "封印",
    })

    # 轻场景关键词（用于跳过检索）
    light_scene_keywords: Set[str] = field(default_factory=lambda: {
        "日常", "过渡", "环境描写", "吃饭", "赶路", "休整", "闲聊", "铺垫",
        "修炼", "冥想", "休息", "准备", "整理", "收拾", "散步", "观光",
    })

    # 检索参数
    candidate_k: int = 12  # 粗筛候选数
    top_k: int = 4  # 精排返回数
    passage_max_chars: int = 220  # 片段最大字符数
    passages_per_chapter: int = 2  # 每章提取片段数

    # 缓存配置
    cache_max_entries: int = 200
    cache_ttl_seconds: int = 3600  # 1小时过期

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """从 ConfigLoader 加载配置"""
        values = load_retrieval_config()
        config = cls()
        config.candidate_k = values.get("candidate_k", config.candidate_k)
        config.top_k = values.get("top_k", config.top_k)
        config.passage_max_chars = values.get("passage_max_chars", config.passage_max_chars)
        config.passages_per_chapter = values.get("passages_per_chapter", config.passages_per_chapter)
        config.cache_max_entries = values.get("cache_max_entries", config.cache_max_entries)
        config.cache_ttl_seconds = values.get("cache_ttl_seconds", config.cache_ttl_seconds)
        return config


@dataclass
class FlowConfig:
    """流程执行配置"""

    # 执行锁配置
    lock_timeout_seconds: int = 300  # 5分钟超时
    lock_check_interval: float = 0.5  # 检查间隔

    # 快照配置
    snapshot_max_count: int = 10  # 最大保留快照数

    # 重试配置
    max_auto_retry_rounds: int = 2
    retry_delay_seconds: float = 1.0

    # 门禁配置
    gate_artifacts_min_bytes: int = 20

    # 存储路径（相对于项目根目录）
    memory_dir: str = "00_memory"
    manuscript_dir: str = "03_manuscript"
    knowledge_base_dir: str = "02_knowledge_base"
    gate_artifacts_dir: str = "04_editing/gate_artifacts"
    retrieval_dir: str = "00_memory/retrieval"
    flow_dir: str = ".flow"

    @classmethod
    def from_env(cls) -> "FlowConfig":
        """从 ConfigLoader 加载配置"""
        values = load_flow_config()
        config = cls()
        config.lock_timeout_seconds = values.get("lock_timeout_seconds", config.lock_timeout_seconds)
        config.lock_check_interval = values.get("lock_check_interval", config.lock_check_interval)
        config.snapshot_max_count = values.get("snapshot_max_count", config.snapshot_max_count)
        config.max_auto_retry_rounds = values.get("max_auto_retry_rounds", config.max_auto_retry_rounds)
        config.retry_delay_seconds = values.get("retry_delay_seconds", config.retry_delay_seconds)
        config.gate_artifacts_min_bytes = values.get("gate_artifacts_min_bytes", config.gate_artifacts_min_bytes)
        return config


# =============================================================================
# 全局配置实例
# =============================================================================

# 懒加载的单例模式
_quality_config: Optional[QualityConfig] = None
_retrieval_config: Optional[RetrievalConfig] = None
_flow_config: Optional[FlowConfig] = None


def get_quality_config() -> QualityConfig:
    """获取质量配置（懒加载）"""
    global _quality_config
    if _quality_config is None:
        _quality_config = QualityConfig.from_env()
    return _quality_config


def get_retrieval_config() -> RetrievalConfig:
    """获取检索配置（懒加载）"""
    global _retrieval_config
    if _retrieval_config is None:
        _retrieval_config = RetrievalConfig.from_env()
    return _retrieval_config


def get_flow_config() -> FlowConfig:
    """获取流程配置（懒加载）"""
    global _flow_config
    if _flow_config is None:
        _flow_config = FlowConfig.from_env()
    return _flow_config


def reload_all_configs():
    """强制重新加载所有配置（清除缓存）"""
    global _quality_config, _retrieval_config, _flow_config
    _quality_config = None
    _retrieval_config = None
    _flow_config = None
    loader = get_loader()
    loader.reload()


__all__ = [
    "QualityConfig",
    "RetrievalConfig",
    "FlowConfig",
    "get_quality_config",
    "get_retrieval_config",
    "get_flow_config",
    "reload_all_configs",
    "__version__",
]
