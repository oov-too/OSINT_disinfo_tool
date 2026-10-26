#!/usr/bin/env python3
"""The unused-rows check (tools/narratives.md section 8e, owner 2026-10-25): held rows bearing on a narrative page's nodes that the page
never cites.
Usage:
  python3 tools/narrative_unused.py <page> [--out <file.md>] [--node N] [--cap K] [--near Y] [--reach-back Y] [--chance C]
                                    [--chance-out C] [--json <file.json>]
  ledger narrate unused <page> [...]                                    (the same command through the launcher)

For every node of the page's `## Nodes` table the tool gathers:
  names   the names the node's Carriers cell gives (cleaned as tools/narratives.py cleans carriers), the speakers of the node's cited rows,
          the page's Carriers table entries the node's text or Carriers cell names, and the capitalised names in the node text; a name
          is matched by its whole phrase, or by its last word when that word is capitalised and four letters or more; a name found in
          more than a fifth of the held rows is too common to select a row alone (it still counts beside another match, and is listed);
  terms   the node text's distinctive words, lightly stemmed (a plural or past tense meets its root): held in at least two rows and in
          at most 8% of them (or 5 rows, whichever is more), and in at least one row the page does not cite; the words the node shares
          with its own cited rows all, and the twelve rarest of the others; document numbers and codes (letters with digits) are kept;
  topics  the topics of the node's cited claims rows (a supporting signal only: a topic never selects a row alone);
  window  the Date cell's years (the years outside parentheses; inside them only when there are none outside), widened by a year each
          side for an `about` date, then by --near years (default 1) each side.
It searches notes.db's claims, timeline and audit rows (every note) for rows that match a name or a term and fall in the window, plus
the rows dated up to --reach-back years (default 10) before it and the undated rows. Each match carries its rarity, log(rows held /
rows matching), and a row enters when its matches together would turn up by chance in at most --chance (default 2) of the held
rows, or --chance-out (default 0.4) for an earlier or undated row, so the bar rises with the corpus; a too-common name adds nothing,
a topic never selects a row alone, and one match alone selects only when it is held in three rows or fewer. A row's dates are its timeline date, or for a claims or audit row the years its own text names. A row
is cited when any `[note table n]` citation anywhere on the page names it (every section, comma lists expanded), or a short `table n`
reference (`claims 25, 27`, `claims 499 to 501`) does, bound to the note last cited before it; cited rows are never listed.
Hits are ranked by how far they would move the node: an event dated earlier than the node's start first, then a row whose basis is a
held document (tools/narratives.py's classifier: a read row whose work is held, a document note's own row), then a row from the other
side (a speaker the node's Carriers cell does not name), then the rest; inside a class by the strength of the match, then by date.
Each node prints a head line (what was searched, the terms, the window, what the cap cut) and a table
  | Row | Date | Speaker | Class | What it says | Why it bears |
of at most --cap rows (default 12); the rows the cap cut are indexed under the table by note and table (no silent caps). Output to --out (an
agent's wip folder) or stdout; --json writes the same per node for a script. Exit 0; exit 2 with a message when the page has no Nodes
table. Reads the page and notes.db only; never writes the page.
"""
import datetime, json, math, os, re, sqlite3, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narratives as N
from ledger import notes as LN

