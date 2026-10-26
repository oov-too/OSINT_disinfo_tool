#!/usr/bin/env python3
"""Build the evidence pack for an Investigation (tools/investigation.md, stage 1): everything notes.db holds on a thread,
row-cited, in one markdown file that the strand agents read before they open a note.
Usage:
  python3 tools/evidence_pack.py --out <path.md> --title "<thread>" --terms "Lisle memo" "Vaněček" "Vanecek" ... \
      [--people "Petra Vanecek" "Gareth Lisle" ...] [--per-note 80] [--max-rows 1500] [--db notes.db] [--pages]
Reads notes.db only (opened read-only; run `python3 tools/build_db.py` first) and, with --pages, greps research/*.md,
subjects/*.md and the pack's further index pages ([tools.evidence_pack] extra_page_files) for the terms (cap per file). Never writes anything but --out.
Matching is a case-insensitive substring match on each term (give accented and unaccented spellings as separate terms:
"Vaněček" and "Vanecek"). Every section states its cap and how many rows it dropped, so a reader never mistakes a
truncated pack for the whole record (no silent caps). Sections:
  1 Sources held (notes with matching claims, with counts per term)
  2 Claims (video, row, time, speaker, topic, claim, class, move, attribution, chain), grouped by note
  3 Audit rows on the thread (declines and partials first)
  4 Dated timeline rows (sorted), with Agreement
  5 Cross-checks already written (kind, verdict, both sides)
  6 Open questions and leads (status, what would settle it, answer)
  7 Relations among the thread's people (edges touching --people, and every edge between two of them)
  8 Works and documents named (works table)
  9 Object register entries and object-watch rows (the section titles are the pack's)
 10 Research-page lines (with --pages): the speaker ledgers, the actor register, the timeline era pages, registers
"""
import sqlite3, sys, os, re, glob, datetime

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
import packload; _D = packload.tool_data("evidence_pack")   # the pack's object register titles and further index pages ([tools.evidence_pack]; phase 7b)

def arg(name, default=None, many=False):
    if name not in sys.argv: return default
    i = sys.argv.index(name)
    if not many: return sys.argv[i + 1]
    vals = []
    for v in sys.argv[i + 1:]:
        if v.startswith("--"): break
        vals.append(v)
    return vals

out = arg("--out"); title = arg("--title", "thread"); terms = arg("--terms", [], many=True)
people = arg("--people", [], many=True); per_note = int(arg("--per-note", 80)); max_rows = int(arg("--max-rows", 1500))
dbp = arg("--db", os.path.join(ROOT, "notes.db")); pages = "--pages" in sys.argv
if not out or not terms:
    sys.exit(__doc__)
db = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True); db.row_factory = sqlite3.Row

def like_clause(cols):
    return " OR ".join(f"lower({c}) LIKE ?" for c in cols for _ in terms), [f"%{t.lower()}%" for c in cols for t in terms]

def q(sql, params=()):
    return db.execute(sql, params).fetchall()

def esc(s, n=None):
    s = (s or "").replace("\n", " ").replace("|", "/")
    return s if n is None or len(s) <= n else s[:n] + "…"

L = [f"# Evidence pack: {title}", "",
     f"Built {datetime.date.today().isoformat()} by tools/evidence_pack.py from {os.path.relpath(dbp, ROOT)}; terms: {', '.join(terms)}; people: {', '.join(people) or 'none given'}. "
     "Every row below is a term match, never a finding: read the cited note and row before using it. Caps are stated per section; a dropped row is still in notes.db."]

# 1 sources
w, p = like_clause(["c.claim", "c.note", "c.attribution", "c.chain"])
rows = q(f"SELECT c.video, v.title, v.uploaded, COUNT(*) AS n FROM claims c LEFT JOIN videos v ON v.id = c.video WHERE {w} GROUP BY c.video ORDER BY n DESC", p)
L += ["", "## 1. Sources held (notes with matching claims rows)", "", f"{len(rows)} notes.", "", "| Note | Uploaded | Matching rows | Title |", "|---|---|---|---|"]
for r in rows: L.append(f"| {r['video']} | {r['uploaded'] or ''} | {r['n']} | {esc(r['title'], 120)} |")

# 2 claims
w, p = like_clause(["claim", "note", "attribution", "chain"])
rows = q(f"SELECT * FROM claims WHERE {w} ORDER BY video, CAST(n AS REAL)", p)
L += ["", f"## 2. Claims rows ({len(rows)} matches; cap {per_note} per note, {max_rows} total)", ""]
by = {}
for r in rows: by.setdefault(r["video"], []).append(r)
total = 0; dropped = 0
for vid, rs in by.items():
    L += ["", f"### {vid} ({len(rs)} rows)", "", "| Row | Time | Speaker | Topic | Claim | Class | Move | Attribution and chain |", "|---|---|---|---|---|---|---|---|"]
    for r in rs[:per_note]:
        if total >= max_rows: dropped += 1; continue
        total += 1
        L.append(f"| {r['n']} | {r['time']} | {esc(r['speaker'], 40)} | {esc(r['topic'], 40)} | {esc(r['claim'], 420)} | {r['source_class']} | {r['move']} | {esc(r['attribution'], 160)}; {esc(r['chain'], 160)} |")
    if len(rs) > per_note: dropped += len(rs) - per_note; L.append(f"| … | | | | {len(rs) - per_note} more rows in this note not shown (cap) | | | |")
