---
name: novel-pipeline
description: 小说写作流水线。创建项目、启动流水线、监控进度、查看结果。当用户说"创建项目""启动流水线""写第X章""查看章节"时使用。
---

# 写作流水线

## 创建项目

用户说"创建一个XX项目"时：

1. 确认项目信息：名称、题材、目标读者
2. 调用 API 创建项目
3. 引导用户添加设定和人物

```bash
# 创建项目
curl -X POST http://127.0.0.1:8001/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"项目名","genre":"题材","target_audience":"目标读者"}'

# 添加设定
curl -X POST http://127.0.0.1:8001/api/projects/{id}/bible \
  -H "Content-Type: application/json" \
  -d '{"category":"world","title":"标题","content":"内容"}'

# 添加人物
curl -X POST http://127.0.0.1:8001/api/projects/{id}/characters \
  -H "Content-Type: application/json" \
  -d '{"name":"名字","role":"角色","personality":"性格","motivation":"动机","background":"背景"}'
```

## 启动流水线

用户说"为第X章启动流水线"时：

1. 确认项目 ID 和章节号
2. 调用 API 启动流水线
3. 轮询事件流，显示进度
4. 返回最终结果

```bash
# 启动流水线
curl -X POST http://127.0.0.1:8001/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"project_id":1,"chapter_number":1}'

# 查看事件
curl http://127.0.0.1:8001/api/projects/{id}/events?limit=10

# 查看章节
curl http://127.0.0.1:8001/api/projects/{id}/chapters
```

## 查看章节

用户说"查看第X章"时：

```bash
# 获取章节详情（含正文）
curl http://127.0.0.1:8001/api/chapters/{id}
```

返回字段：
- `content`：完整正文
- `outline`：章纲
- `status`：状态（outlined/drafting/reviewed/approved/needs_rewrite）
- `word_count`：字数
- `reviews`：审校报告

## 进度监控

流水线启动后，每 10 秒轮询一次事件：

```
[0s] 编剧开始设计章纲
[50s] 编剧章纲完成
[70s] 总编审核完成
[110s] 写手初稿完成
[130s] 字数检查完成
[150s] 章尾检查完成（钩子评分 X/10）
[250s] 审校完成
[300s] 读者评分完成
[350s] 10维度评分完成：综合 7.2
[400s] 复盘完成
[400s] 流水线完成，通过
```

## 章尾检查（Step 3.6）

章尾检查师在写手初稿完成后自动运行，检查维度：
- 钩子具体性：读者是否有具体追问
- 下章衔接度：结尾是否直接触发下一章
- 反套路程度：是否使用AI式结尾
- 对话/行动推进：是否通过对话/行动而非旁白
- 情绪延续性：上一章情绪是否延续

如果综合分<7，章尾检查师会直接输出改写后的章尾，pipeline自动合并到稿件中。
重写循环时，写手会收到章尾检查师的具体反馈。
