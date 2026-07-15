#!/usr/bin/env python3
"""
Sumeru Topic Manager - 网文选题策划管理器
负责选题方案生成、市场分析、拆书训练、选题评估
"""
import os
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class TopicOption:
    """选题方案"""
    id: int
    title: str
    core_concept: str
    golden_finger: Dict
    core_selling_points: List[str]
    audience: str
    cool_point_pattern: Dict
    opening_suggestion: str
    scores: Dict
    risks: List[str]
    differentiation_strategy: str


@dataclass
class BookAnalysis:
    """拆书笔记"""
    book_name: str
    author: str
    platform: str
    genre: str
    tags: List[str]
    target_audience: str
    one_line_selling_point: str
    opening_analysis: Dict
    cool_point_pattern: Dict
    character_template: Dict
    hook_template: Dict
    transferable_writing: List[str]
    non_transferable: List[str]
    inspiration: Dict


@dataclass
class MarketAnalysis:
    """市场分析"""
    trending_genres: List[str]
    target_genre_performance: str
    audience_profile: str
    platform_comparison: Dict


class TopicManager:
    """选题策划管理器"""

    # 平台配置
    PLATFORMS = {
        'qidian': {
            'name': '起点中文网',
            'word_count_per_chapter': '3000-5000字',
            'reader_preference': '偏好精品、有深度、文笔好',
            'newcomer_friendliness': '较低',
            'recommendation_mechanism': '编辑推荐+算法',
        },
        'fanqie': {
            'name': '番茄小说',
            'word_count_per_chapter': '2000-3000字',
            'reader_preference': '偏好快节奏、爽点密、代入感强',
            'newcomer_friendliness': '较高',
            'recommendation_mechanism': '纯算法推荐',
        }
    }

    # 选题评估维度
    EVALUATION_DIMENSIONS = [
        'market_heat',      # 市场热度
        'competition',       # 竞争格局
        'audience_size',     # 受众规模
        'creation_difficulty',  # 创作难度
        'monetization_potential',  # 变现潜力
        'policy_risk',      # 政策风险
        'platform_fit',     # 平台适配性
    ]

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.topic_dir = os.path.join(project_root, ".sumeru", "topic")
        self.book_analysis_dir = os.path.join(self.topic_dir, "book-analysis")
        self.notes_dir = os.path.join(self.book_analysis_dir, "notes")
        os.makedirs(self.topic_dir, exist_ok=True)
        os.makedirs(self.notes_dir, exist_ok=True)

    def create_topic_option(self, option_data: Dict) -> TopicOption:
        """创建选题方案"""
        return TopicOption(
            id=option_data.get('id', 1),
            title=option_data.get('title', ''),
            core_concept=option_data.get('core_concept', ''),
            golden_finger=option_data.get('golden_finger', {}),
            core_selling_points=option_data.get('core_selling_points', []),
            audience=option_data.get('audience', ''),
            cool_point_pattern=option_data.get('cool_point_pattern', {}),
            opening_suggestion=option_data.get('opening_suggestion', ''),
            scores=option_data.get('scores', {}),
            risks=option_data.get('risks', []),
            differentiation_strategy=option_data.get('differentiation_strategy', '')
        )

    def create_book_analysis(self, book_data: Dict) -> BookAnalysis:
        """创建拆书笔记"""
        return BookAnalysis(
            book_name=book_data.get('book_name', ''),
            author=book_data.get('author', ''),
            platform=book_data.get('platform', '番茄小说'),
            genre=book_data.get('genre', ''),
            tags=book_data.get('tags', []),
            target_audience=book_data.get('target_audience', ''),
            one_line_selling_point=book_data.get('one_line_selling_point', ''),
            opening_analysis=book_data.get('opening_analysis', {}),
            cool_point_pattern=book_data.get('cool_point_pattern', {}),
            character_template=book_data.get('character_template', {}),
            hook_template=book_data.get('hook_template', {}),
            transferable_writing=book_data.get('transferable_writing', []),
            non_transferable=book_data.get('non_transferable', []),
            inspiration=book_data.get('inspiration', {})
        )

    def save_book_analysis(self, analysis: BookAnalysis):
        """保存拆书笔记"""
        filename = f"{analysis.book_name.replace('《', '').replace('》', '')}.json"
        filepath = os.path.join(self.notes_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(analysis), f, ensure_ascii=False, indent=2)

    def load_book_analyses(self) -> List[BookAnalysis]:
        """加载所有拆书笔记"""
        analyses = []
        if not os.path.exists(self.notes_dir):
            return analyses

        for filename in os.listdir(self.notes_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.notes_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    analyses.append(BookAnalysis(**data))

        return analyses

    def generate_structures_library(self, analyses: List[BookAnalysis]) -> Dict:
        """生成可迁移结构库"""
        structures = {
            'opening': [],    # 开篇结构
            'cool_point': [], # 爽点结构
            'character': [],  # 人物结构
            'hook': [],       # 钩子结构
        }

        for analysis in analyses:
            # 提取开篇结构
            if analysis.opening_analysis:
                structures['opening'].append({
                    'structure': analysis.opening_analysis,
                    'source': analysis.book_name,
                    'genre': analysis.genre
                })

            # 提取爽点结构
            if analysis.cool_point_pattern:
                structures['cool_point'].append({
                    'structure': analysis.cool_point_pattern,
                    'source': analysis.book_name,
                    'genre': analysis.genre
                })

            # 提取人物结构
            if analysis.character_template:
                structures['character'].append({
                    'structure': analysis.character_template,
                    'source': analysis.book_name,
                    'genre': analysis.genre
                })

            # 提取钩子结构
            if analysis.hook_template:
                structures['hook'].append({
                    'structure': analysis.hook_template,
                    'source': analysis.book_name,
                    'genre': analysis.genre
                })

        return structures

    def generate_cool_points_library(self, analyses: List[BookAnalysis]) -> List[Dict]:
        """生成爽点模式库"""
        cool_points = []

        for analysis in analyses:
            if analysis.cool_point_pattern:
                cool_points.append({
                    'type': analysis.cool_point_pattern.get('type', ''),
                    'source': analysis.book_name,
                    'genre': analysis.genre,
                    'rhythm': analysis.cool_point_pattern.get('rhythm', ''),
                    '铺垫方式': analysis.cool_point_pattern.get('preparation', ''),
                    '爆发方式': analysis.cool_point_pattern.get('explosion', ''),
                    '余韵处理': analysis.cool_point_pattern.get('aftertaste', ''),
                })

        return cool_points

    def generate_characters_library(self, analyses: List[BookAnalysis]) -> List[Dict]:
        """生成人物模板库"""
        characters = []

        for analysis in analyses:
            if analysis.character_template:
                characters.append({
                    'type': analysis.character_template.get('type', ''),
                    'source': analysis.book_name,
                    'genre': analysis.genre,
                    '性格标签': analysis.character_template.get('personality_tags', []),
                    '功能定位': analysis.character_template.get('function', ''),
                    '常见剧情': analysis.character_template.get('common_plots', []),
                })

        return characters

    def generate_hooks_library(self, analyses: List[BookAnalysis]) -> List[Dict]:
        """生成章末钩子库"""
        hooks = []

        for analysis in analyses:
            if analysis.hook_template:
                hooks.append({
                    'type': analysis.hook_template.get('type', ''),
                    'source': analysis.book_name,
                    'genre': analysis.genre,
                    '具体描述': analysis.hook_template.get('description', ''),
                    '强度': analysis.hook_template.get('strength', ''),
                    '适用场景': analysis.hook_template.get('applicable_scenes', ''),
                })

        return hooks

    def evaluate_option(self, option: TopicOption) -> Dict:
        """评估选题方案"""
        evaluation = {
            'option_id': option.id,
            'title': option.title,
            'scores': option.scores,
            'overall_score': 0,
            'recommendation': ''
        }

        # 计算综合得分
        scores = option.scores
        if scores:
            weighted_sum = 0
            weights = {
                'market_heat': 0.2,
                'competition': 0.15,
                'audience_size': 0.2,
                'creation_difficulty': 0.15,
                'monetization_potential': 0.2,
                'platform_fit': 0.1,
            }

            for dim, weight in weights.items():
                if dim in scores:
                    score = scores[dim]
                    if isinstance(score, dict):
                        score = score.get('overall', 5)
                    weighted_sum += score * weight

            evaluation['overall_score'] = round(weighted_sum, 1)

        # 生成推荐建议
        if evaluation['overall_score'] >= 7:
            evaluation['recommendation'] = '强烈推荐'
        elif evaluation['overall_score'] >= 5:
            evaluation['recommendation'] = '可以尝试'
        else:
            evaluation['recommendation'] = '建议优化'

        return evaluation

    def save_options(self, options: List[TopicOption], meta: Dict = None):
        """保存选题方案"""
        data = {
            'meta': meta or {
                'generatedAt': datetime.now().isoformat(),
            },
            'options': [asdict(o) for o in options],
            'recommendedOptionId': options[0].id if options else None
        }

        options_path = os.path.join(self.topic_dir, "options.json")
        with open(options_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_options(self) -> Dict:
        """加载选题方案"""
        options_path = os.path.join(self.topic_dir, "options.json")
        if not os.path.exists(options_path):
            return {}

        with open(options_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_summary(self, options: List[TopicOption], evaluations: List[Dict]):
        """保存选题摘要"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_options': len(options),
            'evaluations': evaluations,
            'recommended_option': None
        }

        # 找出推荐方案
        if evaluations:
            best = max(evaluations, key=lambda x: x.get('overall_score', 0))
            summary['recommended_option'] = best

        summary_path = os.path.join(self.topic_dir, "summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return summary_path

    def save_structures_library(self, structures: Dict):
        """保存可迁移结构库"""
        path = os.path.join(self.book_analysis_dir, "structures.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(structures, f, ensure_ascii=False, indent=2)

    def save_cool_points_library(self, cool_points: List[Dict]):
        """保存爽点模式库"""
        path = os.path.join(self.book_analysis_dir, "cool-points.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cool_points, f, ensure_ascii=False, indent=2)

    def save_characters_library(self, characters: List[Dict]):
        """保存人物模板库"""
        path = os.path.join(self.book_analysis_dir, "characters.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(characters, f, ensure_ascii=False, indent=2)

    def save_hooks_library(self, hooks: List[Dict]):
        """保存章末钩子库"""
        path = os.path.join(self.book_analysis_dir, "hooks.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(hooks, f, ensure_ascii=False, indent=2)

    def get_platform_comparison(self, platform: str = None) -> Dict:
        """获取平台对比信息"""
        if platform:
            return self.PLATFORMS.get(platform, {})
        return self.PLATFORMS


def create_topic_manager(project_root: str) -> TopicManager:
    """创建选题策划管理器实例"""
    return TopicManager(project_root)


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()

    manager = create_topic_manager(project_root)

    # 示例：创建拆书笔记
    sample_book = {
        'book_name': '《示例小说》',
        'author': '示例作者',
        'platform': '番茄小说',
        'genre': '都市脑洞',
        'tags': ['系统流', '打脸', '逆袭'],
        'target_audience': '男频18-30岁',
        'one_line_selling_point': '一个普通人获得系统后逆袭的故事',
        'opening_analysis': {
            'first_chapter_hook': '主角被欺负后获得系统',
            'protagonist_initial_state': '普通上班族',
            'core_conflict': '职场欺压',
            'golden_finger': '职场技能系统',
        },
        'cool_point_pattern': {
            'type': '打脸',
            'rhythm': '每2章一个小打脸，每5章一个大打脸',
            'preparation': '反派挑衅、嘲讽',
            'explosion': '主角用系统能力碾压',
            'aftertaste': '围观群众震惊反应',
        },
        'character_template': {
            'type': '废柴逆袭',
            'personality_tags': ['隐忍', '聪明', '有仇必报'],
            'function': '成长型主角',
            'common_plots': ['被欺负→获得能力→打脸→升级'],
        },
        'hook_template': {
            'type': '危机',
            'description': '章末出现新的挑战或危机',
            'strength': '强',
            'applicable_scenes': '每次打脸后',
        },
        'transferable_writing': [
            '开篇快速引入冲突',
            '打脸节奏控制',
            '系统能力逐步解锁',
        ],
        'non_transferable': [
            '具体系统设定',
            '特定行业背景',
        ],
        'inspiration': {
            '借鉴结构': '系统流+打脸循环',
            '替换外壳': '换成其他职业背景',
            '强化关系': '增加师徒线',
        }
    }

    analysis = manager.create_book_analysis(sample_book)
    manager.save_book_analysis(analysis)
    print(f"已保存拆书笔记: {analysis.book_name}")

    # 示例：创建选题方案
    sample_option = {
        'id': 1,
        'title': '《都市技能大师》',
        'core_concept': '普通上班族获得技能系统，通过学习现实技能逆袭人生',
        'golden_finger': {
            'name': '技能大师系统',
            'description': '可以通过完成任务学习各种现实技能',
            'rules': ['每项技能有熟练度等级', '高级技能需要前置技能'],
            'limitations': ['每天只能学习2小时', '技能不能直接用于战斗'],
        },
        'core_selling_points': ['系统流+都市', '技能学习有代入感', '打脸节奏明快'],
        'audience': '男频18-30岁，职场人士',
        'cool_point_pattern': {
            'type': '打脸',
            'rhythm': '每2章一个小打脸，每5章一个大打脸',
        },
        'opening_suggestion': '第1章：被领导骂→获得系统；第2章：用新学的技能解决工作难题；第3章：第一次打脸嘲笑自己的同事',
        'scores': {
            'market_heat': 8,
            'competition': 6,
            'audience_size': 9,
            'creation_difficulty': 5,
            'monetization_potential': 8,
            'policy_risk': 'low',
            'platform_fit': {
                'qidian': 7,
                'fanqie': 9,
                'recommendedPlatform': 'fanqie',
                'reason': '快节奏爽点密，适合番茄短章节'
            },
        },
        'risks': ['同类系统流作品较多', '需要持续创新打脸方式'],
        'differentiation_strategy': '聚焦现实技能学习，区别于玄幻系统'
    }

    option = manager.create_topic_option(sample_option)
    manager.save_options([option])
    print(f"已保存选题方案: {option.title}")
