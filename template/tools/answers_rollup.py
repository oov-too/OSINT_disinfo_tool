#!/usr/bin/env python3
"""Roll-up of answered questions and leads (added 2026-10-01).
Reads notes.db (run tools/build_db.py first) and writes research/answered-questions.md:
counts by status, then every answered row (status other than open) newest first, with
where it lives, the question, the status, who answered it and when, plus the remaining test
for checked rows. Usage: python3 tools/answers_rollup.py [--db notes.db] [--out research/answered-questions.md]
"""
import sqlite3, argparse, datetime, os, re, sys
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
ap = argparse.ArgumentParser(); ap.add_argument("--db", default=os.path.join(ROOT, "notes.db")); ap.add_argument("--out", default=os.path.join(ROOT, "research/answered-questions.md"))
a = ap.parse_args(); con = sqlite3.connect(a.db)
def rebase(t):
    """links written note-relative (bare 'name.md', correct inside videos/ or books/) are rebased to research/ (added 2026-10-02)"""
    def fix(m):
        name = m.group(1)
        for d in ("videos", "books"):
            if os.path.exists(os.path.join(ROOT, d, name)): return f"](../{d}/{name}{m.group(2) or ''})"
        return m.group(0)
    return re.sub(r"\]\(([^/)#\s]+\.md)(#[^)]*)?\)", fix, str(t or ""))
def cut(t, n=150):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(t or ""))  # links to plain text: cells come from notes with note-relative paths
    t = re.sub(r"\s+", " ", t).strip().replace("|", "/"); return t if len(t) <= n else t[:n-1] + "…"
oq = con.execute("select video, n, question, settles, status, answer, answered_by, answered_on from open_questions").fetchall()
ld = con.execute("select n, lead, settles, status, answer, answered_by, answered_on from leads").fetchall()
def counts(rows, i):
    c = {}
    for r in rows: c[r[i] or "?"] = c.get(r[i] or "?", 0) + 1
    return c
L = ["# Answered questions and leads", "", f"Generated {datetime.date.today().isoformat()} by tools/answers_rollup.py from notes.db. One line per answered row, newest first. Statuses: checked (partial answer, remaining test in the last column), closed (nothing remains), superseded (moved; see the pointer), standing (guidance, never closes). Refused writes are in research/corrections/answer-refusals.md; reopened rows are marked by tools/reopen_check.py.", ""]
co, cl = counts(oq, 4), counts(ld, 3)
L += ["## Counts", "", "| Table | open | checked | closed | standing | superseded | total |", "|---|---|---|---|---|---|---|",
      f"| Open questions (all notes) | {co.get('open',0)} | {co.get('checked',0)} | {co.get('closed',0)} | {co.get('standing',0)} | {co.get('superseded',0)} | {len(oq)} |",
      f"| Leads register | {cl.get('open',0)} | {cl.get('checked',0)} | {cl.get('closed',0)} | {cl.get('standing',0)} | {cl.get('superseded',0)} | {len(ld)} |", ""]
rows = []
for v, n, q, settles, st, ans, by, on in oq:
    if st in ("checked", "closed", "superseded"): rows.append((on or "", f"[{v}](../videos/{v}.md) OQ {n}" if os.path.exists(os.path.join(ROOT, "videos", v + ".md")) else f"[{v}](../books/{v}.md) OQ {n}", q, st, by, settles if st == "checked" else ""))
for n, lead, settles, st, ans, by, on in ld:
    if st in ("checked", "closed", "superseded"): rows.append((on or "", f"[lead {n}](leads-and-inferences.md)", lead, st, by, settles if st == "checked" else ""))
rows.sort(key=lambda r: r[0], reverse=True)
by_src = {}
for r in rows:
    k = re.sub(r"\(.*?\)", "", str(r[4] or "")).strip()[:60] or "(blank)"; by_src[k] = by_src.get(k, 0) + 1
L += ["## Answered by (top sources)", "", "| Answered by | Rows |", "|---|---|"] + [f"| {cut(k, 80)} | {v} |" for k, v in sorted(by_src.items(), key=lambda x: -x[1])[:25]] + [""]
L += ["## Answered rows, newest first", "", "| Answered on | Where | Question or lead | Status | Answered by | Remaining test (checked rows) |", "|---|---|---|---|---|---|"]
for on, where, q, st, by, settles in rows: L.append(f"| {rebase(on) or '?'} | {where} | {cut(q)} | {st} | {cut(by, 90)} | {cut(settles, 110)} |")
LN.write_text(a.out, "\n".join(L) + "\n"); print(f"wrote {a.out}: {len(rows)} answered rows; OQ {co}; leads {cl}")
