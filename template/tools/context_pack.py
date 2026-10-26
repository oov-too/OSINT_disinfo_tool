#!/usr/bin/env python3
"""Context pack for an intake: everything the database already holds that a new source bears on, in one file, so the intake agent
reads <wip>/context.md instead of grepping and reading whole notes (tools/context_pack.md).

Usage:
  python3 tools/context_pack.py <source .txt/.md files...> --wip wip/<task> [--names-only] [--max-rows-per-term 40]
                                [--sets-json <sets.json> --set <key>] [--min-count 1] [--broad 500] [--db notes.db]

Steps (each a section of context.md):
  1 extraction from the source: proper names (people, organisations, programmes, documents, places), dates (YYYY-MM-DD, month-year,
    year), document identifiers (FOIA, contract, exhibit and report numbers, quoted report titles) and URLs; --names-only prints these and stops
  2 held rows: for each name, date, identifier and URL, tools/rows_search.py (claims, timeline, audit) run through its search() function;
    rows grouped by term, deduplicated across terms, each trimmed to citation | date | speaker | text
  3 first-utterance register clusters whose Event or Claim text matches a name, or whose date range covers a source date
  4 narrative pages' contradiction-ledger rows (and nodes) that mention a name, with page and row number
  5 leads register rows that mention a name, with lead number and status
  6 the held notes that mention the names most densely (top 15 by count) with their source kind (research/source-kinds.md)
  7 a header with counts and the commands used (full command list in the last section)
Caps: --max-rows-per-term N (default 40). A term with more matching rows than the cap shows the first N and an "and N more" line, and
every row beyond the cap is written to <wip>/context-overflow.md under the same term heading: nothing is dropped silently. Reduced caps
(stated in each heading): a single-word term that is not a person, a broad term the source names once, and a bare year get a quarter of N;
a month-year half of N. A term with more than --broad rows (default 200) shows its top rows and then per-note counts instead of an
overflow (narrow it with rows_search.py --note). Month-years and years list only timeline rows that also name one of the source's
specific names; the count of the rest is stated.
Reads notes.db (read-only), research/first-utterance-register.md, research/narrative-*.md, research/leads-and-inferences.md,
research/source-kinds.md, tools/name_aliases.json and the held notes' markdown. Writes only <wip>/context.md and <wip>/context-overflow.md."""
import argparse, collections, datetime, glob, json, os, re, sqlite3, sys

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # project paths and the sources/ alias table
import rows_search as rs  # the FTS5 search (tools/rows_search.md); this tool builds on it rather than duplicating it

KINDS = ["claims", "tl", "audit"]
TRIM, TRIM_OVER = 200, 200
REG_CAP = 12   # a name matching more register rows than this is broad for that register; its rows go in index form
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
CONNECTORS = {"of", "the", "for", "and", "de", "du", "da", "von", "van", "der", "den", "y", "&", "la", "le", "del", "di", "las", "los", "dos", "das"}
TITLES = {"dr", "mr", "mrs", "ms", "miss", "prof", "professor", "senator", "sen", "rep", "representative", "hon", "honorable", "honourable",
          "lt", "col", "gen", "capt", "maj", "sgt", "cmdr", "adm", "cdr", "brig", "general", "colonel", "lieutenant", "captain", "major",
          "sergeant", "commander", "admiral", "president", "secretary", "director", "judge", "sir", "lord", "lady", "father", "rev", "reverend"}
STOP = set("""a an the and or but nor if then than so as at by for from in into of off on onto to up with within without about above across
after against along among around before behind below beneath beside between beyond during except inside near outside over past since
through throughout toward towards under until upon via per re this that these those it its he his she her they them their we us our you
your i me my mine him himself herself itself themselves ourselves someone anyone everyone nobody something anything everything nothing
here there where when what who whom whose why how which whether while although though because therefore thus hence however also yes no
not one two three four five six seven eight nine ten first second third last next previous other another some many most all any
each every both either neither such same different various several few little much more less least very quite rather too enough just only dear sincerely
even still already yet again once twice often sometimes usually always never ever perhaps maybe probably possibly certainly indeed
page pages published url urls background update updated image images note notes comment comments source sources see also figure table
part section chapter volume appendix attachment tab results result summary introduction conclusion conclusions methodology scope
results-in-brief monday tuesday wednesday thursday friday saturday sunday am pm et pt est pst gmt utc""".split()) | set(MONTHS) | {
    m[:3] for m in MONTHS} | {"sept"}
NOT_FIRST = {"new", "old", "north", "south", "east", "west", "fort", "mount", "saint", "san", "santa", "el", "air", "army", "navy", "white",
             "black", "red", "blue", "green", "grand", "great", "little", "big", "upper", "lower", "central", "national", "united", "royal", "general",
             "young", "project", "operation", "camp", "lake", "port", "cape", "long", "high", "low", "first", "second"}
ABBREV = {"jr", "sr", "inc", "co", "corp", "ltd", "st", "mt", "ft", "vol", "no", "ed", "eds", "pp", "bros", "assn", "dept", "univ", "intl"}
GENERIC_LAST = {"agency", "office", "institute", "program", "programme", "project", "report", "study", "company", "corporation", "university",
                "department", "committee", "group", "force", "forces", "base", "field", "ranch", "academy", "laboratory", "center", "centre",
                "council", "service", "command", "division", "branch", "wing", "squadron", "times", "post", "journal", "vault", "inc", "llc",
                "ltd", "corp", "foundation", "society", "association", "board", "bureau", "administration", "authority", "commission", "school",
                "college", "hospital", "church", "army", "navy", "states", "kingdom", "republic", "city", "county", "island", "river",
                "mountain", "lake", "valley", "airport", "station", "hotel", "news", "network", "press", "magazine", "review", "podcast", "show",
                "corps", "unit", "facility", "watch", "panel", "park", "man", "woman", "officer", "agent", "director", "manager"}
import packload   # the domain's identifier forms are the pack's (packs/ufo/keywords/id-patterns.tsv; phase 4 handoff 3)
CORE_ID_PATTERNS = [  # label, order, regex (group 1 when present, else group 0, is the identifier); generic document identifier shapes
    ("agency report number", 10, r"\b[A-Z]{2,6}/[A-Z]{2,8}-\d{2,4}-\d{1,5}[A-Z]?\b"),             # ABC/DEFG-12-345
    ("memorandum or case number", 20, r"\b[A-Z]{1,6}-\d{2,4}-\d{3,6}(?:/[A-Z]{1,3})?\b"),           # M-12-3456, M-12-3456/AB
    ("contract number", 30, r"\b[A-Z]{2,6}\d{2,4}-\d{2}-[A-Z]-\d{3,5}\b"),                          # ABC123-08-C-0042
    ("correspondence code", 40, r"\b[A-Z]-\d{6}\b"),                                                 # B-123456
    ("DTIC accession", 50, r"\b(?:AD-?A|ADA)\d{6}\b"),
    ("record group", 60, r"\bRG\s?\d{1,3}\b"),
    ("FOIA case", 80, r"\b(?:FOIA|Case|Request|Ref(?:erence)?)\s*(?:No\.?|Number|#)?\s*[:#]?\s*((?:[A-Z]{1,6}-)?\d{2,}-\d{2,}(?:-\d+)?)"),
]
# the core's and the pack's forms in one list, by order number (the first to match an identifier gives its label)
ID_PATTERNS = [(lab, pat) for lab, _, pat in sorted(CORE_ID_PATTERNS + packload.id_patterns(), key=lambda x: x[1])]

