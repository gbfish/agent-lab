# 03 · Goose 安装与配置

> ⚠️ 项目已从 `block/goose` 迁到 Linux Foundation 的 `aaif-goose/goose`。
> 搜到的旧链接会有一段时间失效,认准新仓库。文档站也在迁移中。

---

## 1. 安装

```bash
# macOS / Linux
curl -fsSL https://getgoose.ai/install.sh | bash

# Windows PowerShell
irm https://getgoose.ai/install.ps1 | iex
```

桌面版和 CLI 都有,全平台。**建议 CLI 起步** —— 我们要看的是日志,GUI 反而挡视线。

---

## 2. 准备 Ollama

先确保 Ollama 在跑:

```bash
ollama serve            # 通常已经作为服务在跑
ollama list             # 看已有模型
ollama pull <model>     # 拉一个 tool calling 强的
```

### ⚠️ 选模型:这里有个大坑

> **7B–14B 这个区间的本地模型,最常被报告的问题是把 tool call 当成裸文本或畸形 XML 吐出来,而不是正确的结构化调用。这会直接让 agent 循环崩掉——不是「答得差一点」,是根本转不动。**

所以:

- ❌ 不要挑「能塞进显存的最小的」
- ✅ 挑硬件能跑的、偏 coder 方向的、尽量大的
- ✅ 装完第一件事就是测这个,别等跑业务逻辑再发现

Qwen3:14b 正好卡在风险区间的上沿——**必须实测,不能假设**。测法见 `05-eval-plan.md`。

---

## 3. 配置

```bash
goose configure
```

交互式向导依次问:

| 步骤 | 选什么 |
|---|---|
| 1. 遥测数据上报 | **否**(厂内数据,别开) |
| 2. Provider | **Ollama (Local open source models)** |
| 3. Host | 默认 `localhost:11434`,是 Ollama 标准地址。除非跑在别的机器上,不用改 |
| 4. Model | 填你 `ollama list` 里的模型名 |
| 5. Extensions | 先跳过,下一步单独配 |

向导会自动发一个测试调用验证配置通不通。

### 验证

```bash
goose session
# 随便说句话,看它能不能真的执行代码而不只是描述代码
```

**判据:它是「说」还是「做」。** 如果只是输出一段代码告诉你自己去跑,那工具没接通。

### 重新配置

```bash
goose configure    # 再跑一次,可切 provider/模型、增删 extension、改偏好
```

---

## 4. 挂上 domain-mcp

配置模板见 `configs/goose.example.yaml`。核心部分:

```yaml
extensions:
  - type: stdio
    name: domain-docs
    cmd: node
    args:
      - /absolute/path/to/domain-mcp/dist/server.js
    timeout: 300
    description: "HVAC 技术文档检索"
    available_tools:
      - search_hvac_docs        # ← 只暴露这一个
```

### 三个要点

**`available_tools` 是最简单有效的权限控制。**
调试阶段只放检索工具,确认稳定了再放写操作。这比在提示词里写「不要修改文件」可靠一万倍——提示词是建议,这是物理隔离。

**`timeout` 给足。**
检索 + 重排序可能慢,默认值容易误杀。300 秒起步,稳定后再调紧。

**路径必须是绝对路径。**
`stdio` 型 extension 是 Goose 直接 spawn 的子进程,工作目录不一定是你想的那个。

---

## 5. 常用命令

```bash
goose session                              # 开一个交互会话
goose session start --working-dir /path    # 指定工作目录
goose session list                         # 列出所有会话
goose session resume <session-id>          # 恢复上次的
goose configure                            # 改配置
```

调试时加 verbose/debug 标志导出完整 trajectory —— 具体标志名以 `goose --help` 为准,版本间有变化。

---

## 6. Recipe(跑通之后再做)

Recipe 是 YAML,打包指令 + 扩展 + 参数,把一次性会话变成可重复流程。

**别手写。** 正常跑一个 session,结果满意了点 "Create Recipe",Goose 自己分析对话、提取意图和用到的扩展、预填表单。

对本项目的用法:「诊断某型号压缩机故障」这类技师高频任务,调好一次存成 recipe,以后一键复用。也是以后产品化时的雏形。

Recipe 可以从当前目录、`GOOSE_RECIPE_PATH` 环境变量指定的目录,或 GitHub 仓库(需要 `gh` 已认证)加载。

---

## 7. 排错

| 症状 | 检查 |
|---|---|
| Extension 起不来 | 命令在 PATH 里吗?路径是绝对的吗?手动跑一遍那条 cmd |
| 模型不调工具 | 工具描述太模糊?或者模型 tool calling 能力不够 → 见 `04-failure-modes.md` 第 1 环 |
| 连不上 Ollama | `curl localhost:11434/api/tags` 通不通 |
| 跑到中途忘了目标 | 上下文溢出 → 第 7 环 |

**遇到任何问题,先看 trajectory,不要看界面渲染后的文字。**
