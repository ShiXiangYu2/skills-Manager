#!/usr/bin/env python3
"""
Finalize Manager 单元测试
"""
import os
import sys
import json
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from finalize_manager import FinalizeManager, ProofreadTask, ProofreadError, create_finalize_manager


class TestFinalizeManager(unittest.TestCase):
    """FinalizeManager 测试类"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.chapters_dir = os.path.join(self.test_dir, "chapters")
        os.makedirs(self.chapters_dir)

        # 创建测试章节文件
        self.test_content = "# 第1章 测试章节\n\n这是测试内容，包含一些文字。\n\n第二段内容。"
        with open(os.path.join(self.chapters_dir, "001.md"), 'w', encoding='utf-8') as f:
            f.write(self.test_content)

        self.manager = create_finalize_manager(self.test_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_dir)

    def test_create_proofread_task(self):
        """测试创建校验任务"""
        task = self.manager.create_proofread_task("001")

        self.assertEqual(task.chapter_id, "001")
        self.assertEqual(task.status, "pending")
        self.assertGreater(task.word_count, 0)

    def test_create_batch_tasks(self):
        """测试批量创建任务"""
        chapter_ids = ["001", "002", "003", "004"]
        agent_tasks = self.manager.create_batch_tasks(chapter_ids)

        # 4章应该分配给2个Agent（3+1）
        self.assertEqual(len(agent_tasks), 2)
        self.assertEqual(len(agent_tasks["agent_1"]), 3)
        self.assertEqual(len(agent_tasks["agent_2"]), 1)

    def test_load_chapter_content(self):
        """测试加载章节内容"""
        content = self.manager.load_chapter_content("001")
        self.assertEqual(content, self.test_content)

    def test_load_chapter_content_not_found(self):
        """测试加载不存在的章节"""
        with self.assertRaises(FileNotFoundError):
            self.manager.load_chapter_content("999")

    def test_proofread_chapter(self):
        """测试校验章节"""
        content = "这是测试内容  多余空格。\n\n中英文混用test标点。"
        errors = self.manager.proofread_chapter("001", content)

        # 应该检测到多余空格
        format_errors = [e for e in errors if e.error_type == 'format']
        self.assertGreater(len(format_errors), 0)

    def test_proofread_chapter_no_errors(self):
        """测试校验无错误章节"""
        content = "这是正常内容。\n\n第二段正常内容。"
        errors = self.manager.proofread_chapter("001", content)

        # 不应该有严重错误
        critical_errors = [e for e in errors if e.severity == 'critical']
        self.assertEqual(len(critical_errors), 0)

    def test_save_error_report(self):
        """测试保存错误报告"""
        errors = [
            ProofreadError("001", "typo", "medium", "第1行", "原文", "建议"),
            ProofreadError("001", "punctuation", "minor", "第2行", "原文", "建议"),
        ]
        stats = {"total_chapters": 1, "total_errors": 2}

        report_path = self.manager.save_error_report(errors, stats)
        self.assertTrue(os.path.exists(report_path))

        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        self.assertEqual(report['summary']['total_errors'], 2)
        self.assertEqual(report['summary']['by_type']['typo'], 1)

    def test_save_stats(self):
        """测试保存统计"""
        chapter_stats = [
            {"chapter_id": "001", "word_count": 1000},
            {"chapter_id": "002", "word_count": 1200},
        ]

        stats_path = self.manager.save_stats(2, 2200, chapter_stats)
        self.assertTrue(os.path.exists(stats_path))

        with open(stats_path, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        self.assertEqual(stats['total_chapters'], 2)
        self.assertEqual(stats['total_words'], 2200)

    def test_format_for_platform_fanqie(self):
        """测试番茄格式化"""
        content = "# 第1章 标题\n\n这是内容。"
        formatted = self.manager.format_for_platform(content, 'fanqie')

        # 番茄不缩进
        self.assertNotIn('　　', formatted)
        self.assertIn('第1章 标题', formatted)

    def test_format_for_platform_qidian(self):
        """测试起点格式化"""
        content = "# 第1章 标题\n\n这是内容。"
        formatted = self.manager.format_for_platform(content, 'qidian')

        # 起点应该有缩进
        self.assertIn('　　', formatted)

    def test_format_for_platform_invalid(self):
        """测试无效平台"""
        with self.assertRaises(ValueError):
            self.manager.format_for_platform("内容", "invalid_platform")

    def test_export_to_platform(self):
        """测试导出到平台"""
        export_path = self.manager.export_to_platform("001", "fanqie")

        self.assertTrue(os.path.exists(export_path))
        self.assertIn("fanqie", export_path)

    def test_get_chapter_list(self):
        """测试获取章节列表"""
        # 创建更多章节
        for i in range(2, 4):
            with open(os.path.join(self.chapters_dir, f"{i:03d}.md"), 'w', encoding='utf-8') as f:
                f.write(f"# 第{i}章\n\n内容")

        chapters = self.manager.get_chapter_list()
        self.assertEqual(len(chapters), 3)
        self.assertIn("001", chapters)

    def test_calculate_agent_count(self):
        """测试计算Agent数量"""
        self.assertEqual(self.manager.calculate_agent_count(1), 1)
        self.assertEqual(self.manager.calculate_agent_count(3), 1)
        self.assertEqual(self.manager.calculate_agent_count(4), 2)

    def test_get_platform_info(self):
        """测试获取平台信息"""
        platforms = self.manager.get_platform_info()
        self.assertIn('qidian', platforms)
        self.assertIn('fanqie', platforms)

        qidian = self.manager.get_platform_info('qidian')
        self.assertEqual(qidian['name'], '起点中文网')


class TestFinalizeConstants(unittest.TestCase):
    """测试常量配置"""

    def test_platform_configs(self):
        """测试平台配置"""
        from finalize_manager import FinalizeManager

        expected_platforms = ['qidian', 'fanqie', 'jjwxc', 'zongheng', '17k']
        for platform in expected_platforms:
            self.assertIn(platform, FinalizeManager.PLATFORM_CONFIGS)
            config = FinalizeManager.PLATFORM_CONFIGS[platform]
            self.assertIn('name', config)
            self.assertIn('title_format', config)

    def test_sensitive_levels(self):
        """测试敏感词等级"""
        from finalize_manager import FinalizeManager

        self.assertIn('level1', FinalizeManager.SENSITIVE_LEVELS)
        self.assertIn('level2', FinalizeManager.SENSITIVE_LEVELS)
        self.assertIn('level3', FinalizeManager.SENSITIVE_LEVELS)

    def test_error_severity(self):
        """测试错误分级"""
        from finalize_manager import FinalizeManager

        self.assertIn('critical', FinalizeManager.ERROR_SEVERITY)
        self.assertIn('medium', FinalizeManager.ERROR_SEVERITY)
        self.assertIn('minor', FinalizeManager.ERROR_SEVERITY)


if __name__ == '__main__':
    unittest.main()
