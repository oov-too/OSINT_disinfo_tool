#!/usr/bin/env python3
"""Builder digest for one thesis seed (tools/narratives.md, token rule of 2026-10-09): the builder's entry point instead of the seven
synchrony pages and the evidence pack. Usage: python3 tools/narrative_digest.py <seed> [--pack wip/narratives-1008/pack] [--out <file.md>]
                                                                             [--tl-cap 250] [--claims-cap 150]
Reads research/narrative-synchrony-*.md, the pack (seeds.md for the terms; contradictions.md), notes.db (read-only). Writes one markdown
file (default wip/narratives-1008/digests/<seed>.md). Contents, each with its cap stated: the seven '### <seed>' subsections under
'For the builders'; the co-movements, contradictions, signals and organisations rows that bear on the seed (the 'Bears on seeds' cell
names it, or a cell matches a term); the pack's contradiction nodes matching the terms; node candidates: timeline rows matching the
terms, grouped by era, and claims rows matching the terms, firsthand and program-record first. The full pages and the pack stay
available on demand; the agent reads this file by shell and never passes it through its own output (tools/filter-blocks.md section 9)."""
import re, os, sys, glob, sqlite3
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0, "tools")
import narratives as nt
def arg(n, d): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
seed = sys.argv[1]; PACK = arg("--pack", "wip/narratives-1008/pack"); OUT = arg("--out", f"wip/narratives-1008/digests/{seed}.md")
TLCAP = int(arg("--tl-cap", 250)); CLCAP = int(arg("--claims-cap", 150))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
seeds = open(os.path.join(PACK, "seeds.md"), encoding="utf-8").read()
m = re.search(r"^## " + re.escape(seed) + r": ([^\n]+)\n\n(.*?)\n\n- Terms: ([^\n]+)", seeds, re.M | re.S)
if not m: sys.exit(f"seed {seed} not in {PACK}/seeds.md")
title, thesis, terms = m.group(1), m.group(2), [t.strip() for t in m.group(3).split(",")]
tl = [t for t in terms if len(t) > 3]; tlow = [t.lower() for t in tl]
def hits(text): t = (text or "").lower(); return [x for x in tlow if x in t]
out = [f"# Builder digest: {seed} ({title})", "", f"Thesis seed: {thesis}", "", f"Terms: {', '.join(terms)}", "", "Built by tools/narrative_digest.py; every section states its cap, and every row beyond a cap is still listed in index form (owner ruling 2026-10-09: nothing is omitted to save tokens). Full synchrony pages (research/narrative-synchrony-*.md), the pack (wip/narratives-1008/pack/) and the evidence pack (wip/narratives-1008/packs/<seed>.md) remain available on demand; grep them, never read them whole.", ""]
# 1 the For-the-builders subsections
out.append(f"## 1. What each era offers this seed (the synchrony pages' '### {seed}' subsections, in full)")
co_rows = []; con_rows = []; sig_rows = []; org_rows = []
for p in sorted(glob.glob("research/narrative-synchrony-*.md")):
    txt = open(p, encoding="utf-8").read(); era = os.path.basename(p)[len("narrative-synchrony-"):-3]
    fb = nt.section(txt, "For the builders"); mm = re.search(r"^### " + re.escape(seed) + r"[^\n]*\n(.*?)(?=^### |\Z)", fb, re.M | re.S)
    out.append(f"\n### {era}\n"); out.append(mm.group(1).strip() if mm else "(no subsection)")
    for r in nt.table(nt.section(txt, "Co-movements")):
        if seed in (r.get("bears on seeds", "") or "").lower() or hits(" ".join(r.values())): co_rows.append((era, r))
    for r in nt.table(nt.section(txt, "Contradictions")):
        if seed in (r.get("bears on seeds", "") or "").lower() or hits(r.get("node", "") + " " + r.get("parties", "")): con_rows.append((era, r))
    for r in nt.table(nt.section(txt, "Signals")):
        if hits(r.get("carrier", "") + " " + r.get("wall (rows, ground)", "")): sig_rows.append((era, r))
    for r in nt.table(nt.section(txt, "Organisations")):
        if hits(r.get("body", "") + " " + r.get("event", "")): org_rows.append((era, r))
