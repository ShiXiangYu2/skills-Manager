#!/usr/bin/env python3
"""
Polish Manager 单元测试
"""
import os
import sys
import json
import tempfile
import shutil
import unittest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from polish_manager import PolishManager, PolishTask, PolishDiff, create_polish_manager


class TestPolishManager(unittest.TestCase):
    """PolishManager 测试类"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.chapters_dir = os.path.join(self.test_dir, "chapters")
        os.makedirs(self.chapters_dir)

        # 创建测试章节文件
        self.test_chapter_content = "# 第1章 测试章节\n\n这是测试内容，包含一些需要润色的文字。"
        with open(os.path.join(self.chapters_dir, "001.md"), 'w', encoding='utf-8') as f:
            f.write(self.test_chapter_content)

        self.manager = create_polish_manager(self.test_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_dir)

    def test_create_polish_task(self):
        """测试创建润色任务"""
        task = self.manager.create_polish_task("001", polish_level='light', style_preset='xiaobuoshuangwen')

        self.assertEqual(task.chapter_id, "001")
        self.assertEqual(task.polish_level, "light")
        self.assertEqual(task.style_preset, "xiaobuoshuangwen")
        self.assertEqual(task.status, "pending")
        self.assertGreater(task.original_word_count, 0)

    def test_create_polish_task_invalid_level(self):
        """测试无效润色等级"""
        with self.assertRaises(ValueError):
            self.manager.create_polish_task("001", polish_level='invalid')

    def test_create_polish_task_invalid_style(self):
        """测试无效风格预设"""
        with self.assertRaises(ValueError):
            self.manager.create_polish_task("001", style_preset='invalid')

    def test_create_batch_tasks(self):
        """测试批量创建任务"""
        chapter_ids = ["001", "002", "003", "004", "005"]
        agent_tasks = self.manager.create_batch_tasks(chapter_ids, polish_level='medium')

        # 5章应该分配给2个Agent（3+2）
        self.assertEqual(len(agent_tasks), 2)
        self.assertEqual(len(agent_tasks["agent_1"]), 3)
        self.assertEqual(len(agent_tasks["agent_2"]), 2)

    def test_backup_chapter(self):
        """测试章节备份"""
        backup_path = self.manager.backup_chapter("001")

        self.assertTrue(os.path.exists(backup_path))
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, self.test_chapter_content)

    def test_backup_chapter_not_found(self):
        """测试备份不存在的章节"""
        with self.assertRaises(FileNotFoundError):
            self.manager.backup_chapter("999")

    def test_save_polished_chapter(self):
        """测试保存润色后的章节"""
        new_content = "# 第1章 测试章节\n\n这是润色后的内容。"
        save_path = self.manager.save_polished_chapter("001", new_content)

        # 验证文件已保存
        self.assertTrue(os.path.exists(save_path))
        with open(save_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, new_content)

        # 验证备份已创建
        backup_path = os.path.join(self.manager.backup_dir, "001.md")
        self.assertTrue(os.path.exists(backup_path))

    def test_save_diff(self):
        """测试保存修改记录"""
        diff = PolishDiff(
            chapter_id="001",
            diff_type="rhythm",
            location="第1段",
            original="原文",
            polished="润色后",
            reason="优化节奏",
            timestamp="2026-01-01T00:00:00"
        )
        self.manager.save_diff(diff)

        diff_file = os.path.join(self.manager.diff_dir, "001.json")
        self.assertTrue(os.path.exists(diff_file))

        with open(diff_file, 'r', encoding='utf-8') as f:
            diffs = json.load(f)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]['diff_type'], 'rhythm')

    def test_save_summary(self):
        """测试保存统计报告"""
        tasks = [
            PolishTask("task1", "001", "light", "xiaobuoshuangwen", ["rhythm"], "completed", 1000, 950),
            PolishTask("task2", "002", "light", "xiaobuoshuangwen", ["rhythm"], "completed", 1200, 1100),
        ]
        diffs = [
            PolishDiff("001", "rhythm", "第1段", "原文", "润色", "优化", "2026-01-01T00:00:00"),
        ]

        summary_path = self.manager.save_summary(tasks, diffs)
        self.assertTrue(os.path.exists(summary_path))

        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        self.assertEqual(summary['total_chapters'], 2)
        self.assertEqual(summary['completed_chapters'], 2)

    def test_get_chapter_list(self):
        """测试获取章节列表"""
        # 创建更多章节文件
        for i in range(2, 4):
            with open(os.path.join(self.chapters_dir, f"{i:03d}.md"), 'w', encoding='utf-8') as f:
                f.write(f"# 第{i}章\n\n内容")

        chapters = self.manager.get_chapter_list()
        self.assertEqual(len(chapters), 3)
        self.assertIn("001", chapters)
        self.assertIn("002", chapters)
        self.assertIn("003", chapters)

    def test_calculate_agent_count(self):
        """测试计算Agent数量"""
        self.assertEqual(self.manager.calculate_agent_count(1), 1)
        self.assertEqual(self.manager.calculate_agent_count(3), 1)
        self.assertEqual(self.manager.calculate_agent_count(4), 2)
        self.assertEqual(self.manager.calculate_agent_count(6), 2)
        self.assertEqual(self.manager.calculate_agent_count(7), 3)


class TestPolishConstants(unittest.TestCase):
    """测试常量配置"""

    def test_polish_levels(self):
        """测试润色等级配置"""
        from polish_manager import PolishManager

        self.assertIn('light', PolishManager.POLISH_LEVELS)
        self.assertIn('medium', PolishManager.POLISH_LEVELS)
        self.assertIn('deep', PolishManager.POLISH_LEVELS)

        self.assertEqual(PolishManager.POLISH_LEVELS['light']['retain_ratio'], 0.8)
        self.assertEqual(PolishManager.POLISH_LEVELS['medium']['retain_ratio'], 0.6)
        self.assertEqual(PolishManager.POLISH_LEVELS['deep']['retain_ratio'], 0.4)

    def test_style_presets(self):
        """测试风格预设配置"""
        from polish_manager import PolishManager

        expected_styles = ['xiaobuoshuangwen', 'jingpinwen', 'gufengxianxia', 'dushi', 'xuanyi', 'kehuan']
        for style in expected_styles:
            self.assertIn(style, PolishManager.STYLE_PRESETS)
            self.assertIn('name', PolishManager.STYLE_PRESETS[style])
            self.assertIn('features', PolishManager.STYLE_PRESETS[style])


if __name__ == '__main__':
    unittest.main()
