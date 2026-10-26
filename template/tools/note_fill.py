#!/usr/bin/env python3
"""Generate the mechanical parts of a note in the house schema (tools/schema.md v1.3) from the held files, the README
beside them, the note's own tables and the onboarding report, so that no agent types them by hand (owner, 2026-10-15).

Fill mode (writes the note in place; prints what it wrote, kept and found different):
  python3 tools/note_fill.py --note <books/<note>.md or wip/<task>/skeleton.md> --sources <held dir or files ...>
          [--readme README.md] [--onboard wip/<task>/onboard.md] [--accept wip/<task>/xc-accept.md]
          [--dest-dir books] [--inventory-under "<heading>"] [--force] [--reset-xc] [--dry-run]
Check mode (writes nothing; exit 1 when anything differs):
  python3 tools/note_fill.py --check <note> [--sources ...] [--readme ...] [--report wip/<task>/report.json]

What it generates
  (a) Metadata block, derivable keys only: Length (pages by pypdf over the PDFs, words by whitespace split over the
      .txt/.md text layers), Transcript (links to the held files), Added to notes (today unless set), URL and
      Uploaded / Recorded when the README beside the sources carries them in its table (ID / Title / Date / Pages /
      Size / URL columns as books/sources/web/*/README.md use them). Judgement keys (Channel, Host, Guest, Speakers,
      Subjects, Description, Tags, Authors) are never touched when filled and are marked `<!-- fill -->` when empty.
      A derivable key already filled by hand is kept and compared; --force overwrites it with the generated value.
  (b) Document inventory: one row per held document (a .pdf and the .txt or .md of the same stem form one document)
      with the files, pages, words, bytes, document date and URL, between `<!-- inventory:start -->` and
      `<!-- inventory:end -->` under `## The documents, one by one` (else `## How the set is built`, else the heading
      given by --inventory-under). Re-running replaces only that block; the hand-written table of the section stays.
  (c) Audit counts line (schema section 3, exact form) computed from the note's own candour audit table (schema section 3; heading
      `## Candour audit`, or the legacy `## Forthrightness audit` the notes carry), between
      `<!-- audit-counts:start -->` / `<!-- audit-counts:end -->`; a hand-typed line that disagrees is reported, and
      replaced only with --force. Counting rules: the four move counts come from the Move cell (compound moves take
      the first class named; `n/a` rows are not counted); stated declines are the rows whose Basis names something
      (not `n/a`, `none stated`, `not known ...`, blank, `redacted: ...` or a sanitisation at release; a redaction is a
      wall, counted separately and reported, never a stated decline) and that refuse: Move closed-outright, or a Note that
      says decline, or a Basis naming a ground of the pack's basis vocabulary (a monologue's sourcing is never a ground); pseudo-declines are the rows whose Note says `pseudo-decline`. The
      basis histogram, the walls and the n/a rows are printed so the explanatory line can be written from them.
  (d) Cross-check candidate rows from <wip>/onboard.md (tools/onboard_check.py's report) in the schema's section 10
      table shape, between `<!-- cross-checks:start -->` / `<!-- cross-checks:end -->` under `## Cross-checks`: the
      This note, Elsewhere and custody cells are generated; Kind and Verdict are `<!-- fill -->` unless an --accept
      file supplies them (one candidate per line: `B12.2 corroborates partial | point: date; ...`; with --accept only
      the listed candidates are written). The block holds the section's single table (tools/build_db.py reads the
      first schema-shaped table under the heading): hand-written rows already in the section are moved into the
      block unchanged and keep their numbers; rows inside the block are never edited or deleted by a re-run, which
      appends only candidates not yet present (by their Elsewhere target) when the onboard report has changed;
      --reset-xc drops the generated rows that are still wholly unfilled and regenerates them.

Check mode recomputes (a) to (c) and reports every difference between the generated values and what the note says
(Length against the files, inventory and the hand table against the files, audit counts against the audit table,
`<!-- fill -->` markers left anywhere), and with --report compares claims_rows, timeline_rows and audit_counts in
report.json with the note. Run it before tools/report_check.py.
"""
import argparse, datetime, hashlib, os, re, sys, json
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # project paths and the sources/ alias table

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
TODAY = datetime.date.today().isoformat()
FILL = "<!-- fill -->"
META_KEYS = ["Channel", "Host", "Guest", "Speakers", "URL", "Uploaded", "Recorded", "Length", "Added to notes",
             "Subjects", "Description", "Tags", "Transcript", "Authors"]
DERIVABLE = {"URL", "Uploaded", "Recorded", "Length", "Added to notes", "Transcript"}
TEXT_EXT = {".txt", ".md"}
PDF_EXT = {".pdf"}
SKIP_NAMES = {"README.md", "INDEX.md", ".DS_Store"}
ARCHIVE_EXT = (".zip", ".tar.gz", ".tgz", ".gz")
XC_HEADER = "| # | Kind | This note (time, row, claim) | Elsewhere (note, row) | Verdict | Note |"
XC_SEP = "|---|---|---|---|---|---|"
INV_HEADER = "| # | Document | Held files | Pages | Words | Bytes | Document date | URL |"
INV_SEP = "|---|---|---|---|---|---|---|---|"
MONTHS = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}

# ----------------------------------------------------------------------------------------------------- small helpers
def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)

cells = LN.cells      # form F1
is_sep = LN.is_sep    # form F3

def clip(s, n=220):
    s = re.sub(r"\s+", " ", (s or "").replace("|", "/")).strip()
    return s if len(s) <= n else s[:n - 3] + "..."

def rel_link(path, dest_dir):
    r = os.path.relpath(os.path.abspath(path), os.path.abspath(dest_dir))
    return quote(r.replace(os.sep, "/"), safe="/-_.~()")

