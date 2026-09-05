# evals: the only asset in this repo with long-term value

> 中文版:[README.md](README.md)

Code gets rewritten, configs go stale, harnesses get swapped.
**But a task set with automatic grading keeps working under any model and any framework.**

Target 50 tasks; 12 to start (`tasks.jsonl` ships with them).

---

## Iron rule: every task must be auto-gradable

Judging "how good was the answer" by eye does not scale. Every task must be decidable by machine from file contents, command output, or keywords in the reply. If it cannot be decided, do not add it yet.

Tasks from real work (sorting logs, fixing scripts, computing over a table) beat invented ones. Do not write tasks "in the shape the model finds easy".

---

## Format

`tasks.jsonl`, one JSON object per line:

```json
{"id": "t07", "task": "buggy.py prints the wrong result; it should print 10. Fix it, then run it yourself to confirm",
 "setup": {"files": {"buggy.py": "..."}},
 "checks": [{"type": "cmd", "cmd": "python3 buggy.py", "stdout_contains": "10"}],
 "category": "multi-step", "difficulty": "medium", "notes": "read → edit → run → check output"}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | ✅ | Unique identifier |
| `task` | ✅ | The exact text sent to the agent |
| `setup.files` | | Files written into the sandbox working directory before the run, `{"relative/path": "content"}` |
| `checks` | ✅ | Grading rules; all must pass. Types below |
| `category` | | single-step / multi-step / impossible / false-premise |
| `difficulty` | | easy / medium / hard |
| `notes` | | What this task is testing |

### Check types

| type | Fields | Passes when |
|---|---|---|
| `tool_calls_min` | `n` | At least n tool calls were made (stops "did nothing" from passing; required on t11/t12) |
| `file_exists` | `path` | File exists |
| `file_absent` | `path` | File does not exist (stops it inventing one) |
| `file_equals` | `path`, `value` | File content equals value after strip |
| `file_contains` | `path`, `value` | File content contains substring |
| `file_not_contains` | `path`, `value` | File content does not contain substring |
| `cmd` | `cmd`, optional `stdout_contains` | Command run in the working directory exits 0 (and output contains substring) |
| `answer_contains` | `any: [...]` | Final reply contains any of the substrings (case-insensitive) |
| `manual` | `note` | Not auto-gradable; flagged for a human. Does not affect the automatic verdict |

Every run happens in **its own empty directory**; any file not listed in setup does not exist.

---

## Suggested mix

| Type | Share | Why |
|---|---|---|
| Single-step (one tool call finishes it) | 40% | Baseline; tests the most basic chain |
| **Multi-step (must look at a result before deciding)** | **40%** | **Tests the agent loop; this is the focus** |
| Impossible (the thing asked for does not exist) | 10% | Tests whether it invents. Inventing is a serious problem |
| False premise | 10% | Tests whether it complies blindly |

Multi-step share has to be high. A single-step task can be done by a script and reveals nothing about agent value or the compounding failure rate of multi-turn calls.

---

## Annotation discipline

- Make `checks` tight: for the common mistake in t08 (also writing worker.log), have a dedicated `file_not_contains`
- Impossible tasks must carry `file_absent`, or the model passes by creating the file itself
- False-premise tasks must carry `file_equals` with the original content plus `tool_calls_min`: a blind edit fails, and declaring "nothing wrong" without reading the file also fails