def arg_parse():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="*", help="held source files (.txt/.md)")
    ap.add_argument("--wip", help="wip folder; context.md and context-overflow.md are written there")
    ap.add_argument("--names-only", action="store_true", help="print the extracted names, dates, identifiers and URLs and stop")
    ap.add_argument("--max-rows-per-term", type=int, default=5, help="rows shown per term; the rest go to the overflow (default 5; was 40 until 2026-10-22)")
    ap.add_argument("--min-count", type=int, default=3, help="minimum mentions for a multi-word name (single words need 2; default 3, was 1)")
    ap.add_argument("--broad", type=int, default=60, help="a term with more held rows than this shows the top rows and per-note counts, with no overflow (default 60, was 200)")
    ap.add_argument("--with-dates", action="store_true", help="include section 2b (held rows by date); skipped all the same when <wip>/timeline-candidates.md exists")
    ap.add_argument("--row-chars", type=int, default=220, help="rows in sections 2, 4 and 5 cut to this many characters after their citation (default 220)")
    ap.add_argument("--full", action="store_true", help="print the rows of sections 2, 4 and 5 whole (no --row-chars cut)")
    ap.add_argument("--index-cap", type=int, default=0, help="rows an index-form line lists per broad name in sections 3 to 5; the rest in the overflow (default 0: all)")
    ap.add_argument("--budget-words", type=int, default=30000, help="the pack's word budget; the summary names the sections over their share (default 30000)")
    ap.add_argument("--sets-json", help="a sets.json beside the sources (books/sources/web/<set>/sets.json)")
    ap.add_argument("--set", dest="set_key", help="the key in --sets-json whose files are the source")
    ap.add_argument("--exclude-note", default="", help="stem(s), comma-separated, of held notes left out (testing a source already held, as timeline_prepass.py --exclude-note)")
    ap.add_argument("--db", default=os.path.join(ROOT, "notes.db"))
    a = ap.parse_args()
    if a.sets_json and a.set_key:
        d = json.load(open(a.sets_json, encoding="utf-8"))
        base = os.path.dirname(os.path.abspath(a.sets_json))
        a.sources += [os.path.join(base, e[3]) for e in d[a.set_key]]
    if not a.sources: sys.exit("no source files given")
    if not a.wip and not a.names_only: sys.exit("--wip is required (unless --names-only)")
    return a

# ---------- 1 extraction ----------
def read_sources(paths):
    parts = []
    for p in paths:
        t = LN.read_text(LP.resolve_arg(p), errors="replace")   # a sources/ layout path resolves to the held file
        parts.append((os.path.relpath(p, ROOT) if os.path.abspath(p).startswith(ROOT) else p, t))
    return parts

def norm_tokens(s):
    """lowercase word tokens the way FTS5 unicode61 sees them (letters, digits; punctuation dropped)."""
    return re.findall(r"[^\W_]+", s.lower())

def phrase(s):
    toks = norm_tokens(s)
    return '"' + " ".join(toks) + '"' if toks else ""

def extract_urls(text):
    urls = collections.Counter()
    for m in re.finditer(r"https?://[^\s\]\)>\"'<]+", text):
        u = m.group(0).rstrip(".,;:)!?]")
        urls[u] += 1
    return urls