def parse_dates(s):
    """Every date in a cell, ISO-sorted: '18 July 2008' -> '2008-07-18'; 'July 2008' -> '2008-07'; '2008' -> '2008'.
    'issued 1 September 2008, offers due 10 September, award 22 September 2008' -> the two full dates (a day with no year is skipped)."""
    if not s: return []
    s = s.strip(); out = []
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", s): out.append(m.group(0))
    for m in re.finditer(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", s):
        if m.group(2).lower() in MONTHS: out.append(f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}")
    for m in re.finditer(r"\b([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\b", s):
        if m.group(1).lower() in MONTHS: out.append(f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}")
    if not out:
        for m in re.finditer(r"\b([A-Za-z]+)\s+(\d{4})\b", s):
            if m.group(1).lower() in MONTHS: out.append(f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}")
    if not out:
        for m in re.finditer(r"\b(1[6-9]\d{2}|20\d{2})\b", s): out.append(m.group(1))
    return sorted(set(out))

def parse_date(s):
    d = parse_dates(s); return d[0] if d else None

def norm_key(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

class Report:
    def __init__(self): self.lines = []; self.diffs = 0; self.writes = 0
    def ok(self, msg): self.lines.append("OK    " + msg)
    def diff(self, msg): self.lines.append("DIFF  " + msg); self.diffs += 1
    def wrote(self, msg): self.lines.append("WROTE " + msg); self.writes += 1
    def kept(self, msg): self.lines.append("KEPT  " + msg)
    def hint(self, msg): self.lines.append("HINT  " + msg)
    def dump(self): print("\n".join(self.lines))

# -------------------------------------------------------------------------------------------------------- the sources
def pdf_pages(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, "pypdf not installed (pip install pypdf)"
    try:
        r = PdfReader(path)
        if r.is_encrypted:
            try: r.decrypt("")
            except Exception: pass
        n = len(r.pages)
        created = None
        try:
            md = r.metadata
            c = (md.get("/CreationDate") if md else None) or ""
            m = re.search(r"D:(\d{4})(\d{2})(\d{2})", str(c))
            if m: created = "-".join(m.groups())
        except Exception: pass
        return n, created
    except Exception as e:
        return None, f"pypdf failed: {e.__class__.__name__}"

def scan_sources(paths, recursive=False):
    """Every held file under the given dirs and files -> records; README/INDEX, hidden files skipped."""
    files = []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isdir(p):
            if recursive:
                for dp, dns, fns in os.walk(p):
                    dns[:] = sorted(d for d in dns if not d.startswith("."))
                    files += [os.path.join(dp, f) for f in sorted(fns)]
            else:
                files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if os.path.isfile(os.path.join(p, f))]
        elif os.path.isfile(p): files.append(p)
        else: raise SystemExit(f"--sources: {p} does not exist")
    recs = []
    for f in files:
        name = os.path.basename(f)
        if name in SKIP_NAMES or name.startswith("."): continue
        low = name.lower()
        ext = next((e for e in ARCHIVE_EXT if low.endswith(e)), None) or os.path.splitext(name)[1].lower()
        stem = name[:-len(ext)] if ext else name
        rec = {"path": f, "name": name, "stem": stem, "ext": ext, "bytes": os.path.getsize(f), "pages": None, "words": None,
               "pdf_created": None, "note": ""}
        if ext in PDF_EXT:
            rec["pages"], extra = pdf_pages(f)
            if rec["pages"] is None: rec["note"] = extra or ""
            else: rec["pdf_created"] = extra
        elif ext in TEXT_EXT:
            try: rec["words"] = len(LN.read_text(f, errors="replace").split())
            except Exception as e: rec["note"] = f"unreadable: {e.__class__.__name__}"
        recs.append(rec)
    return recs

def group_docs(recs):
    """A .pdf and the .txt/.md/.html of the same stem in the same folder form one document."""
    docs, order = {}, []
    for r in recs:
        key = (os.path.dirname(r["path"]), r["stem"])
        if key not in docs:
            docs[key] = {"stem": r["stem"], "dir": os.path.dirname(r["path"]), "files": []}; order.append(key)
        docs[key]["files"].append(r)
    out = []
    for k in order:
        d = docs[k]
        d["pages"] = sum(f["pages"] for f in d["files"] if f["pages"] is not None) or (0 if any(f["ext"] in PDF_EXT for f in d["files"]) else None)
        if any(f["ext"] in PDF_EXT and f["pages"] is None for f in d["files"]): d["pages"] = None
        d["words"] = sum(f["words"] for f in d["files"] if f["words"] is not None) if any(f["words"] is not None for f in d["files"]) else None
        d["bytes"] = sum(f["bytes"] for f in d["files"])
        d["pdf_created"] = next((f["pdf_created"] for f in d["files"] if f["pdf_created"]), None)
        out.append(d)
    return out

# --------------------------------------------------------------------------------------------------------- the README
def find_readmes(paths, explicit):
    """The README beside the sources: the given one, else README.md in each source dir, its parent and grandparent
    (books/sources/web/<batch>/README.md covers its subfolders), stopping at books/sources."""
    if explicit: return [os.path.abspath(explicit)]
    found, seen = [], set()
    stop = os.path.abspath(os.path.join(ROOT, "books", "sources"))
    for p in paths:
        d = os.path.abspath(p) if os.path.isdir(p) else os.path.dirname(os.path.abspath(p))
        for _ in range(3):
            cand = os.path.join(d, "README.md")
            if os.path.isfile(cand) and cand not in seen: seen.add(cand); found.append(cand)
            if os.path.abspath(d) == stop or os.path.dirname(d) == d: break
            d = os.path.dirname(d)
    return found

def parse_readme(path):
    lines = LN.read_lines(path)
    tables = []
    for t in LN.tables(lines, 0, len(lines)):   # form T1b over the whole README
        hdr = t.header
        tables.append({"header": hdr, "rows": [dict(zip(hdr, r + [""] * (len(hdr) - len(r)))) for r in t.row_cells]})
    return {"path": path, "lines": lines, "tables": tables}

def col(hdr, *words, exclude=()):
    for h in hdr:
        hl = h.lower()
        if any(w in hl for w in words) and not any(x in hl for x in exclude): return h
    return None

def readme_lookup(doc, readmes):
    """What the README says about one document: title, date, pages, size, url, words, and where it said it."""
    names = {f["name"].lower() for f in doc["files"]}
    stem_n = norm_key(doc["stem"])
    for rm in readmes:
        for t in rm["tables"]:
            hdr = t["header"]
            c_file = col(hdr, "file"); c_id = next((h for h in hdr if h.strip().lower() == "id"), None)
            c_url = col(hdr, "url"); c_date = col(hdr, "date", "published"); c_pages = col(hdr, "page")
            c_size = col(hdr, "size", "byte"); c_words = col(hdr, "word"); c_pub = col(hdr, "published", "release")
            c_title = col(hdr, "title") or col(hdr, "document", exclude=("date",)) or col(hdr, "what")
            for row in t["rows"]:
                vals = [re.sub(r"[*`]", "", v) for v in row.values()]
                hit = False
                if c_file and row.get(c_file, "").strip().lower() in names: hit = True
                elif c_id and row.get(c_id, "").strip() and stem_n.startswith(norm_key(row[c_id])): hit = True
                elif any(v.strip().lower() in names for v in vals): hit = True
                elif any(norm_key(v) and (norm_key(v) == stem_n or (len(norm_key(v)) > 12 and norm_key(v) in stem_n)) for v in vals): hit = True
                if not hit: continue
                return {"title": row.get(c_title, "").strip() if c_title else "", "date": row.get(c_date, "").strip() if c_date else "",
                        "pages": row.get(c_pages, "").strip() if c_pages else "", "size": row.get(c_size, "").strip() if c_size else "",
                        "url": row.get(c_url, "").strip() if c_url else "", "words": row.get(c_words, "").strip() if c_words else "",
                        "published": row.get(c_pub, "").strip() if c_pub else "", "where": f"{os.path.relpath(rm['path'], ROOT)} table row",
                        "table": True}
        # prose or bullet fallback: a line naming the file or its stem, read for a URL and a date
        for ln in rm["lines"]:
            if cells(ln) is not None: continue
            ll = ln.lower()
            if any(n in ll for n in names) or doc["stem"].lower() in ll:
                urls = re.findall(r"https?://[^\s)\]>,;]+", ln)
                m = re.search(r"^\s*-\s*\S+:\s*(\d{4}-\d{2}-\d{2}):\s*(.+)$", ln)   # '- <stem>: <date>: <title>' (adverse-1014 README)
                date = m.group(1) if m else ""
                title = m.group(2).strip() if m else ""
                if urls or date:
                    return {"title": title, "date": date, "pages": "", "size": "", "url": "; ".join(dict.fromkeys(urls)), "words": "",
                            "published": "", "where": f"{os.path.relpath(rm['path'], ROOT)} prose line", "table": False}
        # folder fallback: a `## <folder>/` section of the README whose prose carries URLs (adverse-1014/README.md's form)
        folder = os.path.basename(doc["dir"]) + "/"
        sec_urls, insec = [], False
        for ln in rm["lines"]:
            if ln.startswith("## "): insec = ln[3:].strip().lower().startswith(folder.lower())
            elif insec: sec_urls += re.findall(r"https?://[^\s)\]>,;]+", ln)
        if sec_urls:
            return {"title": "", "date": "", "pages": "", "size": "", "url": "; ".join(dict.fromkeys(sec_urls)) + " (the folder's URL in the README; not per file)",
                    "words": "", "published": "", "where": f"{os.path.relpath(rm['path'], ROOT)} section {folder}", "table": False, "folder": True}
    return None

def stem_date(stem):
    """A date the fetcher wrote into the file name (ostley-gazette-2017-10-09-..., margin-notes-2021-03-...), marked as such; else ''."""
    m = re.search(r"(?<!\d)((?:1[6-9]|20)\d{2})-(\d{2})(?:-(\d{2}))?(?!\d)", stem)
    if not m: return ""
    d = m.group(1) + "-" + m.group(2) + (f"-{m.group(3)}" if m.group(3) else "")
    return f"{d} (from the file name)"

# ------------------------------------------------------------------------------------------------------- the note text
class Note(LN.Note):
    """The note as the parser library reads it (section: form S2; table: form T1 within the section; block: note_fill's generated
    blocks; meta: form M1 over the first 120 lines). Edits go to self.lines and are saved with LF endings."""
    def __init__(self, path):
        super().__init__(path)

    def section(self, heading_prefix):
        """(start, end) line indices of the first `## ` section whose heading starts with the prefix (end exclusive)."""
        return LN.section_bounds(self.lines, heading_prefix)

    def table(self, start, end, header_prefix):
        """First table between start and end whose header cells start with the given prefixes -> (hdr_idx, rows_idx_list, cells)."""
        t = LN.find_table(self.lines, start, header_prefix, end)
        return (t.header_line, t.row_lines, t.row_cells) if t else (None, [], [])

    def meta(self):
        """{key: (line_idx, value)} for the metadata table at the top of the note."""
        return {k: (i, v) for k, v, i in LN.meta_rows(self.lines, 120)}

    def count_rows(self, heading, header_prefix):
        sec = self.section(heading)
        if not sec: return None
        _, rows, cs = self.table(sec[0], sec[1], header_prefix)
        return len(cs) if rows else None

# ---------------------------------------------------------------------------------------------------- (a) metadata
def gen_metadata(docs, readmes, dest_dir, rm_hits):
    """Generated values for the derivable keys, with hints where the README lacks what a key needs."""
    g, hints = {}, []
    pages = sum(d["pages"] for d in docs if d["pages"])
    words = sum(d["words"] for d in docs if d["words"])
    n_pdf = sum(1 for d in docs if any(f["ext"] in PDF_EXT for f in d["files"]))
    n_txt = sum(1 for d in docs if d["words"] is not None)
    parts = []
    for d in docs:
        if d["pages"] is None and d["words"] is None: continue
        lab = (rm_hits.get(d["stem"]) or {}).get("title") or d["stem"]
        bits = ([f"{fmt(d['pages'])} pages"] if d["pages"] is not None else []) + ([f"{fmt(d['words'])} words"] if d["words"] is not None else [])
        parts.append(f"{clip(lab, 60)}: {', '.join(bits)}")
    detail = "; ".join(parts[:6]) + ("; the rest in the inventory" if len(parts) > 6 else "")
    if pages and words: g["Length"] = f"{fmt(pages)} PDF pages in {n_pdf} held file{'s' if n_pdf != 1 else ''}, {fmt(words)} words in the text layers ({detail})"
    elif words: g["Length"] = f"{fmt(words)} words in {n_txt} held text{'s' if n_txt != 1 else ''} ({detail}); no PDF held"
    elif pages: g["Length"] = f"{fmt(pages)} PDF pages in {n_pdf} held file{'s' if n_pdf != 1 else ''} ({detail}); no text layer held"
    else: g["Length"] = None
    # Transcript: every held file linked, or the folders when the set is large
    links = []
    for d in docs:
        txt = [f for f in d["files"] if f["ext"] in TEXT_EXT]; pdf = [f for f in d["files"] if f["ext"] in PDF_EXT]
        other = [f for f in d["files"] if f["ext"] not in TEXT_EXT | PDF_EXT]
        lab = (rm_hits.get(d["stem"]) or {}).get("title") or d["stem"]
        if txt: s = f"[{clip(lab, 70)}]({rel_link(txt[0]['path'], dest_dir)})" + (f" (and [the pdf]({rel_link(pdf[0]['path'], dest_dir)}))" if pdf else "")
        elif pdf: s = f"[{clip(lab, 70)}]({rel_link(pdf[0]['path'], dest_dir)}) (pdf, no text layer held)"
        else: s = f"[{other[0]['name']}]({rel_link(other[0]['path'], dest_dir)})"
        links.append(s)
    folders = sorted({d["dir"] for d in docs})
    fl = ", ".join(f"[{os.path.relpath(f, ROOT)}/]({rel_link(f, dest_dir)}/)" for f in folders)
    if len(links) > 8:
        g["Transcript"] = f"Source files: {len(docs)} held documents in {fl} (for example {'; '.join(links[:3])}; every file is in the inventory)"
    else:
        g["Transcript"] = "Source files: " + "; ".join(links)
    if readmes:
        g["Transcript"] += "; provenance in " + ", ".join(f"[{os.path.basename(os.path.dirname(r['path']))} README]({rel_link(r['path'], dest_dir)})" for r in readmes)
    g["Added to notes"] = TODAY
    urls = list(dict.fromkeys(u.strip() for h in rm_hits.values() if h and h.get("url") and not h.get("folder") for u in re.split(r"[;\s]+", h["url"]) if u.startswith("http")))
    g["URL"] = ("; ".join(urls[:3]) + (f" (and {len(urls) - 3} more, in the inventory)" if len(urls) > 3 else "")) if urls else None
    folder_urls = list(dict.fromkeys(u for h in rm_hits.values() if h and h.get("folder") for u in re.findall(r"https?://[^\s)\]>,;]+", h["url"])))
    if not urls: hints.append("URL: no per-file URL in the README" + (f"; the README's folder section gives {', '.join(folder_urls)} (not assigned to a file)" if folder_urls else ""))
    pubs = sorted({d for h in rm_hits.values() if h and h.get("published") for d in parse_dates(h["published"])})
    g["Uploaded"] = pubs[0] if pubs else None
    if not pubs: hints.append("Uploaded: the README has no Published or Release column; set it from the release or publication date")
    dates = sorted({d for h in rm_hits.values() if h and h.get("date") and h.get("table") for d in parse_dates(h["date"])})
    if dates: g["Recorded"] = (dates[0] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}") + " [the documents' own dates, from the README beside the files]"
    else:
        g["Recorded"] = None
        pc = sorted({d["pdf_created"] for d in docs if d.get("pdf_created")})
        hints.append("Recorded: no document date in the README" + (f"; PDF CreationDate values seen: {', '.join(pc)}" if pc else ""))
    return g, hints

def length_numbers(cell):
    """Every 'N pages' and 'N words' figure in a Length cell, in order (the first is usually the headline)."""
    pg = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]*)\s*(?:PDF |scanned |printed |held )?pages?\b", cell or "")]
    wd = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]*)\s*(?:OCR )?words?\b", cell or "")]
    return pg, wd

