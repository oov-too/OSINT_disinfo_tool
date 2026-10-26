#!/usr/bin/env python3
"""Narrative pages: parse, score and compare (tools/narratives.md section 7).
Usage:
  python3 tools/narratives.py research/narrative-negligence.md [...]      parse each page; recompute downstream closures from Depends on,
                                                                       recompute the score line, report mismatches with the page's own line
  python3 tools/narratives.py --all                                     every research/narrative-*.md that is a narrative (not synchrony, not the register)
  python3 tools/narratives.py --all --json <out.json>                   machine-readable (used by build_db.py and the register agent)
  python3 tools/narratives.py --all --recurring                         contradictions that recur across narratives (the ones to investigate next)
  python3 tools/narratives.py --all --tree                              the family tree: mainlines and their forks with deltas
  python3 tools/narratives.py --sweep <page> --out <file.md>            the contradiction sweep (change 30): contradicts and drifts rows, cross-checks and
                                                                       divergence leads on the page's cited notes, marked covered or missing in its ledger
  python3 tools/narratives.py --interests <page> --out <file.md>        the Interests seed (relations-register edges for every carrier named in Nodes)
  python3 tools/narratives.py --audit <page> --out <file.md>            the attacker's mechanical tests: citations with snippets, the sweep, circle roots per
                                                                       node from the relations register, downstream mismatches, walls per carrier, and the basis audit
                                                                       (each node's class inferred from its rows against its Basis cell; 2026-10-25)
  python3 tools/narratives.py --check <page> [--v03-ok]                 the score line's form (v0.4) and the sections' presence; exit 1 on a failure; a page whose
                                                                       Nodes table has a Basis column needs a class in every cell and `thin nodes N of N` agreeing
  python3 tools/narratives.py --row '<note> tl|claims|audit|xc <n>'      print one database row in full (for digest and sweep index lines)
  python3 tools/narratives.py --rows <file|->                            print every row referenced in the file, in one call (batch the lookups)
  python3 tools/narratives.py --section <page> '<heading>|latest:<heading>'  print one section only (read sections, not pages)
  python3 tools/narratives.py --slim <page> [--out-dir d]                move receipts and earlier passes off the page (points 2, 3; after an attack hands back)
  python3 tools/narratives.py --diff <before> <after> [--out f]           row-level diff of two versions, for the attacker (point 6)
  python3 tools/narratives.py --adoptions <page> [--all] [--out f]        the adoption check (tools/adoption_check.py): the Revision table's adopted objections
                                                                       with their Rows read resolved and printed, leads resolved, page rows changed; exit 1 on a fail
Outputs go to --out (an agent passes its wip folder); nothing is written into the page. Agents never pass a tool's output through their own
reply; they read the file (tools/filter-blocks.md section 9).
Reads the pages only; never writes a page. The score line is `Narrative scores: clusters N, rows N, roots N, contradictions N, load X.X,
max downstream N, unaffiliated roots N of N, survive under rival N of N, tests N[, thin nodes N of N].` (v0.4; the thin-nodes axis optional, 2026-10-25; closures predicted retired from the line 2026-10-09) Downstream of a ledger row = the forward closure of the
nodes that depend (directly or transitively) on the row's node, counted without the node itself. Weight = core/periphery × independence ×
(1 + downstream / node count); the page's Weight cell is read as given, the load recomputed from the cells, and both are reported.
"""
import re, sys, os, glob, json, datetime
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
SCORE_RE = re.compile(r"Narrative scores: clusters (\d+), rows (\d+), roots (\d+),(?: circle roots (\d+),)?(?: reading roots (\d+),)? contradictions (\d+), load ([\d.]+), max downstream (\d+),(?: closures predicted (\d+) of (\d+),)? unaffiliated roots (\d+) of (\d+),(?: survive under rival (\d+) of (\d+),)? tests (\d+)(?:, thin nodes (\d+) of (\d+))?\.")  # v0.1 to v0.4 lines (change 26, 35; closures predicted retired 2026-10-09, proposal 24); the optional trailing thin-nodes axis from 2026-10-25 (section 8e)
SCORE_KEYS = ["clusters", "rows", "roots", "circle_roots", "reading_roots", "contradictions", "load", "max_downstream", "closures_pred", "closures_all", "unaff_roots", "roots_all", "survive", "nodes_all", "tests", "thin", "thin_all"]
# The Basis column (tools/narratives.md section 5 and 8e, 2026-10-25): optional, since pages built before carry none and are read as before.
BASIS_ORDER = ["document", "record", "recollection", "inference", "press"]   # strongest first
THIN_BASES = {"recollection", "inference", "press"}
def basis_cell(cell):
    """(basis, thin) of one Basis cell: `document`, `recollection; thin`, ... -> ("recollection", True); ("", False) when the cell names no class.
    A cell is thin when it says so or when its class is one of the thin classes."""
    c = (cell or "").strip().lower(); m = re.match(r"\s*(%s)\b" % "|".join(BASIS_ORDER), c)
    b = m.group(1) if m else ""
    return b, bool(b) and (b in THIN_BASES or bool(re.search(r"\bthin\b", c)))
def section(txt, heading): return LN.section_text(txt, heading)   # form S4
def table(body): return LN.loose_table(body)                      # form T2
def meta(txt): return LN.meta_text(txt)                           # form M2
def ints(s): return [int(x) for x in re.findall(r"\d+", s or "")]
# Reading edges (tools/narratives.md, edge rule of proposal 27; 7b2 item 16, 2026-10-23): a Depends-on cell writes an edge the page reads but
# no row supports as `(reading: n)` (or `(reading: node fourteen, <why>)`); that edge is left out of the downstream closure and counted.
# Every other digit in the cell is read as before (the plain edges, and the digits of `parent N`, `upstream N` the fork pages write).
READING_RE = re.compile(r"\(\s*reading\s*:\s*([^()]*)\)", re.I)
_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
          "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUM_TOKEN = re.compile(r"\s*(?:nodes?\s+)?(\d+|(?:%s)(?:[- ](?:%s))?|%s)\b" % ("|".join(_TENS), "|".join(_UNITS[1:10]), "|".join(_UNITS[1:])), re.I)
def _num(tok):
    t = tok.lower()
    if t.isdigit(): return int(t)
    parts = re.split(r"[- ]", t)
    if parts[0] in _TENS: return _TENS[parts[0]] + (_UNITS.index(parts[1]) if len(parts) > 1 else 0)
    return _UNITS.index(parts[0])
