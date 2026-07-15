---
name: novel-scoring
description: 10维度评分。对章节进行多维度评分、查看历史评分。当用户说"评分""对第X章评分""查看评分"时使用。
---

# 10 维度评分

## 评分维度

| 维度 | 说明 | 评分标准 |
|------|------|---------|
| opening | 开场吸引力 | 前三段是否抓人 |
| plot_progress | 剧情推进 | 本章是否推动了主线 |
| conflict | 冲突强度 | 冲突是否有张力 |
| character_motivation | 人物动机 | 人物行为是否合理 |
| satisfaction | 爽点兑现 | 爽点是否铺垫到位、兑现有力 |
| foreshadowing | 伏笔质量 | 伏笔是否自然、有回收预期 |
| hook | 章末钩子 | 是否让人想看下一章 |
| fluency | 语言流畅度 | 是否通顺、无 AI 味 |
| pacing | 网文节奏 | 快慢是否得当 |
| originality_risk | 原创性风险 | 分越高风险越大 |

## 进行评分

```bash
# 对章节进行10维度评分
curl -X POST http://127.0.0.1:8001/api/chapters/{id}/score-10d

# 查看历史评分
curl http://127.0.0.1:8001/api/chapters/{id}/scores
```

## 评分结果示例

```json
{
  "version": "v1",
  "scores": {
    "opening": 7,
    "plot_progress": 6,
    "conflict": 5,
    "character_motivation": 7,
    "satisfaction": 6,
    "foreshadowing": 4,
    "hook": 8,
    "fluency": 8,
    "pacing": 7,
    "originality_risk": 4,
    "weighted_total": 6.4
  },
  "biggest_problem": "开篇只做场景铺垫，缺乏核心冲突",
  "strongest_point": "环境描写扎实，章末钩子有力",
  "rewrite_targets": ["建议在200字内引入人物或冲突"],
  "recommended_techniques": ["悬念前置", "冲突即开场"]
}
```

## 评分标准

| 分数 | 等级 | 说明 |
|------|------|------|
| 9-10 | 优秀 | 可直接发布 |
| 7-8 | 良好 | 小幅修改即可 |
| 5-6 | 及格 | 需要改写 |
| 3-4 | 较差 | 需要大幅改写 |
| 1-2 | 很差 | 建议重写 |

## 评分后操作

评分完成后，系统会自动：
1. 记录评分到数据库
2. 如果综合分 < 6，触发自动重写
3. 运行复盘，更新技法库
