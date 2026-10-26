#!/usr/bin/env python3
"""Per-agent usage of a Workflow run, read from the transcript jsonl (standing measure, 2026-10-16; tools/intake-staged.md).

Why: the staged intake (tools/workflows/staged-intake.js) is justified by a measurement, and the next run must be measured the
same way as the baseline (four guarded-intake agents of 2026-10-15: two intakes, A and B each). This script is that
measure. It reads nothing but the run folder.

Usage (from the project root):
  python3 tools/agent_usage.py                       latest run
  python3 tools/agent_usage.py <run id or dir>       one run (wf_... id or prefix, or the folder)
  python3 tools/agent_usage.py <run> --json          machine-readable
  python3 tools/agent_usage.py <run> --by-phase      add a per-phase subtotal (the staged runs: read, gate, write, finish)
  python3 tools/agent_usage.py <run> --md            the per-agent table as markdown (for tools/intake-staged.md)
  python3 tools/agent_usage.py <run> --append-cost-log   append the run's per-agent rows and its total row to the cost log (the
                                                     path pack [display.status] cost_log names; research/cost-log.md by default),
                                                     which the status page summarises; a run already in the log is not appended
  python3 tools/agent_usage.py [<run>] --task <key> [--records]   only the agents of one task of a staged run (an agent whose
                                                     label has <key> as one of its colon-separated parts: read:<key>:001-010,
                                                     gate2:<key>:write-a:0, resume1:write-b:<key>); without a run, the latest run
                                                     holding an agent of that task. --records prints one JSON line, the task's
                                                     cache-read by records and per phase (the measure staged-intake.js's
                                                     maxRecords is checked against, 2026-10-23)

Run folders live under ~/.claude/projects/<project>/subagents/workflows/wf_*/ (journal.jsonl, agent-<id>.jsonl, agent-<id>.meta.json).

Columns, and how each is counted (the baseline of 2026-10-15 was counted the same way):
  turns        assistant records in the jsonl: one per content block the API streamed (a thinking block and a tool_use block of
               one call are two records). This is the measure the baseline's "turns" used (the fourth agent: 254).
  calls        distinct API calls (message ids). Each call re-reads the whole context.
  cache-create cache_creation_input_tokens summed once per call (the record with the largest output_tokens of that call is taken,
               since streamed records of one call repeat its usage).
  cache-read   cache_read_input_tokens summed once per call: the whole context re-read on every call.
  cache-read(r) the same field summed over every assistant RECORD (streamed blocks of one call counted again): this is how the
               baseline's "cache-read" figures were taken (the first agent 125.0M; per call it is 72.2M). Both are printed so the
               next run compares on either.
  input        uncached input_tokens summed once per call.
  output(est)  the transcript's usage.output_tokens is the stream's opening count (4 to 33 on every call but the final text), so
               output is estimated as the characters of the agent's content blocks (text, thinking, tool inputs) divided by 4.
  context-end  input + cache-create + cache-read of the LAST call: the context the agent carried at the end (the baseline's "end context").
  tools        tool_use blocks by tool name; reads = Read calls plus Bash commands whose first word is cat, sed, head, tail or less;
               greps = Grep calls plus Bash commands containing grep or rg; writes = Write and Edit calls plus Bash heredocs (<<).
  wall         first to last timestamp of the transcript.
"""
import json, os, sys, glob, re, datetime

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_dirs():
    base = os.path.expanduser("~/.claude/projects")
    return sorted(glob.glob(os.path.join(base, "*", "subagents", "workflows", "wf_*")) + glob.glob(os.path.join(base, "*", "*", "subagents", "workflows", "wf_*")), key=os.path.getmtime)


def task_of(label, key):
    """whether an agent's label belongs to a task: the key is one of the label's colon-separated parts"""
    return key in str(label or "").split(":")


def find_task_run(key):
    """the latest run (by modification time) holding an agent of the task"""
    for d in reversed(run_dirs()):
        for mp in glob.glob(os.path.join(d, "agent-*.meta.json")):
            try: meta = json.load(open(mp, encoding="utf-8"))
            except (ValueError, OSError): continue
            if task_of(meta.get("description"), key): return d
    sys.exit(f"no run holds an agent of task {key}")


def find_run(arg):
    if not arg:
        d = run_dirs()
        if not d: sys.exit("no workflow runs found")
        return d[-1]
    if os.path.isdir(arg): return arg
    hits = [d for d in run_dirs() if os.path.basename(d).startswith(arg)]
    if not hits: sys.exit(f"no run matching {arg}")
    return hits[-1]