def reading_targets(body):
    """The node numbers at the head of a `(reading: ...)` body: `14`, `14, 15`, `node fourteen`, `nodes 3 and 4`; the prose after them is ignored."""
    out, pos = [], 0
    while True:
        m = _NUM_TOKEN.match(body, pos)
        if not m: return out
        out.append(_num(m.group(1))); pos = m.end()
        sep = re.match(r"\s*(?:,|\band\b|&)\s*", body[pos:])
        if not sep: return out
        pos += sep.end()
def depends_on(cell):
    """(plain edges, reading edges, unresolved reading parentheticals) of one Depends-on cell, as node numbers."""
    cell = cell or ""; reading, unresolved = [], 0
    for m in READING_RE.finditer(cell):
        t = reading_targets(m.group(1)); reading += t; unresolved += 0 if t else 1
    return ints(READING_RE.sub(" ", cell)), reading, unresolved
def parse(p):
    txt = LN.read_text(p); stem = os.path.basename(p)[:-3]; md = meta(txt)
    nodes = table(section(txt, "Nodes")); ledger = table(section(txt, "Contradiction ledger"))
    nid = {}
    for r in nodes:
        try: nid[int(re.match(r"\d+", r.get("#", "")).group(0))] = r
        except Exception: pass
    _deps = {n: depends_on(r.get("depends on", "")) for n, r in nid.items()}
    dep = {n: set(x for x in d[0] if x in nid and x != n) for n, d in _deps.items()}   # plain edges only: a reading edge stays out of the closure
    reading_edges = sorted({(n, x) for n, d in _deps.items() for x in d[1] if x in nid and x != n})
    reading_unresolved = sum(d[2] for d in _deps.values()) + sum(1 for n, d in _deps.items() for x in d[1] if x not in nid or x == n)
    children = defaultdict(set)
    for n, ds in dep.items():
        for d in ds: children[d].add(n)
    def closure(n):
        seen, stack = set(), [n]
        while stack:
            x = stack.pop()
            for c in children[x]:
                if c not in seen: seen.add(c); stack.append(c)
        return seen
    out_ledger = []
    for r in ledger:
        ns = [x for x in ints(r.get("node", "")) if x in nid]; down = set()
        for n in ns: down |= closure(n)
        down -= set(ns)
        w_page = re.findall(r"[\d.]+", r.get("weight", "")); w_page = float(w_page[0]) if w_page else None
        dcell = r.get("downstream", "") or ""; mlead = re.match(r"\s*(\d+)\b", dcell)  # "11 (nodes 26, 27, ...)" -> 11; "26, 27, 28" -> 3; "none" -> 0 (fix 2026-10-08, found by the lineage attacker)
        d_page = int(mlead.group(1)) if mlead and (re.fullmatch(r"\s*\d+\s*", dcell) or re.match(r"\s*\d+\s*\(", dcell)) else len(ints(dcell))
        cited = set(LN.CITE_ONE_RE.findall(r.get("contradiction", "") + " " + r.get("side taken", "") + " " + r.get("other side", "")))
        leads_cited = set(re.findall(r"\blead(?:s)? (\d+(?:,\s*\d+)*)", r.get("contradiction", "") + " " + r.get("flare", "") + " " + r.get("why survivable", "")))
        leads_cited = set(int(x) for grp in leads_cited for x in re.findall(r"\d+", grp))
        out_ledger.append(dict(n=r.get("#", ""), nodes=ns, contradiction=r.get("contradiction", "")[:200], side=r.get("side taken", "")[:120], weight_page=w_page, downstream_page=d_page,
                               downstream_computed=len(down), flare=r.get("flare", ""), fork=r.get("fork", ""), rows=sorted(cited), leads=sorted(leads_cited)))
    roles = Counter(r.get("role", "").split()[0].lower() if r.get("role") else "" for r in nodes)
    roots = set()
    for r in nodes:
        for part in re.split(r";|,", r.get("carriers (independent roots)", r.get("carriers", ""))):
            part = re.sub(r"\(.*?\)", "", part).strip(" .")
            if part and len(part) < 80: roots.add(part.lower())
    rows = set(LN.CITE_ONE_RE.findall(section(txt, "Nodes")))  # keyed with kind (change 25)
    has_basis = any("basis" in r for r in nodes)
    basis = {n: basis_cell(r.get("basis", ""))[0] for n, r in nid.items()} if has_basis else {}
    thin = sorted(n for n, r in nid.items() if has_basis and basis_cell(r.get("basis", ""))[1])
    sc = section(txt, "Score card"); lines = SCORE_RE.findall(sc)
    tests = len([l for l in section(txt, "Tests").split("\n") if re.match(r"^\s*(\d+\.|-|\|\s*\d+)", l)])
    load_computed = round(sum((l["weight_page"] or 0) for l in out_ledger), 2)
    return dict(page=stem, kind=md.get("Kind", ""), mode=md.get("Mode", ""), parent=md.get("Parent", ""), thesis=md.get("Thesis", ""), alternative=md.get("Alternative", ""),
                span=md.get("Span", ""), lanes=md.get("Lanes", ""), status=md.get("Status", ""), nodes=len(nid), roles=dict(roles), row_citations=len(rows), roots_named=len(roots),
                ledger=out_ledger, contradictions=len(out_ledger), load_computed=load_computed, max_downstream_computed=max([l["downstream_computed"] for l in out_ledger] or [0]),
                flares=sum(1 for l in out_ledger if l["flare"].lower().startswith("possible")), fork_candidates=sum(1 for l in out_ledger if "candidate" in l["fork"].lower()),
                score_lines=[{k: (float(v) if v not in (None, "") else None) for k, v in zip(SCORE_KEYS, s)} for s in lines],
                tests_counted=tests, words=len(txt.split()), load_per_cluster=round(load_computed / len(nid), 3) if nid else None,
                reading_edges=len(reading_edges), reading_edges_unresolved=reading_unresolved,
                has_basis=has_basis, basis={str(n): b for n, b in basis.items()}, thin_nodes=len(thin), thin_node_list=thin,
                basis_tally=dict(Counter(b or "unmarked" for b in basis.values())) if has_basis else {})

CITE_RE = LN.CITE_RE                      # form C1
def citations(txt): return LN.citations(txt)
def _db():
    import sqlite3
    con = sqlite3.connect("file:notes.db?mode=ro", uri=True); con.row_factory = sqlite3.Row; return con