def figures_agree(figs, computed, tol):
    """The cell agrees when its first figure, its largest or the sum of all its figures is within tol of the computed total."""
    if not figs or not computed: return None
    return any(abs(x - computed) <= tol for x in (figs[0], max(figs), sum(figs)))

def do_metadata(note, docs, readmes, dest_dir, rep, write, force, rm_hits):
    meta = note.meta()
    if not meta: rep.diff("metadata: no two-column bold-key table found at the top of the note"); return
    g, hints = gen_metadata(docs, readmes, dest_dir, rm_hits) if docs else ({}, ["no --sources given: Length, Transcript, URL, Uploaded, Recorded not generated"])
    for h in hints: rep.hint(h)
    for key in META_KEYS:
        if key not in meta:
            if key in ("Host", "Guest", "Recorded", "Description", "Authors"): continue
            rep.diff(f"metadata: key {key} missing from the table"); continue
        i, val = meta[key]
        empty = (val.strip() == "" or FILL in val)
        if key in DERIVABLE:
            gen = g.get(key)
            if empty:
                if gen and write:
                    note.lines[i] = f"| **{key}** | {gen} |"; rep.wrote(f"metadata {key}: {clip(gen, 160)}")
                elif gen: rep.diff(f"metadata {key}: empty; generated value: {clip(gen, 160)}")
                else:
                    if write and FILL not in val: note.lines[i] = f"| **{key}** | {FILL} |"
                    rep.diff(f"metadata {key}: empty and not derivable from the sources or README")
            else:
                if key == "Length" and not docs: rep.ok("metadata Length: set (no --sources to compare)")
                if key == "Length" and docs:
                    hp, hw = length_numbers(val)
                    cp = sum(d["pages"] for d in docs if d["pages"]); cw = sum(d["words"] for d in docs if d["words"])
                    probs = []
                    ap_ = figures_agree(hp, cp, 0); aw = figures_agree(hw, cw, max(50, 0.05 * cw))
                    if ap_ is False: probs.append(f"pages: the cell's figures {', '.join(map(fmt, hp))} (first, largest or sum) do not give the files' {fmt(cp)}")
                    if aw is False: probs.append(f"words: the cell's figures {', '.join(map(fmt, hw))} (first, largest or sum) do not give the files' {fmt(cw)}")
                    if not hp and cp: probs.append(f"pages: none stated in the cell; files give {fmt(cp)}")
                    if not hw and cw: probs.append(f"words: none stated in the cell; files give {fmt(cw)}")
                    if probs: rep.diff("metadata Length: " + "; ".join(probs))
                    else: rep.ok(f"metadata Length: headline figures agree with the files (pages {fmt(cp)}, words {fmt(cw)})")
                elif key == "Added to notes":
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val.strip()): rep.diff(f"metadata Added to notes: not YYYY-MM-DD: {val}")
                    else: rep.ok(f"metadata Added to notes: {val}")
                elif key == "Transcript":
                    from urllib.parse import unquote
                    broken = [t for t in LN.MD_LINK_RE.findall(val) if not t.startswith("http") and not LP.exists(unquote(t), base=dest_dir)]   # links resolve through the sources/ alias table
                    if broken: rep.diff(f"metadata Transcript: {len(broken)} link(s) do not resolve from {os.path.relpath(dest_dir, ROOT)}/: {', '.join(broken[:4])}")
                    if not docs: rep.ok("metadata Transcript: links resolve") if not broken else None
                if key == "Transcript" and docs:
                    missing = [d["stem"] for d in docs if not any(quote(f["name"], safe="/-_.~()") in val or f["name"] in val or d["stem"] in val for f in d["files"])]
                    folder_linked = any(os.path.basename(d["dir"]) + "/" in val for d in docs)
                    if missing and not folder_linked: rep.diff(f"metadata Transcript: {len(missing)} held document(s) not linked: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")
                    elif missing: rep.ok(f"metadata Transcript: links the folder; {len(missing)} file(s) not linked by name (see the inventory)")
                    else: rep.ok("metadata Transcript: every held document is linked")
                elif key not in ("Length", "Added to notes", "Transcript") and gen:
                    if re.sub(r"\s+", " ", val) == re.sub(r"\s+", " ", gen): rep.ok(f"metadata {key}: equals the generated value")
                    else:
                        rep.kept(f"metadata {key}: set by hand; generated value would be: {clip(gen, 160)}")
                elif key not in ("Length", "Added to notes", "Transcript"): rep.ok(f"metadata {key}: set by hand; nothing to derive it from the README")
                if force and write and gen and key != "Added to notes":
                    note.lines[i] = f"| **{key}** | {gen} |"; rep.wrote(f"metadata {key} (--force): {clip(gen, 160)}")
        else:
            if empty:
                if write and FILL not in val: note.lines[i] = f"| **{key}** | {FILL} |"; rep.wrote(f"metadata {key}: marked {FILL} (judgement key)")
                else: rep.diff(f"metadata {key}: empty (judgement key, to be filled by the agent)")
    for key in meta:
        if key not in META_KEYS: rep.ok(f"metadata: trailing note-specific key kept: {key}")

