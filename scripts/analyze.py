#!/usr/bin/env python3
"""
analyze.py —— 按「七环」统计失败分布,输出决策依据

用法:
    python3 scripts/analyze.py runs/2026-09-05_143022/

输出:
  1. 工具调用格式正确率  ← 决定买不买 Mac 的关键数字
  2. 七环失败分布        ← 决定接下来做什么

⚠️ 这个脚本做的是粗分类。
   环 3(选错参数)/ 环 4(检索结果差)/ 环 5(没用上结果)
   机器判断不准 —— 必须手工读 trajectory。
   脚本的作用是告诉你「该去读哪几条」,不是替你下结论。

⚠️ 下面的 PATTERNS 需要按你实际 harness 的输出格式调整。
   先手工读 2-3 条 runs/*.json,看看真实输出长什么样,再改这里。
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# 七环定义 —— 完整说明见 docs/04-failure-modes.md
# ---------------------------------------------------------------------------
RINGS = {
    1: ("不调用工具", "凭记忆编答案,压根没碰检索", "换模型 / 改工具描述"),
    2: ("调用格式错", "裸文本、畸形 XML、参数名错、缺必填字段", "换更大模型 / Code mode"),
    3: ("选错工具或参数", "格式对但检索词很糟", "few-shot / 改描述"),
    4: ("工具返回垃圾", "调用正确但 chunk 不相关", "改 RAG,买机器无用"),
    5: ("结果没用上", "证据在上下文里但答案没用", "上下文工程 / 强制引用"),
    6: ("循环不收敛", "反复调同一工具 / 超时 / 早停", "终止条件设计"),
    7: ("上下文溢出", "跑到后面忘了最初的问题", "压缩历史 / subagent"),
}

# ---------------------------------------------------------------------------
# 粗分类规则 —— 按实际输出格式调整
# ---------------------------------------------------------------------------
PATTERNS = {
    # 环 2:模型想调工具但格式坏了
    2: [
        r"failed to parse",
        r"invalid tool call",
        r"malformed",
        r"JSONDecodeError",
        r"unexpected token",
        r"schema validation",
        r"missing required (parameter|field|argument)",
        r"unknown (tool|function)",
    ],
    # 环 4:工具被正确调用但报错或返回空
    4: [
        r"tool (call )?(returned|error)",
        r"no results found",
        r"empty result",
        r"0 documents",
    ],
    # 环 6:循环问题
    6: [
        r"max (iterations|turns|steps) (reached|exceeded)",
        r"loop limit",
    ],
    # 环 7:上下文
    7: [
        r"context (length|window) exceeded",
        r"too many tokens",
        r"maximum context",
        r"truncat(ed|ing) (history|context)",
    ],
}

# 「模型确实发起了工具调用」的迹象 —— 用来区分环 1 和其他
TOOL_CALL_SIGNS = [
    r"tool_call",
    r"tool_use",
    r"function_call",
    r"calling tool",
    r"search_hvac_docs",
    r"domain-docs",
    r"invoking",
]


def classify(record: dict) -> tuple[int | None, str]:
    """
    返回 (环号, 理由)。环号为 None 表示这次运行没检出明显失败,
    需要人工判断答案质量(环 3 / 环 5 通常藏在这里)。

    ⚠️ 只算第一个失败环 —— 后面的都是连带,不单独计数。
    """
    blob = (record.get("stdout", "") + "\n" + record.get("stderr", "")).lower()

    # 超时优先归环 6
    if record.get("timed_out"):
        return 6, "超时"

    # 按环号顺序检查,取第一个命中的
    for ring in sorted(PATTERNS):
        for pat in PATTERNS[ring]:
            if re.search(pat, blob, re.IGNORECASE):
                return ring, f"匹配 /{pat}/"

    # 没有工具调用迹象 → 环 1
    if not any(re.search(p, blob, re.IGNORECASE) for p in TOOL_CALL_SIGNS):
        return 1, "输出里没有任何工具调用迹象"

    # 非零退出但没匹配到具体模式
    rc = record.get("returncode")
    if rc not in (0, None):
        return None, f"非零退出 rc={rc},需人工判断"

    return None, "未检出明显失败,需人工判断答案质量"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir")
    ap.add_argument("--verbose", action="store_true", help="逐条列出分类结果")
    args = ap.parse_args()

    rundir = Path(args.rundir)
    if not rundir.is_dir():
        sys.exit(f"目录不存在: {rundir}")

    files = sorted(f for f in rundir.glob("*.json") if not f.name.startswith("_"))
    if not files:
        sys.exit(f"{rundir} 里没有运行记录")

    meta = {}
    meta_path = rundir / "_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    ring_counts: Counter[int] = Counter()
    unclear: list[tuple[str, str]] = []
    tool_call_ok = 0
    total = 0

    for f in files:
        record = json.loads(f.read_text(encoding="utf-8"))
        total += 1
        ring, reason = classify(record)

        if ring is None:
            unclear.append((f.stem, reason))
        else:
            ring_counts[ring] += 1

        # 工具调用「格式正确」= 没崩在环 1 或环 2
        if ring not in (1, 2):
            tool_call_ok += 1

        if args.verbose:
            label = f"环{ring}" if ring else "待人工"
            print(f"  {f.stem:20s} {label:8s} {reason}")

    if args.verbose:
        print()

    # ---------------- 输出 ----------------
    print("=" * 62)
    print(f"运行目录: {rundir}")
    if meta:
        print(f"harness: {meta.get('harness')}   重复: {meta.get('repeat')}   "
              f"tag: {meta.get('tag') or '(未填)'}")
    print(f"总运行次数: {total}")
    print("=" * 62)

    rate = tool_call_ok / total * 100 if total else 0.0
    print(f"\n【指标 1】工具调用格式正确率: {rate:.1f}%  ({tool_call_ok}/{total})")
    print("  ↳ 定义:没崩在环 1(不调用)或环 2(格式错)的比例")

    if rate >= 90:
        verdict = "≥90% → 模型够用,瓶颈在别处。别买机器,去改 RAG"
    elif rate >= 70:
        verdict = "70-90% → 边缘。先免费试 Code mode / 提示工程,不行再考虑硬件"
    else:
        verdict = "<70% → 模型能力不足。如果环 1/2 占多数,硬件投资理由充分"
    print(f"  ↳ 判据:{verdict}")

    print("\n【指标 2】七环失败分布")
    print("-" * 62)
    if not ring_counts:
        print("  未检出明确失败 —— 要么真的很好,要么 PATTERNS 没匹配上你的输出格式。")
        print("  先手工读 2-3 条 runs/*.json 确认后者。")
    else:
        worst = ring_counts.most_common(1)[0][0]
        for ring in sorted(RINGS):
            n = ring_counts.get(ring, 0)
            name, desc, fix = RINGS[ring]
            bar = "█" * int(n / max(ring_counts.values()) * 24) if n else ""
            mark = " ←" if ring == worst and n else ""
            print(f"  环{ring} {name:12s} {n:3d}  {bar}{mark}")
        print("-" * 62)
        name, desc, fix = RINGS[worst]
        print(f"  主瓶颈:环{worst} · {name}")
        print(f"    症状:{desc}")
        print(f"    修法:{fix}")

    if unclear:
        print(f"\n【待人工判断】{len(unclear)} 条")
        print("  这些没崩,但答案质量要人看 —— 环 3 / 环 5 通常藏在这里")
        for stem, reason in unclear[:10]:
            print(f"    {rundir / (stem + '.json')}")
        if len(unclear) > 10:
            print(f"    ... 还有 {len(unclear) - 10} 条")

    print("\n下一步:走 docs/05-eval-plan.md 的决策树,结论写进 notes/findings.md")


if __name__ == "__main__":
    main()
