# agent-lab

**这是实验台,不是产品。**

目的:在决定任何架构、模型或硬件之前,先用数据搞清楚一件事——

> 本地模型 + Goose 这条链路,跑一个真正的 agent 循环(读文件、跑命令、改文件、看结果再决定下一步),到底在哪一环崩。

所有结论都必须来自 `runs/` 里的原始记录,不接受「感觉还行」。

---

## 现状

| 项 | 值 |
|---|---|
| 阶段 | Phase 0 — 尚未跑通基线 |
| Harness | Goose CLI(AAIF / Linux Foundation,v1.49) |
| 模型 | Ollama 本地。本机 M3 Pro 18GB:`qwen3:8b` 已装,`qwen3:14b` 是这台机器的上限 |
| 工具 | Goose 内置 `developer` extension(shell + 文件读写),跑在每次运行独立的沙箱工作目录里 |
| 待回答的问题 | 工具调用正确率是多少?任务完成率是多少?失败集中在第几环? |

---

## 快速开始

```bash
# 1. 读文档,顺序很重要
open docs/00-glossary.md      # 词汇表,先建立语言
open docs/03-goose-setup.md   # 装 Goose 接 Ollama

# 2. 装 Goose
brew install block-goose-cli  # 或 curl -fsSL https://getgoose.ai/install.sh | bash
goose --version

# 3. 起 Ollama —— 上下文必须调大,默认 4096 会让模型根本看不到工具定义
OLLAMA_CONTEXT_LENGTH=32768 ollama serve
ollama pull qwen3:14b

# 4. 冒烟测试:在一个空目录里让它真的动手
mkdir -p /tmp/goose-smoke && cd /tmp/goose-smoke
goose run --provider ollama --model qwen3:14b --with-builtin developer \
  --no-session -t "在当前目录创建 hello.txt,内容写 hello"
ls   # 看到 hello.txt 才算接通;只输出一段代码让你自己跑 = 工具没接通

# 5. 跑基线(题目在 evals/tasks.jsonl,已带 12 条起步)
python3 scripts/run_eval.py --model qwen3:14b --repeat 3 --tag baseline
python3 scripts/analyze.py runs/<刚才输出的目录>/
```

跑完看 `analyze.py` 输出的那张失败分布表。**那张表决定接下来做什么**,分支逻辑写在 `docs/05-eval-plan.md`。

---

## 目录说明

```
docs/       所有背景知识和决策依据。先读这里。
configs/    Goose 配置的参考副本(实际运行参数由 run_eval.py 逐次传入)
evals/      任务集 ← 本仓库唯一有长期价值的资产
runs/       原始 trajectory 落盘(已 gitignore)
scripts/    跑测试 + 分析失败分布
notes/      每次测完的结论,按日期追加
```

---

## 两条纪律

**1. `evals/tasks.jsonl` 优先于代码。**
代码会被重写,配置会过时,harness 会换。但一份带自动判分的真实任务集,换任何模型任何框架都还能用。目标 50 条,12 条起步。

**2. 不要把 `runs/` 提交上去。**
每次运行会导出完整 session,涨得快。`.gitignore` 已经处理了,但每次 `git add` 前再确认一遍。

---

## 明确不做的事

- ❌ 不自己写 agent 循环(那 150 行留到搞懂之后,见 `docs/02-landscape.md`)
- ❌ 不选 framework(现在选是照评测表选,三个月后会换)
- ❌ 不接业务 MCP(domain-mcp 之类等基础链路跑稳了再说)
- ❌ 不买硬件(先拿到数字,见 `docs/06-hardware.md`)
