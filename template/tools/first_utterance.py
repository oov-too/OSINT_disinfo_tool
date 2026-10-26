#!/usr/bin/env python3
"""First-utterance register (owner, 2026-10-14; tools/narratives.md section 8d; tools/intake-policy.md rule 1).
The register research/first-utterance-register.md is a corpus-level object: one row per claim cluster, with the earliest held telling,
the earliest known public telling, the catalyst that precedes the earliest held one, and the pages that use it. Intake updates it
(--apply <report.json>, from the report's `first_telling_rows`); --refresh recomputes the held side from notes.db; the narrative
pages read it (--narratives joins each page's nodes to clusters and writes research/first-utterance.md).
Usage:
  python3 tools/first_utterance.py --build            seed clusters from the narrative pages' nodes (keeps existing ids; adds new clusters only)
  python3 tools/first_utterance.py --refresh          recompute earliest held telling, tellings, catalyst and status for every cluster
  python3 tools/first_utterance.py --apply <report>   add an intake report's first_telling_rows (cluster id or `new: <claim>`; row; date; venue)
  python3 tools/first_utterance.py --narratives       per-page report joined to the register (research/first-utterance.md)
  python3 tools/first_utterance.py --terms "<phrase>" every held telling of a phrase, by date
  python3 tools/first_utterance.py --catalysts        check research/catalysts.md against held timeline rows
  python3 tools/first_utterance.py --supersede FU-14=FU-1 [FU-27=FU-1 ...] [--cite] [--dry]
                                                      a merge ruling (7b2, 2026-10-24): each left ID is kept (IDs are permanent) with Status
                                                      `superseded by <right> (<date>)`, its Rows and Pages joined to the right ID's; with --cite
                                                      every citation of a left ID in the notes (videos/, books/), subjects/ and research/*.md (the
                                                      register itself, research/tasks/ and snapshots excepted) is rewritten to the right ID.
                                                      A superseded row is never refreshed, matched or reported; --apply sends an item naming it to
                                                      its successor. Re-running is a no-op.
Rows in the register: | ID | Event | Claim | Rows | Earliest held telling | Earliest known public telling | Catalyst before held | Tellings | Pages | Status |
Status: the pack's held label (here `pre-2017 held`: a held telling predates the threshold catalyst, 2017-12-16), `late` (event before the threshold year, no held telling before the threshold), `known earlier not held`
(an earlier public telling is recorded but not yet intaken), `first telling held` (the earliest known telling is held), `recent` (event in the threshold year or later). The threshold is the pack's pack.toml [catalysts]."""
import re, sys, os, glob, sqlite3, datetime, json, collections
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0, "tools")
from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import packload   # the pack's catalysts page and threshold catalyst (pack.toml [catalysts]; moved 2026-10-22)
REG = "research/first-utterance-register.md"; NYT = packload.threshold_date()
HELD = packload.threshold_label(); RECENT_FROM = NYT[:4] + "-01-01"   # the status of a telling held before the threshold catalyst, and the first recent event day (the pack's threshold; phase 4 handoff 4)
CITE = LN.CITE_XC_RE   # form C4
STOP = set("the a an and or of to in on at for by with from as is are was were be been it its this that these those his her their them he she they which who whom when where what how into over under after before between against about told tells telling says said say one two three first second new old per via not no yes then than also only both all any each more most such some other same own".split())
def iso(s):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if m: return m.group(0)
    m = re.search(r"\b(19\d\d|20\d\d)\b", s or ""); return (m.group(1) + "-07-01") if m else None
