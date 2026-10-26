#!/usr/bin/env python3
"""Match one note against the open questions of every OTHER note and the open leads in the register.

Usage: python3 tools/match_leads.py videos/<note>.md [--db notes.db] [--top N] [--all]

Reads notes.db only (run `python3 tools/build_db.py` first; no network, never writes). Builds the note's
term set from its Claims ledger (Claim cells) and People table (names): proper nouns and places (words the
note capitalises mid-sentence), people's names from the People table, and distinctive terms (three or more
letters, not a stopword, and found in few notes' ledgers). Every open or checked question in another note's
`## Open questions` table and every open or checked lead in research/leads-and-inferences.md is scored by
the number of terms it shares with the note (Question plus What would settle it; Lead plus What would
settle it), ties broken by rarity. Prints the top N (default 25; --all for every hit) with the file and row
number, so each match can be promoted to the register or closed by hand."""
import os, re, sys, math, sqlite3
from collections import Counter

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
STOP = set("""the and for that this with from have has had was were are been being not but they them their there
then than what when where which while who whom whose why how into onto over under about above after again against
all any both each few more most other some such only own same very can will just should would could may might must
shall does did doing done its his her hers him she he you your yours our ours out off one two three four five six
seven eight nine ten also said says say saying like even ever never still yet because though although whether
upon within without between through during before until since across along among per via here those these
something anything nothing everything someone anyone everyone thing things way ways lot lots much many
first second last new old own yes okay well really think know knew known see seen get got make made made
tell told asked ask asks answer answered question questions note notes episode video recording host guest
does did whether whose which what who why""".split())
WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]*(?:'[A-Za-z]+)?")

def norm(w):
    w = w.lower()
    return w[:-2] if w.endswith("'s") else w

def words(text):
    return [norm(w) for w in WORD.findall(text or "") if len(norm(w)) >= 3 and norm(w) not in STOP]

def proper_nouns(text):
    """Words capitalised mid-sentence, and capitalised more often than not in the text."""
    caps, low, out = Counter(), Counter(), set()
    for m in WORD.finditer(text or ""):
        w = m.group(0); (caps if w[0].isupper() else low)[norm(w)] += 1
        if not w[0].isupper() or len(norm(w)) < 3 or norm(w) in STOP: continue
        before = text[:m.start()].rstrip(" \t")[-1:]
        if before and before not in "\n.!?:\"“(*[|": out.add(norm(w))
    return {w for w in out if caps[w] > low[w]}

def surname(name):
    """Last capitalised word of a People-table name, ignoring parentheses and quotes."""
    ws = [x for x in WORD.findall(re.sub(r"\(.*?\)", "", name)) if x[0].isupper() and norm(x) not in STOP]
    return norm(ws[-1]) if ws and len(norm(ws[-1])) >= 3 and not name.lower().startswith(("the ", "unnamed", "an ", "a ")) else None

def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"): sys.exit(__doc__)
    db = args[args.index("--db") + 1] if "--db" in args else os.path.join(ROOT, "notes.db")
    top = None if "--all" in args else int(args[args.index("--top") + 1]) if "--top" in args else 25
    vid = os.path.basename(args[0])[:-3] if args[0].endswith(".md") else os.path.basename(args[0])
    con = sqlite3.connect(db)
    if not con.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone(): sys.exit(f"{vid}: not in {db}")
    # document frequency of each word across notes' ledgers, for distinctiveness
    df, nvid = Counter(), 0
    for v, in con.execute("SELECT id FROM videos"):
        nvid += 1
        df.update(set(words(" ".join(c for c, in con.execute("SELECT claim FROM claims WHERE video=?", (v,))))))
    claims = [c for c, in con.execute("SELECT claim FROM claims WHERE video=?", (vid,))]
    names = [n for n, in con.execute("SELECT name FROM mentions WHERE video=?", (vid,))]
    text = "\n".join(claims)
    terms = {}
    for w in set(words(text)):
        if df[w] <= max(2, 0.08 * nvid): terms[w] = "term"
    for w in proper_nouns(text):
        if df[w] <= 0.6 * nvid: terms[w] = "name"
    for n in names:
        if surname(n): terms[surname(n)] = "person"
    idf = {w: math.log((nvid + 1) / (df[w] + 1)) + 1 for w in terms}
    cands = []
    for v, file, n, q, s, st in con.execute("""SELECT o.video, v.file, o.n, o.question, o.settles, o.status
            FROM open_questions o JOIN videos v ON v.id = o.video
            WHERE o.video != ? AND lower(o.status) IN ('open','checked')  -- standing (guidance) and closed rows are excluded""", (vid,)):
        cands.append((f"{file} #{n}", st, q, set(words(f"{q} {s}"))))
    for n, lead, s, st in con.execute("SELECT n, lead, settles, status FROM leads WHERE lower(status) IN ('open','checked')"):
        cands.append((f"research/leads-and-inferences.md #{n}", st, lead, set(words(f"{lead} {s}"))))
    hits = []
    for where, st, q, ws in cands:
        shared = sorted((w for w in ws if w in terms), key=lambda w: -idf[w])
        if shared: hits.append((len(shared), sum(idf[w] for w in shared), where, st, q, shared))
    hits.sort(key=lambda h: (-h[0], -h[1], h[2]))
    print(f"{vid}: {len(terms)} terms ({sum(k != 'term' for k in terms.values())} names); "
          f"{len(cands)} open questions and leads elsewhere; {len(hits)} share a term")
    for k, _, where, st, q, shared in hits[:top]:
        q = re.sub(r"\s+", " ", q.replace("*", ""))
        print(f"{k:3d}  {where} [{st}]  shared: {', '.join(shared[:12])}{' ...' if len(shared) > 12 else ''}")
        print(f"     {q[:150]}{'...' if len(q) > 150 else ''}")

if __name__ == "__main__":
    main()
