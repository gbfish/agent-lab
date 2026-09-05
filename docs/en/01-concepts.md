# 01 · Concepts: what counts as an agent

> 中文版:[../01-concepts.md](../01-concepts.md)

---

## In one sentence

**A plain LLM call is a one-shot question and answer. An agent is a loop.**

```
goal → plan → call a tool → observe the result → re-plan → … → done
```

The difference is **whether it can act**. A chatbot can only "say"; an agent can "do": read files, run commands, query databases, call APIs. The mechanism that lets it act is tool use / function calling, and MCP is the protocol that describes those tools in a standard way.

---

## Four required components

| Component | Role | In this project |
|---|---|---|
| **Model** | The brain that decides | A local model on Ollama |
| **Tools** | Hands that cause side effects | Goose's built-in `developer` extension (shell + file read/write) |
| **Memory / state** | Keeps context across turns | Goose session |
| **Loop control + stop condition** | When to stop, what to do on failure, who approves risky actions | Goose's permission modes |

**The last one is the easiest to overlook and precisely the hardest engineering problem.**

---

## Three common misjudgements

### "I run a local LLM with a WebUI. Is that an agent?"
**No.** That is inference plus an interface.

- Local model = brain
- WebUI = human interface that submits input and renders output
- **Missing: tools, loop, state**

You type → the model generates → done. It never decides "I should check the manual first", and it never thinks another round after seeing a result. **No loop, no agent.**

### "I attached a retrieval tool. Is that an agent?"
**Still no.** If every run is "ask → retrieve once → answer", that is a **RAG pipeline**. The path is hard-coded by you.

### Where the line is
> **After seeing the first retrieval result, can the model decide on its own that the evidence is insufficient and search again with a different query?**
>
> **The decision sits with the model, not your code. That is an agent.**

---

## The line this project has to cross

Not an agent:
```
User says "fix buggy.py" → model emits corrected code → done          [ chat ]
```

An agent:
```
User says "fix buggy.py" → model reads the file → edits → runs it → looks at output
       → wrong, edits again → right, then reports                     [ agent ]
```

The dividing line is task t07 in `evals/tasks.jsonl`: **after editing, does it run the script again to confirm?** Goose already supplies the loop. What we are testing is whether a local model can sustain it.

**This is also where all the trouble comes from.** A multi-turn loop means every turn's tool call can fail, and failure rates compound. That is why the baseline test comes first; see `05-eval-plan.md`.