def tbl(rows, cols, cap):
    if not rows: return ["(none)"]
    lines = ["| Era | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for era, r in rows[:cap]: lines.append("| " + era + " | " + " | ".join((r.get(c.lower(), "") or "").replace("|", "/")[:420] for c in cols) + " |")
    if len(rows) > cap: lines.append(f"(cap {cap}; {len(rows) - cap} more rows in the synchrony pages)")
    return lines
out += ["", f"## 2. Co-movements that bear on this seed ({len(co_rows)}; cap 60)"] + tbl(co_rows, ["#", "Window(s)", "Lanes", "What moves together", "Independent roots", "Rows", "Reading"], 60)
out += ["", f"## 3. Contradictions in the synchrony pages that bear on this seed ({len(con_rows)}; cap 80)"] + tbl(con_rows, ["#", "Window", "Node", "Side A (rows)", "Side B (rows)", "Parties", "Insider or agency", "Provisional impact", "Flare"], 80)
out += ["", f"## 4. Signals on this seed's carriers ({len(sig_rows)}; cap 60)"] + tbl(sig_rows, ["#", "Carrier", "Window", "Wall (rows, ground)", "Near the wall (rows)", "Reading"], 60)
out += ["", f"## 5. Organisations ({len(org_rows)}; cap 40)"] + tbl(org_rows, ["Body", "Event", "Window", "Rows", "Roots"], 40)
# 6 pack contradiction nodes matching the terms
pk = open(os.path.join(PACK, "contradictions.md"), encoding="utf-8").read().split("\n")
prow = [l for l in pk if l.startswith("| ") and l[2].isdigit() and hits(l)]
out += ["", f"## 6. Pack contradiction nodes matching the terms ({len(prow)}; cap 80, ranked by the pack's provisional impact)"] + ["| Rank | Score | Source | Note / row | Date | Party | insider | agency | Kind | Event or lead | Against | div tags |", "|---|---|---|---|---|---|---|---|---|---|---|---|"] + [l[:700] for l in prow[:80]]
# 7 node candidates from notes.db
con = sqlite3.connect("file:notes.db?mode=ro", uri=True); con.row_factory = sqlite3.Row
like = " or ".join("lower(event) like ?" for _ in tl); params = [f"%{t}%" for t in tlow]
rows = con.execute(f"select video, n, date_stated, sortable, event, speaker_basis, chain, agreement_kind from timeline where sortable >= '1933' and ({like}) order by sort_key", params).fetchall()
# first-utterance register rows that touch this seed (owner 2026-10-14: the register is maintained at intake and read here)
try:
    fu = [l for l in open("research/first-utterance-register.md", encoding="utf-8") if l.startswith("| FU-")]
    hit = [l.strip() for l in fu if (seed + ":") in l or any(t.lower() in l.lower() for t in terms)]
    out += ["", f"## 6b. First-utterance register rows for this seed ({len(hit)} of {len(fu)}; research/first-utterance-register.md, columns ID | Event | Claim | Rows | Earliest held telling | Earliest known public telling | Catalyst before held | Tellings | Pages | Status). Cite a cluster in a node's Rows cell as [fu FU-n]; a node whose cluster is `late` rests on a telling the catalyst could have supplied."] + hit
except FileNotFoundError: pass
out += ["", f"## 7. Node candidates: dated timeline rows matching the terms, 1933 on ({len(rows)}; cap {TLCAP}, spread over eras)"]
import packload; ERAS = packload.eras("synchrony")   # the pack's era boundaries (pack.toml [eras]; moved 2026-10-22)
by = {e[0]: [] for e in ERAS}
for r in rows:
    y = re.match(r"~?(\d{4})", r["sortable"] or ""); y = int(y.group(1)) if y else None
    for name, a, b in ERAS:
        if y and a <= y <= b: by[name].append(r); break
per = max(20, TLCAP // 7)
for name, _, _ in ERAS:
    rs = by[name]; out.append(f"\n### {name} ({len(rs)} rows{'; showing ' + str(per) if len(rs) > per else ''})")
    for r in rs[:per]: out.append(f"- [{r['video']} tl {r['n']}] {r['date_stated'] or r['sortable']}: {(r['event'] or '')[:220]} ({(r['speaker_basis'] or '')[:80]}) agree={r['agreement_kind'] or 'new'}")
    if len(rs) > per:  # owner ruling 2026-10-09 (proposal 29): no row is omitted; the rest follow in index form, one line each
        out.append(f"  Index of the remaining {len(rs) - per} rows (read every line; open a row with: python3 tools/narratives.py --row '<note> tl <n>'):")
        for r in rs[per:]: out.append(f"  - [{r['video']} tl {r['n']}] {(r['date_stated'] or r['sortable'] or '')[:12]}: {(r['event'] or '')[:90]} agree={r['agreement_kind'] or 'new'}")
like2 = " or ".join("lower(claim) like ?" for _ in tl)
crows = con.execute(f"select video, n, time, speaker, topic, claim, source_class, move from claims where ({like2}) order by case source_class when 'firsthand' then 0 when 'program-record' then 1 when 'read' then 2 else 3 end", params).fetchall()
out += ["", f"## 8. Claims rows matching the terms ({len(crows)}; cap {CLCAP}, firsthand and program-record first)"]
for r in crows[:CLCAP]: out.append(f"- [{r['video']} claims {r['n']}] {r['speaker']} ({r['source_class']}, {r['topic']}, {r['move']}): {(r['claim'] or '')[:220]}")
if len(crows) > CLCAP:  # proposal 29: nothing omitted; the rest in index form
    out.append(f"\nIndex of the remaining {len(crows) - CLCAP} claims rows (read every line; open a row with: python3 tools/narratives.py --row '<note> claims <n>'):")
    for r in crows[CLCAP:]: out.append(f"- [{r['video']} claims {r['n']}] {r['speaker']} ({r['source_class']}): {(r['claim'] or '')[:90]}")
open(OUT, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(OUT, len(" ".join(out).split()), "words;", "co", len(co_rows), "contra", len(con_rows), "signals", len(sig_rows), "orgs", len(org_rows), "pack", len(prow), "tl", len(rows), "claims", len(crows))
