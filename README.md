# agent-lab

> **English summary** (full English README: [README.en.md](README.en.md); English docs under [`docs/en/`](docs/en/)). An experiment bench, not a product. It answers one question with data:
> *where does the chain **local Ollama model → Goose CLI → Goose's built-in `developer` extension**
> break when asked to run a real agent loop* (read files, run commands, edit files, look at the result,
> decide the next step)? Every conclusion is traceable to raw trajectories under `runs/`.
>
> **Results so far (12 tasks × 3 runs each, Apple M3 Pro 18 GB):**
>
> | Configuration | Tool-call format | Task pass | Mean time | Dominant failure |
> |---|---|---|---|---|
> | `qwen3:14b` (16k ctx) baseline | 83% | 81% | 107 s | Unescaped quotes inside JSON strings → Ollama silently drops the call |
> | `qwen3:14b` + Goose toolshim (`mistral-nemo` interpreter) | 97% | **94%** | **324 s** | Interpreter thrashes; both models exceed GPU budget, 3× slower |
> | `qwen2.5-coder:14b` | **0%** | 0% | 5 s | Emits tool calls as plain-text JSON; never parsed |
> | `qwen3:8b` (32k ctx) | **100%** | 86% | **79 s** | Reasoning errors only: wrong paths, treats `(no output)` as failure, edits code that wasn't broken |
>
> **Takeaways.** The 14b format failure is a quirk of that specific weight, not "small models can't call tools" —
> the 8b never dropped a call. The remaining failures are prompt and tool-output design problems that a 70B
> model would most likely share. **Buying bigger hardware is not justified by any of the four data points.**
> Current best configuration: `qwen3:8b-32k`, bare. Full write-ups in [`notes/findings.md`](notes/findings.md)
> (Chinese); the failure taxonomy ("seven rings") is [`docs/04-failure-modes.md`](docs/04-failure-modes.md).
>
> **The seven rings** (first failing link per run, see `docs/04-failure-modes.md`): 1 never calls a tool ·
> 2 call malformed / dropped by parser · 3 wrong tool or arguments · 4 tool errored and agent didn't recover ·
> 5 result returned but not used · 6 loop doesn't converge · 7 context overflow. Rings 1–2 are model capability;
> everything else is prompt, tool-output, or loop design. Only the first ring is counted per run.
>
> Chinese docs are the originals and every one has an English twin (`docs/en/`, `*.en.md`). Task prompts are Chinese;
> the checks, scripts, and per-experiment summaries under `runs/*/_analysis.txt` are language-neutral. Python ≥ 3.10.

---

**这是实验台,不是产品。**

目的:在决定任何架构、模型或硬件之前,先用数据搞清楚一件事——

> 本地模型 + Goose 这条链路,跑一个真正的 agent 循环(读文件、跑命令、改文件、看结果再决定下一步),到底在哪一环崩。

所有结论都必须来自 `runs/` 里的原始记录,不接受「感觉还行」。

---

## 现状

| 项 | 值 |
|---|---|
| 阶段 | **基线 + 三组对照已完成**(2026-09-05)。下一个变量:`--system` 提示 |
| Harness | Goose CLI(AAIF / Linux Foundation,v1.49) |
| 模型 | Ollama 本地。本机 M3 Pro 18GB:`qwen3:14b` 只能配 16k 上下文;`qwen3:8b` 可配 32k |
| 工具 | Goose 内置 `developer` extension(shell + 文件读写),跑在每次运行独立的沙箱工作目录里 |
| 当前最佳配置 | **`qwen3:8b-32k` 裸跑**:格式 100%、完成 86%、79s/次 |
| 已回答的问题 | 环 2(JSON 引号未转义)是 qwen3:14b 独有怪癖;剩余失败全是推理质量(环 3/5);**硬件升级无数据支持** |
| 待回答的问题 | 提示词能否收回 8b 的路径/`(no output)`/盲改三类失败?toolshim 换小解释器能否不换入换出? |

详细数字见下方「结果」,推理过程见 `notes/findings.md`。

---

## 结果(截至 2026-09-05)

12 题 × 3 次,同一版 `analyze.py` 重算。每组只改一个变量。