# The basis a node's rows carry (section 5, 8e; 2026-10-25), inferred from each row's Source class and chain and the kind of note it sits in.
# A note is a document note when research/source-kinds.md gives it the kind `document` (or, with no row there, when its file is under
# books/), and a press note when, besides, its Guest or Host field names a press form (the [tools.narratives] press_markers: an article,
# a news report, a forum thread). The classes, strongest first:
#   document      a host or firsthand row of a document note (the held document's own words or its author's act), or a read or hearsay
#                 row whose chain or attribution names a held document note (by the document number in its stem or its quoted title)
#   record        a read row whose work is not held (read on screen, through counsel or a hearing), or a hearsay row whose chain names
#                 a document not held (`(document`, a document number)
#   recollection  a firsthand row of a witness or press note (a witness's memory of events), or a hearsay row with no document behind it
#   inference     an inference row; a host row of a witness note (counsel's or the chair's own proposition) with no document behind it
#   press         a host row of a press note, or a press note's hearsay with no document behind it
# A timeline row takes the class its Speaker and basis cell states ((read), (hearsay), firsthand, (inference)) or, when the cell cites
# claims rows of its note, the strongest of theirs; else its note's default. An audit row is its witness's answer: recollection in a
# witness note, document in a document note. A cross-check carries no class of its own.
DOC_ID_RE = re.compile(r"(?:^|-)([a-z]{2,6}\d{5,})(?=-|$)")
DOC_MARK_RE = re.compile(r"\(document\b|\b[A-Z]{2,6}\d{5,}\b", re.I)
class NoteKinds:
    """Per note: kind (document, press, witness) and the held-document keys (document numbers in stems, quoted titles)."""
    def __init__(self, con):
        self.kind, self.keys = {}, []
        sk = {}
        if os.path.exists("research/source-kinds.md"):
            for r in table(LN.read_text("research/source-kinds.md")):
                if r.get("stem"): sk[r["stem"]] = (r.get("kind") or "").strip().lower()
        markers = [m.lower() for m in packload.tool_data("narratives").get("press_markers", [])]
        press_re = re.compile(r"\b(?:%s)s?\b" % "|".join(re.escape(m) for m in markers), re.I) if markers else None
        cols = {r[1] for r in con.execute("pragma table_info(videos)")}
        for r in con.execute("select * from videos"):
            vid = r["id"]; f = (r["file"] or "") if "file" in cols else ""
            k = sk.get(vid) or ("document" if f.startswith("books/") else "witness")
            if k == "document":
                meta = " ".join((r[c] or "") for c in ("guest", "host") if c in cols)
                if press_re and press_re.search(meta): k = "press"
            else: k = "witness"
            self.kind[vid] = k
            if k == "document":
                for m in DOC_ID_RE.finditer(vid): self.keys.append((m.group(1).lower(), vid))
                t = re.search(r"[\"“]([^\"”]{12,})[\"”]", (r["title"] or "") if "title" in cols else "")
                if t and len(t.group(1).split()) >= 3: self.keys.append((t.group(1).lower(), vid))
    def held(self, text):
        """The held document note a chain or attribution names, or None."""
        t = (text or "").lower()
        for k, vid in self.keys:
            if k in t: return vid
        return None
def _claim_basis(nk, note, r):
    sc = (r["source_class"] or "").strip().lower(); chain = " ".join(filter(None, [r["chain"] if "chain" in r.keys() else "", r["attribution"] if "attribution" in r.keys() else ""]))
    nkind = nk.kind.get(note, "witness"); held = nk.held(chain); docmark = bool(DOC_MARK_RE.search(chain))
    if sc in ("host", "firsthand") and nkind == "document": return "document", f"{sc} row of a document note"
    if sc in ("read", "hearsay") and held: return "document", f"{sc}; the work is held ({held})"
    if sc == "read": return "record", "read; the work is not held"
    if sc == "hearsay" and docmark: return "record", "hearsay; the chain names a document not held"
    if sc == "hearsay": return ("press" if nkind == "press" else "recollection"), "hearsay with no document behind it"
    if sc == "firsthand": return "recollection", f"firsthand in a {nkind} note"
    if sc == "inference": return "inference", "inference row"
    if sc == "host" and nkind == "press": return ("record" if docmark else "press"), "host row of a press note" + ("; the chain names a document" if docmark else "")
    if sc == "host": return ("record" if docmark else "inference"), "host row of a witness note" + ("; the chain names a document" if docmark else "")
    return "", f"source class {sc or 'empty'}"
def row_basis(con, nk, note, kind, n):
    """(basis, why) of one cited row; ("", why) when the row is missing or carries no class."""
    if kind == "claims":
        r = con.execute("select * from claims where video=? and n=?", (note, n)).fetchone()
        return _claim_basis(nk, note, r) if r else ("", "not in notes.db")
    if kind == "tl":
        r = con.execute("select * from timeline where video=? and n=?", (note, n)).fetchone()
        if not r: return "", "not in notes.db"
        sb = (r["speaker_basis"] or "") + " " + (r["chain"] or ""); refs = []
        for m in re.finditer(r"\bclaims (\d+(?:\.\d+)?)(?:\s*(?:to|-|–)\s*(\d+))?", sb):
            a = float(m.group(1)); b = float(m.group(2)) if m.group(2) else a
            refs += [str(int(a)) if a.is_integer() else str(a)] + [str(x) for x in range(int(a) + 1, int(b) + 1)]
        got = [_claim_basis(nk, note, c) for c in (con.execute("select * from claims where video=? and n=?", (note, x)).fetchone() for x in refs[:40]) if c]
        got = [g for g in got if g[0]]
        if got: b = min(got, key=lambda g: BASIS_ORDER.index(g[0])); return b[0], "timeline row; its claims rows: " + b[1]
        held = nk.held(sb); nkind = nk.kind.get(note, "witness"); low = sb.lower()
        if held: return "document", f"timeline row naming a held document ({held})"
        if "(read" in low: return "record", "timeline row, read; the work is not held"
        if "(hearsay" in low: return ("record" if DOC_MARK_RE.search(sb) else ("press" if nkind == "press" else "recollection")), "timeline row, hearsay"
        if "inference" in low: return "inference", "timeline row, inference"
        if "firsthand" in low: return ("document" if nkind == "document" else "recollection"), f"timeline row, firsthand in a {nkind} note"
        return {"document": "document", "press": "press"}.get(nkind, "recollection"), f"timeline row; the {nkind} note's default"
    if kind == "audit":
        r = con.execute("select 1 from audit_rows where video=? and n=?", (note, n)).fetchone()
        if not r: return "", "not in notes.db"
        nkind = nk.kind.get(note, "witness"); return ("document" if nkind == "document" else "recollection"), f"audit row (the {nkind} note's answer)"
    return "", "a cross-check carries no class"
def node_basis(con, nk, rows_cell):
    """(strongest basis, [(ref, basis, why)]) of a Rows cell's citations."""
    per = [((note, kind, n),) + row_basis(con, nk, note, kind, n) for note, kind, n in citations(rows_cell or "")]
    have = [p for p in per if p[1]]
    return (min(have, key=lambda p: BASIS_ORDER.index(p[1]))[1] if have else ""), per
