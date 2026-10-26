#!/usr/bin/env python3
"""Onboarding cross-check: does a new note answer standing questions, corroborate or contradict claims already in
the database, or fill someone else's decline? Run it after the note is written and tools/build_db.py has run.

Usage: python3 tools/onboard_check.py videos/<note>.md [--out PATH] [--db notes.db] [--top N] [--per K]

Reads notes.db only, opened read-only. Writes one markdown report to --out (default $TMPDIR/onboard_check/<note>.md;
note-writing agents pass their scratchpad) and a summary line to stdout; it writes nothing else. Term logic is
tools/match_leads.py's (imported), plus hyphen splitting. Shared terms are weighted: a surname or proper noun 2, a
first name 0, any other distinctive term 1. Three parts, each ranked by weight then rarity and cut at --top items
(default 60) with K candidate rows each (--per, default 3):
  A  Standing questions: open or checked `## Open questions` rows in OTHER notes and open or checked leads that
     share two terms with this note and weight 3 with one of its ledger rows, or that sit in a note with the same
     guest, or name the guest; each with its What would settle it and this note's best-matching ledger rows.
  B  Claims: for each ledger row of this note, the best row per other note on the same Topic sharing two terms,
     or on any Topic sharing weight 3 (two terms for the same guest in another note), side by side with note,
     row, time, speaker, source class, attribution and chain: candidate corroborations, contradictions, extensions.
  C  Declines: closed-outright or closed-subtle audit rows in other notes (monologue and narration mapping rows only
     when closed-outright) matching as in A, marked where research/declined-answered-elsewhere.md pairs them.
Every candidate is a term match, never a finding: read both sides before entering it under `## Cross-checks`
(tools/schema.md section 10), and leave out what you reject."""
import os, re, sys, math, sqlite3, tempfile, datetime
from collections import Counter
sys.dont_write_bytecode = True  # importing match_leads must not leave a __pycache__ in the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match_leads import ROOT, WORD, norm, words, proper_nouns, surname
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)

NOISE = set("""january february march april june july august september october november december monday tuesday
wednesday thursday friday saturday sunday mr mrs dr""".split())
SWEEP = os.path.join(ROOT, "research", "declined-answered-elsewhere.md")

def arg(args, flag, default): return args[args.index(flag) + 1] if flag in args else default
def clip(s, n=280):
    s = re.sub(r"\s+", " ", (s or "").replace("|", "/")).strip()
    return s if len(s) <= n else s[:n - 3] + "..."

def toks(text):
    """match_leads.words, plus the parts of hyphenated words (Havana-syndrome-type -> havana, syndrome, type),
    without contractions (i've, don't)."""
    return {w for w in set(words(text)) | set(words((text or "").replace("-", " "))) if "'" not in w}

def guest_surnames(con, vid):
    """Surnames of the non-host voices in this note's Speakers cell (plain two-to-four-word names only)."""
    host, speakers = con.execute("SELECT host, speakers FROM videos WHERE id=?", (vid,)).fetchone()
    hs = {surname(h) for h in re.split(r",| and ", re.sub(r"\(.*?\)", "", host or ""))} - {None}
    out = set()
    sp = re.split(r"\b(?:inserted )?clips? (?:of|from)\b|\bclips?:", speakers or "", flags=re.I)[0]  # drop clip voices: they are not guests
    for ch in re.sub(r"\(.*?\)", "", sp).split(","):
        ws = ch.strip().split()
        if 2 <= len(ws) <= 4 and all(w[0].isupper() for w in ws) and surname(ch) and surname(ch) not in hs: out.add(surname(ch))
    return out