STOPWORDS = set("""a about above after again against all almost along already also although always am among an and another any anyone
anything are around as at away back be became because become been before being below between both but by came can cannot could did do
does doing done down during each either else enough even ever every few for from further get gets given gives go going got had has have
having he her here hers herself him himself his how however i if in into is it its itself just know known last later least less like
made make many may me might more most much must my myself near need neither never next no nor not nothing now of off often on once one
only onto or other others otherwise our ours out over own per perhaps put quite rather really said same say says see seen several shall
she should since so some something still such take than that the their theirs them themselves then there these they this those though
through thus to too toward towards under until up upon us very via was way we well were what when where whether which while who whom
whose why will with within without would yet you your yours first second third two three four five six seven eight nine ten year years
time times day days month months week weeks part whole node nodes row rows note notes page told tells tell telling says saying asked asks
ask question questions answer answers mr mrs ms dr sir""".split())
CALENDAR = set("""january february march april may june july august september october november december jan feb mar apr jun jul aug sep sept
oct nov dec monday tuesday wednesday thursday friday saturday sunday""".split())
HONORIFICS = {"Mr", "Mrs", "Ms", "Dr", "Sir", "Dame", "Lord", "Lady", "MP", "KC", "QC", "Jr", "Sr"}
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]+|[A-Za-z]*\d+[A-Za-z]+\d*|[A-Za-z]+\d+")
CODE_RE = re.compile(r"^(?=.*\d)(?=.*[a-z])[a-z0-9]+$")
CAP_NAME_RE = re.compile(r"(?<![\w'’])((?:[A-Z][A-Za-z'’.-]+|&)(?:\s+(?:[A-Z][A-Za-z'’.-]+|&|de|van|von|der))*)")
YEAR_RE = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
DATE_RE = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?:-(\d\d))?(?:-(\d\d))?(?!\d)")
COMMON_SHARE = 0.2; TERM_SHARE = 0.08; TERM_MIN_CAP = 5; TERMS_PER_NODE = 12; CUT_WORDS = 40
CHANCE_IN = 2.0; CHANCE_OUT = 0.4; SINGLE_DF = 3   # a row enters when its matches together would turn up by chance in at most CHANCE_IN held rows (in the window) or CHANCE_OUT (earlier or undated)
CLASSES = ["earlier date", "document", "other side", "term"]

def words(text): return [w.lower().strip("'’-").replace("’", "'") for w in WORD_RE.findall(text or "")]
def norm_word(w):
    """A light stem, so a plural or a past tense meets its root: transactions -> transaction, altered -> alter, shortages -> shortage."""
    w = re.sub(r"'s?$", "", w)
    if CODE_RE.match(w) or len(w) < 5: return w
    if w.endswith("ies") and len(w) > 5: return w[:-3] + "y"
    if w.endswith("sses"): return w[:-2]
    if w.endswith("ing") and len(w) > 6: return w[:-3]
    if w.endswith("ed") and len(w) > 5 and not w.endswith("eed"): return w[:-2] if not w.endswith("ied") else w[:-3] + "y"
    if w.endswith("s") and not w.endswith(("ss", "us", "is")): return w[:-1]
    return w
def cut(text, n=CUT_WORDS):
    ws = (text or "").replace("|", "/").replace("\n", " ").split()
    return " ".join(ws[:n]) + (" ..." if len(ws) > n else "")

# ---------------------------------------------------------------- citations on the page
FULL_OR_SHORT = re.compile(r"\[(?P<note>[a-z0-9-]{4,}) (?P<k1>tl|claims|audit|xc) (?P<n1>[\d.]+(?:\s*,\s*[\d.]+)*)\]"
                           r"|\b(?P<k2>tl|claims|audit|xc) (?P<n2>\d+(?:\.\d+)?(?:\s*(?:,|and|to|-|–)\s*\d+(?:\.\d+)?)*)\b")
def _expand(ns):
    out = []
    for part in re.split(r"\s*(?:,|\band\b)\s*", ns):
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*", part)
        if m and float(m.group(1)).is_integer() and float(m.group(2)).is_integer() and 0 <= int(float(m.group(2))) - int(float(m.group(1))) <= 60:
            out += [str(x) for x in range(int(float(m.group(1))), int(float(m.group(2))) + 1)]
        else: out += re.findall(r"\d+(?:\.\d+)?", part)
    return out
def page_citations(txt):
    """(cited set of (note, kind, n), counts): full citations anywhere on the page, and short references bound to the note last cited."""
    cited, full, short, unbound, last = set(), 0, 0, 0, None
    for m in FULL_OR_SHORT.finditer(txt):
        if m.group("note"):
            last = m.group("note"); full += 1
            for n in _expand(m.group("n1")): cited.add((last, m.group("k1"), n))
        elif last:
            short += 1
            for n in _expand(m.group("n2")): cited.add((last, m.group("k2"), n))
        else: unbound += 1
    return cited, dict(full=full, short=short, unbound=unbound)

