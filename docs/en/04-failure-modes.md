# 04 · The seven rings: a taxonomy of failure

> 中文版:[../04-failure-modes.md](../04-failure-modes.md)

> This is the repo's core diagnostic framework. `scripts/analyze.py` counts by these categories.

Whichever ring breaks, the visible symptom is "the answer is wrong". But **the causes are completely different and so are the fixes.** Without logs you cannot tell them apart.

---

## The seven rings

### Ring 1 · The model never calls a tool
**Symptom:** Makes up an answer from memory; never touches a tool.
**Cause:** Tool descriptions too vague, or the model's tool-calling training is weak.
**Fix:** Better tool descriptions / system prompt / **a different model**.
**This is the most common first hurdle for small local models.**

### Ring 2 · It called, but the format is wrong
**Symptom:** Emits something that looks like JSON but fails to parse; misspelled parameter names; missing required fields; bare text or malformed XML.
**Cause:** Insufficient structured-output capability.
**Fix:** **A larger model**, or Code mode to bypass multi-turn function calling.
**⚠️ This ring compounds:** 95% per turn becomes 77% over 5 consecutive turns (0.95⁵).

**The concrete form measured 2026-09-04 (qwen3:14b + Ollama):** inside `<tool_call>` the model writes JSON whose string arguments contain unescaped quotes, for example
`"before": "print(f\"Hello, {name}!")"`. Ollama fails to parse it and **silently drops the whole call**; Goose receives a message containing only thinking and ends the turn.
It looks like "the model thought for a long time and did nothing", i.e. ring 1; only the token counts reveal 25–60 tokens emitted after `</think>`.
3 of 6 direct samples were invalid JSON. `edit` calls whose arguments contain quotes are the most exposed.

### Ring 3 · Wrong tool, or unreasonable argument values
**Symptom:** Format is fine, but the query is bad. Asked "compressor on model X won't start", it searches for "HVAC".
**Cause:** Reasoning quality, not formatting.
**Fix:** Few-shot examples, better tool descriptions, a different model.

### Ring 4 · The tool errored and the agent did not recover
**Symptom:** The call is perfectly formed, but the command fails, the file does not exist, or the path is wrong, and the model gives up or improvises instead of correcting.
**Cause:** The model cannot read the tool's error text; or the tool's own output (shell / file editor) is unfriendly to small models.
**Fix:** Read the exact text returned in `toolResponse`; change the tool's output format or the prompt. **Not a model problem; a bigger machine does nothing.**
**Note:** if the tool errored, the model corrected itself, and the task passed, that is not a failure. That is exactly what an agent loop is for.

### Ring 5 · Got a good result and did not use it
**Symptom:** The answer is right there in the retrieved result, but the reply ignores it or uses only the first item.
**Cause:** Context too long and diluted; the prompt does not force evidence-based answers.
**Fix:** Context engineering, mandatory citation, less injection per turn.

### Ring 6 · The loop does not converge
**Symptom:** Calls the same tool repeatedly; five rounds of near-identical searches; or jumps to a conclusion with obviously insufficient evidence.
**Cause:** Stop-condition design.
**Fix:** Loop control, a max-turn cap, an explicit "is the evidence sufficient" judgement.

### Ring 7 · Context overflow
**Symptom:** By turn 6 or 7 it has forgotten the original question.
**Cause:** **A local model's effective context is often far below the nominal value.**
**Fix:** Compress history, isolate with subagents, inject less per turn.

---

## Quick map: where failures cluster → what to do

| Cluster | Meaning | Action |
|---|---|---|
| **Rings 1, 2** | Model capability | **Change model** (→ hardware investment makes sense, see `06-hardware.md`) |
| **Ring 3** | Reasoning quality | Try prompt engineering first, then change model |
| **Ring 4** | Tool output / error recovery | Change tool output format or the prompt; **buying a machine is useless** |
| **Rings 5, 7** | Context engineering | Software problem, costs nothing |
| **Ring 6** | Loop design | Software problem, costs nothing |

> **This table is the basis for the buy-a-Mac decision.** See `06-hardware.md`.

---

## How to locate the ring

### The only correct method

Persist **the raw request and raw response** for every turn. Not the rendered UI text, but:
- The full prompt sent to the model (system prompt, tool definitions, history)
- The raw tokens the model returned (including unparsed tool-call text)
- The arguments the tool actually received
- The raw result the tool returned

Then read it from the top. **The turn and field where the first "that's not right" appears is the ring that broke.**

### Key principle

**Count only the first failing ring.** If a run breaks at ring 2, rings 3–7 afterwards are collateral and are not counted separately. Otherwise the statistics are polluted and the real bottleneck is invisible.

### Tool support

| Harness | Capability |
|---|---|
| Goose | `--output-format stream-json` event stream + `goose session export --format json` full conversation. `toolRequest.toolCall.status == "error"` flags ring 2 directly |
| DeepSeek Harness | **Trajectory View**: append-only event stream with resume / fork / search / replay. Not touched before the baseline is done |

**Fork + replay is especially useful:** branch from the turn that broke, change one variable (prompt / model / tool description), and see whether it is fixed. Goose's `goose run --resume --name X` can continue but cannot fork; look at dsh when that capability is genuinely needed.
