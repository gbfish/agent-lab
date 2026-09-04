# 00 · 词汇表

先建立语言。这些词在所有 harness 的文档里到处都是。

---

## 核心概念

### Agent(智能体)
**一个循环**,不是一次问答。

```
目标 → 规划 → 调用工具 → 观察结果 → 再规划 → …… → 完成
```

跟 chatbot 的区别是它能自主行动——写代码、执行命令、访问文件。判定标准只有一条:**决策权在模型手里,还是在你写死的代码里**。如果路径是你写死的(问 → 检索一次 → 回答),那是流水线,不是 agent。

### Tool calling / Function calling(工具调用)
让模型能「动手」的机制。你把工具的名字、描述、参数 schema 告诉模型,模型输出一段结构化的调用请求,由 harness 执行后把结果塞回上下文。

**这是本仓库要测的核心指标。** 小模型常见的失败是把调用吐成裸文本或畸形 XML,导致循环直接崩掉。

### MCP(Model Context Protocol)
把工具标准化描述出来的开放协议。写一次 MCP server,任何支持 MCP 的 harness 都能用。`domain-mcp` 就是一个 MCP server。

### Context(上下文)
每次发给模型的全部内容:系统提示 + 历史消息 + 工具定义 + 工具返回结果。它有长度上限,而且**本地模型的有效上下文往往远小于标称值**——标称 128k 不代表第 100k 个 token 还有用。

### Context engineering(上下文工程)
决定「什么进上下文、什么不进、怎么压缩」。Agent 跑到第 6、7 轮时忘了最初的问题,基本都是这里没做好。

---

## 分层:harness / framework / 你的应用

| 层 | 你写代码吗 | 例子 |
|---|---|---|
| **模型** | 否 | Qwen3、DeepSeek-V4 |
| **Harness / Runtime** | 否,配置它 | Goose、OpenHands、dsh、OpenCode |
| **Framework** | 是,调它的 API | LangGraph、CrewAI |
| **你的应用** | 是 | domain-mcp + 业务逻辑 |

### Harness(马具 / 夹具)
词源有两个:测试里的 test harness(把被测组件架起来喂输入收输出),和 ML 评测里的 evaluation harness(lm-evaluation-harness)。字面意思是马具——**模型是马,harness 是让它能真的拉动东西的那套皮带**。

模型厂商偏爱这个词,因为对他们来说产品是模型、harness 是测试台。Goose、Cline 这类自称 agent 或 runtime,因为对他们来说产品是工具本身、模型是可换零件。同一个东西,取决于你把哪一半当变量。

### Framework(框架)
你写代码去调的库。给的不是「控制权」,是「一套心智模型」。

**记住这条:harness 你拿来跑,framework 你拿来写。**

### ⚠️ 一个反直觉的事实
Agent 循环本身很短——**一个 while 循环 + 工具执行 + 一个 message 数组,大约 150 行**。所以 framework 卖的不是循环,是循环之外的东西:崩溃恢复(第 7 步失败能从第 7 步续,而不是从零)、durable state、time-travel debugging、人工审批原语。

**你想要的「完全控制」写 150 行就有了;你真正会缺的是恢复、审计、可观测性——恰恰是自己写最贵的部分。**

---

## Goose 专用术语

### Provider(提供方)
「模型从哪来」的抽象层。支持 30+ 个,包括 Ollama(本地)。可以在不同 session 间切换而不用重新配置——敏感数据走本地,公开资料走云端。

### Extension(扩展)
Goose 里「工具」的叫法,底层就是 MCP server。

> **最重要的一句话:你加了哪些 extension,就定义了这个 agent 在你的环境里能做什么、不能做什么。**
> 权限边界靠增删 extension 控制,不靠提示词。提示词是建议,extension 是物理隔离。

类型:
| type | 说明 |
|---|---|
| `stdio` | 标准输入输出启动的外部进程(**domain-mcp 属于这种**) |
| `builtin` | Goose 自带 |
| `platform` | 跑在 agent 进程内 |
| `streamable_http` | 远程 MCP,HTTP 端点 |
| `inline_python` | 内嵌 Python,用 uvx 执行 |

`available_tools` 字段可以限定只暴露某几个工具——**最简单有效的权限控制**。

### Session(会话)
一次任务的完整上下文。可列出、恢复(`goose session resume <id>`)、指定工作目录。

### Recipe(配方)
YAML 文件,打包一整套工作流:指令 + 启用哪些 extension + 用户要提供什么参数。**把一次性会话变成可重复、可分享的流程。**

最实用的用法不是手写:正常跑一个 session,满意了点 "Create Recipe",Goose 自己分析对话、提取意图和参数、预填表单。

### Subagent(子代理)
主 agent 派生的子任务执行者,有独立上下文。用来隔离长任务,避免主上下文被撑爆。

### Scheduler
定时跑任务。

### Memory
跨 session 的长期上下文。

---

## 其他会遇到的词

### Trajectory(轨迹)
一次任务里模型看到的**全部**东西的完整记录:系统提示、推理过程、每次工具调用及结果、上下文注入。DeepSeek Harness 把它做成了产品功能(Trajectory View),支持 resume / fork / search / replay。

**定位失败必须看 trajectory,不能看渲染后的界面文字。**

### Prefill / Prompt processing(预填充)
模型读入上下文的阶段,区别于逐 token 生成的 decode 阶段。RAG 每轮塞几千 token,开销全在这——所以 prefill 速度对 RAG 场景权重很高。

### Eval(评估集)
一组带标准答案的测试用例。**没有 eval,你没法证明改动让系统变好了还是变差了。** 这是 AI engineering 和普通后端开发最大的区别之一。

### Prompt injection(提示注入)
外部内容里藏着指令,被模型当成命令执行。Agent 场景下是真实攻击面——因为 agent 会去读文档、网页、邮件,而这些都是不可信输入。

### Hybrid routing(混合路由)
简单任务走本地模型,复杂推理走云端 API。本地模型在困难任务上落后于顶级云端模型时的常规做法。
