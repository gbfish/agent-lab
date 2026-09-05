# agent-lab

> 中文版:[README.md](README.md)

**An experiment bench, not a product.**

Purpose: before deciding on any architecture, model, or hardware, answer one question with data:

> When a local model drives Goose through a real agent loop (read files, run commands, edit files, look at the result, decide the next step), **which link breaks?**

Every conclusion must come from the raw records under `runs/`. "Feels fine" is not accepted.

---

## Status

| Item | Value |
|---|---|
| Phase | **Baseline + three controls done** (2026-09-05). Next variable: a `--system` prompt |
| Harness | Goose CLI (AAIF / Linux Foundation, v1.49) |
| Model | Local via Ollama. This machine is an M3 Pro 18 GB: `qwen3:14b` only at 16k context; `qwen3:8b` at 32k |
| Tools | Goose's built-in `developer` extension (shell + file read/write), each run in its own sandbox directory |
| Best config so far | **`qwen3:8b-32k`, bare**: format 100%, pass 86%, 79 s per run |
| Answered | Ring 2 (unescaped JSON quotes) is a qwen3:14b-specific quirk; all remaining failures are reasoning quality (rings 3/5); **no data supports a hardware upgrade** |
| Open | Can a prompt recover the 8b's three failure types (paths / `(no output)` / blind edits)? Can toolshim run without model swapping using a smaller interpreter? |

Numbers below; reasoning in `notes/findings.en.md`.

---

## Results (as of 2026-09-05)

12 tasks × 3 runs, all re-scored with the same `analyze.py`. Each experiment changes one variable.

| | Tool-call format | Task pass | Mean time | Mean calls | Main failure |
|---|---|---|---|---|---|
| Baseline `qwen3:14b-16k` | 83.3% (30/36) | 80.6% (29/36) | 107 s | 1.9 | Ring 2 ×6: unescaped quotes inside JSON strings, silently dropped by Ollama |
| A `qwen3:14b` + toolshim | 97.2% (35/36) | **94.4% (34/36)** | **324 s** | 5.1 | Interpreter failed 83 times across 27 runs, survived by retrying; both models exceed the GPU budget and swap every turn |
| B `qwen2.5-coder:14b` | **0%** (0/36) | 0% | 5 s | 0.0 | Emits calls as plain-text JSON; Ollama never parses; ends after one turn |
| C `qwen3:8b-32k` | **100%** (36/36) | 86.1% (31/36) | **79 s** | 2.1 | Rings 3/5: wrong paths, treats `(no output)` as failure, edits on a false premise |

**Three conclusions:**
1. **Ring 2 is a quirk of the qwen3:14b weights, not "small models can't call tools."** The 8b never had a call swallowed. Corollary: a bigger model is not necessarily better.
2. **The remaining failures are "thought wrong", not "couldn't say it":** misreading `(no output)`, blind compliance with a false premise, path reasoning. These are prompt and tool-output design problems that a 70B would most likely share.
3. **Hardware: do not buy.** None of the four data points says "the model is not capable enough."

**The seven rings** (first failing link per run, see `docs/en/04-failure-modes.md`): 1 never calls a tool · 2 call malformed / dropped by parser · 3 wrong tool or arguments · 4 tool errored and agent did not recover · 5 result returned but not used · 6 loop does not converge · 7 context overflow. Rings 1–2 are model capability; everything else is prompt, tool-output, or loop design.

---

## Quick start

Requires Python ≥ 3.10 (the scripts use `X | None` syntax), macOS or Linux.

```bash
# 1. Read the docs, in order
open docs/en/00-glossary.md      # vocabulary first
open docs/en/03-goose-setup.md   # install Goose, connect Ollama

# 2. Install Goose
brew install block-goose-cli  # or: curl -fsSL https://getgoose.ai/install.sh | bash
goose --version               # this repo is verified against 1.49.0

# 3. Prepare a model. Goose does not set num_ctx and Ollama defaults to 4096, which hides the tool
#    definitions from the model. Use a model variant with num_ctx baked in; do not rely on a server
#    environment variable (the menu-bar Ollama app does not see it).
ollama pull qwen3:8b
ollama create qwen3:8b-32k -f configs/Modelfile.qwen3-8b-32k

# 4. Smoke test: make it actually act in an empty directory
mkdir -p /tmp/goose-smoke && cd /tmp/goose-smoke
goose run --provider ollama --model qwen3:8b-32k --no-profile --with-builtin developer \
  --no-session -t "Create hello.txt in the current directory containing hello"
ls   # hello.txt must appear; if it prints code for you to run, the tools are not wired up

# 5. Run the baseline (tasks in evals/tasks.jsonl, 12 included). 12 × 3 takes about 50 min on 8b
cd -
python3 scripts/run_eval.py --model qwen3:8b-32k --repeat 3 --tag baseline
python3 scripts/analyze.py runs/<the directory it printed>/ --verbose
```

Then read the failure-distribution table `analyze.py` prints. **That table decides what to do next**; the branching logic is in `docs/en/05-eval-plan.md`.
Each experiment's `_meta.json` and `_analysis.txt` are committed under `runs/`; raw sessions are not, because they contain local paths.

---

## Layout

```
docs/       All background and decision rationale. Read here first. English in docs/en/.
configs/    Reference copies of Goose config (actual run parameters are passed per run by run_eval.py)
evals/      The task set ← the only asset in this repo with long-term value
runs/       Raw trajectories (gitignored except per-experiment summaries)
scripts/    Run tests + analyse the failure distribution
notes/      Dated conclusions after each experiment
```

Chinese docs are the originals; each has an English twin (`docs/en/`, `*.en.md`). Task prompts in `evals/tasks.jsonl` are Chinese; checks and scripts are language-neutral.

---

## Two disciplines

**1. `evals/tasks.jsonl` comes before code.**
Code gets rewritten, configs go stale, harnesses get swapped. But a task set with automatic grading keeps working under any model and any framework. Target 50; 12 to start.

**2. Commit only summaries from `runs/`.**
Exported session.json files contain local absolute paths and grow fast; they are not committed. Each experiment's `_meta.json` and `_analysis.txt` are, or the numbers in this README cannot be checked. `.gitignore` already encodes this rule.

---

## Explicitly not doing

- ❌ Not writing our own agent loop (those 150 lines wait until we understand the problem; see `docs/en/02-landscape.md`)
- ❌ Not choosing a framework (choosing now means choosing by a star table, and it would change in three months)
- ❌ Not attaching business MCP servers (domain retrieval and the like wait until the basic chain is stable)
- ❌ Not buying hardware (get the numbers first; see `docs/en/06-hardware.md`)
