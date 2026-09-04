# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An experiment bench, not a product. Its single purpose is to answer, with data, *where* the chain **local Ollama model → Goose CLI → Goose's built-in `developer` extension (shell + file editing)** breaks when asked to run a real agent loop. Every conclusion must be traceable to raw trajectories in `runs/`. Docs and code are written in Chinese; keep new docs/notes in Chinese to match.

Read `docs/` in numeric order before changing anything; `docs/04-failure-modes.md` (the seven rings) and `docs/05-eval-plan.md` (decision tree) are the framework the scripts implement. `notes/findings.md` holds dated results and the current to-do list.

## Environment facts (verified 2026-09-04)

- Machine: Apple M3 Pro, 18 GB unified memory. `qwen3:14b` is the largest model that fits; 30B-class does not.
- Goose 1.49.0 installed via `brew install block-goose-cli`. No `~/.config/goose/config.yaml` exists and none is needed: every run passes `--provider`, `--model`, `--no-profile`, `--with-builtin` on the command line.
- Ollama runs as the macOS app. Goose does not set `num_ctx`, so Ollama loads models at its 4096 default and silently truncates. Use the `-32k` model variants built from `configs/Modelfile.*` (`ollama create qwen3:8b-32k -f configs/Modelfile.qwen3-8b-32k`). The runner checks `/api/ps` after the first run and aborts below 16384.
- `goose session remove --name` / `-r` fail non-interactively in 1.49 ("not connected"); sessions from runs accumulate in Goose's SQLite DB. Clean up interactively with `goose session remove`.

## Commands

No build step, no test suite, no dependencies beyond Python 3.10+ stdlib.

```bash
# Baseline run: writes runs/<YYYY-MM-DD_HHMMSS>/{_meta.json, <tid>_r<n>/{record.json, session.json, work/}}
python3 scripts/run_eval.py --model qwen3:14b-32k --repeat 3 --tag "baseline"
python3 scripts/run_eval.py --model qwen3:8b-32k --only t01,t07 --repeat 1   # subset
python3 scripts/run_eval.py --model qwen3:8b-32k --system "..." --tag "system=..."  # prompt-engineering experiment

# Analyze
python3 scripts/analyze.py runs/<dir>/
python3 scripts/analyze.py runs/<dir>/ --verbose      # per-run ring + tool-call count

# Manual smoke test of the chain
goose run --provider ollama --model qwen3:8b-32k --no-profile --with-builtin developer --no-session -t "..."
```

## Architecture

Two scripts and a data contract between them:

- **`scripts/run_eval.py`** — for each (task × repeat) creates an empty sandbox `work/` dir, writes `setup.files`, runs `goose run` with cwd there and `--output-format stream-json`, captures raw stdout/stderr/rc/elapsed, then `goose session export --format json` → `session.json`, then evaluates `checks` and writes `record.json`. The full argv is stored in each record so a run is reproducible without any config file.
- **`scripts/analyze.py`** — parses `session.json` (`conversation[].content[]` items of type `thinking` / `text` / `toolRequest` / `toolResponse`). `toolRequest.toolCall.status == "error"` is the ring-2 signal; `toolResponse.toolResult.value.isError` is the ring-4 signal. Classifies each run into the first failing ring (7 → 6 → 2 → 1 → success → 4 → manual) and prints tool-call format rate, task pass rate with per-task stability, and the ring distribution. Rings 3 and 5 are deliberately left to human review of `session.json`.
- **`evals/tasks.jsonl`** — the only long-lived asset. Each task has `setup.files`, machine-checkable `checks` (`file_exists`, `file_absent`, `file_equals`, `file_contains`, `file_not_contains`, `cmd`, `answer_contains`, `manual`), and a category from single-step / multi-step / impossible / false-premise. Schema and mix rules in `evals/README.md`. Every new task must be auto-gradable.

## Hard rules from the docs

- Change exactly one variable per run and record it in `--tag`.
- Count only the *first* failing ring per run; downstream failures are collateral.
- `runs/` is gitignored (session exports grow fast). Don't un-ignore it.
- Explicitly out of scope right now: writing a custom agent loop, picking a framework, attaching business MCP servers (domain-mcp was removed from this plan on 2026-09-04), DeepSeek Harness (only as a later comparison), and buying hardware before the baseline table exists.