# --------------------------------------------------------------------------------------------------- (b) inventory
def gen_inventory(docs, readmes, dest_dir, rm_hits, sources):
    L = ["<!-- inventory:start -->",
         f"Held files, generated by `tools/note_fill.py` on {TODAY} from {', '.join(os.path.relpath(s, ROOT) for s in sources)} "
         f"(pages by pypdf, words by whitespace split of the .txt or .md text layer, bytes on disk; dates and URLs from "
         f"{', '.join(os.path.relpath(r['path'], ROOT) for r in readmes) or 'no README found'}; `{FILL}` where the README gives none):", "",
         INV_HEADER, INV_SEP]
    tp = tw = tb = nf = 0
    for i, d in enumerate(docs, 1):
        h = rm_hits.get(d["stem"]) or {}
        files = ", ".join(f"[{f['name']}]({rel_link(f['path'], dest_dir)})" for f in d["files"])
        pages = fmt(d["pages"]) if d["pages"] is not None else ("n/a" if not any(f["ext"] in PDF_EXT for f in d["files"]) else "? (pypdf could not read it)")
        words = fmt(d["words"]) if d["words"] is not None else "n/a"
        title = h.get("title") or d["stem"]
        if h.get("pages") and d["pages"] is not None and re.sub(r"\D", "", h["pages"]) and int(re.sub(r"\D", "", h["pages"])) != d["pages"]:
            pages += f" (README says {h['pages']})"
        date = h.get("date") or stem_date(d["stem"]) or FILL
        url = h.get("url") or FILL
        L.append(f"| {i} | {clip(title, 160)} | {files} | {pages} | {words} | {fmt(d['bytes'])} | {clip(date, 120)} | {url} |")
        tp += d["pages"] or 0; tw += d["words"] or 0; tb += d["bytes"]; nf += len(d["files"])
    L.append(f"| | total: {len(docs)} documents | {nf} files | {fmt(tp)} | {fmt(tw)} | {fmt(tb)} | | |")
    L.append("<!-- inventory:end -->")
    return L

