#!/usr/bin/env python3
"""Blocked-output queue (tools/filter-blocks.md): register blocks an agent hit, scan deliverables for markers,
splice the owner's summary back in, list the queue.
Usage:
  python3 tools/blocked_passages.py register <report.json | wip/<task>>   # from the report's blocked_passages or wip/<task>/blocked/*.md
  python3 tools/blocked_passages.py scan [paths...]                        # every '[BLOCKED:' marker under videos/ books/ research/ (or paths)
  python3 tools/blocked_passages.py apply BP-<n> --summary <file> [--note <note.md>] [--no-guidance]
  python3 tools/blocked_passages.py list [--open]
Queue page: research/corrections/blocked-passages.md (ids BP-<n>, permanent). The marker searched for is '[BLOCKED:'.
"""
import sys, os, re, json, glob, datetime
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import packload; _PRECEDENT = packload.tool_data("blocked_passages")["queue_precedent"]   # the pack's first handled block, named on the queue page ([tools.blocked_passages])
Q = "research/corrections/blocked-passages.md"
HEAD = ("# Blocked passages: the human-review queue (tools/filter-blocks.md)\n\n"
        "One row per passage an API filter blocked during an intake or analysis. The owner reads the source at the location, writes a summary, "
        "and `python3 tools/blocked_passages.py apply BP-<n> --summary <file>` splices it into the deliverable under the owner's name. "
        + _PRECEDENT + "\n\n"
        "| Id | Date | Task | Source location | Deliverable location | About | Capture file | Status | Applied |\n|---|---|---|---|---|---|---|---|---|\n")
today = datetime.date.today().isoformat()
def load_queue():
    if not os.path.exists(Q): LN.write_text(Q, HEAD)
    return LN.read_text(Q)
def next_id(s):
    nums = [int(m) for m in re.findall(r"^\| BP-(\d+) \|", s, re.M)]; return max(nums) + 1 if nums else 1
def esc(x): return str(x or "").replace("|", "/").replace("\n", " ").strip()
def register(arg):
    s = load_queue(); items = []
    if arg.endswith(".json"):
        rep = json.load(open(arg, encoding="utf-8")); reps = rep if isinstance(rep, list) else [rep]
        task = os.path.basename(os.path.dirname(os.path.abspath(arg)))
        for r in reps:
            for b in (r.get("blocked_passages") or []):
                if isinstance(b, dict): items.append((task, b))
    else:
        task = os.path.basename(arg.rstrip("/"))
        for f in sorted(glob.glob(os.path.join(arg, "blocked", "*.md"))):
            if f.endswith(".summary.md"): continue
            t = LN.read_text(f)
            if re.search(r"^Id: BP-\d+", t, re.M): continue
            def grab(k):
                m = re.search(rf"^{k}:\s*(.+)$", t, re.M | re.I); return m.group(1).strip() if m else ""
            items.append((task, {"source": grab("source"), "deliverable_location": grab("deliverable"), "about": grab("about"), "bisect_file": grab("bisect"), "capture_file": os.path.relpath(f, ROOT)}))
    n = next_id(s); added = 0
    for task, b in items:
        key = esc(b.get("source"))[:60]
        if key and key in s: continue
        bid = f"BP-{n}"; n += 1; added += 1
        s += f"| {bid} | {today} | {task} | {esc(b.get('source'))} | {esc(b.get('deliverable_location'))} | {esc(b.get('about'))} | {esc(b.get('capture_file') or b.get('bisect_file'))} | open | |\n"
        cf = b.get("capture_file")
        if cf and os.path.exists(cf):
            t = LN.read_text(cf)
            if "Id: BP-" not in t: LN.write_text(cf, f"Id: {bid}\n" + t)
        print("registered", bid, task, esc(b.get("source"))[:80])
    LN.write_text(Q, s); print(f"{added} registered")