def extract_dates(text):
    """returns (full dates Counter keyed YYYY-MM-DD with the forms seen, month-years Counter keyed YYYY-MM, years Counter keyed YYYY)."""
    full, my, years = collections.Counter(), collections.Counter(), collections.Counter()
    forms = collections.defaultdict(set)
    blanked = text
    def month_no(s): return MONTHS.index([m for m in MONTHS if m.startswith(s.lower()[:3])][0]) + 1
    for m in re.finditer(r"\b(1[5-9]\d\d|20[0-4]\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", text):
        k = m.group(0); full[k] += 1; forms[k].add(re.sub(r"\s+", " ", m.group(0))); blanked = blanked.replace(m.group(0), " " * len(m.group(0)), 1)
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + MONTH_RE + r")\.?,?\s+(1[5-9]\d\d|20[0-4]\d)\b", text):
        d, mo, y = int(m.group(1)), month_no(m.group(2)), m.group(3)
        if 1 <= d <= 31: k = f"{y}-{mo:02d}-{d:02d}"; full[k] += 1; forms[k].add(re.sub(r"\s+", " ", m.group(0))); blanked = blanked.replace(m.group(0), " " * len(m.group(0)), 1)
    for m in re.finditer(r"\b(" + MONTH_RE + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(1[5-9]\d\d|20[0-4]\d)\b", text):
        mo, d, y = month_no(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= d <= 31: k = f"{y}-{mo:02d}-{d:02d}"; full[k] += 1; forms[k].add(re.sub(r"\s+", " ", m.group(0))); blanked = blanked.replace(m.group(0), " " * len(m.group(0)), 1)
    for m in re.finditer(r"\b(" + MONTH_RE + r")\.?,?\s+(1[5-9]\d\d|20[0-4]\d)\b", blanked):
        mo, y = month_no(m.group(1)), m.group(2); k = f"{y}-{mo:02d}"; my[k] += 1; forms[k].add(re.sub(r"\s+", " ", m.group(0)))
    for m in re.finditer(r"\b(1[5-9]\d\d|20[0-4]\d)\b", text):
        years[m.group(1)] += 1
    return full, my, years, forms

def extract_ids(text):
    ids = collections.Counter(); label = {}
    for lab, pat in ID_PATTERNS:
        for m in re.finditer(pat, text):
            v = m.group(1) if m.groups() else m.group(0)
            v = v.strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) or len(v) < 5: continue   # a date, not an identifier
            ids[v] += 1; label.setdefault(v, lab)
    for v in list(ids):   # an identifier that is part of a longer one (DEFG-12-345 inside ABC/DEFG-12-345) is the longer one
        if any(v != w and v in w for w in ids): del ids[v]
    titles = collections.Counter()
    for m in re.finditer(r"[\"“]([A-Z][^\"”\n]{8,160}?)[\"”]", text):
        t = m.group(1).strip().rstrip(".,;:")
        n = len(t.split())
        if 3 <= n <= 16 and re.search(r"\b(Report|Study|Memorandum|Memo|Letter|Document|Documents|Paper|Act|Program|Project|Analysis|Review|Summary|Assessment|Briefing|Investigation|Findings|Records|History|Evaluation)\b", t):
            titles[t] += 1
    for m in re.finditer(r"(?<!\*)\*([A-Z][^*\n]{8,160}?)\*(?!\*)", text):
        t = m.group(1).strip()
        if 2 <= len(t.split()) <= 16: titles[t] += 1
    return ids, label, titles

def load_lexicon(con):
    """held people names (notes.db people) and tools/name_aliases.json, normalised; surname -> {normalised full names}."""
    names = set()
    for (n,) in con.execute("SELECT name FROM people"):
        n = re.sub(r"\(.*?\)|\".*?\"|“.*?”", " ", n or "")
        toks = [t for t in norm_tokens(n) if t not in TITLES]
        if 1 <= len(toks) <= 5 and not any(t in ("unnamed", "unidentified", "the", "a", "an") for t in toks): names.add(" ".join(toks))
    aliases = {}
    ap = os.path.join(ROOT, "tools", "name_aliases.json")
    if os.path.exists(ap):
        for canon, vs in json.load(open(ap, encoding="utf-8")).items():
            if canon.startswith("_"): continue
            group = {" ".join(norm_tokens(canon))} | {" ".join(t for t in norm_tokens(re.sub(r"\(.*?\)", "", v)) if t not in TITLES) for v in vs}
            group = {g for g in group if g}
            for g in group: aliases[g] = group
            names |= group
    by_last = collections.defaultdict(set)
    for n in names:
        toks = n.split()
        if len(toks) >= 2: by_last[toks[-1]].add(n)
    return names, by_last, aliases

def clean_text(text):
    """drop URLs, image markers, page markers and boilerplate lines (a line that recurs five or more times once digits are removed:
    running headers and footers of a scanned report); identifiers become line breaks so they never join a name."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[image:[^\]]*\]", " ", text)
    text = re.sub(r"(?m)^-{2,} ?page \d+ ?-{2,}\s*$", "", text)
    lines = text.split("\n")
    key = lambda l: re.sub(r"\d+", "#", re.sub(r"\s+", " ", l.strip()))
    freq = collections.Counter(key(l) for l in lines if l.strip())
    lines = [l for l in lines if not (l.strip() and freq[key(l)] >= 5)]
    text = "\n".join(lines)
    for _, pat in ID_PATTERNS: text = re.sub(pat, "\n", text)
    text = re.sub(r"\S+@\S+\.\w+", " ", text)
    text = re.sub(r"([\(\)\[\]\"“”«»])", r" \1 ", text)
    text = re.sub(r"(?<=\w)/(?=\w)", " ¶ ", text)
    return text

ROMAN = re.compile(r"^(?=[IVXLC])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")

def extract_names(text, min_count, lexicon=frozenset()):
    """capitalised sequences, filtered; returns (Counter of display form -> count, the source's lower-case vocabulary)."""
    text = clean_text(text)
    lower_vocab = set(re.findall(r"\b[a-z][a-z'’\-]+\b", text))
    cands = collections.Counter()
    for para in re.split(r"\n\s*\n", text):
        lines = [l.split() for l in para.split("\n") if l.strip()]
        toks = []
        for i, l in enumerate(lines):
            if i and (len(l) <= 4 or len(lines[i - 1]) <= 4 or (len(l) > 1 and re.fullmatch(r"[A-Z]{2,}", l[0]) and l[1][:1].isupper())): toks.append("¶")
            toks += l
        seq = []
        def flush():
            if seq: cands[" ".join(seq)] += 1
            seq.clear()
        for raw in toks:
            if raw == "¶": flush(); continue
            lead = raw.lstrip("(\"'“‘[«*_")
            opened = lead != raw
            core = lead.rstrip(")\"'”’]»*_,.;:!?")
            closer = lead[len(core):] if core else lead
            core = re.sub(r"['’]s$", "", core)
            if opened: flush()
            if not core or not core[0].isupper():
                if seq and core.lower() in CONNECTORS and not closer: seq.append(core); continue
                flush(); continue
            if core.lower() in STOP and not seq: continue
            seq.append(core)
            if closer == "." and (len(core) == 1 or core.lower() in TITLES or core.lower() in ABBREV): continue
            if closer: flush()
        flush()
    def common(t):
        tl = t.lower().rstrip(".")
        return tl in STOP or tl in TITLES or tl in lower_vocab or (tl.endswith("s") and tl[:-1] in lower_vocab)
    def clean(c):
        toks = c.split()
        while toks and (toks[0].lower().rstrip(".") in STOP | TITLES | {"appendix", "attachment", "tab", "chapter", "figure", "table"} or ROMAN.match(toks[0])
                        or (common(toks[0]) and len(toks) > 1 and (common(toks[1]) or toks[1].lower() in STOP))): toks.pop(0)
        while toks and (toks[-1].lower() in CONNECTORS or toks[-1].lower() in STOP or toks[-1].lower().rstrip(".") in TITLES): toks.pop()
        if not toks: return None
        norm = " ".join(norm_tokens(" ".join(toks)))
        if norm in lexicon: return " ".join(toks)
        if all(common(t) for t in toks): return None
        if len(toks) == 1:
            t = toks[0].rstrip(".")
            if len(t) < 3 or re.match(r"^[A-Z]\.[A-Z]", t) or re.search(r"['’][a-z]{1,2}$", t) or t.lower() in GENERIC_LAST or (t.lower() in lower_vocab and not t.isupper()): return None
            if t.isupper() and (t.capitalize() in cands or t.lower() in lower_vocab): return None
            return t
        if all(len(t) <= 3 for t in toks): return None
        if all(t.isupper() for t in toks if t.lower() not in CONNECTORS) and len(toks) > 2 and cands.get(c, 0) < 2: return None  # an all-caps heading seen once
        return " ".join(toks)
    out = collections.Counter()
    for c, n in cands.items():
        parts = [c] + ([x.strip() for x in c.split(" and ")] if " and " in c else [])
        for i, part in enumerate(parts):
            d = clean(part)
            if d: out[d] += n
    for c in list(out):  # plurals join the singular (Authorities, Authority)
        if len(c.split()) == 1 and c.endswith("s") and c[:-1] in out: out[c[:-1]] += out.pop(c)
    final = collections.Counter()
    for c, n in out.items():
        if len(c.split()) == 1 and n < 2: continue
        if len(c.split()) > 1 and n < min_count: continue
        final[c] += n
    return final, lower_vocab

def group_names(names, lexicon, by_last, aliases, lower_vocab=frozenset()):
    """Group the candidates: a person's surname-only mentions join the full name; an acronym joins the phrase whose initials it is;
    held lexicon and alias forms are added as query variants. Returns a list of dicts: display, count, kind, variants, members."""
    items = {c: {"display": c, "count": n, "variants": {" ".join(norm_tokens(c))}, "members": {c}, "kind": "name"} for c, n in names.items()}
    first_names = {n.split()[0] for n in lexicon if len(n.split()) >= 2 and len(n.split()[0]) >= 3} - STOP
    def person_like(c):
        toks = [t for t in norm_tokens(c) if t not in TITLES]
        if not (2 <= len(toks) <= 4) or any(t in CONNECTORS for t in toks) or toks[-1] in GENERIC_LAST: return None
        if any(t.isupper() and len(t) > 1 for t in c.split()): return None
        full = " ".join(toks); fl = toks[0] + " " + toks[-1]
        if toks[-1] in lower_vocab or toks[0] in lower_vocab: return None
        if full in lexicon or fl in lexicon or re.match(r"(?i)^(" + "|".join(TITLES) + r")\.?\s", c): return toks
        if (toks[0] in first_names and toks[0] not in NOT_FIRST and toks[0] not in lower_vocab and toks[-1] not in lower_vocab and len(toks) <= 3
                and all(t.isalpha() for t in toks) and len(toks[-1]) >= 3 and not c.split()[0].isupper()): return toks
        return None
    # people
    for c, it in list(items.items()):
        toks = person_like(c)
        if not toks: continue
        it["kind"] = "person"; it["last"] = toks[-1]
        it["variants"] |= {" ".join(toks), toks[0] + " " + toks[-1]}
        for lex in by_last.get(toks[-1], ()):
            if lex.split()[0] == toks[0]: it["variants"].add(lex)
        for v in list(it["variants"]):
            if v in aliases: it["variants"] |= {x for x in aliases[v] if len(x.split()) >= 2 or x == toks[-1]}
        # the surname alone is a query variant only when the source itself uses it alone (a standalone candidate merges in below)
    # persons with the same first and last token merge (Gareth Lisle, Gareth T Lisle)
    key = {}
    for c in sorted(items, key=lambda x: -items[x]["count"]):
        it = items[c]
        if it["kind"] != "person": continue
        toks = [t for t in norm_tokens(c) if t not in TITLES]; k = (toks[0], toks[-1])
        if k in key:
            o = items[key[k]]; o["count"] += it["count"]; o["members"] |= it["members"]; o["variants"] |= it["variants"]; del items[c]
        else: key[k] = c
    # surname-only and first-name-only candidates join a person when exactly one person carries that token
    for c in list(items):
        if c not in items or len(c.split()) != 1 or c.isupper(): continue
        low = c.lower()
        owners = [k for k, it in items.items() if it["kind"] == "person" and (it.get("last") == low or norm_tokens(k)[0] == low)]
        if len(owners) == 1:
            o = items[owners[0]]; o["count"] += items[c]["count"]; o["members"].add(c)
            if o.get("last") == low and len(low) >= 4 and low not in lower_vocab and low not in GENERIC_LAST: o["variants"].add(low)
            del items[c]
    # title-only variants ("Dr James T Lacatski" and "James T Lacatski") merge
    by_norm = collections.defaultdict(list)
    for c, it in items.items():
        by_norm[" ".join(t for t in norm_tokens(c) if t not in TITLES)].append(c)
    for k, cs in by_norm.items():
        if len(cs) > 1:
            keep = max(cs, key=lambda x: (items[x]["count"], -len(x)))
            for c in cs:
                if c == keep: continue
                items[keep]["count"] += items[c]["count"]; items[keep]["members"].add(c); items[keep]["variants"] |= items[c]["variants"]; del items[c]
    # acronyms join the phrase whose initials they are
    for c in list(items):
        if c not in items or len(c.split()) != 1 or not c.isupper(): continue
        owners = [k for k in items if len(k.split()) > 1 and "".join(t[0] for t in k.split() if t.lower() not in CONNECTORS).upper() == c]
        if len(owners) == 1:
            o = items[owners[0]]; o["count"] += items[c]["count"]; o["members"].add(c); o["variants"].add(c.lower()); o["kind"] = "organisation or programme"; del items[c]
    for it in items.values():
        it["variants"] = {v for v in it["variants"] if v}
        if it["kind"] == "name" and len(it["display"].split()) == 1 and it["display"].isupper(): it["kind"] = "acronym"
    return sorted(items.values(), key=lambda it: (-it["count"], it["display"].lower()))

# ---------- 2 held rows ----------
def fts_query(variants):
    ps = sorted({phrase(v) for v in variants if phrase(v)}, key=len, reverse=True)
    return " OR ".join(ps)

def trim(s, n): return rs.trim(s, n)

ROW_CHARS = None   # set from --row-chars by main(); None prints rows whole (--full)

def cut(s):
    """A row's content after its citation, cut to --row-chars (whole under --full)."""
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if ROW_CHARS is None or len(s) <= ROW_CHARS else s[:ROW_CHARS - 1].rstrip() + "…"

def row_note(a):
    return (f"Rows are cut to {a.row_chars} characters after their citation (`--full` prints them whole): read the full row in its note before using it.\n" if not a.full
            else "Rows are printed whole (`--full`); read the row in its note before using it.\n")

def fmt_row(r, n=TRIM):
    return f"- {rs.cite(r['kind'], r['video'], r['n'])} | " + cut(f"{r['date'] or ''} | {r['speaker'] or ''} | {r['text'] or ''}")

class Pack:
    def __init__(self, con, cap, broad, excl=()):
        self.con, self.cap, self.broad, self.excl = con, cap, broad, set(excl)
        self.seen = {}            # cite -> term that first showed it
        self.commands = []
        self.L, self.O = [], []   # context.md and overflow lines
        self.rows_cited = 0; self.notes_cited = collections.Counter()
        self.terms_with_rows = 0; self.terms_without = []; self.broad_terms = []

    def run(self, query, kinds=KINDS, d_from=None, d_to=None):
        cmd = f"python3 tools/rows_search.py '{query}' --table {','.join('timeline' if k == 'tl' else k for k in kinds)}"
        if d_from: cmd += f" --from {d_from}"
        if d_to: cmd += f" --to {d_to}"
        self.commands.append(cmd)
        try:
            total, rows = rs.search(self.con, query, None, None, kinds, d_from, d_to, 10 ** 7)
            if self.excl:
                kept = [r for r in rows if r["video"] not in self.excl]; total -= len(rows) - len(kept); rows = kept
        except sqlite3.OperationalError as e:
            self.L.append(f"  (query error: {e}; command: {cmd})"); return 0, []
        return total, rows

    def emit(self, heading, total, rows, prefer=None, note="", only_prefer=False, cap=None):
        """write one term's group: up to cap rows (those matching `prefer` first), 'and N more' line, overflow.
        A broad term (total > --broad) shows the cap and then per-note counts instead of an overflow. With only_prefer, rows that
        fail `prefer` are not shown at all but counted (bare years: a timeline row in the year that names none of the source's names)."""
        if total == 0:
            self.terms_without.append(heading); return
        if prefer:
            rows = sorted(rows, key=lambda r: 0 if prefer(r) else 1)
            if only_prefer:
                keep = [r for r in rows if prefer(r)]
                note = (note + "; " if note else "") + f"{len(rows) - len(keep)} rows in the range name none of the source's names and are not listed"
                rows = keep
                if not rows:
                    self.L.append(f"\n### {heading} ({total} held rows; none names one of the source's names)\n"); return
        self.terms_with_rows += 1
        broad = total > self.broad; cap = cap or self.cap
        self.L.append(f"\n### {heading} ({total} held rows{'; ' + note if note else ''}{'; broad: top rows and per-note counts only' if broad else ''}; cap {cap})\n")
        new = [r for r in rows if rs.cite(r["kind"], r["video"], r["n"]) not in self.seen]
        dup = [r for r in rows if rs.cite(r["kind"], r["video"], r["n"]) in self.seen]
        shown = new[:cap]
        for r in shown:
            c = rs.cite(r["kind"], r["video"], r["n"]); self.seen[c] = heading; self.rows_cited += 1; self.notes_cited[r["video"]] += 1
            self.L.append(fmt_row(r))
        if dup:
            self.L.append(f"- also matched, shown under an earlier term: " + ", ".join(rs.cite(r["kind"], r["video"], r["n"]) for r in dup[:40]) + (f" and {len(dup) - 40} more" if len(dup) > 40 else ""))
        rest = new[cap:]
        if rest and broad:
            by = collections.Counter(r["video"] for r in rest)
            self.broad_terms.append((heading, total, self.commands[-1]))
            self.L.append(f"- and {len(rest)} more rows, by note (narrow with --note): " + ", ".join(f"{v} {n}" for v, n in by.most_common(30)) + (f" and {len(by) - 30} other notes" if len(by) > 30 else ""))
        elif rest:
            self.L.append(f"- and {len(rest)} more rows, listed in context-overflow.md under this heading")
            self.O.append(f"\n### {heading} ({len(rest)} rows beyond the cap of {cap})\n")
            for r in rest: self.O.append(fmt_row(r, TRIM_OVER))

# ---------- 3 to 6 registers and pages ----------
def name_regex(variants):
    vs = sorted({v for v in variants if len(v) >= 4}, key=len, reverse=True)
    if not vs: return None
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(v).replace(r"\ ", r"[\s\.]+") for v in vs) + r")(?![\w-])", re.I)

