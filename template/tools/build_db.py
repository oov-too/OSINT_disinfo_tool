#!/usr/bin/env python3
"""Derive notes.db (SQLite) from the markdown notes per tools/schema.md. Never writes to markdown.
Usage: python3 tools/build_db.py [--db notes.db] [--report]
Prints a per-note report of which structured sections were found and how many rows each yielded,
so unconverted notes show up as gaps."""
import re, json, os, sys, glob, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2 of tools/platform-plan.md)
import packload                  # the pack's actor and polity register and its clusters page (pack.toml [actors], [display.typed_graph])

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
DB = os.path.join(ROOT, "notes.db")
OQ_STATUS = LN.OQ_STATUS
XC_KIND = LN.XC_KIND; XC_VERDICT = LN.XC_VERDICT
TOPICS = packload.topic_ids()   # the pack's claims topic codes ([audit] topics)
_D = packload.tool_data("build_db")   # the pack's research page kinds and ties tracker ([tools.build_db]; phase 7b, 2026-10-22)
OBJ = packload.name("table.object_watch")         # the object watch table: core object_watch; a pack may keep an earlier name ([names])
OBJ_LABEL = packload.name("label.object_rows")    # its printed count

SCHEMA = """
DROP TABLE IF EXISTS videos; DROP TABLE IF EXISTS video_subjects; DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS claims; DROP TABLE IF EXISTS audit_rows; DROP TABLE IF EXISTS audit_counts;
DROP TABLE IF EXISTS people; DROP TABLE IF EXISTS mentions; DROP TABLE IF EXISTS works; DROP TABLE IF EXISTS {OBJ}; DROP TABLE IF EXISTS narratives; DROP TABLE IF EXISTS narrative_nodes; DROP TABLE IF EXISTS narrative_contradictions;
DROP TABLE IF EXISTS quotes; DROP TABLE IF EXISTS tracker_candidates; DROP TABLE IF EXISTS register; DROP TABLE IF EXISTS tracker; DROP TABLE IF EXISTS leads; DROP TABLE IF EXISTS relations;
DROP TABLE IF EXISTS subject_rows; DROP TABLE IF EXISTS sections; DROP TABLE IF EXISTS build_report; DROP TABLE IF EXISTS open_questions;
DROP TABLE IF EXISTS cross_checks;
DROP TABLE IF EXISTS timeline; DROP TABLE IF EXISTS pages; DROP TABLE IF EXISTS page_links;
DROP TABLE IF EXISTS owner_notes; DROP TABLE IF EXISTS owner_investigations; DROP TABLE IF EXISTS rows_fts;
DROP TABLE IF EXISTS actors; DROP TABLE IF EXISTS polity_statements;
CREATE TABLE videos(id TEXT PRIMARY KEY, file TEXT, title TEXT, channel TEXT, host TEXT, guest TEXT, speakers TEXT, url TEXT, uploaded TEXT, recorded TEXT, length TEXT, added TEXT, description TEXT, transcript TEXT, words INTEGER);
CREATE TABLE video_subjects(video TEXT, subject TEXT);
CREATE TABLE tags(video TEXT, tag TEXT);
CREATE TABLE claims(video TEXT, n TEXT, time TEXT, speaker TEXT, topic TEXT, claim TEXT, source_class TEXT, move TEXT, note TEXT, attribution TEXT, chain TEXT);
CREATE TABLE audit_rows(video TEXT, n TEXT, time TEXT, asked_by TEXT, question TEXT, answer TEXT, move TEXT, basis TEXT, note TEXT);
CREATE TABLE audit_counts(video TEXT PRIMARY KEY, open INTEGER, partial INTEGER, closed_outright INTEGER, closed_subtle INTEGER, stated_declines INTEGER, pseudo_declines INTEGER);
CREATE TABLE people(name TEXT PRIMARY KEY);
CREATE TABLE mentions(video TEXT, name TEXT, role TEXT, times TEXT, relation TEXT, detail TEXT);
CREATE TABLE works(video TEXT, title TEXT, author TEXT, kind TEXT, time TEXT, note TEXT);
CREATE TABLE {OBJ}(video TEXT, time TEXT, object TEXT, witness TEXT, custody TEXT, criteria TEXT, strength TEXT, register_entry TEXT, note TEXT);
CREATE TABLE quotes(video TEXT, n INTEGER, time TEXT, quote TEXT);
CREATE TABLE tracker_candidates(video TEXT, name TEXT, seats TEXT, degree TEXT, kind TEXT, note TEXT);
CREATE TABLE open_questions(video TEXT, n INTEGER, kind TEXT, asked_by TEXT, question TEXT, bears_on TEXT, settles TEXT, status TEXT, answer TEXT, answered_by TEXT, answered_on TEXT);
CREATE TABLE cross_checks(video TEXT, n TEXT, kind TEXT, this_note TEXT, elsewhere TEXT, verdict TEXT, note TEXT, point TEXT, settled TEXT, revised TEXT, was TEXT);
CREATE TABLE timeline(video TEXT, n TEXT, n_sort REAL, date_stated TEXT, sortable TEXT, sort_key TEXT, approx INTEGER, event TEXT, speaker_basis TEXT, chain TEXT, link TEXT, agreement TEXT, agreement_kind TEXT);
CREATE TABLE register(n INTEGER, video TEXT, timestamp TEXT, who TEXT, object TEXT, match TEXT, strength TEXT);
CREATE TABLE tracker(n INTEGER, from_node TEXT, to_node TEXT, degree TEXT, kind TEXT, when_ TEXT, what TEXT, source TEXT);
CREATE TABLE leads(n INTEGER, lead TEXT, kind TEXT, asked_by TEXT, sources TEXT, settles TEXT, status TEXT, answer TEXT, answered_by TEXT, answered_on TEXT, added TEXT);
CREATE TABLE relations(n INTEGER, a TEXT, b TEXT, kind TEXT, hierarchy TEXT, when_ TEXT, what TEXT, source TEXT, chain TEXT, confidence TEXT, added TEXT, a_canon TEXT, b_canon TEXT);
CREATE TABLE subject_rows(subject TEXT, uploaded TEXT, video_link TEXT, speakers TEXT, what_it_adds TEXT);
CREATE TABLE sections(video TEXT, heading TEXT, line INTEGER);
CREATE TABLE build_report(video TEXT, section TEXT, status TEXT, rows INTEGER);
CREATE TABLE pages(id TEXT PRIMARY KEY, file TEXT, title TEXT, kind TEXT, generated INTEGER, words INTEGER, links_out INTEGER);
CREATE TABLE owner_notes(id TEXT PRIMARY KEY, title TEXT, tags TEXT, body TEXT, links TEXT, created TEXT, updated TEXT);  -- the owner's notes written on the map (owner/notes.json; tools/owner_store.py)
CREATE TABLE owner_investigations(id TEXT PRIMARY KEY, title TEXT, body TEXT, origin TEXT, base TEXT, created TEXT, updated TEXT);  -- investigations written or edited on the map (owner/investigations.json)
CREATE TABLE page_links(page TEXT, target TEXT, target_kind TEXT, count INTEGER);
CREATE TABLE narratives(page TEXT PRIMARY KEY, mode TEXT, parent TEXT, thesis TEXT, alternative TEXT, span TEXT, lanes TEXT, status TEXT, nodes INTEGER, contradictions INTEGER, flares INTEGER, load REAL, max_downstream INTEGER, score_line TEXT, words INTEGER);  -- tools/narratives.md section 7 (2026-10-08)
CREATE TABLE narrative_nodes(page TEXT, n INTEGER, date TEXT, lane TEXT, node TEXT, carriers TEXT, rows TEXT, depends_on TEXT, role TEXT, basis TEXT);  -- basis: the Basis cell (2026-10-25), empty on a page without the column
CREATE TABLE actors(line INTEGER, section TEXT, n TEXT, kind TEXT, body TEXT, teller TEXT, chain TEXT, goals TEXT, polity TEXT, history TEXT, relation TEXT, cluster TEXT, confidence TEXT, codes TEXT, placed TEXT, placed_by TEXT, oob_role TEXT, oob_polity TEXT, cells TEXT);  -- the pack's actor and polity register, actor rows (2026-10-22)
CREATE TABLE polity_statements(line INTEGER, section TEXT, n TEXT, teller TEXT, body TEXT, inside TEXT, outside TEXT, opposed TEXT, standing TEXT, time TEXT, quote TEXT, chain TEXT, upstream TEXT, body_kind TEXT, polity TEXT, inside_placed TEXT, outside_placed TEXT, opposed_placed TEXT, cells TEXT);
CREATE TABLE narrative_contradictions(page TEXT, n TEXT, node TEXT, contradiction TEXT, side TEXT, other TEXT, weight TEXT, downstream TEXT, downstream_computed INTEGER, survivable TEXT, fork TEXT, flare TEXT);
""".replace("{OBJ}", OBJ)