def scan(paths):
    paths = paths or ["videos", "books", "research"]
    s = load_queue(); hits = 0
    for p in paths:
        files = [p] if os.path.isfile(p) else glob.glob(os.path.join(p, "**", "*.md"), recursive=True)
        for f in files:
            if "/corrections/blocked-passages.md" in f: continue
            for i, ln in enumerate(LN.iter_lines(f, errors="replace"), 1):
                if "[BLOCKED:" in ln:
                    hits += 1; m = re.search(r"wip/[^;\]\s]+", ln); cap = m.group(0) if m else ""
                    reg = "registered" if (cap and cap in s) else "NOT registered"
                    print(f"{f}:{i}: {reg}: {ln.strip()[:160]}")
    print(f"{hits} markers")
def apply(bid, summary_file, note=None, guidance=True):
    s = load_queue()
    m = re.search(rf"^\| {re.escape(bid)} \| (.+?) \|$", s, re.M)
    if not m: sys.exit(f"{bid} not in queue")
    cells = [c.strip() for c in m.group(0).strip("|").split("|")]
    _, date, task, source, deliv, about, cap, status, applied = cells[:9]
    summary = LN.read_text(summary_file).strip().replace("\n", " ")
    # find the deliverable: the note named, else the marker that cites the capture file
    target = note
    if not target:
        for f in glob.glob("videos/*.md") + glob.glob("books/*.md") + glob.glob("research/*.md"):
            if cap and cap in LN.read_text(f): target = f; break
    if not target: sys.exit("deliverable not found; pass --note")
    t = LN.read_text(target)
    pat = re.compile(r"\[BLOCKED:[^\]]*" + re.escape(cap) + r"[^\]]*\]") if cap else re.compile(r"\[BLOCKED:[^\]]*\]")
    if not pat.search(t): sys.exit(f"marker for {bid} not found in {target}")
    rep = f"owner's summary, entered {today}: {summary}"
    t, k = pat.subn(rep, t, count=1)
    t = re.sub(r"attribution: n/a \(pointer\); chain: 1: ([^()]+?) \(n/a\)\.", lambda mm: f"attribution: owner's paraphrase, entered {today} (blocked output, tools/filter-blocks.md); chain: 1: {mm.group(1)} (basis not stated).", t, count=1)
    LN.write_text(target, t)
    # guidance row
    if guidance and "## Open questions" in t and f"({bid})" not in t:
        i = t.find("## Open questions"); j = t.find("\n## ", i + 5); block = t[i:j if j > 0 else len(t)]
        rows = re.findall(r"^\| (\d+) \|", block, re.M); n = max(int(x) for x in rows) + 1 if rows else 1
        last = list(re.finditer(r"^\| \d+ \|.*$", block, re.M))
        row = (f"| {n} | guidance | own: the database owner, {today} | The passage at {source} could not be restated by an agent: an API output filter blocked it ({bid}); the owner's summary stands in its place at {deliv} and the owner has the source. "
               f"Future edits keep the passage to the owner's summary and pointer rows; a quotation is never reconstructed from the summary. | other; {source} | unknown | standing | | own: the database owner, instruction of {today} | {today} |")
        if last:
            pos = i + last[-1].end(); t = t[:pos] + "\n" + row + t[pos:]
            LN.write_text(target, t)
    s = s.replace(m.group(0), m.group(0).rsplit("| open |", 1)[0] + f"| done | {today} {target} |" if "| open |" in m.group(0) else m.group(0))
    LN.write_text(Q, s)
    print(f"{bid}: summary spliced into {target} ({k} marker); queue row marked done")
def listq(open_only):
    s = load_queue()
    for ln in s.split("\n"):
        if ln.startswith("| BP-") and (not open_only or "| open |" in ln): print(ln[:220])
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    if a[0] == "register": register(a[1])
    elif a[0] == "scan": scan(a[1:])
    elif a[0] == "apply":
        sf = a[a.index("--summary") + 1]; nt = a[a.index("--note") + 1] if "--note" in a else None
        apply(a[1], sf, nt, guidance="--no-guidance" not in a)
    elif a[0] == "list": listq("--open" in a)
    else: sys.exit(__doc__)
