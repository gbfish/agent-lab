# evals —— 本仓库唯一有长期价值的资产

代码会被重写,配置会过时,harness 会换。
**但一份带自动判分的任务集,换任何模型任何框架都还能用。**

目标 50 条,12 条起步(`tasks.jsonl` 已带)。

---

## 铁律:任务必须能自动判分

「答得好不好」靠人看是不可持续的。每条任务都要能用文件内容、命令输出或回答里的关键字机器判定过没过。判不了的先别加。

真实工作里的任务(整理日志、改脚本、算表格)比人造题好。不要把题写成「模型容易答对的样子」。

---

## 格式

`tasks.jsonl`,一行一条 JSON:

```json
{"id": "t07", "task": "buggy.py 运行结果不对,应该打印 10。把它修好,修完自己跑一遍确认",
 "setup": {"files": {"buggy.py": "..."}},
 "checks": [{"type": "cmd", "cmd": "python3 buggy.py", "stdout_contains": "10"}],
 "category": "multi-step", "difficulty": "medium", "notes": "读 → 改 → 跑 → 看输出"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 唯一标识 |
| `task` | ✅ | 发给 agent 的原话 |
| `setup.files` | | 运行前写进沙箱工作目录的文件,`{"相对路径": "内容"}` |
| `checks` | ✅ | 判分规则,全部通过才算过。类型见下 |
| `category` | | single-step / multi-step / impossible / false-premise |
| `difficulty` | | easy / medium / hard |
| `notes` | | 这条在测什么 |

### checks 类型

| type | 字段 | 判定 |
|---|---|---|
| `tool_calls_min` | `n` | 至少调用了 n 次工具(防止「什么都没做」也算过,t11/t12 必配) |
| `file_exists` | `path` | 文件存在 |
| `file_absent` | `path` | 文件不存在(防止它编一个出来) |
| `file_equals` | `path`, `value` | 文件内容 strip 后完全相等 |
| `file_contains` | `path`, `value` | 文件内容包含子串 |
| `file_not_contains` | `path`, `value` | 文件内容不包含子串 |
| `cmd` | `cmd`, 可选 `stdout_contains` | 在工作目录跑命令,退出码 0(且输出含子串) |
| `answer_contains` | `any: [...]` | 最终回答包含任一子串(不分大小写) |
| `manual` | `note` | 自动判不了,标记给人看。不影响自动通过与否 |

每次运行都在**独立的空目录**里跑,setup 里没写的文件就不存在。

---

## 配比建议

| 类型 | 占比 | 为什么 |
|---|---|---|
| 单步(一次工具调用能完成) | 40% | 基线,测最基本的链路 |
| **多步(需要看结果再决定)** | **40%** | **测 agent 循环,这是重点** |
| 无解(要的东西不存在) | 10% | 测它会不会编。会编就是大问题 |
| 前提错误 | 10% | 测它会不会盲从 |

多步题占比要高 —— 单步题一个脚本就能做,测不出 agent 的价值,也测不出多轮调用的累积失败率。

---

## 标注纪律

- `checks` 要卡到位:t08 那种「把 worker.log 也写进去」的常见错法要有专门的 `file_not_contains`
- 无解题必须配 `file_absent`,否则它自己建个文件就过了
- 前提错误题必须配 `file_equals` 原内容 + `tool_calls_min`,盲改算失败,没看文件就说没问题也算失败