| | 工具调用格式 | 任务完成 | 平均耗时 | 平均调用 | 主要失败 |
|---|---|---|---|---|---|
| 基线 `qwen3:14b-16k` | 83.3% (30/36) | 80.6% (29/36) | 107s | 1.9 | 环 2 ×6:JSON 字符串里引号没转义,被 Ollama 静默丢弃 |
| A `qwen3:14b` + toolshim | 97.2% (35/36) | **94.4% (34/36)** | **324s** | 5.1 | 解释器 27 次运行里解析失败 83 次,靠重试扛过去;两个模型超 GPU 预算,每轮换入换出 |
| B `qwen2.5-coder:14b` | **0%** (0/36) | 0% | 5s | 0.0 | 把调用当纯文本 JSON 吐,Ollama 不解析,一轮就结束 |
| C `qwen3:8b-32k` | **100%** (36/36) | 86.1% (31/36) | **79s** | 2.1 | 环 3/5:路径写错、把 `(no output)` 当失败、前提错误盲改 |

**三个结论:**
1. **环 2 是 qwen3:14b 这个权重的怪癖,不是「模型小所以不会调工具」**——8b 一次调用都没被吞。反推:更大的模型未必更好。
2. **剩下的失败是「想错了」,不是「说不出来」**:误读 `(no output)`、盲从错误前提、路径推理错。这些是提示词和工具输出设计的问题,70B 大概率一样会犯。
3. **硬件:别买。** 四组数据没有一组指向「模型能力不够」。

---

## 快速开始

需要 Python ≥ 3.10(脚本用了 `X | None` 语法),macOS 或 Linux。

```bash
# 1. 读文档,顺序很重要
open docs/00-glossary.md      # 词汇表,先建立语言
open docs/03-goose-setup.md   # 装 Goose 接 Ollama

# 2. 装 Goose
brew install block-goose-cli  # 或 curl -fsSL https://getgoose.ai/install.sh | bash
goose --version               # 本仓库按 1.49.0 核对

# 3. 准备模型 —— Goose 不设 num_ctx,Ollama 默认 4096 会让模型看不全工具定义。
#    用带 num_ctx 的模型变体,不要依赖服务端环境变量(菜单栏版 Ollama 吃不到)
ollama pull qwen3:8b
ollama create qwen3:8b-32k -f configs/Modelfile.qwen3-8b-32k

# 4. 冒烟测试:在一个空目录里让它真的动手
mkdir -p /tmp/goose-smoke && cd /tmp/goose-smoke
goose run --provider ollama --model qwen3:8b-32k --no-profile --with-builtin developer \
  --no-session -t "在当前目录创建 hello.txt,内容写 hello"
ls   # 看到 hello.txt 才算接通;只输出一段代码让你自己跑 = 工具没接通

# 5. 跑基线(题目在 evals/tasks.jsonl,已带 12 条)。12 题 × 3 次,8b 约 50 分钟
cd -
python3 scripts/run_eval.py --model qwen3:8b-32k --repeat 3 --tag baseline
python3 scripts/analyze.py runs/<刚才输出的目录>/ --verbose
```

跑完看 `analyze.py` 输出的那张失败分布表。**那张表决定接下来做什么**,分支逻辑写在 `docs/05-eval-plan.md`。
每组实验的 `_meta.json` 和 `_analysis.txt` 已随仓库提交(`runs/`),原始 session 因含本机路径不提交。

---

## 目录说明

```
docs/       所有背景知识和决策依据。先读这里。英文版在 docs/en/。
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

**2. `runs/` 只提交摘要。**
每次运行导出的 session.json 含本机绝对路径且涨得快,不提交;每组实验的 `_meta.json` 和 `_analysis.txt` 要提交,否则 README 里的数字没法核对。`.gitignore` 已按这个规则设好。

---

## 明确不做的事

- ❌ 不自己写 agent 循环(那 150 行留到搞懂之后,见 `docs/02-landscape.md`)
- ❌ 不选 framework(现在选是照评测表选,三个月后会换)
- ❌ 不接业务 MCP(领域检索之类,等基础链路跑稳了再说)
- ❌ 不买硬件(先拿到数字,见 `docs/06-hardware.md`)
