# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An experiment bench, not a product. Its single purpose is to answer, with data, *where* the chain **local Ollama model → Goose (or DeepSeek Harness) → domain-mcp (read-only HVAC doc retrieval)** breaks. Every conclusion must be traceable to raw trajectories in `runs/`. Docs and code are written in Chinese; keep new docs/notes in Chinese to match.

Read `docs/` in numeric order before changing anything; `docs/04-failure-modes.md` and `docs/05-eval-plan.md` are the core framework the scripts implement.

## Commands

No build step, no test suite, no dependencies beyond Python 3.10+ stdlib (uses `set[str] | None` syntax).

```bash
# One-time setup
cp configs/goose.example.yaml configs/goose.yaml        # fill in absolute path to domain-mcp
cp evals/questions.example.jsonl evals/questions.jsonl  # replace with real technician questions

# Run baseline (writes runs/<YYYY-MM-DD_HHMMSS>/{_meta.json, <qid>_r<n>.json})
python3 scripts/run_eval.py --repeat 3 --tag "what-changed"
python3 scripts/run_eval.py --harness dsh --repeat 3    # DeepSeek Harness instead of Goose
python3 scripts/run_eval.py --only q001,q003             # subset of question ids
python3 scripts/run_eval.py --timeout 300 --outdir runs/custom

# Analyze a run
python3 scripts/analyze.py runs/<dir>/
python3 scripts/analyze.py runs/<dir>/ --verbose         # per-record classification
```

Note: README's quick-start shows `run_eval.py --config configs/goose.yaml`, but the script has no `--config` flag. Goose reads its own config; `configs/goose.yaml` is documentation for reproducibility. Harness invocation is defined in the `HARNESSES` dict at the top of `scripts/run_eval.py` and must be verified against the installed CLI version (`goose --help`) before batch runs.

## Architecture

Two scripts and a data contract between them:

- **`scripts/run_eval.py`** shells out to a harness CLI once per (question × repeat), capturing raw stdout/stderr/returncode/elapsed/timeout into one JSON per run. It deliberately stores raw output, never rendered text. The `{question}` placeholder in `HARNESSES[...]["cmd"]` is substituted per call.
- **`scripts/analyze.py`** reads a run dir and classifies each record into one of the **seven rings** (环 1–7) via regex `PATTERNS` and `TOOL_CALL_SIGNS`, then prints (1) tool-call format correctness rate = share not failing in ring 1 or 2, with ≥90% / 70–90% / <70% decision thresholds, and (2) ring distribution. Rings 3/4/5 cannot be detected by regex and land in the "待人工判断" bucket on purpose. `PATTERNS` and `TOOL_CALL_SIGNS` are expected to be tuned after reading real harness output.
- **`evals/questions.jsonl`** (gitignored) is the only long-lived asset. Schema and the single-hop / multi-hop / unanswerable / false-premise mix are specified in `evals/README.md`. Never invent questions; they must be verbatim technician phrasing.
- **`notes/findings.md`** is the append-only, reverse-chronological log using the template at its top. Every experiment ends by writing a dated entry there and following the decision tree in `docs/05-eval-plan.md`.

## Hard rules from the docs

- Change exactly one variable per run and record it in `--tag`.
- Count only the *first* failing ring per run; downstream failures are collateral.
- `runs/`, `configs/goose.yaml`, `configs/dsh.yaml`, and `evals/questions.jsonl` are gitignored because they can contain factory-internal document fragments, absolute paths, or credentials. Don't un-ignore them.
- Explicitly out of scope right now: writing a custom agent loop, picking a framework, adding write-capable tools to the MCP extension, and buying hardware. Retrieval quality problems (ring 4) belong in the domain-mcp repo, not here.
