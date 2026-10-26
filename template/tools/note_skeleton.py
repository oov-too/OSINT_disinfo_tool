#!/usr/bin/env python3
"""Note skeleton: the house form of a note, derived from the schema and the exemplar notes (tools/note_skeleton.md).

  python3 tools/note_skeleton.py --form document|adverse-web|adverse-forum|video|text --task wip/<task> \
          [--note books/<planned>.md] [--source <held path> ...] [--stdout]
      writes wip/<task>/skeleton.md: the metadata block (every key in schema order, the derivable cells filled),
      every section heading of tools/schema.md in order with the form's own sections, each table's header row,
      and two example rows per table lifted verbatim from the exemplar notes, each marked `<!-- example row, delete -->`.

  python3 tools/note_skeleton.py --check <note.md> [--form <form>]
      reports which schema sections, table headers and lines a finished note lacks or misorders; exit 1 on a schema gap.

Nothing structural is typed here: the schema's section headings, column headers and count lines are parsed from
tools/schema.md, and every heading, table header, sub-heading and example row is parsed from the exemplar notes, so the
skeleton cannot drift from the real form. The per-form tables below only SELECT which exemplar supplies which section;
a selected heading that an exemplar no longer carries is an error, never a silent omission.
"""
import argparse, datetime, glob, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # project paths and the sources/ alias table

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
SCHEMA = os.path.join(_T, "schema.md")   # the core schema, beside the tools
# schema section 6, the object watch, under the name the schema beside these tools gives it (the core schema's `## Object watch`; a
# project's own schema may keep its pack's name); the pack's [objects] watch_heading is the heading the notes carry (phase 7b)
WATCH = next((m.group(1) for m in (re.match(r"^## 6\. `## (.+?)`", l) for l in LN.read_lines(SCHEMA)) if m), "Object watch")
MARK = "<!-- example row, delete -->"

# The exemplars and the form sections are the pack's (the pack's skeleton-forms.toml through tools/packload.py; phase 4 handoff 1,
# 2026-10-22): "primary" gives the heading order; "sections" lists the form's own (non-schema) headings and, where the primary lacks
# one, the exemplar that supplies it. "pool" is searched for example rows after the primary and the suppliers. GRID is the pack's
# free-section trio.
import packload
FORMS, GRID = packload.skeleton_forms()
# The core default forms (2026-10-22, phase 6b handoff 1): a pack that names no [skeleton] forms has no exemplar notes yet (a new
# pack's first intake), so the skeleton is built from tools/schema.md alone: every schema section in order with its table header,
# count line and empty-table line, the metadata keys with the schema's own descriptions, no example rows. A pack's exemplar-based
# forms, where it names them, override these.
CORE_FORMS = {"video": "a recording (interview, hearing day, monologue, tape): the core form of tools/schema.md",
              "document": "a document, a document set or a web text: the core form of tools/schema.md",
              "text": "a single-voice text (a post, an essay): the core form of tools/schema.md"}
CORE = not FORMS
if CORE: FORMS = {k: {"primary": None, "pool": [], "sections": {}, "about": v} for k, v in CORE_FORMS.items()}
OBJ = packload.objects()   # the object register's criteria column header and vocabulary line (phase 4 handoff 1)
# the two schema sections whose heading is the pack's (pack.toml [audit] heading, [objects] watch_heading): the skeleton writes the
# pack's heading and --check accepts it; the keys below stay the schema's names
_P = packload.pack()
SHOW = {"Forthrightness audit": (_P.get("audit", {}).get("heading") or "## Forthrightness audit")[3:].strip(),
        WATCH: (_P.get("objects", {}).get("watch_heading") or "## " + WATCH)[3:].strip()}
ALL_EXEMPLARS = sorted({p for f in FORMS.values() for p in [f["primary"], *f["pool"], *[s for s in f["sections"].values() if s]] if p})

# Which rows to lift as examples, per table: lists of (marker, cell index or None) that a row must carry, in priority order.
# The first two distinct hits win; the shortest matching row is taken so the skeleton stays small.
PRIORITY = {  # (high, low): the high markers are sought tier by tier before any low one is used
    "Claims ledger": ([[("(program record)", None), ("attribution:", 7)], [("[first telling:", 7)], [("document claimed, not named", 7)],
                       [("(pseudonym)", 7)], [("[div:", 7)], [("corroboration 2:", 7)]], []),
    "Forthrightness audit": ([[("redacted", 6)], [("pseudo-decline", 7)]], [[("closed-outright", 5)], [("stated decline", 7)]]),
    "Dated timeline": ([[("[div:", 7), ("contradicts", 7)], [("[first telling:", None)]], [[("matches", 7)]]),
    "Cross-checks": ([[("[div:", 5), ("point:", 5)]], [[("answers", 1)], [("extends", 1)], [("custody:", 5)]]),
    "Open questions": ([[("checked", 6)]], [[("open", 6)]]),
    WATCH: ([[("candidate", 6)]], [[("nil", 5)]]),
    "What this contests": ([[("[div:", None)]], []),
}
MIN_LEN = 120