# the forms below live in the parser library (tools/ledger/notes.py); the names stay for any caller of this module
cells = LN.cells
is_sep = LN.is_sep
section_start = LN.section_start

def find_table(lines, start, header_prefix):
    """Find the first table after `start` whose first cell text (lowercased) starts with header_prefix tuple.
    Returns (header_cells, rows, end_index) or (None, [], start). (The library's find_table, form T1.)"""
    t = LN.find_table(lines, start, header_prefix)
    return (t.header, t.row_cells, t.end) if t else (None, [], start)

def parse_note(path):
    """A note in the house schema as a dict (the library's parse_note: tools/ledger/notes.py)."""
    return LN.parse_note(path, ROOT)

def parse_register():
    # the pack's object register ([objects] register); a project without one has no rows (2026-10-22)
    p = os.path.join(ROOT, packload.pack().get("objects", {}).get("register") or "research/object-register.md")
    if not os.path.exists(p): return []
    return LN.register_rows(p, "## Register", ("#", "video", "timestamp", "who", "object", "match", "strength"), 7)

def parse_leads():
    p = os.path.join(ROOT, "research", "leads-and-inferences.md")
    if not os.path.exists(p): return []
    return LN.register_rows(p, "## Lead register", ("#", "lead", "kind", "asked by", "sources", "what would settle it", "status", "answer", "answered by", "answered on", "added"), 11)

