#!/usr/bin/env python3
"""The adoption check: the mechanical half of the attacker's test 9 (tools/narratives.md section 6, the revision rule; tools/adoption_check.md).
Usage:
  python3 tools/adoption_check.py <page> [--all] [--out <file.md>] [--snapshots <dir>] [--chars N]
  python3 tools/narratives.py --adoptions <page> [--all] [--out <file.md>]          (the same command, dispatched from narratives.py)

For the page's latest `## Revision` section (every Revision section on the page and in research/narrative-history/<stem>.md with --all)
the Revision table is parsed, one row per objection: disposition (adopted, partly, declined, other), `Rows read`, `Leads checked`, what changed.
For every adopted or partly adopted objection (and, with fails counted the same way, every applied row that is not an objection: brief items,
proposal rows):
  1. an empty Rows read cell: FAIL empty-rows-read (the revision rule);
  2. every citation in Rows read resolved against notes.db: FAIL missing-note, FAIL missing-row; WARN outside-note when the note is cited
     nowhere on the page (Nodes, ledger and the rest) and was not newly added by this revision; bare references without a note are counted;
  3. the page rows the adoption changed: the nodes and ledger rows the Objection and What changed cells name, diffed between the snapshot
     taken before the revision and the first snapshot after it (research/tasks/tool-feedback/snapshots/, tools/narrative_snapshot.py; the page
     itself when no later snapshot exists), with the citations on the changed text set against the Rows read set (same rows, or new ones:
     WARN new-rows-on-change); WARN no-change-located when none of the named rows differs;
  4. the leads in Leads checked resolved against research/leads-and-inferences.md: FAIL missing-lead; WARN open-lead (the adoption rests on an
     unresolved lead); the status the page states is shown beside the register's;
  5. the full text of every Rows read row, trimmed to --chars (400) characters, so the attacker reads the list and rules whether the rows say
     what the objection says (the human half of test 9), writing the ruling in findings-B.md.
Output: markdown to --out (the attacker's wip folder) or stdout: a summary line (adoptions N, mechanical fails N by kind), then one block per
adoption, severity first (FAIL, WARN, OK), then the declined and other rows in one table each. Exit code 1 when any mechanical fail exists,
so the staged workflow can gate on it; 0 otherwise. Reads the pages, the snapshots and notes.db only; never writes a page.
"""
import re, sys, os, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narratives as N
ROOT = N.ROOT; os.chdir(ROOT)
SNAP_DIR = "research/tasks/tool-feedback/snapshots"; HIST_DIR = "research/narrative-history"; LEADS_MD = "research/leads-and-inferences.md"
STATUS_WORDS = ("open", "checked", "closed", "standing", "superseded")
EMPTY_CELL = re.compile(r"^\s*(?:none|n/a|-|—|–|not applicable)?\s*\.?\s*$", re.I)
TABLES = {"tl": "timeline", "claims": "claims", "audit": "audit_rows", "xc": "cross_checks"}

# ---------- sections: page order, with the history file's earlier passes first ----------
def sections_of(txt):
    """[(heading line without '## ', body)] for every top-level section in order (form S5 of the parser library)."""
    return N.LN.sections_text(txt)
def combined_sections(page):
    stem = os.path.basename(page)[:-3]; hist = os.path.join(HIST_DIR, stem + ".md"); out = []
    if os.path.exists(hist): out += [(h, b, "history") for h, b in sections_of(N.LN.read_text(hist))]
    out += [(h, b, "page") for h, b in sections_of(N.LN.read_text(page))]
    return out

