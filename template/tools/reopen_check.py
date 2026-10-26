#!/usr/bin/env python3
"""Reopen rule (added 2026-10-01): a `contradicts` cross-check that cites an answered open-question row
or lead reopens it to `checked`. This tool finds the candidates from notes.db and, with --apply, edits the
rows: Status becomes checked (closed and checked rows only), and Answer gains
"Reopened <date>: contradicted by <note> cross-check <n> (<verdict>)". Without --apply it only writes
research/corrections/reopen-candidates.md. Usage: python3 tools/reopen_check.py [--apply]
Citation forms recognised in a cross-check's cells: "open question N", "OQ N", "open questions N" after a note
link or name (the cross-check's elsewhere cell names the note), and "lead N" / "leads N".
"""
import sqlite3, re, os, sys, datetime, argparse
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--db", default=os.path.join(ROOT, "notes.db")); a = ap.parse_args()
con = sqlite3.connect(a.db); today = datetime.date.today().isoformat()
oq = {(v, int(n)): (st, q) for v, n, st, q in con.execute("select video, n, status, question from open_questions") if str(n).isdigit()}
ld = {int(n): (st, q) for n, st, q in con.execute("select n, status, lead from leads") if str(n).isdigit()}
def note_stem(text):
    m = LN.NOTE_LINK_RE.search(text); return m.group(1) if m else None   # form L3
cands = []
for v, n, kind, this_note, elsewhere, verdict, note in con.execute("select video, n, kind, this_note, elsewhere, verdict, note from cross_checks where kind='contradicts'"):
    text = " ".join(str(x or "") for x in (elsewhere, note))
    stem = note_stem(text)
    for m in re.finditer(r"\b(?:open questions?|OQ)\s*(\d+)", text, re.I):
        key = (stem, int(m.group(1)))
        if stem and key in oq and oq[key][0] in ("checked", "closed"): cands.append(("oq", stem, int(m.group(1)), oq[key][0], oq[key][1], v, n, verdict))
    for m in re.finditer(r"\bleads?\s+(\d+)\b", text, re.I):
        k = int(m.group(1))
        if k in ld and ld[k][0] in ("checked", "closed"): cands.append(("lead", "leads-and-inferences", k, ld[k][0], ld[k][1], v, n, verdict))
seen = set(); cands = [c for c in cands if not (c[:3] in seen or seen.add(c[:3]))]
out = [f"# Reopen candidates (tools/reopen_check.py, {today})", "", "Answered rows cited by a `contradicts` cross-check elsewhere. Rule (schema section 9): such a citation reopens the row to checked; the earlier answer stays and the reopening is noted. With --apply the rows are edited.", "", "| Kind | Where | Status now | Question or lead | Contradicting cross-check | Verdict |", "|---|---|---|---|---|---|"]
for kind, stem, num, st, q, v, n, verdict in cands:
    out.append(f"| {kind} | {stem} {num} | {st} | {str(q)[:120].replace('|','/')} | {v} cross-check {n} | {str(verdict)[:160].replace('|','/')} |")
os.makedirs(os.path.join(ROOT, "research/corrections"), exist_ok=True)
LN.write_text(os.path.join(ROOT, "research/corrections/reopen-candidates.md"), "\n".join(out) + "\n"); print(f"{len(cands)} candidates written to research/corrections/reopen-candidates.md")
if a.apply:
    done = 0
    for kind, stem, num, st, q, v, n, verdict in cands:
        if kind == "oq":
            path = next((p for p in (os.path.join(ROOT, "videos", stem + ".md"), os.path.join(ROOT, "books", stem + ".md")) if os.path.exists(p)), None)
            if not path: continue
            s = LN.read_text(path); i = s.find("## Open questions")
            if i < 0: continue
            m = LN.row_match(s[i:], num, tail=r" .*$")   # form R2
            if not m or f"Reopened" in m.group(0): continue
            c = LN.split_spaced(m.group(0)); c[-1] = c[-1].rstrip(" |")
            if len(c) < 8: continue
            c[6] = "checked"; c[7] = (c[7] + " " if c[7].strip() else "") + f"Reopened {today}: contradicted by [{v}]({v}.md) cross-check {n}."
            s = s[:i] + s[i:].replace(m.group(0), " | ".join(c) + " |", 1); LN.write_text(path, s); done += 1
        else:
            p = os.path.join(ROOT, "research/leads-and-inferences.md"); s = LN.read_text(p)
            m = LN.row_match(s, num, tail=r" .*$")
            if not m or "Reopened" in m.group(0): continue
            c = LN.split_spaced(m.group(0)); c[-1] = c[-1].rstrip(" |")
            if len(c) < 9: continue
            c[6] = "checked"; c[7] = (c[7] + " " if c[7].strip() else "") + f"Reopened {today}: contradicted by [{v}](../videos/{v}.md) cross-check {n}."
            s = s.replace(m.group(0), " | ".join(c) + " |", 1); LN.write_text(p, s); done += 1
    print(f"applied: {done} rows reopened")
