#!/usr/bin/env python3
"""
run_eval.py —— 跑基线测试,把原始 trajectory 全部落盘

用法:
    python3 scripts/run_eval.py --model qwen3:14b --repeat 3 --tag baseline
    python3 scripts/run_eval.py --model qwen3:8b --only t01,t07
    python3 scripts/run_eval.py --model qwen3:14b --max-turns 30 --tag "max-turns=30"

每次运行(任务 × 重复)做的事:
  1. 建一个空的沙箱目录 runs/<stamp>/<tid>_r<n>/work/,写入 setup 文件
  2. 在那个目录里 goose run(只挂 --with-builtin developer,--no-profile 不加载别的)
  3. 把 stdout(stream-json 事件流)、stderr、退出码、耗时原样落盘
  4. goose session export --format json → session.json(干净的完整对话,分析用这个)
  5. 跑 checks,记录每条过没过

注意:session 会留在 goose 自己的数据库里(goose 1.49 的非交互 `session remove` 有 bug)。
堆多了用 `goose session remove` 交互式清,或者直接 `goose session list` 看着删。

原则:
  - 落盘的是原始输出,不是渲染后的文字 —— 渲染后的没有诊断价值
  - --repeat 是为了看稳定性,不是看单次表现
  - 每次只改一个变量,改了什么写进 --tag

⚠️ 跑之前:Ollama 必须用 OLLAMA_CONTEXT_LENGTH=32768 起。
   默认 4096 会让模型看不全工具定义,所有失败都会被误判成环 1。
   脚本会在第一次运行后查 /api/ps 核对,不够会直接退出。
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_CONTEXT = 16384


# ---------------------------------------------------------------------------
# 题目
# ---------------------------------------------------------------------------
def load_tasks(path: Path, only: set[str] | None) -> list[dict]:
    if not path.exists():
        sys.exit(f"找不到 {path}(格式见 evals/README.md)")
    tasks = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError as e:
            sys.exit(f"{path}:{lineno} JSON 解析失败: {e}")
        for key in ("id", "task", "checks"):
            if key not in t:
                sys.exit(f"{path}:{lineno} 缺字段 {key}")
        if only and t["id"] not in only:
            continue
        tasks.append(t)
    if not tasks:
        sys.exit("没有题目可跑")
    return tasks


def write_setup(workdir: Path, setup: dict) -> None:
    for rel, content in (setup.get("files") or {}).items():
        p = workdir / rel
        if not p.resolve().is_relative_to(workdir.resolve()):
            sys.exit(f"setup 路径越界: {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 跑 goose
# ---------------------------------------------------------------------------
def goose_cmd(args, task_text: str, session_name: str) -> list[str]:
    cmd = [
        "goose", "run",
        "--provider", args.provider,
        "--model", args.model,
        "--no-profile",
        "--with-builtin", args.builtin,
        "--output-format", "stream-json",
        "--max-turns", str(args.max_turns),
        "--max-tool-repetitions", str(args.max_tool_repetitions),
        "--name", session_name,
        "-t", task_text,
    ]
    if args.system:
        cmd += ["--system", args.system]
    return cmd


def run_once(cmd: list[str], cwd: Path, timeout: int) -> dict:
    """跑一次,原样捕获 stdout / stderr / 返回码 / 耗时。"""
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_sec": round(time.time() - started, 2),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        # 超时本身就是信号 —— 通常是环 6(循环不收敛)
        return {
            "returncode": None,
            "stdout": e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace"),
            "stderr": e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace"),
            "elapsed_sec": round(time.time() - started, 2),
            "timed_out": True,
        }
    except FileNotFoundError:
        sys.exit("找不到 goose。先装:brew install block-goose-cli")


def export_session(name: str, dest: Path) -> dict | None:
    proc = subprocess.run(
        ["goose", "session", "export", "--name", name, "--format", "json", "-o", str(dest)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not dest.exists():
        return None
    try:
        return json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def count_tool_calls(session: dict | None) -> int:
    n = 0
    for m in (session or {}).get("conversation") or []:
        for part in m.get("content") or []:
            if part.get("type") == "toolRequest":
                n += 1
    return n


def final_answer(session: dict | None) -> str:
    """最后一条 assistant 文本(不含 thinking)。"""
    if not session:
        return ""
    texts = []
    for m in session.get("conversation") or []:
        if m.get("role") != "assistant":
            continue
        for part in m.get("content") or []:
            if part.get("type") == "text" and part.get("text"):
                texts.append(part["text"])
    return texts[-1] if texts else ""


# ---------------------------------------------------------------------------
# 判分
# ---------------------------------------------------------------------------
def read_file(workdir: Path, rel: str) -> str | None:
    p = workdir / rel
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def run_check(check: dict, workdir: Path, answer: str, n_tool_calls: int = 0) -> dict:
    t = check.get("type")
    ok, detail = False, ""
    if t == "tool_calls_min":
        ok = n_tool_calls >= int(check.get("n", 1))
        detail = f"实际调用 {n_tool_calls} 次"
    elif t == "file_exists":
        ok = (workdir / check["path"]).is_file()
    elif t == "file_absent":
        ok = not (workdir / check["path"]).exists()
    elif t == "file_equals":
        got = read_file(workdir, check["path"])
        ok = got is not None and got.strip() == check["value"].strip()
        detail = "文件不存在" if got is None else ""
    elif t == "file_contains":
        got = read_file(workdir, check["path"])
        ok = got is not None and check["value"] in got
        detail = "文件不存在" if got is None else ""
    elif t == "file_not_contains":
        got = read_file(workdir, check["path"])
        ok = got is not None and check["value"] not in got
        detail = "文件不存在" if got is None else ""
    elif t == "cmd":
        try:
            proc = subprocess.run(check["cmd"], shell=True, cwd=workdir,
                                  capture_output=True, text=True, timeout=60)
            ok = proc.returncode == 0 and check.get("stdout_contains", "") in proc.stdout
            detail = f"rc={proc.returncode} stdout={proc.stdout.strip()[:200]!r}"
        except subprocess.TimeoutExpired:
            detail = "命令超时"
    elif t == "answer_contains":
        low = answer.lower()
        ok = any(s.lower() in low for s in check.get("any", []))
    elif t == "manual":
        ok = True  # 不影响自动结果,只是提醒人看
        detail = check.get("note", "")
    else:
        detail = f"未知 check 类型 {t}"
    return {"check": check, "ok": ok, "detail": detail}


# ---------------------------------------------------------------------------
# Ollama 上下文核对
# ---------------------------------------------------------------------------
def ollama_context_length(host: str, model: str) -> int | None:
    try:
        with urllib.request.urlopen(f"{host}/api/ps", timeout=5) as r:
            data = json.load(r)
    except Exception:
        return None
    for m in data.get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("context_length")
    return None


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default=os.environ.get("GOOSE_MODEL", "qwen3:8b"),
                    help="Ollama 模型名。本机 18GB 的上限是 qwen3:14b")
    ap.add_argument("--builtin", default="developer",
                    help="挂哪些 builtin extension,逗号分隔")
    ap.add_argument("--system", default="", help="附加 system 指令(做提示工程实验时用)")
    ap.add_argument("--tasks", default=str(ROOT / "evals" / "tasks.jsonl"))
    ap.add_argument("--repeat", type=int, default=3,
                    help="每题跑几遍 —— 要看的是稳定性,不是单次表现")
    ap.add_argument("--timeout", type=int, default=600, help="单次运行秒数上限")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--max-tool-repetitions", type=int, default=3)
    ap.add_argument("--only", default="", help="只跑这些 id,逗号分隔")
    ap.add_argument("--tag", default="", help="这次改了什么变量。⚠️ 每次只改一个")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--skip-context-check", action="store_true")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    tasks = load_tasks(Path(args.tasks), only)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    outdir = Path(args.outdir) if args.outdir else ROOT / "runs" / stamp
    outdir.mkdir(parents=True, exist_ok=True)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not ollama_host.startswith("http"):
        ollama_host = "http://" + ollama_host

    meta = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": args.model,
        "builtin": args.builtin,
        "system": args.system,
        "repeat": args.repeat,
        "timeout": args.timeout,
        "max_turns": args.max_turns,
        "max_tool_repetitions": args.max_tool_repetitions,
        "tag": args.tag,
        "task_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
        "ollama_context_length": None,
        "goose_version": subprocess.run(["goose", "--version"], capture_output=True,
                                        text=True).stdout.strip(),
    }
    (outdir / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                       encoding="utf-8")

    total = len(tasks) * args.repeat
    print(f"model={args.model}  题目={len(tasks)}  重复={args.repeat}  共 {total} 次\n输出 → {outdir}\n")
    if not args.tag:
        print("⚠️  没填 --tag。三周后你会忘记这次改了什么。\n")

    done = 0
    passed = 0
    for t in tasks:
        for rep in range(1, args.repeat + 1):
            done += 1
            tid = t["id"]
            run_name = f"{tid}_r{rep}"
            session_name = f"agentlab_{stamp}_{run_name}"
            rundir = outdir / run_name
            workdir = rundir / "work"
            workdir.mkdir(parents=True, exist_ok=True)
            write_setup(workdir, t.get("setup") or {})

            print(f"[{done}/{total}] {run_name} ... ", end="", flush=True)
            cmd = goose_cmd(args, t["task"], session_name)
            result = run_once(cmd, workdir, args.timeout)

            session = export_session(session_name, rundir / "session.json")

            answer = final_answer(session)
            n_calls = count_tool_calls(session)
            checks = [run_check(c, workdir, answer, n_calls) for c in t["checks"]]
            auto_checks = [c for c in checks if c["check"].get("type") != "manual"]
            task_ok = bool(auto_checks) and all(c["ok"] for c in auto_checks)
            passed += task_ok

            record = {
                "task": t,
                "repeat": rep,
                "cmd": cmd,
                "cmd_str": " ".join(shlex.quote(c) for c in cmd),
                "workdir": str(workdir),
                "session_exported": session is not None,
                "final_answer": answer,
                "n_tool_calls": n_calls,
                "checks": checks,
                "task_ok": task_ok,
                **result,
            }
            (rundir / "record.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

            status = "PASS" if task_ok else "FAIL"
            if result["timed_out"]:
                status = "TIMEOUT"
            elif result["returncode"] not in (0, None):
                status += f" exit={result['returncode']}"
            print(f"{status} ({result['elapsed_sec']}s)")

            # 第一次跑完就核对上下文,不够立刻停,别浪费一下午
            if done == 1 and not args.skip_context_check:
                ctx = ollama_context_length(ollama_host, args.model)
                meta["ollama_context_length"] = ctx
                (outdir / "_meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                if ctx is not None and ctx < MIN_CONTEXT:
                    sys.exit(
                        f"\n⚠️ Ollama 给 {args.model} 加载的上下文只有 {ctx},"
                        f"模型很可能看不全工具定义,结果没有意义。\n"
                        f"   重启:OLLAMA_CONTEXT_LENGTH=32768 ollama serve\n"
                        f"   (硬要跑加 --skip-context-check)"
                    )

    print(f"\n完成。任务通过 {passed}/{total}。下一步:\n  python3 scripts/analyze.py {outdir}")
    print("\n⚠️ 别只看脚本输出 —— 至少手工读 10 条失败的 session.json。")
    print("   环 3 / 环 5 的区别机器判断不准,必须人看。")


if __name__ == "__main__":
    main()