# ---------------------------------------------------------------- dates
def date_window(cell, near):
    """(start tuple, start year, end year, about, window from, window to) of a Date cell."""
    c = cell or ""; outside = re.sub(r"\([^)]*\)", " ", c)
    ds = [tuple(int(x) if x else 0 for x in m.groups()) for m in DATE_RE.finditer(outside)] or [tuple(int(x) if x else 0 for x in m.groups()) for m in DATE_RE.finditer(c)]
    if not ds: return None
    about = bool(re.search(r"\b(about|circa|c\.|around|by)\b", c, re.I))
    y0, y1 = min(d[0] for d in ds), max(d[0] for d in ds)
    start = min(ds)
    if about: y0 -= 1; y1 += 1; start = (y0, 0, 0)
    return dict(start=start, y0=y0, y1=y1, about=about, w0=y0 - near, w1=y1 + near)
def row_dates(kind, r, text):
    """[(y, m, d)] the row's dates: a timeline row's sortable date (both ends of a range), else the years its own text names."""
    if kind == "tl":
        ds = [tuple(int(x) if x else 0 for x in m.groups()) for m in DATE_RE.finditer((r["sortable"] or "") + " " + (r["date_stated"] or ""))]
        if ds: return ds
    return [(int(y), 0, 0) for y in YEAR_RE.findall(text)]
def earlier(d, start):
    """d before start at the precision both share."""
    k = 3
    while k > 1 and (d[k - 1] == 0 or start[k - 1] == 0): k -= 1
    return d[:k] < start[:k]
def fmt_date(d): return "-".join([str(d[0])] + [f"{x:02d}" for x in d[1:] if x]) if d else ""

