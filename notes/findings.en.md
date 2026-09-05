# Experiment log

> 中文版:[findings.md](findings.md)

**Reverse chronological, newest first. Every entry must carry a date.**

Three weeks from now you will not remember why you made a choice. Write it down.

---

## Template

```
## YYYY-MM-DD · One-sentence conclusion

**Variable changed:** (one per run)

**Config:** model / goose version / extension / max-turns

**Data:**
- Tool-call format rate:  % (N runs)
- Task pass rate:  % (N runs)
- Failure distribution: ring1 __ ring2 __ ring3 __ ring4 __ ring5 __ ring6 __ ring7 __

**Seen while reading trajectories by hand:**

**Conclusion / next step:**
```

---

## To do

- [x] Install Goose (1.49.0, brew), connect Ollama, hello world
- [x] 12-task set → `evals/tasks.jsonl`
- [x] Runner + analyzer working (3-task smoke)
- [x] `ollama pull qwen3:14b` + build `qwen3:14b-16k` (32k does not fit)
- [x] Baseline: `run_eval.py --model qwen3:14b-16k --repeat 3 --tag baseline` (2026-09-04, 36 runs, 64 min)
- [x] `analyze.py` + read all 9 failed session.json by hand
- [x] Walk the `docs/05-eval-plan.md` decision tree → ring 2 dominant, free countermeasures first
- [x] Control A: `qwen3:8b-32k --repeat 3` → format 100%, ring 2 gone, failures all become ring 3/5 (2026-09-05)
- [x] Control B: Goose toolshim → format 97%, pass 94%, but 3× slower (2026-09-05)
- [x] Control C: `qwen2.5-coder:14b` → 0/36, emits calls as plain text (2026-09-05)
- [ ] Next variable: `--system` prompt targeting "(no output) treated as failure" and "don't fix what isn't broken". Run on 8b and 14b
- [ ] Toolshim with a smaller interpreter (`qwen3:4b`) to avoid model swapping; get 324 s back under 150 s
- [ ] Decide: buy the Mac? (ships 9/22). **All four data points say no**, see 2026-09-05 entry
- [ ] Grow the task set to 50; add: "confirm with cat after (no output)", "leave unbroken things alone", relative/absolute path confusion

---

## Entries

## 2026-09-05 · Three controls: ring 2 is a qwen3:14b quirk, the 8b is 100% format-correct; the remaining failures are all reasoning quality. Do not buy the Mac

**Variable changed:** one per control. A: toolshim on; B: qwen2.5-coder:14b; C: qwen3:8b. Everything else as baseline.

**Config:** goose 1.49.0 / `--no-profile --with-builtin developer --max-turns 20 --max-tool-repetitions 3` / 12 tasks × 3 / M3 Pro 18 GB
- A: `qwen3:14b-16k` + `GOOSE_TOOLSHIM=true GOOSE_TOOLSHIM_OLLAMA_MODEL=mistral-nemo`, timeout 1500
- B: `qwen2.5-coder:14b-16k`
- C: `qwen3:8b-32k`

**Data (all re-scored with the same analyze.py; regraded after the t11 keyword fix):**