def event_iso(s):
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", s or ""); return (m.group(1) + "-01-01") if m else None
def db(): con = sqlite3.connect("file:notes.db?mode=ro", uri=True); con.row_factory = sqlite3.Row; return con
def note_dates(con): return {r["id"]: (iso(r["recorded"]) or iso(r["uploaded"]) or "9999-12-31") for r in con.execute("select id, recorded, uploaded from videos")}
def catalysts():
    out = []
    for line in LN.iter_lines(packload.catalysts_page()):
        m = re.match(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", line)
        if m: out.append(dict(date=m.group(1), name=m.group(2), what=m.group(3), keys=[k.strip() for k in m.group(4).split(";") if k.strip()]))
    return sorted(out, key=lambda c: c["date"])
def toks(s): return {w for w in re.findall(r"[a-z0-9']+", (s or "").lower()) if len(w) > 3 and w not in STOP}
SUPERSEDED_RE = re.compile(r"^superseded by (FU-\d+)")
def successor(r):
    m = SUPERSEDED_RE.match(r.get("Status", "") or ""); return m.group(1) if m else None
# ---------- register io ----------
COLS = ["ID", "Event", "Claim", "Rows", "Earliest held telling", "Earliest known public telling", "Catalyst before held", "Tellings", "Pages", "Status"]
def load():
    rows = []
    if not os.path.exists(REG): return rows
    for line in LN.iter_lines(REG):
        if not line.startswith("| FU-"): continue
        cells = LN.split_row(line)
        if len(cells) < len(COLS): cells += [""] * (len(COLS) - len(cells))
        rows.append(dict(zip(COLS, cells[:len(COLS)])))
    return rows
def save(rows, note=""):
    head = ["# First-utterance register", "", "A corpus-level register (tools/intake-policy.md rule 1; tools/narratives.md section 8d): one row per claim cluster, maintained at intake and read by the narrative pages. `Earliest held telling` is recomputed from notes.db by `python3 tools/first_utterance.py --refresh` (the citing note's recorded date; a document's own date). `Earliest known public telling` is written by intake (`--apply <report>`) or by hand from research/early-tellings-review.md, as `date; venue; [note row] if held`. `Catalyst before held` is the newest row of research/catalysts.md preceding the earliest held telling: it could have supplied the telling. Status: " + HELD + "; late; known earlier not held; first telling held; recent. Rows is a `;`-separated list of `[note kind n]` citations; Pages lists the narrative pages whose nodes join the cluster. Never renumber an ID; add rows at the end.", "", f"Last written {datetime.date.today().isoformat()}. {note}", "", "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    body = ["| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in COLS) + " |" for r in rows]
    LN.write_text(REG, "\n".join(head + body) + "\n")
# ---------- build ----------
def narrative_pages(): return sorted(p for p in glob.glob("research/narrative-*.md") if not any(x in p for x in ("synchrony", "rival", "register", "history")))
def page_nodes():
    import narratives as N
    out = []
    for p in narrative_pages():
        txt = LN.read_text(p); stem = os.path.basename(p)[:-3].replace("narrative-", "")
        for row in N.table(N.section(txt, "Nodes")):
            if not (row.get("#") or "").strip().isdigit(): continue
            cites = sorted({f"[{m.group(1)} {m.group(2)} {m.group(3)}]" for m in CITE.finditer((row.get("rows", "") or "") + " " + (row.get("node", "") or ""))})
            out.append(dict(page=stem, n=row["#"].strip(), date=row.get("date", ""), text=(row.get("node", "") or "").split(". ")[0][:180], cites=cites))
    return out
def build():
    rows = load(); nodes = page_nodes()
    # existing clusters: match a node to a cluster by shared citations (>=2) or by claim-token jaccard >= 0.5 with same event year
    def key(r): return set(c.strip() for c in r["Rows"].split(";") if c.strip())
    assigned = 0; new = 0
    for nd in nodes:
        cs = set(nd["cites"]); yr = (event_iso(nd["date"]) or "")[:4]; best = None; bs = 0
        for r in rows:
            if successor(r): continue
            shared = len(cs & key(r)); jac = len(toks(nd["text"]) & toks(r["Claim"])) / max(1, len(toks(nd["text"]) | toks(r["Claim"])))
            score = shared * 2 + (jac * 4 if (r["Event"][:4] == yr) else 0)
            if (shared >= 2 or (jac >= 0.5 and r["Event"][:4] == yr)) and score > bs: best, bs = r, score
        tag = f"{nd['page']}:{nd['n']}"
        if best:
            if tag not in best["Pages"].split(", "): best["Pages"] = ", ".join([x for x in best["Pages"].split(", ") if x] + [tag])
            best["Rows"] = "; ".join(sorted(key(best) | cs)); assigned += 1
        else:
            rows.append({"ID": f"FU-{len(rows) + 1}", "Event": (nd["date"] or "")[:40], "Claim": nd["text"], "Rows": "; ".join(sorted(cs)), "Earliest held telling": "", "Earliest known public telling": "", "Catalyst before held": "", "Tellings": "", "Pages": tag, "Status": ""}); new += 1
    save(rows, f"--build: {assigned} nodes joined existing clusters, {new} new clusters."); print(f"register: {len(rows)} clusters ({new} new, {assigned} nodes joined)"); refresh()
