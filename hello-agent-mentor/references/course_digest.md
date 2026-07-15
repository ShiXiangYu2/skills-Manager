# hello-agent — 课程蒸馏笔记

**生成时间**: 2026-06-22T09:32:03.432282

**课程规模**: 0 课, 0.0 小时

---

## 一、课程概览
《hello-agent》共 0 课，总时长约 0.0 小时。本轮为文本优先蒸馏，已基于转写内容生成逐课摘要、关键词、主题入口和复习路径。

以下内容来自逐课转写摘要与关键词抽取，用作 Skill 检索和学习入口。若需要引用原话或验证细节，应回到 `full_transcript.md` 与对应转录 JSON。

## 二、课程体系图
- **课程主线**：按课程顺序复盘讲者反复出现的核心问题、关键词和判断框架。
- **概念与方法**：提取课程中的关键概念、操作步骤、模型和原则，作为后续检索入口。
- **案例与应用**：整理课程中的案例、示范、数据、工具或实操场景，连接到具体课时。
- **复习与迁移**：把逐课摘要转为可执行复习顺序，并提示哪些结论需要回到原文核对。

## 三、逐课精要


## 四、跨课程主题图谱
- **核心关键词**：
- **高频主题**：优先围绕高频关键词回查逐课摘要，确认课程的主干问题。
- **案例线索**：含有“案例、数据、示范、操作、复盘”等词的课时适合作为应用入口。
- **方法线索**：含有“框架、模型、原则、步骤、路径”等词的课时适合作为体系化复习入口。

## 五、关键概念词汇表


## 六、可执行行动清单


## 七、核心金句集


## 八、文字资料补充
以下内容来自课程讲义、OCR、Markdown/TXT 笔记或其他纯文字资料，已通过 text_distillation 证据卡片流程整理。

# hello-agent — Text Course Synthesis

This synthesis is generated from pure-text sources and OCR/notes artifacts.

## 关键概念

