# 实验记录

**倒序排列,最新在上。每条必须带日期。**

三周后你会忘记为什么做了某个选择 —— 写下来。

---

## 模板

```
## YYYY-MM-DD · 一句话结论

**改了什么变量:**(每次只改一个)

**配置:** 模型 / harness / extension

**数据:**
- 工具调用正确率:  % (N 次运行)
- 失败分布:环1 __ 环2 __ 环3 __ 环4 __ 环5 __ 环6 __ 环7 __

**手工读 trajectory 看到的:**

**结论 / 下一步:**
```

---

## 待办

- [ ] 装 Goose,配 Ollama,跑通 hello world
- [ ] 挂 domain-mcp(只放检索工具)
- [ ] 整理 20 条真实题目 → `evals/questions.jsonl`
- [ ] 跑基线:`run_eval.py --repeat 3`
- [ ] `analyze.py` + 手工读 10 条失败 trajectory
- [ ] 走 `docs/05-eval-plan.md` 的决策树
- [ ] 决定:买不买 Mac(9/22 发货,别拖过预订窗口)

---

## 记录
