# 技能边界矩阵

## 体系定位

### 网文创作技能体系架构

本技能体系是一个完整的网文创作流水线，从创意萌芽到作品完稿，提供一站式创作服务。体系采用模块化设计，各技能职责清晰、边界明确，通过数据共享机制协同工作。

#### 核心设计原则

1. **单一职责**：每个技能专注于特定创作阶段，避免功能重叠
2. **数据驱动**：通过 `.sumeru/` 目录实现技能间数据共享
3. **流程编排**：由 `sumeru-worldbuilder` 作为主控技能协调全流程
4. **质量门禁**：每个阶段设置质量检查点，确保输出质量
5. **断点恢复**：支持创作中断后从上次进度继续

#### 技能层级结构

```
主控层：sumeru-worldbuilder（全流程协调）
    ├── 选题层：sumeru-topic（创意策划）
    ├── 大纲层：sumeru-outline（结构设计）
    ├── 创作层：sumeru-write（内容生成）
    ├── 审查层：sumeru-review（质量控制）
    │   ├── sumeru-audit（问题检测）
    │   └── sumeru-fix（问题修复）
    ├── 润色层：sumeru-polish（文笔优化）
    └── 完稿层：sumeru-finalize（技术校验与导出）
```

## 功能边界

### 各技能职责范围

#### 1. sumeru-worldbuilder（世界构建师）

**职责**：全流程协调与数据流转
- 收集用户创作需求
- 协调各子技能的调用顺序与参数传递
- 管理创作进度与断点恢复
- 执行止损判断机制
- 管理工作时长与节奏

**不负责**：具体内容创作、问题检测、文笔优化

#### 2. sumeru-topic（选题策划）

**职责**：创意生成与市场分析
- 拆书训练与成功案例分析
- 市场热点题材分析
- 多维度选题方案生成
- 金手指设计与爽点规划
- 平台适配性评估

**不负责**：大纲设计、内容创作、问题修复

#### 3. sumeru-outline（大纲设计）

**职责**：结构设计与世界观构建
- 世界观设定（力量体系、社会规则、地理设定）
- 人物设定（主角、配角、反派）
- 剧情框架（主线、支线、分卷规划）
- 完整章节细纲生成
- 合规检查（避免侵权风险）

**不负责**：具体内容创作、文笔优化、技术校验

#### 4. sumeru-write（章节撰写）

**职责**：内容生成与章节创作
- 基于细纲批量生成章节内容
- 保持人物性格与剧情一致性
- 适配网文节奏（开头抓眼球、中间有冲突、结尾留悬念）
- 支持续写、重写、扩写等多种模式
- 执行章节质量门禁检查

**不负责**：大纲设计、问题检测、文笔优化

#### 5. sumeru-review（逻辑审查修复）

**职责**：质量控制与问题修复（组合调用）
- 全局审查：时间线、设定一致性、伏笔回收
- 章节细节审查：字数、OOC、物品状态、场景质量
- 问题修复：轻量修复、严重问题闭环修复、底线问题零遗漏
- 大纲修订与章节重写

**不负责**：内容创作、文笔优化、技术校验

#### 6. sumeru-audit（全局审查审计）

**职责**：问题检测与审查报告
- 全局信息审查（剧情脉络、时间线、设定一致性）
- 章节细节审查（字数、OOC、物品状态、场景质量）
- 底线问题扫描（六类致命问题）
- 生成详细问题清单

**不负责**：问题修复、内容创作、文笔优化

#### 7. sumeru-fix（问题统一修复）

**职责**：问题修复与大纲修订
- 轻量修复（文字修正、段落调整）
- 严重问题闭环修复（大纲修订+章节重写）
- 底线问题零遗漏核验
- 修复验证与报告生成

**不负责**：问题检测、内容创作、文笔优化

#### 8. sumeru-polish（内容润色）

**职责**：文笔优化与内容提升
- 三级润色等级（轻度/中度/深度）
- 风格适配（小白爽文、精品文、古风仙侠等）
- 针对性优化（节奏收紧、爽点强化、对话优化、文笔优化）
- 保持人物性格与剧情一致性

**不负责**：问题检测、问题修复、技术校验

#### 9. sumeru-finalize（完稿校验）

**职责**：技术校验与多平台导出
- 错别字、标点、语法错误检查
- 敏感内容、违规内容排查
- 格式规范统一
- 适配各平台发布格式导出
- Obsidian 导出功能

**不负责**：内容创作、文笔优化、问题修复

## 调用规则

### 标准调用流程

