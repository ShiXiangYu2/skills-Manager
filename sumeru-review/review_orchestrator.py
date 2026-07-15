#!/usr/bin/env python3
"""
Sumeru Review Orchestrator - 网文逻辑审查修复编排器
协调 sumeru-audit 和 sumeru-fix 完成完整的审查修复流程
"""
import os
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# 导入子技能的管理器
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sumeru-audit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sumeru-fix'))

from audit_manager import AuditManager, create_audit_manager, GlobalIssue, BottomLineItem, ChapterIssue
from fix_manager import FixManager, create_fix_manager, FixTask, OutlineRevision, BottomLineFix


class ReviewOrchestrator:
    """审查修复编排器"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.audit_manager = create_audit_manager(project_root)
        self.fix_manager = create_fix_manager(project_root)
        self.review_dir = os.path.join(project_root, ".sumeru", "review")
        os.makedirs(self.review_dir, exist_ok=True)

    def run_full_review(self) -> Dict:
        """执行完整的三阶段审查修复流程"""
        print("=" * 60)
        print("开始执行完整审查修复流程")
        print("=" * 60)

        # 第一阶段：全局审查
        print("\n[第一阶段] 执行全局审查...")
        global_issues, bottom_line = self._run_global_audit()
        print(f"  - 发现 {len(global_issues)} 个全局问题")
        print(f"  - 发现 {len(bottom_line)} 个底线问题")

        # 第二阶段：章节细节审查
        print("\n[第二阶段] 执行章节细节审查...")
        chapter_issues = self._run_chapter_audit()
        print(f"  - 审查完成，共 {len(chapter_issues)} 章")

        # 合并问题清单
        print("\n合并问题清单...")
        all_issues = self._merge_issues(global_issues, chapter_issues, bottom_line)
        self._save_merged_issues(all_issues)

        # 第三阶段：统一修复
        print("\n[第三阶段] 执行统一修复...")
        fix_results = self._run_fix(all_issues, bottom_line)
        print(f"  - 完成 {fix_results['fixed_count']} 项修复")
        print(f"  - 剩余 {fix_results['pending_count']} 项待处理")

        # 生成最终报告
        print("\n生成审查修复报告...")
        final_report = self._generate_final_report(global_issues, chapter_issues, bottom_line, fix_results)

        print("\n" + "=" * 60)
        print("审查修复流程完成!")
        print("=" * 60)

        return final_report

    def run_audit_only(self) -> Dict:
        """仅执行审查（不修复）"""
        print("=" * 60)
        print("执行审查（不修复）")
        print("=" * 60)

        # 第一阶段：全局审查
        print("\n[第一阶段] 执行全局审查...")
        global_issues, bottom_line = self._run_global_audit()
        print(f"  - 发现 {len(global_issues)} 个全局问题")
        print(f"  - 发现 {len(bottom_line)} 个底线问题")

        # 第二阶段：章节细节审查
        print("\n[第二阶段] 执行章节细节审查...")
        chapter_issues = self._run_chapter_audit()
        print(f"  - 审查完成，共 {len(chapter_issues)} 章")

        # 保存审查结果
        self.audit_manager.save_global_issues(global_issues, bottom_line)

        return {
            'global_issues': global_issues,
            'chapter_issues': chapter_issues,
            'bottom_line': bottom_line
        }

    def run_fix_only(self) -> Dict:
        """仅执行修复（基于已有审查结果）"""
        print("=" * 60)
        print("执行修复（基于已有审查结果）")
        print("=" * 60)

        # 加载审查结果
        audit_results = self.fix_manager.load_audit_results()
        if not audit_results.get('global_issues') and not audit_results.get('chapter_issues'):
            print("未找到审查结果，请先执行审查")
            return {}

        # 创建修复任务
        fix_tasks = self.fix_manager.create_fix_tasks(audit_results)
        print(f"  - 创建 {len(fix_tasks)} 个修复任务")

        # 执行修复
        bottom_line = audit_results.get('bottom_line', {}).get('items', [])
        bottom_line_items = [BottomLineItem(**item) for item in bottom_line] if bottom_line else []
        fix_results = self._execute_fixes(fix_tasks, bottom_line_items)
        print(f"  - 完成 {fix_results['fixed_count']} 项修复")
        print(f"  - 剩余 {fix_results['pending_count']} 项待处理")

        return fix_results

    def _run_global_audit(self) -> Tuple[List[GlobalIssue], List[BottomLineItem]]:
        """执行全局审查"""
        chapters = self.audit_manager.load_chapter_files()
        outlines = self.audit_manager.load_outlines()

        # 这里应该调用实际的审查逻辑
        # 目前返回示例数据，实际实现需要根据具体需求编写
        global_issues = []
        bottom_line = []

        return global_issues, bottom_line

    def _run_chapter_audit(self) -> Dict[str, List[ChapterIssue]]:
        """执行章节细节审查"""
        chapters = self.audit_manager.load_chapter_files()
        agent_count = self.audit_manager.calculate_agent_distribution(len(chapters))
        print(f"  - 需要 {agent_count} 个 Agent 并行处理")

        # 这里应该调用实际的审查逻辑
        # 目前返回示例数据，实际实现需要根据具体需求编写
        chapter_issues = {}

        return chapter_issues

    def _merge_issues(self, global_issues: List[GlobalIssue],
                      chapter_issues: Dict[str, List[ChapterIssue]],
                      bottom_line: List[BottomLineItem]) -> Dict:
        """合并所有问题"""
        all_issues = {
            'global': [asdict(i) for i in global_issues],
            'chapters': {k: [asdict(i) for i in v] for k, v in chapter_issues.items()},
            'bottom_line': [asdict(b) for b in bottom_line],
            'total_count': len(global_issues) + sum(len(v) for v in chapter_issues.values()) + len(bottom_line)
        }
        return all_issues

    def _save_merged_issues(self, all_issues: Dict):
        """保存合并后的问题清单"""
        path = os.path.join(self.review_dir, "merged-issues.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(all_issues, f, ensure_ascii=False, indent=2)

    def _run_fix(self, all_issues: Dict, bottom_line: List[BottomLineItem]) -> Dict:
        """执行修复"""
        # 创建修复任务
        fix_tasks = []
        for issue in all_issues.get('global', []):
            task = FixTask(
                task_id=f"global_{issue['issue_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                task_type='light_fix',
                severity=issue['severity'],
                description=issue['description'],
                affected_chapters=issue.get('affected_chapters', []),
                status='pending'
            )
            fix_tasks.append(task)

        for chapter_id, issues in all_issues.get('chapters', {}).items():
            for issue in issues:
                task = FixTask(
                    task_id=f"chapter_{chapter_id}_{issue['issue_type']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    task_type='light_fix',
                    severity=issue['severity'],
                    description=f"Chapter {chapter_id}: {issue['description']}",
                    affected_chapters=[chapter_id],
                    status='pending'
                )
                fix_tasks.append(task)

        for item in bottom_line:
            if item.status == 'pending':
                task = FixTask(
                    task_id=f"bottom_line_{item.category}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    task_type='bottom_line_fix',
                    severity=item.severity,
                    description=item.description,
                    affected_chapters=item.affected_chapters,
                    status='pending'
                )
                fix_tasks.append(task)

        # 按严重程度排序
        severity_order = {'fatal': 0, 'serious': 1, 'medium': 2, 'minor': 3}
        fix_tasks.sort(key=lambda x: severity_order.get(x.severity, 4))

        # 保存修复计划
        self.fix_manager.save_fix_plan(fix_tasks)

        # 执行修复
        return self._execute_fixes(fix_tasks, bottom_line)

    def _execute_fixes(self, fix_tasks: List[FixTask], bottom_line: List[BottomLineItem]) -> Dict:
        """执行修复任务"""
        fixed_count = 0
        pending_count = 0
        fixed_issues = []

        for task in fix_tasks:
            print(f"  处理: {task.description}")
            # 这里应该调用实际的修复逻辑
            # 目前标记为待处理，实际实现需要根据具体需求编写
            task.status = 'pending'
            pending_count += 1

        # 保存修复记录
        self.fix_manager.save_fixed_issues(fixed_issues)

        # 处理底线问题
        bottom_line_fixes = self._process_bottom_line(bottom_line)

        return {
            'fixed_count': fixed_count,
            'pending_count': pending_count,
            'fixed_issues': fixed_issues,
            'bottom_line_fixes': bottom_line_fixes
        }

    def _process_bottom_line(self, bottom_line: List[BottomLineItem]) -> List[BottomLineFix]:
        """处理底线问题"""
        fixes = []
        for item in bottom_line:
            if item.status == 'pending':
                fix = BottomLineFix(
                    category=item.category,
                    description=item.description,
                    status='manual_required',
                    solution='需要人工干预',
                    manual_suggestion=item.suggestion
                )
                fixes.append(fix)

        # 保存底线问题修复记录
        if fixes:
            self.fix_manager.save_bottom_line_fixes(fixes)

        return fixes

    def _generate_final_report(self, global_issues: List[GlobalIssue],
                               chapter_issues: Dict[str, List[ChapterIssue]],
                               bottom_line: List[BottomLineItem],
                               fix_results: Dict) -> Dict:
        """生成最终报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_global_issues': len(global_issues),
                'total_chapters': len(chapter_issues),
                'total_bottom_line': len(bottom_line),
                'fixed_count': fix_results.get('fixed_count', 0),
                'pending_count': fix_results.get('pending_count', 0)
            },
            'global_issues': [asdict(i) for i in global_issues],
            'chapter_issues': {k: [asdict(i) for i in v] for k, v in chapter_issues.items()},
            'bottom_line': [asdict(b) for b in bottom_line],
            'fix_results': fix_results
        }

        # 保存报告
        report_path = os.path.join(self.review_dir, "final-report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 保存修复报告
        self.fix_manager.save_fix_report({
            'global_issues': [asdict(i) for i in global_issues],
            'chapter_issues': {k: [asdict(i) for i in v] for k, v in chapter_issues.items()},
            'fix_results': fix_results
        })

        return report


def create_review_orchestrator(project_root: str) -> ReviewOrchestrator:
    """创建审查编排器实例"""
    return ReviewOrchestrator(project_root)


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()

    orchestrator = create_review_orchestrator(project_root)
    orchestrator.run_full_review()