# ---------------------------------------------------------------- parsing helpers (the same reading as tools/build_db.py)
cells = LN.cells                # form F1
is_sep = LN.is_sep              # form F3
headings = LN.headings          # form S3: [(level, text, line index)] for every # heading
section_span = LN.section_span  # form S3: (start, end) of the first heading with this exact text

def read(path):
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    return LN.read_lines(LP.resolve_arg(p))

def tables(lines, start, end):
    """[(header line index, header cells, [row lines])] for every table in lines[start:end] (form T1b)."""
    return [(t.header_line, t.header, [lines[j] for j in t.row_lines]) for t in LN.tables(lines, start, end)]

# ---------------------------------------------------------------- the schema
LEGACY_HEADING = {"Candour audit": "Forthrightness audit"}   # schema name -> the heading the notes carry (2026-10-22)

def parse_schema():
    lines = read(SCHEMA)
    s = {"version": "", "sections": [], "headers": {}, "meta_keys": [], "lines": {}, "optional": set(), "order": []}
    m = re.search(r"\(v([\d.]+), ", lines[0]); s["version"] = m.group(1) if m else "?"
    cur = None
    for i, l in enumerate(lines):
        m = re.match(r"^## (\d+)\. (?:`## (.+?)`|(.+?))\s*(\(optional.*)?$", l)
        if m:
            num = int(m.group(1)); head = m.group(2); cur = (num, head)
            if head:
                s["sections"].append((num, head))
                if m.group(4): s["optional"].add(head)
            continue
        if cur is None: continue
        num, head = cur
        if num == 1:
            c = cells(l)
            if c and len(c) == 2 and c[0] not in ("Key", "") and not is_sep(l): s["meta_keys"].append(c[0])
        elif head:
            m2 = re.match(r"^`(\| .+ \|)`\s*$", l)
            if m2 and head not in s["headers"]: s["headers"][head] = cells(m2.group(1))
            m3 = re.match(r"^`((Audit counts|[A-Z][a-z]+ vocabulary): .+)`\s*$", l)
            if m3: s["lines"][head] = m3.group(1)
    # Placement: schema section 11 says the timeline is "placed before `## Open questions`"; assert the rule is still there.
    txt = "\n".join(lines)
    assert "placed before `## Open questions`" in txt, "schema placement rule for the Dated timeline not found; update note_skeleton.py"
    # The candour audit (schema section 3, renamed 2026-10-22) is emitted and checked under the notes' legacy heading until the
    # owner-approved corpus pass renames the sections; the exemplars carry the legacy heading, so the key stays "Forthrightness audit".
    s["sections"] = [(n, LEGACY_HEADING.get(h, h)) for n, h in s["sections"]]
    for k in ("headers", "lines"): s[k] = {LEGACY_HEADING.get(h, h): v for h, v in s[k].items()}
    s["optional"] = {LEGACY_HEADING.get(h, h) for h in s["optional"]}
    # the object register's criteria column is the pack's (phase 4 handoff 1): schema.md may write it `<reference object> criteria met`
    s["headers"] = {h: [OBJ["criteria_column"] if c.endswith("criteria met") else c for c in hdr] for h, hdr in s["headers"].items()}
    # and so is the vocabulary line that follows that table (`<label>: <word> N, ...`; schema section 6 describes it, the pack gives it)
    if OBJ["vocabulary"]:
        for h, hdr in s["headers"].items():
            if OBJ["criteria_column"] in hdr: s["lines"][h] = f"{OBJ['vocabulary_line']}: " + ", ".join(f"{w} N" for w in OBJ["vocabulary"]) + "."
    order = [h for _, h in s["sections"]]
    order.remove("Dated timeline"); order.insert(order.index("Open questions"), "Dated timeline")
    s["order"] = order
    for h in ("Claims ledger", "Forthrightness audit", "People", "Works", WATCH, "Notable quotes", "Open questions", "Cross-checks", "Dated timeline"):
        assert h in order, f"schema section {h!r} not parsed from tools/schema.md"
    return s

def line_regex(form_line):
    """`Audit counts: open N, partial N, ...` -> a regex with \\d+ for each N."""
    return "^" + re.escape(form_line).replace(re.escape("N"), r"\d+") + r"(?:\s*\(.*)?$"