```
用户需求
    ↓
[sumeru-worldbuilder] 接收需求，初始化创作会话
    ↓
[sumeru-topic] 选题策划
    → 输出: 选题策划报告.md, .sumeru/topic/options.json
    ↓
[sumeru-outline] 大纲设计
    → 输入: .sumeru/topic/options.json (可选)
    → 输出: 小说大纲_*.md, .sumeru/outline/*.json
    ↓
[sumeru-write] 章节撰写
    → 输入: .sumeru/outline/chapter-outlines.json
    → 输出: chapters/*.md, .sumeru/write/*.json
    ↓
[sumeru-review] 逻辑审查修复
    → 输入: .sumeru/outline/*.json, chapters/*.md
    → 输出: 剧情审查报告.md, .sumeru/review/*.json
    ↓
[sumeru-polish] 内容润色
    → 输入: chapters/*.md, .sumeru/review/*.json
    → 输出: chapters/*.md（润色后）, .sumeru/polish/*.json
    ↓
[sumeru-finalize] 完稿校验
    → 输入: chapters/*.md
    → 输出: publish/*, .sumeru/finalize/*
```

### 子Agent并行处理规则

**全局约束**：每个子Agent最多负责3个章节

**适用阶段**：
- 细纲生成（sumeru-outline）
- 章节撰写（sumeru-write）
- 逻辑审查（sumeru-review）
- 内容润色（sumeru-polish）
- 完稿校验（sumeru-finalize）

**调度逻辑**：
1. 计算所需Agent数：`ceil(总章节数 / 3)`
2. 按章节顺序连续分配（如Agent1负责第1-3章，Agent2负责第4-6章）
3. 尾部不足3章的Agent按实际剩余章节数分配
4. 相邻章节分配给同一Agent，保持上下文连贯性

### 数据共享机制

所有技能通过 `.sumeru/` 目录共享数据：

```
.sumeru/
├── session/          # 全局会话配置、用户需求、进度状态
├── topic/            # 选题数据 → 供 outline 使用
├── outline/          # 大纲数据 → 供 write、review 使用
│   ├── chapter-outlines.json  # 完整章节细纲
│   ├── characters.json        # 人物设定
│   └── world.json             # 世界观设定
├── write/            # 创作进度 → 供 review 使用
├── review/           # 审查问题 → 供 write、polish 使用
├── polish/           # 润色结果 → 供 finalize 使用
└── finalize/         # 完稿数据
```

### 质量门禁规则

#### 章节质量门禁（sumeru-write）

**新手模式（8问检查表）**：
1. 目标明确：本章有明确目标
2. 冲突存在：有冲突或阻力
3. 情绪变化：有情绪变化曲线
4. 爽点/期待：有爽点或期待感
5. 推进主线：剧情有实质性推进
6. 强化人物：人物有成长/变化
7. 伏笔埋设：新埋伏笔或回收旧伏笔
8. 章末钩子：结尾有具体悬念

**标准模式（14项检查）**：
- 开篇速度：前1000字出现处境/矛盾/金手指/强情绪≥2项
- 目标明确性：本章有明确目标
- 爽点密度：至少1个爽点，形成循环
- 情绪曲线：有情绪变化
- 人设清晰度：出场人物有鲜明功能
- 章末钩子：结尾留下具体钩子
- 短剧感：有冲突外显、关系张力、画面感
- 推进主线：剧情有实质性推进
- 强化人物：人物有成长/变化
- 伏笔埋设：新埋伏笔或回收旧伏笔
- 设定一致：不违反已有设定
- 节奏合理：快慢交替
- 对话自然：符合人物性格
- 章节长度：字数在合理范围内

#### 底线问题零遗漏规则（sumeru-review）

**六类底线问题**：
1. 时间线矛盾（事件顺序错误、年龄/日期冲突）
2. 设定崩坏（力量体系前后不一致、世界观规则自相矛盾）
3. 人物OOC（性格突变无铺垫、行为与动机矛盾）
4. 重复情节（相似事件重复发生无差异、桥段雷同）
5. 信息泄露（角色知道不该知道的信息、信息边界混乱）
6. 伏笔死结（已埋伏笔无回收可能、伏笔自相矛盾）

**核验规则**：
- 全部底线问题必须标记为「已解决」或「需人工干预」
- 不允许跳过或搁置任何底线问题
- 修复流程结束后才允许进入下一阶段

## 场景选择指南

### 按创作阶段选择技能

#### 创意萌芽阶段
- **需求**：想写小说但不知道写什么
- **推荐技能**：`sumeru-topic`
- **输出**：选题策划报告、多套选题方案

#### 结构设计阶段
- **需求**：有选题，需要设计大纲和世界观
- **推荐技能**：`sumeru-outline`
- **输出**：世界观设定、人物设定、剧情大纲、章节细纲

#### 内容创作阶段
- **需求**：有大纲，需要生成章节内容
- **推荐技能**：`sumeru-write`
- **输出**：完整章节内容