def parse_relations():
    p = os.path.join(ROOT, "research", "relations-register.md")
    if not os.path.exists(p): return []
    rows = LN.register_rows(p, "## Relation register", ("#", "a", "b", "kind", "hierarchy", "when", "what", "source", "chain", "confidence", "added"), 11)
    return [(*r, canon(r[1]), canon(r[2])) for r in rows]
_ALIAS = None
def canon(name):
    """Canonical person or organisation name from tools/name_aliases.json (variants matched case-insensitively after stripping honorifics and bracketed tags); otherwise the stripped name."""
    global _ALIAS
    if _ALIAS is None:
        _ALIAS = {}
        ap = os.path.join(ROOT, "tools", "name_aliases.json")
        if os.path.exists(ap):
            for k, vs in json.load(open(ap, encoding="utf-8")).items():
                if k == "_comment": continue
                _ALIAS[_strip(k).lower()] = k
                for v in vs: _ALIAS[_strip(v).lower()] = k
    st = _strip(name)
    return _ALIAS.get(st.lower(), st)
def _strip(name):
    if re.match(r"^General (Atomics|Dynamics|Electric|Motors|Mills|Services|Accounting|Staff|Motors)\b", name.strip()): return re.sub(r"\s+", " ", name).strip()
    n = re.sub(r"\s*\((?:clip|captions?|as heard|probable|probably|pseudonym|host|guest|narrator|unnamed)[^)]*\)", "", name)
    n = re.sub(r"^(?:Dr\.?|Rep\.?|Sen\.?|Col\.?|Colonel|Major|Maj\.?|Gen\.?|General|Lt\.?|Lieutenant|Capt\.?|Captain|Adm\.?|Admiral|RADM|VADM|Rear Adm\.?|Prof\.?|Professor|Mr\.?|Mrs\.?|Ms\.?)\s+", "", n.strip(), flags=re.I)
    return re.sub(r"\s+", " ", n).strip()