# ---------------------------------------------------------------- exemplar reading
class Exemplar:
    def __init__(self, path):
        self.path = path; self.lines = read(path); self.heads = headings(self.lines)
    def span(self, heading, level=2): return section_span(self.lines, heading, level)
    def sub_headings(self, heading):
        sp = self.span(heading)
        if not sp: return []
        return [(t, i) for lv, t, i in self.heads if lv == 3 and sp[0] < i < sp[1]]
    def first_table(self, heading):
        sp = self.span(heading)
        if not sp: return None
        t = tables(self.lines, sp[0], sp[1])
        return t[0] if t else None
    def all_tables(self, heading):
        sp = self.span(heading)
        return tables(self.lines, sp[0], sp[1]) if sp else []
    def quote_items(self):
        sp = self.span("Notable quotes")
        if not sp: return []
        return [l for l in self.lines[sp[0]:sp[1]] if LN.QUOTE_ITEM_RE.match(l)]
    def meta(self):
        return [(k, v) for k, v, _ in LN.meta_rows(self.lines, 80)]   # form M1

_cache = {}
def ex(path):
    if path not in _cache: _cache[path] = Exemplar(path)
    return _cache[path]

def row_matches(row_line, conds):
    c = cells(row_line) or []
    for marker, idx in conds:
        hay = row_line if idx is None else (c[idx] if idx < len(c) else "")
        if marker not in hay: return False
    return True

def pick_examples(heading, header_cells, tiers):
    """Two example rows for the table under `heading`, from tables whose header equals header_cells: the form's own
    exemplars first (tier 1), then every exemplar (tier 2); within a tier by PRIORITY, then the shortest row over MIN_LEN."""
    def candidates(paths):
        out = []
        for p in paths:
            e = ex(p)
            for hi, hc, rows in e.all_tables(heading):
                if hc != header_cells: continue
                for k, r in enumerate(rows):
                    if MARK not in r: out.append((p, hi + 2 + k, r))
        return out
    chosen = []
    def take(pool):
        pool = [c for c in pool if c[2] not in [x[2] for x in chosen]]
        if not pool: return
        long_enough = [c for c in pool if len(c[2]) >= MIN_LEN] or pool
        chosen.append(min(long_enough, key=lambda c: len(c[2])))
    tier_cands = [candidates(t) for t in tiers]
    high, low = PRIORITY.get(heading, ([], []))
    used = set()  # each priority contributes at most one row, so a later tier adds a marker the earlier tiers lacked
    def sweep(conds_list, cands):
        for k, conds in enumerate(conds_list):
            if len(chosen) >= 2: break
            if (conds_list is high, k) in used: continue
            n = len(chosen); take([c for c in cands if row_matches(c[2], conds)])
            if len(chosen) > n: used.add((conds_list is high, k))
    sweep(high, tier_cands[0])  # tier 1: the section's own exemplars
    if not chosen: take(tier_cands[0])  # at least one row in the form's own style (its Time cells, its voices)
    for cands in tier_cands[1:]: sweep(high, cands)  # the marked rows the form's exemplars lack (a redaction wall, a first-telling tag)
    for cands in tier_cands: sweep(low, cands)
    for cands in tier_cands:
        while len(chosen) < 2 and any(c[2] not in [x[2] for x in chosen] for c in cands): take(cands)
    return chosen

def mark(row):
    """Append the marker inside the last cell, so an undeleted example still parses as one row and --check can find it."""
    s = row.rstrip()
    return s[:-1].rstrip() + " " + MARK + " |" if s.endswith("|") else s + " " + MARK

# ---------------------------------------------------------------- the form's heading order
def form_order(form, schema):
    cfg = FORMS[form]; prim = ex(cfg["primary"])
    wanted = {}  # heading -> supplier path
    for h in cfg["sections"]:
        sup = cfg["sections"][h] or cfg["primary"]
        if not ex(sup).span(h): sys.exit(f"error: form {form}: heading '## {h}' not found in {sup}; the exemplar changed, update FORMS")
        wanted[h] = sup
    for h in schema["order"]:
        if prim.span(h): wanted[h] = cfg["primary"]
        elif h in schema["optional"]: continue
        else:
            sup = next((p for p in cfg["pool"] if ex(p).span(h)), None)
            if not sup: sys.exit(f"error: schema section '## {h}' is in no exemplar of form {form}")
            wanted[h] = sup
    order = [t for lv, t, i in prim.heads if lv == 2 and t in wanted]
    for h, sup in wanted.items():
        if h in order: continue
        seq = [t for lv, t, i in ex(sup).heads if lv == 2]
        before = [t for t in seq[:seq.index(h)] if t in order]
        pos = order.index(before[-1]) + 1 if before else 0
        order.insert(pos, h)
    return order, wanted