#### 质量控制阶段
- **需求**：已有章节，需要检查逻辑问题
- **推荐技能**：`sumeru-review`（组合调用 `sumeru-audit` + `sumeru-fix`）
- **输出**：审查报告、修复后的章节

#### 文笔优化阶段
- **需求**：章节内容需要提升文笔
- **推荐技能**：`sumeru-polish`
- **输出**：润色后的章节

#### 完稿发布阶段
- **需求**：需要校验技术问题并导出发布格式
- **推荐技能**：`sumeru-finalize`
- **输出**：多平台发布格式、完稿报告

### 按用户需求选择技能

#### "我想写小说"
- **推荐**：`sumeru-worldbuilder`（全流程一站式服务）
- **流程**：选题 → 大纲 → 创作 → 审查 → 润色 → 完稿

#### "帮我写一章小说"
- **推荐**：`sumeru-write`
- **前提**：需要已有大纲和细纲

#### "检查小说有没有bug"
- **推荐**：`sumeru-review`（自动调用 audit + fix）
- **输出**：审查报告、修复后的章节

#### "润色这段小说"
- **推荐**：`sumeru-polish`
- **选项**：轻度/中度/深度润色

#### "导出发布格式"
- **推荐**：`sumeru-finalize`
- **选项**：起点/番茄/晋江等平台格式

### 按项目类型选择技能组合

#### 新建项目（从零开始）
- **技能组合**：`sumeru-topic` → `sumeru-outline` → `sumeru-write` → `sumeru-review` → `sumeru-polish` → `sumeru-finalize`
- **协调者**：`sumeru-worldbuilder`

#### 续写项目（已有大纲）
- **技能组合**：`sumeru-write` → `sumeru-review` → `sumeru-polish` → `sumeru-finalize`
- **前提**：已有 `.sumeru/outline/` 数据

#### 修复项目（已有章节）
- **技能组合**：`sumeru-review` → `sumeru-fix` → `sumeru-polish` → `sumeru-finalize`
- **前提**：已有 `chapters/` 目录

#### 优化项目（已完稿）
- **技能组合**：`sumeru-polish` → `sumeru-finalize`
- **前提**：已有完整章节内容

### 按问题类型选择技能

#### 时间线矛盾
- **检测**：`sumeru-audit`（全局审查）
- **修复**：`sumeru-fix`（大纲修订+章节重写）

#### 人物OOC
- **检测**：`sumeru-audit`（章节细节审查）
- **修复**：`sumeru-fix`（轻量修复或重写）

#### 设定崩坏
- **检测**：`sumeru-audit`（全局审查）
- **修复**：`sumeru-fix`（大纲修订+章节重写）

#### 文笔不佳
- **优化**：`sumeru-polish`（三级润色）
- **选项**：轻度/中度/深度

#### 技术问题（错别字、标点）
- **校验**：`sumeru-finalize`（技术校验）
- **导出**：多平台发布格式

## 附录：技能依赖关系图

```
sumeru-worldbuilder (主控)
    ├── 依赖 → sumeru-topic
    ├── 依赖 → sumeru-outline
    ├── 依赖 → sumeru-write
    ├── 依赖 → sumeru-review
    │   ├── 调用 → sumeru-audit
    │   └── 调用 → sumeru-fix
    ├── 依赖 → sumeru-polish
    └── 依赖 → sumeru-finalize

sumeru-topic → 输出 → sumeru-outline
sumeru-outline → 输出 → sumeru-write
sumeru-write → 输出 → sumeru-review
sumeru-review → 输出 → sumeru-polish
sumeru-polish → 输出 → sumeru-finalize
```

## 附录：数据流转矩阵

| 技能 | 输入数据 | 输出数据 | 存储位置 |
|------|---------|---------|---------|
| sumeru-topic | 用户需求 | 选题策划报告、options.json | `.sumeru/topic/` |
| sumeru-outline | options.json（可选） | 世界观、人设、大纲、细纲 | `.sumeru/outline/` |
| sumeru-write | chapter-outlines.json | 章节内容 | `chapters/` |
| sumeru-audit | 大纲、章节内容 | 问题清单、底线问题清单 | `.sumeru/audit/` |
| sumeru-fix | 审查问题清单 | 修复后的章节、大纲修订记录 | `.sumeru/fix/` |
| sumeru-polish | 章节内容、审查问题 | 润色后的章节 | `chapters/` |
| sumeru-finalize | 章节内容 | 多平台发布格式、完稿报告 | `publish/` |

## 相关文档

- [术语表](glossary.md) - 网文创作、质量控制、技术实现等关键术语定义
- [sumeru-review 协作流程图](../sumeru-review/WORKFLOW.md) - 审查修复三阶段流程详解
- [sumeru-outline 风格参考库](../sumeru-outline/references/) - 多风格设定参考信息库