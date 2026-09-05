# configs

> 中文版:[README.md](README.md)

The experiments **do not use** Goose's config file. Every parameter is passed to `goose run` on the command line by `scripts/run_eval.py`, one run at a time (`--provider` / `--model` / `--no-profile` / `--with-builtin` / `--max-turns` …), and the full command line is recorded in each run's `record.json`.

Reason: a config file is global state and quietly adds a variable between two runs.

This directory holds only two kinds of thing:

- `Modelfile.*`: Ollama model variants with `num_ctx` baked in. Context length is the most easily overlooked variable in this project; putting it in the model name (`qwen3:8b-32k`) is more reliable than relying on an environment variable.
- `goose.yaml` (gitignored): if you have run `goose configure`, copy `~/.config/goose/config.yaml` here for reference.

```bash
ollama create qwen3:8b-32k  -f configs/Modelfile.qwen3-8b-32k
ollama create qwen3:14b-16k -f configs/Modelfile.qwen3-14b-16k
```

Measured 2026-09-04 (M3 Pro 18 GB): 14b with 32k context needs 15 GB, spills 2 GB to CPU, and generation drops to 0.1 tok/s, unusable. With 16k it is 11.7 GB, entirely on GPU, 13.5 tok/s. **On this machine 14b only works at 16k.**