def check_hand_inventory(note, sec, docs, rep):
    """The section's hand table (How the set is built) against the files: Pages cell per matched row, unmatched rows, unlisted files."""
    hdr_i, rows_i, rows = note.table(sec[0], sec[1], ("#",))
    if hdr_i is None: return
    hdr = [h.lower() for h in cells(note.lines[hdr_i])]
    pcol = next((k for k, h in enumerate(hdr) if h.startswith("page")), None)
    matched = set()
    for r in rows:
        if not r or not re.fullmatch(r"\d+(\.\d+)?", r[0]): continue
        text = " ".join(r); tn = norm_key(text)
        hit = None
        for d in docs:
            keys = [d["stem"]] + [f["name"] for f in d["files"]]
            if any(k.lower() in text.lower() for k in keys) or (len(norm_key(d["stem"])) > 10 and norm_key(d["stem"]) in tn): hit = d; break
            # an ID such as HI-114 or DC-0917 in the row against the stem
            ns = norm_key(d["stem"])
            for m in re.findall(r"\b([A-Z]{2,}(?:[-_ ][A-Z]+)*[-_ ]?\d{1,4}[A-Z]?)\b", text):
                nid = norm_key(m)
                if nid and ns.startswith(nid) and (len(ns) == len(nid) or not ns[len(nid)].isdigit()): hit = d; break
            if hit: break
        if not hit: rep.hint(f"inventory: hand row {r[0]} matches no held file by name or ID: {clip(text, 100)}"); continue
        matched.add(hit["stem"])
        if pcol is not None and pcol < len(r) and hit["pages"] is not None:
            m = re.search(r"\d[\d,]*", r[pcol])
            if m and int(m.group(0).replace(",", "")) != hit["pages"]:
                rep.diff(f"inventory: hand row {r[0]} says {r[pcol]} pages; pypdf gives {hit['pages']} for {hit['stem']}")
            elif m: rep.ok(f"inventory: hand row {r[0]} pages {hit['pages']} agree with {hit['stem']}")
    un = [d["stem"] for d in docs if d["stem"] not in matched]
    if un: rep.hint(f"inventory: {len(un)} held document(s) not named in the hand table: {', '.join(un[:6])}{'...' if len(un) > 6 else ''}")

def do_inventory(note, docs, readmes, dest_dir, rep, write, rm_hits, sources, under, check=False):
    secs = [s_ for s_ in (note.section(h) for h in ([under] if under else []) + ["## How the set is built", "## The documents, one by one"]) if s_]
    if not secs and check and not under and not docs:
        # check mode on a note that is not in the document form (no inventory section, no --sources): nothing to compare (2026-10-22)
        rep.ok("inventory: not a document-form note (no `## How the set is built` or `## The documents, one by one`): not checked"); return
    if not secs:
        rep.diff("inventory: no `## How the set is built` or `## The documents, one by one` section (give --inventory-under)"); return
    sec = next((s_ for s_ in secs if note.block("inventory", s_[0], s_[1])), secs[0])
    blk = note.block("inventory", sec[0], sec[1])
    if not docs:
        if blk: rep.ok("inventory: block present (no --sources given, not recomputed)")
        else: rep.hint("inventory: no --sources given; nothing to compare")
        return
    gen = gen_inventory(docs, readmes, dest_dir, rm_hits, sources)
    for s_ in secs:
        if note.table(s_[0], s_[1], ("#",))[0] is not None: check_hand_inventory(note, s_, docs, rep); break
    else: rep.hint("inventory: no hand table with a # column in either section to compare")
    if blk:
        old = note.lines[blk[0]:blk[1] + 1]
        strip = lambda L: [re.sub(r"generated by `tools/note_fill.py` on \d{4}-\d{2}-\d{2}", "", l) for l in L]
        if strip(old) == strip(gen): rep.ok(f"inventory: block up to date ({len(docs)} documents)")
        elif write: note.lines[blk[0]:blk[1] + 1] = gen; rep.wrote(f"inventory: block refreshed ({len(docs)} documents, {sum(len(d['files']) for d in docs)} files)")
        else: rep.diff(f"inventory: block differs from the files ({len(docs)} documents now)")
    else:
        if write:
            at = sec[0] + 1
            while at < sec[1] and note.lines[at].strip() == "": at += 1
            note.lines[at:at] = gen + [""]
            rep.wrote(f"inventory: block inserted under {note.lines[sec[0]].strip()} ({len(docs)} documents)")
        else: rep.hint(f"inventory: no generated block in the note ({len(docs)} held documents would be listed); fill mode inserts it under {note.lines[sec[0]].strip()}")

# ------------------------------------------------------------------------------------------------- (c) audit counts
MOVES = ("open", "partial", "closed-outright", "closed-subtle")

# Stated declines (2026-10-22): a row whose Basis names something (not n/a, none stated, not known, blank; a redaction or a
# sanitisation at release is a wall, never a decline) counts when it refuses: its Move is closed-outright (the schema's mapping, a
# refusal with a ground given), or its Note says it is a decline ("stated decline", "X's decline"; not "pseudo-decline", not "not
# counted as a decline"), or its Basis names a ground of the basis vocabulary (the pack's [audit] basis_vocabulary; the schema's list
# as the core default), on any move (a decline inside another answer). The sourcing a monologue's rows carry in Basis ("His own
# reasoning", a book title) is never a ground: the earlier rule counted any named Basis, which put 204 stated declines on a
# monologue whose hand line says 4. Measured on the 266 notes: 85 hand lines disagreed before, 55 after, none by more than 5.
GROUNDS_CORE = ["classification", "promise", "NDA", "pending investigation", "not tasked", "safety", "protecting a named person"]

def _grounds():
    try:
        import packload
        return list(packload.pack().get("audit", {}).get("basis_vocabulary") or GROUNDS_CORE)
    except Exception: return GROUNDS_CORE

def _ground_rx(terms):
    """each term as a phrase; a word of five letters or more matches its inflections (classifi- for classification and classified,
    promis- for promise and promised, not prominent); up to two words may stand inside a phrase (pending IG reprisal investigation)"""
    def word(w):
        if len(w) <= 4 or w.isupper(): return re.escape(w) + r"(?!\w)"
        return re.escape(w[:max(5, len(w) - 1 if len(w) <= 8 else int(len(w) * 0.6))]) + r"\w*"
    return re.compile(r"(?<![\w-])(?:" + "|".join(r"(?:\s+[\w'-]+){0,2}?\s+".join(word(w) for w in t.split()) for t in terms) + r")", re.I)

GROUND_RE = _ground_rx(_grounds())
NOTE_DECLINE_RE = re.compile(r"declin(?:e|es|ed|ing)\b", re.I)
NOTE_NOT_DECLINE_RE = re.compile(r"(?:pseudo-|pseudo |\bnot (?:counted as )?(?:a |an )?(?:stated )?|\bno (?:stated )?|\bnever (?:a )?)$", re.I)

def note_declines(note):
    """the Note cell says the row is a decline: a mention of decline not preceded by pseudo-, not, no or never"""
    return any(not NOTE_NOT_DECLINE_RE.search(note[max(0, m.start() - 30):m.start()]) for m in NOTE_DECLINE_RE.finditer(note or ""))

