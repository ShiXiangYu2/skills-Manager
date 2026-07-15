---
name: novel-techniques
description: 技法库管理。查看技法、筛选分类、随机获取、导入新技法。当用户说"查看技法库""有什么开篇技法""随机技法""导入技法"时使用。
---

# 技法库管理

## 查看技法库

```bash
# 查看所有技法
curl http://127.0.0.1:8001/api/techniques

# 按分类筛选
curl "http://127.0.0.1:8001/api/techniques?category=开篇"
curl "http://127.0.0.1:8001/api/techniques?category=冲突"
curl "http://127.0.0.1:8001/api/techniques?category=爽点"

# 随机获取（灵感启发）
curl "http://127.0.0.1:8001/api/techniques/random?count=3"
```

## 技法分类

| 分类 | 说明 | 数量 |
|------|------|------|
| 开篇 | 开场技法 | 2 |
| 冲突 | 冲突设计 | 3 |
| 爽点 | 爽感制造 | 1 |
| 伏笔 | 伏笔埋设与回收 | 1 |
| 节奏 | 快慢控制 | 3 |
| 人物 | 人物塑造 | 2 |
| 设定释放 | 世界观信息释放 | 2 |

## 导入技法

从 novel-note-workflow 的 skill-cards 导入：

```bash
cd "D:\GitHub Learn\novel-studio"
python scripts/import_to_studio.py --all
```

## 查看素材库

```bash
# 查看所有素材
curl http://127.0.0.1:8001/api/materials

# 按类型筛选
curl "http://127.0.0.1:8001/api/materials?type_=人设"
curl "http://127.0.0.1:8001/api/materials?type_=桥段"
```

## 技法卡结构

每个技法包含：
- `name`：技法名称
- `category`：分类
- `description`：说明
- `conditions`：使用条件
- `risks`：风险提示
- `template`：结构模板
- `quality_score`：质量评分（1-10）
- `usage_count`：使用次数

## 技法库生命周期

```
创建 → 使用 → 评分 → 更新/淘汰
                    ↓
             连续3次评分<6 → 标记为"待修正"
             连续5次评分<6 → 移入"已淘汰"
             连续3次评分>8 → 标记为"核心技法"
```