def md_table_rows(body):
    """rows of the first markdown table in body, as dicts keyed by lower-cased header (form T2b of the parser library)."""
    return LN.first_table(body)

def section(txt, heading):
    return LN.section_text(txt, heading)   # form S4

def fu_year_range(event):
    e = re.sub(r"\(.*?\)", " ", event or "")
    ys = [int(y) for y in re.findall(r"\b(1[5-9]\d\d|20[0-4]\d)\b", e)]
    return (min(ys), max(ys)) if ys else None

def source_kinds():
    p = os.path.join(ROOT, "research", "source-kinds.md"); kinds = {}
    if os.path.exists(p):
        for r in md_table_rows(LN.read_text(p)):
            if r.get("stem"): kinds[r["stem"]] = r.get("kind", "")
    return kinds

INDEX_CAP = 0   # set from --index-cap by main(); 0 lists every row

def index_line(section, name, items, pk):
    """An index-form line: the rows a broad name matched (items, rendered), at most --index-cap of them; with a cap, the whole line
    is written to context-overflow.md under the section, so nothing is dropped."""
    head = f"- matched only by the broad name '{name}' ({len(items)}): "
    keep = len(items) if not INDEX_CAP else min(INDEX_CAP, len(items))
    if ROW_CHARS is not None and section.startswith(("4", "5")):   # sections 4 and 5: the line cut to --row-chars at a whole row
        n, used = 0, 0
        while n < keep and (n == 0 or used + 2 + len(items[n]) <= ROW_CHARS): used += (2 if n else 0) + len(items[n]); n += 1
        keep = n
    if keep >= len(items): return head + "; ".join(items)
    pk.O.append(f"\n### Section {section}: every row matched only by the broad name '{name}' ({len(items)})\n"); pk.O.append(head + "; ".join(items))
    return head + "; ".join(items[:keep]) + f"; and {len(items) - keep} more, listed in context-overflow.md (section {section})"

