#!/usr/bin/env python3
"""Regenerate every generated page after a hand-back, in order, as one command (tools/platform-plan.md, phase 5: the pages the
hand-back used to run by hand). Each step runs the tool as `python3 tools/<tool>.py [args]` would, from the project root; a step that
fails is reported and the next still runs (the pages are independent), and the command exits 1 when any step failed.

Usage: python3 tools/build_reports.py [--only a,b] [--skip a,b] [--with-graph] [--log DIR] [--list]
  --only / --skip   step names (below) to run or leave out
  --with-graph      also rebuild the map's data files (tools/build_graph_data.py: graph-*.json, graph-display.json, graph-typed.json)
  --log DIR         save each step's printed output as DIR/<step>.txt (UTF-8, LF)
  --list            print the steps in order and their outputs, and the pages no tool regenerates; run nothing
Every output is a local file in the folder; nothing here reaches a network."""
import os, sys, time, subprocess
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0, "tools")
import packload   # the pack's file prefix for the candour page and the first-utterance report's path
from ledger import notes as LN

PX = packload.display("candour")["file_prefix"]; FU = packload.pack().get("catalysts", {}).get("report", "research/first-utterance.md")
STEPS = [   # (name, argv after python3, outputs), in order: a step that reads another's output comes after it
    ("index", ["tools/build_index.py"], ["README.md"]),
    ("timeline", ["tools/build_timeline.py"], ["research/timeline-master.md"]),
    ("timeline-contradictions", ["tools/build_timeline.py", "--contradictions"], ["research/timeline-contradictions.md"]),
    ("answers", ["tools/answers_rollup.py"], ["research/answered-questions.md"]),
    ("openness-dataset", ["tools/draw_openness_map.py", "--dataset-only"], [packload.pack().get("audit", {}).get("openness_dataset", "research/figures/openness-dataset.json")]),
    ("candour-charts", ["tools/draw_forthrightness_chart.py", "--all"], [f"research/figures/{PX}-groups.json", f"research/figures/{PX}-by-interviewee.png"]),   # pilot defect 8 (7b2): a pack keeping its charts by hand skips
    ("candour-page", ["tools/build_forthrightness_page.py"], [f"research/{PX}-charts.md"]),
    ("topic-corroboration", ["tools/draw_topic_corroboration.py"], ["research/figures/topic-corroboration.png", "research/figures/topic-corroboration.svg", "research/figures/topic-corroboration.json"]),
    ("echoes", ["tools/echoes.py"], ["research/echo-patterns.md", "research/figures/echoes.json"]),
    ("first-utterance", ["tools/first_utterance.py", "--narratives"], [FU]),
    ("divergences", ["tools/divergences.py"], ["research/divergence-patterns.md", "research/figures/divergences.json"]),
    ("viewer", ["tools/build_narrative_viewer.py"], ["research/figures/narratives-viewer.html"]),
    ("status", ["tools/build_status.py"], ["research/status.md"]),
]
# pages no tool writes: agent-written, so a rebuild cannot regenerate them (listed by --list so a copy knows what stays as copied)
AGENT_WRITTEN = [("research/timeline-consolidated.md and the era pages research/timeline-consolidated-<era>.md", "one agent per era (2026-09-27), new notes' rows placed by agents; the generated contradictions and drifts are the timeline-contradictions step"),
                 ("research/timeline-contradictions-2026-09-27.md", "compiled by agents from the timeline-retrofit reports, with assessments")]
GRAPH = ("graph", ["tools/build_graph_data.py"], ["research/figures/graph-data.json", "research/figures/graph-display.json", "research/figures/graph-typed.json"])

def main(argv):
    def opt(f): return argv[argv.index(f) + 1].split(",") if f in argv else None
    steps = list(STEPS)
    if "--with-graph" in argv: steps.insert(len(steps) - 1, GRAPH)   # after echoes and divergences (it reads their JSON), before the status page (it reads graph-typed.json)
    only, skip, log = opt("--only"), opt("--skip") or [], (argv[argv.index("--log") + 1] if "--log" in argv else None)
    names = {s[0] for s in steps} | {GRAPH[0]}
    for n in (only or []) + skip:
        if n not in names: sys.exit(f"build_reports: no step {n!r} (steps: {', '.join(s[0] for s in STEPS)}, graph)")
    if only: steps = [s for s in (steps if GRAPH in steps else steps[:-1] + [GRAPH, steps[-1]]) if s[0] in only]   # naming graph in --only runs it too
    steps = [s for s in steps if s[0] not in skip]
    if "--list" in argv:
        for k, (n, a, outs) in enumerate(steps, 1): print(f"{k:2}. {n:24} python3 {' '.join(a):45} -> {', '.join(outs)}")
        print("Not regenerated (agent-written; no tool writes them):")
        for page, why in AGENT_WRITTEN: print(f"    {page}: {why}")
        return 0
    if log: os.makedirs(log, exist_ok=True)
    res = []
    for n, a, outs in steps:
        t0 = time.time(); print(f"[{n}] python3 {' '.join(a)}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(_T, os.path.basename(a[0]))] + a[1:], capture_output=True, text=True)   # the tool beside this one; the project is the working folder
        dt = time.time() - t0; last = (r.stdout.strip().split("\n") or [""])[-1][:160]
        if log: LN.write_text(os.path.join(log, n + ".txt"), f"argv: python3 {' '.join(a)}\nexit: {r.returncode}\n--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}\n")
        if r.returncode: sys.stderr.write(r.stderr[-2000:])
        res.append((n, r.returncode, dt, outs, last))
        print(f"[{n}] exit {r.returncode} ({dt:.1f}s): {last}", flush=True)
    print("\n| Step | Exit | Seconds | Output |\n|---|---|---|---|")
    for n, rc, dt, outs, _ in res: print(f"| {n} | {rc} | {dt:.1f} | {', '.join(o + ('' if os.path.exists(o) else ' (missing)') for o in outs)} |")
    bad = [n for n, rc, *_ in res if rc]
    print(f"\n{len(res) - len(bad)} of {len(res)} steps passed" + (f"; failed: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0

if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv: sys.exit(print(__doc__) or 0)
    sys.exit(main(sys.argv[1:]))
