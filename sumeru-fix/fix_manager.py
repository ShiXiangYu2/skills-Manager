#!/usr/bin/env python3
"""
Sumeru Fix Manager - 网文问题统一修复管理器
基于sumeru-audit的审查结果，执行轻量修复、大纲修订、章节重写
"""
import os
import json
import math
import shutil
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FixTask:
    """修复任务"""
    task_id: str
    task_type: str  # light_fix, outline_revision, chapter_rewrite, bottom_line_fix
    severity: str  # fatal, serious, medium, minor
    description: str
    affected_chapters: List[str]
    status: str  # pending, in_progress, completed, failed
    fix_plan: Dict = None


@dataclass
class OutlineRevision:
    """大纲修订记录"""
    chapter_id: str
    revision_type: str
    reason: str
    before: Dict
    after: Dict
    timestamp: str


@dataclass
class BottomLineFix:
    """底线问题修复记录"""
    category: str
    description: str
    status: str  # fixed_light, fixed_rewrite, manual_required
    solution: str
    manual_suggestion: Optional[str] = None


class FixManager:
    """修复管理器"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.fix_dir = os.path.join(project_root, ".sumeru", "fix")
        self.audit_dir = os.path.join(project_root, ".sumeru", "audit")
        self.original_dir = os.path.join(project_root, ".sumeru", "write", "original")
        self.rewrite_dir = os.path.join(self.fix_dir, "rewrite-chapters")
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.fix_dir, exist_ok=True)
        os.makedirs(self.original_dir, exist_ok=True)
        os.makedirs(self.rewrite_dir, exist_ok=True)

    def load_audit_results(self) -> Dict:
        """加载审查结果"""
        results = {
            'global_issues': self._load_json(os.path.join(self.audit_dir, "global-issues.json")),
            'bottom_line': self._load_json(os.path.join(self.audit_dir, "bottom-line-checklist.json")),
            'chapter_issues': {}
        }

        issues_dir = os.path.join(self.audit_dir, "chapter-issues")
        if os.path.exists(issues_dir):
            for f in os.listdir(issues_dir):
                if f.endswith('.json'):
                    chapter_id = f.replace('.json', '')
                    results['chapter_issues'][chapter_id] = self._load_json(os.path.join(issues_dir, f))

        return results

    def _load_json(self, path: str) -> Optional[Dict]:
        """加载JSON文件"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def backup_chapter(self, chapter_id: str) -> str:
        """备份章节文件"""
        chapter_path = os.path.join(self.project_root, "chapters", f"{chapter_id}.md")
        if os.path.exists(chapter_path):
            backup_path = os.path.join(self.original_dir, f"{chapter_id}.md")
            shutil.copy2(chapter_path, backup_path)
            return backup_path
        return None

    def restore_chapter(self, chapter_id: str) -> bool:
        """从备份恢复章节"""
        backup_path = os.path.join(self.original_dir, f"{chapter_id}.md")
        chapter_path = os.path.join(self.project_root, "chapters", f"{chapter_id}.md")
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, chapter_path)
            return True
        return False

    def save_fix_plan(self, tasks: List[FixTask]) -> str:
        """保存修复计划"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'tasks': [asdict(t) for t in tasks]
        }
        path = os.path.join(self.fix_dir, "fix-plan.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_fix_report(self, report: Dict) -> str:
        """保存修复报告"""
        data = {
            'timestamp': datetime.now().isoformat(),
            **report
        }
        path = os.path.join(self.fix_dir, "fix-report.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_outline_revision(self, revision: OutlineRevision) -> str:
        """保存大纲修订记录"""
        revisions_path = os.path.join(self.fix_dir, "outline-revisions.json")
        revisions = self._load_json(revisions_path) or {'revisions': []}
        revisions['revisions'].append(asdict(revision))
        revisions['timestamp'] = datetime.now().isoformat()

        with open(revisions_path, 'w', encoding='utf-8') as f:
            json.dump(revisions, f, ensure_ascii=False, indent=2)
        return revisions_path

    def save_bottom_line_fixes(self, fixes: List[BottomLineFix]) -> str:
        """保存底线问题修复记录"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'fixes': [asdict(f) for f in fixes]
        }
        path = os.path.join(self.fix_dir, "bottom-line-fixes.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_fixed_issues(self, fixed_issues: List[Dict]) -> str:
        """保存已修复问题记录"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'fixed_issues': fixed_issues
        }
        path = os.path.join(self.fix_dir, "issues-fixed.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def save_rewrite_comparison(self, chapter_id: str, before: str, after: str) -> str:
        """保存章节重写对比"""
        data = {
            'chapter_id': chapter_id,
            'timestamp': datetime.now().isoformat(),
            'before': before,
            'after': after
        }
        path = os.path.join(self.rewrite_dir, f"{chapter_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def create_fix_tasks(self, audit_results: Dict) -> List[FixTask]:
        """根据审查结果创建修复任务"""
        tasks = []

        # 处理全局问题
        if audit_results.get('global_issues'):
            for issue in audit_results['global_issues'].get('issues', []):
                task = FixTask(
                    task_id=f"global_{issue['issue_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    task_type='light_fix',
                    severity=issue['severity'],
                    description=issue['description'],
                    affected_chapters=issue.get('affected_chapters', []),
                    status='pending'
                )
                tasks.append(task)

        # 处理章节问题
        for chapter_id, chapter_data in audit_results.get('chapter_issues', {}).items():
            if chapter_data and 'issues' in chapter_data:
                for issue in chapter_data['issues']:
                    task = FixTask(
                        task_id=f"chapter_{chapter_id}_{issue['issue_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        task_type='light_fix',
                        severity=issue['severity'],
                        description=f"Chapter {chapter_id}: {issue['description']}",
                        affected_chapters=[chapter_id],
                        status='pending'
                    )
                    tasks.append(task)

        # 处理底线问题
        if audit_results.get('bottom_line'):
            for item in audit_results['bottom_line'].get('items', []):
                if item['status'] == 'pending':
                    task = FixTask(
                        task_id=f"bottom_line_{item['category']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        task_type='bottom_line_fix',
                        severity=item['severity'],
                        description=item['description'],
                        affected_chapters=item.get('affected_chapters', []),
                        status='pending'
                    )
                    tasks.append(task)

        # 按严重程度排序
        severity_order = {'fatal': 0, 'serious': 1, 'medium': 2, 'minor': 3}
        tasks.sort(key=lambda x: severity_order.get(x.severity, 4))

        return tasks

    def calculate_agent_distribution(self, chapters: List[str], chapters_per_agent: int = 3) -> Dict[str, int]:
        """计算Agent分配"""
        total = len(chapters)
        agent_count = math.ceil(total / chapters_per_agent)
        distribution = {}
        for i, chapter in enumerate(chapters):
            agent_index = i // chapters_per_agent
            distribution[chapter] = agent_index
        return distribution


def create_fix_manager(project_root: str) -> FixManager:
    """创建修复管理器实例"""
    return FixManager(project_root)