NAME_RE = re.compile(r"^(?:u/[A-Za-z0-9_]+|(?:[A-Z][A-Za-z'.-]+|de|von|van|der)(?:\s+(?:[A-Z][A-Za-z'.-]+|de|von|van|der)){0,3})$")
import packload; STOP = set(packload.tool_data("narratives")["stop_names"])   # words a chain cell names that are not a teller ([tools.narratives]; phase 7b)
def _clean_name(part):
    part = re.sub(r"\(.*?\)", "", part); part = re.sub(r"\[.*?\]", "", part)
    part = re.sub(r"^\s*\d+\s*:\s*", "", part); part = re.sub(r"^(root|relay|roots|firsthand|relayed|via|through)\s*:?\s*", "", part, flags=re.I)
    part = part.strip(" .*'\"“”‘’:;")
    part = re.sub(r"^(the|an?|all|most|some|his|her|their)\s+", "", part, flags=re.I)
    return part.strip()
def _carriers(txt):
    names = []
    for r in table(section(txt, "Nodes")):
        cell = r.get("carriers (independent roots)", r.get("carriers", ""))
        for part in re.split(r";|,|\band\b|<-|->|/", cell):
            part = _clean_name(part)
            if part and NAME_RE.match(part) and part not in STOP and not re.search(r"\d", part): names.append(part)
    return names
def _alias_map():
    try: al = json.load(open("tools/name_aliases.json"))
    except Exception: return {}
    m = {}
    for canon, vs in al.items():
        if canon.startswith("_"): continue
        m[canon.lower()] = canon
        for v in vs: m[v.lower()] = canon
    return m
def _rel_rows(con, name, am):
    key = am.get(name.lower(), name); sur = key.split()[-1].lower()
    rows = con.execute("select n, a, b, kind, hierarchy, when_, what, confidence, a_canon, b_canon from relations where lower(coalesce(a_canon,a)) = ? or lower(coalesce(b_canon,b)) = ?", (key.lower(), key.lower())).fetchall()
    if not rows and len(sur) > 3:
        rows = con.execute("select n, a, b, kind, hierarchy, when_, what, confidence, a_canon, b_canon from relations where lower(coalesce(a_canon,a)) like ? or lower(coalesce(b_canon,b)) like ?", (f"%{sur}%", f"%{sur}%")).fetchall()
    return rows
AFFIL = ("employer", "member-of", "funder", "founder", "directs", "owner", "operator", "student-of", "patient-of"); OPP = ("adversary", "critic")
def sweep(page, out=None):
    txt = LN.read_text(page); con = _db()
    cites = citations(section(txt, "Nodes") + section(txt, "Contradiction ledger")); notes = sorted({c[0] for c in cites})
    ledger_cites = set((c[0], c[1], c[2]) for c in citations(section(txt, "Contradiction ledger")))
    node_cites = set((c[0], c[1], c[2]) for c in citations(section(txt, "Nodes")))
    lines = [f"# Contradiction sweep for {os.path.basename(page)} ({len(notes)} cited notes, {len(node_cites)} node citations)", "", "Change 30 (tools/narratives.md): every row below gets a ledger row or a one-line reason for leaving it out. `covered` = a ledger row already cites that row; `missing` = no ledger row cites it. Rows are the database's; the page's own judgement decides.", ""]
    miss = cov = 0
    lines.append("## A. Cited timeline rows tagged contradicts or drifts"); 
    for (note, kind, n) in sorted(node_cites | ledger_cites):
        if kind != "tl": continue
        r = con.execute("select n, date_stated, event, agreement_kind, agreement from timeline where video=? and n=?", (note, n)).fetchone()
        if r and r["agreement_kind"] in ("contradicts", "drifts"):
            st = "covered" if (note, "tl", n) in ledger_cites else "missing"; miss += st == "missing"; cov += st == "covered"
            lines.append(f"- [{st}] [{note} tl {n}] {r['date_stated']}: {(r['event'] or '')[:180]} | {r['agreement_kind']}: {(r['agreement'] or '')[:220]}")
    lines.append(""); lines.append("## B. Other contradicts and drifts rows in the cited notes (not cited by the page; no cap, owner ruling 2026-10-09)")
    for note in notes:
        rows = con.execute("select n, date_stated, event, agreement_kind, agreement from timeline where video=? and agreement_kind in ('contradicts','drifts') order by n_sort", (note,)).fetchall()
        rows = [r for r in rows if (note, "tl", str(r["n"])) not in node_cites | ledger_cites]
        if not rows: continue
        lines.append(f"- {note}: {len(rows)} rows")
        for r in rows: lines.append(f"  - [{note} tl {r['n']}] {r['date_stated']}: {(r['event'] or '')[:150]} | {r['agreement_kind']}: {(r['agreement'] or '')[:160]}")
    lines.append(""); lines.append("## C. Cross-checks of kind or verdict contradicts in the cited notes (no cap)")
    for note in notes:
        rows = con.execute("select n, kind, verdict, this_note, elsewhere from cross_checks where video=? and (lower(kind) like '%contradict%' or lower(verdict) like '%contradict%')", (note,)).fetchall()
        for r in rows: lines.append(f"- [{note} xc {r['n']}] {r['kind']}/{r['verdict']}: {(r['this_note'] or '')[:150]} || {(r['elsewhere'] or '')[:150]}")
    lines.append(""); lines.append("## D. Divergence leads whose sources name a cited note (no cap)")
    k = 0
    for r in con.execute("select n, lead, sources, status from leads where kind='divergence'"):
        if any(note in (r["sources"] or "") or note in (r["lead"] or "") for note in notes):
            lines.append(f"- lead {r['n']} ({r['status']}): {(r['lead'] or '')[:220]}"); k += 1
    lines.insert(3, f"Summary: section A {cov} covered, {miss} missing.")
    text = "\n".join(lines) + "\n"
    if out: LN.write_text(out, text); print("sweep written to", out, f"(A: {cov} covered, {miss} missing)")
    else: print(text)