L.append(f"\nShown {total}; dropped by caps {dropped}.")

# 3 audit rows
w, p = like_clause(["question", "answer", "basis", "note"])
rows = q(f"SELECT * FROM audit_rows WHERE {w} ORDER BY CASE WHEN move LIKE 'closed%' THEN 0 WHEN move='partial' THEN 1 ELSE 2 END, video, CAST(n AS REAL)", p)
L += ["", f"## 3. Candour audit rows on the thread ({len(rows)}; declines and partials first; cap {max_rows // 3})", "", "| Note | Row | Time | Asked by | Question | Answer | Move | Basis | Note |", "|---|---|---|---|---|---|---|---|---|"]
for r in rows[:max_rows // 3]:
    L.append(f"| {r['video']} | {r['n']} | {r['time']} | {esc(r['asked_by'], 30)} | {esc(r['question'], 200)} | {esc(r['answer'], 260)} | {r['move']} | {esc(r['basis'], 80)} | {esc(r['note'], 160)} |")
if len(rows) > max_rows // 3: L.append(f"\n{len(rows) - max_rows // 3} more audit rows not shown (cap).")

# 4 timeline
w, p = like_clause(["event", "speaker_basis", "chain", "link", "agreement"])
rows = q(f"SELECT * FROM timeline WHERE {w} ORDER BY sort_key, video, n_sort", p)
L += ["", f"## 4. Dated timeline rows ({len(rows)}; sorted by date; cap {max_rows // 2})", "", "| Sortable | Date as stated | Event | Speaker, basis | Chain | Note, tl | Database link | Agreement |", "|---|---|---|---|---|---|---|---|"]
for r in rows[:max_rows // 2]:
    L.append(f"| {r['sortable']} | {esc(r['date_stated'], 60)} | {esc(r['event'], 260)} | {esc(r['speaker_basis'], 120)} | {esc(r['chain'], 120)} | {r['video']} tl {r['n']} | {esc(r['link'], 100)} | {esc(r['agreement'], 220)} |")
if len(rows) > max_rows // 2: L.append(f"\n{len(rows) - max_rows // 2} more timeline rows not shown (cap).")

# 5 cross-checks
w, p = like_clause(["this_note", "elsewhere", "note"])
rows = q(f"SELECT * FROM cross_checks WHERE {w} ORDER BY video, CAST(n AS REAL)", p)
L += ["", f"## 5. Cross-checks already written ({len(rows)}; cap {max_rows // 2})", "", "| Note | Row | Kind | This note | Elsewhere | Verdict | Note (custody, tag, markers) |", "|---|---|---|---|---|---|---|"]
for r in rows[:max_rows // 2]:
    L.append(f"| {r['video']} | {r['n']} | {r['kind']} | {esc(r['this_note'], 220)} | {esc(r['elsewhere'], 160)} | {r['verdict']} | {esc(r['note'], 300)} |")
if len(rows) > max_rows // 2: L.append(f"\n{len(rows) - max_rows // 2} more cross-check rows not shown (cap).")

# 6 open questions and leads
w, p = like_clause(["question", "settles", "answer", "bears_on"])
rows = q(f"SELECT * FROM open_questions WHERE {w} ORDER BY status, video, n", p)
L += ["", f"## 6a. Open questions in notes ({len(rows)}; cap {max_rows // 3})", "", "| Note | # | Kind | Asked by | Question | What would settle it | Status | Answer | Answered by, on |", "|---|---|---|---|---|---|---|---|---|"]
for r in rows[:max_rows // 3]:
    L.append(f"| {r['video']} | {r['n']} | {r['kind']} | {esc(r['asked_by'], 40)} | {esc(r['question'], 260)} | {esc(r['settles'], 200)} | {r['status']} | {esc(r['answer'], 220)} | {esc(r['answered_by'], 80)} {r['answered_on'] or ''} |")
w, p = like_clause(["lead", "settles", "answer", "sources"])
rows = q(f"SELECT * FROM leads WHERE {w} ORDER BY status, n", p)
L += ["", f"## 6b. Leads register rows ({len(rows)})", "", "| # | Kind | Asked by | Lead | Sources | What would settle it | Status | Answer | Answered by, on | Added |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['n']} | {r['kind']} | {esc(r['asked_by'], 50)} | {esc(r['lead'], 320)} | {esc(r['sources'], 120)} | {esc(r['settles'], 220)} | {r['status']} | {esc(r['answer'], 220)} | {esc(r['answered_by'], 80)} {r['answered_on'] or ''} | {r['added'] or ''} |")

# 7 relations
if people:
    pl = [x.lower() for x in people]
    rows = q("SELECT * FROM relations")
    touch = [r for r in rows if any(x in (r['a_canon'] or r['a'] or '').lower() or x in (r['b_canon'] or r['b'] or '').lower() for x in pl)]
    both = [r for r in touch if any(x in (r['a_canon'] or r['a'] or '').lower() for x in pl) and any(x in (r['b_canon'] or r['b'] or '').lower() for x in pl)]
    L += ["", f"## 7. Relations ({len(touch)} edges touch the named people; {len(both)} join two of them; the joined edges are listed first, then the rest up to the cap {max_rows // 2})", "", "| # | A | B | Kind | Hierarchy | When | What | Source | Chain | Confidence |", "|---|---|---|---|---|---|---|---|---|---|"]
    seen = set()
    for r in both + [r for r in touch if r not in both]:
        if len(seen) >= max_rows // 2: break
        if r['n'] in seen: continue
        seen.add(r['n'])
        L.append(f"| {r['n']} | {esc(r['a'], 50)} | {esc(r['b'], 50)} | {r['kind']} | {esc(r['hierarchy'], 60)} | {esc(r['when_'], 60)} | {esc(r['what'], 240)} | {esc(r['source'], 90)} | {esc(r['chain'], 120)} | {esc(r['confidence'], 30)} |")
    if len(touch) > len(seen): L.append(f"\n{len(touch) - len(seen)} more edges not shown (cap). Query a person with `python3 tools/relations.py \"<name>\"`.")
else:
    L += ["", "## 7. Relations", "", "No --people given; run `python3 tools/relations.py \"<name>\"` for each party."]

# 8 works
w, p = like_clause(["title", "author", "note"])
rows = q(f"SELECT * FROM works WHERE {w} ORDER BY kind, title", p)
L += ["", f"## 8. Works and documents named ({len(rows)}; cap {max_rows // 3})", "", "| Note | Title | Author | Kind | Time | Note |", "|---|---|---|---|---|---|"]
for r in rows[:max_rows // 3]:
    L.append(f"| {r['video']} | {esc(r['title'], 120)} | {esc(r['author'], 60)} | {r['kind']} | {r['time']} | {esc(r['note'], 220)} |")
w, p = like_clause(["lead"])
cd = q("SELECT video, n, claim, attribution FROM claims WHERE attribution LIKE 'document claimed%' OR attribution LIKE 'author named, work not named%' OR attribution LIKE 'publication named%'")
cdm = [r for r in cd if any(t.lower() in ((r['claim'] or '') + (r['attribution'] or '')).lower() for t in terms)]
L += ["", f"### Claimed-but-unnamed documents on the thread ({len(cdm)}; corroboration targets)", "", "| Note | Row | Claim | Attribution |", "|---|---|---|---|"]
for r in cdm[:200]: L.append(f"| {r['video']} | {r['n']} | {esc(r['claim'], 260)} | {esc(r['attribution'], 160)} |")

# 9 the object register
w, p = like_clause(["object", "who", "match"])
rows = q(f"SELECT * FROM register WHERE {w} ORDER BY n", p)
L += ["", f"## 9. {_D['register_title']} ({len(rows)})", "", "| # | Video | Time | Who | Object | Match | Strength |", "|---|---|---|---|---|---|---|"]
for r in rows[:200]: L.append(f"| {r['n']} | {esc(r['video'], 60)} | {r['timestamp']} | {esc(r['who'], 40)} | {esc(r['object'], 200)} | {esc(r['match'], 200)} | {r['strength']} |")
w, p = like_clause(["object", "witness", "note", "criteria"])
rows = q(f"SELECT * FROM {packload.name('table.object_watch')} WHERE {w} ORDER BY video", p)
L += ["", f"### {_D['watch_title']} ({len(rows)})", "", "| Note | Time | Object | Witness | Custody | Criteria | Strength | Entry | Note |", "|---|---|---|---|---|---|---|---|---|"]
for r in rows[:200]: L.append(f"| {r['video']} | {r['time']} | {esc(r['object'], 140)} | {esc(r['witness'], 40)} | {esc(r['custody'], 60)} | {esc(r['criteria'], 120)} | {r['strength']} | {r['register_entry']} | {esc(r['note'], 160)} |")

# 10 pages
if pages:
    L += ["", "## 10. Research-page and subject-page lines matching the terms (cap 40 lines per file; a line is a table row or a paragraph)", ""]
    files = sorted(glob.glob(os.path.join(ROOT, "research", "*.md")) + glob.glob(os.path.join(ROOT, "subjects", "*.md")))
    for idx in (os.path.join(ROOT, x) for x in _D["extra_page_files"]):
        if os.path.exists(idx): files.append(idx)
    for f in files:
        try: lines = open(f, encoding="utf-8").read().split("\n")
        except Exception: continue
        hits = [(i + 1, ln) for i, ln in enumerate(lines) if any(t.lower() in ln.lower() for t in terms)]
        if not hits: continue
        L += ["", f"### {os.path.relpath(f, ROOT)} ({len(hits)} lines)", ""]
        for i, ln in hits[:40]: L.append(f"- line {i}: {esc(ln, 500)}")
        if len(hits) > 40: L.append(f"- … {len(hits) - 40} more lines not shown (cap)")

open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"wrote {out}: {len(L)} lines, {sum(len(x) for x in L)} chars")