# ---------- the Revision table ----------
ADOPT_RE = re.compile(r"\b(adopt\w*|done\b|carried\b|folded in\b|accepted\b|applied\b)", re.I); DECL_RE = re.compile(r"\b(declin\w*|reject\w*|not adopted\b|withdrawn\b|refused\b)", re.I)
PART_RE = re.compile(r"\b(in part|partly|partial|adopt(ed)? (?:for )?\([a-z]\))", re.I); NOTAPP_RE = re.compile(r"^\s*(not applicable|answered|no change|n/a|none)\b", re.I)
def classify(changed, label=""):
    """adopted | partly | declined | applied (no disposition word, but the cell describes a change) | other (not applied).
    A cell that opens with the word is read by its opening ('Adopted.', 'adopt in part.', 'declined:', 'Carried.'); otherwise the word is looked
    for in the cell's first 80 characters and in any parenthesis of the Objection cell ('(adopted: a, b, c)'), then anywhere in the cell. A cell
    that says both ('Row 40's reweighting declined: ... Row 13's side adopted') is partly."""
    c = (changed or "").strip(); head = c[:80]; par = " ".join(re.findall(r"\(([^()]*)\)", label or ""))
    if NOTAPP_RE.match(head): return "other"
    if DECL_RE.match(c): return "partly" if PART_RE.search(c) or ADOPT_RE.search(c[:200]) else "declined"
    if ADOPT_RE.match(c): return "partly" if PART_RE.search(c[:120]) or DECL_RE.search(c[:200]) else "adopted"
    a_head, d_head = bool(ADOPT_RE.search(head + " " + par)), bool(DECL_RE.search(head + " " + par))
    a_any, d_any = bool(ADOPT_RE.search(c + " " + par)), bool(DECL_RE.search(c + " " + par))
    if a_head and d_head: return "partly"
    if a_head: return "partly" if PART_RE.search(head + " " + par) or d_any else "adopted"
    if d_head: return "partly"  # the head describes a change and declines a part ('Test 17 struck; test 7 rewritten, not struck (objection 13 declined in that part)')
    if a_any and d_any: return "partly"
    if a_any: return "adopted"
    return "applied" if c else "other"  # a decline word deep in a cell that opens by describing a change does not make the row a decline
def parse_revision(body):
    rows = N.table(body); out = []
    for r in rows:
        obj = r.get("objection", "") or r.get("#", "")
        if (not obj and not r.get("what changed")) or obj.strip().lower() == "objection": continue
        rr = r.get("rows read"); legacy = False
        if rr is None: rr = r.get("rows", ""); legacy = True  # the 2026-10-08 tables: one `Rows` column mixing page rows and citations
        out.append(dict(label=obj, changed=r.get("what changed", ""), rows_read=rr or "", leads=r.get("leads checked", "") or "", legacy=legacy,
                        disposition=classify(r.get("what changed", ""), obj), is_objection=bool(re.match(r"^\s*\d+", obj)) and not re.match(r"^\s*(brief|r0|p\d+|prefatory)", obj, re.I)))
    return out

# ---------- the objection's own text ----------
def objection_text(obj_body, label):
    m = re.match(r"^\s*(\d+)\s*(?:\(([a-z])\)|([a-z])\b)?", label)
    if not m: return ""
    n, sub = m.group(1), (m.group(2) or m.group(3))
    mm = re.search(r"^[ \t]*" + n + r"\.[ \t]+\*\*(.*)", obj_body, re.M)
    if not mm: return ""
    rest = obj_body[mm.start():]; first = rest.find("\n"); e = re.search(r"^[ \t]*\d+\.[ \t]+\*\*", rest[first + 1:], re.M) if first >= 0 else None
    text = rest[:first + 1 + e.start()] if e else rest
    if sub:
        s = re.search(r"\(" + sub + r"\)", text)
        if s:
            nxt = re.search(r"\(" + chr(ord(sub) + 1) + r"\)", text[s.start() + 3:])
            text = text[:text.find("\n")] + "\n   ... " + (text[s.start():s.start() + 3 + nxt.start()] if nxt else text[s.start():])
    return re.sub(r"\n\s*\n", "\n", text.strip())

# ---------- rows ----------
def row_text(con, note, kind, n, chars):
    tab = TABLES[kind]; r = con.execute(f"select * from {tab} where video=? and n=?", (note, n)).fetchone()
    if not r: return None
    if kind == "tl": t = f"{r['date_stated'] or ''}: {r['event'] or ''}" + (f" | chain: {r['chain']}" if r["chain"] else "") + (f" | {r['agreement_kind']}: {r['agreement']}" if r["agreement_kind"] else "")
    elif kind == "claims": t = f"{r['time'] or ''} {r['speaker'] or ''} [{r['topic'] or ''}; {r['move'] or ''}]: {r['claim'] or ''}" + (f" | chain: {r['chain']}" if r["chain"] else "")
    elif kind == "audit": t = f"{r['time'] or ''} {r['asked_by'] or ''} asks: {r['question'] or ''} => {r['answer'] or ''} [{r['move'] or ''}; basis: {r['basis'] or ''}]"
    else: t = f"{r['kind'] or ''}/{r['verdict'] or ''}: {r['this_note'] or ''} || {r['elsewhere'] or ''}"
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= chars else t[:chars - 1].rstrip() + "…"
def note_exists(con, note):
    if con.execute("select 1 from videos where id=?", (note,)).fetchone(): return True
    for tab in TABLES.values():
        if con.execute(f"select 1 from {tab} where video=? limit 1", (note,)).fetchone(): return True
    return False