def parse_actor_register():
    """The pack's actor and polity register ([actors] register; tools/ledger/notes.py form A) as (actor rows, polity statements).
    Every row of every actor table and statement table lands, with its line number and the heading above its table. The placement
    columns are the order-of-battle reading (notes.ActorPlacer, the rules tools/build_graph_data.py applied to the page): codes =
    the row's cluster codes that the clusters page defines; placed = the clusters it is placed under (its codes, else the actor
    vocabulary in its kind cell); placed_by = cluster code, vocabulary or unplaced (a row that names neither: placed, oob_role and
    oob_polity empty); oob_role and oob_polity = the polity cell's head (member, outside, opposed, subordinate or placed, and the body
    named), empty when it places nothing. Statements: body_kind and polity from the Body cell's head (polity empty when it places
    nothing); inside_placed, outside_placed, opposed_placed = the clusters each cell places. Lists are joined with "; ".
    cells = the row as {column header: cell} (JSON, in column order)."""
    av = packload.actor_vocabulary()
    if not av["register"]: return [], []
    dt = packload.display("typed_graph")
    act, stm = LN.actor_register(packload.path(av["register"]))
    page = av["clusters"] and packload.path(av["clusters"])   # a pack with no clusters page places by its declared polities ([actors] polities; 2026-10-23)
    names = LN.cluster_names(page) if page else LN.polity_names(packload.pack().get("actors", {}).get("polities", []))
    pl = LN.ActorPlacer(names, av["actors"], dt.get("actor_aliases", {}), dt.get("polity_unplaced", []), [r for _, _, r in act], polity_codes=not page)
    j = "; ".join; C, H = LN.reg_col, LN.reg_col_has
    ar = []
    for ln, sec, r in act:
        p = pl.place_actor_row(r)
        ar.append((ln, sec, r.get("#", ""), LN.reg_kind_cell(r), C(r, "body"), C(r, "teller"), H(r, "chain"), C(r, "goals"), C(r, "polity"), C(r, "history"),
                   C(r, "relation"), H(r, "cluster"), C(r, "confidence"), j(p["codes"]), j(p["placed"]), p["placed_by"], p["role"], p["polity"], json.dumps(r, ensure_ascii=False)))
    sr = []
    for ln, sec, r in stm:
        p = pl.place_statement(r)
        sr.append((ln, sec, r.get("#", ""), C(r, "teller"), C(r, "body"), C(r, "inside"), C(r, "outside"), C(r, "opposed"), H(r, "standing"), C(r, "time"), C(r, "quote"),
                   C(r, "chain"), C(r, "upstream"), p["body_kind"], p["polity"], j(p["member"]), j(p["outside"]), j(p["opposed"]), json.dumps(r, ensure_ascii=False)))
    return ar, sr

def parse_tracker():
    p = os.path.join(ROOT, _D["ties_tracker"])
    if not os.path.exists(p): return []   # a project without the ties tracker (2026-10-22)
    return LN.register_rows(p, "## Tie register", ("#", "from", "to", "degree", "kind", "when", "what", "source"), 8)

SUBJECT_WARNINGS = []   # subject pages whose table is not loaded (pilot defect 20, 7b2 2026-10-23): printed by main, never fatal

