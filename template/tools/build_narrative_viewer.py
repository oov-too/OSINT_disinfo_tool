#!/usr/bin/env python3
"""Build the narrative viewer page from the narrative pages, the register, the synchrony pages and the pack.
Usage: python3 tools/build_narrative_viewer.py [--pack <narrative folder>] [--out research/figures/narratives-viewer.html] [--no-grid]
The narrative folder (the synchrony index the grid reads) is the pack's [narratives] folder unless --pack names one. When it is not
there (a copy of the project, a recipient's folder before its first narrative run) the viewer is built without the synchrony grid, with a notice (owner ruling 2026-10-26: the
viewer is always produced); --no-grid asks for that explicitly.
Reads research/narrative-*.md and the pack's synchrony-index.md; writes one self-contained local HTML file (template:
tools/narrative_viewer_template.html, data inlined as JSON) that opens from the folder with no network: no external script,
stylesheet or font (tools/platform-plan.md, phase 5). Its title, views, lane names, about line and first page are the pack's
display settings (pack.toml [display.viewer]); the synchrony years are the pack's [eras]. Re-run after every narrative phase."""
import re, os, sys, json, glob, datetime
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0, "tools")
import narratives as nt
import packload   # the viewer's display settings (pack.toml [display.viewer]) and the narrative years ([eras]); phase 5, 2026-10-22
LN = nt.LN   # the parser library (tools/ledger/notes.py, phase 2), through narratives
def arg(n, d): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
PACK = arg("--pack", packload.pack().get("narratives", {}).get("folder", "")); OUT = arg("--out", "research/figures/narratives-viewer.html")
IDX = os.path.join(PACK, "synchrony-index.md") if PACK else ""
if not (IDX and os.path.exists(IDX)) and "--no-grid" not in sys.argv:
    # owner ruling 2026-10-26: the viewer is produced for the user automatically; without a narrative folder it is built without the
    # synchrony grid (the pages, register and ledgers still show), with a notice, instead of being skipped
    print(f"build_narrative_viewer: no narrative folder (pack.toml [narratives] folder " + (f"{PACK!r} has no synchrony-index.md" if PACK else "is not set")
          + "): building the viewer without the synchrony grid; set the folder to a narrative pack (tools/narrative_pack.py) for the grid.")
    sys.argv.append("--no-grid")
def sections(txt):
    return LN.split_sections(txt)   # form S5b
def meta_block(txt):
    m = re.search(r"^\| \*\*.*?(?=^## )", txt, re.S | re.M); return m.group(0) if m else ""
data = {"built": datetime.date.today().isoformat(), "narratives": [], "synchrony": [], "register": {}, "grid": {}, "dense": [], "recurring": []}
for p in sorted(glob.glob("research/narrative-*.md")):
    stem = os.path.basename(p)[:-3]; txt = LN.read_text(p); secs = sections(txt); md = nt.meta(txt)
    title = next((l[2:].strip() for l in txt.split("\n") if l.startswith("# ")), stem)
    if stem == "narrative-register":
        data["register"] = {"title": title, "meta": md, "sections": secs, "words": len(txt.split())}; continue
    if "narrative-rival-" in stem: continue
    if "synchrony" in stem:
        data["synchrony"].append({"id": stem, "era": md.get("Era", stem.replace("narrative-synchrony-", "")), "title": title, "meta": md,
            "lanes": secs.get("Lanes in this era", ""), "windows": nt.table(secs.get("Windows", "")), "co": nt.table(secs.get("Co-movements", "")),
            "contradictions": nt.table(secs.get("Contradictions", "")), "signals": nt.table(secs.get("Signals", "")), "orgs": nt.table(secs.get("Organisations", "")),
            "builders": secs.get("For the builders", ""), "words": len(txt.split())}); continue
    r = nt.parse(p)
    comp = {str(l["n"]): l for l in r["ledger"]}
    ledger = []
    for row in nt.table(secs.get("Contradiction ledger", "")):
        l = comp.get(row.get("#", ""), {}); row["_downstream_computed"] = l.get("downstream_computed"); row["_rows"] = l.get("rows", []); row["_leads"] = l.get("leads", []); ledger.append(row)
    data["narratives"].append({"id": stem, "title": title, "meta": md, "mode": r["mode"], "parent": r["parent"], "thesis_line": r["thesis"], "alternative_line": r["alternative"],
        "span": r["span"], "lanes": r["lanes"], "status": r["status"], "words": r["words"], "score_lines": r["score_lines"],
        "thesis": secs.get("Thesis", ""), "deltas": secs.get("Deltas against the parent", ""), "nodes": nt.table(secs.get("Nodes", "")), "ledger": ledger,
        "synchrony": nt.table(secs.get("Synchrony", "")), "carriers": nt.table(secs.get("Carriers", "")), "interests": nt.table(secs.get("Interests", "")),
        "objections": secs.get("Objections", ""), "scorecard": secs.get("Score card", ""), "forks": secs.get("Forks", ""), "tests": secs.get("Tests", ""),
        "leads": nt.table(secs.get("Leads returned", "")), "relations": nt.table(secs.get("Relations returned", ""))})
