---
name: novel-studio
description: AI 小说写作工作室。技法库驱动写作 → 10维度评分 → 复盘反哺。支持：创建项目、启动流水线、查看技法库、评分、复盘。当用户说"写小说""启动流水线""查看技法库""评分""复盘"时使用。
---

# Novel Studio — AI 小说写作工作室

技法库驱动的多 Agent 协作写作系统。读书笔记蒸馏为技法 → 技法驱动写作 → 评分 → 复盘 → 技法库持续进化。

## 范围 Scope

### 做什么
- 创建小说项目（题材、设定、人物）
- 启动写作流水线（作战卡→编剧→写手→章尾检查→审校→评分→复盘）
- 查看和管理技法库/素材库
- 对章节进行 10 维度评分
- 运行复盘，反哺技法库
- 从 novel-note-workflow 导入技法和素材
- 扩写现有章节到4500字以上

### 不做什么
- ❌ 不直接写正文（通过流水线 Agent 完成）
- ❌ 不管理飞书多维表格（那是 novel-note-workflow 的职责）
- ❌ 不修改 novel-studio 后端代码

## 字数门禁（确定性工具，非 AI 估算）

> **核心原则：AI 负责写和改，程序负责数。** 字数审查必须工程化，不能让 AI 自己数。

### 字数标准

| 区间 | 状态 | 处理 |
|------|------|------|
| 4200-4800 | ✅ PASS | 进入审校 |
| 4000-4199 | ⚠️ WARNING | 提示扩写，AI 补充内容 |
| <4000 | ❌ FAIL_SHORT | 必须扩写，AI 补充场景/互动/冲突 |
| 4801-5000 | ⚠️ WARNING | 提示压缩，AI 删除冗余 |
| >5000 | ❌ FAIL_LONG | 必须压缩，AI 精简灌水段 |

### 统计口径

统计 **有效正文字符数**：去掉空格、空行、Markdown 标题、章节号、作者备注、代码块、分隔符后，统计剩余可见字符。

**不要用**：
- `wc -m`（包含空格和换行）
- `wc -w`（按空白分词，不适合中文）
- AI 自己数（不稳定，会翻车）

**用这个**：
```bash
python "C:\Users\17551\.claude\skills\novel-studio\scripts\word_count.py" <文件路径>
```

输出示例：
```
✅ 第12章_海洋守护者.md: 4514 字 (目标 4500, 范围 4200-4800, 偏差 +14)
```

JSON 输出（供流水线集成）：
```bash
python scripts/word_count.py <文件路径> --json
```

### 流水线中的字数门禁位置

```
写手提交章节
    ↓
字数工具统计 ← 这里用确定性工具，不用 AI
    ↓
若 PASS (4200-4800)：进入审校
若 FAIL_SHORT (<4000)：AI 给扩写建议，扩写后重新计数
若 FAIL_LONG (>5000)：AI 给压缩建议，压缩后重新计数
    ↓
最多 3 轮扩写/压缩循环
    ↓
最终仍不通过：标记为需要人工干预
```

## 前置条件

1. novel-studio 后端已启动：`cd "D:\GitHub Learn\novel-studio\backend" && python run.py`
2. 技法库已有数据：`python scripts/import_to_studio.py --all`

## 核心命令

### 创建项目
```
用户：创建一个玄幻修仙项目，主角叫秦羽
```
→ 调用 `POST /api/projects` + `POST /api/projects/{id}/bible` + `POST /api/projects/{id}/characters`

### 启动流水线
```
用户：为第1章启动写作流水线
```
→ 调用 `POST /api/pipeline/run` → 监控事件流 → 返回结果

### 查看技法库
```
用户：查看技法库中有哪些开篇技法
```
→ 调用 `GET /api/techniques?category=开篇`

### 评分
```
用户：对第3章进行10维度评分
```
→ 调用 `POST /api/chapters/{id}/score-10d` → 返回评分结果

### 复盘
```
用户：复盘第3章
```
→ 调用 `POST /api/chapters/{id}/retrospective` → 返回复盘结果