def parse_subjects():
    out = []
    objreg = os.path.normpath(os.path.join(ROOT, packload.pack().get("objects", {}).get("register") or "research/object-register.md"))
    for p in sorted(glob.glob(os.path.join(ROOT, "subjects", "*.md"))):
        subj = os.path.basename(p)[:-3]; lines = LN.read_lines(p)
        s = section_start(lines, "## Videos in this subject")
        if s is None:
            if os.path.normpath(p) != objreg: SUBJECT_WARNINGS.append(f"subjects/{subj}.md: no `## Videos in this subject` section; no subject rows loaded")
            continue
        hdr, rows, _ = find_table(lines, s, ("uploaded", "video", "speakers", "what"))
        if hdr is None:
            t = LN.find_table(lines, s, ())
            SUBJECT_WARNINGS.append(f"subjects/{subj}.md: the table under `## Videos in this subject` is not headed `| Uploaded | Video | Speakers | What it adds |`"
                                    + (f" (it is `| {' | '.join(t.header)} |`)" if t else " (no table)") + "; no subject rows loaded")
        for r in rows:
            r += [""] * (4 - len(r)); out.append((subj, r[0], r[1], r[2], r[3]))
    return out
PAGE_KINDS = [tuple(x) for x in _D["page_kinds"]]   # (prefix or exact stem, kind, generated); research pages are derived objects that cite notes, never sources (2026-10-01); the first prefix that fits wins
def parse_pages():
    pages, links = [], []
    link_re = LN.PAGE_LINK_RE
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "*.md"))):
        stem = os.path.basename(p)[:-3]; txt = LN.read_text(p)
        title = LN.title_any(txt, stem)
        kind, gen = "other", 0
        for pre, k, g in PAGE_KINDS:
            if stem.startswith(pre): kind, gen = k, g; break
        c = {}
        for m in link_re.finditer(txt):
            key = (m.group(2), m.group(1)); c[key] = c.get(key, 0) + 1
        pages.append((stem, "research/" + stem + ".md", title, kind, gen, len(txt.split()), sum(c.values())))
        links += [(stem, t, tk, n) for (t, tk), n in c.items()]
    return pages, links

