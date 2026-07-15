#!/usr/bin/env python3
"""
Topic Manager 单元测试
"""
import os
import sys
import json
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from topic_manager import TopicManager, TopicOption, BookAnalysis, create_topic_manager


class TestTopicManager(unittest.TestCase):
    """TopicManager 测试类"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.manager = create_topic_manager(self.test_dir)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_dir)

    def test_create_topic_option(self):
        """测试创建选题方案"""
        option_data = {
            'id': 1,
            'title': '测试小说',
            'core_concept': '测试概念',
            'golden_finger': {'name': '测试系统'},
            'core_selling_points': ['卖点1', '卖点2'],
            'audience': '测试受众',
            'cool_point_pattern': {'type': '打脸'},
            'opening_suggestion': '开篇建议',
            'scores': {'market_heat': 8},
            'risks': ['风险1'],
            'differentiation_strategy': '差异化策略'
        }

        option = self.manager.create_topic_option(option_data)

        self.assertEqual(option.id, 1)
        self.assertEqual(option.title, '测试小说')
        self.assertEqual(option.core_concept, '测试概念')
        self.assertEqual(option.core_selling_points, ['卖点1', '卖点2'])

    def test_create_book_analysis(self):
        """测试创建拆书笔记"""
        book_data = {
            'book_name': '《测试书》',
            'author': '测试作者',
            'platform': '番茄小说',
            'genre': '都市脑洞',
            'tags': ['系统流', '打脸'],
            'target_audience': '男频18-30岁',
            'one_line_selling_point': '一句话卖点',
            'opening_analysis': {'first_chapter_hook': '钩子'},
            'cool_point_pattern': {'type': '打脸', 'rhythm': '节奏'},
            'character_template': {'type': '废柴逆袭'},
            'hook_template': {'type': '危机'},
            'transferable_writing': ['可迁移写法1'],
            'non_transferable': ['不可迁移1'],
            'inspiration': {'启发': '内容'}
        }

        analysis = self.manager.create_book_analysis(book_data)

        self.assertEqual(analysis.book_name, '《测试书》')
        self.assertEqual(analysis.platform, '番茄小说')
        self.assertEqual(analysis.genre, '都市脑洞')
        self.assertIn('系统流', analysis.tags)

    def test_save_and_load_book_analysis(self):
        """测试保存和加载拆书笔记"""
        book_data = {
            'book_name': '《测试书》',
            'author': '测试作者',
            'platform': '番茄小说',
            'genre': '都市',
            'tags': ['测试'],
            'target_audience': '测试',
            'one_line_selling_point': '测试',
            'opening_analysis': {},
            'cool_point_pattern': {},
            'character_template': {},
            'hook_template': {},
            'transferable_writing': [],
            'non_transferable': [],
            'inspiration': {}
        }

        analysis = self.manager.create_book_analysis(book_data)
        self.manager.save_book_analysis(analysis)

        # 加载并验证
        analyses = self.manager.load_book_analyses()
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0].book_name, '《测试书》')

    def test_generate_structures_library(self):
        """测试生成可迁移结构库"""
        analyses = [
            BookAnalysis(
                book_name='书1', author='作者1', platform='番茄', genre='都市',
                tags=[], target_audience='', one_line_selling_point='',
                opening_analysis={'hook': '测试钩子'},
                cool_point_pattern={'type': '打脸'},
                character_template={'type': '主角'},
                hook_template={'type': '危机'},
                transferable_writing=[], non_transferable=[], inspiration={}
            ),
            BookAnalysis(
                book_name='书2', author='作者2', platform='起点', genre='玄幻',
                tags=[], target_audience='', one_line_selling_point='',
                opening_analysis={'hook': '另一钩子'},
                cool_point_pattern={'type': '升级'},
                character_template={'type': '主角'},
                hook_template={'type': '反转'},
                transferable_writing=[], non_transferable=[], inspiration={}
            )
        ]

        structures = self.manager.generate_structures_library(analyses)

        self.assertEqual(len(structures['opening']), 2)
        self.assertEqual(len(structures['cool_point']), 2)
        self.assertEqual(len(structures['character']), 2)
        self.assertEqual(len(structures['hook']), 2)

    def test_generate_cool_points_library(self):
        """测试生成爽点模式库"""
        analyses = [
            BookAnalysis(
                book_name='书1', author='作者1', platform='番茄', genre='都市',
                tags=[], target_audience='', one_line_selling_point='',
                opening_analysis={}, cool_point_pattern={'type': '打脸', 'rhythm': '每2章'},
                character_template={}, hook_template={},
                transferable_writing=[], non_transferable=[], inspiration={}
            )
        ]

        cool_points = self.manager.generate_cool_points_library(analyses)
        self.assertEqual(len(cool_points), 1)
        self.assertEqual(cool_points[0]['type'], '打脸')

    def test_evaluate_option(self):
        """测试选题评估"""
        option = TopicOption(
            id=1, title='测试', core_concept='测试',
            golden_finger={}, core_selling_points=[], audience='',
            cool_point_pattern={}, opening_suggestion='',
            scores={'market_heat': 8, 'competition': 6, 'audience_size': 9,
                    'creation_difficulty': 5, 'monetization_potential': 8,
                    'platform_fit': 8},
            risks=[], differentiation_strategy=''
        )

        evaluation = self.manager.evaluate_option(option)

        self.assertEqual(evaluation['option_id'], 1)
        self.assertGreater(evaluation['overall_score'], 0)
        self.assertIn(evaluation['recommendation'], ['强烈推荐', '可以尝试', '建议优化'])

    def test_save_and_load_options(self):
        """测试保存和加载选题方案"""
        option = TopicOption(
            id=1, title='测试', core_concept='测试',
            golden_finger={}, core_selling_points=[], audience='',
            cool_point_pattern={}, opening_suggestion='',
            scores={}, risks=[], differentiation_strategy=''
        )

        self.manager.save_options([option])
        loaded = self.manager.load_options()

        self.assertIn('options', loaded)
        self.assertEqual(len(loaded['options']), 1)
        self.assertEqual(loaded['options'][0]['title'], '测试')

    def test_get_platform_comparison(self):
        """测试获取平台对比"""
        platforms = self.manager.get_platform_comparison()
        self.assertIn('qidian', platforms)
        self.assertIn('fanqie', platforms)

        qidian = self.manager.get_platform_comparison('qidian')
        self.assertEqual(qidian['name'], '起点中文网')


class TestTopicConstants(unittest.TestCase):
    """测试常量配置"""

    def test_platforms(self):
        """测试平台配置"""
        from topic_manager import TopicManager

        self.assertIn('qidian', TopicManager.PLATFORMS)
        self.assertIn('fanqie', TopicManager.PLATFORMS)

    def test_evaluation_dimensions(self):
        """测试评估维度"""
        from topic_manager import TopicManager

        self.assertIn('market_heat', TopicManager.EVALUATION_DIMENSIONS)
        self.assertIn('competition', TopicManager.EVALUATION_DIMENSIONS)
        self.assertIn('audience_size', TopicManager.EVALUATION_DIMENSIONS)


if __name__ == '__main__':
    unittest.main()
