# 03 · Installing and configuring Goose

> 中文版:[../03-goose-setup.md](../03-goose-setup.md)

> The project moved from `block/goose` to the Linux Foundation's `aaif-goose/goose` (2026-04).
> Old links will be broken for a while; use the new repo. This page was verified against **goose 1.49.0**.

---

## 1. Install

```bash
brew install block-goose-cli          # the Homebrew formula has not been renamed yet
# or
curl -fsSL https://getgoose.ai/install.sh | bash

goose --version                        # 1.49.0
goose info                             # where config / session DB / logs live
```

There is a desktop app and a CLI. **Use the CLI.** We want to read logs; a GUI gets in the way.

---

## 2. Prepare Ollama

### ⚠️ The first trap: context length

**Ollama gives models a 4096-token context by default and truncates silently past it.** Goose's system prompt plus tool definitions alone are over two thousand tokens; add the task and a few rounds of tool results and you are over. Once over, the model cannot see the tool definitions. It looks like "the model never calls tools", gets misclassified as ring 1, and contaminates the whole failure table.

On this machine Ollama is the menu-bar app at `/Applications/Ollama.app`; changing its environment means restarting it. **The cleaner approach is a model variant with `num_ctx` baked in.** It leaves the server alone and the context size is right there in the name:

```bash
printf 'FROM qwen3:8b\nPARAMETER num_ctx 32768\n' > /tmp/Modelfile
ollama create qwen3:8b-32k -f /tmp/Modelfile
```

Verify (after one run, check the context actually loaded):
```bash
curl -s localhost:11434/api/ps | python3 -c 'import sys,json;[print(m["name"],m["context_length"]) for m in json.load(sys.stdin)["models"]]'
```

`run_eval.py` checks this automatically after the first run and aborts below 16384.

### Choosing a model: this machine is an M3 Pro with 18 GB

| Model | Fits? | Community reports on tool calling |
|---|---|---|
| `qwen3:8b` (installed, Q4_K_M 5.2 GB) | Fast | Stable with 5 or fewer tools; this repo's smoke test 3/3 |
| `qwen3:14b` (Q4 9.3 GB) | Yes, **but only with 16k context** (32k spills to CPU, 0.1 tok/s) | The usual recommendation for one consumer machine; t07 passed first try here in 240 s |
| `qwen3:30b-a3b` | **Does not fit** | — |

> The most-reported problem in the 7B–14B range is emitting tool calls as bare text or malformed XML.
> Qwen3 is among the most stable in the community on this. **But it must be measured, not assumed.**

```bash
ollama pull qwen3:14b
ollama create qwen3:14b-16k -f configs/Modelfile.qwen3-14b-16k   # 16k, not 32k; see configs/README.md
```

Verify placement: in `/api/ps`, `size_vram` must equal `size`. Otherwise it has spilled to CPU and speed drops a hundredfold.

---

## 3. `goose configure` is not needed

Every parameter is passed on the command line by `run_eval.py`, one run at a time:

```bash
goose run \
  --provider ollama --model qwen3:8b-32k \
  --no-profile \                       # do not load your default extensions; only what follows
  --with-builtin developer \           # shell + file read/write
  --output-format stream-json \        # machine-readable event stream
  --max-turns 20 \                     # ring 6 guard
  --max-tool-repetitions 3 \           # cap on consecutive identical calls, ring 6 guard
  --name <session-name> \
  -t "the task, verbatim"
```

Why no config file: **a config file is global state, and it quietly adds a variable between two runs.** The full command line of every run is stored in `record.json`, so it is reproducible.

Run `goose configure` only when you want to play interactively (say no to telemetry).

---

## 4. Smoke test

```bash
mkdir -p /tmp/goose-smoke && cd /tmp/goose-smoke
goose run --provider ollama --model qwen3:8b-32k --no-profile \
  --with-builtin developer --no-session \
  -t "Create hello.txt in the current directory containing hello"
ls
```

**The test: does it "say" or "do"?** Only if `hello.txt` appears is the chain connected. If it prints code and tells you to run it yourself, the tools are not wired up.

Measured here 2026-09-04: `qwen3:8b` finished in 35 s with one `write` call.

---

## 5. Getting the trajectory

Two sources; `run_eval.py` stores both:

| Source | Content | Use |
|---|---|---|
| stdout (`--output-format stream-json`) | Token-by-token events: `thinking` / `text` / `toolRequest` / `toolResponse`, ending with a `complete` event carrying token counts | Timing; where it stalled |
| `goose session export --name <n> --format json` | Clean full conversation `conversation[]` with the same four content types, plus usage / model_config | **Use this for analysis** |

`toolRequest.toolCall.status == "error"` means Goose could not parse the call the model emitted. That is the most direct evidence of ring 2.

---

## 6. Everyday commands

```bash
goose session list                         # list sessions
goose session export --name X --format json -o X.json
goose session remove                       # interactive delete. In 1.49, --name / -r non-interactive delete is broken ("not connected")
goose info -v                              # effective config and extensions
```

---

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| Model does not call tools | **Check context first** (`context_length` in `/api/ps`). Then tool descriptions and model capability → `04-failure-modes.md` ring 1 |
| Bare `<tool_call>` text in the output | Ring 2, the model's formatting is not good enough |
| Cannot reach Ollama | Does `curl localhost:11434/api/tags` respond |
| Forgets the goal mid-run | Context overflow → ring 7 |
| `goose run` is slow | 14b on this machine takes 2–5 minutes per multi-step task; give `--timeout` room |

**Whatever the problem, read session.json first, never the rendered UI text.**
