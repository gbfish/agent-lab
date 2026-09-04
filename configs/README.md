# configs

实验里**不用** Goose 的配置文件。所有参数由 `scripts/run_eval.py` 逐次通过命令行传给 `goose run`(`--provider` / `--model` / `--no-profile` / `--with-builtin` / `--max-turns` …),完整命令行记在每次运行的 `record.json` 里。

原因:配置文件是全局状态,会让两次运行之间悄悄多出一个变量。

这个目录只放两样东西:

- `Modelfile.*` —— 带 `num_ctx` 的 Ollama 模型变体定义。上下文长度是本项目最容易被忽略的变量,写进模型名里(`qwen3:8b-32k`)比靠环境变量可靠。
- `goose.yaml`(gitignore 了)—— 如果你 `goose configure` 过,把 `~/.config/goose/config.yaml` 拷一份到这里备查。

```bash
ollama create qwen3:8b-32k  -f configs/Modelfile.qwen3-8b-32k
ollama create qwen3:14b-32k -f configs/Modelfile.qwen3-14b-32k
```