# ---------- the word budget (2026-10-22) ----------
SHARES = [("1", "Extracted from the source", 0.10), ("2", "Held rows by name", 0.35), ("2b", "Held rows by date", 0.10), ("2c", "by identifier and title", 0.08),
          ("2d", "by URL", 0.03), ("2e", "Terms with no held rows", 0.04), ("3", "First-utterance clusters", 0.10), ("4", "Narrative ledgers and nodes", 0.10),
          ("5", "Leads", 0.07), ("6", "Dense notes", 0.03)]

def budget_summary(H, L, budget):
    """One line: the pack's words against --budget-words, and the sections over their share of it (SHARES; 4b counts with 4)."""
    words = {k: 0 for k, _, _ in SHARES}; cur = "1"
    for line in H + L:
        m = re.match(r"^\s*##+ (\d[a-e]?)\.", line.lstrip("\n"))
        if m: cur = m.group(1) if m.group(1) in words else ("4" if m.group(1) == "4b" else None)   # section 7 (commands) is not counted
        if cur in words: words[cur] += len(line.split())
    total = sum(words.values())
    over = [(k, name, words[k], int(budget * s)) for k, name, s in SHARES if words[k] > budget * s]
    return (f"Budget: {total:,} words against --budget-words {budget:,}" + (" (within)" if total <= budget else f" (over by {total - budget:,})") + "; "
            + (("sections over their share: " + "; ".join(f"{k} {name} {w:,} of {s:,}" for k, name, w, s in over)) if over else "no section over its share")
            + ". Narrow with --max-rows-per-term, --min-count, --broad or --row-chars.")