# ---------- refresh ----------
def refresh():
    con = db(); nd = note_dates(con); cats = catalysts(); rows = load()
    for r in rows:
        if successor(r): continue   # a superseded cluster keeps its row and status (a merge ruling)
        notes = sorted({m.group(1) for m in CITE.finditer(r["Rows"])})
        dated = sorted((nd.get(n, "9999-12-31"), n) for n in notes)
        held = f"{dated[0][0]}; [{dated[0][1]}]" if dated else ""
        r["Earliest held telling"] = held; r["Tellings"] = str(len(notes))
        if dated:
            before = [c for c in cats if c["date"] <= dated[0][0]]; r["Catalyst before held"] = f"{before[-1]['name']} ({before[-1]['date']})" if before else ""
        ev = event_iso(r["Event"]); known = r["Earliest known public telling"].strip()
        if ev and ev >= RECENT_FROM: st = "recent"
        elif dated and dated[0][0] < NYT: st = HELD
        elif known and CITE.search(known): st = "first telling held"
        elif known.lower().startswith("candidate:"): st = "candidate not held"
        elif known: st = "known earlier not held"
        elif ev: st = "late"
        else: st = ""
        r["Status"] = st
    save(rows, "--refresh run."); c = collections.Counter(r["Status"] for r in rows); print("refresh:", dict(c))
# ---------- apply an intake report ----------
def apply(path):
    rep = json.load(open(path)); items = rep.get("first_telling_rows") or []; rows = load(); n = 0
    for it in items:
        cid = str(it.get("cluster", "")).strip(); row = it.get("row", ""); date = it.get("date", ""); venue = it.get("venue", "")
        entry = "; ".join(x for x in (date, venue, row) if x)
        ids = {r["ID"]: r for r in rows}; seen = set()
        while cid in ids and successor(ids[cid]) and cid not in seen: seen.add(cid); cid = successor(ids[cid])   # to the successor of a merge
        if cid.lower().startswith("new:"):
            claim = cid[4:].strip()[:180]   # idempotent (2026-10-23, the pilot run: a re-run of an integration added the same cluster again)
            if any(r["Claim"] == claim and (not row or row in r["Rows"]) for r in rows): continue
            rows.append({"ID": f"FU-{len(rows) + 1}", "Event": it.get("event", "")[:40], "Claim": cid[4:].strip()[:180], "Rows": row, "Earliest held telling": "", "Earliest known public telling": entry, "Catalyst before held": "", "Tellings": "", "Pages": "", "Status": ""}); n += 1
        else:
            for r in rows:
                if r["ID"] == cid:
                    if row and row not in r["Rows"]: r["Rows"] = "; ".join(x for x in [r["Rows"], row] if x)
                    cur = r["Earliest known public telling"].strip(); curd = (re.search(r"\d{4}-\d{2}-\d{2}", cur) or [None])
                    if not cur or (date and (not re.search(r"\d{4}-\d{2}-\d{2}", cur) or date < re.search(r"\d{4}-\d{2}-\d{2}", cur).group(0))): r["Earliest known public telling"] = entry
                    n += 1
    save(rows, f"--apply {os.path.basename(path)}: {n} items."); print(f"applied {n} first-telling items from {path}"); refresh()