def sweep_chunks(page, out, k):
    """--sweep <page> --out <file> --chunks k: the sweep's rows (every `- [` and `- lead N` line) cut into k chunks of near-equal size,
    each under its section headings, written beside <file> as <stem>-chunk-1.md ... <stem>-chunk-k.md (the form wip/narratives-1009/
    make_args2.py wrote; phase 4 handoff 7). Every row is in exactly one chunk."""
    import math
    lines = LN.read_lines(out)
    rows = [i for i, l in enumerate(lines) if re.match(r"^\s*- \[", l) or re.match(r"^- lead \d+", l)]
    k = max(1, min(k, len(rows) or 1)); per = math.ceil(len(rows) / k) if rows else 0
    if per: k = math.ceil(len(rows) / per)   # no empty last chunk
    stem = out[:-3] if out.endswith(".md") else out
    for j in range(k):
        sel = set(rows[j * per:(j + 1) * per]); o = [f"# Sweep chunk {j + 1} of {k} for {os.path.basename(page)} ({len(sel)} rows; every row needs a disposition line)", ""]
        cur = None
        for i, l in enumerate(lines):
            if l.startswith("## "): cur = l; continue
            if i in sel:
                if cur: o.append(cur); cur = None
                o.append(l)
        LN.write_text(f"{stem}-chunk-{j + 1}.md", "\n".join(o) + "\n")
    print(f"{k} chunks written beside {out} ({len(rows)} rows, up to {per} each)")
def interests(page, out=None, names=None):
    txt = LN.read_text(page) if page else ""; con = _db(); am = _alias_map()
    names = names or sorted(set(_carriers(txt)), key=str.lower)
    lines = [f"# Interests seed for {os.path.basename(page) if page else 'the given carriers'} ({len(names)} carriers)", "", "Seeded mechanically from research/relations-register.md (kinds employer, member-of, funder, founder, directs, owner, operator, student-of, patient-of; opponents adversary, critic). The author decides which parties the narrative benefits and classes each root: unaffiliated; affiliated and adverse (adversity from the carrier's own rows); affiliated and not adverse; unnamed roots apart (change 29).", "", "| Carrier | Affiliations (kind -> party [when], rel n) | Opponents | Classed as (author fills) |", "|---|---|---|---|"]
    for name in names:
        rows = _rel_rows(con, name, am); aff = []; opp = []
        for r in rows:
            kind = (r["kind"] or "").split(" ")[0]
            sur = name.split()[-1].lower(); a_side = sur in (r["a_canon"] or r["a"] or "").lower()
            other = r["b"] if a_side else r["a"]
            cell = f"{kind} -> {other}" + (f" [{r['when_']}]" if r["when_"] else "") + f" (rel {r['n']})"
            if kind in AFFIL: aff.append(cell)
            elif kind in OPP: opp.append(cell)
        if not rows: aff = ["no register row (unnamed or unregistered)"]
        lines.append(f"| {name} | {'; '.join(aff[:10])}{' (+%d more)' % (len(aff)-10) if len(aff) > 10 else ''} | {'; '.join(opp[:6])} | |")
    text = "\n".join(lines) + "\n"
    if out: LN.write_text(out, text); print("interests seed written to", out, f"({len(names)} carriers)")
    else: print(text)
def circles(con, names, am):
    """Group carriers that share an employer, member-of, founder or directs party (one circle per shared party; a carrier may sit in several)."""
    party_of = {}
    for n in names:
        for r in _rel_rows(con, n, am):
            kind = (r["kind"] or "").split(" ")[0]
            if kind in ("employer", "member-of", "founder", "directs", "owner", "operator"):
                sur = n.split()[-1].lower(); other = r["b"] if sur in (r["a_canon"] or r["a"] or "").lower() else r["a"]
                other = re.sub(r"\(.*?\)", "", other).strip().lower()
                if any(other.endswith(x.split()[-1].lower()) for x in names if x != n): continue  # a person, not a body
                party_of.setdefault(n, set()).add(other)
    groups = []; seen = set()
    for n in names:
        if n in seen: continue
        g = {n}; seen.add(n); ps = set(party_of.get(n, ()))
        changed = True
        while changed:
            changed = False
            for m in names:
                if m in seen: continue
                if party_of.get(m) and ps & party_of[m]: g.add(m); seen.add(m); ps |= party_of[m]; changed = True
        groups.append((g, ps))
    return groups
def audit(page, out=None):
    txt = LN.read_text(page); con = _db(); am = _alias_map(); r = parse(page)
    lines = [f"# Mechanical audit of {os.path.basename(page)} (tools/narratives.py --audit, {__import__('datetime').date.today().isoformat()})", "", "The attacker starts here (brief-attack.md): these are tests 1, 2 (part), 3 (part) and 5 (part) done mechanically; the attacker spends on judgement: do the rows say what the node says, is the other side's best evidence stated, are the tests runnable.", ""]
    # 1 citations with snippets
    cites = citations(section(txt, "Nodes") + section(txt, "Contradiction ledger")); missing = []; shown = 0
    lines.append(f"## 1. Citations ({len(cites)} in Nodes and ledger): existence and snippet")
    for (note, kind, n) in cites:
        if kind == "tl": row = con.execute("select event as t from timeline where video=? and n=?", (note, n)).fetchone()
        elif kind == "claims": row = con.execute("select claim as t from claims where video=? and n=?", (note, n)).fetchone()
        else: row = con.execute("select answer as t from audit_rows where video=? and n=?", (note, n)).fetchone()
        if not row: missing.append(f"[{note} {kind} {n}]"); continue
        if shown < 400: lines.append(f"- [{note} {kind} {n}] {(row['t'] or '')[:160]}"); shown += 1
    lines.insert(4, f"Missing from notes.db: {len(missing)}" + (": " + ", ".join(missing[:40]) if missing else ""))
    # 2 roots and circles per node
    lines.append(""); lines.append("## 2. Carriers per node and circle collapse (shared employer, member-of, founder, directs party in the relations register)")
    for nd in table(section(txt, "Nodes")):
        cell = nd.get("carriers (independent roots)", nd.get("carriers", "")); names = []
        for part in re.split(r";|,|\band\b|<-|->|/", cell):
            part = _clean_name(part)
            if part and NAME_RE.match(part) and part not in STOP and not re.search(r"\d", part) and part not in names: names.append(part)
        if len(names) < 2: continue
        gs = circles(con, names, am); multi = [g for g in gs if len(g[0]) > 1]
        if multi: lines.append(f"- node {nd.get('#','?')}: {len(names)} carriers -> {len(gs)} after circle collapse; circles: " + "; ".join("{" + ", ".join(sorted(g)) + "} via " + ", ".join(sorted(ps)[:3]) for g, ps in multi))
    # 3 downstream mismatches
    lines.append(""); lines.append("## 3. Downstream: page cell against the closure computed from Depends on")
    mm = [l for l in r["ledger"] if l["downstream_page"] != l["downstream_computed"]]
    lines.append(f"{len(mm)} mismatches" + ("" if not mm else ": " + "; ".join(f"row {l['n']} page {l['downstream_page']} computed {l['downstream_computed']}" for l in mm[:30])))
    # 4 walls per carrier (claims moves by topic; audit rows closed where the carrier is the guest)
    lines.append(""); lines.append("## 4. Walls per carrier (closed claims rows by topic; stated grounds from audit rows where the carrier is the note's guest)")
    for name in sorted(set(_carriers(txt)), key=str.lower)[:60]:
        sur = name.split()[-1]
        rows = con.execute("select topic, count(*) c from claims where speaker like ? and move in ('closed-subtle','closed-outright') group by topic order by c desc", (f"%{sur}%",)).fetchall()
        if not rows: continue
        bases = con.execute("select basis, count(*) c from audit_rows a join videos v on v.id=a.video where v.guest like ? and a.move in ('closed-subtle','closed-outright') and basis not in ('','none','none stated','None','n/a') group by basis order by c desc limit 6", (f"%{sur}%",)).fetchall()
        lines.append(f"- {name}: " + ", ".join(f"{x['topic']} {x['c']}" for x in rows[:6]) + (" | grounds: " + "; ".join(f"{b['basis'][:50]} ({b['c']})" for b in bases) if bases else ""))
    # 5 the sweep
    tmp = out + ".sweep.md" if out else None
    lines.append(""); lines.append("## 5. The contradiction sweep" + (f" (written beside this file as {os.path.basename(tmp)})" if tmp else ""))
    if tmp: sweep(page, tmp)
    # 6 the basis audit (test 9, section 8e)
    lines.append(""); lines += basis_audit_lines(txt, con, r)
    text = "\n".join(lines) + "\n"
    if out: LN.write_text(out, text); print("audit written to", out, f"(citations {len(cites)}, missing {len(missing)}, downstream mismatches {len(mm)})")
    else: print(text)