def expand(spec):
    """'26 to 28' -> 26 27 28; '51, 66' -> 51 66."""
    out = []
    for part in re.split(r",|\band\b", spec):
        m = re.match(r"\s*(\d+)\s*(?:to\s*(\d+))?", part)
        if m: out += list(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    return out

def sweep_index(vid):
    """(video, audit n) -> where research/declined-answered-elsewhere.md pairs that decline."""
    idx, sec = {}, ""
    if not os.path.exists(SWEEP): return idx
    for line in LN.iter_lines(SWEEP):
        if line.startswith("## "): sec = line[3:].strip()[:45]
        c = LN.split_row(line) if line.startswith("|") else []
        if len(c) < 4 or not c[0].isdigit(): continue
        mine = " (this note already credited)" if vid in c[3] else ""
        for part in re.split(r"(?=\]\(\.\./videos/)", c[2])[1:]:
            m = LN.SWEEP_NOTE_RE.match(part)   # form L10
            if not m: continue
            v = m.group(1)
            for a in re.finditer(r"audit ((?:\d+(?:\s*(?:to|,|and)\s*)?)+)", part):
                for n in expand(a.group(1)): idx.setdefault((v, str(n)), []).append(f"'{sec}' row {c[0]}{mine}")
    return idx

def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"): sys.exit(__doc__)
    db = arg(args, "--db", os.path.join(ROOT, "notes.db")); top = int(arg(args, "--top", 60)); per = int(arg(args, "--per", 3))
    vid = os.path.basename(args[0]); vid = vid[:-3] if vid.endswith(".md") else vid
    out = arg(args, "--out", os.path.join(tempfile.gettempdir(), "onboard_check", vid + ".md"))
    con = sqlite3.connect(f"file:{os.path.abspath(db)}?mode=ro", uri=True)
    files = dict(con.execute("SELECT id, file FROM videos"))
    if vid not in files: sys.exit(f"{vid}: not in {db}; run tools/build_db.py first")
    by_vid = {}
    for r in con.execute("SELECT video, n, time, speaker, topic, claim, source_class, attribution, chain FROM claims"):
        by_vid.setdefault(r[0], []).append(r + (toks(r[5]),))
    nvid = len(files); df = Counter()
    for rs in by_vid.values(): df.update(set().union(*(r[9] for r in rs)))
    mine = by_vid.get(vid, [])
    if not mine: sys.exit(f"{vid}: no Claims ledger rows in {db}")
    text = "\n".join(r[5] for r in mine)
    terms = {w: "term" for w in set().union(*(r[9] for r in mine)) if df[w] <= max(2, 0.08 * nvid)}
    terms.update({w: "name" for w in proper_nouns(text) if df[w] <= 0.6 * nvid})
    for n, in con.execute("SELECT name FROM mentions WHERE video=?", (vid,)):
        if surname(n): terms[surname(n)] = "person"
    loose = {w for w in set().union(*(r[9] for r in mine)) if df[w] <= 0.15 * nvid} | set(terms)
    for w in NOISE: terms.pop(w, None); loose.discard(w)
    gs = guest_surnames(con, vid)  # a note with the same guest is the likeliest to be answered, echoed or contradicted
    same = {v for v, g in con.execute("SELECT id, guest FROM videos WHERE id != ?", (vid,))
            if gs & set(toks(re.split(r"[,(]", g or "")[0]))}
    idf = lambda w: math.log((nvid + 1) / (df[w] + 1)) + 1
    allnames = [n for n, in con.execute("SELECT DISTINCT name FROM mentions")]
    sur = {surname(n) for n in allnames if len(WORD.findall(re.sub(r"\(.*?\)", "", n))) >= 2} - {None}  # first names carry no weight
    firsts = {norm(ws[0]) for n in allnames for ws in [WORD.findall(re.sub(r"\(.*?\)", "", n))]
              if len(ws) >= 2 and ws[0][0].isupper() and ws[1][0].isupper()} - sur
    units = lambda ws: {w for w in ws if w not in firsts}
    wt = lambda ws: sum(2 if terms.get(w) in ("name", "person") else 1 for w in units(ws))  # names and people count double
    def score(shared): return (wt(shared), sum(idf(w) for w in shared))
    def srt(ws): return sorted(ws, key=lambda w: -idf(w))

    def answering(qwords):
        """This note's ledger rows ranked by terms shared with a question, lead or decline."""
        hits = [(score(sh), r, srt(sh)) for r in mine for sh in [(r[9] & qwords & loose) - gs] if sh]
        hits.sort(key=lambda h: (-h[0][0], -h[0][1])); return hits[:per]

    L = [f"# Onboarding cross-check: {vid}", "",
         f"Generated {datetime.date.today()} from notes.db ({nvid} notes) by `tools/onboard_check.py`. {len(terms)} terms "
         f"({sum(k != 'term' for k in terms.values())} names or people) from {len(mine)} ledger rows. Every candidate is a "
         "term match, not a finding: read both sides before entering it under `## Cross-checks` (schema section 10); "
         f"rejected candidates are not listed there. Guest surnames: {', '.join(sorted(gs)) or 'none'}; notes with the same guest: "
         f"{', '.join(files[v] for v in sorted(same)) or 'none'}.", ""]
    # A: standing questions and leads
    cands = [(f"{files[v]} #{n}", st, q, s, toks(f"{q} {s}"), "same guest" if v in same else "") for v, n, q, s, st in con.execute(
        "SELECT video, n, question, settles, status FROM open_questions WHERE video != ? AND lower(status) IN ('open','checked')", (vid,))]
    cands += [(f"research/leads-and-inferences.md #{n}", st, q, s, toks(f"{q} {s}"), "") for n, q, s, st in con.execute(
        "SELECT n, lead, settles, status FROM leads WHERE lower(status) IN ('open','checked')")]
    A = []
    for c in cands:
        sh, rows = c[4] & set(terms), answering(c[4])
        why = c[5] or ("names the guest" if gs & c[4] else "")
        if why or (len(units(sh)) >= 2 and rows and rows[0][0][0] >= 3): A.append((score(sh), c, srt(sh), rows, why))
    A.sort(key=lambda h: (-(h[3][0][0][0] if h[3] else 0), -h[0][0], -h[0][1], h[1][0]))
    L += [f"## A. Standing questions and leads this note may answer ({min(top, len(A))} shown of {len(A)}; {len(cands)} open or checked)", "",
          "Listed when the question shares two or more terms with this note and one ledger row shares weight 3 (names and people count 2), "
          "and always when it sits in a note with the same guest or names the guest.", ""]
    for i, ((k, _), (where, st, q, s, qw, _), sh, rows, why) in enumerate(A[:top], 1):
        L += [f"### A{i}. {where} [{st}]{' [' + why + ']' if why else ''}, {len(sh)} shared: {', '.join(sh[:10]) or 'none'}", "", f"**Question:** {clip(q, 500)}", "",
              f"**What would settle it:** {clip(s, 300) or 'not given'}", "", "| This note # | Time | Speaker | Class | Claim | Shared |", "|---|---|---|---|---|---|"]
        L += [f"| {r[1]} | {r[2]} | {r[3]} | {r[6]} | {clip(r[5])} | {', '.join(w[:6])} |" for _, r, w in rows] + (
            [] if rows else ["| none | | | | no ledger row shares a term: read the question against the note | |"]) + [""]
    # B: claims elsewhere on the same topic
    B = []
    for r in mine:
        mt = r[9] & loose
        best = {}
        for v, rs in by_vid.items():
            if v == vid: continue
            for o in rs:
                sh = mt & o[9]
                if len(units(sh)) >= 2 and (o[4] == r[4] or wt(sh) >= 3 or (v in same and gs & toks(o[3]))):
                    h = (score(sh), o, srt(sh))
                    if v not in best or h[0] > best[v][0]: best[v] = h
        hits = sorted(best.values(), key=lambda h: (-h[0][0], -h[0][1]))
        if hits: B.append((hits[0][0], r, hits))
    B.sort(key=lambda b: (-b[0][0], -b[0][1]))
    nb = sum(len(b[2]) for b in B)
    L += [f"## B. Claims elsewhere on the same topic ({min(top, len(B))} of this note's rows shown of {len(B)} with a match; {nb} pairs in all)", "",
          "Listed: rows on the same Topic sharing two or more terms; on any Topic sharing weight 3 (names and people count 2), or two terms "
          "when the other row is the same guest in another note (the Topic column shows which); best row per other note. "
          "Candidate corroborations, contradictions or extensions. Attribution and chain are the other row's chain of custody: a hearsay row corroborates less than a firsthand one.", ""]
    for i, (_, r, hits) in enumerate(B[:top], 1):
        L += [f"### B{i}. This note #{r[1]} ({r[2]}, {r[3]}, {r[6]}, {r[4]})", "", f"> {clip(r[5], 500)}", "",
              "| Shared | Note | # | Time | Speaker | Class | Topic | Attribution; chain | Claim |", "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {len(sh)}: {', '.join(sh[:6])} | {files[o[0]]} | {o[1]} | {o[2]} | {o[3]} | {o[6]} | {'same' if o[4] == r[4] else o[4]} | {clip((o[7] or '') + ('; ' + o[8] if o[8] else ''), 120) or 'not recorded'} | {clip(o[5])} |"
              for (_, _), o, sh in hits[:per]] + [""]
    # C: declines elsewhere this note may fill
    sweep = sweep_index(vid); C = []
    for v, n, t, who, q, a, mv, basis in con.execute("""SELECT video, n, time, asked_by, question, answer, move, basis FROM audit_rows
            WHERE video != ? AND move IN ('closed-outright','closed-subtle')""", (vid,)):
        if mv == "closed-subtle" and re.search(r"monologue|narration|^none\b", (who or "").strip().lower()): continue
        qw = toks(f"{q} {a}"); sh = qw & set(terms); rows = answering(qw)
        if v in same or (len(units(sh)) >= 2 and rows and rows[0][0][0] >= 3):
            C.append((score(sh), (v, n, t, who, q, a, mv, basis, qw), srt(sh), rows))
    C.sort(key=lambda h: (-(h[3][0][0][0] if h[3] else 0), -h[0][0], -h[0][1]))
    L += [f"## C. Declines elsewhere this note may fill ({min(top, len(C))} shown of {len(C)} closed audit rows sharing two or more terms, one row of this note weight 3; always for a note with the same guest)", "",
          "Cross-reference: research/declined-answered-elsewhere.md. A decline already paired there is marked; a new fill belongs in `## Cross-checks` as `fills`.", ""]
    for i, ((k, _), (v, n, t, who, q, a, mv, basis, qw), sh, rows) in enumerate(C[:top], 1):
        sw = "; ".join(sweep.get((v, str(n)), [])) or "not in the sweep"
        L += [f"### C{i}. {files[v]} audit {n} ({t}, {mv}, basis: {basis or 'blank'}), {len(sh)} shared: {', '.join(sh[:8])}", "",
              f"**Asked by:** {who}. **Question:** {clip(q, 400)}", "", f"**Answer:** {clip(a, 400)}", "", f"**Sweep:** {sw}", "",
              "| This note # | Time | Speaker | Class | Claim | Shared |", "|---|---|---|---|---|---|"]
        L += [f"| {r[1]} | {r[2]} | {r[3]} | {r[6]} | {clip(r[5])} | {', '.join(w[:6])} |" for _, r, w in rows] + (
            [] if rows else ["| none | | | | no ledger row shares a term: read the decline against the note | |"]) + [""]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    LN.write_text(out, "\n".join(L) + "\n")
    insweep = sum(1 for _, c, _, _ in C if (c[0], str(c[1])) in sweep)
    print(f"{vid}: {len(terms)} terms; A questions/leads {len(A)} (of {len(cands)}); B rows {len(B)} ({nb} pairs); "
          f"C declines {len(C)} ({insweep} already in the sweep); top {top} per part, {per} each -> {out}")

if __name__ == "__main__":
    main()