SHORT_RE = N.LN.SHORT_CITE_RE   # form C5
def cites_in(cell):
    """ordered, unique citations from a cell: [(note, kind, n, shorthand)], plus the count of bare references that no note precedes.
    Shorthand ('[same claims 10]', '; tl 5, 7, 10 of the same note', 'claims 44, 161' after a bracketed citation) resolves to the note last
    named in the cell and is marked so; a bare reference before any note is counted and left unresolved."""
    seen, out, bare, last = set(), [], 0, None
    for m in SHORT_RE.finditer(cell or ""):
        note = m.group("note"); short = False
        if note is None or note == "same":
            if last is None: bare += 1; continue
            note = last; short = True
        else: last = note
        for n in re.split(r"\s*,\s*", m.group("ns")):
            key = (note, m.group("kind"), n)
            if key not in seen: seen.add(key); out.append(key + (short,))
    return out, bare
# ---------- leads ----------
def load_leads():
    """{n: (status, lead text)} from research/leads-and-inferences.md (the register; notes.db's `leads` is built from it)."""
    d = {}
    try: txt = N.LN.read_text(LEADS_MD)
    except Exception: txt = ""
    for m in N.LN.LEAD_ROW_RE.finditer(txt):
        cells = [c.strip() for c in m.group(0).strip("| \n").split(" | ")]
        line = txt[m.start():txt.find("\n", m.start())]; cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7: d[int(cells[0])] = (cells[6].lower(), cells[1])
    if not d:
        con = N._db()
        for r in con.execute("select n, status, lead from leads"): d[int(r["n"])] = ((r["status"] or "").lower(), r["lead"] or "")
    return d
def leads_in(cell):
    """[(n, stated status or '')] from a Leads checked cell; relations numbers, citations, dates and parenthesised notes are not leads."""
    c = N.CITE_RE.sub(" ", cell or ""); c = re.sub(r"\([^()]*\)", " ", c); c = re.sub(r"\([^()]*\)", " ", c)
    c = re.sub(r"\brel(?:ations?)?\s+\d+(?:\s*(?:,|and|to)\s*\d+)*", " ", c, flags=re.I); c = re.sub(r"\d{4}-\d{2}-\d{2}", " ", c)
    c = re.sub(r"\b(?:T|M|N|P|CM|FU)\d+\b", " ", c); c = re.sub(r"\b(?:rows?|nodes?|tl|claims|audit|xc|objections?|ledger|test|tests|step|of|chain)\s+\d+\b", " ", c, flags=re.I)
    out = []
    for seg in re.split(r";", c):
        nums = [(m.start(), int(m.group(0))) for m in re.finditer(r"\b\d{1,5}\b", seg)]
        for pos, n in nums:
            after = seg[pos:]; st = re.search(r"\b(" + "|".join(STATUS_WORDS) + r")\b", after, re.I)
            out.append((n, st.group(1).lower() if st else ""))
    seen = set(); uniq = []
    for n, st in out:
        if n not in seen: seen.add(n); uniq.append((n, st))
    inherits = bool(re.search(r"\b(as above|all leads above|see above)\b", cell or "", re.I))
    return uniq, inherits

# ---------- the page rows an adoption changed ----------
def numlist(s):
    out = []
    for grp in re.findall(r"\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*", s):
        parts = re.split(r"\s*(?:,|and)\s*", grp)
        for p in parts:
            rng = re.match(r"(\d+)\s*(?:to|–|-)\s*(\d+)$", p)
            if rng:
                a, b = int(rng.group(1)), int(rng.group(2))
                if 0 < b - a <= 40: out += list(range(a, b + 1)); continue
            out += [int(x) for x in re.findall(r"\d+", p)]
    return out
