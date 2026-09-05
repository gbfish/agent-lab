# 06 · Hardware decision (Mac Studio)

> 中文版:[../06-hardware.md](../06-hardware.md)

> **Decided 2026-09-05: not buying.** The baseline plus three controls (144 runs) produced no data point that says "the model is not capable enough":
> qwen3:8b has a 100% tool-call format rate; the 14b's format problem is a quirk of that specific weight and toolshim rescues it; every remaining failure is a prompt / tool-output design problem.
> Data in the 2026-09-05 entry of `notes/findings.md`. The analysis below is kept as a record of how to think before deciding.
>
> Original conclusion: run the baseline in `05-eval-plan.md` first, then decide.
> This machine: M3 Pro, 18 GB unified memory. qwen3:14b only fits with 16k context; 30B-class does not fit.

---

## The new Mac Studio (announced 2026-08-25)

| | M5 Max | M5 Ultra |
|---|---|---|
| Starting price | **$2,499** | $5,499 |
| Memory | 36 GB base, configurable 48 / 64 / **128 GB** | 96 GB base, 256 / **512 GB** |
| Bandwidth | **614 GB/s** | **1.2 TB/s** |
| CPU | 18 cores (6 super + 12 performance) | 36 cores |
| GPU | Up to 40 cores, each with a Neural Accelerator | Up to 80 cores |
| Storage | 512 GB base, up to 8 TB, PCIe Gen 6 | 1 TB base, up to 16 TB |

**Timing:** pre-orders opened 8/25, **ships 9/22**; the 512 GB variant not until late October.

**Other:** Wi-Fi 7, Bluetooth 6, Thunderbolt 5 throughout.

### Performance
- M5 Max AI performance is **3.9×** the previous generation, mostly in prompt processing
- M5 Max bandwidth 614 GB/s vs 546 GB/s on the M4 Max
- M5 Ultra is two dual-die M5 Max chips joined by UltraFusion, over 4.4 TB/s between dies
- M5 Ultra supports Thunderbolt 5 + RDMA clustering with a shared memory pool; **a four-machine cluster infers at about 3× a single machine**

---

## What buying it would change

### ✅ 1. One model tier up; rings 1 and 2 mostly filled in
**This is the most substantive change.**

The current pain is that a 14b model may emit tool calls as bare text and crash the loop, the typical disease of the 7B–14B range. **128 GB runs 70B-class comfortably and, quantised, can touch 100B+. At that size structured tool calling is basically stable.**

Corollary: the Code mode countermeasure may become unnecessary.

### ✅ 2. Prompt processing 3.9× faster, right where RAG hurts
An agent re-feeds the entire history plus tool results (file contents, command output, easily thousands of tokens) every turn, and all of that cost is in the prefill phase, exactly where the M5 improves most. It will show even more once retrieval tools are attached.

### ✅ 3. The on-prem business story holds
Apple's line is "run large models locally with complete privacy, without counting tokens or worrying about rising cloud costs".

For data that must not leave the building, that sentence is the sales pitch. A $2,499 machine in the plant vs a monthly API bill is an easy ROI table.

---

## What it would not change

### ❌ Tool output quality
If the model cannot read the tool's error text and the prompt does not make it self-correct, no model size saves that. **Hardware carries none of ring 4.**

### ❌ Harness choice
Goose stays Goose.

### ❌ Agent architecture
Loop design, permission control, stop conditions are all software.

### ❌ Your differentiation
Hardware lets you run a better model, but **everyone who can afford $2,499 can run it too**. The moat is still the domain documents, the real user phrasing, the eval set.

---

## Recommendation

### Do not buy the M5 Ultra
512 GB is for "run frontier-class models locally". This project's scenario is a 70B-class agent; **the M5 Max 128 GB is fully sufficient, three thousand dollars less.**

The clustering feature sounds cool, but it is for video / VFX / large-scale inference, not for one local agent.

### The decision input = the failure table

| Test result | Decision |
|---|---|
| Tool-call rate ≥ 90% | **Do not buy.** The bottleneck is not the model; fix the software |
| 70–90% | Try Code mode and prompt engineering for free first; buy only if that fails |
| < 70% and rings 1/2 dominate | **Buy the M5 Max 128 GB; the case is solid** |
| Failures concentrated in ring 4 | **Do not buy.** Fix tool output / prompts |

### The timing works
Ships 9/22. Start testing today, results within a week, two weeks left to decide. **There is no reason to skip the test and order.**