def basis_audit_lines(txt, con, r):
    """The audit's Basis section: per node the basis inferred from its rows (the strongest class), the page's own cell, a mismatch flag,
    and the row that carries the inferred class; then the tallies and the thin count against the score line's axis."""
    nk = NoteKinds(con); out = ["## 6. Basis: the class each node's rows carry, against the page's Basis cell (test 9; tools/narratives.md section 8e)", ""]
    out.append("Inferred = the strongest class among the node's cited rows (document, record, recollection, inference, press), from each row's Source class and chain and its note's kind (document, press or witness: research/source-kinds.md and the note's Guest and Host). The inference reads the rows only; the page's cell is the author's judgement and may rightly differ (a row the tool cannot class, a document the chain does not name). A mismatch is a place to look, not a verdict.")
    if not r["has_basis"]: out.append("The page has no Basis column (a page built before 2026-10-25): the inferred column alone is given.")
    out += ["", "| # | Role | Page's Basis | Inferred | Mismatch | Carried by |", "|---|---|---|---|---|---|"]
    tally_inf, mism, thin_inf = Counter(), 0, 0
    for nd in table(section(txt, "Nodes")):
        m = re.match(r"\d+", nd.get("#", "") or "")
        if not m: continue
        inf, per = node_basis(con, nk, nd.get("rows", "")); tally_inf[inf or "unclassed"] += 1; thin_inf += inf in THIN_BASES
        page_b, page_thin = basis_cell(nd.get("basis", "")) if r["has_basis"] else ("", False)
        flag = ""
        if r["has_basis"]:
            if not page_b: flag = "page cell unmarked"
            elif inf and page_b != inf: flag = ("page stronger than its rows" if BASIS_ORDER.index(page_b) < BASIS_ORDER.index(inf) else "page weaker than its rows")
            elif (page_b in THIN_BASES) != page_thin: flag = "thin mark does not follow the class"
            mism += bool(flag)
        best = [p for p in per if p[1] == inf][:1]
        carry = (f"[{best[0][0][0]} {best[0][0][1]} {best[0][0][2]}] ({best[0][2]})" if best else "no classed row") + f"; rows classed {sum(1 for p in per if p[1])} of {len(per)}"
        out.append(f"| {m.group(0)} | {nd.get('role', '')} | {nd.get('basis', '') if r['has_basis'] else '(no column)'} | {inf or 'unclassed'} | {flag or 'no'} | {carry} |")
    out.append("")
    out.append("Inferred tally: " + ", ".join(f"{b} {tally_inf[b]}" for b in BASIS_ORDER + ["unclassed"] if tally_inf[b]) + f"; thin by inference {thin_inf} of {r['nodes']}.")
    if r["has_basis"]:
        out.append("Page's tally: " + ", ".join(f"{b} {n}" for b, n in sorted(r["basis_tally"].items(), key=lambda x: (BASIS_ORDER + ['unmarked']).index(x[0]) if x[0] in BASIS_ORDER + ['unmarked'] else 9)) + f"; thin nodes {r['thin_nodes']} of {r['nodes']} ({', '.join(map(str, r['thin_node_list'])) or 'none'}); mismatches {mism}.")
        last = r["score_lines"][-1] if r["score_lines"] else None
        if last and last.get("thin") is not None: out.append(f"Score line: thin nodes {int(last['thin'])} of {int(last['thin_all'])}" + (" (agrees)" if int(last["thin"]) == r["thin_nodes"] and int(last["thin_all"]) == r["nodes"] else f" (DISAGREES with the cells: {r['thin_nodes']} of {r['nodes']})"))
        else: out.append("Score line: no thin-nodes axis (the page has a Basis column, so its last score line should carry `thin nodes N of N`).")
    return out
SECTIONS_NARRATIVE = ["Thesis", "Nodes", "Contradiction ledger", "Synchrony", "Carriers", "Interests", "Objections", "Score card", "Forks", "Tests", "Leads returned", "Relations returned"]
def check(page):
    txt = LN.read_text(page); ok = True
    for h in SECTIONS_NARRATIVE:
        if not LN.has_section(txt, h): print("MISSING section:", h); ok = False
    lines = SCORE_RE.findall(section(txt, "Score card"))
    if not lines: print("MISSING score line"); ok = False
    else:
        last = lines[-1]
        if last[3] == "" or last[11] == "": print("score line is not v0.3 (needs circle roots, reading roots, survive under rival)"); ok = False
        if last[8] != "" and "--v03-ok" not in sys.argv: print("score line is v0.3: closures predicted was retired from the score line on 2026-10-09 (proposal 24); keep the closures table in Carriers and drop the pair from the line"); ok = False
    md = meta(txt)
    for k in ("Kind", "Mode", "Thesis", "Alternative", "Status"):
        if k not in md: print("MISSING metadata key:", k); ok = False
    r = parse(page); mm = [l for l in r["ledger"] if l["downstream_page"] != l["downstream_computed"]]
    if mm: print(f"downstream mismatches: {len(mm)} (run --audit)"); ok = False
    if r["has_basis"] and lines:   # a page with the Basis column (2026-10-25) carries the axis, and it agrees with the cells
        k = SCORE_KEYS.index("thin"); last = lines[-1]
        unmarked = [n for n, b in sorted(r["basis"].items(), key=lambda x: int(x[0])) if not b]
        if unmarked: print("Basis cells naming no class (document, record, recollection, inference, press): nodes", ", ".join(unmarked)); ok = False
        if last[k] == "": print("score line has no `thin nodes N of N` axis, but the Nodes table has a Basis column"); ok = False
        elif (int(last[k]), int(last[k + 1])) != (r["thin_nodes"], r["nodes"]): print(f"score line says thin nodes {last[k]} of {last[k + 1]}; the Basis cells give {r['thin_nodes']} of {r['nodes']}"); ok = False
    print("check:", "OK" if ok else "FAILED", page); return ok