- inalTool** (`hello_agents/tools/builtin/terminal_tool.py`)：终端工具，支持智能体进行文件系统操作和即时上下文检索（第九章 上下文工程.md#5）
- 当对话接近上下文上限时：对其进行高保真总结，并用该摘要重启一个新的上下文窗口，以维持长程连贯性。（第九章 上下文工程.md#40）
- 也称“智能体记忆”。智能体以固定频率将关键信息写入<strong>上下文外的持久化存储</strong>：在后续阶段按需拉回。（第九章 上下文工程.md#41）
- inalTool 为智能体提供了<strong>安全的命令行执行能力</strong>，支持常用的文件系统和文本处理命令，同时通过多层安全机制确保系统安全。这种：智能体不需要预先加载所有文件，而是按需探索和检索。（第九章 上下文工程.md#376）
- inal.run({"command"："find . -name '*.py' -type f"}) # 快速、实时（第九章 上下文工程.md#383）
- inal.run({"command"："grep -r 'class UserService' ."}) # 精确定位（第九章 上下文工程.md#383）
- inal.run({"command"："head -n 50 src/services/user.py"}) # 按需查看（第九章 上下文工程.md#383）
- inal.run({"command"："ls -lh /var/log/app.log"})（第九章 上下文工程.md#386）
- inal.run({"command"："tail -n 100 /var/log/app.log | grep ERROR"})（第九章 上下文工程.md#387）
- inal.run({"command"："grep ERROR /var/log/app.log | cut -d':' -f3 | sort | uniq -c"})（第九章 上下文工程.md#388）
- inal.run({"command"："head -n 5 data/sales.csv"})（第九章 上下文工程.md#391）
- inal.run({"command"："wc -l data/*.csv"})（第九章 上下文工程.md#392）
- inal.run({"command"："head -n 1 data/sales.csv | tr ',' '\n'"})（第九章 上下文工程.md#393）
- inal.run({"command"："rm -rf /"})（第九章 上下文工程.md#401）
- inalTool 只能访问指定的工作目录及其子目录：无法访问系统其他部分：（第九章 上下文工程.md#403）
- inal = TerminalTool(workspace="./project")（第九章 上下文工程.md#404）
- inal.run({"command"："cat ./src/main.py"}) # ✅（第九章 上下文工程.md#405）
- inal.run({"command"："cat /etc/passwd"}) # ❌ 不允许访问工作目录外的路径（第九章 上下文工程.md#406）
- inal.run({"command"："cd ../../../etc"}) # ❌ 不允许访问工作目录外的路径（第九章 上下文工程.md#407）
- inal = TerminalTool(（第九章 上下文工程.md#411）
- inal.run({"command"："find / -name '*.log'"})（第九章 上下文工程.md#412）
- inal.run({"command"："cat huge_file.log"})（第九章 上下文工程.md#416）
- inalTool 的实现聚焦于两个核心功能：命令执行和目录导航。（第九章 上下文工程.md#419）
- inal.run({"command"："ls -la"})（第九章 上下文工程.md#441）
- inal.run({"command"："cd src"})（第九章 上下文工程.md#442）
- inal.run({"command"："find . -name '*service*.py'"})（第九章 上下文工程.md#443）
- inal.run({"command"："cat user_service.py"})（第九章 上下文工程.md#444）
- inalTool 支持多种常见的文件系统操作模式。（第九章 上下文工程.md#446）
- inal = TerminalTool(workspace="./my_project")（第九章 上下文工程.md#450）
- inal = TerminalTool(workspace="./data")（第九章 上下文工程.md#456）
- inal = TerminalTool(workspace="/var/log")（第九章 上下文工程.md#462）
- inal = TerminalTool(workspace="./codebase")（第九章 上下文工程.md#468）
- inalTool 的真正威力在于与 MemoryTool、NoteTool 和 ContextBuilder 的协同使用。（第九章 上下文工程.md#474）
- inalTool 发现的信息可以存储到记忆系统中：（第九章 上下文工程.md#476）
- inalTool 的输出可以作为上下文的一部分：（第九章 上下文工程.md#484）
- inalTool提供了文件系统操作能力，但在9.5.2节中强调了安全性设计。请分析：当前的安全机制（路径验证、命令白名单、权限检查）是否足够？如果智能体需要访问敏感文件或执行危险操作，应该如何设计一个"人机协作审批"流程？（第九章 上下文工程.md#648）
- =concept or "general",（第八章 记忆与检索.md#399）
- 智能体的核心在于编写高质量的系统消息 (System Message)。系统消息就像是给智能体设定的“行为准则”和“专业知识库”：它精确地规定了智能体的角色、职责、工作流程，甚至是与其他智能体交互的方式。一个精心设计的系统消息是确保多智能体系统能够高效、准确协作的关键。在我们的软件开发团队中，我们为每一个角色都创建了一个独立的函数来封装其定义。（第六章 框架开发实践.md#48）
- ination_condition=TextMentionTermination("TERMINATE"),（第六章 框架开发实践.md#78）
- 好状态结构后：下一步是创建构成我们工作流的各个节点。在 LangGraph 中，每个节点都是一个执行具体任务的 Python 函数。这些函数接收当前的状态对象作为输入，并返回一个包含更新后字段的字典。（第六章 框架开发实践.md#291）

## 方法流程

- 化的 ReActAgent 在保持核心逻辑不变的同时：提升了代码的组织性和可维护性，主要是通过提示词优化和与框架工具系统的集成。（第七章 构建你的Agent框架.md#245）
- 化的ReActAgent将执行流程分解为清晰的步骤：（第七章 构建你的Agent框架.md#263）
- 实现了智能的后端选择逻辑：（第七章 构建你的Agent框架.md#413）
- 的可扩展性是设计的重要考量因素之一。你现在要扩展 `HelloAgents` 框架：为其实现一些有趣的新功能和特性。（第七章 构建你的Agent框架.md#534）
- 取舍可以遵循以下经验法则：（第九章 上下文工程.md#43）
- 分解：将复杂问题拆解为简单步骤（第五章 基于低代码平台的智能体搭建.md#114）
- 1：仔细阅读并理解用户提出的日常问题（第五章 基于低代码平台的智能体搭建.md#120）
- 2：分析问题类型和用户潜在需求（第五章 基于低代码平台的智能体搭建.md#120）
- 3：基于常识和经验提供具体可行的建议（第五章 基于低代码平台的智能体搭建.md#120）
- 4：用通俗易懂的语言组织回答内容（第五章 基于低代码平台的智能体搭建.md#120）
- 5：检查回答的实用性和安全性（第五章 基于低代码平台的智能体搭建.md#120）
- ed_texts = []（第八章 记忆与检索.md#300）
- ed_content = _preprocess_markdown_for_embedding(raw_content)（第八章 记忆与检索.md#300）
- ed_texts.append(processed_content)（第八章 记忆与检索.md#300）
- _time = time.time()：start_time（第八章 记忆与检索.md#367）
- 允许通过系统消息（System Message）为每个智能体赋予高度专业化的角色。在案例中：`ProductManager` 专注于需求，而 `CodeReviewer` 则专注于质量。一个精心设计的智能体可以在不同项目中被复用，易于维护和扩展。（第六章 框架开发实践.md#97）
- 选型是智能体产品开发过程中的关键决策之一。假设你是一家 `AI` 公司的技术架构师：公司计划开发以下三个智能体产品应用，请为每个应用选择最合适的框架（`AutoGen`、`AgentScope`、`CAMEL`、`LangGraph` 或不借助框架从零开发），并详细说明理由：（第六章 框架开发实践.md#367）
- 奖励(StepReward)鼓励模型生成清晰的推理步骤：提高可解释性。数学定义为:（第十一章 Agentic-RL.md#141）
- 检测方法包括：查找"Step 1:"， "Step 2:"等标记、查找换行符数量、使用正则表达式匹配推理模式。例如，一个包含 3 个清晰步骤的正确答案，奖励为 $1 + 0.1 \times 3 = 1.3$。（第十一章 Agentic-RL.md#144）
- 奖励的优点是鼓励可解释的推理：生成的答案更容易验证和调试，有助于模型学习系统化的思考方式。缺点是可能导致模型为了获得更多奖励生成冗余步骤，需要平衡步骤数量和答案质量，步骤检测可能不准确。（第十一章 Agentic-RL.md#150）
- 奖励：+0.3（第十一章 Agentic-RL.md#164）
- 1：运行HelloAgents评估（第十二章 智能体性能评估.md#132）
- 2：导出BFCL格式结果（第十二章 智能体性能评估.md#136）
- 3：运行BFCL官方评估（第十二章 智能体性能评估.md#137）
- 4：生成评估报告（第十二章 智能体性能评估.md#141）
- 2：导出GAIA格式结果（第十二章 智能体性能评估.md#369）
- 3：生成评估报告（第十二章 智能体性能评估.md#370）

## 案例线索

- 我们直接向模型下达指令：要求它完成情感分类任务。（第三章 大语言模型基础.md#173）
- 我们先给模型一个完整的“问题-答案”对作为示范：然后提出我们的新问题。（第三章 大语言模型基础.md#176）
- 我们提供涵盖了不同情况的多个示例：让模型对任务有更全面的理解。（第三章 大语言模型基础.md#181）
- 中使用了"分层上下文管理"策略：即时访问（TerminalTool）+ 会话记忆（MemoryTool）+ 持久笔记（NoteTool）。请分析：这三层之间应该如何协调？什么信息应该放在哪一层？如何避免信息冗余和不一致？（第九章 上下文工程.md#650）
- 中使用了"问题分类器"进行智能路由：将不同类型的请求分发到不同的子智能体。这种多智能体架构有什么优势？如果不使用分类器，而是让一个单一的智能体处理所有任务，会遇到什么问题？（第五章 基于低代码平台的智能体搭建.md#280）
- 中使用的 `Simple Vector Store` 和 `Simple Memory` 都是基于内存的：服务重启后数据会丢失。请查阅 `n8n` 文档，尝试将其替换为持久化存储方案（如 `Pinecone`、`Redis` 等），并说明配置过程。（第五章 基于低代码平台的智能体搭建.md#283）
- 中的`ask_question()`方法同时使用了RAG检索和记忆检索。请分析：在什么情况下应该优先使用RAG？在什么情况下应该优先使用Memory？如何设计一个"智能路由"机制来自动选择最合适的检索方式？（第八章 记忆与检索.md#443）
- 中使用了 `MsgHub`（消息中心）来管理智能体间的通信：请解释消息驱动架构相比传统函数调用的优势是什么？在什么场景下这种架构特别有价值？（第六章 框架开发实践.md#362）
- 中使用了 GSM8K 数据集进行训练和评估。请分析：这个数据集的特点是什么？它适合训练什么类型的推理能力？如果要训练一个能够处理更复杂数学问题（如高等数学、数学证明）的智能体，应该如何扩展数据集和训练方法？（第十一章 Agentic-RL.md#724）
- 中的训练是离线的（使用预先收集的数据集）。请设计一个"在线学习"方案：智能体在实际使用过程中持续收集用户反馈，并自动更新模型。这个方案需要考虑哪些技术挑战（如数据质量控制、灾难性遗忘、安全性保障）？（第十一章 Agentic-RL.md#724）
- **（第十三章 智能旅行助手.md#138）
- 输出：（第十四章 自动化深度研究智能体.md#136）
- 'progress':（第十四章 自动化深度研究智能体.md#476）
- 'plan':（第十四章 自动化深度研究智能体.md#477）
- 'task_summary':（第十四章 自动化深度研究智能体.md#478）
- 'report':（第十四章 自动化深度研究智能体.md#479）
- 'error':（第十四章 自动化深度研究智能体.md#480）
- 'completed':（第十四章 自动化深度研究智能体.md#481）
- Messages = [（第四章 智能体经典范式构建.md#28）

## 边界与风险

- int = 10,（第九章 上下文工程.md#284）
- 返回数量限制（第九章 上下文工程.md#285）
- int = 20（第九章 上下文工程.md#294）
- 笔记数量：避免上下文过载（第九章 上下文工程.md#371）
- 命令输出的大小：防止内存溢出：（第九章 上下文工程.md#414）
- 低,只是数据库迁移（第九章 上下文工程.md#610）
- 中,影响多个服务类（第九章 上下文工程.md#611）
- 高,核心业务逻辑（第九章 上下文工程.md#612）
- int = 5,（第八章 记忆与检索.md#104）
- =limit,（第八章 记忆与检索.md#105）
- =3（第八章 记忆与检索.md#114）
- =max(limit * 5, 20),（第八章 记忆与检索.md#216）
- =3,（第八章 记忆与检索.md#251）
- =per,（第八章 记忆与检索.md#329）
- =5,（第八章 记忆与检索.md#386）
- =limit（第八章 记忆与检索.md#400）
- 评估：识别潜在的技术风险和用户体验问题（第六章 框架开发实践.md#52）
- 这里使用了`List[Attraction]`来表示景点列表：`default_factory=list`表示默认值是一个空列表。（第十三章 智能旅行助手.md#97）
- 必须按顺序执行,每个工具只能调用一次,输出必须是JSON格式...（第十三章 智能旅行助手.md#123）
- 本文档中部分示例使用 `npx` 启动 MCP（Model Context Protocol）服务。而在本节代码仓中：我们实际采用的是 `uvx` 方式。需要说明的是，`npx` 和 `uvx` 在设计理念上高度一致，区别仅在于所处的生态系统，`npx` 面向 JavaScript/Node.js（包来自 npm），而`uvx` 面向 Python（包来自 PyPI）。两种方式并无优劣之分，请大家在使用时按需进行选择。（第十三章 智能旅行助手.md#191）
- 我们没有把 Unsplash 封装成 Tool 或 MCP 工具：而是直接在 API 路由中调用。这是因为图片搜索不需要 Agent 的智能决策，只是一个简单的数据增强步骤。如果你想让 Agent 能够自主决定是否需要图片，或者选择不同的图片来源，可以考虑把它封装成 Tool。（第十三章 智能旅行助手.md#236）
- 这里使用了`Location`类型作为字段类型：这就是嵌套类型。问号`?`表示可选字段，对应后端 Pydantic 模型中的`Optional`。（第十三章 智能旅行助手.md#253）
- 这个函数的类型签名：参数是`TripPlanRequest`类型，返回值是`Promise<TripPlan>`类型。这意味着 TypeScript 会检查调用者传递的参数是否符合要求，也会检查返回值的使用是否正确。（第十三章 智能旅行助手.md#269）
- v-model：value`指令，它实现了双向数据绑定。当用户在输入框中输入内容时，`formData.city`会自动更新。当`formData.city`的值改变时，输入框的内容也会自动更新。（第十三章 智能旅行助手.md#288）
- v-if="tripPlan.budget"`这个条件渲染。因为预算信息是可选的(在 Pydantic 模型中定义为`Optional[Budget]`)：如果 LLM 没有生成预算信息，这个卡片就不会显示。这体现了前端对数据的容错处理。（第十三章 智能旅行助手.md#315）
- 这里使用了`JSON.parse(JSON.stringify(...))`来深拷贝对象。为什么不直接赋值？因为 JavaScript 中对象是引用类型：如果直接赋值，`originalPlan`和`tripPlan`会指向同一个对象，修改一个会影响另一个。深拷贝可以创建一个完全独立的副本。（第十三章 智能旅行助手.md#328）
- ed_sources = []（第十四章 自动化深度研究智能体.md#394）
- ed_sources.append({（第十四章 自动化深度研究智能体.md#398）
- 需要设置环境变量（第十章 智能体通信协议.md#154）

## 练习与行动

- 并非循环的终点。智能体的行动会引起<strong>环境 (Environment)</strong> 的<strong>状态变化 (State Change)<：环境随即会产生一个新的<strong>观察 (Observation)</strong> 作为结果反馈。这个新的观察又会在下一轮循环中被智能体的感知系统捕获，形成一个持续的“感知-思考-行动-观察”的闭环。智能体正是通过不断重复这一循环，逐步推进任务，从初始状态向目标状态演进。（第一章 初识智能体.md#75）
- get_weather("北京")（第一章 初识智能体.md#82）
- 执行后：环境会返回一个结果。例如，`get_weather`函数可能返回一个包含详细天气数据的 JSON 对象。然而，原始的机器可读数据（如 JSON）通常包含 LLM 无需关注的冗余信息，且格式不符合其自然语言处理的习惯。（第一章 初识智能体.md#84）
- [你要执行的具体行动]（第一章 初识智能体.md#100）
- 的格式必须是以下之一：（第一章 初识智能体.md#101）
- 必须在同一行：不要换行（第一章 初识智能体.md#102）
- _match = re.search(r"Action：(.*)", llm_output, re.DOTALL)（第一章 初识智能体.md#142）
- _str = action_match.group(1).strip()（第一章 初识智能体.md#142）
- get_weather(city="北京")（第一章 初识智能体.md#151）
- get_attraction(city="北京", weather="Sunny")（第一章 初识智能体.md#153）
- Finish[今天北京的天气是晴朗的：气温26摄氏度，非常适合外出游玩。我推荐您去颐和园欣赏美丽的湖景和古建筑，或者前往长城体验其壮观的景观和深厚的历史意义。希望您有一个愉快的旅行！]（第一章 初识智能体.md#155）
- 完成，最终答案：今天北京的天气是晴朗的，气温26摄氏度，非常适合外出游玩。我推荐您去颐和园欣赏美丽的湖景和古建筑，或者前往长城体验其壮观的景观和深厚的历史意义。希望您有一个愉快的旅行！（第一章 初识智能体.md#156）
- 选择一个行动：格式必须是以下之一:（第七章 构建你的Agent框架.md#251）
- {task}（第七章 构建你的Agent框架.md#277）
- s = [（第七章 构建你的Agent框架.md#511）
- _notes = self.note_tool.run({（第九章 上下文工程.md#534）
- = """我们需要开发一个比特币价格显示应用：具体要求如下：（第六章 框架开发实践.md#83）
- 完成状态：成功（第六章 框架开发实践.md#92）
- _prompt = """（第六章 框架开发实践.md#210）
- _prompt=task_prompt,（第六章 框架开发实践.md#215）
- 适用性的边界（第六章 框架开发实践.md#255）
- =task,（第十四章 自动化深度研究智能体.md#89）
- 总结 Agent 会从每个搜索结果中提取核心观点：合并相似信息，保留重要的数字、日期、名称等关键数据，并为每个观点添加来源引用。例如，对于"Datawhale 的基本信息"的搜索结果，总结 Agent 可能生成：（第十四章 自动化深度研究智能体.md#92）
- s_payload = self._extract_tasks(response)（第十四章 自动化深度研究智能体.md#143）
- = TodoItem(（第十四章 自动化深度研究智能体.md#144）
- _summarizer_instructions = """（第十四章 自动化深度研究智能体.md#151）
- 标题：{task_title}（第十四章 自动化深度研究智能体.md#152）
- 意图：{task_intent}（第十四章 自动化深度研究智能体.md#152）
- TodoItem,（第十四章 自动化深度研究智能体.md#165）
- _title=task.title,（第十四章 自动化深度研究智能体.md#166）
- _intent=task.intent,（第十四章 自动化深度研究智能体.md#166）
- _query=task.query,（第十四章 自动化深度研究智能体.md#166）
- _summaries：List[Tuple[TodoItem, str]]（第十四章 自动化深度研究智能体.md#194）
- _summaries=formatted_summaries,（第十四章 自动化深度研究智能体.md#195）
- _summaries = []（第十四章 自动化深度研究智能体.md#226）
- _summaries.append((task, summary))（第十四章 自动化深度研究智能体.md#228）
- s1 = service._extract_tasks(response1)（第十四章 自动化深度研究智能体.md#316）
- s2 = service._extract_tasks(response2)（第十四章 自动化深度研究智能体.md#318）
- 任务信息（第十四章 自动化深度研究智能体.md#340）
- _summaries：List[Tuple[TodoItem, str, List[str]]]（第十四章 自动化深度研究智能体.md#363）
- _summaries：子任务总结列表，每个元素是(任务, 总结, 来源URL列表)（第十四章 自动化深度研究智能体.md#364）
- 序号（第十四章 自动化深度研究智能体.md#370）
- 标题（第十四章 自动化深度研究智能体.md#370）
- 意图（第十四章 自动化深度研究智能体.md#370）
- _summaries.append((task, summary, source_urls))（第十四章 自动化深度研究智能体.md#462）
- = proposal.get("task")（第十章 智能体通信协议.md#389）
- = match.group(1).strip()（第十章 智能体通信协议.md#393）
- 你决定采取的行动：必须是以下格式之一:（第四章 智能体经典范式构建.md#96）
- _match = re.search(r"Action：\s*(.*?)$", text, re.DOTALL)（第四章 智能体经典范式构建.md#113）
- = action_match.group(1).strip() if action_match else None（第四章 智能体经典范式构建.md#113）
- Search[华为最新手机型号及主要卖点]（第四章 智能体经典范式构建.md#136）
- Finish[根据最新信息：华为的最新手机可能是HUAWEI Pura 80 Pro+或HUAWEI Mate 70。其中，HUAWEI Mate 70的主要卖点包括顶级的拍照配置，全焦段覆盖，适合专业摄影，做工出色，并且具有良好的户外抗摔性能。而HUAWEI Pura 80 Pro+则强调了先锋影像技术。]（第四章 智能体经典范式构建.md#139）
- 完成 ---（第四章 智能体经典范式构建.md#223）
- 编写一个Python函数：找出1到n之间所有的素数 (prime numbers)。（第四章 智能体经典范式构建.md#286）

## 待确认问题

- ** {question}（第七章 构建你的Agent框架.md#253）
- =input_text,（第七章 构建你的Agent框架.md#267）
- {question}（第七章 构建你的Agent框架.md#295）
- = "一个水果店周一卖出了15个苹果：周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？"（第七章 构建你的Agent框架.md#308）
- ⚠️ 缺少索引,email 字段未设置唯一约束（第九章 上下文工程.md#584）
- ✅ 设计合理（第九章 上下文工程.md#585）
- ⚠️ 缺少创建时间字段,不利于数据分析（第九章 上下文工程.md#586）
- 分析能力（第五章 基于低代码平台的智能体搭建.md#113）
- 用户问题（第八章 记忆与检索.md#383）
- =question,（第八章 记忆与检索.md#386）
- Janet's ducks lay 16 eggs per day. She eats three for breakfast（第十一章 Agentic-RL.md#7）
- Natalia sold clips to 48 of her friends in April, and then she sold half（第十一章 Agentic-RL.md#86）
- = """Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?"""（第十一章 Agentic-RL.md#226）
- = "What is 48 + 24?"（第十一章 Agentic-RL.md#373）
- = error['question']（第十一章 Agentic-RL.md#465）
- {problem_a}（第十二章 智能体性能评估.md#590）
- {problem_b}（第十二章 智能体性能评估.md#591）
- 表述的清晰度（第十二章 智能体性能评估.md#592）
- = match.group(1).strip() if match else text（第十章 智能体通信协议.md#373）
- 一个水果店周一卖出了15个苹果：周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？（第四章 智能体经典范式构建.md#217）



---

## 附录：逐课摘要