# ---------- narratives report ----------
def narratives():
    rows = load(); by = {}
    for r in rows:
        if successor(r): continue
        for tag in r["Pages"].split(", "):
            if tag: by[tag] = r
    lines = ["# First-utterance tests on the narrative pages", "", f"Built {datetime.date.today().isoformat()} by tools/first_utterance.py --narratives from {REG} ({len(rows)} clusters). Each node is joined to its register cluster; the register is maintained at intake (tools/intake-policy.md rule 1) and this report only reads it. A node whose cluster is `late` has no held telling before {NYT} and no earlier telling recorded; `known earlier not held` names what to intake; `first telling held` means the earliest known telling is in the database.", ""]
    summ = []
    for p in narrative_pages():
        stem = os.path.basename(p)[:-3].replace("narrative-", ""); tags = sorted((k for k in by if k.startswith(stem + ":")), key=lambda k: int(k.split(":")[1]))
        c = collections.Counter(by[k]["Status"] for k in tags); summ.append((stem, len(tags), c))
        lines += [f"## {stem}: {len(tags)} nodes; " + ", ".join(f"{k} {v}" for k, v in c.most_common()), "", "| Node | Cluster | Event | Earliest held | Earliest known | Catalyst before held | Tellings | Status |", "|---|---|---|---|---|---|---|---|"]
        order = {"late": 0, "candidate not held": 1, "known earlier not held": 2, "first telling held": 3, HELD: 4, "recent": 5, "": 6}
        for k in sorted(tags, key=lambda k: (order.get(by[k]["Status"], 9), int(k.split(":")[1]))):
            r = by[k]; lines.append(f"| {k.split(':')[1]} | {r['ID']} | {r['Event'][:30]} | {r['Earliest held telling'][:60]} | {r['Earliest known public telling'][:70]} | {r['Catalyst before held']} | {r['Tellings']} | {r['Status']} |")
        lines.append("")
    lines.insert(3, "| Page | Nodes | late | candidate not held | known earlier not held | first telling held | " + HELD + " | recent |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(f"| {s} | {n} | {c.get('late',0)} | {c.get('candidate not held',0)} | {c.get('known earlier not held',0)} | {c.get('first telling held',0)} | {c.get(HELD,0)} | {c.get('recent',0)} |" for s, n, c in summ) + "\n")
    LN.write_text("research/first-utterance.md", "\n".join(lines) + "\n"); print("written research/first-utterance.md")
def supersede(pairs, cite=False, dry=False):
    """The merge ruling: {left: right}; returns (rows marked, citations rewritten by file)."""
    rows = load(); ids = {r["ID"]: r for r in rows}; today = datetime.date.today().isoformat(); marked = 0
    for left, right in pairs.items():
        if left not in ids or right not in ids: sys.exit(f"--supersede: no register row {left if left not in ids else right}")
        if left == right or successor(ids[right]): sys.exit(f"--supersede: {right} is itself superseded or the same as {left}")
        a, b = ids[left], ids[right]
        if successor(a) == right: continue
        b["Rows"] = "; ".join(sorted({x.strip() for x in (b["Rows"] + ";" + a["Rows"]).split(";") if x.strip()}))
        b["Pages"] = ", ".join(sorted({x.strip() for x in (b["Pages"] + "," + a["Pages"]).split(",") if x.strip()}, key=lambda t: (t.split(":")[0], int(t.split(":")[1]) if t.split(":")[-1].isdigit() else 0)))
        a["Status"] = f"superseded by {right} ({today})"; marked += 1
    changed = {}
    if cite:
        rx = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(pairs, key=len, reverse=True)) + r")(?!\d)")
        files = sorted(glob.glob("videos/*.md") + glob.glob("books/*.md") + glob.glob("subjects/*.md") + glob.glob("research/*.md"))
        for f in files:
            if os.path.normpath(f) == os.path.normpath(REG): continue
            t = LN.read_text(f); t2, k = rx.subn(lambda m: pairs[m.group(1)], t)
            if k:
                changed[f] = k
                if not dry: LN.write_text(f, t2)
    if not dry and marked: save(rows, f"--supersede: {marked} clusters superseded (a merge ruling).")
    print(f"supersede: {marked} rows marked" + (" (dry run)" if dry else "") + (f"; citations rewritten: {sum(changed.values())} in {len(changed)} files" if cite else ""))
    for f, k in changed.items(): print(f"  {f}: {k}")
    return marked, changed
def terms(phrases):
    con = db(); nd = note_dates(con)
    for ph in phrases:
        print(f"=== '{ph}'"); hits = []
        for r in con.execute("select video, n, speaker, claim from claims where lower(claim) like ?", (f"%{ph.lower()}%",)): hits.append((nd.get(r["video"], "?"), r["video"], f"claims {r['n']}", r["speaker"], (r["claim"] or "")[:140]))
        for r in con.execute("select video, n, event from timeline where lower(event) like ?", (f"%{ph.lower()}%",)): hits.append((nd.get(r["video"], "?"), r["video"], f"tl {r['n']}", "", (r["event"] or "")[:140]))
        for h in sorted(hits): print(f"{h[0]}  [{h[1]} {h[2]}] {h[3]}: {h[4]}")
        if not hits: print("  no held telling")
def check_catalysts():
    con = db()
    for c in catalysts():
        y = c["date"][:4]; found = sum(con.execute("select count(*) from timeline where (sortable like ? or date_stated like ?) and event like ?", (y + "%", "%" + y + "%", "%" + k + "%")).fetchone()[0] for k in c["keys"])
        print(f"{'ok ' if found else 'MISSING'} {c['date']} {c['name']}: {found} timeline rows in {y} matching {c['keys']}")
if __name__ == "__main__":
    a = sys.argv[1:]
    if "--build" in a: build()
    elif "--refresh" in a: refresh()
    elif "--apply" in a: apply(a[a.index("--apply") + 1])
    elif "--narratives" in a: narratives()
    elif "--terms" in a: terms(a[a.index("--terms") + 1:])
    elif "--catalysts" in a: check_catalysts()
    elif "--supersede" in a:
        pairs = dict(x.split("=", 1) for x in a[a.index("--supersede") + 1:] if "=" in x and not x.startswith("--"))
        supersede(pairs, "--cite" in a, "--dry" in a)
    else: print(__doc__)