# ---------------------------------------------------------------- derivable metadata
def transcript_meta(path):
    """Channel, URL, Uploaded, Length (Hh Mm Ss), title, words and the description's first paragraph from a transcripts/<id>.md header."""
    lines = read(path); m = {}
    t = re.match(r"^# Transcript: (.+)", lines[0]); m["title"] = t.group(1).strip() if t else ""
    for l in lines[:12]:
        mm = re.match(r"^- (Channel|URL|Uploaded|Captions|Source|Length): (.+)", l)
        if mm: m[mm.group(1).lower()] = mm.group(2).strip()
    L = m.get("length", "")
    mm = re.search(r"(\d+):(\d\d):(\d\d)", L)
    if mm: h, mi, s = (int(x) for x in mm.groups()); m["length_hms"] = f"{h}h {mi}m {s}s"
    else:
        mm = re.search(r"(?:(\d+)h )?(\d+)m(?: (\d+)s)?", L)
        if mm: h, mi, s = mm.groups(); m["length_hms"] = f"{int(h or 0)}h {int(mi)}m" + (f" {int(s)}s" if s else "")
    mw = re.search(r"~?([\d,]+) words", L); m["words"] = mw.group(1) if mw else ""
    desc = None
    for i, l in enumerate(lines):
        if l.startswith("## Video description"):
            paras = [p for p in "\n".join(lines[i + 1:]).split("\n\n") if p.strip()]
            desc = " ".join(re.sub(r"^>\s?", "", x).strip() for x in paras[0].split("\n")).strip() if paras else ""
            break
    m["description"] = desc
    return m

def pdf_pages(path):
    try:
        out = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", "-raw", path], capture_output=True, text=True, timeout=20).stdout.strip()
        if out.isdigit(): return int(out), "mdls"
    except Exception: pass
    try:
        with open(path, "rb") as f: data = f.read()
        n = len(re.findall(rb"/Type\s*/Page(?![s/])", data))
        if n: return n, "regex over the PDF objects, approximate"
    except Exception: pass
    return None, "not readable"

def held_files(sources):
    files = []
    for s in sources:
        p = LP.resolve_arg(s if os.path.isabs(s) else os.path.join(ROOT, s))
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for n in sorted(names): files.append(os.path.join(root, n))
        elif os.path.exists(p): files.append(p)
        else: sys.exit(f"error: --source {s} does not exist")
    return files

def document_length(files):
    texts = [f for f in files if f.lower().endswith((".txt", ".md", ".htm", ".html"))]
    pdfs = [f for f in files if f.lower().endswith(".pdf")]
    wparts = []; wtotal = 0
    for f in texts:
        n = len(LN.read_text(f, errors="replace").split())
        wtotal += n; wparts.append(f"{os.path.basename(f)} {n:,}")
    pparts = []; ptotal = 0; how = set()
    for f in pdfs:
        n, h = pdf_pages(f); how.add(h)
        if n: ptotal += n; pparts.append(f"{os.path.basename(f)} {n} pp")
        else: pparts.append(f"{os.path.basename(f)} pages {h}")
    out = []
    if pdfs: out.append(f"{ptotal:,} pages across {len(pdfs)} PDF{'s' if len(pdfs) != 1 else ''} ({'; '.join(pparts)}; counted by {', '.join(sorted(how))})")
    else: out.append("<pages: no PDF held; give the printed page count or say none>")
    if texts: out.append(f"{wtotal:,} words in the held text file{'s' if len(texts) != 1 else ''} ({'; '.join(wparts)}; whitespace count, headers and OCR noise included)")
    else: out.append("<words: no text file held>")
    return "; ".join(out)

def rel_link(target, note_path):
    base = os.path.dirname(os.path.join(ROOT, note_path)) if note_path else os.path.join(ROOT, "books")
    return os.path.relpath(target, base)

