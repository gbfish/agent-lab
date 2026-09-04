#!/usr/bin/env python3
"""
analyze.py —— 按「七环」统计失败分布,输出决策依据

用法:
    python3 scripts/analyze.py runs/2026-09-05_143022/
    python3 scripts/analyze.py runs/2026-09-05_143022/ --verbose

输入:run_eval.py 产出的 <rundir>/<tid>_r<n>/{record.json, session.json}
输出:
  1. 工具调用格式正确率  ← 决定买不买 Mac 的关键数字
  2. 任务完成率 + 每题稳定性
  3. 七环失败分布        ← 决定接下来做什么

⚠️ 这个脚本做的是粗分类。
   环 3(选错工具/参数)/ 环 5(结果没用上)机器判断不准 —— 必须手工读 session.json。
   脚本的作用是告诉你「该去读哪几条」,不是替你下结论。

分类依据的是 goose 导出的 session.json,里面每条 assistant 消息的 content 有:
  toolRequest  → toolCall.status ("success" / "error"),error 就是模型吐的调用格式坏了(环 2)
  toolResponse → toolResult.value.isError(工具跑了但报错,环 4 候选)
  thinking / text
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 七环定义 —— 完整说明见 docs/04-failure-modes.md
# ---------------------------------------------------------------------------
RINGS = {
    1: ("不调用工具", "凭记忆编答案 / 只描述该怎么做,压根没动手", "换模型 / 改工具描述"),
    2: ("调用格式错", "裸文本、畸形 XML、参数名错、缺必填字段", "换更大模型"),
    3: ("选错工具或参数", "格式对但选的工具 / 传的参数不合理", "few-shot / 改描述"),
    4: ("工具返回错误", "调用正确但命令报错、文件不存在,且没能恢复", "看工具输出是否可读 / 提示词"),
    5: ("结果没用上", "工具返回了正确信息但回答没用上", "上下文工程 / 强制引用"),
    6: ("循环不收敛", "反复调同一工具 / 超时 / 撞上 max-turns", "终止条件设计"),
    7: ("上下文溢出", "跑到后面忘了最初的问题 / 上下文报错", "压缩历史 / 调大 num_ctx"),
}

# 环 7:上下文相关的报错文本(stderr / stdout / 工具返回里都可能出现)
CONTEXT_PATTERNS = [
    r"context (length|window) exceeded",
    r"too many tokens",
    r"maximum context",
    r"truncat(ed|ing) (history|context)",
    r"exceeds? the (model'?s )?context",
]

# 环 2:模型把工具调用当文本吐出来了(goose 没解析成 toolRequest)
RAW_TOOLCALL_IN_TEXT = [
    r"<tool_call>",
    r"<function[=_ ]",
    r"<invoke ",
    r"\"tool_calls\"\s*:",
    r"^\s*```(json)?\s*\{\s*\"name\"\s*:\s*\"(shell|write|text_editor|str_replace|view)\"",
]


# ---------------------------------------------------------------------------
def walk_session(session: dict | None) -> dict:
    """从 session.json 里抽出诊断需要的结构化信息。"""
    info = {
        "tool_requests": [],   # {name, args, status}
        "tool_errors": 0,      # toolRequest.status == error(格式坏)
        "tool_responses": [],  # {is_error, text}
        "assistant_texts": [],
        "assistant_turns": 0,
    }
    if not session:
        return info
    for m in session.get("conversation") or []:
        role = m.get("role")
        if role == "assistant":
            info["assistant_turns"] += 1
        for part in m.get("content") or []:
            t = part.get("type")
            if t == "toolRequest":
                tc = part.get("toolCall") or {}
                status = tc.get("status")
                val = tc.get("value") or {}
                info["tool_requests"].append({
                    "name": val.get("name"),
                    "args": val.get("arguments"),
                    "status": status,
                })
                if status != "success":
                    info["tool_errors"] += 1
            elif t == "toolResponse":
                tr = part.get("toolResult") or {}
                val = tr.get("value") or {}
                text = " ".join(
                    c.get("text", "") for c in (val.get("content") or []) if isinstance(c, dict)
                )
                info["tool_responses"].append({
                    "is_error": bool(val.get("isError")) or tr.get("status") not in (None, "success"),
                    "text": text,
                })
            elif t == "text" and role == "assistant" and part.get("text"):
                info["assistant_texts"].append(part["text"])
    return info


def classify(record: dict, info: dict, meta: dict) -> tuple[int | None, str]:
    """
    返回 (环号, 理由)。
    环号 None + task_ok=True  → 成功
    环号 None + task_ok=False → 需人工判断(环 3 / 环 5 通常藏在这里)

    ⚠️ 只算第一个失败环 —— 后面的都是连带,不单独计数。
    """
    blob = (record.get("stdout", "") + "\n" + record.get("stderr", "")).lower()
    texts = "\n".join(info["assistant_texts"])
    reqs = info["tool_requests"]

    # 环 7:上下文报错优先(它会伪装成别的环)
    for pat in CONTEXT_PATTERNS:
        if re.search(pat, blob, re.IGNORECASE):
            return 7, f"匹配 /{pat}/"

    # 环 6:超时 / 撞 max-turns / 连续重复调用
    if record.get("timed_out"):
        return 6, "超时"
    max_turns = meta.get("max_turns")
    if max_turns and len(reqs) >= max_turns:
        return 6, f"工具调用 {len(reqs)} 次,撞上 max-turns={max_turns}"
    if len(reqs) >= 3:
        keys = [json.dumps({"n": r["name"], "a": r["args"]}, sort_keys=True) for r in reqs]
        for i in range(len(keys) - 2):
            if keys[i] == keys[i + 1] == keys[i + 2]:
                return 6, f"连续 3 次完全相同的调用 {reqs[i]['name']}"

    # 环 2:goose 解析失败的调用,或调用被当成文本吐出来
    if info["tool_errors"]:
        return 2, f"{info['tool_errors']} 个 toolRequest 状态为 error(格式坏)"
    if not reqs:
        for pat in RAW_TOOLCALL_IN_TEXT:
            if re.search(pat, texts, re.IGNORECASE | re.MULTILINE):
                return 2, f"回答文本里出现裸工具调用 /{pat}/"

    # 环 1:一次工具都没调
    if not reqs:
        return 1, "没有任何 toolRequest"

    # 到这里工具调用格式都对。任务过了就是成功
    if record.get("task_ok"):
        return None, "成功"

    # 环 4:工具调了但全报错,且最终没过
    resps = info["tool_responses"]
    if resps and all(r["is_error"] for r in resps):
        return 4, f"{len(resps)} 次工具调用全部返回错误"

    return None, "工具调过、没报错、但任务没过 → 人工判断环 3 / 环 5"


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir")
    ap.add_argument("--verbose", action="store_true", help="逐条列出分类结果")
    args = ap.parse_args()

    rundir = Path(args.rundir)
    if not rundir.is_dir():
        sys.exit(f"目录不存在: {rundir}")

    meta = {}
    meta_path = rundir / "_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    run_dirs = sorted(d for d in rundir.iterdir() if d.is_dir() and (d / "record.json").exists())
    if not run_dirs:
        sys.exit(f"{rundir} 里没有运行记录")

    ring_counts: Counter[int] = Counter()
    unclear: list[tuple[str, str]] = []
    per_task: dict[str, list[bool]] = defaultdict(list)
    tool_call_ok = 0
    task_ok = 0
    total = 0
    elapsed_sum = 0.0
    tool_calls_sum = 0
    rows = []

    for d in run_dirs:
        record = json.loads((d / "record.json").read_text(encoding="utf-8"))
        session = None
        sp = d / "session.json"
        if sp.exists():
            try:
                session = json.loads(sp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                session = None
        info = walk_session(session)
        ring, reason = classify(record, info, meta)

        total += 1
        elapsed_sum += record.get("elapsed_sec") or 0
        tool_calls_sum += len(info["tool_requests"])
        tid = record.get("task", {}).get("id", d.name)
        per_task[tid].append(bool(record.get("task_ok")))
        if record.get("task_ok"):
            task_ok += 1
        if ring not in (1, 2):
            tool_call_ok += 1
        if ring is not None:
            ring_counts[ring] += 1
        elif not record.get("task_ok"):
            unclear.append((d.name, reason))
        rows.append((d.name, ring, reason, len(info["tool_requests"]), record.get("task_ok")))

    if args.verbose:
        for name, ring, reason, ncalls, ok in rows:
            label = f"环{ring}" if ring else ("OK" if ok else "待人工")
            print(f"  {name:12s} {label:6s} calls={ncalls:<3d} {reason}")
        print()

    # ---------------- 输出 ----------------
    print("=" * 62)
    print(f"运行目录: {rundir}")
    if meta:
        print(f"model: {meta.get('model')}   重复: {meta.get('repeat')}   "
              f"tag: {meta.get('tag') or '(未填)'}")
        ctx = meta.get("ollama_context_length")
        print(f"ollama 上下文: {ctx if ctx else '(未记录)'}   goose: {meta.get('goose_version')}")
    print(f"总运行次数: {total}   平均耗时: {elapsed_sum / total:.0f}s   "
          f"平均工具调用: {tool_calls_sum / total:.1f} 次")
    print("=" * 62)

    rate = tool_call_ok / total * 100 if total else 0.0
    print(f"\n【指标 1】工具调用格式正确率: {rate:.1f}%  ({tool_call_ok}/{total})")
    print("  ↳ 定义:没崩在环 1(不调用)或环 2(格式错)的比例")
    if rate >= 90:
        verdict = "≥90% → 模型够用,瓶颈在别处。别买机器,去修软件问题"
    elif rate >= 70:
        verdict = "70-90% → 边缘。先免费试提示工程 / 减少工具数,不行再考虑硬件"
    else:
        verdict = "<70% → 模型能力不足。如果环 1/2 占多数,硬件投资理由充分"
    print(f"  ↳ 判据:{verdict}")

    trate = task_ok / total * 100 if total else 0.0
    print(f"\n【指标 2】任务完成率: {trate:.1f}%  ({task_ok}/{total})")
    print("  ↳ 每题稳定性(过/跑):")
    for tid in sorted(per_task):
        r = per_task[tid]
        n_ok = sum(r)
        flag = "" if n_ok in (0, len(r)) else "  ← 不稳定,重点读"
        print(f"      {tid}  {n_ok}/{len(r)}{flag}")

    print("\n【指标 3】七环失败分布")
    print("-" * 62)
    if not ring_counts:
        print("  未检出明确失败 —— 要么真的很好,要么全落在「待人工」里。")
    else:
        worst = ring_counts.most_common(1)[0][0]
        peak = max(ring_counts.values())
        for ring in sorted(RINGS):
            n = ring_counts.get(ring, 0)
            name, desc, fix = RINGS[ring]
            bar = "█" * int(n / peak * 24) if n else ""
            mark = " ←" if ring == worst and n else ""
            print(f"  环{ring} {name:12s} {n:3d}  {bar}{mark}")
        print("-" * 62)
        name, desc, fix = RINGS[worst]
        print(f"  主瓶颈:环{worst} · {name}")
        print(f"    症状:{desc}")
        print(f"    修法:{fix}")

    if unclear:
        print(f"\n【待人工判断】{len(unclear)} 条")
        print("  工具调过、没报错、但任务没过 —— 环 3 / 环 5 藏在这里,读 session.json:")
        for name, reason in unclear[:10]:
            print(f"    {rundir / name / 'session.json'}")
        if len(unclear) > 10:
            print(f"    ... 还有 {len(unclear) - 10} 条")

    print("\n下一步:走 docs/05-eval-plan.md 的决策树,结论写进 notes/findings.md")


if __name__ == "__main__":
    main()
