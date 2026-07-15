#!/usr/bin/env python3
"""
Sumeru Finalize Manager - 网文完稿校验与导出管理器
负责全技术性文字校验（错别字、标点、语法）与合规检查
支持多平台格式导出和Obsidian导出
"""
import os
import json
import math
import re
import shutil
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ProofreadTask:
    """校验任务"""
    task_id: str
    chapter_id: str
    status: str  # pending, in_progress, completed, failed
    errors_found: int = 0
    word_count: int = 0


@dataclass
class ProofreadError:
    """校验错误"""
    chapter_id: str
    error_type: str  # typo, punctuation, grammar, sensitive, format
    severity: str  # critical, medium, minor
    location: str
    original: str
    suggestion: str
    line_number: int = 0


@dataclass
class ExportConfig:
    """导出配置"""
    platform: str
    title_format: str
    indent: bool
    paragraph_spacing: bool
    word_count_per_chapter: str
    special_rules: List[str]


class FinalizeManager:
    """完稿校验与导出管理器"""

    # 平台导出配置
    PLATFORM_CONFIGS = {
        'qidian': {
            'name': '起点中文网',
            'title_format': '第X章 标题内容',
            'title_centered': True,
            'indent': True,
            'indent_chars': 2,
            'paragraph_spacing': True,
            'word_count_per_chapter': '3000-5000字',
            'special_rules': [
                '禁止使用特殊符号作为章节标题',
                '对话单独成段',
                '标点符号使用中文全角',
            ]
        },
        'fanqie': {
            'name': '番茄小说',
            'title_format': '第X章 标题内容',
            'title_centered': False,
            'indent': False,
            'paragraph_spacing': True,
            'word_count_per_chapter': '2000-3000字',
            'special_rules': [
                '每句尽量简短，适合移动端阅读',
                '重点内容可使用加粗标记',
                '对话使用引号包裹',
            ]
        },
        'jjwxc': {
            'name': '晋江文学城',
            'title_format': '第X章 标题内容',
            'title_centered': False,
            'indent': True,
            'indent_chars': 2,
            'paragraph_spacing': True,
            'word_count_per_chapter': '2500-4000字',
            'special_rules': [
                '支持HTML格式标签',
                '作者有话要说区域单独设置',
                '支持章节提要',
            ]
        },
        'zongheng': {
            'name': '纵横中文网',
            'title_format': '第X章 标题内容',
            'title_centered': False,
            'indent': True,
            'indent_chars': 2,
            'paragraph_spacing': True,
            'word_count_per_chapter': '3000-6000字',
            'special_rules': [
                '支持分卷设置',
                '标点规范使用中文全角',
            ]
        },
        '17k': {
            'name': '17K小说网',
            'title_format': '第X章 标题内容',
            'title_centered': False,
            'indent': True,
            'indent_chars': 2,
            'paragraph_spacing': True,
            'word_count_per_chapter': '2000-4000字',
            'special_rules': [
                '支持章节预览',
                '每章结束可设置下章预告',
            ]
        }
    }

    # 敏感词检测标准
    SENSITIVE_LEVELS = {
        'level1': {
            'name': '一级敏感（必须修改）',
            'keywords': [
                # 这里应该添加实际的敏感词库
                # 示例：政治敏感、色情、暴力等内容的关键词
            ],
            'action': '必须修改'
        },
        'level2': {
            'name': '二级敏感（建议修改）',
            'keywords': [
                # 示例：低俗用语、过度暴力等
            ],
            'action': '建议修改'
        },
        'level3': {
            'name': '三级敏感（优化建议）',
            'keywords': [
                # 示例：网络用语过多、重复表述等
            ],
            'action': '优化建议'
        }
    }

    # 错误分级
    ERROR_SEVERITY = {
        'critical': {
            'name': '严重错误',
            'color': 'red',
            'description': '错别字导致语义完全改变、敏感词一级违规、格式严重混乱'
        },
        'medium': {
            'name': '中等错误',
            'color': 'yellow',
            'description': '一般错别字、标点不规范、敏感词二级内容'
        },
        'minor': {
            'name': '轻微错误',
            'color': 'blue',
            'description': '建议优化的用词、标点可更规范、敏感词三级内容'
        }
    }

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.chapters_dir = os.path.join(project_root, "chapters")
        self.finalize_dir = os.path.join(project_root, ".sumeru", "finalize")
        self.clean_dir = os.path.join(self.finalize_dir, "clean")
        self.clean_chapters_dir = os.path.join(self.clean_dir, "chapters")
        self.publish_dir = os.path.join(project_root, "publish")
        os.makedirs(self.clean_chapters_dir, exist_ok=True)
        os.makedirs(self.publish_dir, exist_ok=True)

    def create_proofread_task(self, chapter_id: str) -> ProofreadTask:
        """创建校验任务"""
        task_id = f"proofread_{chapter_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        word_count = 0
        if os.path.exists(chapter_path):
            with open(chapter_path, 'r', encoding='utf-8') as f:
                content = f.read()
                word_count = len(content.replace('\n', '').replace(' ', ''))

        return ProofreadTask(
            task_id=task_id,
            chapter_id=chapter_id,
            status='pending',
            word_count=word_count
        )

    def create_batch_tasks(self, chapter_ids: List[str], agent_count: int = None) -> Dict[str, List[ProofreadTask]]:
        """批量创建校验任务，按Agent分配"""
        if agent_count is None:
            agent_count = math.ceil(len(chapter_ids) / 3)

        tasks = []
        for chapter_id in chapter_ids:
            task = self.create_proofread_task(chapter_id)
            tasks.append(task)

        # 按Agent分配（每个Agent最多3章）
        agent_tasks = {}
        for i, task in enumerate(tasks):
            agent_id = f"agent_{i // 3 + 1}"
            if agent_id not in agent_tasks:
                agent_tasks[agent_id] = []
            agent_tasks[agent_id].append(task)

        return agent_tasks

    def load_chapter_content(self, chapter_id: str) -> str:
        """加载章节内容"""
        chapter_path = os.path.join(self.chapters_dir, f"{chapter_id}.md")
        if not os.path.exists(chapter_path):
            raise FileNotFoundError(f"章节文件不存在: {chapter_path}")

        with open(chapter_path, 'r', encoding='utf-8') as f:
            return f.read()

    def proofread_chapter(self, chapter_id: str, content: str) -> List[ProofreadError]:
        """校验单个章节"""
        errors = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            # 基础校验规则
            # 1. 检查多余空格
            if '  ' in line:
                errors.append(ProofreadError(
                    chapter_id=chapter_id,
                    error_type='format',
                    severity='minor',
                    location=f"第{line_num}行",
                    original=line[:50] + '...' if len(line) > 50 else line,
                    suggestion='存在多余空格',
                    line_number=line_num
                ))

            # 2. 检查中英文标点混用（示例）
            if re.search(r'[a-zA-Z][，。！？；：]', line) or re.search(r'[，。！？；：][a-zA-Z]', line):
                errors.append(ProofreadError(
                    chapter_id=chapter_id,
                    error_type='punctuation',
                    severity='medium',
                    location=f"第{line_num}行",
                    original=line[:50] + '...' if len(line) > 50 else line,
                    suggestion='中英文标点混用',
                    line_number=line_num
                ))

            # 3. 检查连续标点
            if re.search(r'[。，！？；：]{2,}', line):
                errors.append(ProofreadError(
                    chapter_id=chapter_id,
                    error_type='punctuation',
                    severity='medium',
                    location=f"第{line_num}行",
                    original=line[:50] + '...' if len(line) > 50 else line,
                    suggestion='存在连续标点',
                    line_number=line_num
                ))

        return errors

    def save_error_report(self, errors: List[ProofreadError], stats: Dict):
        """保存错误报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'errors': [asdict(e) for e in errors],
            'summary': {
                'total_errors': len(errors),
                'by_type': {},
                'by_severity': {}
            }
        }

        # 统计各类型错误数量
        for error in errors:
            # 按类型统计
            if error.error_type not in report['summary']['by_type']:
                report['summary']['by_type'][error.error_type] = 0
            report['summary']['by_type'][error.error_type] += 1

            # 按严重程度统计
            if error.severity not in report['summary']['by_severity']:
                report['summary']['by_severity'][error.severity] = 0
            report['summary']['by_severity'][error.severity] += 1

        report_path = os.path.join(self.finalize_dir, "error-report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report_path

    def save_stats(self, total_chapters: int, total_words: int, chapter_stats: List[Dict]):
        """保存完稿统计"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'total_chapters': total_chapters,
            'total_words': total_words,
            'avg_words_per_chapter': total_words // total_chapters if total_chapters > 0 else 0,
            'chapters': chapter_stats
        }

        stats_path = os.path.join(self.finalize_dir, "stats.json")
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        return stats_path

    def format_for_platform(self, content: str, platform: str) -> str:
        """按平台格式化内容"""
        config = self.PLATFORM_CONFIGS.get(platform)
        if not config:
            raise ValueError(f"不支持的平台: {platform}，可选: {list(self.PLATFORM_CONFIGS.keys())}")

        formatted_lines = []
        lines = content.split('\n')

        for line in lines:
            # 处理章节标题
            if line.startswith('# ') or line.startswith('## '):
                title = line.lstrip('#').strip()
                if config.get('title_centered'):
                    formatted_lines.append(f"<center>{title}</center>")
                else:
                    formatted_lines.append(title)
                formatted_lines.append('')  # 标题后空一行
                continue

            # 处理段落
            if line.strip():
                if config.get('indent'):
                    # 首行缩进
                    indent = '　　' * config.get('indent_chars', 2)
                    formatted_lines.append(f"{indent}{line}")
                else:
                    formatted_lines.append(line)

                # 段落间空行
                if config.get('paragraph_spacing'):
                    formatted_lines.append('')

        return '\n'.join(formatted_lines)

    def export_to_platform(self, chapter_id: str, platform: str) -> str:
        """导出单个章节到指定平台格式"""
        content = self.load_chapter_content(chapter_id)
        formatted = self.format_for_platform(content, platform)

        # 创建平台导出目录
        platform_dir = os.path.join(self.publish_dir, platform)
        os.makedirs(platform_dir, exist_ok=True)

        # 保存文件
        export_path = os.path.join(platform_dir, f"{chapter_id}.md")
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(formatted)

        return export_path

    def export_all_chapters(self, chapter_ids: List[str], platforms: List[str]) -> Dict[str, List[str]]:
        """批量导出所有章节到多个平台"""
        results = {}

        for platform in platforms:
            results[platform] = []
            for chapter_id in chapter_ids:
                try:
                    path = self.export_to_platform(chapter_id, platform)
                    results[platform].append(path)
                except Exception as e:
                    print(f"导出失败: {chapter_id} -> {platform}: {e}")

        return results

    def generate_full_text(self, chapter_ids: List[str]) -> str:
        """生成纯净版全文"""
        full_text = []

        for chapter_id in chapter_ids:
            content = self.load_chapter_content(chapter_id)
            full_text.append(content)
            full_text.append('\n\n')  # 章节间空两行

        return '\n'.join(full_text)

    def save_clean_text(self, full_text: str, chapter_ids: List[str]):
        """保存纯净版全文"""
        # 保存完整全文
        full_text_path = os.path.join(self.clean_dir, "full-text.md")
        with open(full_text_path, 'w', encoding='utf-8') as f:
            f.write(full_text)

        # 按章节拆分保存
        for chapter_id in chapter_ids:
            content = self.load_chapter_content(chapter_id)
            chapter_path = os.path.join(self.clean_chapters_dir, f"{chapter_id}.md")
            with open(chapter_path, 'w', encoding='utf-8') as f:
                f.write(content)

    def save_export_config(self, platforms: List[str]):
        """保存导出配置"""
        config = {
            'platforms': platforms,
            'timestamp': datetime.now().isoformat(),
            'platform_configs': {p: self.PLATFORM_CONFIGS.get(p, {}) for p in platforms}
        }

        config_path = os.path.join(self.finalize_dir, "export-config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_chapter_list(self) -> List[str]:
        """获取所有章节ID列表"""
        if not os.path.exists(self.chapters_dir):
            return []

        chapters = []
        for filename in sorted(os.listdir(self.chapters_dir)):
            if filename.endswith('.md'):
                chapter_id = filename[:-3]
                chapters.append(chapter_id)

        return chapters

    def calculate_agent_count(self, total_chapters: int) -> int:
        """计算所需Agent数量（每个Agent最多3章）"""
        return math.ceil(total_chapters / 3)

    def get_platform_info(self, platform: str = None) -> Dict:
        """获取平台信息"""
        if platform:
            return self.PLATFORM_CONFIGS.get(platform, {})
        return self.PLATFORM_CONFIGS


def create_finalize_manager(project_root: str) -> FinalizeManager:
    """创建完稿校验管理器实例"""
    return FinalizeManager(project_root)


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()

    manager = create_finalize_manager(project_root)

    # 获取章节列表
    chapters = manager.get_chapter_list()
    print(f"发现 {len(chapters)} 个章节: {chapters}")

    # 示例：导出到番茄格式
    if chapters:
        print("\n导出到番茄小说格式...")
        results = manager.export_all_chapters(chapters[:3], ['fanqie'])
        for platform, paths in results.items():
            print(f"\n{platform}:")
            for path in paths:
                print(f"  - {path}")