def audit_counts(rows):
    c = {m: 0 for m in MOVES}; na = 0; declines = 0; pseudo = 0; walls = 0; basis_hist = {}; decline_rows = []; wall_rows = []; odd = []
    for r in rows:
        r = r + [""] * (8 - len(r))
        mv = r[5].strip().lower(); mv1 = next((m for m in MOVES if mv.startswith(m)), None)
        if mv1 is None and re.search(r"\bn/?a\b", mv): na += 1
        elif mv1 is None: odd.append((r[0], r[5]))
        else:
            if mv1 != mv: pass  # compound move: first class named counts (schema parser rule)
            c[mv1] += 1
        b = r[6].strip(); bl = b.lower()
        basis_hist[b] = basis_hist.get(b, 0) + 1
        if bl.startswith("redacted") or "sanitis" in bl or "sanitiz" in bl: walls += 1; wall_rows.append(r[0])   # a release-time sanitisation is a redaction (an archive exemplar's wording)
        elif (bl and bl not in ("n/a", "na", "none stated", "none", "-") and not bl.startswith(("not known", "none stated", "n/a"))
              and (mv1 == "closed-outright" or note_declines(r[7]) or GROUND_RE.search(b))):
            declines += 1; decline_rows.append(r[0])
        if re.search(r"(?<!not a )(?<!no )pseudo-decline", r[7].lower()): pseudo += 1
    line = (f"Audit counts: open {c['open']}, partial {c['partial']}, closed-outright {c['closed-outright']}, closed-subtle {c['closed-subtle']}, "
            f"stated declines {declines}, pseudo-declines {pseudo}.")
    return {"line": line, "counts": c, "na": na, "declines": declines, "decline_rows": decline_rows, "pseudo": pseudo, "walls": walls,
            "wall_rows": wall_rows, "basis": basis_hist, "odd": odd, "rows": len(rows)}

def do_audit(note, rep, write, force):
    sec = note.section("## Candour audit") or note.section("## Forthrightness audit")   # the candour audit (renamed 2026-10-22); the legacy heading still accepted
    if not sec: rep.diff("audit: no `## Candour audit` (or legacy `## Forthrightness audit`) section"); return None
    hdr_i, rows_i, rows = note.table(sec[0], sec[1], ("#", "time", "asked", "question", "answer", "move", "basis"))
    if hdr_i is None: rep.diff("audit: heading found, table not in schema shape"); return None
    a = audit_counts(rows)
    hist = ", ".join(f"{k or '(blank)'} {v}" for k, v in sorted(a["basis"].items(), key=lambda x: -x[1]))
    rep.hint(f"audit: {a['rows']} rows; n/a moves {a['na']}; walls (Basis redacted) {a['walls']}" + (f" (rows {', '.join(a['wall_rows'])})" if a["wall_rows"] and len(a["wall_rows"]) <= 12 else "")
             + f"; stated declines counted on rows {', '.join(a['decline_rows']) or 'none'}; basis: {hist}")
    if a["odd"]: rep.diff(f"audit: Move cell not in the vocabulary on rows {', '.join(f'{n} ({m})' for n, m in a['odd'])}")
    # the hand or generated line
    hand_i = next((i for i in range(rows_i[-1] + 1 if rows_i else hdr_i, sec[1]) if note.lines[i].startswith("Audit counts:")), None)
    blk = note.block("audit-counts", sec[0], sec[1])
    if hand_i is not None and not re.search(r"open \d+", note.lines[hand_i]):
        # a skeleton placeholder (`open N, partial N ...`), not a hand count: treated as absent
        if write:
            note.lines[hand_i:hand_i + 1] = ["<!-- audit-counts:start -->", a["line"], "<!-- audit-counts:end -->"]
            rep.wrote(f"audit counts: skeleton placeholder replaced: {a['line']}")
        else: rep.diff(f"audit counts: the line is still the skeleton placeholder; the table gives `{a['line']}`")
    elif hand_i is not None:
        hand = note.lines[hand_i].strip()
        if hand == a["line"]: rep.ok(f"audit counts: the note's line agrees with the table: {a['line']}")
        else:
            rep.diff(f"audit counts: note says `{hand}`; the table gives `{a['line']}` (stated declines counted as refusing rows with a ground: closed-outright, a Note that says decline, or a vocabulary ground in Basis; a row carrying two refusals counts once here)")
        if write:
            if blk is None:
                if hand == a["line"] or force:
                    note.lines[hand_i:hand_i + 1] = ["<!-- audit-counts:start -->", a["line"], "<!-- audit-counts:end -->"]
                    rep.wrote("audit counts: line wrapped in markers" + (" and replaced (--force)" if hand != a["line"] else ""))
                else: rep.kept("audit counts: hand line kept (differs; --force replaces it)")
            elif hand != a["line"] and force:
                note.lines[hand_i] = a["line"]; rep.wrote("audit counts: line replaced (--force)")
            elif hand != a["line"]: rep.kept("audit counts: line inside the block differs and was kept (--force replaces it)")
    else:
        if write:
            at = (rows_i[-1] + 1) if rows_i else hdr_i + 2
            note.lines[at:at] = ["", "<!-- audit-counts:start -->", a["line"], "<!-- audit-counts:end -->"]
            rep.wrote(f"audit counts: line written after the table: {a['line']}")
        else: rep.diff(f"audit counts: no `Audit counts:` line in the section; the table gives `{a['line']}`")
    return a

# ------------------------------------------------------------------------------------------------- (d) cross-checks
def parse_onboard(path):
    """Candidates from tools/onboard_check.py's report: list of dicts with id, part, elsewhere (file, kind, n), this-note rows, custody."""
    L = LN.read_lines(path)
    cands, i, cur = [], 0, None
    def table_rows(j):
        rows = []
        while j < len(L) and cells(L[j]) is None and not L[j].startswith("#"): j += 1
        if j < len(L) and cells(L[j]) and j + 1 < len(L) and is_sep(L[j + 1]):
            hdr = cells(L[j]); j += 2
            while j < len(L) and cells(L[j]) is not None: rows.append(dict(zip(hdr, cells(L[j]) + [""] * len(hdr)))); j += 1
        return rows
    while i < len(L):
        l = L[i]
        mA = re.match(r"^### A(\d+)\. (\S+) #(\S+) \[([^\]]*)\](?: \[([^\]]*)\])?, (\d+) shared: (.*)$", l)
        mB = re.match(r"^### B(\d+)\. This note #(\S+) \((.*)\)$", l)
        mC = re.match(r"^### C(\d+)\. (\S+) audit (\S+) \(([^,]*), ([^,]*), basis: (.*)\), (\d+) shared: (.*)$", l)
        if mA:
            q = next((x for x in L[i + 1:i + 8] if x.startswith("**Question:**")), ""); s = next((x for x in L[i + 1:i + 10] if x.startswith("**What would settle it:**")), "")
            rows = [r for r in table_rows(i + 1) if r.get("This note #", "").strip().lower() != "none"]
            file = mA.group(2); n = mA.group(3)
            kind = "lead" if file.startswith("research/leads") else "open question"
            cands.append({"id": f"A{mA.group(1)}", "part": "A", "file": file, "ref": f"{kind} {n}", "status": mA.group(4), "why": mA.group(5) or "",
                          "shared": mA.group(7), "question": q.replace("**Question:**", "").strip(), "settles": s.replace("**What would settle it:**", "").strip(),
                          "rows": rows, "custody": "", "likely": "answers"})
        elif mB:
            quote_l = next((x for x in L[i + 1:i + 6] if x.startswith("> ")), "")
            meta = mB.group(3); parts = [p.strip() for p in meta.rsplit(",", 3)]
            rows = table_rows(i + 1)
            for j, r in enumerate(rows, 1):
                file = r.get("Note", ""); n = r.get("#", "")
                cands.append({"id": f"B{mB.group(1)}.{j}", "part": "B", "file": file, "ref": f"claims {n}", "status": "", "why": "",
                              "shared": r.get("Shared", ""), "question": "", "settles": "", "likely": "corroborates / contradicts / extends",
                              "rows": [{"This note #": mB.group(2), "Time": parts[0] if parts else "", "Speaker": parts[1] if len(parts) > 1 else "",
                                        "Class": parts[2] if len(parts) > 2 else "", "Claim": quote_l[2:].strip()}],
                              "custody": f"custody: {r.get('Class', '')}; " + (r.get("Attribution; chain", "") if r.get("Attribution; chain", "") not in ("", "not recorded") else "attribution and chain not recorded in notes.db"),
                              "other_claim": r.get("Claim", ""), "other_time": r.get("Time", ""), "other_speaker": r.get("Speaker", "")})
        elif mC:
            q = next((x for x in L[i + 1:i + 6] if x.startswith("**Asked by:**")), ""); a = next((x for x in L[i + 1:i + 8] if x.startswith("**Answer:**")), "")
            sw = next((x for x in L[i + 1:i + 10] if x.startswith("**Sweep:**")), "")
            rows = [r for r in table_rows(i + 1) if r.get("This note #", "").strip().lower() != "none"]
            cands.append({"id": f"C{mC.group(1)}", "part": "C", "file": mC.group(2), "ref": f"audit {mC.group(3)}", "status": mC.group(5), "why": "",
                          "shared": mC.group(8), "question": q.replace("**Asked by:**", "asked by").strip(), "settles": "", "rows": rows, "likely": "fills",
                          "custody": f"custody of the decline: {mC.group(5)}, basis {mC.group(6)}; {a.replace('**Answer:**', 'answer:').strip()}; {sw.replace('**Sweep:**', 'sweep:').strip()}"})
        i += 1
    return cands

