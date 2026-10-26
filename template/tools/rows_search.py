#!/usr/bin/env python3
"""Full-text search over the held rows of notes.db (claims, timeline, audit, quotes, people), returning each matching row in the
citation form the agents use: [<note stem> claims N], [<stem> tl N], [<stem> audit N], [<stem> quote N], [<stem> people <name>].
Find the held row for a fact in one query instead of grepping the markdown or reading a note (tools/rows_search.md).

Usage: python3 tools/rows_search.py "<query>" [--note <stem glob>[,<glob>]] [--speaker <name>] [--table claims|timeline|audit|quote|people[,..]]
                                     [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--limit N] [--full] [--json] [--db PATH]

The query is FTS5 syntax passed through unchanged: words are ANDed; "a phrase in quotes" matches in order; OR, NOT, NEAR(a b, 5),
prefix* and column filters (text:, speaker:, date:, extra:, video:) all work. Results are ranked by bm25 (text weighted highest).
--from/--to compare against the row's own date for timeline rows and the note's Uploaded date for every other kind.
Default output, one row per line: citation | date cell | speaker cell | text cell trimmed to about 300 characters (--full: untrimmed).
--json prints a list of objects with every cell of the matching row from its own table. A summary line goes to stderr.
Reads notes.db only (built by tools/build_db.py, which rebuilds the rows_fts index on every run)."""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library: the citation form and the sort-key encoding (tools/ledger/notes.py)

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
DB = os.path.join(ROOT, "notes.db")
KINDS = {"claims": "claims", "claim": "claims", "timeline": "tl", "tl": "tl", "audit": "audit", "audit_rows": "audit",
         "quote": "quote", "quotes": "quote", "people": "people", "mentions": "people", "person": "people"}
TABLE = {"claims": "claims", "tl": "timeline", "audit": "audit_rows", "quote": "quotes", "people": "mentions"}
CITE = {"claims": "claims", "tl": "tl", "audit": "audit", "quote": "quote", "people": "people"}
TRIM = 300

def cite(kind, video, n):
    return LN.cite(kind, video, n)   # form C6

def date_key(d, end=False):
    """YYYY-MM-DD (or YYYY, YYYY-MM) to the timeline sort_key encoding (year + 1,000,000,000, ten digits)."""
    k = LN.date_key(d, end)   # form Q6b
    if k is None: sys.exit(f"--from/--to: expected YYYY-MM-DD, got {d!r}")
    return k

def trim(s, n=TRIM):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"

def full_row(con, kind, video, n):
    tab = TABLE[kind]
    if kind == "people": r = con.execute(f"SELECT * FROM {tab} WHERE video=? AND name=?", (video, n)).fetchone()
    else: r = con.execute(f"SELECT * FROM {tab} WHERE video=? AND n=?", (video, n)).fetchone()
    return {k: r[k] for k in r.keys()} if r else {}

def search(con, query, notes=None, speaker=None, kinds=None, d_from=None, d_to=None, limit=50):
    where = ["rows_fts MATCH ?"]; args = [query]
    if kinds:
        where.append("kind IN (" + ",".join("?" * len(kinds)) + ")"); args += kinds
    if notes:
        where.append("(" + " OR ".join("video GLOB ?" for _ in notes) + ")"); args += notes
    if speaker:
        where.append("lower(speaker) LIKE ?"); args.append(f"%{speaker.lower()}%")
    if d_from: where.append("sort_key >= ?"); args.append(date_key(d_from))
    if d_to: where.append("sort_key <= ?"); args.append(date_key(d_to, end=True))
    w = " AND ".join(where)
    total = con.execute(f"SELECT COUNT(*) FROM rows_fts WHERE {w}", args).fetchone()[0]
    # bm25 weights, one per column in table order: kind, video, n, date, speaker, text, extra, sort_key
    rows = con.execute(f"SELECT kind, video, n, date, speaker, text, extra FROM rows_fts WHERE {w} ORDER BY bm25(rows_fts, 0.0, 0.5, 0.5, 1.0, 2.0, 10.0, 3.0, 0.0) LIMIT ?", args + [limit]).fetchall()
    return total, rows

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", help="FTS5 query; phrase queries in quotes")
    ap.add_argument("--note", help="note stem glob, comma-separated for several (e.g. 'hi-*,ostley-gazette*')")
    ap.add_argument("--speaker", help="substring of the speaker, speaker/basis, asked-by or name cell, case-insensitive")
    ap.add_argument("--table", help="claims|timeline|audit|quote|people, comma-separated; default all")
    ap.add_argument("--from", dest="d_from", metavar="YYYY-MM-DD", help="timeline rows by event date, other rows by the note's Uploaded date")
    ap.add_argument("--to", dest="d_to", metavar="YYYY-MM-DD")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--full", action="store_true", help="print the text cell untrimmed")
    ap.add_argument("--json", action="store_true", help="print every cell of each matching row as JSON")
    ap.add_argument("--db", default=DB)
    a = ap.parse_args()
    kinds = None
    if a.table:
        kinds = []
        for t in a.table.split(","):
            t = t.strip().lower()
            if t not in KINDS: sys.exit(f"--table: unknown table {t!r}; use claims, timeline, audit, quote or people")
            kinds.append(KINDS[t])
    notes = [g.strip() for g in a.note.split(",") if g.strip()] if a.note else None
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    if not con.execute("SELECT name FROM sqlite_master WHERE name='rows_fts'").fetchone():
        sys.exit("notes.db has no rows_fts table; run python3 tools/build_db.py first")
    try:
        total, rows = search(con, a.query, notes, a.speaker, kinds, a.d_from, a.d_to, a.limit)
    except sqlite3.OperationalError as e:
        sys.exit(f"FTS5 query error: {e}\n(quote phrases, escape a bare hyphenated or punctuated term in double quotes, e.g. \"LISLE MEMO\" \"DC-0917\")")
    if a.json:
        out = []
        for r in rows:
            d = {"cite": cite(r["kind"], r["video"], r["n"]), "kind": r["kind"], "note": r["video"], "n": r["n"], "table": TABLE[r["kind"]]}
            d.update(full_row(con, r["kind"], r["video"], r["n"]))
            out.append(d)
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            text = re.sub(r"\s+", " ", r["text"] or "").strip() if a.full else trim(r["text"])
            parts = [cite(r["kind"], r["video"], r["n"]), trim(r["date"], 60), trim(r["speaker"], 60), text]
            print(" | ".join(p for p in parts if p != ""))
    print(f"{total} matching rows, showing {len(rows)} (query: {a.query!r}" + (f"; note {a.note}" if a.note else "") + (f"; speaker {a.speaker}" if a.speaker else "")
          + (f"; table {a.table}" if a.table else "") + (f"; from {a.d_from}" if a.d_from else "") + (f"; to {a.d_to}" if a.d_to else "") + ")", file=sys.stderr)

if __name__ == "__main__":
    main()
