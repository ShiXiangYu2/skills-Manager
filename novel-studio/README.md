# Novel Studio Skill

AI 小说写作工作室的 Claude Code 技能。

## 安装

```powershell
# 方式1：运行安装脚本
powershell -ExecutionPolicy Bypass -File install.ps1

# 方式2：手动复制
xcopy /E /I skill\* %USERPROFILE%\.claude\skills\novel-studio\
```

## 使用

在 Claude Code 中输入：

```
/novel-studio          # 主技能
/novel-pipeline        # 写作流水线
/novel-techniques      # 技法库管理
/novel-scoring         # 10维度评分
/novel-retrospective   # 写作复盘
```

## 前置条件

1. 启动后端：
```powershell
cd "D:\GitHub Learn\novel-studio\backend"
python run.py
```

2. 导入技法库：
```powershell
cd "D:\GitHub Learn\novel-studio"
python scripts/import_to_studio.py --all
```

## 功能

- 创建小说项目（题材、设定、人物）
- 启动写作流水线（作战卡→编剧→写手→审校→评分→复盘）
- 查看和管理技法库/素材库
- 对章节进行 10 维度评分
- 运行复盘，反哺技法库

## 技法库

当前技法库包含：
- 14 个写作技法（开篇/冲突/爽点/伏笔/节奏/人物/设定释放）
- 30 个素材卡（人设/桥段/设定/冲突/反转/爽点/伏笔）

技法来源：从 novel-note-workflow 的读书笔记中蒸馏。

## 闭环

```
读书笔记 → 蒸馏技法 → 写作 → 评分 → 复盘 → 更新技法 → 下一章更强
```