READ_CMDS = ("cat", "sed", "head", "tail", "less")


def classify_bash(cmd):
    """first-word reads, grep anywhere, heredoc writes; a command may count in more than one bucket"""
    out = set()
    for part in re.split(r"\s*(?:&&|\|\||;|\n)\s*", cmd):
        part = part.strip()
        if not part: continue
        if part.startswith("cd "): continue
        head = part.split()[0] if part.split() else ""
        if head in READ_CMDS: out.add("reads")
        if re.search(r"\b(grep|rg)\b", part): out.add("greps")
        if "<<" in part or re.match(r"(python3?|cp|mv|tee)\b", head): out.add("writes") if "<<" in part or head in ("cp", "mv", "tee") else None
    return out


def parse_agent(path):
    calls = {}      # message id -> usage dict with the largest output_tokens seen
    order = []      # message ids in first-seen order
    turns = 0
    cache_read_records = 0
    out_chars = 0
    tools = {}
    reads = greps = writes = 0
    ts = []
    model = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try: d = json.loads(line)
            except ValueError: continue
            if d.get("timestamp"): ts.append(d["timestamp"])
            if d.get("type") != "assistant": continue
            turns += 1
            m = d.get("message") or {}
            model = model or m.get("model")
            mid = m.get("id") or d.get("requestId") or d.get("uuid")
            u = m.get("usage") or {}
            cache_read_records += u.get("cache_read_input_tokens") or 0
            for c in m.get("content") or []:
                if c.get("type") == "tool_use": out_chars += len(json.dumps(c.get("input") or {}))
                else: out_chars += len(c.get("text") or c.get("thinking") or "")
            if mid not in calls: calls[mid] = dict(u); order.append(mid)
            elif (u.get("output_tokens") or 0) > (calls[mid].get("output_tokens") or 0): calls[mid] = dict(u)
            for c in m.get("content") or []:
                if c.get("type") != "tool_use": continue
                name = c.get("name") or "?"
                tools[name] = tools.get(name, 0) + 1
                inp = c.get("input") or {}
                if name == "Read": reads += 1
                elif name == "Grep": greps += 1
                elif name in ("Write", "Edit", "MultiEdit", "NotebookEdit"): writes += 1
                elif name == "Bash":
                    k = classify_bash(str(inp.get("command") or ""))
                    reads += "reads" in k; greps += "greps" in k; writes += "writes" in k
    def s(key): return sum((calls[m].get(key) or 0) for m in order)
    last = calls[order[-1]] if order else {}
    ctx_end = (last.get("input_tokens") or 0) + (last.get("cache_creation_input_tokens") or 0) + (last.get("cache_read_input_tokens") or 0)
    wall = None
    if len(ts) >= 2:
        try:
            a = datetime.datetime.fromisoformat(ts[0].replace("Z", "+00:00")); b = datetime.datetime.fromisoformat(ts[-1].replace("Z", "+00:00"))
            wall = int((b - a).total_seconds())
        except ValueError: wall = None
    return {"turns": turns, "calls": len(order), "cache_create": s("cache_creation_input_tokens"), "cache_read": s("cache_read_input_tokens"),
            "cache_read_records": cache_read_records, "input": s("input_tokens"), "output_usage": s("output_tokens"), "output": out_chars // 4, "context_end": ctx_end, "tools": tools, "reads": reads, "greps": greps,
            "writes": writes, "wall_s": wall, "model": model, "first": ts[0] if ts else None, "last": ts[-1] if ts else None}


def agents_of(run):
    out = []
    for p in sorted(glob.glob(os.path.join(run, "agent-*.jsonl"))):
        aid = os.path.basename(p)[len("agent-"):-len(".jsonl")]
        meta = {}
        mp = os.path.join(run, f"agent-{aid}.meta.json")
        if os.path.exists(mp):
            try: meta = json.load(open(mp, encoding="utf-8"))
            except ValueError: meta = {}
        r = parse_agent(p)
        r.update({"agent": aid, "label": meta.get("description") or aid, "phase": meta.get("workflowPhase") or "", "model_requested": meta.get("model")})
        out.append(r)
    return out


