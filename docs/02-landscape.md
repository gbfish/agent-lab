# 02 · 开源 Agent 生态与选型

> English version: [en/02-landscape.md](en/02-landscape.md)

> 数据来源:2026-08-29 的 GitHub 星数快照。这个领域变化很快,超过三个月请重新核对。

---

## 全景表

| 项目 | 星数 | 语言/形态 | 定位 | MCP | 本地模型 |
|---|---|---|---|---|---|
| DeepSeek Harness | ~203k | Node/TS CLI | 全插件化,developer preview | ✅ | ✅ |
| OpenCode | ~202k | TS 终端 UI | provider 无关,MCP + LSP | ✅ | ✅ 75+ |
| Codex CLI | ~119k | CLI | OpenAI 官方,带沙箱 | ✅ | ⚠️ |
| Pi | ~98k | CLI | 精简省 token,易改造 | ✅ | ✅ |
| **OpenHands** | ~85k | Python/Docker | 自主执行 + 沙箱隔离 | ✅ | ✅ LiteLLM 100+ |
| Cline | ~67k | VS Code + CLI | Plan/Act 分离,每步批准 | ✅ | ✅ |
| **Goose** | ~54k | **Rust** 桌面+CLI+API | **通用 agent,不限于编码** | ✅ 70+ | ✅ |
| Aider | ~48k | Python CLI | Git 原生结对编程 | ❌ | ✅ |
| CodeWhale | ~41k | Rust | DeepSeek-TUI 演化来的 harness | ✅ | ✅ |

---

## 四条关键区分维度

### 1. 编码 agent vs 通用 agent
表里绝大多数假设你的工作对象是一个 git 仓库。**只有 Goose 明确定位为通用**——研究、自动化、数据分析和写代码并列。

我们要测的是「本地模型能不能撑住一个真实的工具循环」,不想被编码 IDE 的假设绑死,这一条基本把选择缩到 Goose 和 OpenHands。

### 2. 自主度与沙箱(= 信任层级)
- **OpenHands** 最激进:Docker 沙箱里无人值守跑完整任务
- **Cline** 最保守:每次文件编辑和终端命令都要显式批准,审计链最完整

这就是 Suggest / Draft / Automate 三层信任在产品上的实现。**做企业内部工具,先从最保守那档起步**,信任建立起来再往上推。

### 3. 离线友好度
Goose 配好 Ollama 就能离线工作。Cline 和 OpenHands 虽支持本地模型,但配成 offline-first 更麻烦。

on-prem / 数据不出厂场景下这条权重很高。

### 4. 厂商中立性
Goose 已转到 Linux Foundation 的 Agentic AI Foundation(AAIF),Apache 2.0,不绑任何模型厂商。Codex CLI 和 DeepSeek Harness 虽开源但为自家模型调优。

**做产品底座要选中立的。**

---

## 决定:主选 Goose

2026-09-04 核对:仓库在 `aaif-goose/goose`,Apache 2.0,~54k 星,v1.49.0(9/3 发布),Ollama 是一等 provider。五条全中:
1. Rust 写的 — 读源码/fork 门槛低
2. MCP 原生 — 内置 developer extension 开箱能用,以后业务 MCP 直接挂
3. 通用而非只做代码 — 匹配知识问答场景
4. Ollama 离线可用 — 匹配 on-prem
5. 基金会托管,厂商中立 — 可长期押注

---

## DeepSeek Harness:不当地基,当调试台

三周前刚开源,Node.js/TS,MIT。核心是**一切皆插件**——模型、工具、技能、会话、沙箱、存储、循环、调度、UI 都是插件,底层 Cordis 驱动。`npx @deepseek-ai/dsh web`,3080 端口。

### 两个对本仓库特别有用的功能

**Trajectory View**
模型看到的一切都记在 append-only 事件流里,resume / fork / search / replay 全作用在同一条流上。

→ 这正是「把每轮原始请求和响应落盘」的现成实现。**fork + replay 意味着可以从某一轮分叉重跑,改个提示词看结果怎么变**,其他 harness 大多没有。

**Code mode**
四种预设模式之一。它改变了工具触达模型的方式:不是把工具暴露成一个个 function call,而是**生成一个 TypeScript SDK 让模型直接写程序调用**——本来五个来回的调用序列变成一次完成。

→ 直接针对本仓库的核心风险:多轮工具调用的累积失败率从 `0.95^N` 变回接近 `0.95`。**如果基线测试结果很差,这是第一个该试的对策。基线跑通之前不碰。**

(另外两种模式:Standard 完整工具集;Minimal 只留 bash + str_replace_editor,专门用来 benchmark 模型裸能力。)

### 为什么不当地基
- Developer preview,README 全大写警告会有破坏性变更
- **不接受外部 PR** —— 只收 Discussions 和插件形式的贡献。官方定位是「一个想法、一份展示、一个灵感来源」,不是规范
- 原生 DeepSeek 路由,接 Ollama 属于「能跑但不是主路径」

---

## 明确不选的

**OpenCode** — 星数虽高,强项是终端编码工作流,LSP 的价值只在改代码时兑现。

**LangGraph 及其他 framework** — 现在不选。缺的不是框架,是「跑通一个真实 agent 循环」的手感。

关于 framework 的完整论证见下节。

---

## 关于「最终目标是 framework,我要完全控制」

这个说法要修正。三点:

**1. Framework 也是别人的抽象。** LangGraph 给的是「一套图的心智模型」——state shape、edges、reducers 都得按它的方式来。用冗长换控制,新手常在真正需要之前就把 state 过度设计了。真正的完全控制不是 framework,是自己写那 150 行 while 循环。

**2. 循环不是难的部分。** 见 `00-glossary.md`。你想要的控制权 150 行就有;你会缺的是崩溃恢复、审计、可观测性——自己写最贵。

**3. 差异化不在这一层。** Agent 循环是全世界都有的公共品,写得再好也只是重新实现了别人开源的东西。

> **该自己拥有的:工具设计、检索质量、eval 数据集、领域知识、权限模型。**
> **该租用的:循环、状态机、崩溃恢复、追踪。**

### 什么时候该往下走
1. **harness 挡了路** —— 想做的事它做不到,且不是配置问题。被需求推,不被「我想要控制权」推
2. **学习** —— 花一个周末手写那 150 行,收益极大。但**当学习,不当地基**
3. **研究** —— agentic OS 那条线的成果本来就是新抽象层,不写不行。但那是研究,跟产品是两条线

**路线:Goose 跑通 → 手写 150 行搞懂原理 → 卡住了再选 framework。**