| | Tool-call format | Task pass | Mean time | Mean calls | Main failure |
|---|---|---|---|---|---|
| Baseline qwen3:14b | 83.3% (30/36) | 80.6% (29/36) | 107 s | 1.9 | Ring 2 ×6 (unescaped JSON quotes swallowed by Ollama) |
| A toolshim + 14b | 97.2% (35/36) | **94.4% (34/36)** | **324 s** | 5.1 | Interpreter failed to parse 83 times across 27 runs, survived by retrying; 1 hit max-turns |
| B qwen2.5-coder:14b | **0%** (0/36) | 0% | 5 s | 0.0 | Emits calls as plain-text JSON (sometimes in a ``` fence); Ollama never parses; ends after one turn |
| C qwen3:8b | **100%** (36/36) | 86.1% (31/36) | **79 s** | 2.1 | Rings 3/5: wrong paths, treats (no output) as failure, edits on a false premise |

Per-task stability (passes out of 3):
- Baseline 14b: t07 2, t08 2, t10 2, t11 2, t12 0, rest full
- Toolshim: t11 2, t12 2, rest full
- 8b: t05 2, t09 2, t12 0, rest full

**Seen while reading trajectories by hand:**
- **The 8b never had a call swallowed.** So "unescaped quotes inside JSON strings" is a quirk of the qwen3:14b weights, not "small models can't call tools". Corollary: a bigger model is not necessarily better, and hardware has no certain payoff on this axis.
- **Toolshim's cost:** main model plus mistral-nemo (7 GB) exceeds the GPU budget, so Ollama swaps them every turn and time triples. The interpreter is also unstable: when the model is giving its final answer it often still fabricates an `unparseable_tool_call`, and Goose loops once more. All three t02 runs did this; the worst took 13 rounds before "port 8731" got through.
- **The 8b's failures are "thought wrong", not "couldn't say it":**
  - t05_r1: cwd was already work/, yet it wrote to `work/out/README.md`. Path reasoning (ring 3).
  - t09_r3: the `tr` conversion actually succeeded, the tool returned `(no output)`, it treated that as failure, tried three rewrites, and finally **overwrote the original notes.txt with invented content**. Ring 5, and destructive. The same pattern appeared in baseline t08_r2 and 8b t06_r2, just without damage those times.
  - t12 all three: read the file, saw nothing wrong, edited anyway (to an f-string, while admitting in the reply "the original code has no syntax error"). Blind compliance with a false premise (ring 3). The 14b under toolshim resisted 2/3; the 8b 0/3.
- **The t11 keyword list missed again** ("未在…找到"). `answer_contains` is fragile; widened, but long-term the model should emit a fixed status field.

**Conclusion / next step:**
- **Hardware: do not buy.** None of the four data points says "the model is not capable enough": 8b format is perfect; the 14b's format problem is a specific quirk that toolshim rescues; the remaining failures (misreading (no output), blind compliance, paths) are prompt and tool-output design problems that a 70B would most likely share, or at least there is no evidence it would not. The 9/22 pre-order window can go.
- **Current best config: `qwen3:8b-32k` bare.** 86% pass, 79 s per run, zero format errors. 8 points below toolshim+14b but 4× faster, and the failure modes are clean and all attackable with prompts.
- **Next variable (only this one): `--system` with three rules: `(no output)` means the command succeeded, confirm with cat rather than re-running; read before editing and leave unbroken things alone; use relative paths from `<working-directory>`.** Run on 8b and 14b; see whether t05/t09/t12 come back.
- If toolshim is to stay, swap the interpreter for something that fits, like `qwen3:4b`, and first check that the swapping disappears.
- The task set needs: "confirm after (no output)", "don't fix what isn't broken", relative/absolute paths. Those three are the real failure points now.


## 2026-09-04 · Baseline: qwen3:14b tool-call rate 83%, main bottleneck is ring 2 (unescaped JSON quotes silently dropped by Ollama)

**Variable changed:** none, this is the baseline.

**Config:** `qwen3:14b-16k` / goose 1.49.0 / `--no-profile --with-builtin developer --max-turns 20 --max-tool-repetitions 3` / 12 tasks × 3 / M3 Pro 18 GB

**Data (36 runs, mean 107 s per run, mean 1.9 tool calls):**
- Tool-call format rate: **83.3%** (30/36) → lands in the 70–90% "borderline" band
- Task pass rate: **80.6%** (29/36)
- Distribution: ring1 0 · **ring2 6** · ring3 0 · ring4 0 · ring5 0 · ring6 1 · ring7 0 · manual 2
- Single-step (t01–t05) 15/15, multi-step (t06–t10) 13/15, impossible t11 2/3, false-premise t12 0/3

**Seen while reading trajectories by hand:**
- **Ring 2's real shape:** 6 runs ended with "a long block of thinking and then nothing". The stream's `complete` event shows 25–60 output tokens after `</think>` that never became text or a toolRequest.
  Reproduced by calling Ollama directly (bypassing the parser so the raw text lands in content): the model writes
  `{"name": "edit", "arguments": {"before": "print(f\"Hello, {name}!")", ...}}`. Unescaped quote inside the string, invalid JSON, Ollama drops the whole call, Goose gets an empty message and ends. 3 of 6 samples invalid.
  Reproduced 5 times with thinking off (`think=false`): 4 calls succeeded, 1 was swallowed the same way. **Not thinking's fault.**
- **t08_r2 (ring 6):** `grep ... > errors.txt` succeeded all three times, but the tool returned `(no output)`; the model treated it as failure and retried, then reported "no ERROR found". The file was actually correct. The real cause is **ring 5 (did not understand the tool result)**, not loop design.
- **t12_r3:** false-premise task, the model changed `message` to `msg` without reading the file. Blind compliance. t12_r1/r2 "passed" because the call was swallowed and nothing happened; a `tool_calls_min` check now closes that hole.
- **t11 r1/r3:** actually correct ("settings.yaml not found"); my keyword list did not cover "未找到". Fixed, re-scored with `regrade.py`.
- Twice `rg: command not found`: the model assumes ripgrep exists.
- 16k context was never hit (ring 7 = 0); the longest run, t08_r2 with seven calls, did not overflow.

**Conclusion / next step:**
- Decision tree: ring 2 dominant → the model's structured output. But the form is very specific (quote escaping), **not "the model is too small to call tools"**; 15/15 on single-step tasks says the basic chain is stable.
- Hardware: **not yet.** Whether a 70B makes the same escaping mistake is unknown, and three free countermeasures can be tried first (see to-do).
- Next, in order, one variable each: toolshim → different model family → 8b control.

## 2026-09-04 · Chain connected; Ollama's default 4096 context is the first trap to route around

**Variable changed:** none, establishing the baseline environment.

**Config:** goose 1.49.0 / ollama / `--no-profile --with-builtin developer --max-turns 20 --max-tool-repetitions 3` / M3 Pro 18 GB

**Data (smoke, not baseline):**
- `qwen3:8b`, context 4096: t01 passed (19 s, 1 call). But `/api/ps` shows goose does not set `num_ctx` and Ollama loads at the 4096 default; it passed purely because the task was short.
- `qwen3:8b-32k` (Modelfile `num_ctx 32768`): t01 / t07 / t11 once each, **3/3 passed**. Tool-call format 100% (3/3).
  - t07 (fix a bug and re-run to confirm): 5 tool calls, 130 s. It really did read → edit → run → look at output.
  - t11 (file does not exist): 3 calls, did not invent a number, did not create the file.

**Seen while reading trajectories by hand:**
- `toolRequest.toolCall.status` in session.json is `success` or `error`; error means the model's call could not be parsed by goose. Ring 2 now has a direct evidence source instead of guesswork.
- The 8b thinks at length (about 400 thinking-token events before t01's single call); most of a multi-step task's time goes there.

- `qwen3:14b` at 32k: 15 GB, 2 GB spilled to CPU, 4% system memory free, "Say OK" took 4.5 minutes (0.1 tok/s). **Unusable.**
- `qwen3:14b` at 16k: 11.7 GB fully on GPU, 13.5 tok/s. t07 passed first try, 4 calls, 240 s (8b-32k: 130 s).

**Conclusion / next step:**
- 3 runs are not enough for any conclusion; they only prove the chain works and the scripts are right.
- On this machine 14b gets 16k context only. Whether multi-step tasks fit in 16k will show as ring 7 in the baseline.
- Baseline launched: `qwen3:14b-16k`, 12 tasks × 3. Do not run anything heavy meanwhile; swap is already at 14 GB.
- goose 1.49's `session remove --name` / `-r` fail non-interactively with `not connected`; sessions pile up in the DB. Ignoring for now.
