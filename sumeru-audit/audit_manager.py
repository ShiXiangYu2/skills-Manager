#!/usr/bin/env python3
"""
Sumeru Audit Manager - 网文全局审查审计管理器
负责第一阶段（全局审查）和第二阶段（章节细节审查）
不执行修复操作，仅输出问题清单供sumeru-fix使用
"""
import os
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ChapterIssue:
    """章节问题"""
    chapter_id: str
    issue_type: str  # timeline, ooc, plot_hole, foreshadowing, word_count, quality
    severity: str  # fatal, serious, medium, minor
    description: str
    location: str  # 位置描述
    suggestion: str  # 修复建议
    line_range: Optional[Tuple[int, int]] = None


@dataclass
class GlobalIssue:
    """全局问题"""
    issue_type: str
    severity: str
    description: str
    affected_chapters: List[str]
    suggestion: str


@dataclass
class BottomLineItem:
    """底线问题项"""
    category: str  # timeline, setting, ooc, repetition, info_leak, foreshadow
    description: str
    severity: str
    status: str  # pending, fixed_light, fixed_rewrite, manual_required
    affected_chapters: List[str]
    suggestion: str


class AuditManager:
    """审查审计管理器"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.audit_dir = os.path.join(project_root, ".sumeru", "audit")
        self.summaries_dir = os.path.join(self.audit_dir, "summaries")
        self.issues_dir = os.path.join(self.audit_dir, "chapter-issues")
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.audit_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        os.makedirs(self.issues_dir, exist_ok=True)

    def load_chapter_files(self) -> List[Dict]:
        """加载所有章节文件"""
        chapters_dir = os.path.join(self.project_root, "chapters")
        if not os.path.exists(chapters_dir):
            return []

        chapters = []
        files = sorted([f for f in os.listdir(chapters_dir) if f.endswith('.md')])
        for f in files:
            path = os.path.join(chapters_dir, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            chapter_id = f.replace('.md', '')
            chapters.append({
                'id': chapter_id,
                'file': f,
                'path': path,
                'content': content,
                'word_count': len(content)
            })
        return chapters

    def load_outlines(self) -> Dict:
        """加载大纲数据"""
        outline_path = os.path.join(self.project_root, ".sumeru", "outline", "chapter-outlines.json")
        if os.path.exists(outline_path):
            with open(outline_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def calculate_agent_distribution(self, total_chapters: int, chapters_per_agent: int = 3) -> int:
        """计算需要的Agent数量"""
        return math.ceil(total_chapters / chapters_per_agent)

    def save_global_issues(self, issues: List[GlobalIssue], bottom_line: List[BottomLineItem]):
        """保存全局问题清单"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'issues': [asdict(i) for i in issues],
            'bottom_line': [asdict(b) for b in bottom_line]
        }
        path = os.path.join(self.audit_dir, "global-issues.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_bottom_line_checklist(self, bottom_line: List[BottomLineItem]):
        """保存底线问题清单"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'items': [asdict(b) for b in bottom_line]
        }
        path = os.path.join(self.audit_dir, "bottom-line-checklist.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_chapter_summary(self, chapter_id: str, summary: Dict):
        """保存章节概要"""
        path = os.path.join(self.summaries_dir, f"{chapter_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return path

    def save_chapter_issues(self, chapter_id: str, issues: List[ChapterIssue]):
        """保存章节问题"""
        data = {
            'chapter_id': chapter_id,
            'timestamp': datetime.now().isoformat(),
            'issues': [asdict(i) for i in issues]
        }
        path = os.path.join(self.issues_dir, f"{chapter_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def generate_audit_report(self) -> Dict:
        """生成审查报告汇总"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'global_issues': self._load_json(os.path.join(self.audit_dir, "global-issues.json")),
            'bottom_line': self._load_json(os.path.join(self.audit_dir, "bottom-line-checklist.json")),
            'chapter_issues': self._load_all_chapter_issues(),
            'summaries': self._load_all_summaries()
        }
        return report

    def _load_json(self, path: str) -> Optional[Dict]:
        """加载JSON文件"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _load_all_chapter_issues(self) -> Dict:
        """加载所有章节问题"""
        issues = {}
        if os.path.exists(self.issues_dir):
            for f in os.listdir(self.issues_dir):
                if f.endswith('.json'):
                    path = os.path.join(self.issues_dir, f)
                    with open(path, 'r', encoding='utf-8') as file:
                        issues[f.replace('.json', '')] = json.load(file)
        return issues

    def _load_all_summaries(self) -> Dict:
        """加载所有章节概要"""
        summaries = {}
        if os.path.exists(self.summaries_dir):
            for f in os.listdir(self.summaries_dir):
                if f.endswith('.json'):
                    path = os.path.join(self.summaries_dir, f)
                    with open(path, 'r', encoding='utf-8') as file:
                        summaries[f.replace('.json', '')] = json.load(file)
        return summaries


def create_audit_manager(project_root: str) -> AuditManager:
    """创建审查管理器实例"""
    return AuditManager(project_root)