### 扩写
```
用户：扩写第7章到4500字
```
→ 调用 `skills/expand/SKILL.md` 中的规则

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| POST | /api/projects | 创建项目 |
| GET | /api/projects | 列出项目 |
| POST | /api/projects/{id}/bible | 添加设定 |
| POST | /api/projects/{id}/characters | 添加人物 |
| POST | /api/pipeline/run | 启动流水线 |
| GET | /api/projects/{id}/chapters | 列出章节 |
| GET | /api/chapters/{id} | 章节详情（含正文） |
| GET | /api/techniques | 查询技法库 |
| GET | /api/techniques/random | 随机获取技法 |
| GET | /api/materials | 查询素材库 |
| POST | /api/chapters/{id}/score-10d | 10维度评分 |
| GET | /api/chapters/{id}/scores | 获取历史评分 |
| POST | /api/chapters/{id}/retrospective | 复盘 |

## 流水线流程

```
Step 0: 生成作战卡（从技法库检索推荐技法）
    ↓
Step 1: 编剧写章纲（参考作战卡 + 题材约束）
    ↓
Step 2: 总编审核章纲
    ↓
Step 3: 写手写正文（参考技法库）
    ↓
Step 3.5: 字数门禁（python word_count.py 确定性统计）
    ↓         ← FAIL_SHORT: AI 扩写 → 重新计数（最多3轮）
    ↓         ← FAIL_LONG: AI 压缩 → 重新计数（最多3轮）
    ↓         ← PASS: 进入下一步
Step 3.6: 章尾检查（钩子具体性 + 下章衔接度 + 反套路 + 对话推进 + 情绪延续）
    ↓         ← 综合分<7时自动改写章尾并合并
Step 4: 审校（审校 + 爽点编辑 + 设定管理员）
    ↓
Step 5: 读者模拟器评分
    ↓
Step 5.5: 10维度评分
    ↓
Step 5.6: 复盘（反哺技法库）
    ↓
Step 7: 自动重写循环（不达标→重写→再评分，最多3次）
```

## 10 维度评分

| 维度 | 说明 |
|------|------|
| opening | 开场吸引力 |
| plot_progress | 剧情推进 |
| conflict | 冲突强度 |
| character_motivation | 人物动机 |
| satisfaction | 爽点兑现 |
| foreshadowing | 伏笔质量 |
| hook | 章末钩子（由章尾检查师专项评分） |
| fluency | 语言流畅度 |
| pacing | 网文节奏 |
| originality_risk | 原创性风险（分越高风险越大） |

## 技法库分类

| 分类 | 说明 |
|------|------|
| 开篇 | 开场技法 |
| 冲突 | 冲突设计 |
| 爽点 | 爽感制造 |
| 伏笔 | 伏笔埋设与回收 |
| 节奏 | 快慢控制 |
| 人物 | 人物塑造 |
| 钩子 | 章末钩子 |
| 设定释放 | 世界观信息释放 |

## 子技能

- `skills/pipeline/` — 流水线操作
- `skills/techniques/` — 技法库管理
- `skills/scoring/` — 评分操作
- `skills/retrospective/` — 复盘操作
- `skills/expand/` — 章节扩写（防重复规则、去AI味）
- `skills/shared-rules.md` — 共享规则（字数标准、AI味模板、每段新功能、章节末尾规则）

---

## 扩写规则速查

> 详细规则见 `skills/expand/SKILL.md`，共享规则见 `skills/shared-rules.md`

**核心原则：**
1. 扩写目标是4500字以上，不要强行灌水
2. 每段必须有新功能（新行动/新信息/新冲突/新后果/新情绪）
3. 禁止AI味模板反应句（心跳漏了一拍、沉默了三秒、心里一紧等）
4. 禁止模板替换模板（不能把"沉默了三秒"改成"没有立刻接话"）
5. 章节结尾设置悬念钩子，不要总结式收尾

---

## 扩写后审稿规则速查

> 详细规则见 `skills/expand/SKILL.md`

**检查目标：**
1. 连续三段以上的重复内容
2. 前后相隔较远但信息和结构高度相同的段落
3. "总结目标""复盘信息""查看面板"等流程是否重复
4. AI味模板反应是否重复出现
5. 是否为了凑字数添加低信息量内容
6. 是否出现"替换型AI味"

**处理规则：**
1. 后文是前文重复 → 删除后文
2. 前文简略版、后文升级版 → 保留后文，压缩前文
3. 两段都需要保留 → 后一段承担新功能
4. 删除后检查转场是否顺畅
5. 模板化反应句优先删除，需要保留时改成场景专属动作
6. 不要使用固定替换模板