def named_targets(*cells):
    txt = " ".join(cells); txt = N.CITE_RE.sub(" ", txt); txt = re.sub(r"\brel(?:ations?)?\s+\d+(?:\s*(?:,|and|to)\s*\d+)*", " ", txt, flags=re.I)
    txt = re.sub(r"\bleads?\s+\d+(?:\s*(?:,|and|to)\s*\d+)*", " ", txt, flags=re.I); txt = re.sub(r"\bedges?\s+\d+\s*(?:to|<-|->|on)\s*\d+", " ", txt)
    nodes, rows = set(), set()
    for m in re.finditer(r"\bnodes?\s+(\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*)", txt, re.I): nodes |= set(numlist(m.group(1)))
    for m in re.finditer(r"\b(?:ledger\s+)?rows?\s+(\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*)", txt, re.I): rows |= set(numlist(m.group(1)))
    for m in re.finditer(r"\bledger\s+(\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*)", txt, re.I): rows |= set(numlist(m.group(1)))
    return sorted(nodes), sorted(rows)
def keyed(txt, heading):
    out = {}
    for r in N.table(N.section(txt, heading)):
        m = re.match(r"\s*(\d+)", r.get("#", "") or "")
        if m: out[int(m.group(1))] = r
    return out
def snapshots_for(page, heading, snap_dir, later_headings=(), where="page"):
    """(before, after): after = the oldest snapshot holding this Revision heading (None when no snapshot does); before = the newest snapshot
    older than it that lacks the heading. When no snapshot holds the heading: for a revision still on the page, the newest snapshot lacking it
    and every later Revision heading; for one already moved to the history file, none (a snapshot lacking it may postdate it: slim moves
    earlier passes off the page)."""
    stem = os.path.basename(page)[:-3]; fs = sorted(glob.glob(f"{snap_dir}/{stem}.*.md"), key=os.path.getmtime)
    line = "## " + heading; texts = {f: N.LN.read_text(f) for f in fs}
    after = next((f for f in fs if line in texts[f]), None); before = None
    if after:
        for f in fs:
            if os.path.getmtime(f) < os.path.getmtime(after) and line not in texts[f]: before = f
    elif where == "page":
        for f in fs:
            if line not in texts[f] and not any("## " + h in texts[f] for h in later_headings): before = f
    return before, after
def row_cites(r): return set(c for c in N.citations(" ".join(str(v) for v in r.values())))
def change_report(before_txt, after_txt, nodes, rows, read_set, cap=6, max_named=12):
    """per named node/ledger row: changed columns, citations on the new text against the Rows read set. Names on neither version are dropped
    (a 'rows 440' from a score line is not a ledger row); when more than max_named are named, only the changed ones are listed."""
    out = []; any_change = False; new_rows = set(); unchanged = []
    for heading, keys, word in (("Nodes", nodes, "node"), ("Contradiction ledger", rows, "ledger row")):
        a, b = keyed(before_txt, heading), keyed(after_txt, heading)
        keys = [k for k in keys if k in a or k in b]; many = len(nodes) + len(rows) > max_named
        for k in keys:
            if k not in a: ca = set(); st = "added"
            elif k not in b: out.append(f"{word} {k}: removed"); any_change = True; continue
            else:
                ca = row_cites(a[k]); cols = [c for c in b[k] if b[k].get(c) != a[k].get(c)]
                if not cols:
                    if many: unchanged.append(f"{word} {k}")
                    else: out.append(f"{word} {k}: unchanged")
                    continue
                st = "changed " + ", ".join(cols)
            any_change = True; cb = row_cites(b[k]); added = cb - ca; removed = ca - cb
            in_read = cb & read_set; new = cb - read_set
            s = f"{word} {k}: {st}; citations on the new text {len(cb)} ({len(in_read)} in Rows read, {len(new)} not); added {len(added)}, removed {len(removed)}"
            if added - read_set: s += "; added rows not in Rows read: " + ", ".join(f"[{n} {kd} {x}]" for n, kd, x in sorted(added - read_set)[:cap]) + (" …" if len(added - read_set) > cap else "")
            new_rows |= (added - read_set)
            if k in a:
                for c in cols[:3]: s += f"\n    - {c}: {str(a[k].get(c))[:220]}  ->  {str(b[k].get(c))[:220]}"
            out.append(s)
    if unchanged: out.append(f"unchanged: {len(unchanged)} of the named rows (" + ", ".join(unchanged[:20]) + (" …" if len(unchanged) > 20 else "") + ")")
    return out, any_change, new_rows
