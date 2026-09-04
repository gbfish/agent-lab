#!/usr/bin/env python3
"""
run_eval.py —— 跑基线测试,把原始 trajectory 全部落盘

用法:
    python3 scripts/run_eval.py --repeat 3
    python3 scripts/run_eval.py --harness dsh --repeat 3
    python3 scripts/run_eval.py --only q001,q003        # 只跑指定题目

原则:
  1. 落盘的是原始输出,不是渲染后的文字 —— 渲染后的没有诊断价值
  2. --repeat 是为了看稳定性,不是看单次表现
  3. 每次只改一个变量,改了什么写进 --tag

⚠️ 重要:下面的 HARNESSES 里的命令行需要你按实际版本核对一遍。
   Goose 的 CLI 标志在版本间有变化,先跑 `goose --help` 确认。
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Harness 命令模板
#
# {question} 会被替换成题目文本。
# ⚠️ 先手动跑一遍确认能通,再批量跑 —— 不然你会得到 60 个一模一样的报错。
# ---------------------------------------------------------------------------
HARNESSES = {
    "goose": {
        # 核对点:headless 执行的子命令名、传文本的标志、verbose 标志
        "cmd": ["goose", "run", "--text", "{question}"],
        "env": {},
    },
    "dsh": {
        # DeepSeek Harness。它的 trajectory 是 append-only 事件流,
        # 支持 fork/replay —— 定位失败时比 goose 好用
        "cmd": ["npx", "@deepseek-ai/dsh", "run", "{question}"],
        "env": {},
    },
}


def load_questions(path: Path, only: set[str] | None) -> list[dict]:
    if not path.exists():
        sys.exit(
            f"找不到 {path}\n"
            f"先执行: cp evals/questions.example.jsonl evals/questions.jsonl\n"
            f"然后换成真实技师问过的问题(别自己编,理由见 evals/README.md)"
        )
    questions = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            q = json.loads(line)
        except json.JSONDecodeError as e:
            sys.exit(f"{path}:{lineno} JSON 解析失败: {e}")
        if only and q.get("id") not in only:
            continue
        questions.append(q)
    if not questions:
        sys.exit("没有题目可跑")
    return questions


def run_once(harness: dict, question: str, timeout: int) -> dict:
    """跑一次,原样捕获 stdout / stderr / 返回码 / 耗时。"""
    cmd = [part.replace("{question}", question) for part in harness["cmd"]]
    env = {**os.environ, **harness["env"]}

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_sec": round(time.time() - started, 2),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        # 超时本身就是信号 —— 通常是环 6(循环不收敛)
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "") if isinstance(e.stderr, str) else "",
            "elapsed_sec": round(time.time() - started, 2),
            "timed_out": True,
        }
    except FileNotFoundError:
        sys.exit(
            f"命令找不到: {cmd[0]}\n"
            f"确认它在 PATH 里,并核对 scripts/run_eval.py 顶部的 HARNESSES 配置"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", default="goose", choices=sorted(HARNESSES))
    ap.add_argument("--questions", default=str(ROOT / "evals" / "questions.jsonl"))
    ap.add_argument("--repeat", type=int, default=3,
                    help="每题跑几遍 —— 要看的是稳定性,不是单次表现")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--only", default="", help="只跑这些 id,逗号分隔")
    ap.add_argument("--tag", default="",
                    help="这次改了什么变量。⚠️ 每次只改一个")
    ap.add_argument("--outdir", default="")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    questions = load_questions(Path(args.questions), only)
    harness = HARNESSES[args.harness]

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    outdir = Path(args.outdir) if args.outdir else ROOT / "runs" / stamp
    outdir.mkdir(parents=True, exist_ok=True)

    meta = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "harness": args.harness,
        "cmd_template": harness["cmd"],
        "repeat": args.repeat,
        "timeout": args.timeout,
        "tag": args.tag,
        "question_count": len(questions),
    }
    (outdir / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = len(questions) * args.repeat
    done = 0
    print(f"harness={args.harness}  题目={len(questions)}  重复={args.repeat}  "
          f"共 {total} 次\n输出 → {outdir}\n")
    if not args.tag:
        print("⚠️  没填 --tag。三周后你会忘记这次改了什么。\n")

    for q in questions:
        for rep in range(1, args.repeat + 1):
            done += 1
            qid = q.get("id", "noid")
            print(f"[{done}/{total}] {qid} rep{rep} ... ", end="", flush=True)

            result = run_once(harness, q["question"], args.timeout)
            record = {"question": q, "repeat": rep, **result}

            (outdir / f"{qid}_r{rep}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if result["timed_out"]:
                print(f"TIMEOUT ({result['elapsed_sec']}s)")
            elif result["returncode"] not in (0, None):
                print(f"exit={result['returncode']} ({result['elapsed_sec']}s)")
            else:
                print(f"ok ({result['elapsed_sec']}s)")

    print(f"\n完成。下一步:\n  python3 scripts/analyze.py {outdir}")
    print("\n⚠️ 别只看脚本输出 —— 至少手工读 10 条失败的完整 trajectory。")
    print("   环 3/4/5 的区别机器判断不准,必须人看。")


if __name__ == "__main__":
    main()
