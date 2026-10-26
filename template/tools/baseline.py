#!/usr/bin/env python3
"""Platform baseline (phase 0 of tools/platform-plan.md, 2026-10-22): a frozen description of the corpus that the
refactor's regression test compares against. Writes research/platform-baseline.json; --check recomputes and diffs.

Usage:
  python3 tools/baseline.py                       write the baseline (run tools/build_db.py first)
  python3 tools/baseline.py --check               recompute and report differences (exit 1 on any)

What it records: every table's row count in notes.db; per-note counts (claims, audit, timeline, people, works, object watch,
quotes, open questions, cross-checks) and word count for every note; word count and sha256 of every research, subject
and tools markdown page; the list of tools and workflows; the register sizes (leads, relations, first-utterance
clusters by status, object register entries, actor register rows). Agent cost tables live in tools/intake-staged.md and the
Token Efficiency Lessons doc and are not repeated here.
"""
import sqlite3, json, os, sys, glob, hashlib, re, collections
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
OUT = "research/platform-baseline.json"
import packload
OBJ_TABLE = packload.name("table.object_watch")   # the object watch table (core object_watch; the pack may keep an earlier name)

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
def words(p):
    return len(LN.read_text(p, errors="replace").split())

def build():
    b = {"frozen": "2026-10-22", "tables": {}, "notes": {}, "pages": {}, "tools": {}, "registers": {}}
    con = sqlite3.connect("notes.db")
    for (t,) in con.execute("select name from sqlite_master where type='table' and name not like 'rows_fts%' order by name"):
        b["tables"][t] = con.execute(f"select count(*) from {t}").fetchone()[0]
    cols = {"claims": "claims", "audit_rows": "audit", "timeline": "timeline", "people": "people", "works": "works",
            OBJ_TABLE: packload.name("baseline.object"), "quotes": "quotes", "open_questions": "open_questions", "cross_checks": "cross_checks"}
    per = collections.defaultdict(dict)
    for table, key in cols.items():
        vcol = [c[1] for c in con.execute(f"pragma table_info({table})") if c[1] in ("video", "note", "slug")]
        if not vcol: continue
        for v, n in con.execute(f"select {vcol[0]}, count(*) from {table} group by 1"):
            per[v][key] = n
    for p in sorted(glob.glob("videos/*.md") + glob.glob("books/*.md")):
        stem = os.path.basename(p)[:-3]
        d = dict(per.get(stem, {})); d["words"] = words(p); d["sha"] = sha(p)
        b["notes"][stem] = d
    for p in sorted(glob.glob("research/*.md") + glob.glob("subjects/*.md") + glob.glob("tools/*.md")):
        b["pages"][p] = {"words": words(p), "sha": sha(p)}
    b["tools"] = {"python": sorted(os.path.basename(p) for p in glob.glob("tools/*.py")),
                  "retired": sorted(os.path.basename(p) for p in glob.glob("tools/retired/*.py")),
                  "workflows": sorted(os.path.basename(p) for p in glob.glob("tools/workflows/*.js")),
                  "other": sorted(os.path.basename(p) for p in glob.glob("tools/*") if not p.endswith((".py", ".md")) and os.path.isfile(p))}
    reg = {}
    lines = lambda p: LN.iter_lines(p, errors="replace") if os.path.exists(p) else []   # a register a new project has not written yet counts 0 (phase 7b)
    reg["leads"] = sum(1 for l in lines("research/leads-and-inferences.md") if re.match(r"^\| \d+ \|", l))
    reg["relations"] = sum(1 for l in lines("research/relations-register.md") if l.startswith("| ") and not l.startswith("| From") and not l.startswith("|---"))
    fu = collections.Counter()
    for l in lines("research/first-utterance-register.md"):
        if l.startswith("| FU-"):
            c = LN.split_row(l)
            fu[c[-1].split("(")[0].strip() if c else ""] += 1
    reg["first_utterance"] = dict(fu)
    # the pack's object register ([objects] register) and actor register ([actors] register); the keys are the core's, or the pack's
    # earlier names ([names]; 7b2, 2026-10-23)
    for key, rel in ((packload.name("baseline.object_entries"), packload.pack().get("objects", {}).get("register")), (packload.name("baseline.actor_rows"), packload.pack().get("actors", {}).get("register"))):
        reg[key] = sum(1 for l in LN.iter_lines(rel, errors="replace") if re.match(r"^\| \d+ \|", l)) if rel and os.path.exists(rel) else 0
    b["registers"] = reg
    return b

def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: out.append(f"+ {path}/{k}")
            elif k not in b: out.append(f"- {path}/{k}")
            else: out += diff(a[k], b[k], f"{path}/{k}")
    elif a != b:
        out.append(f"~ {path}: {a} -> {b}")
    return out

if __name__ == "__main__":
    if "--check" in sys.argv:
        if not os.path.exists(OUT):   # a new project (phase 7b): nothing is frozen until the baseline is written
            print(f"no baseline at {OUT}: freeze one with `python3 tools/baseline.py` (after tools/build_db.py), then --check compares against it")
            sys.exit(2)
        old = json.load(open(OUT)); new = build(); new["frozen"] = old["frozen"]
        d = diff(old, new)
        for line in d: print(line)
        print(f"{len(d)} difference(s) against {OUT}")
        sys.exit(1 if d else 0)
    b = build(); json.dump(b, LN.open_write(OUT), indent=1)
    print(f"wrote {OUT}: {len(b['tables'])} tables, {len(b['notes'])} notes, {len(b['pages'])} pages, {len(b['tools']['python'])} tools")
    print("tables:", {k: v for k, v in b["tables"].items() if v})
    print("registers:", b["registers"])