def short_title(file):
    """A short link text for another note: its H1 up to the first colon or bracket, else the stem."""
    p = os.path.join(ROOT, file)
    stem = os.path.basename(file)[:-3] if file.endswith(".md") else file
    if file.startswith("research/leads"): return "Leads"
    try:
        h1 = LN.first_line(p).strip().lstrip("# ").strip()
        t = re.split(r"[:(\[]", h1)[0].strip().rstrip(",")
        t = re.sub(r"^(The|A)\s+", "", t)
        return clip(t, 60) if t else stem
    except OSError: return stem

def xc_link(file, dest_dir):
    p = os.path.join(ROOT, file)
    return f"[{short_title(file)}]({rel_link(p, dest_dir)})"

def xc_key(elsewhere):
    """A row's Elsewhere target as a comparable key: (path stem, ref words)."""
    m = LN.ELSEWHERE_RE.search(elsewhere or "")
    if not m: return re.sub(r"\s+", " ", elsewhere or "").strip().lower()
    path = os.path.basename(m.group(1)); refs = re.sub(r"\s+", " ", m.group(2)).strip().lower()
    return f"{path} {refs}"

def parse_accept(path):
    """`B12.2 corroborates partial | note text` per line; blank lines and # comments skipped."""
    acc = {}
    for ln in LN.iter_lines(path):
        ln = ln.strip()
        if not ln or ln.startswith("#"): continue
        head, _, note = ln.partition("|")
        ws = head.split()
        if len(ws) < 3: raise SystemExit(f"--accept: a line needs `<id> <kind> <verdict> [| note]`: {ln}")
        acc[ws[0]] = {"kind": ws[1], "verdict": ws[2], "note": note.strip()}
    return acc

def gen_xc_rows(cands, dest_dir, accept, start_n, present_keys, skipped):
    rows = []
    n = start_n
    for c in cands:
        if accept is not None and c["id"] not in accept: continue
        els = f"{xc_link(c['file'], dest_dir)} {c['ref']}"
        if xc_key(els) in present_keys: skipped.append(c["id"]); continue
        r0 = c["rows"][0] if c["rows"] else {}
        this = f"{r0.get('Time', '')}, row {r0.get('This note #', '')}: {clip(r0.get('Claim', ''), 240)}" if r0 else "no ledger row shared a term: read the question against the note"
        if len(c["rows"]) > 1: this += f" (also rows {', '.join(r.get('This note #', '') for r in c['rows'][1:])})"
        a = accept.get(c["id"]) if accept else None
        kind = a["kind"] if a else FILL; verdict = a["verdict"] if a else FILL
        note = []
        if a and a["note"]: note.append(a["note"])
        if c["custody"]: note.append(clip(c["custody"], 400))
        else: note.append(f"custody: {FILL}")
        if c["part"] == "B": note.append(f"elsewhere: {c.get('other_time', '')}, {c.get('other_speaker', '')}: {clip(c.get('other_claim', ''), 200)}")
        if c["part"] == "A": note.append(f"what would settle it: {clip(c['settles'], 200) or 'not given'}")
        if c["part"] == "C": note.append(clip(c["question"].replace("**Question:**", "question:").replace("**", ""), 160))
        note.append(f"candidate {c['id']} ({c['shared']} shared)" + (f", {c['why']}" if c["why"] else "") + (f"; likely {c['likely']}" if not a else ""))
        if not a: note.append(FILL)
        rows.append(f"| {n} | {kind} | {this} | {els} | {verdict} | {'; '.join(note)} |")
        n += 1
    return rows

def do_xc(note, onboard, accept_path, dest_dir, rep, write, reset):
    sec = note.section("## Cross-checks")
    if not sec: rep.diff("cross-checks: no `## Cross-checks` section"); return
    cands = parse_onboard(onboard)
    accept = parse_accept(accept_path) if accept_path else None
    if accept is not None:
        unknown = [k for k in accept if k not in {c["id"] for c in cands}]
        if unknown: rep.diff(f"cross-checks: --accept names candidates not in the onboard report: {', '.join(unknown)}")
    h = hashlib.sha1(open(onboard, "rb").read()).hexdigest()[:12]
    blk = note.block("cross-checks", sec[0], sec[1])
    hdr_i, rows_i, rows = note.table(sec[0], sec[1], ("#", "kind", "this note", "elsewhere", "verdict", "note"))
    existing = [note.lines[k] for k in rows_i]
    same_report = blk is not None and f"onboard={h}" in note.lines[blk[0]]
    if reset and blk:
        existing = [l for l in existing if not (cells(l)[1] == FILL and cells(l)[4] == FILL)]
    present = {xc_key(cells(l)[3]) for l in existing if cells(l) and len(cells(l)) > 3}
    nums = [float(cells(l)[0]) for l in existing if cells(l) and re.fullmatch(r"\d+(\.\d+)?", cells(l)[0])]
    start_n = int(max(nums)) + 1 if nums else 1
    if same_report and not reset and accept is None:
        rep.ok(f"cross-checks: block already generated from this onboard report ({len(existing)} rows present); nothing added")
        return
    skipped = []
    new = gen_xc_rows(cands, dest_dir, accept, start_n, present, skipped)
    if skipped: rep.ok(f"cross-checks: {len(skipped)} candidate(s) already present in the table by their Elsewhere target" + (f": {', '.join(skipped[:8])}" if accept is not None else ""))
    if not new and blk:
        if write and not same_report:
            note.lines[blk[0]] = f"<!-- cross-checks:start onboard={h} source={os.path.relpath(onboard, ROOT)} generated={TODAY} -->"
        rep.ok("cross-checks: nothing to add"); return
    if len(new) > 80 and accept is None: rep.hint(f"cross-checks: {len(new)} candidate rows; an --accept file (ids with Kind and Verdict) writes only the kept ones")
    gen = [f"<!-- cross-checks:start onboard={h} source={os.path.relpath(onboard, ROOT)} generated={TODAY} -->", XC_HEADER, XC_SEP] + existing + new + ["<!-- cross-checks:end -->"]
    if not write:
        rep.diff(f"cross-checks: {len(new)} candidate row(s) would be added to {len(existing)} present") if new else rep.ok("cross-checks: no new candidates")
        return
    if blk:
        # the block holds the table; a hand table outside it (before the block) is moved in
        if hdr_i is not None and not (blk[0] < hdr_i < blk[1]):
            del note.lines[hdr_i:rows_i[-1] + 1 if rows_i else hdr_i + 2]
            blk = note.block("cross-checks", sec[0], note.section("## Cross-checks")[1])
        note.lines[blk[0]:blk[1] + 1] = gen
    elif hdr_i is not None:
        end = rows_i[-1] + 1 if rows_i else hdr_i + 2
        note.lines[hdr_i:end] = gen
    else:
        at = sec[1]
        while at > sec[0] + 1 and note.lines[at - 1].strip() == "": at -= 1
        note.lines[at:at] = [""] + gen + [""]
    rep.wrote(f"cross-checks: block written with {len(existing)} existing row(s) kept and {len(new)} candidate row(s) added" + (" (--accept)" if accept is not None else ""))