# recurring contradictions (same grouping as narratives.py --recurring, change 24)
res = [nt.parse(p) for p in sorted(glob.glob("research/narrative-*.md")) if "synchrony" not in p and "narrative-rival-" not in p and not p.endswith("narrative-register.md")]
def family(r): return re.sub(r"-fork-\d+$", "", r["page"])
keyed = []
for r in res:
    for l in r["ledger"]:
        keys = set(("row",) + x for x in l["rows"]) | set(("lead", x) for x in l["leads"])
        if keys: keyed.append((r, l, keys))
seen = set()
for i, (r1, l1, k1) in enumerate(keyed):
    group = [(r1, l1)]
    for r2, l2, k2 in keyed[i + 1:]:
        if k1 & k2: group.append((r2, l2))
    if len(group) < 2: continue
    sig = tuple(sorted((g[0]["page"], g[1]["n"]) for g in group))
    if sig in seen: continue
    seen.add(sig); fams = {family(g[0]) for g in group}
    data["recurring"].append({"contradiction": l1["contradiction"], "kind": "cross-mainline" if len(fams) > 1 else "inherited", "members": [{"page": g[0]["page"], "row": g[1]["n"], "side": g[1]["side"], "flare": g[1]["flare"][:160]} for g in group]})
data["recurring"].sort(key=lambda g: (g["kind"] != "cross-mainline", -len(g["members"])))
# synchrony grid from the pack index
idx = LN.read_text(IDX) if IDX and os.path.exists(IDX) else ""   # empty with --no-grid and no folder: the grid stays empty
m = re.search(r"## Counts by window and lane\n\n(.*?)\n\n## Dense", idx, re.S)
for line in (m.group(1).split("\n")[2:] if m else []):
    c = LN.split_row(line)
    if len(c) >= 10: data["grid"][c[0]] = {L: int(c[i + 1] or 0) for i, L in enumerate("ABCDEFGH")}
m = re.search(r"## Dense windows.*?\n\n(\| Rank.*?)(?:\n\n|\Z)", idx, re.S)
for line in (m.group(1).split("\n")[2:] if m else []):
    c = LN.split_row(line)
    if len(c) >= 5: data["dense"].append({"window": c[1], "lanes": int(c[2]), "rows": int(c[3])})
V = packload.display("viewer"); _E = packload.pack().get("eras", {}); _mains = packload.pack().get("narratives", {}).get("mainlines", [])
TITLE = V["title"] or packload.ledger_title() + " Narratives"
data["lane_names"] = dict(V["lanes"])
data["display"] = {"title": TITLE, "about": V["about"], "views": V["views"], "default_page": V["default_page"] or ("narrative-" + _mains[0] if _mains else ""),
                   "synchrony_from": _E.get("narrative_from", 1933), "quarter_from": _E.get("narrative_quarter_from", "")}
tpl = LN.read_text(os.path.join(_T, "narrative_viewer_template.html"))
blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
_t = TITLE.replace("&", "&amp;").replace("<", "&lt;")
html = tpl.replace("/*__DATA__*/null", blob).replace("/*__TITLE__*/", _t)
assert not re.search(r"<(?:script|link)[^>]+(?:src|href)=[\"']?https?:", html), "the viewer must not load anything from a network"
LN.write_text(OUT, html)
print(OUT, f"{len(html)/1e6:.2f} MB;", len(data["narratives"]), "narratives,", len(data["synchrony"]), "synchrony pages,", len(data["recurring"]), "recurring groups,", len(data["grid"]), "windows")
