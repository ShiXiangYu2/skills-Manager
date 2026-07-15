# Sumeru Review 协作流程图

## 职责分离架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     sumeru-review (编排器)                           │
│                     review_orchestrator.py                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  第一阶段：全局审查                            │   │
│  │                      sumeru-audit                           │   │
│  │                    audit_manager.py                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                第二阶段：章节细节审查                          │   │
│  │                      sumeru-audit                           │   │
│  │                    (Agent Team 并行)                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                第三阶段：统一修复                              │   │
│  │                      sumeru-fix                             │   │
│  │                    fix_manager.py                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 数据流向图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          输入数据                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  .sumeru/outline/chapter-outlines.json    chapters/*.md             │
│              ↓                              ↓                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   sumeru-audit                              │   │
│  │                                                             │   │
│  │  第一阶段：全局审查                                          │   │
│  │  ├─ global-issues.json (全局问题清单)                       │   │
│  │  ├─ timeline.json (时间线图谱)                              │   │
│  │  ├─ plot-map.json (剧情脉络图)                              │   │
│  │  ├─ foreshadowing-tracking.json (伏笔追踪)                  │   │
│  │  └─ bottom-line-checklist.json (底线问题清单)               │   │
│  │                                                             │   │
│  │  第二阶段：章节细节审查                                      │   │
│  │  ├─ summaries/ (章节概要目录)                               │   │
│  │  │   └─ 001.json, 002.json, ...                            │   │
│  │  ├─ chapter-issues/ (章节问题目录)                          │   │
│  │  │   └─ 001.json, 002.json, ...                            │   │
│  │  └─ word-count.json (字数统计)                              │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   sumeru-fix                                │   │
│  │                                                             │   │
│  │  第三阶段：统一修复                                          │   │
│  │  ├─ fix-plan.json (修复计划)                                │   │
│  │  ├─ fix-report.json (修复报告)                              │   │
│  │  ├─ outline-revisions.json (大纲修订记录)                   │   │
│  │  ├─ issues-fixed.json (已修复问题记录)                      │   │
│  │  └─ rewrite-chapters/ (重写章节对比)                        │   │
│  │                                                             │   │
│  │  输出修改                                                   │   │
│  │  ├─ chapters/*.md (直接修改)                                │   │
│  │  ├─ .sumeru/write/original/*.md (自动备份)                  │   │
│  │  └─ .sumeru/outline/chapter-outlines.json (大纲修订)        │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│                         输出数据                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
.agents/skills/
├── sumeru-review/                    # 组合调用编排器
│   ├── SKILL.md                      # 技能说明（三阶段流程）
│   ├── review_orchestrator.py        # 编排器实现
│   └── WORKFLOW.md                   # 本文档
│
├── sumeru-audit/                     # 审查审计技能
│   ├── SKILL.md                      # 技能说明（第一、二阶段）
│   └── audit_manager.py             # 审查管理器实现
│
└── sumeru-fix/                       # 问题修复技能
    ├── SKILL.md                      # 技能说明（第三阶段）
    └── fix_manager.py               # 修复管理器实现
```

## 调用关系

### 1. 组合调用模式（使用 sumeru-review）

```python
# review_orchestrator.py 会自动调用 sumeru-audit 和 sumeru-fix
from review_orchestrator import create_review_orchestrator

orchestrator = create_review_orchestrator(project_root)
orchestrator.run_full_review()  # 执行完整三阶段流程
```

### 2. 独立调用模式

```python
# 仅执行审查（不修复）
from audit_manager import create_audit_manager

audit = create_audit_manager(project_root)
# 执行审查逻辑...

# 仅执行修复（基于已有审查结果）
from fix_manager import create_fix_manager

fix = create_fix_manager(project_root)
# 执行修复逻辑...
```

## 数据存储结构

```
.sumeru/
├── audit/                            # 审查数据（sumeru-audit 输出）
│   ├── global-issues.json            # 全局问题清单
│   ├── timeline.json                 # 时间线图谱
│   ├── plot-map.json                 # 剧情脉络图
│   ├── foreshadowing-tracking.json   # 伏笔追踪表
│   ├── coherence-score.json          # 连贯性评分
│   ├── bottom-line-checklist.json    # 底线问题清单
│   ├── word-count.json               # 字数统计
│   ├── summaries/                    # 章节概要目录
│   │   ├── 001.json
│   │   ├── 002.json
│   │   └── ...
│   └── chapter-issues/               # 章节问题目录
│       ├── 001.json
│       ├── 002.json
│       └── ...
│
├── fix/                              # 修复数据（sumeru-fix 输出）
│   ├── fix-plan.json                 # 修复计划
│   ├── fix-report.json               # 修复报告
│   ├── outline-revisions.json        # 大纲修订记录
│   ├── issues-fixed.json             # 已修复问题记录
│   └── rewrite-chapters/             # 重写章节对比
│       ├── 001.json
│       └── ...
│
└── write/
    └── original/                     # 自动备份目录
        ├── 001.md
        ├── 002.md
        └── ...
```

## Agent 并行处理规则

### 审查阶段（sumeru-audit）

- 每个子 Agent 最多负责 3 个章节
- 所需 Agent 数 = ceil(总章节数 / 3)
- 分配策略：按章节顺序连续分配
- 示例：10 章 → 4 个 Agent（3+3+3+1）

### 修复阶段（sumeru-fix）

- 轻量修复：每个 Agent 最多负责 3 个章节
- 章节重写：基于修订后的大纲，使用子 Agent 并行重写
- 重写前后对比记录到 `rewrite-chapters/`

## 修复类型

### 1. 轻量修复

- 文字修正
- 段落调整
- 语句优化
- 字数填充
- 直接修改 `chapters/` 文件

### 2. 严重问题闭环修复

- 剧情逻辑严重矛盾
- 大面积 OOC
- 设定崩坏
- 重复情节
- 流程：大纲修订 → 章节重写

### 3. 底线问题专项修复

- 时间线矛盾
- 设定崩坏
- 人物 OOC
- 重复情节
- 信息泄露
- 伏笔死结
- 必须全部解决或标记「需人工干预」

## 底线问题零遗漏机制

1. 逐一核对 `bottom-line-checklist.json` 中的每项底线问题
2. 轻量修复能解决的 → 标记为「已解决-轻量修复」
3. 大纲修订+重写能解决的 → 标记为「已解决-重写修复」
4. 无法自动解决的 → 标记为「需人工干预」，并输出明确建议
5. **全部底线问题标记后，流程才允许结束**

## 数据复用

- 返工修改时直接读取问题清单定位需要调整的章节
- 支持增量审查，新增章节时基于已有审查结果只检测新增内容
- 修复完成后可再次调用自动验证问题是否解决
- 字数填充记录可用于后续章节的字数参考

## 与其他 Skill 的配合

### 前置 Skill

- **sumeru-outline**：提供大纲数据
- **sumeru-write**：提供章节内容

### 后续 Skill

- **sumeru-polish**：接收修复后的章节，进行文笔润色
- **sumeru-finalize**：接收修复后的章节，进行完稿校验和多平台导出

### 流程衔接

```
sumeru-outline → sumeru-write → sumeru-review → sumeru-polish → sumeru-finalize
                              (audit + fix)
```