def row(ref):
    con = _db()
    note, kind, n = LN.ROW_REF_RE.match(ref.strip()).groups()
    tab = {"tl": "timeline", "claims": "claims", "audit": "audit_rows", "xc": "cross_checks"}[kind]
    r = con.execute(f"select * from {tab} where video=? and n=?", (note, n)).fetchone()
    if not r: print("no such row"); return
    for k in r.keys():
        if r[k] not in (None, ""): print(f"{k}: {r[k]}")

def rows_batch(src):
    """--rows <file|->: print every referenced row in full, one block each; refs one per line as 'note tl n' or '[note claims n]'."""
    con = _db(); refs = (sys.stdin.read() if src == "-" else LN.read_text(src))
    seen = set()
    for m in LN.ROW_REF_RE.finditer(refs):
        key = m.groups()
        if key in seen: continue
        seen.add(key); note, kind, n = key
        tab = {"tl": "timeline", "claims": "claims", "audit": "audit_rows", "xc": "cross_checks"}[kind]
        r = con.execute(f"select * from {tab} where video=? and n=?", (note, n)).fetchone()
        print(f"=== [{note} {kind} {n}]")
        if not r: print("no such row"); continue
        for k in r.keys():
            if r[k] not in (None, "") and k not in ("video", "n", "n_sort"): print(f"{k}: {r[k]}")
    print(f"=== {len(seen)} refs")

def section_cmd(page, heading):
    """--section <page> <heading>: print one top-level section (heading matched as a prefix, so 'Objections (second pass)' and 'Objections' both work; 'latest:Objections' prints the last section whose heading starts so)."""
    txt = LN.read_text(page)
    latest = heading.startswith("latest:")
    m, body = LN.section_match(txt, heading[7:] if latest else heading, latest=latest)   # form S4 (S4b for latest:)
    if not m: print(""); return
    print(m.group(0) + body)

def slim(page, out_dir):
    """--slim <page> --out-dir <dir> (owner 2026-10-09, token points 2 and 3): moves the '### Rows read and left out' body to <dir>/<stem>-rows-left-out.md
    leaving a count line and pointer; moves every '## Objections*' and '## Revision*' section except the latest of each to research/narrative-history/<stem>.md
    (appended, dated), leaving a pointer line under the latest Objections heading. Idempotent."""
    txt = LN.read_text(page); stem = os.path.basename(page)[:-3]; os.makedirs(out_dir, exist_ok=True); moved = []
    # receipts
    m = re.search(r"^### Rows read and left out[^\n]*\n", txt, re.M)
    if m:
        body = txt[m.end():]; e = re.search(r"^#{1,3} ", body, re.M); body = body[:e.start()] if e else body  # #### sub-headings belong to the receipts
        n_lines = sum(1 for l in body.split("\n") if l.strip())
        if n_lines > 12:
            dest = os.path.join(out_dir, f"{stem}-rows-left-out.md")
            LN.append_text(dest, f"\n\n# {stem}: rows read and left out (moved {datetime.date.today().isoformat()})\n\n" + body.strip() + "\n")
            txt = txt[:m.end()] + f"\n{n_lines} sweep entries dispositioned, every one with a reason; the list is kept at {dest} (moved off the page {datetime.date.today().isoformat()}, owner ruling: receipts in the archive, not on the page).\n\n" + txt[m.end() + len(body):]
            moved.append(f"receipts {n_lines} lines -> {dest}")
    # earlier passes
    heads = [(mm.start(), mm.end(), mm.group(0)) for mm in re.finditer(r"^## [^\n]*\n", txt, re.M)]
    def sec_bounds(i):
        st, en, h = heads[i]; nxt = heads[i + 1][0] if i + 1 < len(heads) else len(txt); return st, nxt, h
    obj = [i for i, h in enumerate(heads) if h[2].startswith("## Objections")]
    rev = [i for i, h in enumerate(heads) if h[2].startswith("## Revision")]
    drop = sorted(set(obj[:-1] + rev[:-1]), reverse=True)
    if drop:
        hist = os.path.join("research", "narrative-history", f"{stem}.md"); os.makedirs(os.path.dirname(hist), exist_ok=True)
        chunks = []
        for i in drop:
            st, en, h = sec_bounds(i); chunks.append(txt[st:en]); txt = txt[:st] + txt[en:]
        LN.append_text(hist, f"\n\n# {stem}: earlier passes (moved {datetime.date.today().isoformat()})\n\n" + "\n".join(reversed(chunks)))
        mm = re.search(r"^## Objections[^\n]*\n", txt, re.M)
        if mm and "Earlier passes:" not in txt[mm.end():mm.end() + 300]:
            txt = txt[:mm.end()] + f"\nEarlier passes: {hist} (moved {datetime.date.today().isoformat()}; the Score card keeps every attacker line).\n" + txt[mm.end():]
        moved.append(f"{len(drop)} earlier Objections/Revision sections -> {hist}")
    LN.write_text(page, txt)
    print(f"{page}: " + ("; ".join(moved) if moved else "nothing to move") + f"; now {len(txt.split())} words")

