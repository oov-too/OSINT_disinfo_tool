#!/usr/bin/env python3
"""List cross-check rows that cite a claim since corrected (either side) but carry no audit marker
(point / settled / revised / adopted / was).  These are the rows a correction round leaves undecided:
run after every correction pass and hand the list to an audit batch (wip/xc-audit-1001/RUBRIC.md).
usage: python3 tools/xc_unaudited.py [--json out.json]"""
import sqlite3, re, json, sys, collections
con = sqlite3.connect("notes.db")
corr = {}
for v, n, note in con.execute("select video, n, note from claims"):
    m = re.search(r"[Cc]orrected (\d{4}-\d{2}-\d{2})", note or "")
    if m: corr[(v, str(n))] = m.group(1)
link = re.compile(r"\]\((?:\.\./)?(?:(?:videos|books)/)?([^)#/]+?)\.md\)")
def nums(t, word):
    out = []
    for m in re.finditer(word + r"\s+([\d]+(?:\s*(?:,|and|to)\s*[\d]+)*)", t or ""):
        seg = m.group(1); to = re.match(r"^(\d+)\s*to\s*(\d+)$", seg)
        if to: out += [str(k) for k in range(int(to.group(1)), int(to.group(2)) + 1)]
        else: out += [x.strip() for x in re.split(r"\s*(?:,|and)\s*", seg) if x.strip().isdigit()]
    return out
files = {v: f for v, f in con.execute("select id, file from videos")}
out = []
for v, n, k, this, els, ver, note, point, settled, revised, was in con.execute(
        "select video, n, kind, this_note, elsewhere, verdict, note, point, settled, revised, was from cross_checks"):
    if point or settled or revised or was or re.search(r"adopted \d{4}", note or ""): continue
    targets = []; last = None
    for m in link.finditer(els or ""):
        if last: targets.append((last[0], els[last[1]:m.start()]))
        last = (m.group(1), m.end())
    if last: targets.append((last[0], els[last[1]:]))
    cor = [(t, c, corr[(t, c)]) for t, tail in targets for c in nums(tail, r"claims?") if (t, c) in corr]
    own = [(v, c, corr[(v, c)]) for c in nums(this, r"rows?") if (v, c) in corr]
    if cor or own:
        out.append(dict(note=v, file=files.get(v, ""), n=n, kind=k, this=this, elsewhere=els, verdict=ver, note_cell=note,
                        flags=(["corrected-target"] if cor else []) + (["corrected-own"] if own else []), corrected=cor + own))
by = collections.Counter(r["note"] for r in out)
print(f"unaudited rows citing a corrected claim: {len(out)} across {len(by)} notes")
for v, c in by.most_common(10): print(f"  {v}: {c}")
if "--json" in sys.argv:
    p = sys.argv[sys.argv.index("--json") + 1]; json.dump(out, open(p, "w"), ensure_ascii=False, indent=0); print("wrote", p)
