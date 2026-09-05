# 02 · The open-source agent landscape and our pick

> 中文版:[../02-landscape.md](../02-landscape.md)

> Source: GitHub star snapshot taken 2026-08-29. This field moves fast; re-check anything older than three months.

---

## Overview

| Project | Stars | Language / form | Positioning | MCP | Local models |
|---|---|---|---|---|---|
| DeepSeek Harness | ~203k | Node/TS CLI | Everything is a plugin, developer preview | ✅ | ✅ |
| OpenCode | ~202k | TS terminal UI | Provider-agnostic, MCP + LSP | ✅ | ✅ 75+ |
| Codex CLI | ~119k | CLI | OpenAI official, sandboxed | ✅ | ⚠️ |
| Pi | ~98k | CLI | Lean on tokens, easy to modify | ✅ | ✅ |
| **OpenHands** | ~85k | Python/Docker | Autonomous execution + sandbox isolation | ✅ | ✅ LiteLLM 100+ |
| Cline | ~67k | VS Code + CLI | Plan/Act split, approve every step | ✅ | ✅ |
| **Goose** | ~54k | **Rust** desktop + CLI + API | **General-purpose agent, not coding-only** | ✅ 70+ | ✅ |
| Aider | ~48k | Python CLI | Git-native pair programming | ❌ | ✅ |
| CodeWhale | ~41k | Rust | Harness evolved from DeepSeek-TUI | ✅ | ✅ |

---

## Four dimensions that matter

### 1. Coding agent vs general agent
Almost everything in the table assumes your subject is a git repository. **Only Goose explicitly positions itself as general**: research, automation, data analysis, and coding side by side.

We want to test "can a local model sustain a real tool loop" without being tied to coding-IDE assumptions. That alone narrows the field to Goose and OpenHands.

### 2. Autonomy and sandboxing (= trust tiers)
- **OpenHands** is the most aggressive: runs whole tasks unattended inside a Docker sandbox.
- **Cline** is the most conservative: every file edit and terminal command needs explicit approval; the most complete audit trail.

This is the Suggest / Draft / Automate trust ladder implemented as products. **For an internal enterprise tool, start at the most conservative tier** and move up as trust is earned.

### 3. Offline friendliness
Goose works offline once Ollama is configured. Cline and OpenHands support local models but are more work to set up offline-first.

For on-prem / data-never-leaves-the-building scenarios this weighs heavily.

### 4. Vendor neutrality
Goose has moved to the Linux Foundation's Agentic AI Foundation (AAIF), Apache 2.0, tied to no model vendor. Codex CLI and DeepSeek Harness are open source but tuned for their own models.

**Pick a neutral foundation for a product base.**

---

## Decision: Goose

Verified 2026-09-04: the repo is `aaif-goose/goose`, Apache 2.0, ~54k stars, v1.49.0 released 9/3, Ollama is a first-class provider. All five criteria met:
1. Written in Rust: low barrier to reading the source or forking
2. MCP-native: the built-in developer extension works out of the box; business MCP servers plug in later
3. General-purpose rather than coding-only: fits knowledge-work scenarios
4. Works offline with Ollama: fits on-prem
5. Foundation-hosted and vendor-neutral: safe to bet on long term

---

## DeepSeek Harness: not a foundation, a debugging bench

Open-sourced three weeks ago, Node.js/TS, MIT. The core idea is **everything is a plugin**: models, tools, skills, sessions, sandboxes, storage, the loop, scheduling, UI. Driven by Cordis underneath. `npx @deepseek-ai/dsh web`, port 3080.

### Two features especially useful for this repo

**Trajectory View**
Everything the model sees goes into an append-only event stream; resume / fork / search / replay all operate on that one stream.

→ This is a ready-made implementation of "persist every raw request and response". **Fork + replay means you can branch from a given turn, change a prompt, and see how the outcome changes.** Most other harnesses cannot do this.

**Code mode**
One of four preset modes. It changes how tools reach the model: instead of exposing each tool as a function call, it **generates a TypeScript SDK and lets the model write a program that calls them**. A five-round call sequence becomes one round.

→ Aimed directly at this repo's core risk: cumulative multi-turn failure drops from `0.95^N` back toward `0.95`. **If the baseline is bad, this is the first countermeasure to try. Do not touch it before the baseline is done.**

(The other two modes: Standard with the full toolset; Minimal with only bash + str_replace_editor, meant for benchmarking raw model capability.)

### Why not as a foundation
- Developer preview; the README warns in capitals about breaking changes
- **Does not accept external PRs**; only Discussions and plugin-style contributions. Official positioning is "an idea, a showcase, a source of inspiration", not a spec
- Native DeepSeek routing; Ollama is "works but not the main path"

---

## Explicitly not chosen

**OpenCode**: high star count, but its strength is terminal coding workflows and the LSP value only pays off when editing code.

**LangGraph and other frameworks**: not now. What is missing is not a framework but the feel of having run a real agent loop end to end.

The full argument about frameworks is in the next section.

---

## On "the end goal is a framework, I want full control"

That claim needs correcting. Three points:

**1. A framework is someone else's abstraction too.** LangGraph gives you "a graph mental model": state shape, edges, reducers all have to be done its way. You trade verbosity for control, and beginners routinely over-design state before they need it. Real full control is not a framework; it is writing the 150-line while loop yourself.

**2. The loop is not the hard part.** See `00-glossary.md`. The control you want is 150 lines away; what you will lack is crash recovery, audit, observability, and those are the most expensive to write yourself.

**3. Differentiation is not at this layer.** The agent loop is a public good the whole world has. Writing a better one only re-implements what others have open-sourced.

> **Own: tool design, retrieval quality, the eval dataset, domain knowledge, the permission model.**
> **Rent: the loop, the state machine, crash recovery, tracing.**

### When to go down a layer
1. **The harness is in the way**: something you need is impossible and it is not a configuration issue. Pushed by requirements, not by "I want control".
2. **Learning**: spend a weekend hand-writing the 150 lines. Huge payoff. But **treat it as learning, not as a foundation.**
3. **Research**: the agentic-OS line of work is a new abstraction layer by definition and has to be written. But that is research, a separate track from product.

**Route: get Goose working → hand-write 150 lines to understand the mechanism → pick a framework only when stuck.**