# ---------- the check ----------
def check(page, all_revisions=False, out=None, snap_dir=SNAP_DIR, chars=400):
    con = N._db(); leads = load_leads(); secs = combined_sections(page); stem = os.path.basename(page)
    page_txt = N.LN.read_text(page)
    core_notes = {c[0] for c in N.citations(N.section(page_txt, "Nodes") + N.section(page_txt, "Contradiction ledger"))}
    page_notes = {c[0] for c in N.citations(page_txt)}
    revs = [i for i, (h, b, w) in enumerate(secs) if h.startswith("Revision")]
    if not revs:
        text = f"# Adoption check: {stem}\n\nNo `## Revision` section on the page or in {HIST_DIR}/{stem}.\n"
        if out: N.LN.write_text(out, text)
        print(f"{stem}: no Revision section"); return 0, dict(adoptions=0, fails=0)
    todo = revs if all_revisions else revs[-1:]
    today = datetime.date.today().isoformat()
    lines = [f"# Adoption check: {stem} (tools/adoption_check.py, {today})", "",
             "The mechanical half of the attacker's test 9 (tools/narratives.md section 6, the revision rule). Each block is one adopted or partly adopted objection: its own text, what the reviser changed, the rows the reviser says were read (resolved, with their text), the leads checked (with the register's status), and the page rows that changed with their citations set against the Rows read set. Severity first: FAIL is a mechanical fail (the step gates on it); WARN needs the attacker's judgement; OK passed the mechanical checks. The human half is yours: read each block's rows and rule whether they say what the objection says, in findings-B.md, citing the block.", ""]
    totals = dict(adoptions=0, adopted=0, partly=0, applied=0, declined=0, other=0, fails=0, warns=0, open_leads=0); kinds = {}; wkinds = {}
    body = []
    for ri in todo:
        heading, rbody, where = secs[ri]
        obj_secs = [j for j in range(ri - 1, -1, -1) if secs[j][0].startswith("Objections")]
        obj_head, obj_body = (secs[obj_secs[0]][0], secs[obj_secs[0]][1]) if obj_secs else ("", "")
        before, after = snapshots_for(page, heading, snap_dir, [secs[j][0] for j in revs if j > ri], where)
        before_txt = N.LN.read_text(before) if before else ""
        after_txt = N.LN.read_text(after) if after else page_txt
        new_notes = ({c[0] for c in N.citations(after_txt)} - {c[0] for c in N.citations(before_txt)}) if before else set()
        rows = parse_revision(rbody)
        blocks = []; declined = []; others = []
        for r in rows:
            d = r["disposition"]; applied = d in ("adopted", "partly", "applied") or (d == "other" and not re.match(r"^\s*(not applicable|answered|no change)", (r["changed"] or "").strip(), re.I))
            fails, warns, infos = [], [], []
            # 1, 2: rows read
            cites, bare = cites_in(r["rows_read"]); read_set = set(c[:3] for c in cites)
            inherit = re.search(r"\b(as above|rows above|(?:as|see|rows of|same as|the rows of)\s+(?:objections?\s+)?P?\d+(?:\s*(?:,|and)\s*(?:objections?\s+)?P?\d+)*)", r["rows_read"], re.I)
            if inherit:
                refs = re.findall(r"\bP?\d+\b", inherit.group(0)); got = 0
                for k in refs:
                    for rr in rows:
                        if rr is not r and re.match(r"^\s*" + re.escape(k) + r"(?![\d])", rr["label"]): read_set |= set(c[:3] for c in cites_in(rr["rows_read"])[0]); got += 1
                infos.append(f"Rows read refers to other rows of the table ({inherit.group(0)[:60]}); {len(read_set)} rows inherited from {got} row(s)")
            empty = EMPTY_CELL.match(r["rows_read"] or "")
            if empty and d in ("adopted", "partly", "applied") and r["is_objection"] and not r["legacy"]: fails.append("empty-rows-read: the Rows read cell is empty (revision rule: an adopted objection with an empty Rows read cell fails)")
            elif empty and applied: warns.append("empty-rows-read: no Rows read on an applied row that is not a numbered objection")
            elif not cites and not inherit and applied and r["legacy"]: infos.append("v0.3 table: the Rows column lists page rows, not rows read (" + r["rows_read"][:120] + "); the revision rule postdates it")
            elif not cites and inherit and not read_set and applied: warns.append("no-row-citations: the Rows read cell refers to other rows of the table but none of them names a database row (" + r["rows_read"][:120] + ")")
            elif not cites and not inherit and applied: warns.append("no-row-citations: the Rows read cell names no database row (" + (r["rows_read"][:120]) + ")")
            if bare: warns.append(f"bare-references: {bare} reference(s) of the form 'claims N' with no note named before them (unresolvable)")
            resolved = []; shorts = sum(1 for c in cites if c[3])
            if shorts: infos.append(f"{shorts} shorthand reference(s) ('same', or 'tl N' after a note) taken as the note last named before them")
            for (note, kind, n, short) in cites:
                t = row_text(con, note, kind, n, chars)
                if t is None:
                    if short: warns.append(f"unresolved-shorthand: '{kind} {n}' taken as [{note} {kind} {n}] has no such row (the shorthand may mean another note)"); resolved.append((note, kind, n, "MISSING ROW (shorthand; which note?)", ""))
                    elif not note_exists(con, note): fails.append(f"missing-note: [{note} {kind} {n}] (no such note in notes.db)"); resolved.append((note, kind, n, "MISSING NOTE", ""))
                    else: fails.append(f"missing-row: [{note} {kind} {n}]"); resolved.append((note, kind, n, "MISSING ROW", ""))
                    continue
                if short: wh_pre = "shorthand; "
                else: wh_pre = ""
                if note in core_notes: wh = "nodes/ledger"
                elif note in page_notes: wh = "elsewhere on the page"
                elif note in new_notes: wh = "new in this revision"
                else: wh = "OUTSIDE the page"; warns.append(f"outside-note: [{note} {kind} {n}] is from a note the page cites nowhere and this revision did not add")
                resolved.append((note, kind, n, wh_pre + wh, t))
            # relations numbers named in Rows read (register rows, not database rows): resolved so the block is self-contained
            rel_lines = []
            for m in re.finditer(r"\brel(?:ations?)?\s+(\d+(?:\s*(?:,|and|to)\s*\d+)*)", r["rows_read"] + " " + r["leads"], re.I):
                for n in numlist(m.group(1)):
                    rr = con.execute("select a, kind, b, when_ from relations where n=?", (n,)).fetchone()
                    if rr: rel_lines.append(f"rel {n}: {rr['a']} -> {(rr['kind'] or '')[:40]} -> {rr['b']}" + (f" [{rr['when_']}]" if rr["when_"] else ""))
                    else: rel_lines.append(f"rel {n}: NOT IN THE RELATIONS REGISTER"); warns.append(f"missing-relation: relation {n} is not in research/relations-register.md")
            rel_lines = list(dict.fromkeys(rel_lines))
            # 4: leads
            lead_list, lead_inherit = leads_in(r["leads"]); lead_lines = []; open_leads = []
            for n, stated in lead_list:
                if n not in leads: fails.append(f"missing-lead: lead {n} is not in {LEADS_MD}"); lead_lines.append(f"lead {n}: NOT IN THE REGISTER (page says {stated or 'nothing'})"); continue
                st, lt = leads[n]
                if st == "open" and applied: open_leads.append(n)
                mark = "" if not stated or stated == st else f" (page says {stated})"
                lead_lines.append(f"lead {n}: {st.upper() if st == 'open' else st}{mark}: {lt[:160]}")
            if lead_inherit: infos.append("Leads checked refers to earlier rows")
            if open_leads: infos.append(f"open leads: {', '.join(str(x) for x in open_leads)} are open in the register, so the adoption rests on unresolved leads (the attacker weighs this; not a mechanical fail)")
            # 3: the page rows changed
            nodes, lrows = named_targets(r["label"], r["changed"]); chg_lines = []; new_on_change = set()
            if applied:
                if not before: chg_lines.append("no snapshot precedes this revision: change diff unavailable" + (f" (the first snapshot holding it: {after})" if after else ""))
                elif not nodes and not lrows: chg_lines.append("no node or ledger row named in the Objection or What changed cell: the change is in prose (Thesis, Carriers, Score card, Tests) or the cell does not say")
                else:
                    chg_lines, any_change, new_on_change = change_report(before_txt, after_txt, nodes, lrows, read_set)
                    shared = [rr["label"][:40] for rr in rows if rr is not r and (set(nodes) & set(named_targets(rr["label"], rr["changed"])[0]) or set(lrows) & set(named_targets(rr["label"], rr["changed"])[1]))]
                    if shared: chg_lines.append("the same nodes or rows are also named by: " + "; ".join(shared) + " (their changes show here too)")
                    if not any_change: warns.append("no-change-located: none of the named nodes or ledger rows differs between the snapshots")
                    if new_on_change: warns.append(f"new-rows-on-change: the changed text adds {len(new_on_change)} row(s) not in Rows read")
            sev = "FAIL" if fails else ("WARN" if warns else "OK")
            totals["open_leads"] += len(open_leads) if d in ("adopted", "partly", "applied") else 0
            rec = dict(r=r, sev=sev, fails=fails, warns=warns, infos=infos, resolved=resolved, lead_lines=lead_lines, rel_lines=rel_lines, chg_lines=chg_lines, nodes=nodes, lrows=lrows, applied=applied)
            if d in ("adopted", "partly", "applied"): blocks.append(rec)
            elif d == "declined": declined.append(rec)
            else: others.append(rec)
        # counts
        for rec in blocks + others:
            for f in rec["fails"]: kinds[f.split(":")[0]] = kinds.get(f.split(":")[0], 0) + 1
            for w in rec["warns"]: wkinds[w.split(":")[0]] = wkinds.get(w.split(":")[0], 0) + 1
            totals["fails"] += len(rec["fails"]); totals["warns"] += len(rec["warns"])
        for rec in declined:
            for f in rec["fails"]: kinds[f.split(":")[0]] = kinds.get(f.split(":")[0], 0) + 1; totals["fails"] += 1
        totals["adoptions"] += len(blocks); totals["adopted"] += sum(1 for b in blocks if b["r"]["disposition"] == "adopted"); totals["partly"] += sum(1 for b in blocks if b["r"]["disposition"] == "partly"); totals["applied"] += sum(1 for b in blocks if b["r"]["disposition"] == "applied")
        totals["declined"] += len(declined); totals["other"] += len(others)
        order = {"FAIL": 0, "WARN": 1, "OK": 2}
        body += [f"## {heading} ({where}; {len(rows)} table rows: {len(blocks)} adopted, partly or applied, {len(declined)} declined, {len(others)} other)", "",
                 f"Objections answered: {obj_head or 'not located'}. Snapshot before the revision: {before or 'none'}; version after it: {after or page + ' (the page itself)'}." + (" This is a v0.3 table (one `Rows` column mixing page rows and citations; no Leads checked)." if rows and rows[0]["legacy"] else ""), ""]
        for rec in sorted(blocks, key=lambda x: order[x["sev"]]) + [dict(x, sev="[" + x["sev"] + ", not an objection]") for x in sorted(others, key=lambda x: order[x["sev"]]) if x["applied"]]:
            r = rec["r"]
            body.append(f"### {rec['sev']} | {r['label'][:140]} ({r['disposition']})")
            for f in rec["fails"]: body.append(f"- FAIL {f}")
            for w in rec["warns"]: body.append(f"- WARN {w}")
            for i in rec["infos"]: body.append(f"- note: {i}")
            ot = objection_text(obj_body, r["label"]) if r["is_objection"] else ""
            body.append(""); body.append("**The objection:** " + (ot[:900] + (" …" if len(ot) > 900 else "") if ot else "(text not located in " + (obj_head or "any Objections section") + ")"))
            body.append(""); body.append("**What changed:** " + r["changed"][:1200] + (" …" if len(r["changed"]) > 1200 else ""))
            body.append(""); body.append(f"**Rows read ({len(rec['resolved'])} citations; {sum(1 for x in rec['resolved'] if x[3].startswith('MISSING'))} missing):**")
            if not rec["resolved"]: body.append(f"- (none resolvable; the cell reads: {r['rows_read'][:200] or 'empty'})")
            for note, kind, n, wh, t in rec["resolved"]: body.append(f"- [{note} {kind} {n}] ({wh}) {t}" if t else f"- [{note} {kind} {n}] {wh}")
            if rec["rel_lines"]:
                body.append(""); body.append(f"**Relations named ({len(rec['rel_lines'])}; register rows, not database rows):**")
                for l in rec["rel_lines"]: body.append(f"- {l}")
            body.append(""); body.append("**Leads checked:**" + ("" if rec["lead_lines"] else f" {r['leads'][:160] or 'empty'}"))
            for l in rec["lead_lines"]: body.append(f"- {l}")
            body.append(""); body.append("**Page rows changed" + (f" (named: nodes {rec['nodes']}, ledger rows {rec['lrows']})" if rec["nodes"] or rec["lrows"] else "") + ":**")
            for c in rec["chg_lines"]: body.append(f"- {c}")
            if not rec["chg_lines"]: body.append("- (not checked: the row was not applied)")
            body.append(""); body.append("**Attacker's ruling (test 9): do the rows say what the objection says?** _(write it in findings-B.md, citing this block)_"); body.append("")
        if declined:
            body.append("### Declined objections (the rows named are the reviser's grounds; a declined objection that still changed the page is noted)"); body.append("")
            body.append("| Objection | Rows cited | Missing | Named nodes / rows | Changed? |"); body.append("|---|---|---|---|---|")
            for rec in declined:
                r = rec["r"]; chg = "n/a"
                if before and (rec["nodes"] or rec["lrows"]):
                    cl, anyc, _ = change_report(before_txt, after_txt, rec["nodes"], rec["lrows"], set()); chg = "yes: " + "; ".join(c.split("\n")[0] for c in cl if "unchanged" not in c and "not on either" not in c)[:200] if anyc else "no"
                body.append(f"| {r['label'][:100]} | {len(rec['resolved'])} | {sum(1 for x in rec['resolved'] if x[3].startswith('MISSING'))}{' (' + '; '.join(f for f in rec['fails'])[:160] + ')' if rec['fails'] else ''} | {rec['nodes']} / {rec['lrows']} | {chg} |")
            body.append("")
        skipped = [x for x in others if not x["applied"]]
        if skipped:
            body.append("### Other rows not applied (resolutions, not-applicable)"); body.append("")
            for rec in skipped: body.append(f"- {rec['r']['label'][:100]}: {rec['r']['changed'][:160]}")
            body.append("")
    summary = (f"Summary: adoptions {totals['adoptions']} (adopted {totals['adopted']}, partly {totals['partly']}, applied without a disposition word {totals['applied']}); declined {totals['declined']}; other rows {totals['other']}; "
               f"mechanical fails {totals['fails']}" + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) + ")" if kinds else "") +
               f"; warnings {totals['warns']}" + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(wkinds.items())) + ")" if wkinds else "") + f"; adoptions resting on open leads {totals['open_leads']}; revisions checked {len(todo)} of {len(revs)}.")
    lines.append(summary); lines.append(""); lines += body
    text = "\n".join(lines) + "\n"
    if out: N.LN.write_text(out, text); print(f"{stem}: {summary}" + f" -> {out}")
    else: print(text)
    return (1 if totals["fails"] else 0), totals

def main(argv):
    pages = [a for a in argv if a.endswith(".md") and not (argv[argv.index(a) - 1] in ("--out",) if argv.index(a) > 0 else False)]
    pages = [p for p in pages if os.path.exists(p)]
    if not pages: print(__doc__); return 2
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    snap = argv[argv.index("--snapshots") + 1] if "--snapshots" in argv else SNAP_DIR
    chars = int(argv[argv.index("--chars") + 1]) if "--chars" in argv else 400
    code, _ = check(pages[0], "--all" in argv, out, snap, chars)
    return code

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