# ----------------------------------------------------------------------------------------------- report.json check
def check_report(note, path, audit, rep):
    try: r = json.load(open(path, encoding="utf-8"))
    except Exception as e: rep.diff(f"report: {path} is not valid JSON: {e}"); return
    claims = note.count_rows("## Claims ledger", ("#", "time", "speaker", "topic", "claim", "source", "move"))
    tl = note.count_rows("## Dated timeline", ("#", "date", "sortable", "event", "speaker", "chain", "database link", "agreement"))
    for key, val, what in (("claims_rows", claims, "Claims ledger rows"), ("timeline_rows", tl, "Dated timeline rows")):
        if key in r:
            if val is None: rep.diff(f"report {key}={r[key]}; the note has no parsable {what}")
            elif r[key] != val: rep.diff(f"report {key}={r[key]}; the note has {val} {what}")
            else: rep.ok(f"report {key}={r[key]} agrees with the note")
        else: rep.hint(f"report: no {key} key")
    if "audit_rows" in r and audit:
        if r["audit_rows"] != audit["rows"]: rep.diff(f"report audit_rows={r['audit_rows']}; the note's audit table has {audit['rows']} rows")
        else: rep.ok(f"report audit_rows={r['audit_rows']} agrees")
    if "audit_counts" in r and audit:
        norm = lambda s: re.sub(r"^Audit counts:\s*", "", str(s).strip()).rstrip(".").strip()
        if norm(r["audit_counts"]) != norm(audit["line"]): rep.diff(f"report audit_counts `{r['audit_counts']}`; the table gives `{audit['line']}`")
        else: rep.ok("report audit_counts agrees with the table")
    if "words" in r:
        w = len(note.text.split())
        if abs(r["words"] - w) > max(20, 0.02 * w): rep.diff(f"report words={r['words']}; the note has {w}")
        else: rep.ok(f"report words={r['words']} agrees ({w})")
    if "file" in r and os.path.basename(r["file"]) != os.path.basename(note.path): rep.diff(f"report file={r['file']}; checking {os.path.relpath(note.path, ROOT)}")

# -------------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--note", help="the note (books/<note>.md) or skeleton (wip/<task>/skeleton.md) to fill in place")
    ap.add_argument("--check", metavar="NOTE", help="check mode: recompute and report differences, write nothing")
    ap.add_argument("--sources", nargs="*", default=[], help="held dir(s) and/or files")
    ap.add_argument("--recursive", action="store_true", help="descend into subfolders of a --sources dir")
    ap.add_argument("--readme", help="the README beside the sources (default: README.md in the source dir, its parent or grandparent)")
    ap.add_argument("--onboard", help="wip/<task>/onboard.md from tools/onboard_check.py")
    ap.add_argument("--accept", help="accepted candidates: `<id> <kind> <verdict> [| note]` per line; only these are written")
    ap.add_argument("--report", help="wip/<task>/report.json to compare in check mode")
    ap.add_argument("--dest-dir", help="folder the note will live in, for relative links (default: the note's folder if under books/ or videos/, else books/)")
    ap.add_argument("--inventory-under", help="heading to place the inventory under when the usual two are absent")
    ap.add_argument("--force", action="store_true", help="overwrite hand-filled derivable keys and a differing audit counts line")
    ap.add_argument("--reset-xc", action="store_true", help="drop still-unfilled generated cross-check rows and regenerate")
    ap.add_argument("--dry-run", action="store_true", help="fill mode without writing the file")
    a = ap.parse_args()
    if not a.note and not a.check: ap.error("give --note <path> (fill) or --check <path>")
    check = a.check is not None
    path = os.path.abspath(a.check or a.note)
    if not os.path.isfile(path): sys.exit(f"{path}: not found")
    note = Note(path)
    write = not check and not a.dry_run
    rep = Report()
    dest = a.dest_dir
    if not dest:
        d = os.path.dirname(path)
        dest = d if os.path.basename(d) in ("books", "videos") else os.path.join(ROOT, "books")
    recs = scan_sources(a.sources, a.recursive) if a.sources else []
    docs = group_docs(recs)
    readmes = [parse_readme(p) for p in find_readmes(a.sources, a.readme)] if a.sources else []
    rm_hits = {d["stem"]: readme_lookup(d, readmes) for d in docs}
    if docs:
        rep.hint(f"sources: {len(recs)} files in {len(docs)} documents; README{'s' if len(readmes) != 1 else ''}: {', '.join(os.path.relpath(r['path'], ROOT) for r in readmes) or 'none found'}; "
                 f"README rows matched for {sum(1 for v in rm_hits.values() if v)} of {len(docs)}")
        for d in docs:
            for f in d["files"]:
                if f["note"]: rep.hint(f"sources: {f['name']}: {f['note']}")
    do_metadata(note, docs, readmes, dest, rep, write, a.force, rm_hits)
    do_inventory(note, docs, readmes, dest, rep, write, rm_hits, [os.path.abspath(s) for s in a.sources], a.inventory_under, check)
    audit = do_audit(note, rep, write, a.force)
    if a.onboard:
        if not os.path.isfile(a.onboard): sys.exit(f"--onboard {a.onboard}: not found")
        if check: rep.hint("cross-checks: --onboard is used in fill mode; check mode reports only what is in the note")
        else: do_xc(note, os.path.abspath(a.onboard), a.accept, dest, rep, write, a.reset_xc)
    fills = sum(l.count(FILL) for l in note.lines)
    if fills: (rep.diff if check else rep.hint)(f"{fills} `{FILL}` marker(s) in the note" + (" (fill them before report_check)" if check else ""))
    if a.report: check_report(note, a.report, audit, rep)
    if write and rep.writes:
        LN.write_lines(path, note.lines)
        rep.lines.append(f"saved {os.path.relpath(path, ROOT)}")
    elif a.dry_run: rep.lines.append("dry run: nothing saved")
    rep.dump()
    if check: sys.exit(1 if rep.diffs else 0)

if __name__ == "__main__":
    main()