def parse_narratives():
    """Narrative pages (tools/narratives.md): research/narrative-<slug>.md, not the synchrony pages or the register; parsed by tools/narratives.py."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import importlib; nt = importlib.import_module("narratives")
    except Exception as e:
        print("narratives: parser unavailable:", e); return [], [], []
    nv, nn, nc = [], [], []
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "narrative-*.md"))):
        stem = os.path.basename(p)[:-3]
        if "synchrony" in stem or "narrative-rival-" in stem or stem == "narrative-register": continue
        try: r = nt.parse(p)
        except Exception as e:
            print("narratives:", stem, "parse failed:", e); continue
        last = r["score_lines"][-1] if r["score_lines"] else None
        nv.append((stem, r["mode"], r["parent"], r["thesis"], r["alternative"], r["span"], r["lanes"], r["status"], r["nodes"], r["contradictions"], r["flares"], r["load_computed"], r["max_downstream_computed"], json.dumps(last) if last else None, r["words"]))
        txt = LN.read_text(p)
        for row in nt.table(nt.section(txt, "Nodes")):
            m = re.match(r"\d+", row.get("#", "") or "")
            if not m: continue
            nn.append((stem, int(m.group(0)), row.get("date", ""), row.get("lane", ""), row.get("node", ""), row.get("carriers (independent roots)", row.get("carriers", "")), row.get("rows", ""), row.get("depends on", ""), row.get("role", ""), row.get("basis", "")))
        comp = {str(l["n"]): l["downstream_computed"] for l in r["ledger"]}
        for row in nt.table(nt.section(txt, "Contradiction ledger")):
            nc.append((stem, row.get("#", ""), row.get("node", ""), row.get("contradiction", ""), row.get("side taken", ""), row.get("other side", ""), row.get("weight", ""), row.get("downstream", ""), comp.get(row.get("#", "")), row.get("why survivable", ""), row.get("fork", ""), row.get("flare", "")))
    return nv, nn, nc

FTS_SQL = """
CREATE VIRTUAL TABLE rows_fts USING fts5(kind, video, n, date, speaker, text, extra, sort_key UNINDEXED, tokenize='unicode61 remove_diacritics 2');
"""
def build_fts(cur):
    """Full-text index over the row tables for tools/rows_search.py (2026-10-15). One FTS5 row per held row of claims, timeline,
    audit_rows, quotes and mentions, rebuilt on every run (no separate index file). Columns: kind (claims, tl, audit, quote, people:
    the citation keyword), video (note stem), n (row number; the name for people rows), date (the row's time or date cell), speaker
    (speaker, speaker/basis, asked-by, or the person's name), text (the claim, event, question => answer, quote, or role; detail),
    extra (the row's other cells, labelled), sort_key (timeline: the row's own sort key; other kinds: the note's Uploaded date in the
    same ten-digit encoding, for --from/--to)."""
    cur.executescript(FTS_SQL)
    ukey = "CASE WHEN v.uploaded GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*' THEN printf('%010d', CAST(substr(v.uploaded,1,4) AS INTEGER) + 1000000000) || substr(v.uploaded,5,6) ELSE '9999999999-99-99' END"
    nz = lambda c: f"coalesce({c},'')"
    cur.execute(f"""INSERT INTO rows_fts(kind, video, n, date, speaker, text, extra, sort_key)
        SELECT 'claims', c.video, c.n, c.time, c.speaker, c.claim,
               'topic: ' || {nz('c.topic')} || '; source: ' || {nz('c.source_class')} || '; move: ' || {nz('c.move')} || '; note: ' || {nz('c.note')}, {ukey}
        FROM claims c JOIN videos v ON v.id = c.video""")
    cur.execute(f"""INSERT INTO rows_fts(kind, video, n, date, speaker, text, extra, sort_key)
        SELECT 'tl', t.video, t.n, t.date_stated, t.speaker_basis, t.event,
               'sortable: ' || {nz('t.sortable')} || '; chain: ' || {nz('t.chain')} || '; link: ' || {nz('t.link')} || '; agreement: ' || {nz('t.agreement')}, t.sort_key
        FROM timeline t""")
    cur.execute(f"""INSERT INTO rows_fts(kind, video, n, date, speaker, text, extra, sort_key)
        SELECT 'audit', a.video, a.n, a.time, a.asked_by, {nz('a.question')} || ' => ' || {nz('a.answer')},
               'move: ' || {nz('a.move')} || '; basis: ' || {nz('a.basis')} || '; note: ' || {nz('a.note')}, {ukey}
        FROM audit_rows a JOIN videos v ON v.id = a.video""")
    cur.execute(f"""INSERT INTO rows_fts(kind, video, n, date, speaker, text, extra, sort_key)
        SELECT 'quote', q.video, q.n, q.time, '', q.quote, '', {ukey}
        FROM quotes q JOIN videos v ON v.id = q.video""")
    cur.execute(f"""INSERT INTO rows_fts(kind, video, n, date, speaker, text, extra, sort_key)
        SELECT 'people', m.video, m.name, m.times, m.name, {nz('m.role')} || '; ' || {nz('m.detail')}, 'relation: ' || {nz('m.relation')}, {ukey}
        FROM mentions m JOIN videos v ON v.id = m.video""")
    return cur.execute("SELECT COUNT(*) FROM rows_fts").fetchone()[0]

def main():
    db = DB; report = "--report" in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv: sys.exit(__doc__ or "usage: python3 tools/build_db.py [--report] [--db PATH]")
    if "--db" in sys.argv: db = sys.argv[sys.argv.index("--db") + 1]
    con = sqlite3.connect(db); cur = con.cursor(); cur.executescript(SCHEMA)
    # the database is derived: a table this build does not make (one a pack renamed, or an older build's) is dropped (7b2, 2026-10-23)
    made = {m.lower() for m in re.findall(r"CREATE (?:VIRTUAL )?TABLE (\w+)", SCHEMA)}
    for (t,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        if t.lower() not in made and not t.lower().startswith(("rows_fts", "sqlite_")):
            cur.execute(f'DROP TABLE IF EXISTS "{t}"'); print(f"build_db: dropped the stale table {t}", file=sys.stderr)
    notes = sorted(glob.glob(os.path.join(ROOT, "videos", "*.md")) + glob.glob(os.path.join(ROOT, "books", "*.md")))  # book notes in the house schema are loaded like video notes (2026-09-28)
    totals = {"claims": 0, "audit": 0, "people": 0, "works": 0, "objects": 0, "quotes": 0, "oq": 0, "xc": 0, "tl": 0}
    for path in notes:
        o = parse_note(path); m = o["meta"]; v = o["id"]
        cur.execute("INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (v, o["file"], m.get("title"), m.get("channel"), m.get("host"), m.get("guest"), m.get("speakers") or m.get("speaker"), m.get("url"), m.get("uploaded"), m.get("recorded"), m.get("length"), m.get("added to notes"), m.get("description"), m.get("transcript"), o["words"]))
        cur.executemany("INSERT INTO video_subjects VALUES (?,?)", [(v, s) for s in o["subjects"]])
        cur.executemany("INSERT INTO tags VALUES (?,?)", [(v, t) for t in o["tags"]])
        cur.executemany("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["claims"]])
        cur.executemany("INSERT INTO audit_rows VALUES (?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["audit"]])
        if o["counts"]: cur.execute("INSERT INTO audit_counts VALUES (?,?,?,?,?,?,?)", (v, *o["counts"]))
        for r in o["people"]:
            cur.execute("INSERT OR IGNORE INTO people VALUES (?)", (r[0],))
            cur.execute("INSERT INTO mentions VALUES (?,?,?,?,?,?)", (v, *r))
        cur.executemany("INSERT INTO works VALUES (?,?,?,?,?,?)", [(v, *r) for r in o["works"]])
        cur.executemany(f"INSERT INTO {OBJ} VALUES (?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["objects"]])
        cur.executemany("INSERT INTO quotes VALUES (?,?,?,?)", [(v, *q) for q in o["quotes"]])
        cur.executemany("INSERT INTO tracker_candidates VALUES (?,?,?,?,?,?)", [(v, *r) for r in o["cands"]])
        cur.executemany("INSERT INTO open_questions VALUES (?,?,?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["oq"]])
        cur.executemany("INSERT INTO cross_checks VALUES (?,?,?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["xc"]])
        cur.executemany("INSERT INTO timeline VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [(v, *r) for r in o["tl"]])
        cur.executemany("INSERT INTO sections VALUES (?,?,?)", [(v, h, ln) for h, ln in o["sections"]])
        cur.executemany("INSERT INTO build_report VALUES (?,?,?,?)", [(v, *r) for r in o["report"]])
        for k in totals: totals[k] += len(o[k])
    cur.executemany("INSERT INTO register VALUES (?,?,?,?,?,?,?)", parse_register())
    cur.executemany("INSERT INTO tracker VALUES (?,?,?,?,?,?,?,?)", parse_tracker())
    cur.executemany("INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", parse_relations())
    cur.executemany("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?)", parse_leads())
    cur.executemany("INSERT INTO subject_rows VALUES (?,?,?,?,?)", parse_subjects())
    for w in SUBJECT_WARNINGS: print(f"build_db: warning: {w}", file=sys.stderr)
    ar, sr = parse_actor_register(); cur.executemany("INSERT INTO actors VALUES (" + ",".join("?" * 19) + ")", ar); cur.executemany("INSERT INTO polity_statements VALUES (" + ",".join("?" * 19) + ")", sr)
    pg, pl = parse_pages(); cur.executemany("INSERT INTO pages VALUES (?,?,?,?,?,?,?)", pg); cur.executemany("INSERT INTO page_links VALUES (?,?,?,?)", pl)
    nv, nn, nc = parse_narratives(); cur.executemany("INSERT INTO narratives VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", nv); cur.executemany("INSERT INTO narrative_nodes VALUES (?,?,?,?,?,?,?,?,?,?)", nn); cur.executemany("INSERT INTO narrative_contradictions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", nc)
    def _own(kind):
        try: return json.load(open(os.path.join(ROOT, "owner", kind + ".json"), encoding="utf-8"))
        except (OSError, ValueError): return {}
    cur.executemany("INSERT INTO owner_notes VALUES (?,?,?,?,?,?,?)", [(i, d.get("title"), ", ".join(d.get("tags") or []), d.get("body"), json.dumps(d.get("links") or [], ensure_ascii=False), d.get("created"), d.get("updated")) for i, d in _own("notes").items()])
    cur.executemany("INSERT INTO owner_investigations VALUES (?,?,?,?,?,?,?)", [(i, d.get("title"), d.get("body"), d.get("origin"), d.get("base"), d.get("created"), d.get("updated")) for i, d in _own("investigations").items()])
    nfts = build_fts(cur)  # tools/rows_search.py (2026-10-15)
    con.commit()
    nxc = cur.execute("SELECT COUNT(*) FROM build_report WHERE section='cross checks' AND status='ok'").fetchone()[0]
    ntl = cur.execute("SELECT COUNT(*) FROM build_report WHERE section='timeline' AND status='ok'").fetchone()[0]
    nreg = cur.execute("SELECT COUNT(*) FROM register").fetchone()[0]; ntr = cur.execute("SELECT COUNT(*) FROM tracker").fetchone()[0]; nsr = cur.execute("SELECT COUNT(*) FROM subject_rows").fetchone()[0]; nld = cur.execute("SELECT COUNT(*) FROM leads").fetchone()[0]; nrel = cur.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    print(f"{os.path.relpath(db, ROOT)}: {len(notes)} videos; claims {totals['claims']}, audit rows {totals['audit']}, people {totals['people']}, works {totals['works']}, {OBJ_LABEL} {totals['objects']}, quotes {totals['quotes']}, open questions {totals['oq']}, cross-checks {totals['xc']} ({nxc} notes with the section, {len(notes) - nxc} missing); timeline rows {totals['tl']} ({ntl} notes with the section); register {nreg}, tracker {ntr}, subject rows {nsr}, leads {nld}, relations {nrel}, actors {len(ar)} ({sum(1 for x in ar if x[15] != "unplaced")} placed, {sum(1 for x in ar if x[15] == "unplaced")} unplaced), polity statements {len(sr)}, research pages {len(pg)} ({sum(1 for x in pg if not x[4])} authored, {len(pl)} link pairs); rows_fts {nfts} rows (tools/rows_search.py)")
    gaps = cur.execute("""SELECT video, section, status FROM build_report WHERE status != 'ok'
        AND NOT (section = 'cross checks' AND status = 'missing') AND NOT (section = 'timeline' AND status = 'missing') ORDER BY video, section""").fetchall()
    bad = {}
    for v, s, st in gaps: bad.setdefault(v, []).append(s)
    print(f"notes with sections not in schema: {len(bad)} of {len(notes)}")
    if report:
        for v, ss in bad.items(): print(f"  {v}: {', '.join(ss)}")
        xc = cur.execute("SELECT video, rows FROM build_report WHERE section='cross checks' AND status='ok' ORDER BY video").fetchall()
        print(f"cross-checks section (schema 10) in {len(xc)} notes: " + (", ".join(f"{v} ({n})" for v, n in xc) or "none")
              + f"; missing in {len(notes) - len(xc)} (not a gap until retrofitted)")
        tl = cur.execute("SELECT video, rows FROM build_report WHERE section='timeline' AND status='ok' ORDER BY video").fetchall()
        print(f"timeline section (schema 11) in {len(tl)} notes: " + (", ".join(f"{v} ({n})" for v, n in tl) or "none") + f"; missing in {len(notes) - len(tl)} (not a gap until retrofitted)")
    con.close()

if __name__ == "__main__":
    main()
