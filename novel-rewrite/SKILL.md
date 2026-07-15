---
name: novel-rewrite
description: 小说章节定向改写工具。读取已有章节+上下文+改写指令，通过分析师→写手→检查员三步流水线完成改写，含自动重试。当用户说"改写第X章""重写章节""修改章节"时使用。
---

# Novel Rewrite — 小说章节定向改写

基于 novel-studio 的改写专用流水线，对已有章节进行定向修改。

## 与 novel-studio 的区别

| | novel-studio | novel-rewrite |
|---|---|---|
| 输入 | 章号+题材（从零生成） | 章号+**已有章节**+**改写指令** |
| 上下文 | 只看前5章摘要 | 前3章+后2章完整上下文 |
| 流程 | PM→编剧→总编→写手→审校 | 分析师→写手→检查员（含重试） |
| 输出 | 新章节 | **基于原文定向修改** |

## 使用方式

### 基本用法

```
/novel-rewrite 第33章 灰鸥号残片增加奥斯本子承包商标识
```

### 完整参数

```
/novel-rewrite --project 15 --chapter 33 --instructions "改写指令"
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| --project | 否 | 15 | 项目ID |
| --chapter | 是 | — | 章节号 |
| --instructions | 是 | — | 改写指令 |
| --max-retry | 否 | 2 | 最大重试次数 |
| --pass-score | 否 | 85 | 通过分数门槛 |

## 工作流程

```
Step 1: 改写分析师
  输入: 原文 + 前后章上下文 + 改写指令
  输出: 改写方案（JSON）+ state_snapshot + arc_alignment
    ↓
Step 2: 改写写手
  输入: 改写方案 + 原文 + 技法规则
  输出: 改写稿
    ↓
Step 3: 连续性检查
  输入: 改写稿 + 前后章摘要
  输出: JSON（verdict + score + blocking_issues + retry_brief）
    ↓
  如果 score < 85 或有 blocking_issues：
    → Step 2（修订模式，使用 retry_brief）
    → Step 3（重新检查）
    → 最多重试 2 次
    ↓
  输出: 改写稿（保存到数据库 + 文件）
```

## 核心机制

### state_snapshot（状态快照）

分析师必须从前文摘要中提取进入本章时的硬状态：

```json
{
  "state_snapshot": {
    "characters": [{
      "name": "角色名",
      "physical_state": "伤势、疲劳、能力限制",
      "mental_state": "心理状态、情绪压力",
      "knowledge_state": "知道/不知道的信息",
      "capability_limits": "不能突破的限制"
    }],
    "active_injuries_or_constraints": [],
    "unresolved_threads": [],
    "forbidden_contradictions": []
  }
}
```

**硬性要求**：前章伤势/虚弱/能力限制必须在改写稿中体现，不能自动消失。

### retry_brief（修复指令）

检查员发现问题后，输出结构化修复指令：

```json
{
  "retry_brief": {
    "must_fix": ["必须修复的问题"],
    "preserve": ["必须保留的内容"],
    "do_not_change": ["不要动的部分"]
  }
}
```

写手在修订模式下，只修复 `must_fix` 中的问题，不重写全章。

### 自动重试

- 最多重试 2 次（共 3 轮生成）
- 通过门槛：score >= 85 且 blocking_issues 为空
- 第 1 轮：完整改写
- 第 2-3 轮：修订模式（只修复检查员指出的问题）

## 文件位置

| 文件 | 路径 |
|------|------|
| 脚本 | `D:\GitHub Learn\novel-studio\scripts\rewrite_standalone.py` |
| 分析师prompt | `D:\GitHub Learn\novel-studio\backend\prompts\rewrite_analyst.md` |
| 写手prompt | `D:\GitHub Learn\novel-studio\backend\prompts\rewrite_writer.md` |
| 修订prompt | `D:\GitHub Learn\novel-studio\backend\prompts\rewrite_writer_revision.md` |
| 检查员prompt | `D:\GitHub Learn\novel-studio\backend\prompts\rewrite_checker.md` |
| 共享规则 | `D:\GitHub Learn\novel-studio\backend\prompts\shared\` |
| 输出目录 | `D:\GitHub Learn\novel-studio\output\` |

## Agent 执行步骤

当用户调用 `/novel-rewrite` 时，执行以下步骤：

### 1. 解析参数

从用户输入中提取：
- chapter_number（必填）
- instructions（必填）
- project_id（默认15）
- max_retry（默认2）
- pass_score（默认85）

### 2. 检查前置条件

```bash
# 检查脚本是否存在
ls "D:\GitHub Learn\novel-studio\scripts\rewrite_standalone.py"

# 检查 prompt 文件是否存在
ls "D:\GitHub Learn\novel-studio\backend\prompts\rewrite_analyst.md"
ls "D:\GitHub Learn\novel-studio\backend\prompts\rewrite_writer.md"
ls "D:\GitHub Learn\novel-studio\backend\prompts\rewrite_checker.md"
ls "D:\GitHub Learn\novel-studio\backend\prompts\rewrite_writer_revision.md"
```

### 3. 执行改写

```bash
cd "D:\GitHub Learn\novel-studio"
python scripts/rewrite_standalone.py \
  --project {project_id} \
  --chapter {chapter_number} \
  --instructions "{instructions}"
```

### 4. 报告结果

向用户报告：
- 原文长度 → 改写长度
- 最终评分
- 重试次数
- 输出文件路径
- 检查员发现的问题（如有）

### 5. 可选：查看改写稿

```bash
cat "D:\GitHub Learn\novel-studio\output\第{chapter_number:02d}章_改写稿.md"
```

## 注意事项

- 改写指令要具体："假药弱化为民间蹭热度"比"改一下假药线"效果好
- 如果章节不在数据库中，脚本会自动从 .md 文件读取
- 改写稿会同时保存到数据库和输出文件
- 如果流水线因网络问题中断，可以重新运行，会覆盖上次结果