# ---------- main ----------
def main():
    a = arg_parse()
    global ROW_CHARS, INDEX_CAP
    ROW_CHARS = None if a.full else a.row_chars; INDEX_CAP = a.index_cap
    srcs = read_sources(a.sources)
    text = "\n\n".join(t for _, t in srcs)
    words = len(text.split())
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    if not con.execute("SELECT name FROM sqlite_master WHERE name='rows_fts'").fetchone():
        sys.exit("notes.db has no rows_fts table; run python3 tools/build_db.py first")
    lexicon, by_last, aliases = load_lexicon(con)
    cands, lower_vocab = extract_names(text, a.min_count, lexicon)
    names = group_names(cands, lexicon, by_last, aliases, lower_vocab)
    full, my, years, forms = extract_dates(text)
    ids, id_label, titles = extract_ids(text)
    urls = extract_urls(text)
    if a.names_only:
        print(f"# names ({len(names)}) from {len(srcs)} files, {words} words: count | kind | display | members | query variants")
        for it in names: print(f"{it['count']} | {it['kind']} | {it['display']} | {'; '.join(sorted(it['members'] - {it['display']}))} | {' OR '.join(sorted(it['variants']))}")
        print(f"\n# dates: {len(full)} full, {len(my)} month-year, {len(years)} years")
        for k, n in sorted(full.items()): print(f"{n} | date | {k} | {'; '.join(sorted(forms[k]))}")
        for k, n in sorted(my.items()): print(f"{n} | month | {k} | {'; '.join(sorted(forms[k]))}")
        print("years: " + ", ".join(f"{y} ({n})" for y, n in sorted(years.items())))
        print(f"\n# identifiers ({len(ids)}) and titles ({len(titles)})")
        for k, n in ids.most_common(): print(f"{n} | {id_label[k]} | {k}")
        for k, n in titles.most_common(): print(f"{n} | title | {k}")
        print(f"\n# urls ({len(urls)})")
        for k, n in urls.most_common(): print(f"{n} | {k}")
        return
    os.makedirs(a.wip, exist_ok=True)
    excl = [x.strip() for x in a.exclude_note.split(",") if x.strip()]
    pk = Pack(con, a.max_rows_per_term, a.broad, excl)
    def created_by_excluded(text):   # a register row whose every cited note is an excluded one (the excluded intake made it)
        cited = set(re.findall(r"(?:\[|/)([a-z0-9][a-z0-9-]+?)(?:\.md|\s+(?:tl|claims|audit|xc)\s)", text or ""))
        return bool(excl) and bool(cited) and cited <= set(excl)
    L = pk.L
    # --- 2 names
    L.append("## 2. Held rows by name\n")
    L.append("Each group: the name as the source gives it (mentions in the source), the query variants, then the matching held rows ranked by bm25, "
             "`[citation] | date | speaker | text`. A row is shown once, under the first term that matched it; later terms list it as a citation only. "
             f"Cap {a.max_rows_per_term} rows per term; a single-word term that is not a person, or a broad term (more than {a.broad} held rows) the source names only once, gets a quarter of that. "
             "A term match is never a finding: read the row in its note before citing it (tools/schema.md section 10).")
    L.append(row_note(a))
    for it in names:
        q = fts_query(it["variants"])
        if not q: continue
        total, rows = pk.run(q)
        mem = "; ".join(sorted(it["members"] - {it["display"]}))
        single = len(it["display"].split()) == 1 and it["kind"] != "person"
        quarter = single or (total > a.broad and it["count"] < 2)   # a single word, or a broad term the source names only once
        multi = name_regex({v for v in it["variants"] if " " in v})   # rows carrying a fuller form of the name rank before surname-only matches
        pref = (lambda r: bool(multi.search((r["text"] or "") + " " + (r["speaker"] or "") + " " + (r["extra"] or "")))) if multi and len(it["variants"]) > 1 else None
        pk.emit(f"{it['display']} ({it['count']} mentions{'; also ' + mem if mem else ''})", total, rows, pref, note=f"query {q}", cap=max(5, a.max_rows_per_term // 4) if quarter else None)
    # --- 2b dates
    L.append("\n## 2b. Held rows by date\n")
    tc = os.path.join(a.wip, "timeline-candidates.md")
    dates_on = a.with_dates and not os.path.exists(tc)
    if not dates_on:
        L.append(("Not built: " + (f"{os.path.relpath(tc, ROOT) if os.path.abspath(tc).startswith(ROOT) else tc} holds the source's dates against the held timeline rows (tools/timeline_prepass.py)." if os.path.exists(tc)
                  else "off by default (`--with-dates` builds it); the dates are better read in timeline-candidates.md from tools/timeline_prepass.py.")) + f" The source's dates are listed in section 1.")
    else: L.append("Full dates and month-years: timeline rows whose event date falls in the day or month (`--from/--to`), then claims and audit rows whose "
             "text carries the date. Month-years and bare years: only the timeline rows in that month or year that also name one of the source's specific names (the count of the rest is stated). "
             "Claims and audit rows are not searched by bare year (the match would be the note's own date, not the claim's). "
             f"Caps: a full date {a.max_rows_per_term} rows, a month-year half that, a bare year a quarter; the rest go to the overflow.")
    name_re = name_regex({v for it in names for v in it["variants"]})
    # the registers, pages and date ranges are matched on specific names only: multi-word variants, people's surnames, and single words of
    # five letters or more that are not acronyms of four letters or fewer (an agency or statute acronym would match every row on its subject),
    # and a plain name (not a person, organisation or programme) counts only when the source names it at least twice
    reg_vars = set()
    for it in names:
        if it["kind"] not in ("person", "organisation or programme") and it["count"] < 2: continue
        for v in it["variants"]:
            if " " in v or it["kind"] == "person" or (len(v) >= 5 and not (it["kind"] == "acronym" and len(v) <= 4)): reg_vars.add(v)
    reg_re = name_regex(reg_vars)
    def prefer(r): return r["kind"] != "tl" or bool(reg_re and reg_re.search((r["text"] or "") + " " + (r["extra"] or "")))
    for k, n in (sorted(full.items()) if dates_on else []):
        total, rows = pk.run("kind:tl", ["tl"], k, k)
        y, mo, d = k.split("-"); mn = MONTHS[int(mo) - 1]
        q = f'"{int(d)} {mn} {y}" OR "{mn} {int(d)} {y}" OR "{y} {mo} {d}"' + (f' OR "{d} {mn} {y}"' if d.startswith("0") else "")
        t2, r2 = pk.run(q, ["claims", "audit"])
        pk.emit(f"{k} ({n} mentions: {'; '.join(sorted(forms[k]))})", total + t2, list(rows) + list(r2), prefer, "timeline by event date, then claims and audit by text")
    for k, n in (sorted(my.items()) if dates_on else []):
        y, mo = k.split("-"); mn = MONTHS[int(mo) - 1]
        total, rows = pk.run("kind:tl", ["tl"], k + "-00", k + "-31")
        t2, r2 = pk.run(f'"{mn} {y}"', ["claims", "audit"])
        pk.emit(f"{k} ({n} mentions: {'; '.join(sorted(forms[k]))})", total + t2, list(rows) + list(r2), prefer, "timeline rows in the month that name one of the source's names, then claims and audit by text", only_prefer=True, cap=max(5, a.max_rows_per_term // 2))
    for y, n in (sorted(years.items()) if dates_on else []):
        total, rows = pk.run("kind:tl", ["tl"], y + "-00-00", y + "-12-31")
        pk.emit(f"{y} ({n} mentions)", total, rows, prefer, "timeline rows in the year that name one of the source's names", only_prefer=True, cap=max(5, a.max_rows_per_term // 4))
    # --- 2c identifiers
    L.append("\n## 2c. Held rows by document identifier and title\n")
    for k, n in ids.most_common():
        q = phrase(k)
        if not q: continue
        total, rows = pk.run(q)
        pk.emit(f"{k} ({id_label[k]}; {n} mentions)", total, rows, note=f"query {q}")
    for k, n in titles.most_common():
        q = phrase(k)
        total, rows = pk.run(q)
        pk.emit(f"“{k}” (quoted title; {n} mentions)", total, rows, note=f"query {q}")
    # --- 2d urls
    L.append("\n## 2d. Held rows by URL\n")
    held_urls = {}
    for r in con.execute("SELECT id, url FROM videos WHERE url IS NOT NULL AND url != ''"):
        m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", r["url"] or "")
        held_urls[m.group(1) if m else r["url"].rstrip("/")] = r["id"]
    for u, n in urls.most_common():
        m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", u)
        key = m.group(1) if m else u.rstrip("/")
        held = held_urls.get(key)
        q = phrase(re.sub(r"^https?://(www\.)?", "", u))
        total, rows = pk.run(q) if q else (0, [])
        if held: L.append(f"\n- {u}: held as a note, [{held}]")
        pk.emit(f"{u} ({n} mentions{'; held as [' + held + ']' if held else ''})", total, rows, note="the URL's tokens as a phrase")
    L.append("\n## 2e. Terms with no held rows, and broad terms\n")
    if pk.terms_without:
        L.append(f"\n### Terms with no held rows ({len(pk.terms_without)})\n")
        L.append("; ".join(pk.terms_without))
    if pk.broad_terms:
        L.append(f"\n### Broad terms ({len(pk.broad_terms)}; each has more than {a.broad} held rows: the top {a.max_rows_per_term} are shown above with per-note counts, nothing in the overflow; narrow with --note)\n")
        for d, t, c in pk.broad_terms: L.append(f"- {d}: {t} rows; `{c} --note '<stem glob>'`")
    # --- 3 first-utterance register
    def by_name(rows_hits, cap=REG_CAP):
        """rows_hits: list of (row, [matched names]). A name that matched more than cap rows is broad for this register. Returns
        (full rows: those with at least one non-broad name; index rows: the rest, grouped by name) so nothing is dropped."""
        cnt = collections.Counter(h for _, hits in rows_hits for h in hits)
        broad = {h for h, n in cnt.items() if n > cap}
        full = [(r, hits) for r, hits in rows_hits if any(h not in broad for h in hits)]
        idx = collections.defaultdict(list)
        for r, hits in rows_hits:
            if not any(h not in broad for h in hits):
                for h in hits: idx[h].append(r)
        return full, idx, broad
    L.append("\n## 3. First-utterance register clusters (research/first-utterance-register.md)\n")
    fu_path = os.path.join(ROOT, "research", "first-utterance-register.md")
    fu_name, fu_date = [], []
    src_years = set(int(k[:4]) for k in list(full) + list(my)) | set(int(y) for y in years)
    src_specific = set(int(k[:4]) for k in list(full) + list(my))
    if os.path.exists(fu_path):
        for r in md_table_rows(LN.read_text(fu_path)):
            if not r.get("id", "").startswith("FU-") or created_by_excluded(r.get("rows", "")): continue
            hit = reg_re.findall(r.get("event", "") + " " + r.get("claim", "")) if reg_re else []
            rng = fu_year_range(r.get("event", ""))
            if hit: fu_name.append((r, sorted({h.lower() for h in hit})))
            elif rng and any(rng[0] <= y <= rng[1] for y in src_years): fu_date.append((r, rng, "specific" if any(rng[0] <= y <= rng[1] for y in src_specific) else "year"))
    fu_full, fu_idx, fu_broad = by_name(fu_name)
    L.append(f"Name matches ({len(fu_name)}; Event or Claim names one of the source's names; {len(fu_full)} in full, the rest in index form under the broad name that matched them): "
             "ID | Event | Claim | Rows | Earliest held | Status | matched. Cite a cluster as [fu FU-n].\n")
    for r, hit in fu_full:
        L.append(f"- {r['id']} | {trim(r.get('event',''), 80)} | {trim(r.get('claim',''), 240)} | {trim(r.get('rows',''), 200)} | {trim(r.get('earliest held telling',''), 60)} | {r.get('status','')} | {', '.join(hit)}")
    for h, rows_ in sorted(fu_idx.items(), key=lambda x: -len(x[1])):
        L.append(index_line("3 first-utterance clusters", h, [f"{r['id']} ({r.get('status','')}) {trim(r.get('claim',''), 60)}" for r in rows_], pk))
    L.append(f"\nDate matches ({len(fu_date)}; the cluster's year range covers a source date; 'specific' when a full date or month-year of the source falls in it, 'year' when only a bare year does): ID | range | Claim | Status.\n")
    for r, rng, how in fu_date:
        L.append(f"- {r['id']} | {rng[0]}-{rng[1]} ({how}) | {trim(r.get('claim',''), 140)} | {r.get('status','')}")
    # --- 4 narrative ledgers
    L.append("\n## 4. Narrative pages: contradiction-ledger rows that name the source's names\n")
    L.append("Columns: page ledger row # (node) | contradiction | side taken | matched names. Rows matched only by a broad name (one that matched more than "
             f"{REG_CAP} rows) follow in index form. Nodes in 4b. Cite a ledger row as `<page> ledger row N`.\n")
    L.append(row_note(a))

    pages = sorted(p for p in glob.glob(os.path.join(ROOT, "research", "narrative-*.md")) if not re.search(r"narrative-(synchrony|rival|register|history)", os.path.basename(p)))
    led, nod = [], []
    for p in pages:
        txt = LN.read_text(p); stem = os.path.basename(p)[:-3]
        for r in md_table_rows(section(txt, "Contradiction ledger")):
            blob = " ".join(r.get(c, "") for c in ("contradiction", "side taken", "other side", "why survivable", "flare"))
            hit = reg_re.findall(blob) if reg_re else []
            if hit: led.append(((stem, r), sorted({h.lower() for h in hit})))
        for r in md_table_rows(section(txt, "Nodes")):
            blob = " ".join(r.get(c, "") for c in ("node", "carriers", "rows"))
            hit = reg_re.findall(blob) if reg_re else []
            if hit: nod.append(((stem, r), sorted({h.lower() for h in hit})))
    led_full, led_idx, _ = by_name(led)
    L.append(f"Ledger rows ({len(led)}; {len(led_full)} in full):\n")
    for (stem, r), hit in led_full:
        L.append(f"- {stem} ledger row {r.get('#','')} (node {r.get('node','')}) | " + cut(f"{r.get('contradiction','')} | side: {r.get('side taken','')}") + f" | matched: {', '.join(hit)}")
    for h, rows_ in sorted(led_idx.items(), key=lambda x: -len(x[1])):
        L.append(index_line("4 ledger rows", h, [f"{stem} row {r.get('#','')} (node {r.get('node','')}) {trim(r.get('contradiction',''), 50)}" for stem, r in rows_], pk))
    nod_full, nod_idx, _ = by_name(nod)
    L.append(f"\n### 4b. Nodes ({len(nod)}; {len(nod_full)} in full): page node # | date | node | carriers | matched\n")
    for (stem, r), hit in nod_full:
        L.append(f"- {stem} node {r.get('#','')} | " + cut(f"{r.get('date','')} | {r.get('node','')} | {r.get('carriers','')}") + f" | matched: {', '.join(hit)}")
    for h, rows_ in sorted(nod_idx.items(), key=lambda x: -len(x[1])):
        L.append(index_line("4b nodes", h, [f"{stem} node {r.get('#','')} {trim(r.get('node',''), 50)}" for stem, r in rows_], pk))
    # --- 5 leads
    L.append("\n## 5. Leads register rows that name the source's names (research/leads-and-inferences.md)\n")
    L.append("Columns: lead # (kind, status) | lead | what would settle it | answer | matched. Rows matched only by a broad name follow in index form. "
             "Answer a lead in the note's Cross-checks (`answers`, `lead N`).\n")
    L.append(row_note(a))

    lp = os.path.join(ROOT, "research", "leads-and-inferences.md"); leads_hit = []
    if os.path.exists(lp):
        hdr = None
        for line in LN.iter_lines(lp):
            if not line.startswith("|"): continue
            cells = LN.split_row(line)
            if cells and cells[0] == "#": hdr = [c.lower() for c in cells]; continue
            if hdr and cells and re.fullmatch(r"\d+", cells[0]) and not created_by_excluded(" ".join(cells[3:5])):
                r = dict(zip(hdr, cells))
                blob = " ".join(r.get(c, "") for c in ("lead", "sources", "what would settle it", "answer"))
                hit = reg_re.findall(blob) if reg_re else []
                if hit: leads_hit.append((r, sorted({h.lower() for h in hit})))
    lead_full, lead_idx, _ = by_name(leads_hit)
    L.append(f"Leads ({len(leads_hit)}; {len(lead_full)} in full):\n")
    for r, hit in lead_full:
        L.append(f"- lead {r.get('#','')} ({r.get('kind','')}, {r.get('status','')}) | " + cut(f"{r.get('lead','')} | settle: {r.get('what would settle it','')} | answer: {r.get('answer','')}") + f" | matched: {', '.join(hit)}")
    for h, rows_ in sorted(lead_idx.items(), key=lambda x: -len(x[1])):
        L.append(index_line("5 leads", h, [f"lead {r.get('#','')} ({r.get('status','')}) {trim(r.get('lead',''), 50)}" for r in rows_], pk))
    # --- 6 dense notes
    L.append("\n## 6. Held notes that mention the names most densely (top 15 by count)\n")
    L.append("Columns: note | source kind | mentions of the source's names in the note (its transcript included) | the names counted most | rows of it cited above.\n")
    kinds = source_kinds(); dens = []
    if reg_re:
        for r in con.execute("SELECT id, file FROM videos"):
            if r["id"] in excl: continue
            fp = os.path.join(ROOT, r["file"] or "")
            if not os.path.exists(fp): continue
            cnt = collections.Counter(m.group(0).lower() for m in reg_re.finditer(LN.read_text(fp, errors="replace")))
            if cnt: dens.append((sum(cnt.values()), r["id"], cnt))
    dens.sort(key=lambda x: -x[0])
    L.append("| Note | Kind | Mentions | Names counted most | Rows cited above |\n|---|---|---|---|---|")
    for total, vid, cnt in dens[:15]:
        L.append(f"| {vid} | {kinds.get(vid, '')} | {total} | {', '.join(f'{k} {v}' for k, v in cnt.most_common(6))} | {pk.notes_cited.get(vid, 0)} |")
    if len(dens) > 15:
        L.append(f"\nThe other {len(dens) - 15} notes with any mention, by count: " + "; ".join(f"{vid} {t}" for t, vid, _ in dens[15:]))
    # --- 7 commands
    L.append("\n## 7. Commands used\n")
    L.append(f"{len(pk.commands)} tools/rows_search.py queries were run through its search() function with no limit (the full list is at the end of context-overflow.md). Forms: "
             "a name as its variants OR-ed, each a quoted phrase, `--table claims,timeline,audit`; a date as `kind:tl --table timeline --from <d> --to <d>` (a timeline event-date range) "
             "and its spellings as phrases over claims and audit; an identifier, title or URL as the phrase of its tokens.")
    pk.O.append(f"\n## Commands used ({len(pk.commands)})\n")
    pk.O += [f"- `{c}`" for c in pk.commands]
    # --- header
    today = datetime.date.today().isoformat()
    H = [f"# Context pack: {', '.join(os.path.basename(p) for p, _ in srcs[:3])}{' and ' + str(len(srcs) - 3) + ' more files' if len(srcs) > 3 else ''}", "",
         f"Built {today} by tools/context_pack.py from {len(srcs)} source file(s), {words} words. Command: `python3 tools/context_pack.py {' '.join(a.sources[:3])}{' ...' if len(a.sources) > 3 else ''} --wip {a.wip} --max-rows-per-term {a.max_rows_per_term} --min-count {a.min_count} --broad {a.broad}{' --with-dates' if a.with_dates else ''}{' --full' if a.full else ' --row-chars ' + str(a.row_chars)}`.",
         "", "Rule: read this file before any held note; open a note only for a row this pack cites, and read that row in its note before entering it in Cross-checks. "
         "Every row here is a term match, never a finding. Caps are stated per group; rows beyond a cap are in context-overflow.md, never dropped.", "",
         "| Count | |", "|---|---|",
         f"| Source files | {len(srcs)}: {'; '.join(p for p, _ in srcs)} |",
         f"| Names extracted | {len(names)} ({sum(1 for it in names if it['kind'] == 'person')} people) |",
         f"| Dates | {len(full)} full dates, {len(my)} month-years, {len(years)} years |",
         f"| Identifiers and titles | {len(ids)} identifiers, {len(titles)} quoted titles |",
         f"| URLs | {len(urls)} |",
         f"| Held rows cited | {pk.rows_cited} rows across {len(pk.notes_cited)} notes; terms with rows {pk.terms_with_rows}, without {len(pk.terms_without)}, broad {len(pk.broad_terms)} |",
         f"| Overflow rows | {sum(1 for l in pk.O if l.startswith('- '))} in context-overflow.md |",
         f"| First-utterance clusters | {len(fu_name)} by name, {len(fu_date)} by date |",
         f"| Narrative ledger rows | {len(led)} (nodes {len(nod)}) |",
         f"| Leads | {len(leads_hit)} |",
         f"| Notes with any mention | {len(dens)} |",
         "", "## 1. Extracted from the source", "",
         "Names (mentions; kind; other forms seen):", ""]
    H += [f"- {it['display']} ({it['count']}; {it['kind']}{'; also ' + '; '.join(sorted(it['members'] - {it['display']})) if len(it['members']) > 1 else ''})" for it in names]
    H += ["", "Dates: " + ", ".join(f"{k} ({n})" for k, n in sorted(full.items())) + " | months: " + ", ".join(f"{k} ({n})" for k, n in sorted(my.items())) + " | years: " + ", ".join(f"{y} ({n})" for y, n in sorted(years.items())),
          "", "Identifiers: " + ", ".join(f"{k} ({id_label[k]}, {n})" for k, n in ids.most_common()) + " | titles: " + "; ".join(f"“{k}” ({n})" for k, n in titles.most_common()),
          "", f"URLs ({len(urls)}): " + ", ".join(u for u, _ in urls.most_common()), ""]
    out = os.path.join(a.wip, "context.md"); over = os.path.join(a.wip, "context-overflow.md")
    budget = budget_summary(H, L, a.budget_words)
    H[3:3] = [budget, ""]; print(budget)
    LN.write_text(out, "\n".join(H + L) + "\n")
    LN.write_text(over, f"# Context pack overflow for {out}\n\nRows beyond --max-rows-per-term {a.max_rows_per_term}, under the same headings as context.md section 2; nothing is dropped.\n" + "\n".join(pk.O) + "\n")
    wc = lambda p: len(LN.read_text(p).split())
    print(f"wrote {out} ({wc(out)} words) and {over} ({wc(over)} words); names {len(names)}, rows cited {pk.rows_cited}, overflow rows {sum(1 for l in pk.O if l.startswith('- '))}, fu {len(fu_name)}+{len(fu_date)}, ledger {len(led)}, nodes {len(nod)}, leads {len(leads_hit)}, notes {len(dens)}")

if __name__ == "__main__":
    main()
