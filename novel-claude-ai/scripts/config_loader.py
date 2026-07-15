#!/usr/bin/env python3
"""统一配置加载器

集中管理所有配置的加载、验证和覆盖机制。
支持多来源优先级：环境变量 > YAML配置文件 > 默认值。
所有配置模块通过 ConfigLoader 获取配置，确保一致性和可追溯性。
"""

import os
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, fields, asdict
from typing import Any, Dict, List, Set, Optional, Type, TypeVar, get_type_hints

T = TypeVar("T")

# =============================================================================
# 配置验证 Schema
# =============================================================================

@dataclass
class ConfigField:
    """单个配置字段的验证规则"""
    name: str
    field_type: type
    default: Any = None
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    env_var: Optional[str] = None
    description: str = ""


class ConfigSchema:
    """配置验证 Schema 定义"""

    QUALITY_SCHEMA = [
        ConfigField("min_chars", int, default=1200, min_value=100, max_value=50000,
                     env_var="QUALITY_MIN_CHARS", description="章节最小字数"),
        ConfigField("min_paragraphs", int, default=6, min_value=1, max_value=200,
                     env_var="QUALITY_MIN_PARAGRAPHS", description="章节最小段落数"),
        ConfigField("min_dialogue_ratio", float, default=0.03, min_value=0.0, max_value=1.0,
                     env_var="QUALITY_MIN_DIALOGUE_RATIO", description="对话占比下限"),
        ConfigField("max_stub_effective_chars", int, default=800, min_value=100, max_value=5000,
                     description="占位章有效字符上限"),
    ]

    RETRIEVAL_SCHEMA = [
        ConfigField("candidate_k", int, default=12, min_value=1, max_value=100,
                     env_var="RETRIEVAL_CANDIDATE_K", description="粗筛候选数"),
        ConfigField("top_k", int, default=4, min_value=1, max_value=50,
                     env_var="RETRIEVAL_TOP_K", description="精排返回数"),
        ConfigField("passage_max_chars", int, default=220, min_value=50, max_value=2000,
                     description="片段最大字符数"),
        ConfigField("passages_per_chapter", int, default=2, min_value=1, max_value=20,
                     description="每章提取片段数"),
        ConfigField("cache_max_entries", int, default=200, min_value=10, max_value=10000,
                     description="缓存最大条目数"),
        ConfigField("cache_ttl_seconds", int, default=3600, min_value=60, max_value=86400,
                     env_var="RETRIEVAL_CACHE_TTL", description="缓存过期时间(秒)"),
    ]

    FLOW_SCHEMA = [
        ConfigField("lock_timeout_seconds", int, default=300, min_value=30, max_value=3600,
                     env_var="FLOW_LOCK_TIMEOUT", description="执行锁超时(秒)"),
        ConfigField("lock_check_interval", float, default=0.5, min_value=0.1, max_value=10.0,
                     description="锁检查间隔(秒)"),
        ConfigField("snapshot_max_count", int, default=10, min_value=1, max_value=100,
                     description="最大保留快照数"),
        ConfigField("max_auto_retry_rounds", int, default=2, min_value=0, max_value=10,
                     env_var="FLOW_MAX_RETRY", description="最大自动重试轮数"),
        ConfigField("retry_delay_seconds", float, default=1.0, min_value=0.1, max_value=30.0,
                     description="重试延迟(秒)"),
        ConfigField("gate_artifacts_min_bytes", int, default=20, min_value=0, max_value=10000,
                     description="门禁产物最小字节数"),
    ]

    @classmethod
    def get_all_schemas(cls) -> Dict[str, List[ConfigField]]:
        return {
            "quality": cls.QUALITY_SCHEMA,
            "retrieval": cls.RETRIEVAL_SCHEMA,
            "flow": cls.FLOW_SCHEMA,
        }


# =============================================================================
# 配置验证器
# =============================================================================

class ConfigValidator:
    """配置值验证器"""

    @staticmethod
    def validate_field(field_def: ConfigField, value: Any) -> List[str]:
        """验证单个字段，返回错误列表"""
        errors = []

        # 类型检查
        expected = field_def.field_type
        if not isinstance(value, expected):
            try:
                value = expected(value)
            except (ValueError, TypeError):
                errors.append(
                    f"字段 '{field_def.name}' 类型错误: 期望 {expected.__name__}, "
                    f"实际 {type(value).__name__}"
                )
                return errors

        # 范围检查
        if field_def.min_value is not None and value < field_def.min_value:
            errors.append(
                f"字段 '{field_def.name}' 值 {value} 小于最小值 {field_def.min_value}"
            )
        if field_def.max_value is not None and value > field_def.max_value:
            errors.append(
                f"字段 '{field_def.name}' 值 {value} 大于最大值 {field_def.max_value}"
            )

        # 选项检查
        if field_def.choices is not None and value not in field_def.choices:
            errors.append(
                f"字段 '{field_def.name}' 值 '{value}' 不在允许选项 {field_def.choices} 中"
            )

        return errors

    @staticmethod
    def validate_config(schema: List[ConfigField], values: Dict[str, Any]) -> List[str]:
        """验证一组配置值，返回所有错误"""
        all_errors = []
        schema_map = {s.name: s for s in schema}

        for field_def in schema:
            if field_def.name in values:
                errs = ConfigValidator.validate_field(field_def, values[field_def.name])
                all_errors.extend(errs)
            elif field_def.required and field_def.default is None:
                all_errors.append(
                    f"必填字段 '{field_def.name}' 缺失且无默认值"
                )

        return all_errors


