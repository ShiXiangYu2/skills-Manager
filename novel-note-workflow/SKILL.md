---
name: novel-note-workflow
description: 小说读书笔记工作流 — Chrome/Edge + CDP + LM Studio + 飞书多维表格。读取起点小说页面，多 Agent 生成结构化笔记，自动上传飞书。
---

# Novel Note Workflow — 小说读书笔记工作流

通过 Chrome/Edge CDP 读取起点小说页面，调用本地 LM Studio 生成结构化读书笔记，自动上传飞书多维表格。

## 工作流总览

```
Chrome/Edge CLI + CDP → 页面内容提取 → LM Studio 多 Agent 分析
→ notes/ 保存 → normalize_notes.py → 飞书 dry-run → 确认后上传
```

## 完整步骤

### 1. 启动浏览器（Chrome 或 Edge）

```powershell
# Chrome（默认，端口 9222）
powershell -ExecutionPolicy Bypass -File scripts/start_chrome.ps1

# Edge（端口 9222）
powershell -ExecutionPolicy Bypass -File scripts/start_chrome.ps1 -Browser edge
```

脚本路径：`D:/GitHub Learn/novel-note-workflow/scripts/start_chrome.ps1`

### 2. 检查 CDP 连接

```bash
python scripts/check_chrome_cdp.py
```

确认输出 `[OK] Chrome CDP 可用` 或 `[OK] Edge CDP 可用`。

### 3. 在浏览器中打开起点章节

- 打开 https://www.qidian.com/
- 登录账号
- 打开目标小说章节页面

### 4. 运行多 Agent 分析

```bash
python scripts/run_pipeline.py
```

脚本自动完成：
1. 通过 CDP 连接浏览器（`http://127.0.0.1:9222`）
2. 提取当前页面的章节标题、URL、正文
3. 调用 LM Studio（`http://localhost:1234`）运行 5 个 Agent
4. 保存笔记到 `notes/`
5. 运行 `normalize_notes.py`
6. 运行 `upload_to_feishu_bitable.py --dry-run`

### 5. 确认后上传飞书

```bash
python scripts/upload_to_feishu_bitable.py
```

## 调用的工具/API

| 工具 | 用途 | 端口/地址 |
|------|------|----------|
| Chrome/Edge CDP | 浏览器调试协议，读取页面内容 | `http://127.0.0.1:9222` |
| websocket-client | Python WebSocket 库，连接 CDP | - |
| LM Studio | 本地 LLM 推理（qwen3-vl-4b） | `http://localhost:1234` |
| 飞书开放平台 API | 多维表格读写 | `https://open.feishu.cn` |
| requests | HTTP 请求 | - |
| python-dotenv | 环境变量管理 | - |

## 5 个 Agent 职责

| Agent | 职责 | 输出字段 |
|-------|------|---------|
| 阅读 Agent | 生成事实摘要 | 书名、作者、平台、章节序号、章节名、剧情摘要 |
| 剧情 Agent | 分析冲突、伏笔、爽点 | 冲突与推进、伏笔/设定、爽点/钩子 |
| 人物 Agent | 分析人物关系和变化 | 人物变化 |
| 素材 Agent | 提炼可借鉴写法 | 可借鉴素材、写法分析、简短评价、标签 |
| 审校 Agent | 检查质量和合规性 | 审校结果、问题列表 |

## 关键脚本

| 脚本 | 功能 |
|------|------|
| `scripts/start_chrome.ps1` | 启动 Chrome/Edge CDP 模式 |
| `scripts/check_chrome_cdp.py` | 检查 CDP 连接状态 |
| `scripts/run_pipeline.py` | 多 Agent 流程主脚本 |
| `scripts/normalize_notes.py` | 笔记标准化（MD → JSON + 整理后 MD） |
| `scripts/upload_to_feishu_bitable.py` | 飞书多维表格上传（支持 --dry-run） |

## 飞书配置

- App ID：`cli_aaaa97a0fef89cd5`
- 多维表格：`https://bcnve0i97ntn.feishu.cn/base/ZS60bRekZaBm2espgwEcDrLin7d`
- 有趣设定合集：`https://bcnve0i97ntn.feishu.cn/base/Lrj2bZTKOaEfJDsO1pncX9OvnXc`
- 配置文件：`D:/GitHub Learn/novel-note-workflow/.env`

## 合规要求

1. 不绕过登录、验证码、付费墙或反爬机制
2. 只处理合法访问的章节页面
3. 不保存小说完整正文
4. notes/output/飞书中只保存原创摘要和分析
5. 每次处理 1-5 章
6. 正式上传前必须 dry-run 并等待确认

## 典型使用场景

```
用户：帮我读一下起点小说《XXX》前三章，生成笔记上传飞书

Agent 执行：
1. 启动 Chrome CDP
2. 导航到小说页面
3. 逐章运行 run_pipeline.py
4. 整理笔记到 notes/
5. normalize_notes.py
6. upload_to_feishu_bitable.py --dry-run
7. 确认后 upload_to_feishu_bitable.py
```
