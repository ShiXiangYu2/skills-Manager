#!/usr/bin/env python3
"""
Sumeru Polish Manager - 网文内容润色管理器
负责小说内容的文笔优化、节奏调整、爽点强化、对话优化
支持3级润色等级和6种风格适配
"""
import os
import json
import math
import shutil
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PolishTask:
    """润色任务"""
    task_id: str
    chapter_id: str
    polish_level: str  # light, medium, deep
    style_preset: str  # xiaobuoshuangwen, jingpinwen, gufengxianxia, dushi, xuanyi,kehuan
    focus_areas: List[str]  # rhythm, cool_point, dialogue, prose
    status: str  # pending, in_progress, completed, failed
    original_word_count: int = 0
    polished_word_count: int = 0


@dataclass
class PolishDiff:
    """润色修改记录"""
    chapter_id: str
    diff_type: str  # rhythm, cool_point, dialogue, prose, word_count
    location: str
    original: str
    polished: str
    reason: str
    timestamp: str


class PolishManager:
    """润色管理器"""

    # 润色等级配置
    POLISH_LEVELS = {
        'light': {
            'name': '轻度润色',
            'description': '优化句式表达，去除冗余表述，精炼用词',
            'retain_ratio': 0.8,  # 保留80%原文
        },
        'medium': {
            'name': '中度润色',
            'description': '重构段落结构，优化叙事视角，全面提升文笔质感',
            'retain_ratio': 0.6,  # 保留60%原文
        },
        'deep': {
            'name': '深度润色',
            'description': '逐字打磨，雕琢细节，追求最佳阅读体验',
            'retain_ratio': 0.4,  # 保留40%原文
        }
    }

    # 风格适配配置
    STYLE_PRESETS = {
        'xiaobuoshuangwen': {
            'name': '小白爽文',
            'features': ['短句为主', '节奏明快', '情绪直接', '用词通俗易懂'],
        },
        'jingpinwen': {
            'name': '精品文',
            'features': ['句式多变', '文笔细腻', '注重氛围营造', '人物心理刻画深入'],
        },
        'gufengxianxia': {
            'name': '古风仙侠',
            'features': ['用词雅致', '意境悠远', '适当运用古典词汇', '修辞手法丰富'],
        },
        'dushi': {
            'name': '都市现实',
            'features': ['语言生活化', '对话接地气', '场景描写真实可感'],
        },
        'xuanyi': {
            'name': '悬疑推理',
            'features': ['语言凝练', '节奏紧凑', '信息密度适中', '悬念感强'],
        },
        'kehuan': {
            'name': '科幻未来',
            'features': ['科技感词汇准确', '逻辑严密', '世界观表述清晰'],
        }
    }

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.chapters_dir = os.path.join(project_root, "chapters")
        self.backup_dir = os.path.join(project_root, ".sumeru", "write", "original")
        self.polish_dir = os.path.join(project_root, ".sumeru", "polish")
        self.diff_dir = os.path.join(self.polish_dir, "diff")
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.diff_dir, exist_ok=True)

    def create_polish_task(self, chapter_id: str, polish_level: str = 'light',
                           style_preset: str = 'xiaobuoshuangwen',
                           focus_areas: List[str] = None) -> PolishTask:
        """创建润色任务"""
        if polish_level not in self.POLISH_LEVELS:
            raise ValueError(f"不支持的润色等级: {polish_level}，可选: {list(self.POLISH_LEVELS.keys())}")
        if style_preset not in self.STYLE_PRESETS:
            raise ValueError(f"不支持的风格预设: {style_preset}，可选: {list(self.STYLE_PRESETS.keys())}")

        if focus_areas is None:
            focus_areas = ['rhythm', 'prose']

        task_id = f"polish_{chapter_id}_{polish_level}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        word_count = 0
        if os.path.exists(chapter_path):
            with open(chapter_path, 'r', encoding='utf-8') as f:
                content = f.read()
                word_count = len(content.replace('\n', '').replace(' ', ''))

        return PolishTask(
            task_id=task_id,
            chapter_id=chapter_id,
            polish_level=polish_level,
            style_preset=style_preset,
            focus_areas=focus_areas,
            status='pending',
            original_word_count=word_count
        )

    def create_batch_tasks(self, chapter_ids: List[str], polish_level: str = 'light',
                           style_preset: str = 'xiaobuoshuangwen',
                           focus_areas: List[str] = None,
                           agent_count: int = None) -> Dict[str, List[PolishTask]]:
        """批量创建润色任务，按Agent分配

        Args:
            chapter_ids: 章节ID列表
            polish_level: 润色等级
            style_preset: 风格预设
            focus_areas: 优化重点领域
            agent_count: 指定Agent数量，None则自动计算

        Returns:
            Dict[agent_id, List[PolishTask]]
        """
        if agent_count is None:
            agent_count = math.ceil(len(chapter_ids) / 3)

        tasks = []
        for chapter_id in chapter_ids:
            task = self.create_polish_task(chapter_id, polish_level, style_preset, focus_areas)
            tasks.append(task)

        # 按Agent分配（每个Agent最多3章）
        agent_tasks = {}
        for i, task in enumerate(tasks):
            agent_id = f"agent_{i // 3 + 1}"
            if agent_id not in agent_tasks:
                agent_tasks[agent_id] = []
            agent_tasks[agent_id].append(task)

        return agent_tasks

    def backup_chapter(self, chapter_id: str) -> str:
        """备份章节文件到 .sumeru/write/original/"""
        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        if not os.path.exists(chapter_path):
            raise FileNotFoundError(f"章节文件不存在: {chapter_path}")

        backup_path = os.path.join(self.backup_dir, f"{chapter_id}.md")
        shutil.copy2(chapter_path, backup_path)
        return backup_path

    def save_polished_chapter(self, chapter_id: str, content: str) -> str:
        """保存润色后的章节内容到 chapters/"""
        # 先备份
        self.backup_chapter(chapter_id)

        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        with open(chapter_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return chapter_path

    def save_diff(self, diff: PolishDiff):
        """保存润色修改记录"""
        diff_file = os.path.join(self.diff_dir, f"{diff.chapter_id}.json")

        diffs = []
        if os.path.exists(diff_file):
            with open(diff_file, 'r', encoding='utf-8') as f:
                diffs = json.load(f)

        diffs.append(asdict(diff))

        with open(diff_file, 'w', encoding='utf-8') as f:
            json.dump(diffs, f, ensure_ascii=False, indent=2)

    def save_summary(self, tasks: List[PolishTask], diffs: List[PolishDiff]):
        """保存润色统计报告"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_chapters': len(tasks),
            'completed_chapters': sum(1 for t in tasks if t.status == 'completed'),
            'polish_level': tasks[0].polish_level if tasks else 'unknown',
            'style_preset': tasks[0].style_preset if tasks else 'unknown',
            'total_original_words': sum(t.original_word_count for t in tasks),
            'total_polished_words': sum(t.polished_word_count for t in tasks),
            'diff_stats': {
                'total_diffs': len(diffs),
                'by_type': {}
            },
            'tasks': [asdict(t) for t in tasks]
        }

        # 统计各类型修改数量
        for diff in diffs:
            diff_type = diff.diff_type
            if diff_type not in summary['diff_stats']['by_type']:
                summary['diff_stats']['by_type'][diff_type] = 0
            summary['diff_stats']['by_type'][diff_type] += 1

        summary_path = os.path.join(self.polish_dir, "summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary_path

    def save_style_config(self, polish_level: str, style_preset: str, focus_areas: List[str]):
        """保存本次润色配置"""
        config = {
            'polish_level': polish_level,
            'style_preset': style_preset,
            'focus_areas': focus_areas,
            'timestamp': datetime.now().isoformat()
        }

        config_path = os.path.join(self.polish_dir, "style-config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_chapter_content(self, chapter_id: str) -> str:
        """加载章节内容"""
        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        if not os.path.exists(chapter_path):
            raise FileNotFoundError(f"章节文件不存在: {chapter_path}")

        with open(chapter_path, 'r', encoding='utf-8') as f:
            return f.read()

    def get_chapter_list(self) -> List[str]:
        """获取所有章节ID列表"""
        if not os.path.exists(self.chapters_dir):
            return []

        chapters = []
        for filename in sorted(os.listdir(self.chapters_dir)):
            if filename.endswith('.md'):
                chapter_id = filename[:-3]  # 去掉 .md 后缀
                chapters.append(chapter_id)

        return chapters

    def calculate_agent_count(self, total_chapters: int) -> int:
        """计算所需Agent数量（每个Agent最多3章）"""
        return math.ceil(total_chapters / 3)


def create_polish_manager(project_root: str) -> PolishManager:
    """创建润色管理器实例"""
    return PolishManager(project_root)


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()

    manager = create_polish_manager(project_root)

    # 获取章节列表
    chapters = manager.get_chapter_list()
    print(f"发现 {len(chapters)} 个章节: {chapters}")

    # 创建批量润色任务
    if chapters:
        agent_tasks = manager.create_batch_tasks(chapters, polish_level='light', style_preset='xiaobuoshuangwen')
        for agent_id, tasks in agent_tasks.items():
            print(f"\n{agent_id} 负责 {len(tasks)} 个章节:")
            for task in tasks:
                print(f"  - {task.chapter_id}: {task.original_word_count} 字")
