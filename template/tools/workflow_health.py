#!/usr/bin/env python3
"""Health check for Workflow runs: which agents finished, which are running, which died, and why (standing, 2026-10-02).

A workflow agent whose output is refused by an API content filter dies without seeing the error: the script gets null,
the run carries on, and the only signal is an "Error" chip. This tool reads the run's journal and agent transcripts so the
orchestrator never learns of a death from a screenshot.

Usage (from the project root):
  python3 tools/workflow_health.py                 latest run
  python3 tools/workflow_health.py <run id or dir> one run (wf_... id, or its folder)
  python3 tools/workflow_health.py <run> --runlog  also append the dead agents to research/corrections/blocked-runs.md (idempotent)
  python3 tools/workflow_health.py <run> --json    machine-readable
  python3 tools/workflow_health.py <run> --classify "<label>" "<classification>" "<resolution>"   fill the run-log row (transient | reproducible passage BP-n | length-triggered | model-declined)
Run folders live under ~/.claude/projects/<project>/subagents/workflows/wf_*/ (journal.jsonl, agent-<id>.jsonl, .meta.json).
"""
import json, os, sys, glob, re, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
RUNLOG = os.path.join(ROOT, "research", "corrections", "blocked-runs.md")
ERR = re.compile(r"API Error|Output blocked|content filtering|rate_limit|overloaded|terminated|killed", re.I)

def run_dirs():
    base = os.path.expanduser("~/.claude/projects")
    return sorted(glob.glob(os.path.join(base, "*", "subagents", "workflows", "wf_*")) + glob.glob(os.path.join(base, "*", "*", "subagents", "workflows", "wf_*")), key=os.path.getmtime)

def find_run(arg):
    if not arg: return run_dirs()[-1]
    if os.path.isdir(arg): return arg
    hits = [d for d in run_dirs() if os.path.basename(d).startswith(arg)]
    if not hits: sys.exit(f"no run matching {arg}")
    return hits[-1]

def transcript_tail(path, n=6):
    """last tool calls, last text, first/last timestamps of an agent transcript"""
    tools, texts, ts = [], [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try: d = json.loads(line)
            except ValueError: continue
            if d.get("timestamp"): ts.append(d["timestamp"])
            c = (d.get("message") or {}).get("content")
            if not isinstance(c, list): continue
            for x in c:
                if x.get("type") == "tool_use":
                    inp = x.get("input") or {}
                    arg = inp.get("file_path") or inp.get("command") or inp.get("pattern") or json.dumps(inp)[:200]
                    tools.append((x.get("name"), str(arg).replace("\n", " ")[:200]))
                elif x.get("type") == "text": texts.append(x["text"][:300].replace("\n", " "))
    files = []
    for name, arg in tools[-n:]:
        files += re.findall(r"(?:videos|books|research|transcripts|wip)/[^\s'\";|&)]+", arg)
    return dict(last_tools=tools[-n:], last_text=texts[-1] if texts else "", error=next((t for t in reversed(texts) if ERR.search(t)), ""),
                started=ts[0][:19] if ts else "", last=ts[-1][:19] if ts else "", tool_calls=len(tools), files=sorted(set(files))[-8:])

def report(run):
    lab, status, keys = {}, {}, {}
    jp = os.path.join(run, "journal.jsonl")
    if os.path.exists(jp):
        for line in open(jp, encoding="utf-8"):
            d = json.loads(line); t = d.get("type")
            if t == "started": lab[d["agentId"]] = d.get("label", "?"); status[d["agentId"]] = "running"; keys[d["agentId"]] = d.get("key")
            elif t in ("result", "failed"): status[d["agentId"]] = "done" if t == "result" else "failed"
    out = []
    for aid, st in status.items():
        tp = os.path.join(run, f"agent-{aid}.jsonl")
        tail = transcript_tail(tp) if os.path.exists(tp) else {}
        meta = json.load(open(os.path.join(run, f"agent-{aid}.meta.json"))) if os.path.exists(os.path.join(run, f"agent-{aid}.meta.json")) else {}
        out.append(dict(agent=aid, label=lab.get(aid, "?"), status=st, model=meta.get("model", ""), **tail))
    return out

def runlog(run, rows):
    today = datetime.date.today().isoformat(); rid = os.path.basename(run)
    hdr = ("# Blocked and dead agent runs (run log; standing, tools/filter-blocks.md section 8)\n\nTerminal and transient blocks that did not isolate a passage. "
           "Reproducible passages awaiting the owner's summary are in blocked-passages.md instead. One row per dead agent; the classification is filled in when the resume reports.\n\n"
           "| Date | Run | Agent (label) | Died at (UTC) | Last tool call | Files in play | Error | Classification | Resolution |\n|---|---|---|---|---|---|---|---|---|\n")
    s = LN.read_text(RUNLOG) if os.path.exists(RUNLOG) else hdr
    added = 0
    for r in rows:
        if r["status"] != "failed": continue
        key = f"| {rid} | {r['label']} |"
        if key in s: continue
        lt = r["last_tools"][-1] if r.get("last_tools") else ("", "")
        s = s.rstrip("\n") + f"\n| {today} | {rid} | {r['label']} | {r.get('last','')} | {lt[0]}: {lt[1][:90].replace('|','/')} | {', '.join(r.get('files', []))[:160].replace('|','/')} | {(r.get('error') or 'none recorded')[:80].replace('|','/')} | unclassified (resume pending) | |"
        added += 1
    LN.write_text(RUNLOG, s + "\n"); print(f"run log: {added} rows added to {os.path.relpath(RUNLOG, ROOT)}")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run = find_run(args[0] if args else None); rows = report(run)
    if "--json" in sys.argv: print(json.dumps(rows, indent=1)); sys.exit()
    from collections import Counter
    print(f"run {os.path.basename(run)}: {dict(Counter(r['status'] for r in rows))}")
    for r in sorted(rows, key=lambda r: (r["status"] != "failed", r["label"])):
        flag = "  DEAD " if r["status"] == "failed" else ("  run  " if r["status"] == "running" else "  done ")
        print(f"{flag} {r['label']:<22} {r.get('started','')[11:]}..{r.get('last','')[11:]}  calls {r.get('tool_calls',0)}")
        if r["status"] == "failed":
            print(f"         error: {r.get('error') or 'none recorded in transcript'}")
            for n, a in r.get("last_tools", [])[-3:]: print(f"         last:  {n}: {a[:110]}")
            if r.get("files"): print(f"         files: {', '.join(r['files'])}")
    if "--runlog" in sys.argv: runlog(run, rows)
    if "--classify" in sys.argv:
        i = sys.argv.index("--classify"); label, cls, res = sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3]; rid = os.path.basename(run)
        s = LN.read_text(RUNLOG); out = []
        for line in s.split("\n"):
            if f"| {rid} | {label} |" in line:
                cells = line.split("|"); cells[-3] = f" {cls} "; cells[-2] = f" {res} "; line = "|".join(cells)
            out.append(line)
        LN.write_text(RUNLOG, "\n".join(out)); print(f"classified {label}: {cls}")