# =============================================================================
# 配置加载器
# =============================================================================

class ConfigLoader:
    """统一配置加载器

    加载优先级: 环境变量 > YAML文件 > 默认值
    支持配置验证、缓存和变更检测。
    """

    def __init__(self, project_root: Optional[str] = None):
        """初始化加载器

        Args:
            project_root: 项目根目录，None 则自动检测
        """
        if project_root:
            self._project_root = Path(project_root)
        else:
            self._project_root = self._detect_project_root()

        self._config_cache: Dict[str, Any] = {}
        self._config_hash: Optional[str] = None
        self._yaml_config: Optional[Dict[str, Any]] = None

    @staticmethod
    def _detect_project_root() -> Path:
        """向上查找项目根目录"""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / ".novel_writer_config.yaml").exists():
                return parent
            if (parent / "novel_writer_config.template.yaml").exists():
                return parent
        return current.parents[3]  # 默认: .agents/skills/novel-claude-ai/scripts -> 项目根

    def _load_yaml_config(self) -> Dict[str, Any]:
        """加载 YAML 配置文件（延迟加载）"""
        if self._yaml_config is not None:
            return self._yaml_config

        yaml_path = self._project_root / ".novel_writer_config.yaml"
        if not yaml_path.exists():
            self._yaml_config = {}
            return self._yaml_config

        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                self._yaml_config = yaml.safe_load(f) or {}
        except ImportError:
            # yaml 模块不可用时，回退到简单解析
            self._yaml_config = self._simple_yaml_parse(yaml_path)
        except Exception as e:
            print(f"[ConfigLoader] 警告: 加载 YAML 配置失败: {e}")
            self._yaml_config = {}

        return self._yaml_config

    @staticmethod
    def _simple_yaml_parse(path: Path) -> Dict[str, Any]:
        """简易 YAML 解析（无依赖回退方案）"""
        config = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        # 类型推断
                        if value.lower() == "true":
                            config[key] = True
                        elif value.lower() == "false":
                            config[key] = False
                        elif value.isdigit():
                            config[key] = int(value)
                        else:
                            try:
                                config[key] = float(value)
                            except ValueError:
                                config[key] = value
        except Exception:
            pass
        return config

    def get_env_value(self, env_var: str, default: Any = None) -> Any:
        """从环境变量获取值"""
        if env_var in os.environ:
            raw = os.environ[env_var]
            if isinstance(default, bool):
                return raw.lower() in ("true", "1", "yes")
            if isinstance(default, int):
                return int(raw)
            if isinstance(default, float):
                return float(raw)
            return raw
        return default

    def resolve_value(self, field_def: ConfigField, default: Any) -> Any:
        """解析单个配置值：环境变量 > YAML > 默认值"""
        # 1. 环境变量（最高优先级）
        if field_def.env_var:
            env_val = self.get_env_value(field_def.env_var, default=field_def.default)
            if env_val is not None:
                return env_val

        # 2. YAML 配置文件
        yaml_config = self._load_yaml_config()
        if field_def.name in yaml_config:
            return yaml_config[field_def.name]

        # 3. 默认值
        return default

    def load_config(self, schema: List[ConfigField]) -> Dict[str, Any]:
        """根据 schema 加载并验证配置"""
        values = {}
        for field_def in schema:
            values[field_def.name] = self.resolve_value(field_def, field_def.default)

        # 验证
        errors = ConfigValidator.validate_config(schema, values)
        if errors:
            for err in errors:
                print(f"[ConfigLoader] 配置验证警告: {err}")

        return values

    def get_config_hash(self, schema: List[ConfigField]) -> str:
        """获取当前配置的哈希值，用于变更检测"""
        values = self.load_config(schema)
        serialized = json.dumps(values, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode()).hexdigest()

    def reload(self):
        """强制重新加载所有配置"""
        self._yaml_config = None
        self._config_cache.clear()
        self._config_hash = None


# =============================================================================
# 便捷加载函数
# =============================================================================

_default_loader: Optional[ConfigLoader] = None


def get_loader(project_root: Optional[str] = None) -> ConfigLoader:
    """获取全局配置加载器实例"""
    global _default_loader
    if _default_loader is None or project_root is not None:
        _default_loader = ConfigLoader(project_root)
    return _default_loader


def load_quality_config() -> Dict[str, Any]:
    """加载质量检查配置"""
    loader = get_loader()
    return loader.load_config(ConfigSchema.QUALITY_SCHEMA)


def load_retrieval_config() -> Dict[str, Any]:
    """加载 RAG 检索配置"""
    loader = get_loader()
    return loader.load_config(ConfigSchema.RETRIEVAL_SCHEMA)


def load_flow_config() -> Dict[str, Any]:
    """加载流程执行配置"""
    loader = get_loader()
    return loader.load_config(ConfigSchema.FLOW_SCHEMA)


def load_all_configs() -> Dict[str, Dict[str, Any]]:
    """加载所有配置"""
    return {
        "quality": load_quality_config(),
        "retrieval": load_retrieval_config(),
        "flow": load_flow_config(),
    }


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "ConfigLoader",
    "ConfigSchema",
    "ConfigValidator",
    "ConfigField",
    "get_loader",
    "load_quality_config",
    "load_retrieval_config",
    "load_flow_config",
    "load_all_configs",
]
