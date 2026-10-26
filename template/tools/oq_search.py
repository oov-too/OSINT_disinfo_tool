#!/usr/bin/env python3
"""Search the held open questions and leads (notes.db tables open_questions and leads, which rows_search's FTS does not cover).
Usage: python3 tools/oq_search.py "<term>" ["<term2>" ...] [--all] [--status open|checked|closed|standing] [--limit N] [--json]
Terms are matched case-insensitively (LIKE) against the question or lead text, bears_on/sources and settles; several terms are ORed
unless --all (ANDed). Output: [<note stem> oq N] or [lead N] | status | text (trimmed) | settles (trimmed)."""
import sqlite3, sys, json, os
_T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _T)
from ledger.paths import root as _root; os.chdir(_root())
a = sys.argv[1:]; opts = {}; terms = []
i = 0
while i < len(a):
    if a[i] in ("--status", "--limit"): opts[a[i]] = a[i + 1]; i += 2
    elif a[i] in ("--all", "--json"): opts[a[i]] = True; i += 1
    else: terms.append(a[i]); i += 1
if not terms: sys.exit(__doc__)
c = sqlite3.connect("notes.db"); lim = int(opts.get("--limit", 40)); joiner = " AND " if opts.get("--all") else " OR "
def q(table, textcol, extra_cols, cite):
    where = joiner.join([f"(lower({textcol}) LIKE ? OR lower({extra_cols[0]}) LIKE ? OR lower(settles) LIKE ?)" for _ in terms])
    params = [p for t in terms for p in (f"%{t.lower()}%",) * 3]
    if opts.get("--status"): where = f"({where}) AND status = ?"; params.append(opts["--status"])
    cols = ("video, n" if table == "open_questions" else "n") + f", status, {textcol}, settles, kind"
    return [dict(zip([x.strip() for x in cols.split(",")], r), table=table) for r in c.execute(f"SELECT {cols} FROM {table} WHERE {where} LIMIT {lim}", params)]
rows = q("open_questions", "question", ["bears_on"], "oq") + q("leads", "lead", ["sources"], "lead")
if opts.get("--json"): print(json.dumps(rows, ensure_ascii=False, indent=1)); sys.exit()
for r in rows:
    cite = f"[{r['video']} oq {r['n']}]" if r["table"] == "open_questions" else f"[lead {r['n']}]"
    text = r.get("question") or r.get("lead") or ""
    print(f"{cite} | {r['status']} | {text[:220]} | settles: {(r.get('settles') or '')[:120]}")
print(f"{len(rows)} row(s)", file=sys.stderr)
