# 03 · Goose 安装与配置

> English version: [en/03-goose-setup.md](en/03-goose-setup.md)

> 项目已从 `block/goose` 迁到 Linux Foundation 的 `aaif-goose/goose`(2026-04)。
> 搜到的旧链接会有一段时间失效,认准新仓库。本文按 **goose 1.49.0** 核对过。

---

## 1. 安装

```bash
brew install block-goose-cli          # Homebrew formula 名还没改
# 或
curl -fsSL https://getgoose.ai/install.sh | bash

goose --version                        # 1.49.0
goose info                             # 看配置 / session 库 / 日志在哪
```

桌面版和 CLI 都有。**用 CLI** —— 我们要看的是日志,GUI 反而挡视线。

---

## 2. 准备 Ollama

### ⚠️ 第一个坑:上下文长度

**Ollama 默认给模型 4096 上下文,而且超了就静默截断。** Goose 的系统提示 + 工具定义本身就两千多 token,再加任务和几轮工具结果就超了。超了之后模型看不到工具定义 —— 表现出来就是「不调用工具」,会被误判成环 1,把整张失败分布表污染掉。

本机 Ollama 是 `/Applications/Ollama.app` 跑的菜单栏程序,改环境变量要重启它。**更干净的办法是建一个带 `num_ctx` 的模型变体**,不动服务端,名字里就写明了上下文:

```bash
printf 'FROM qwen3:8b\nPARAMETER num_ctx 32768\n' > /tmp/Modelfile
ollama create qwen3:8b-32k -f /tmp/Modelfile
```

验证(跑过一次之后看实际加载的上下文):
```bash
curl -s localhost:11434/api/ps | python3 -c 'import sys,json;[print(m["name"],m["context_length"]) for m in json.load(sys.stdin)["models"]]'
```

`run_eval.py` 第一次运行后会自动查这个,低于 16384 直接退出。

### 选模型:本机是 M3 Pro 18GB

| 模型 | 能不能跑 | 社区反馈的工具调用表现 |
|---|---|---|
| `qwen3:8b`(已装,Q4_K_M 5.2GB) | 快 | 5 个以内工具基本稳;本仓库冒烟 3/3 通过 |
| `qwen3:14b`(Q4 9.3GB) | 能,**上下文只能给 16k**(32k 会溢到 CPU,0.1 tok/s) | 单卡消费级机器的常规推荐;本仓库 t07 一次通过,240s |
| `qwen3:30b-a3b` | **塞不下** | — |

> 7B–14B 区间最常被报告的问题是把 tool call 当成裸文本或畸形 XML 吐出来。
> Qwen3 在这方面是社区里最稳的一档。**但必须实测,不能假设。**

```bash
ollama pull qwen3:14b
ollama create qwen3:14b-16k -f configs/Modelfile.qwen3-14b-16k   # 16k,不是 32k,见 configs/README.md
```

验证放置:`/api/ps` 里 `size_vram` 必须等于 `size`,否则就是溢到 CPU 了,速度会掉一百倍。

---

## 3. 不需要 `goose configure`

实验里所有参数都由 `run_eval.py` 逐次通过命令行传给 `goose run`:

```bash
goose run \
  --provider ollama --model qwen3:8b-32k \
  --no-profile \                       # 不加载你的默认 extension,只用下面指定的
  --with-builtin developer \           # shell + 文件读写
  --output-format stream-json \        # 事件流,机器可读
  --max-turns 20 \                     # 环 6 保险
  --max-tool-repetitions 3 \           # 连续相同调用上限,环 6 保险
  --name <session-name> \
  -t "任务原话"
```

不用配置文件的原因:**配置文件是全局状态,会让两次运行之间悄悄多出一个变量。** 每次运行的完整命令行都记在 `record.json` 里,可复现。

想交互式玩的时候再 `goose configure`(遥测那一项选否)。

---

## 4. 冒烟测试

```bash
mkdir -p /tmp/goose-smoke && cd /tmp/goose-smoke
goose run --provider ollama --model qwen3:8b-32k --no-profile \
  --with-builtin developer --no-session \
  -t "在当前目录创建 hello.txt,内容写 hello"
ls
```

**判据:它是「说」还是「做」。** 目录里出现 `hello.txt` 才算接通。只输出一段代码让你自己跑 = 工具没接通。

2026-09-04 本机实测:`qwen3:8b` 35 秒完成,1 次 `write` 调用。

---

## 5. 拿 trajectory

两个来源,`run_eval.py` 都存:

| 来源 | 内容 | 用途 |
|---|---|---|
| stdout(`--output-format stream-json`) | 逐 token 事件流,`thinking` / `text` / `toolRequest` / `toolResponse`,最后一条 `complete` 带 token 数 | 看时序、看它卡在哪 |
| `goose session export --name <n> --format json` | 干净的完整对话 `conversation[]`,同样的四种 content,外加 usage / model_config | **分析用这个** |

`toolRequest.toolCall.status` 是 `"error"` 就说明模型吐的调用 goose 没解析动 —— 这是环 2 最直接的证据。

---

## 6. 常用命令

```bash
goose session list                         # 列出所有会话
goose session export --name X --format json -o X.json
goose session remove                       # 交互式删。1.49 的 --name / -r 非交互删有 bug("not connected")
goose info -v                              # 看当前生效的配置和 extension
```

---

## 7. 排错

| 症状 | 检查 |
|---|---|
| 模型不调工具 | **先查上下文**(`/api/ps` 的 `context_length`)。再看工具描述、模型能力 → `04-failure-modes.md` 环 1 |
| 输出里有 `<tool_call>` 之类裸文本 | 环 2,模型格式能力不够 |
| 连不上 Ollama | `curl localhost:11434/api/tags` 通不通 |
| 跑到中途忘了目标 | 上下文溢出 → 环 7 |
| `goose run` 慢 | 14b 在这台机器上一次多步任务 2–5 分钟正常,`--timeout` 给足 |

**遇到任何问题,先看 session.json,不要看界面渲染后的文字。**