# ---------------------------------------------------------------- the skeleton
def metadata_rows(form, schema, args, files):
    today = datetime.date.today().isoformat()
    desc = {}  # the schema's own one-line descriptions of each key, as placeholders
    for l in read(SCHEMA)[:40]:
        c = cells(l)
        if c and len(c) == 2 and c[0] in schema["meta_keys"]: desc[c[0]] = c[1]
    v = {k: f"<{desc.get(k, k)}>" for k in schema["meta_keys"]}
    v["Added to notes"] = today
    notes = []
    if form == "video":
        if not args.source: notes.append("no --source transcript given: Channel, URL, Uploaded, Length and Description left as placeholders")
        else:
            tm = transcript_meta(args.source[0])
            v["Channel"] = tm.get("channel") or v["Channel"]; v["URL"] = tm.get("url") or v["URL"]
            v["Uploaded"] = tm.get("uploaded") or v["Uploaded"]
            v["Length"] = tm.get("length_hms", v["Length"]) + (f" <!-- from the transcript header: {tm.get('length', '')} -->" if tm.get("length_hms") else "")
            v["Transcript"] = f"[Full transcript]({rel_link(os.path.join(ROOT, args.source[0]) if not os.path.isabs(args.source[0]) else args.source[0], args.note)})"
            if tm.get("description") is None: v["Description"] = "<the transcript has no `## Video description` block: say so (run tools/fetch_description.py)>"
            elif tm["description"]: v["Description"] = f"\"{tm['description']}\" <!-- the description's first paragraph as held; check it is the first substantive one and say if sponsor, merch or link boilerplate was skipped -->"
            v["Host"] = "<host name, or `none`; a monologue's narrator; a hearing's chair>"; v["Guest"] = "<guest name(s); `none` for a monologue; a hearing's witnesses>"
            v["Speakers"] = "<every voice on the recording, comma separated>"
            if tm.get("source"): notes.append(f"transcript header says: Source: {tm['source']}")
            if tm.get("title"): notes.append(f"transcript title: {tm['title']}")
        keys = schema["meta_keys"]
    else:
        conv = {  # the document conventions of brief-document.md ("Metadata for documents") and the exemplars' Authors key
            "Channel": "<the issuing body or publisher>", "Host": "none (<the issuing office or author>)",
            "Guest": "none (<the documents listed: kinds and count>)", "Speakers": "<every office, author and quoted person who speaks in the document>",
            "URL": "<the original>", "Uploaded": "<the release or publication date, YYYY-MM-DD>",
            "Recorded": "<the documents' own dates, YYYY-MM-DD or a range [with the evidence]>",
            "Description": "<the document's own opening or cover words, quoted; `none:` and why if it has none>",
        }
        if form == "adverse-forum":
            conv["Guest"] = "none (<the thread: posts, pages, dates; and any documents cited and held>)"
            conv["Speakers"] = "<the posters by handle (pseudonymous; which state firsthand knowledge), then quoted or cited parties>"
        if form == "text":
            conv["Host"] = "<the author (the single voice; pseudonymous?)>"; conv["Guest"] = "none (a document: <kind, words, links>)"
        v.update(conv)
        if files:
            v["Length"] = document_length(files)
            texts = [f for f in files if not f.lower().endswith(".pdf")]; pdfs = [f for f in files if f.lower().endswith(".pdf")]
            links = ", ".join(f"[{os.path.basename(f)}]({rel_link(f, args.note)})" for f in texts)
            if pdfs: links += " (and the scan" + ("s" if len(pdfs) > 1 else "") + " " + ", ".join(f"[{os.path.basename(f)}]({rel_link(f, args.note)})" for f in pdfs) + ")"
            v["Transcript"] = f"Held copies: {links}"
        else:
            notes.append("no --source given: Length and Transcript left as placeholders")
            v["Length"] = "<pages and words, computed from the held files>"; v["Transcript"] = "<the held copy's path under books/sources/ (and the pdf beside it)>"
        keys = schema["meta_keys"] + ["Authors"]
        v["Authors"] = "<the author(s) as printed, pseudonymity, what the text says of them>"
    rows = ["| | |", "|---|---|"] + [f"| **{k}** | {v[k]} |" for k in keys]
    return rows, notes

def build_core(form, args):
    """The core default form: tools/schema.md alone (no exemplar notes)."""
    schema = parse_schema(); lines = read(SCHEMA)
    files = held_files(args.source) if args.source else []
    secnum = {h: n for n, h in schema["sections"]}
    span = {}   # schema section heading -> (first, last) line index of its schema text, for the citation
    heads = [(i, re.match(r"^## (\d+)\. ", l)) for i, l in enumerate(lines)]
    starts = [(i, int(m.group(1))) for i, m in heads if m]
    for k, (i, n) in enumerate(starts):
        for num, h in schema["sections"]:
            if num == n: span[h] = (i + 1, (starts[k + 1][0] if k + 1 < len(starts) else len(lines)))
    out = [f"# <title: {('speaker, \"title\" | channel' if form == 'video' else 'author or issuer, \"title\" (venue, year)')}>", "",
           f"<!-- skeleton: core form {form}, {FORMS[form]['about']}; schema v{schema['version']}; generated {datetime.date.today().isoformat()} by tools/note_skeleton.py",
           f"     for {args.note or '<planned note path>'}. The pack names no note forms (pack.toml [skeleton] forms), so this skeleton is built from",
           "     tools/schema.md alone: every schema section in order, its table header and count line; there are no example rows. Each section's",
           "     comment names the schema lines that define it. Free sections (schema section 12: summary, key claims, thematic sections,",
           "     connections) are prose and go where the brief places them. Keep every heading and header row. -->", ""]
    meta, notes = metadata_rows(form, schema, args, files)
    out += meta + ["", "> Note: <what this is an intake of, in which form; the status line while in progress: Status: in progress>", ""]
    for n in notes: out.append(f"<!-- {n} -->")
    if notes: out.append("")
    for h in schema["order"]:
        out.append(f"## {SHOW.get(h, h)}")
        a, b = span.get(h, (0, 0))
        out.append(f"<!-- tools/schema.md section {secnum.get(h, '?')} (lines {a} to {b})" + ("; optional: omit the section when it has no rows" if h in schema["optional"] else "") + " -->")
        out.append("")
        if h in schema["headers"]:
            hc = schema["headers"][h]
            out += ["| " + " | ".join(hc) + " |", "|" + "---|" * len(hc), ""]
        if h == "Notable quotes": out += ["<!-- a list, one item per quote, in the form tools/schema.md section 7 gives -->", ""]
        if h in schema["lines"]:
            out.append(schema["lines"][h] + ("  <!-- generated by tools/note_fill.py from the table; then one explanatory line, then the prose subsections -->" if h == "Forthrightness audit" else "  <!-- whole-word counts over the whole held text -->"))
            out.append("")
        if h == "Forthrightness audit":
            out += ["<!-- the prose subsections (schema section 3): lettering and headings are free-form but must cover public-record checks, confidence labelling, internal tensions, what is withheld, the host's or author's moves, and what the pack's channelled-class clause adds -->", ""]
        if h == "Open questions": out += ["<!-- a note with no questions keeps the empty table and the line: This note recorded no open questions. -->", ""]
        if h == "Cross-checks": out += ["<!-- filled last, from tools/onboard_check.py; a note with none keeps the empty table and the line: This note's onboarding check found no cross-checks. -->", ""]
    return "\n".join(out).rstrip() + "\n"

