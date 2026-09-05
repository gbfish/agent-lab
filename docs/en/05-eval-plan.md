# 05 · Baseline test plan

> 中文版:[../05-eval-plan.md](../05-eval-plan.md)

**Goal: obtain a failure-distribution table. No architecture or purchasing decision before that.**

---

## Why this comes first

Three open questions (change model? change prompts / tool descriptions? buy a Mac?) **all have their answer hidden in the same table**, and that table costs nothing and takes two days.

Choosing without measuring is gambling. The cost of guessing wrong: three thousand dollars, or three months.

---

## What to measure

### Metric 1 · Tool-call format rate (the critical one)
Per run: were the model's tool calls valid structured calls (did not break in ring 1 / ring 2)?

**Thresholds:**
| Rate | Conclusion |
|---|---|
| **≥ 90%** | Model is adequate, the bottleneck is elsewhere → do not buy a machine, fix the software |
| **70–90%** | Borderline. Try prompt engineering / fewer tools first, then consider hardware |
| **< 70%** | Model insufficient → **hardware investment has clear value** |

### Metric 2 · Task pass rate + per-task stability
A task passes only if every `check` passes. A task that passes some of its 3 repeats and fails others is the one most worth reading.

### Metric 3 · Failure distribution over the seven rings
Each failure is attributed to the first ring that broke. See `04-failure-modes.md`.

---

## How to measure

### Step 1: the task set

`evals/tasks.jsonl` ships with 12 tasks. Format and mix are in `evals/README.md`. The iron rule for new tasks: **they must be auto-gradable.**

### Step 2: run

```bash
python3 scripts/run_eval.py --model qwen3:14b-16k --repeat 3 --tag baseline
```

`--repeat 3` because the same task can come out differently three times. **We are measuring stability, not a single performance.** 12 tasks × 3 = 36 runs; 14b takes 1–2 hours on this machine (t07 once took 240 s).

Each run's artefacts live in `runs/<date_time>/<tid>_r<n>/`: `record.json` (command, raw stdout/stderr, grading), `session.json` (full conversation), `work/` (the sandbox directory, so you can inspect what it actually changed).

### Step 3: analyse

```bash
python3 scripts/analyze.py runs/<date_time>/ --verbose
```

After editing a task's `checks` there is no need to re-run; `python3 scripts/regrade.py runs/<dir>/` re-scores.

### Step 4: read the trajectories by hand

**The script only does coarse classification. Rings 3 and 5 cannot be told apart by machine; a human has to look.**

Read at least 10 failed `session.json` files. This is the best-spent time in the whole process.

---

## Decision tree

```
Failure table in hand
│
├─ Rings 1, 2 dominate (format / no call)
│   → First rule out context (ollama_context_length ≥ 16384 in _meta.json?)
│   → Still rings 1/2 → model capability bottleneck
│   → Try qwen3:14b first (free)
│   → Still bad → hardware makes sense: M5 Max 128GB for 70B-class
│
├─ Ring 3 dominates (wrong tool / arguments)
│   → Change --system prompt, add few-shot
│   → Cheap, try first
│
├─ Ring 4 dominates (tool errored, no recovery)
│   → Is the error text returned to the model readable?
│   → Usually prompt / tool-output format; costs nothing
│
├─ Rings 5, 6, 7 dominate (context / loop)
│   → Pure software; costs nothing
│   → Context engineering + stop-condition design
│
└─ Flat distribution
    → Not at the bottleneck yet; the basic chain is unstable
    → Go back and check configuration rather than optimising any single point
```

---

## Timeline

| Day | Task | Status |
|---|---|---|
| Day 1 | Install Goose, configure Ollama, hello world | ✅ 2026-09-04 |
| Day 2 | 12-task set, runner + analyzer working | ✅ 2026-09-04 (3-task smoke 3/3) |
| Day 3 | Pull qwen3:14b, run `--repeat 3` baseline | ✅ 2026-09-04, 36 runs in 64 min |
| Day 4 | `analyze.py` + read failed trajectories by hand | ✅ 2026-09-04, all 9 read |
| Day 5 | Write conclusions to `notes/findings.md`, walk the decision tree | ✅ 2026-09-04, ring 2 dominant → free countermeasures first |
| Day 6 | Three controls: toolshim / qwen2.5-coder / qwen3:8b | ✅ early 2026-09-05, 108 runs in 4 h |
| Later | Grow the task set to 50; save the best workflow as a recipe | |

---

## Hard rules

1. **Change one variable per run.** Change model and prompt together and you cannot tell which one acted. Write it in `--tag`.
2. **Persist every raw trajectory.** Rendered text has no diagnostic value.
3. **Count only the first failing ring.** Downstream collateral failures are not counted, or the statistics are polluted.
4. **Write conclusions to `notes/findings.md`, dated.** Three weeks from now you will not remember why you chose something.