def journal_results(run):
    """label -> whether the journal recorded a result (ok) for the agent"""
    res = {}
    jp = os.path.join(run, "journal.jsonl")
    if not os.path.exists(jp): return res
    started = {}
    for line in open(jp, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except ValueError: continue
        if d.get("type") == "started": started[d.get("agentId")] = d.get("label")
        if d.get("type") == "result": res[d.get("agentId")] = d.get("result") is not None
    return res


def fmt_m(n): return f"{n / 1e6:.1f}M" if n >= 1e6 else (f"{n / 1e3:.0f}k" if n >= 1e3 else str(n))


def fmt_wall(s):
    if s is None: return "?"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


COST_HEADER = ["| Run | Date | Agent | Phase | Model | Turns | Calls | Cache-create | Cache-read | Cache-read (records) | Output (est) | Context at end | Wall | Result |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]


def append_cost_log(name, rows, tot):
    """Append the run's rows to the cost log: one table for every run, a header written once, a row per agent and a total row per
    run (2026-10-22, phase 5 handoff 8). The status page (tools/build_status.py) prints the header and the log's last 20 rows. A run
    whose name is already in the log's Run column is not appended again. Returns (path, rows appended)."""
    import packload
    from ledger import notes as LN
    path = os.path.join(ROOT, packload.display("status")["cost_log"])
    old = LN.read_text(path) if os.path.exists(path) else ""
    if re.search(r"^\| " + re.escape(name) + r" \|", old, re.M): return path, 0
    cell = lambda t: str(t if t is not None else "").replace("|", "/").replace("\n", " ").strip()
    day = min((r["first"] for r in rows if r["first"]), default="")[:10]
    res = lambda ok: "" if ok is None else ("ok" if ok else "dead")
    out = [f"| {name} | {day} | {cell(r['label'])} | {cell(r['phase'])} | {cell(r['model_requested'] or r['model'])} | {r['turns']} | {r['calls']} | {fmt_m(r['cache_create'])} | {fmt_m(r['cache_read'])} | {fmt_m(r['cache_read_records'])} | {fmt_m(r['output'])} | {fmt_m(r['context_end'])} | {fmt_wall(r['wall_s'])} | {res(r['ok'])} |" for r in rows]
    out.append(f"| {name} | {day} | **total, {len(rows)} agent(s)** | | | {tot['turns']} | {tot['calls']} | {fmt_m(tot['cache_create'])} | {fmt_m(tot['cache_read'])} | {fmt_m(tot['cache_read_records'])} | {fmt_m(tot['output'])} | max {fmt_m(tot['context_end_max'])} | | {sum(1 for r in rows if r['ok'])} ok |")
    if not old.strip():
        head = ["# Cost log", "", "Per-agent usage of each Workflow run, appended by `python3 tools/agent_usage.py <run> --append-cost-log` (the columns are",
                "counted as tools/agent_usage.py's docstring says; output is estimated from the characters written; Date is the run's first UTC timestamp).",
                "One table for every run, in the order appended; each run ends with its total row. The status page (research/status.md) shows the last rows.", ""] + COST_HEADER
        LN.write_text(path, "\n".join(head + out) + "\n")
    else:
        LN.write_text(path, old.rstrip("\n") + "\n" + "\n".join(out) + "\n")
    return path, len(out)


def main():
    a = sys.argv[1:]
    as_json = "--json" in a; by_phase = "--by-phase" in a; md = "--md" in a
    task = a[a.index("--task") + 1] if "--task" in a and a.index("--task") + 1 < len(a) else None
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and not (i > 0 and a[i - 1] == "--task")]
    run = find_run(pos[0]) if pos else (find_task_run(task) if task else find_run(None))
    rows = agents_of(run)
    if task: rows = [r for r in rows if task_of(r["label"], task)]
    if task and "--records" in a:
        ph = {}
        for r in rows: ph[r["phase"] or "(none)"] = ph.get(r["phase"] or "(none)", 0) + r["cache_read_records"]
        rec = sum(r["cache_read_records"] for r in rows)
        print(json.dumps({"ok": True, "task": task, "run": os.path.basename(run), "agents": len(rows), "records": rec, "by_phase": ph,
                          "context_end_max": max((r["context_end"] for r in rows), default=0),
                          "summary": f"task {task}: {len(rows)} agent(s), cache-read by records {rec / 1e6:.1f}M (" + ", ".join(f"{k} {v / 1e6:.1f}M" for k, v in ph.items()) + f") in run {os.path.basename(run)}"}))
        return
    ok = journal_results(run)
    for r in rows: r["ok"] = ok.get(r["agent"])
    tot = {k: sum(r[k] for r in rows) for k in ("turns", "calls", "cache_create", "cache_read", "cache_read_records", "input", "output", "reads", "greps", "writes")}
    tot["context_end_max"] = max((r["context_end"] for r in rows), default=0)
    phases = {}
    for r in rows:
        p = phases.setdefault(r["phase"] or "(none)", {k: 0 for k in ("agents", "turns", "calls", "cache_create", "cache_read", "cache_read_records", "output", "context_end_max")})
        p["agents"] += 1
        for k in ("turns", "calls", "cache_create", "cache_read", "cache_read_records", "output"): p[k] += r[k]
        p["context_end_max"] = max(p["context_end_max"], r["context_end"])
    if as_json:
        print(json.dumps({"run": run, "agents": rows, "totals": tot, "phases": phases}, indent=1)); return
    name = os.path.basename(run)
    if "--append-cost-log" in a:
        path, n = append_cost_log(name, rows, tot)
        print(f"cost log {os.path.relpath(path, ROOT)}: " + (f"{n} row(s) appended for run {name} ({len(rows)} agent(s) and the total)" if n else f"run {name} is already in the log; nothing appended"))
        return
    if md:
        print(f"| agent | phase | model | turns | calls | cache-create | cache-read | cache-read (records) | output (est) | context at end | reads | greps | writes | wall |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['label']} | {r['phase']} | {r['model_requested'] or r['model']} | {r['turns']} | {r['calls']} | {fmt_m(r['cache_create'])} | {fmt_m(r['cache_read'])} | {fmt_m(r['cache_read_records'])} | {fmt_m(r['output'])} | {fmt_m(r['context_end'])} | {r['reads']} | {r['greps']} | {r['writes']} | {fmt_wall(r['wall_s'])} |")
        print(f"| **run {name}** | | | {tot['turns']} | {tot['calls']} | {fmt_m(tot['cache_create'])} | {fmt_m(tot['cache_read'])} | {fmt_m(tot['cache_read_records'])} | {fmt_m(tot['output'])} | max {fmt_m(tot['context_end_max'])} | {tot['reads']} | {tot['greps']} | {tot['writes']} | |")
        return
    print(f"run {name}: {len(rows)} agent(s)  ({run})")
    print(f"{'agent':40} {'phase':8} {'turns':>5} {'calls':>5} {'cache-cr':>9} {'cache-rd':>9} {'rd(recs)':>9} {'out(est)':>8} {'ctx-end':>8} {'reads':>5} {'greps':>5} {'writes':>6} {'wall':>7}  ok")
    for r in rows:
        print(f"{r['label'][:40]:40} {r['phase'][:8]:8} {r['turns']:5} {r['calls']:5} {fmt_m(r['cache_create']):>9} {fmt_m(r['cache_read']):>9} {fmt_m(r['cache_read_records']):>9} {fmt_m(r['output']):>8} {fmt_m(r['context_end']):>8} {r['reads']:5} {r['greps']:5} {r['writes']:6} {fmt_wall(r['wall_s']):>7}  {'' if r['ok'] is None else ('yes' if r['ok'] else 'DEAD')}")
    print(f"{'total':40} {'':8} {tot['turns']:5} {tot['calls']:5} {fmt_m(tot['cache_create']):>9} {fmt_m(tot['cache_read']):>9} {fmt_m(tot['cache_read_records']):>9} {fmt_m(tot['output']):>8} {'max ' + fmt_m(tot['context_end_max']):>8} {tot['reads']:5} {tot['greps']:5} {tot['writes']:6}")
    if by_phase:
        print("\nby phase:")
        for p, v in phases.items():
            print(f"  {p:10} agents {v['agents']:3}  turns {v['turns']:5}  calls {v['calls']:5}  cache-create {fmt_m(v['cache_create']):>8}  cache-read {fmt_m(v['cache_read']):>8} (records {fmt_m(v['cache_read_records'])})  output (est) {fmt_m(v['output']):>6}  max context at end {fmt_m(v['context_end_max'])}")
    tools = {}
    for r in rows:
        for k, v in r["tools"].items(): tools[k] = tools.get(k, 0) + v
    print("tools: " + ", ".join(f"{k} {v}" for k, v in sorted(tools.items(), key=lambda x: -x[1])))


if __name__ == "__main__": main()