def build_skeleton(form, args):
    if CORE: return build_core(form, args)
    schema = parse_schema(); cfg = FORMS[form]
    order, supplier = form_order(form, schema)
    files = held_files(args.source) if args.source else []
    own_all = [cfg["primary"]] + [s for s in dict.fromkeys(supplier.values()) if s != cfg["primary"]]  # the form's exemplars
    srcs = own_all + [p for p in cfg["pool"] if p not in own_all]  # plus its pool
    srcs_all = srcs + [p for p in ALL_EXEMPLARS if p not in srcs]  # then every exemplar
    out = []
    out.append(f"# <title as the exemplar gives it: {('speaker, \"title\" | channel' if form == 'video' else 'author or issuer, \"title\" (venue, year)')}>")
    out.append("")
    out.append(f"<!-- skeleton: form {form}, {cfg['about']}; schema v{schema['version']}; generated {datetime.date.today().isoformat()} by tools/note_skeleton.py")
    out.append(f"     for {args.note or '<planned note path>'}; heading order from {cfg['primary']}; every heading, table header and example row below is lifted from an exemplar.")
    out.append(f"     Delete every line carrying `{MARK}` (or the `<!-- example ... -->` mark on a heading or item); keep every heading and header row.")
    out.append("     Each section's comment names the exemplar lines that carry that section in full: read them with `sed -n 'a,bp' <exemplar>` only where the form is unclear.")
    out.append("     Schema prose rules are not repeated here: tools/schema.md section N is cited at each schema section. -->")
    out.append("")
    meta, notes = metadata_rows(form, schema, args, files)
    out += meta
    out.append("")
    out.append("> Note: <the exemplar's standing note: what this is an intake of, in which form, after which exemplars; the status line while in progress: Status: in progress>")
    out.append("")
    for n in notes: out.append(f"<!-- {n} -->")
    if notes: out.append("")
    secnum = {h: n for n, h in schema["sections"]}
    for h in order:
        sup = supplier[h]; e = ex(sup); sp = e.span(h)
        out.append(f"## {h}")
        cite = f"tools/schema.md section {secnum[h]}; " if h in secnum else "form section; "
        out.append(f"<!-- {cite}form as in {sup} lines {sp[0] + 1} to {sp[1]} -->")
        out.append("")
        tbls = e.all_tables(h)
        is_schema = h in schema["headers"]
        if is_schema:
            # the schema's header is the authority; the exemplar's first table must agree (else the exemplar drifted)
            hdr = schema["headers"][h]
            if not tbls or tbls[0][1] != hdr:
                sys.exit(f"error: {sup} '## {h}' first table header differs from the schema: {tbls[0][1] if tbls else None} vs {hdr}")
            tbls = [tbls[0]]
        elif h in ("Notable quotes", "The documents, one by one"):
            tbls = []  # quotes are a list; the per-document section carries only its own tables, not lifted
        else:
            tbls = tbls[:1]  # a form section's first table is its form; later tables are the exemplar's own
        for hi, hc, rows in tbls:
            out.append("| " + " | ".join(hc) + " |")
            out.append("|" + "---|" * len(hc))
            own = list(dict.fromkeys([cfg["primary"], sup]))  # this section's own exemplars first
            exs = pick_examples(h, hc, [own, srcs, srcs_all])
            for p, li, r in exs: out.append(mark(r))
            out.append("")
        if h == "Notable quotes":
            for q in e.quote_items()[:2]: out.append(q.rstrip() + " " + MARK.replace("row", "item"))
            out.append("")
        if h in schema["lines"]:
            out.append(schema["lines"][h] + ("  <!-- numbers only; then one explanatory line (the mapping used), then the prose subsections -->" if h == "Forthrightness audit" else "  <!-- whole-word counts over the whole held text; a parenthetical on false positives is mandatory when any count includes one -->"))
            out.append("")
        subs = e.sub_headings(h)
        if h == "Forthrightness audit":
            if not subs:
                alt = next((p for p in srcs if ex(p).sub_headings(h)), None)
                if alt: subs = ex(alt).sub_headings(h); sup_subs = alt
            else: sup_subs = sup
            if subs: out.append(f"<!-- the prose subsections, as in {sup_subs}: lettering and headings are free-form (schema section 3) but must cover public-record checks, confidence labelling, internal tensions, what is withheld, the author's or host's moves, who supplies the frame -->"); out.append("")
            for t, i in subs: out.append(f"### {t}"); out.append("")
        elif h == "The documents, one by one" and subs:
            out.append(f"### {subs[0][0]}  <!-- example heading, replace; one `### N. <title, date> (<identifier>)` per document, as {sup} -->"); out.append("")
        if h == "Open questions": out.append("<!-- a note with no questions keeps the empty table and the line: This note recorded no open questions. -->"); out.append("")
        if h == "Cross-checks": out.append("<!-- filled last, from tools/onboard_check.py; a note with none keeps the empty table and the line: This note's onboarding check found no cross-checks. -->"); out.append("")
    return "\n".join(out).rstrip() + "\n"

