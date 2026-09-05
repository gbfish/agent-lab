# 00 · Glossary

> 中文版:[../00-glossary.md](../00-glossary.md)

Build the vocabulary first. These words are everywhere in every harness's documentation.

---

## Core concepts

### Agent
**A loop**, not a single question-and-answer.

```
goal → plan → call a tool → observe the result → re-plan → … → done
```

What separates it from a chatbot is that it acts on its own: writes code, runs commands, touches files. There is exactly one test: **does the model hold the decision, or does your hard-coded code?** If the path is fixed by you (ask → retrieve once → answer), that is a pipeline, not an agent.

### Tool calling / function calling
The mechanism that lets the model act. You give it each tool's name, description, and parameter schema; the model emits a structured call request; the harness executes it and pushes the result back into context.

**This is the core metric this repo measures.** The classic small-model failure is emitting the call as bare text or malformed XML, which crashes the loop outright.

### MCP (Model Context Protocol)
An open protocol for describing tools in a standard way. Write an MCP server once and any MCP-capable harness can use it. Every Goose extension is an MCP server underneath, including the built-in `developer`.

### Context
Everything sent to the model on each call: system prompt + message history + tool definitions + tool results. It has a length cap, and **the effective context of local models is often far below the advertised number**. A nominal 128k does not mean the 100,000th token is still useful.

### Context engineering
Deciding what goes into context, what stays out, and how to compress. When an agent forgets the original question by turn 6 or 7, this is almost always what went wrong.

---

## Layers: harness / framework / your application

| Layer | Do you write code? | Examples |
|---|---|---|
| **Model** | No | Qwen3, DeepSeek-V4 |
| **Harness / runtime** | No, you configure it | Goose, OpenHands, dsh, OpenCode |
| **Framework** | Yes, you call its API | LangGraph, CrewAI |
| **Your application** | Yes | The task set + grading rules + future business tools |

### Harness
Two origins: the test harness in software testing (mount the component, feed inputs, collect outputs) and the evaluation harness in ML (lm-evaluation-harness). Literally, a horse's harness: **the model is the horse, the harness is the set of straps that lets it actually pull something.**

Model vendors like the word because to them the product is the model and the harness is the test rig. Goose and Cline call themselves agents or runtimes because to them the product is the tool and the model is a swappable part. Same thing, depending on which half you treat as the variable.

### Framework
A library you write code against. What it gives you is not "control" but "a mental model".

**Remember: a harness you run, a framework you write.**

### ⚠️ A counter-intuitive fact
The agent loop itself is short: **a while loop + tool execution + a message array, about 150 lines.** So what a framework sells is not the loop but everything around it: crash recovery (resume from step 7 instead of from zero), durable state, time-travel debugging, human-approval primitives.

**The "full control" you want is 150 lines away. What you will actually lack is recovery, audit, and observability, which are exactly the most expensive parts to write yourself.**

---

## Goose-specific terms

### Provider
The abstraction for "where the model comes from". 30+ supported, including Ollama (local). You can switch between sessions without reconfiguring: sensitive data stays local, public material goes to the cloud.

### Extension
Goose's word for "tool". An MCP server underneath.

> **The single most important sentence: which extensions you add defines what this agent can and cannot do in your environment.**
> Permission boundaries are set by adding and removing extensions, not by prompts. A prompt is a suggestion; an extension is physical isolation.

Types:
| type | Meaning |
|---|---|
| `stdio` | External process on stdin/stdout (use this for business MCP servers later) |
| `builtin` | Ships with Goose (**`developer` is one; this repo uses only that**) |
| `platform` | Runs inside the agent process |
| `streamable_http` | Remote MCP over an HTTP endpoint |
| `inline_python` | Embedded Python run through uvx |

`available_tools` restricts which tools an extension exposes; `goose run --no-profile` loads no default extensions at all. **The simplest effective permission control there is.**

### Session
The full context of one task. Can be listed, resumed (`goose session resume <id>`), and pinned to a working directory.

### Recipe
A YAML file bundling an entire workflow: instructions + which extensions + which parameters the user supplies. **Turns a one-off session into a repeatable, shareable process.**

The practical way to make one is not to write it by hand: run a session, and when it works click "Create Recipe". Goose analyses the conversation, extracts intent and parameters, and pre-fills the form.

### Subagent
A child executor spawned by the main agent with its own context. Used to isolate long tasks so the main context does not blow up.

### Scheduler
Runs tasks on a timer.

### Memory
Long-term context across sessions.

---

## Other words you will meet

### Trajectory
The complete record of **everything** the model saw during a task: system prompt, reasoning, every tool call and result, every context injection. DeepSeek Harness made it a product feature (Trajectory View) with resume / fork / search / replay.

**To locate a failure you must read the trajectory, never the rendered UI text.**

### Prefill / prompt processing
The phase where the model reads the context in, as opposed to the token-by-token decode phase. RAG stuffs thousands of tokens per turn, and all of that cost lands here, so prefill speed matters a lot for RAG workloads.

### Eval
A set of test cases with known answers. **Without an eval you cannot prove a change made the system better or worse.** This is one of the biggest differences between AI engineering and ordinary backend work.

### Prompt injection
Instructions hidden inside external content that the model executes as commands. A real attack surface for agents, because agents read documents, web pages, and email, all of which are untrusted input.

### Hybrid routing
Simple tasks go to the local model, hard reasoning goes to a cloud API. The standard move when a local model trails top cloud models on difficult tasks.