# ---------------------------------------------------------------- the corpus
class Corpus:
    def __init__(self, con):
        self.con = con; self.rows = []
        guest = {r["id"]: (r["guest"] or "") for r in con.execute("select id, guest from videos")}
        for r in con.execute("select * from claims"):
            text = r["claim"] or ""; side = " ".join(filter(None, [r["chain"], r["attribution"]]))
            self.rows.append(dict(ref=(r["video"], "claims", r["n"]), kind="claims", r=r, text=text, side=side, speaker=r["speaker"] or "",
                                  topic=(r["topic"] or "").strip(), cls=r["source_class"] or "", dates=row_dates("claims", r, text)))
        for r in con.execute("select * from timeline"):
            text = r["event"] or ""; side = " ".join(filter(None, [r["speaker_basis"], r["chain"]]))
            sp = re.split(r"[;,(]", r["speaker_basis"] or "")[0].strip()
            self.rows.append(dict(ref=(r["video"], "tl", r["n"]), kind="tl", r=r, text=text, side=side, speaker=sp, topic="",
                                  cls="timeline" + (f" ({r['agreement_kind']})" if r["agreement_kind"] else ""), dates=row_dates("tl", r, text), date_stated=r["date_stated"] or ""))
        for r in con.execute("select * from audit_rows"):
            text = " ".join(filter(None, [r["question"], r["answer"]]))
            g = re.sub(r"\(.*?\)", "", guest.get(r["video"], "")).strip()
            g = "" if g.lower().startswith("none") else g
            self.rows.append(dict(ref=(r["video"], "audit", r["n"]), kind="audit", r=r, text=text, side=r["basis"] or "", speaker=g, topic="",
                                  cls="audit" + (f" ({r['move']})" if r["move"] else ""), dates=row_dates("audit", r, text)))
        self.by_ref = {x["ref"]: x for x in self.rows}
        self.df = Counter()
        self.index = {}   # word -> row positions (text, chain and speaker words): the rows a node can match at all
        for i, x in enumerate(self.rows):
            x["words"] = set(norm_word(w) for w in words(x["text"]))
            x["allwords"] = x["words"] | set(norm_word(w) for w in words(x["side"] + " " + x["speaker"]))
            self.df.update(x["words"])
            for w in x["allwords"]: self.index.setdefault(w, []).append(i)
        self._re, self._share, self._basis = {}, {}, {}
        self.n = len(self.rows)
        self.counts = Counter(x["kind"] for x in self.rows)
        self.topic_df = Counter(x["topic"] for x in self.rows if x["topic"])
        # the examiners (a note's host, the askers of a hosted note's audit rows): counsel and chairs put the questions; they are no side of a node
        ex = set()
        for r in con.execute("select host from videos"): ex.add(re.sub(r"\(.*?\)", "", r["host"] or "").strip())
        for r in con.execute("select distinct a.asked_by, v.guest from audit_rows a join videos v on v.id = a.video where lower(coalesce(v.host, 'none')) not like 'none%'"):
            a = re.sub(r"\(.*?\)", "", r["asked_by"] or "").strip(); g = re.sub(r"\(.*?\)", "", r["guest"] or "").strip()
            if a and a != g: ex.add(a)   # a witness who volunteers is no examiner   # the askers in a hosted note (a hearing, an interview); a document's own questioners are parties
        self.examiners = {e for e in ex if e and e[0].isupper() and e.split()[0].lower() not in ("none", "the")}
    def idf(self, df): return math.log(self.n / max(1, df))
    def name_hit(self, key, x):
        """The name's whole phrase (any case), or its last word as written (capitalised), in the row's text, chain or speaker."""
        phrase, last = key
        if key not in self._re:
            pw = set(norm_word(w) for w in words(phrase))
            self._re[key] = (pw, re.compile(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", re.I) if phrase else None,
                             norm_word(last.lower()) if last else "", re.compile(r"(?<![\w])" + re.escape(last) + r"(?![\w])") if last else None)
        pw, pre, lw, lre = self._re[key]
        aw = x.get("allwords")
        hay = None
        if pre and (aw is None or pw <= aw):
            hay = x["text"] + " " + x["side"] + " " + x["speaker"]
            if pre.search(hay): return True
        if lre and (aw is None or lw in aw):
            hay = hay or x["text"] + " " + x["side"] + " " + x["speaker"]
            if lre.search(hay): return True
        return False
    def candidates(self, ws):
        """Row positions holding any of the words ws."""
        out = set()
        for w in ws: out.update(self.index.get(w, ()))
        return out
    def key_words(self, key):
        phrase, last = key
        pw = [norm_word(w) for w in words(phrase)]
        return ({min(pw, key=lambda w: len(self.index.get(w, ())))} if pw else set()) | ({norm_word(last.lower())} if last else set())
    def name_df(self, key):
        if key not in self._share: self._share[key] = sum(1 for i in self.candidates(self.key_words(key)) if self.name_hit(key, self.rows[i]))
        return self._share[key]
    def basis(self, nk, x):
        if x["ref"] not in self._basis:
            self._basis[x["ref"]] = N._claim_basis(nk, x["ref"][0], x["r"]) if x["kind"] == "claims" else N.row_basis(self.con, nk, *x["ref"])
        return self._basis[x["ref"]]
    def share(self, key): return self.name_df(key) / max(1, self.n)

# ---------------------------------------------------------------- names, terms and topics of a node
def _name_key(name):
    """(phrase, last word or '') of a name: the whole phrase, and its last word when capitalised, four letters or more, not an honorific."""
    name = re.sub(r"[’']s?$", "", name.strip(" .,:;"))
    toks = [t for t in name.split() if t not in HONORIFICS]
    if not toks: return None
    phrase = " ".join(toks)
    last = toks[-1] if len(toks) > 1 and re.match(r"^[A-Z][a-z'’-]{3,}$", toks[-1]) and toks[-1].lower() not in STOPWORDS else ""
    if len(toks) == 1 and (len(phrase) < 3 or phrase.lower() in STOPWORDS): return None
    return (phrase, last)
def _cell_names(cell):
    out = []
    for part in re.split(r";|,|\band\b|<-|->|/|\bvia\b|\bthrough\b", cell or ""):
        part = N._clean_name(part)
        if part and N.NAME_RE.match(part) and part not in N.STOP and not re.search(r"\d", part): out.append(part)
    return out
def _text_names(text):
    """Capitalised runs of the node text, split at a possessive (`Fujitsu's Bracknell` gives Fujitsu and Bracknell); a lone capitalised
    word that opens a sentence, a stop word or a calendar word is no name."""
    out = []
    for m in CAP_NAME_RE.finditer(text or ""):
        pre = (text[:m.start()].rstrip()[-1:] if text[:m.start()].strip() else ".")
        groups, cur = [], []
        for t in m.group(1).strip(" &.").split():
            if re.search(r"['’]s?$", t): cur.append(re.sub(r"['’]s?$", "", t)); groups.append(cur); cur = []
            else: cur.append(t)
        if cur: groups.append(cur)
        for gi, toks in enumerate(groups):
            toks = [t for t in toks if t.lower() not in CALENDAR]
            while toks and toks[0].lower() in STOPWORDS: toks = toks[1:]
            if not toks: continue
            if len(toks) == 1 and ((gi == 0 and pre in ".:;!?\"“(") or toks[0].lower() in STOPWORDS or len(toks[0]) < 3 or re.search(r"[-'’]", toks[0])): continue
            out.append(" ".join(toks))
    return out
def node_profile(nd, carriers_table, corpus, cited_refs, near):
    text = nd.get("node", ""); ccell = nd.get("carriers (independent roots)", nd.get("carriers", ""))
    refs = [(a, b, c) for a, b, c in LN.citations(nd.get("rows", ""))]
    speakers = []
    for ref in refs:
        x = corpus.by_ref.get(ref)
        if x and x["speaker"]: speakers.append(re.sub(r"\(.*?\)", "", x["speaker"]).strip())
    carrier_names = _cell_names(ccell)
    tab = []
    for c in carriers_table:
        for nm in _cell_names(c.get("carrier", "")):
            k = _name_key(nm)
            if k and (k[0] in text or k[0] in ccell or (k[1] and (k[1] in text or k[1] in ccell))): tab.append(nm)
    names, seen = [], set()
    for nm in carrier_names + speakers + tab + _text_names(text):
        k = _name_key(nm)
        if k and k[0].lower() not in seen: seen.add(k[0].lower()); names.append((nm, k))
    sel, common, examiners = [], [], []
    for nm, k in names:
        if any(k[0] == e or (k[1] and k[1] in e.split()) or k[0] in e.split() for e in corpus.examiners): examiners.append(nm); continue   # counsel and chairs speak in every exchange
        (common if corpus.share(k) > COMMON_SHARE else sel).append((nm, k))
    name_words = set(w for nm, k in names for w in words(nm))
    tf = Counter(norm_word(w) for w in words(text))
    row_words = set()
    for r in refs:
        if r in corpus.by_ref: row_words |= corpus.by_ref[r]["words"]
    cited_df = Counter()
    for r in cited_refs:
        if r in corpus.by_ref: cited_df.update(corpus.by_ref[r]["words"])
    cap = max(TERM_MIN_CAP, TERM_SHARE * corpus.n); cand = []
    for w, f in tf.items():
        if w in STOPWORDS or w in CALENDAR or w in name_words or len(w) < 4 and not CODE_RE.match(w): continue
        df = corpus.df.get(w, 0)
        if df - cited_df.get(w, 0) < 1: continue   # held only in rows the page cites: it can select nothing
        if CODE_RE.match(w): cand.append((w, 0, 99.0, df)); continue
        if df < 2 or df > cap: continue
        cand.append((w, 0 if w in row_words else 1, f * math.log(corpus.n / df), df))   # the words the node shares with its own rows first
    cand.sort(key=lambda t: (t[1], -t[2], t[3], t[0]))
    terms = [t[0] for t in cand if t[1] == 0] + [t[0] for t in cand if t[1] == 1][:TERMS_PER_NODE]   # every shared word, and the rarest others
    topics = Counter(corpus.by_ref[r]["topic"] for r in refs if r in corpus.by_ref and corpus.by_ref[r]["topic"])
    carrier_keys = [_name_key(nm) for nm in carrier_names]
    return dict(names=sel, common=common, examiners=examiners, terms=terms, topics=set(topics), carrier_keys=[k for k in carrier_keys if k],
                carrier_names=carrier_names, refs=refs, window=date_window(nd.get("date", ""), near))

# ---------------------------------------------------------------- matching and ranking
def match_node(prof, corpus, cited, reach_back, nk, node_basis, chance_in=CHANCE_IN, chance_out=CHANCE_OUT):
    """The uncited rows bearing on one node, ranked. A row's match weight is the sum of the rarities (log of rows held over rows
    matching) of the names, terms and topic it shares with the node; a too-common name adds nothing and a topic never selects alone.
    It enters when its matches would turn up by chance (independence assumed) in at most chance_in of the held rows, weight
    log(rows held / chance_in) or more, when one of its dates falls in the window; at most chance_out (weight log(rows / chance_out))
    when it is dated up to reach_back years before the window or is undated. The bar so rises with the corpus."""
    w = prof["window"]; hits = []
    t_in, t_out = math.log(corpus.n / chance_in), math.log(corpus.n / chance_out)
    nidf = {k: corpus.idf(corpus.name_df(k)) for nm, k in prof["names"]}
    ws = set(prof["terms"])
    for nm, k in prof["names"]: ws |= corpus.key_words(k)
    for i in sorted(corpus.candidates(ws)):
        x = corpus.rows[i]
        if x["ref"] in cited: continue
        nh = [(nm, k) for nm, k in prof["names"] if corpus.name_hit(k, x)]
        th = [t for t in prof["terms"] if t in x["words"]]
        if not nh and not th: continue
        top = bool(x["topic"]) and x["topic"] in prof["topics"]
        score = sum(nidf[k] for nm, k in nh) + sum(corpus.idf(corpus.df.get(t, 1)) for t in th) + (corpus.idf(corpus.topic_df[x["topic"]]) if top else 0)
        ds = x["dates"]
        if w is None: place, need = "undated node", t_out
        elif not ds: place, need = "undated", t_out
        elif any(w["w0"] <= d[0] <= w["w1"] for d in ds): place, need = "in window", t_in
        elif any(w["w0"] - reach_back <= d[0] < w["w0"] for d in ds): place, need = "before the window", t_out
        else: continue
        feats = len(nh) + len(th) + (1 if top else 0)
        if score < need: continue
        if feats < 2 and not (place == "in window" and len(nh) + len(th) == 1 and score >= corpus.idf(SINGLE_DF)): continue   # one match alone selects only when it is held in SINGLE_DF rows or fewer
        why, cls = [], None
        e = [d for d in ds if w and earlier(d, w["start"])]
        if e: cls = "earlier date"; why.append(f"earlier date ({fmt_date(min(e))} before the node's {fmt_date(w['start'])})")
        b, bwhy = corpus.basis(nk, x)
        if b == "document":
            cls = cls or "document"
            why.append("document (" + bwhy + (f"; the node's rows carry {node_basis}" if node_basis and node_basis != "document" else "") + ")")
        sp = x["speaker"]
        examiner = any(e_ and (e_ in sp or sp in e_) for e_ in corpus.examiners) if sp else True
        if sp and not examiner and prof["carrier_keys"] and not any(corpus.name_hit(k, dict(text="", side="", speaker=sp)) or (k[1] and k[1] in sp) for k in prof["carrier_keys"]):
            cls = cls or "other side"; why.append(f"other side ({sp} is not among the node's carriers)")
        cls = cls or "term"
        if nh: why.append("names: " + ", ".join(nm for nm, k in nh))
        if th: why.append("terms: " + ", ".join(th))
        if top: why.append(f"topic {x['topic']}")
        if place in ("undated", "before the window"): why.append(place)
        why.append(f"weight {score:.1f}")
        hits.append(dict(x=x, cls=cls, why="; ".join(why), score=score, basis=b, first=min(ds) if ds else (9999, 0, 0)))
    hits.sort(key=lambda h: (CLASSES.index(h["cls"]), -h["score"], h["first"], h["x"]["ref"]))
    return hits

def compact_refs(refs):
    """`note: claims 3, 9; tl 4 | note2: ...` in first-seen note order, the rows of each table in rank order."""
    by = {}
    for note, kind, n in refs: by.setdefault(note, {}).setdefault(kind, []).append(n)
    return " | ".join(f"{note}: " + "; ".join(f"{k} {', '.join(ns)}" for k, ns in kinds.items()) for note, kinds in by.items())
def ref_str(ref): return f"[{ref[0]} {ref[1]} {ref[2]}]"
def row_date_cell(x):
    if x["kind"] == "tl": return (x.get("date_stated") or (fmt_date(x["dates"][0]) if x["dates"] else "undated")).replace("|", "/")
    ys = sorted({d[0] for d in x["dates"]})
    return ", ".join(map(str, ys)) if ys else "undated"

def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    def opt(k, d=None, f=str): return f(argv[argv.index(k) + 1]) if k in argv else d
    page = os.path.abspath(argv[0]); out = opt("--out"); out = os.path.abspath(out) if out else None
    js = opt("--json"); js = os.path.abspath(js) if js else None
    only = opt("--node", None, int); cap = opt("--cap", 12, int); near = opt("--near", 1, int); reach = opt("--reach-back", 10, int)
    c_in = opt("--chance", CHANCE_IN, float); c_out = opt("--chance-out", CHANCE_OUT, float)
    # no chdir: a tool run in-process (the tests call main()) must not move the interpreter into a project folder that may be
    # deleted later (the deleted-cwd defect of 2026-10-26: a later subprocess died at os.getcwd()); every path below is absolute
    if not os.path.exists(page): print(f"no such page: {argv[0]}", file=sys.stderr); return 2
    txt = LN.read_text(page)
    nodes = [r for r in N.table(N.section(txt, "Nodes")) if re.match(r"\d+", r.get("#", "") or "")]
    if not nodes:
        print(f"{argv[0]}: no Nodes table (a `## Nodes` section with a `| # | Date | ... |` table); the unused-rows check reads nodes only", file=sys.stderr); return 2
    con = sqlite3.connect(f"file:{os.path.join(N.ROOT, 'notes.db')}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    corpus = Corpus(con); nk = N.NoteKinds(con)
    cited, cc = page_citations(txt)
    carriers_table = N.table(N.section(txt, "Carriers"))
    rel = os.path.relpath(page, N.ROOT)
    head = [f"# Unused rows for {os.path.basename(page)} (tools/narrative_unused.py, {datetime.date.today().isoformat()})", "",
            f"Searched: notes.db, every note: claims {corpus.counts['claims']}, timeline {corpus.counts['tl']}, audit {corpus.counts['audit']} rows. "
            f"Cited on the page (never listed): {len(cited)} rows, from {cc['full']} full citations in every section and {cc['short']} short references bound to the note last cited before them"
            + (f" ({cc['unbound']} short references with no note before them, ignored)" if cc["unbound"] else "") + ". "
            f"Per node: names (the Carriers cell, the speakers of the node's rows, the Carriers table entries the node names, the capitalised names in the node text; a name held in more than {int(COMMON_SHARE * 100)}% of rows is too common to select a row alone, and an examiner's name (a note's host, an audit row's asker: {', '.join(sorted(corpus.examiners)) or 'none'}) never selects), "
            f"terms (the node text's words, lightly stemmed, held in 2 to {int(TERM_SHARE * 100)}% of rows (at least {TERM_MIN_CAP}) and in at least one row the page does not cite; every word the node shares with its own cited rows and the {TERMS_PER_NODE} rarest others; codes kept), topics (of the node's cited claims rows; supporting only); "
            f"window: the Date cell's years, a year each side for `about`, then {near} year(s) each side; a row enters when the names, terms and topic it shares with the node would together turn up by chance in at most {c_in:g} of the {corpus.n} held rows (weight, the sum of log(rows held / rows matching) over its matches, at least {math.log(corpus.n / c_in):.1f}; a too-common name adds nothing, a topic never selects alone, one match alone only when held in {SINGLE_DF} rows or fewer), and a row dated up to {reach} years before the window or undated only at {c_out:g} (weight {math.log(corpus.n / c_out):.1f}). "
            f"Ranked: earlier date, document, other side, the rest (term); inside a class by that weight, then date. Cap {cap} rows per node: the author reads every row shown; the rows a cap cut are indexed under each table by note (raise --cap or run --node N to see them).", ""]
    body, report, distinct, total, cut_total = [], [], set(), 0, 0
    nbasis = {}
    for nd in nodes:
        n = int(re.match(r"\d+", nd["#"]).group(0))
        if only is not None and n != only: continue
        prof = node_profile(nd, carriers_table, corpus, cited, near)
        nb, _ = N.node_basis(con, nk, nd.get("rows", "")); nbasis[n] = nb
        hits = match_node(prof, corpus, cited, reach, nk, nb, c_in, c_out)
        shown, cutl = hits[:cap], hits[cap:]
        total += len(hits); cut_total += len(cutl); distinct |= {h["x"]["ref"] for h in hits}
        w = prof["window"]; byc = Counter(h["cls"] for h in hits)
        body.append(f"## Node {n} ({nd.get('date', '')}; {nd.get('role', '')}; rows carry {nb or 'no classed row'}): {cut(nd.get('node', ''), 18)}")
        body.append("")
        body.append("Searched: window " + (f"{w['w0']} to {w['w1']} (Date cell {w['y0']}{'' if w['y0'] == w['y1'] else ' to ' + str(w['y1'])}{', about: widened' if w['about'] else ''}); earlier rows from {w['w0'] - reach}" if w else f"none (the Date cell names no year: the earlier-or-undated bar only)")
                    + "; names: " + (", ".join(nm for nm, k in prof["names"]) or "none")
                    + ("; too common to select alone: " + ", ".join(nm for nm, k in prof["common"]) if prof["common"] else "")
                    + ("; examiners, never selecting: " + ", ".join(prof["examiners"]) if prof["examiners"] else "")
                    + "; terms: " + (", ".join(prof["terms"]) or "none") + "; topics: " + (", ".join(sorted(prof["topics"])) or "none") + ".")
        body.append(f"Matched {len(hits)} uncited rows (" + ", ".join(f"{c} {byc[c]}" for c in CLASSES if byc[c]) + (")" if hits else "none)") + f"; shown {len(shown)} (cap {cap})" + (f"; cut {len(cutl)}, listed below the table." if cutl else "; nothing cut."))
        body.append("")
        if shown:
            body += ["| Row | Date | Speaker | Class | What it says | Why it bears |", "|---|---|---|---|---|---|"]
            for h in shown:
                x = h["x"]
                body.append(f"| {ref_str(x['ref'])} | {row_date_cell(x)} | {(x['speaker'] or '').replace('|', '/')} | {x['cls']}{'; ' + h['basis'] if h['basis'] else ''} | {cut(x['text'])} | {h['cls']}: {h['why'].replace('|', '/')} |")
            body.append("")
        if cutl:
            body.append(f"Cut by the cap ({len(cutl)}; " + ", ".join(f"{c} {n_}" for c, n_ in Counter(h['cls'] for h in cutl).items()) + "), by note: " + compact_refs([h["x"]["ref"] for h in cutl]))
            body.append("")
        report.append(dict(node=n, date=nd.get("date", ""), basis_rows=nb, window=w, names=[nm for nm, k in prof["names"]], common=[nm for nm, k in prof["common"]],
                           terms=prof["terms"], topics=sorted(prof["topics"]), matched=len(hits), shown=len(shown), cut=len(cutl),
                           rows=[dict(row=ref_str(h["x"]["ref"]), cls=h["cls"], why=h["why"], shown=i < cap) for i, h in enumerate(hits)]))
    head.append(f"Summary: {len(report)} nodes; {total} node-row matches, {len(distinct)} distinct rows; {total - cut_total} shown, {cut_total} cut by the cap (indexed). "
                "Every shown row is read by the author and cited or dismissed under `### Rows read and left out` with a reason (section 8e).")
    head.append("")
    text = "\n".join(head + body).rstrip() + "\n"
    if out: LN.write_text(out, text); print(f"unused rows written to {out} ({len(report)} nodes, {len(distinct)} distinct rows, {cut_total} cut by the cap and listed)")
    else: print(text)
    if js: LN.write_text(js, json.dumps(dict(page=rel, nodes=report), indent=1, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
