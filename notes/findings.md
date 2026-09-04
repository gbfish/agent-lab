# 实验记录

**倒序排列,最新在上。每条必须带日期。**

三周后你会忘记为什么做了某个选择 —— 写下来。

---

## 模板

```
## YYYY-MM-DD · 一句话结论

**改了什么变量:**(每次只改一个)

**配置:** 模型 / goose 版本 / extension / max-turns

**数据:**
- 工具调用正确率:  % (N 次运行)
- 任务完成率:  % (N 次运行)
- 失败分布:环1 __ 环2 __ 环3 __ 环4 __ 环5 __ 环6 __ 环7 __

**手工读 trajectory 看到的:**

**结论 / 下一步:**
```

---

## 待办

- [x] 装 Goose(1.49.0,brew),接 Ollama,跑通 hello world
- [x] 任务集 12 条 → `evals/tasks.jsonl`
- [x] runner + analyzer 跑通(3 题冒烟)
- [ ] `ollama pull qwen3:14b` + 建 `qwen3:14b-32k`
- [ ] 跑基线:`run_eval.py --model qwen3:14b-32k --repeat 3 --tag baseline`(约 1 小时)
- [ ] 同一批题跑 `qwen3:8b-32k --repeat 3`,对照
- [ ] `analyze.py` + 手工读 10 条失败 session.json
- [ ] 走 `docs/05-eval-plan.md` 的决策树
- [ ] 决定:买不买 Mac(9/22 发货,别拖过预订窗口)
- [ ] 任务集扩到 50 条

---

## 记录

## 2026-09-04 · 链路接通;Ollama 默认 4096 上下文是第一个必须绕开的坑

**改了什么变量:** 无,建立基线环境。

**配置:** goose 1.49.0 / ollama / `--no-profile --with-builtin developer --max-turns 20 --max-tool-repetitions 3` / 本机 M3 Pro 18GB

**数据(冒烟,不是基线):**
- `qwen3:8b`,上下文 4096:t01 通过(19s,1 次调用)。但 `/api/ps` 显示 goose 不设 `num_ctx`,Ollama 按默认 4096 加载 —— 这次能过纯粹因为任务短。
- `qwen3:8b-32k`(Modelfile `num_ctx 32768`):t01 / t07 / t11 各 1 次,**3/3 通过**。工具调用格式正确率 100%(3/3)。
  - t07(改 bug + 自己跑一遍确认):5 次工具调用,130s。真的读 → 改 → 跑 → 看输出了。
  - t11(文件不存在):3 次调用,没有编数字,也没自己建文件。

**手工读 trajectory 看到的:**
- session.json 的 `toolRequest.toolCall.status` 有 `success` / `error` 两种,error 就是模型吐的调用 goose 解析不了 —— 环 2 有了直接证据来源,不用猜。
- 8b 的 thinking 很长(t01 一次调用前 thinking 约 400 个 token 事件),多步任务大部分时间花在这。

**结论 / 下一步:**
- 3 次运行不够下任何结论,只证明链路通、脚本对。
- 明天拉 `qwen3:14b`,建 32k 变体,跑 12 题 × 3。
- goose 1.49 的 `session remove --name` / `-r` 非交互报 `not connected`,session 会堆在库里,先不管。
