# agent-lab

**这是实验台,不是产品。**

目的:在决定任何架构、模型或硬件之前,先用数据搞清楚一件事——

> 本地模型 + Goose + domain-mcp 这条链路,到底在哪一环崩。

所有结论都必须来自 `runs/` 里的原始记录,不接受「感觉还行」。

---

## 现状

| 项 | 值 |
|---|---|
| 阶段 | Phase 0 — 尚未跑通基线 |
| Harness | Goose(主) / DeepSeek Harness(对照) |
| 模型 | Ollama 本地(待定,见 `docs/06-hardware.md`) |
| 工具 | domain-mcp(检索,只读) |
| 待回答的问题 | 工具调用正确率是多少?失败集中在第几环? |

---

## 快速开始

```bash
# 1. 读文档,顺序很重要
open docs/00-glossary.md      # 词汇表,先建立语言
open docs/03-goose-setup.md   # 装 Goose 接 Ollama

# 2. 装环境
curl -fsSL https://getgoose.ai/install.sh | bash
goose configure               # 选 Ollama,host 默认 localhost:11434

# 3. 挂上 domain-mcp
cp configs/goose.example.yaml configs/goose.yaml
# 编辑 configs/goose.yaml,填入 domain-mcp 的真实路径

# 4. 准备题目(这一步最重要,别跳过)
cp evals/questions.example.jsonl evals/questions.jsonl
# 换成真实技师问过的问题,至少 20 条

# 5. 跑基线
python3 scripts/run_eval.py --config configs/goose.yaml --repeat 3
python3 scripts/analyze.py runs/<今天的日期>/
```

跑完看 `analyze.py` 输出的那张失败分布表。**那张表决定接下来做什么**,分支逻辑写在 `docs/05-eval-plan.md`。

---

## 目录说明

```
docs/       所有背景知识和决策依据。先读这里。
configs/    Goose / DeepSeek Harness 的配置
evals/      测试题集 ← 本仓库唯一有长期价值的资产
runs/       原始 trajectory 落盘(已 gitignore)
scripts/    跑测试 + 分析失败分布
notes/      每次测完的结论,按日期追加
```

---

## 两条纪律

**1. `evals/questions.jsonl` 优先于代码。**
代码会被重写,配置会过时,harness 会换。但一份真实的、带标注的技师问题集,换任何模型任何框架都还能用。这是唯一别人抄不走的东西。目标 100 条,20 条起步。

**2. 不要把 `runs/` 提交上去。**
trajectory 日志涨得快,而且里面会包含厂内文档片段。`.gitignore` 已经处理了,但每次 `git add` 前再确认一遍。

---

## 明确不做的事

- ❌ 不自己写 agent 循环(那 150 行留到搞懂之后,见 `docs/02-landscape.md`)
- ❌ 不选 framework(现在选是照评测表选,三个月后会换)
- ❌ 不加写操作工具(检索跑稳之前,只读)
- ❌ 不买硬件(先拿到数字,见 `docs/06-hardware.md`)