def diff_pages(before, after, out=None):
    """--diff <before> <after> [--out f]: row-level diff for the attacker: nodes, ledger rows, edges, tests, score lines changed."""
    a, b = LN.read_text(before), LN.read_text(after); lines = [f"# Diff: {os.path.basename(before)} -> {os.path.basename(after)}", ""]
    def rows(txt, heading):
        t = table(section(txt, heading)); out = {}
        for r in t:
            k = (r.get("#") or r.get("Measure") or "").strip()
            if k: out[k] = r
        return out
    for heading, key in (("Nodes", "Node"), ("Contradiction ledger", "Contradiction"), ("Carriers", "Carrier"), ("Deltas against the parent", "Measure")):
        ra, rb = rows(a, heading), rows(b, heading)
        if not ra and not rb: continue
        added = [k for k in rb if k not in ra]; removed = [k for k in ra if k not in rb]
        changed = [k for k in rb if k in ra and rb[k] != ra[k]]
        lines.append(f"## {heading}: {len(added)} added, {len(removed)} removed, {len(changed)} changed (unchanged {len(rb) - len(added) - len(changed)})")
        for k in added: lines.append(f"- added {k}: " + " | ".join(f"{c}: {str(v)[:160]}" for c, v in rb[k].items() if v))
        for k in removed: lines.append(f"- removed {k}: " + " | ".join(f"{c}: {str(v)[:160]}" for c, v in ra[k].items() if v))
        for k in changed:
            cols = [c for c in rb[k] if rb[k].get(c) != ra[k].get(c)]
            lines.append(f"- changed {k} ({', '.join(cols)}):"); [lines.append(f"    {c}: {str(ra[k].get(c))[:220]}  ->  {str(rb[k].get(c))[:220]}") for c in cols]
        lines.append("")
    for heading in ("Tests", "Score card", "Thesis", "Forks"):
        sa, sb = section(a, heading), section(b, heading)
        la, lb = [l for l in sa.split("\n") if l.strip()], [l for l in sb.split("\n") if l.strip()]
        add = [l for l in lb if l not in la]; rem = [l for l in la if l not in lb]
        lines.append(f"## {heading}: {len(add)} lines added, {len(rem)} removed")
        for l in add: lines.append(f"+ {l[:300]}")
        for l in rem: lines.append(f"- {l[:300]}")
        lines.append("")
    text = "\n".join(lines) + "\n"
    if out: LN.write_text(out, text); print(f"diff written to {out} ({len(text.split())} words)")
    else: print(text)

if __name__ == "__main__":
    if "--adoptions" in sys.argv: import adoption_check; i = sys.argv.index("--adoptions"); sys.exit(adoption_check.main([sys.argv[i + 1]] + [a for j, a in enumerate(sys.argv[1:], 1) if j != i and j != i + 1]))
    if "--rows" in sys.argv: rows_batch(sys.argv[sys.argv.index("--rows") + 1]); sys.exit(0)
    if "--section" in sys.argv: i = sys.argv.index("--section"); section_cmd(sys.argv[i + 1], sys.argv[i + 2]); sys.exit(0)
    if "--slim" in sys.argv: slim(sys.argv[sys.argv.index("--slim") + 1], sys.argv[sys.argv.index("--out-dir") + 1] if "--out-dir" in sys.argv else "research/tasks/tool-feedback/receipts"); sys.exit(0)
    if "--diff" in sys.argv: i = sys.argv.index("--diff"); diff_pages(sys.argv[i + 1], sys.argv[i + 2], sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None); sys.exit(0)
    if "--row" in sys.argv: row(sys.argv[sys.argv.index("--row") + 1]); sys.exit(0)
    if "--sweep" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        sweep(sys.argv[sys.argv.index("--sweep") + 1], out)
        if "--chunks" in sys.argv:
            if not out: sys.exit("--chunks needs --out")
            sweep_chunks(sys.argv[sys.argv.index("--sweep") + 1], out, int(sys.argv[sys.argv.index("--chunks") + 1]))
        sys.exit(0)
    if "--interests" in sys.argv:
        names = sys.argv[sys.argv.index("--names") + 1].split("|") if "--names" in sys.argv else None
        pg = sys.argv[sys.argv.index("--interests") + 1]; interests(None if pg == "-" else pg, sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None, names); sys.exit(0)
    if "--audit" in sys.argv: audit(sys.argv[sys.argv.index("--audit") + 1], sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None); sys.exit(0)
    if "--check" in sys.argv: sys.exit(0 if check(sys.argv[sys.argv.index("--check") + 1]) else 1)
    pages = [a for a in sys.argv[1:] if a.endswith(".md")]
    if "--all" in sys.argv: pages = [p for p in sorted(glob.glob("research/narrative-*.md")) if "synchrony" not in p and "narrative-rival-" not in p and not p.endswith("narrative-register.md")]
    res = [parse(p) for p in pages]
    if "--json" in sys.argv: LN.write_text(sys.argv[sys.argv.index("--json") + 1], json.dumps(res, indent=1, ensure_ascii=False))
    for r in res:
        print(f"{r['page']}: mode={r['mode']} nodes={r['nodes']} roles={r['roles']} citations={r['row_citations']} ledger={r['contradictions']} flares={r['flares']} forks={r['fork_candidates']} load(sum of page weights)={r['load_computed']} load/cluster={r['load_per_cluster']} max downstream(computed)={r['max_downstream_computed']} tests={r['tests_counted']} words={r['words']}")
        for s in r["score_lines"]: print("   score line:", s)
        if r["reading_edges"] or r["reading_edges_unresolved"]: print(f"   reading edges (out of the closure): {r['reading_edges']}" + (f"; unresolved (reading: ...) cells: {r['reading_edges_unresolved']}" if r["reading_edges_unresolved"] else ""))
        for l in r["ledger"]:
            if l["downstream_page"] != l["downstream_computed"]: print(f"   ledger {l['n']} node {l['nodes']}: downstream page {l['downstream_page']} vs computed {l['downstream_computed']}")
    if "--recurring" in sys.argv:
        # change 24: match on cited rows and leads, not wording; cross-mainline recurrences apart from rows a fork inherits from its parent
        def family(r): return re.sub(r"-fork-\d+$", "", r["page"])
        keyed = []
        for r in res:
            for l in r["ledger"]:
                keys = set(("row",) + x for x in l["rows"]) | set(("lead", x) for x in l["leads"])
                if keys: keyed.append((r, l, keys))
        print("\nRecurring contradictions (sharing a cited row or lead):")
        seen = set()
        for i, (r1, l1, k1) in enumerate(keyed):
            group = [(r1, l1)]
            for r2, l2, k2 in keyed[i + 1:]:
                if k1 & k2: group.append((r2, l2))
            if len(group) < 2: continue
            sig = tuple(sorted((g[0]["page"], g[1]["n"]) for g in group))
            if sig in seen: continue
            seen.add(sig)
            fams = {family(g[0]) for g in group}
            kind = "cross-mainline" if len(fams) > 1 else "inherited within one family"
            print(f"  {len(group)}x [{kind}] {l1['contradiction'][:90]} :: " + "; ".join(f"{g[0]['page']} row {g[1]['n']}: {g[1]['side'][:40]}" for g in group))
    if "--tree" in sys.argv:
        print("\nFamily tree:")
        for r in res:
            if r["mode"] == "mainline":
                print(f"  {r['page']} (load {r['load_computed']}, nodes {r['nodes']})")
                for f in res:
                    if f["mode"] == "fork" and r["page"] in f["parent"]: print(f"    fork {f['page']} (load {f['load_computed']}, nodes {f['nodes']})")