# ---------------------------------------------------------------- --check
def detect_form(path, lines):
    hs = {t for lv, t, i in headings(lines) if lv == 2}
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    if rel.startswith("videos/"): return "video"
    if "How the post is built" in hs: return "text"
    if "What this contests" in hs:
        meta = dict(Exemplar(path).meta())
        blob = (meta.get("Guest", "") + meta.get("Channel", "")).lower()
        return "adverse-forum" if ("thread" in blob or " posts" in blob) else "adverse-web"
    return "document"

def check(path, form=None):
    schema = parse_schema(); lines = read(path); e = Exemplar(path); fails = []; warns = []; rep = []
    given = form is not None
    form = form or detect_form(path, lines)
    if form not in FORMS: form = "document"   # the core forms have no adverse variants
    rep.append(f"{os.path.relpath(os.path.abspath(path) if not os.path.isabs(path) else path, ROOT)}: form {form} ({'given' if given else 'detected'}); schema v{schema['version']}")
    # metadata
    meta = [k for k, v in e.meta()]
    want = schema["meta_keys"]; allowed_missing = {"Host", "Guest", "Recorded", "Description"}
    missing = [k for k in want if k not in meta]
    bad_missing = [k for k in missing if k not in allowed_missing]
    present = [k for k in meta if k in want]
    in_order = present == [k for k in want if k in present]
    trailing = meta[meta.index("Transcript") + 1:] if "Transcript" in meta else []
    stray = [k for k in meta if k not in want and k not in trailing]
    line = f"metadata: {len(present)} of {len(want)} schema keys"
    if bad_missing: fails.append(f"metadata keys missing: {', '.join(bad_missing)}")
    if missing and not bad_missing: line += f" (missing, allowed: {', '.join(missing)})"
    if not in_order: fails.append(f"metadata keys out of schema order: {present}")
    if stray: fails.append(f"metadata keys not in the schema before Transcript: {', '.join(stray)}")
    if trailing: line += f"; trailing: {', '.join(trailing)}" + ("" if len(trailing) <= 1 else " (schema allows one; Status: in progress is the usual second)")
    rep.append(line + ("; order ok" if in_order else ""))
    # schema sections, by the parser's reading (first heading starting with the text) and by exact text
    found = {}
    for h in schema["order"]:
        names = {h, SHOW.get(h, h)} | {k for k, v in LEGACY_HEADING.items() if v == h}   # a note may carry the schema's name, the pack's heading or the legacy heading
        exact = next((i for lv, t, i in e.heads if lv == 2 and t in names), None)
        prefix = min((i for i in (LN.section_start(lines, "## " + n) for n in names) if i is not None), default=None)   # form S1
        if exact is not None: found[h] = exact
        elif prefix is not None:
            found[h] = prefix; warns.append(f"'## {h}' only by prefix at line {prefix + 1}: {lines[prefix].strip()!r}")
    miss = [h for h in schema["order"] if h not in found and h not in schema["optional"]]
    if miss: fails.append(f"schema sections missing: {', '.join(miss)}")
    seq = [h for h in schema["order"] if h in found]
    pos = [found[h] for h in seq]
    # longest increasing subsequence of positions: the sections outside it are the misordered ones
    best = []; prev = [-1] * len(pos); lis_end = -1
    dp = [1] * len(pos)
    for i in range(len(pos)):
        for j in range(i):
            if pos[j] < pos[i] and dp[j] + 1 > dp[i]: dp[i] = dp[j] + 1; prev[i] = j
    if pos:
        lis_end = max(range(len(pos)), key=lambda i: dp[i]); k = lis_end
        while k != -1: best.append(k); k = prev[k]
    misordered = [seq[i] for i in range(len(seq)) if i not in best]
    if misordered: fails.append(f"schema sections out of order: {', '.join(f'{h} (line {found[h] + 1})' for h in misordered)}; expected order {' > '.join(schema['order'])}")
    rep.append(f"schema sections: {len(found)} of {len(schema['order'])} present" + (f" ({', '.join(h for h in schema['optional'] if h not in found)} optional, absent)" if any(h not in found for h in schema['optional']) else "") + ("; order ok" if not misordered else ""))
    # table headers
    for h, hdr in schema["headers"].items():
        if h not in found: continue
        sp = section_span(lines, lines[found[h]][3:].strip())
        tb = tables(lines, sp[0], sp[1]) if sp else []
        if not tb: fails.append(f"'## {h}': no table"); continue
        got = tb[0][1]
        if got != hdr:
            fails.append(f"'## {h}' table header differs from the schema at line {tb[0][0] + 1}: got {' | '.join(got)!r}, schema {' | '.join(hdr)!r}")
        if h in ("Open questions", "Cross-checks") and not tb[0][2]:
            txt = "\n".join(lines[sp[0]:sp[1]])
            need = "This note recorded no open questions." if h == "Open questions" else "This note's onboarding check found no cross-checks."
            if need not in txt: warns.append(f"'## {h}': empty table without the line {need!r}")
    rep.append("table headers: " + ("ok" if not any("table header" in f or "no table" in f for f in fails) else "see failures"))
    # the count lines
    for h, fl in schema["lines"].items():
        if h not in found: continue
        sp = section_span(lines, lines[found[h]][3:].strip()); rx = re.compile(line_regex(fl))
        if not any(rx.match(l.strip()) for l in lines[sp[0]:sp[1]]): fails.append(f"'## {h}': no line in the form `{fl}`")
    rep.append("count lines: " + ("ok" if not any("no line in the form" in f for f in fails) else "see failures"))
    # the form's own sections
    cfg = FORMS[form]; fs = [h for h in cfg["sections"] if h != "One-paragraph summary"]
    have = {t for lv, t, i in e.heads if lv == 2}
    fmiss = [h for h in fs if not any(t == h or t.startswith(h) for t in have)]
    rep.append(f"form sections ({form}): {len(fs) - len(fmiss)} of {len(fs)} present" + (f"; absent: {', '.join(fmiss)}" if fmiss else ""))
    if fmiss and given: fails.append(f"form sections absent: {', '.join(fmiss)}")
    # leftovers
    left = [i + 1 for i, l in enumerate(lines) if "<!-- example" in l]
    if left: fails.append(f"example rows or marks left from the skeleton at lines {left[:10]}{'...' if len(left) > 10 else ''}")
    status = [k for k, v in e.meta() if k == "Status"]
    if status: warns.append("metadata carries a Status key (in progress?)")
    for w in warns: rep.append("warn: " + w)
    for f in fails: rep.append("FAIL: " + f)
    rep.append("RESULT: " + ("PASS" if not fails else "FAIL"))
    return "\n".join(rep), not fails

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--form", choices=sorted(FORMS))
    ap.add_argument("--task", help="the agent's wip folder; skeleton.md is written there")
    ap.add_argument("--note", help="the planned note path (books/<stem>.md or videos/<stem>.md); sets the link base")
    ap.add_argument("--source", action="append", help="a held file or folder (document forms) or the transcript (video); repeatable")
    ap.add_argument("--stdout", action="store_true", help="print the skeleton instead of writing it")
    ap.add_argument("--check", metavar="NOTE", help="check a finished note against the schema and the form")
    ap.add_argument("--sizes", action="store_true", help="print the size of every form's skeleton (no sources)")
    a = ap.parse_args()
    if a.check:
        rep, ok = check(a.check, a.form); print(rep); sys.exit(0 if ok else 1)
    if a.sizes:
        class A: note = None; source = None
        for f in sorted(FORMS):
            s = build_skeleton(f, A()); print(f"{f:14s} {len(s.encode()):7,} bytes {len(s.split()):6,} words {s.count(chr(10)):4d} lines (about {len(s) // 4:,} tokens)")
        return
    if not a.form: ap.error("--form is required (or --check / --sizes)")
    if not a.task and not a.stdout: ap.error("--task <wip folder> is required (or --stdout)")
    s = build_skeleton(a.form, a)
    if a.stdout: sys.stdout.write(s); return
    task = a.task if os.path.isabs(a.task) else os.path.join(ROOT, a.task)
    os.makedirs(task, exist_ok=True)
    dest = os.path.join(task, "skeleton.md")
    LN.write_text(dest, s)
    print(f"wrote {os.path.relpath(dest, ROOT) if dest.startswith(ROOT) else dest}: {len(s.encode()):,} bytes, {len(s.split()):,} words, {s.count(chr(10))} lines (about {len(s) // 4:,} tokens); form {a.form}")

if __name__ == "__main__":
    main()
