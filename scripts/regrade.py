#!/usr/bin/env python3
"""
regrade.py —— 用当前 evals/tasks.jsonl 里的 checks 重新给已有运行判分,不重跑模型

用法:
    python3 scripts/regrade.py runs/baseline_qwen3-14b-16k/

什么时候用:改了某条任务的 checks(比如关键字没覆盖到),不想为了判分重跑一小时。
只改 record.json 里的 checks / task_ok,其他原始数据不动。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import ROOT, count_tool_calls, load_tasks, run_check  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rundir = Path(sys.argv[1])
    tasks = {t["id"]: t for t in load_tasks(ROOT / "evals" / "tasks.jsonl", None)}
    changed = 0
    for d in sorted(p for p in rundir.iterdir() if p.is_dir() and (p / "record.json").exists()):
        rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
        tid = rec["task"]["id"]
        if tid not in tasks:
            print(f"  {d.name}: 任务 {tid} 已不在 tasks.jsonl,跳过")
            continue
        session = None
        if (d / "session.json").exists():
            try:
                session = json.loads((d / "session.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        n_calls = count_tool_calls(session)
        rec["n_tool_calls"] = n_calls
        checks = [run_check(c, d / "work", rec.get("final_answer", ""), n_calls) for c in tasks[tid]["checks"]]
        auto = [c for c in checks if c["check"].get("type") != "manual"]
        ok = bool(auto) and all(c["ok"] for c in auto)
        if ok != rec.get("task_ok"):
            print(f"  {d.name}: {rec.get('task_ok')} -> {ok}")
            changed += 1
        rec["checks"] = checks
        rec["task_ok"] = ok
        rec["task"]["checks"] = tasks[tid]["checks"]
        (d / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"重判完成,{changed} 条结果变化")


if __name__ == "__main__":
    main()
