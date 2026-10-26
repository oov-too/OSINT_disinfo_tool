"""The parser library (phase 2 of tools/platform-plan.md, 2026-10-22): one module that reads a ledger page in the house form
(a note under videos/ or books/, a register or a narrative page under research/) and gives it back as lines, headings, sections,
tables with their rows and line numbers, the metadata table, the schema sections of tools/schema.md, and the citations and links
in every form the tools write. Every tool that parses a note calls this module; wip/platform-phase2/inventory.md lists the forms
(F, S, T, M, Q, C, L, R, U) and which tool used which before the library existed.

Portability (tools/platform-plan.md, Portability): readers normalise line endings (CRLF and a lone CR become LF) and drop a
leading byte-order mark; writers emit LF and UTF-8 whatever the platform. Citations are line numbers and the verbatim gate
matches text, so a note edited on Windows must parse exactly as one edited here.

The forms are kept exactly as the tools had them, including where two tools read a section or a table differently (a prefix
match against an exact one, the first table against every pipe line of a body): a tool's output must not change because its
parsing moved here. Each function's docstring names its form and the tools that use it.
"""
import os, re
from functools import cached_property

# ============================================================================================================ read and write
def normalise(text):
    """CRLF and lone CR to LF; a leading byte-order mark dropped (portability rule: readers normalise)."""
    if text.startswith("﻿"): text = text[1:]
    if "\r" in text: text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def read_text(path, errors="strict"):
    """The file as UTF-8 text with line endings normalised."""
    with open(path, encoding="utf-8", errors=errors, newline="") as f:
        return normalise(f.read())


def read_lines(path, errors="strict"):
    """read_text split on LF (the `text.split("\\n")` every tool uses: a trailing newline leaves a final empty element)."""
    return read_text(path, errors).split("\n")


def iter_lines(path, errors="strict"):
    """Line by line with the newline kept, as `for line in open(path)` yields them (split on LF only)."""
    text = read_text(path, errors)
    parts = text.split("\n")
    for i, p in enumerate(parts):
        if i < len(parts) - 1: yield p + "\n"
        elif p: yield p


def read_head(path, n, errors="strict"):
    """The first n characters after line-ending translation (a provenance header), as `open(path).read(n)` counts them."""
    with open(path, encoding="utf-8", errors=errors, newline=None) as f:
        return normalise(f.read(n))


def first_line(path, errors="strict"):
    """The first line with its newline, as `open(path).readline()` gives it (only that line is decoded)."""
    with open(path, encoding="utf-8", errors=errors, newline="") as f:
        line = f.readline()
    if line.startswith("﻿"): line = line[1:]
    if line.endswith("\r\n"): line = line[:-2] + "\n"
    elif "\r" in line:
        line = line.split("\r", 1)[0] + "\n"
    return line


def write_text(path, text):
    """Write UTF-8 with LF line endings on every platform (portability rule: writers emit LF)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def open_write(path):
    """A text file opened for writing, UTF-8 with LF endings (for json.dump and other writers that take a file)."""
    return open(path, "w", encoding="utf-8", newline="\n")


def open_append(path):
    """A text file opened for appending, UTF-8 with LF endings (logs, queues, JSON-lines checkpoints)."""
    return open(path, "a", encoding="utf-8", newline="\n")


def append_text(path, text):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_lines(path, lines):
    write_text(path, "\n".join(lines))


# ============================================================================================================ rows (F)
SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")


def cells(line):
    """F1: the cells of a table row, or None when the stripped line does not start with a pipe (build_db, note_fill, note_skeleton)."""
    s = line.strip()
    if not s.startswith("|"): return None
    return [p.strip() for p in s.strip("|").split("|")]


def split_row(line):
    """F2: the cells without the pipe test (narratives, context_pack, timeline_insert, intake_gate, first_utterance and others)."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def split_spaced(line):
    """F2b: `line.split(" | ")`, the end cells keeping their outer pipes (writers that rebuild a row in place)."""
    return line.split(" | ")


def is_sep(line):
    """F3: a separator line `|---|---|` (build_db, note_fill, note_skeleton)."""
    return bool(SEP_RE.match(line))


def is_sep_cells(cs):
    """F3b: every cell made of `-`, `:` and spaces (narratives, context_pack, narrative_apply)."""
    return all(set(c) <= set("-: ") for c in cs)


def join_row(cs):
    """A row as the tools write it: `| a | b |`."""
    return "| " + " | ".join(cs) + " |"


# ============================================================================================================ headings and sections (S)
HEADING_RE = re.compile(r"^(#{1,6}) (.+?)\s*$")
H2_LINE_RE = re.compile(r"^##\s+(.+?)\s*$")


def headings(lines):
    """[(level, text, line index)] for every `#` heading (S3; note_skeleton)."""
    out = []
    for i, l in enumerate(lines):
        m = HEADING_RE.match(l)
        if m: out.append((len(m.group(1)), m.group(2), i))
    return out


def section_start(lines, heading):
    """S1: the index of the first line, anywhere, whose stripped lower-cased text starts with `heading` lower-cased (the heading
    includes `## `), or None (build_db; timeline_insert, timeline_relocate, integrate_report)."""
    h = heading.lower()
    for i, l in enumerate(lines):
        if l.strip().lower().startswith(h): return i
    return None


def h2_end(lines, start):
    """The index of the next line starting `## ` after `start`, or len(lines)."""
    j = start + 1
    while j < len(lines) and not lines[j].startswith("## "): j += 1
    return j


def section_bounds(lines, prefix):
    """S2: (start, end) of the first `## ` line whose stripped lower-cased text starts with the prefix; end is the next `## ` line
    (exclusive), or None (note_fill)."""
    hp = prefix.lower()
    for i, l in enumerate(lines):
        if l.strip().lower().startswith(hp) and l.startswith("## "):
            return i, h2_end(lines, i)
    return None


def section_span(lines, heading, level=2, heads=None):
    """S3: (start, end) of the first heading of `level` whose text is exactly `heading`; end is the next heading of the same or a
    higher level (exclusive), or None (note_skeleton)."""
    hs = heads if heads is not None else headings(lines)
    for k, (lv, t, i) in enumerate(hs):
        if lv == level and t == heading:
            end = len(lines)
            for lv2, t2, i2 in hs[k + 1:]:
                if lv2 <= level: end = i2; break
            return i, end
    return None


_H2_ANY = re.compile(r"^## ", re.M)


def section_text(txt, heading, latest=False):
    """S4: the body of the first (latest=True: the last) `## <heading>...` line, case-sensitive prefix, to the next `## ` line;
    "" when absent (narratives, context_pack, adoption_check through narratives)."""
    rx = re.compile(r"^## " + re.escape(heading) + r"[^\n]*\n", re.M)
    if latest:
        ms = list(rx.finditer(txt))
        if not ms: return ""
        m = ms[-1]
    else:
        m = rx.search(txt)
        if not m: return ""
    body = txt[m.end():]; e = _H2_ANY.search(body)
    return body[:e.start()] if e else body


def section_match(txt, heading, latest=False):
    """The S4 heading match itself (the heading line with its newline) and the body, or (None, "")."""
    rx = re.compile(r"^## " + re.escape(heading) + r"[^\n]*\n", re.M)
    ms = list(rx.finditer(txt)) if latest else [m for m in [rx.search(txt)] if m]
    if not ms: return None, ""
    m = ms[-1]; body = txt[m.end():]; e = _H2_ANY.search(body)
    return m, (body[:e.start()] if e else body)


def section_text_until(txt, heading, stop_re=r"^## "):
    """S4 with a caller's stop pattern; None when the heading is absent (narrative_apply)."""
    m = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n", txt, re.M)
    if not m: return None
    body = txt[m.end():]; e = re.search(stop_re, body, re.M)
    return body[:e.start()] if e else body


_H2_FULL = re.compile(r"^## ([^\n]*)\n", re.M)


def sections_text(txt):
    """S5: [(heading text stripped, body)] for every `## ` section in order (adoption_check)."""
    heads = list(_H2_FULL.finditer(txt)); out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
        out.append((m.group(1).strip(), txt[m.end():end]))
    return out


def split_sections(txt):
    """S5b: {heading: body} by `re.split(r"^(## [^\\n]+)\\n", ...)` (build_narrative_viewer)."""
    out = {}; parts = re.split(r"^(## [^\n]+)\n", txt, flags=re.M)
    for i in range(1, len(parts), 2): out[parts[i][3:].strip()] = parts[i + 1]
    return out


def line_sections(lines):
    """S6: {1-based line number: the title of the `## ` section it is in} ("(head)" before the first) (intake_gate)."""
    sec = {}; cur = "(head)"
    for i, l in enumerate(lines, 1):
        m = H2_LINE_RE.match(l)
        if m: cur = m.group(1)
        sec[i] = cur
    return sec


# ============================================================================================================ tables (T)
class Table:
    """A table: the header line's index, its cells, and the rows as (line index, cells)."""
    __slots__ = ("header_line", "header", "rows")

    def __init__(self, header_line, header, rows):
        self.header_line, self.header, self.rows = header_line, header, rows

    @property
    def row_lines(self): return [i for i, _ in self.rows]

    @property
    def row_cells(self): return [c for _, c in self.rows]

    @property
    def end(self): return (self.rows[-1][0] + 1) if self.rows else self.header_line + 2

    def __repr__(self): return f"Table(line {self.header_line + 1}, {len(self.header)} columns, {len(self.rows)} rows)"


def _header_ok(hcells, header_prefix):
    hdr = [h.lower() for h in hcells]
    return all(any(h.startswith(p) for h in hdr) for p in header_prefix)


def find_table(lines, start, header_prefix, end=None):
    """T1: the first table at or after `start` whose lower-cased header cells start with every prefix given; the header is a row
    followed by a separator line; rows run while the line is a row; the scan stops at the next `## ` line after `start` (or at
    `end`). None when there is none (build_db's find_table, note_fill's Note.table)."""
    if end is None: end = len(lines)
    i = start
    while i < end:
        if lines[i].startswith("## ") and i > start: break
        c = cells(lines[i])
        if c and i + 1 < len(lines) and is_sep(lines[i + 1]):
            if _header_ok(c, header_prefix):
                rows = []; j = i + 2
                while j < end:
                    r = cells(lines[j])
                    if r is None: break
                    rows.append((j, r)); j += 1
                return Table(i, c, rows)
        i += 1
    return None


def tables(lines, start, end):
    """T1b: every table in lines[start:end]: header row + separator inside the range, rows while the line is a row; the scan
    resumes after each table (note_skeleton's tables(), note_fill's README reader with start=0, end=len)."""
    out = []; i = start
    while i < end:
        c = cells(lines[i])
        if c and i + 1 < end and is_sep(lines[i + 1]):
            rows = []; j = i + 2
            while j < end and cells(lines[j]):
                rows.append((j, cells(lines[j]))); j += 1
            out.append(Table(i, c, rows)); i = j
        else: i += 1
    return out


def loose_table(body, with_lines=False):
    """T2: every line of `body` starting with `|`; the first is the header (lower-cased); separator rows (F3b) are skipped; rows as
    dicts keyed by the header (zip, so a short row has fewer keys). with_lines=True gives (line, dict) pairs (narrative_apply).
    (narratives.table, the Nodes, Contradiction ledger and Revision tables.)"""
    hdr, rows = None, []
    for line in body.split("\n"):
        if not line.startswith("|"): continue
        cs = [c.strip() for c in line.strip().strip("|").split("|")]
        if hdr is None: hdr = [c.lower() for c in cs]; continue
        if is_sep_cells(cs): continue
        rows.append((line, dict(zip(hdr, cs))) if with_lines else dict(zip(hdr, cs)))
    return (hdr, rows) if with_lines else rows


def first_table(body):
    """T2b: T2 limited to the first table: the first non-pipe line after the header ends it (context_pack's md_table_rows)."""
    hdr, rows, started = None, [], False
    for line in body.split("\n"):
        if not line.startswith("|"):
            if started: break
            continue
        cs = [c.strip() for c in line.strip().strip("|").split("|")]
        if hdr is None: hdr = [c.lower() for c in cs]; started = True; continue
        if is_sep_cells(cs): continue
        rows.append(dict(zip(hdr, cs)))
    return rows


def hash_table_bounds(lines, heading_lower):
    """T3: for the first line whose stripped lower-cased text starts with `heading_lower` (S1): (section start, header line, first
    row, end) where the header is the first line from the section start that starts `| # |` and the rows run while a line starts
    with `|` (timeline_insert, timeline_relocate). Raises StopIteration when there is no `| # |` line, as the tools did."""
    s = section_start(lines, heading_lower)
    if s is None: return None
    h = next(i for i in range(s, len(lines)) if lines[i].startswith("| # |"))
    st = h + 2; en = st
    while en < len(lines) and lines[en].startswith("|"): en += 1
    return s, h, st, en


# ============================================================================================================ metadata (M)
META_TEXT_RE = re.compile(r"^\| \*\*([^*]+)\*\* \| (.*?) \|\s*$", re.M)


def meta_rows(lines, limit=80):
    """M1: [(key, value, line index)] for the two-cell rows with a bold first cell in the first `limit` lines; key is the cell with
    the asterisks and spaces stripped, value the second cell (build_db 80, note_skeleton 80, note_fill 120)."""
    out = []
    for i, l in enumerate(lines[:limit]):
        c = cells(l)
        if c and len(c) == 2 and c[0].startswith("**"):
            out.append((c[0].strip("*").strip(), c[1], i))
    return out


def meta_text(txt):
    """M2: {key: value} by `^\\| \\*\\*([^*]+)\\*\\* \\| (.*?) \\|\\s*$` over the whole text, the last row of a key winning (narratives.meta)."""
    d = {}
    for m in META_TEXT_RE.finditer(txt): d[m.group(1).strip()] = m.group(2).strip()
    return d


def meta_value(txt, key):
    """M2b: the value of one bold key by `\\| \\*\\*<key>\\*\\* \\| (.+?) \\|$` (first match, re.M), "" when absent (build_index)."""
    r = re.search(r"\| \*\*%s\*\* \| (.+?) \|$" % key, txt, re.M)
    return r.group(1).strip() if r else ""


def title_line0(lines, default):
    """M3: the H1 when the first line is `# ...` (build_db), else default."""
    m = re.match(r"# (.+)", lines[0]) if lines else None
    return m.group(1).strip() if m else default


def title_any(txt, default=None):
    """M3b: the text of the first line starting `# ` anywhere (build_db pages, build_narrative_viewer); default when none."""
    return next((l[2:].strip() for l in txt.split("\n") if l.startswith("# ")), default)


def title_re(txt):
    """M3c: `^# (.+)$` (re.M) stripped; raises AttributeError when absent, as build_index did."""
    return re.search(r"^# (.+)$", txt, re.M).group(1).strip()


# ============================================================================================================ fixed lines and cells (Q)
QUOTE_RE = re.compile(r"^\s*(\d+)\.\s*\(([\d:]+(?:\s*(?:to|,)\s*[\d:]+)*)\)\s*(.*)$")
# a document note's locator (a page, paragraph, section or appendix: `(p. 17, App. 4 §1.10)`), taken only when the quotation mark follows it
# (the pilot's document notes, 2026-10-23; no item of the first corpus's notes changes)
QUOTE_LOC_RE = re.compile(r"^\s*(\d+)\.\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*([\"“].*)$")
QUOTE_ITEM_RE = re.compile(r"^\d+\. \(")
COUNTS_RE = re.compile(r"Audit counts: open (\d+), partial (\d+), closed-outright (\d+), closed-subtle (\d+), stated declines (\d+), pseudo-declines (\d+)\.")
ROW_ID_RE = re.compile(r"\d+(\.\d+)?")
SORTABLE_RE = re.compile(r"~?\s*(-?\d{1,9})(?:-(\d{2}))?(?:-(\d{2}))?")
UNDATED_KEY = "9999999999-99-99"


TRAILING_PTR_RE = re.compile(r"(?:\s*\[u \d{3}:\d+(?:-\d+)?\])+\s*$")


def attribution_chain(note):
    """Q4: (attribution, chain) from a claims row's Note cell (schema section 2): `attribution: ...; chain: ...` with the chain cut
    at its origin parenthetical's closing period; attribution alone when there is no chain (build_db)."""
    attr = chain = ""
    m = re.search(r"attribution:\s*(.*?);\s*chain:\s*(.*)", note, re.S)
    if m:
        attr = m.group(1).strip()
        rest = TRAILING_PTR_RE.sub("", m.group(2))   # a staged note's unit pointer after an unclosed chain is not part of it (2026-10-23)
        mc = re.search(r"^(.*?\))\.(?:\s|$)", rest, re.S) or re.search(r"^(.*?\))\s*$", rest, re.S)
        chain = (mc.group(1) if mc else rest.split(". ")[0]).strip().rstrip(".")
    elif re.search(r"attribution:", note):
        attr = re.split(r"attribution:\s*", note, 1)[1].split(". ")[0].strip().rstrip(".")
    return attr, chain


def xc_markers(note):
    """Q5: (point, settled, revised, was) from a cross-check's Note cell (schema section 10), "" where absent (build_db)."""
    def mk(rx):
        m = re.search(rx, note, re.I)
        return m.group(1).strip() if m else ""
    return (mk(r"(?:^|;\s*)point\s*:\s*([a-z]+)"), mk(r"settled\s+(\d{4}-\d{2}-\d{2})"), mk(r"revised\s+(\d{4}-\d{2}-\d{2})"), mk(r"\bwas\s*:\s*([a-z\-]+)"))


def sort_key(sortable):
    """Q6: a timeline Sortable cell to the sort key: year + 1,000,000,000 as ten digits, then -MM-DD (00 when absent), so BC and
    deep-past years order correctly; UNDATED_KEY when no year (build_db, timeline_insert; schema section 11)."""
    m = SORTABLE_RE.match(sortable.strip())
    if not m: return UNDATED_KEY
    yv = max(-999_999_999, min(int(m.group(1)), 8_000_000_000))
    return f"{yv + 1_000_000_000:010d}-{m.group(2) or '00'}-{m.group(3) or '00'}"


def date_key(d, end=False):
    """Q6b: YYYY, YYYY-MM or YYYY-MM-DD to the sort-key encoding; end=True fills a missing month or day to the end of the range;
    None when the text is not a date (rows_search --from/--to)."""
    m = re.fullmatch(r"(-?\d{1,9})(?:-(\d{2}))?(?:-(\d{2}))?", d.strip())
    if not m: return None
    y = int(m.group(1)); mo = m.group(2) or ("12" if end else "00"); da = m.group(3) or ("31" if end else "00")
    return f"{y + 1_000_000_000:010d}-{mo}-{da}"


# ============================================================================================================ citations and links (C, L)
CITE_RE = re.compile(r"\[([a-z0-9-]+) (tl|claims|audit) ([\d.]+(?:\s*,\s*[\d.]+)*)\]")             # C1
CITE_ONE_RE = re.compile(r"\[([a-z0-9-]+) (tl|claims|audit) ([\d.]+)\]")                             # C2
ROW_REF_RE = re.compile(r"\[?([a-z0-9-]+) (tl|claims|audit|xc) ([\d.]+)\]?")                         # C3
CITE_XC_RE = re.compile(r"\[([a-z0-9-]+) (tl|claims|audit|xc) ([\d.]+)\]")                           # C4
SHORT_CITE_RE = re.compile(r"(?:\[(?P<note>[a-z0-9-]{4,}|same) )?\b(?P<kind>tl|claims|audit|xc) (?P<ns>[\d.]+(?:\s*,\s*[\d.]+)*)\]?")  # C5
CITE_KIND = {"claims": "claims", "tl": "tl", "audit": "audit", "quote": "quote", "people": "people"}


def citations(txt):
    """C1 with comma lists expanded: [(note, kind, n)] in order (narratives.citations)."""
    out = []
    for m in CITE_RE.finditer(txt):
        for n in re.split(r"\s*,\s*", m.group(3)): out.append((m.group(1), m.group(2), n))
    return out


def cite(kind, video, n):
    """C6: the citation form the agents write: `[<stem> claims N]`, `[<stem> tl N]`, `[<stem> audit N]`, `[<stem> quote N]`,
    `[<stem> people <name>]` (rows_search)."""
    return f"[{video} {CITE_KIND[kind]} {n}]"


PAGE_LINK_RE = re.compile(r"\]\((?:\.\./)?(videos|books|research)/([^)#/]+?)\.md")                   # L1 build_db
LOCAL_LINK_RE = re.compile(r"\]\((\.\.?/[^)#]+|[a-zA-Z0-9_./-]+\.(?:md|png|svg|json))(#[^)]*)?\)")    # L2 integrate_report
NOTE_LINK_RE = re.compile(r"\]\((?:\.\./)?(?:videos|books)/([^)#]+)\.md")                             # L3 reopen_check
NOTE_STEM_LINK_RE = re.compile(r"\]\((?:\.\./videos/|\.\./books/)?([a-z0-9\-]+)\.md")                 # L4 divergences
NOTE_SLUG_RE = re.compile(r"\((?:\.\./)?(?:videos/|books/)?([a-z0-9\-]+)\.md")                        # L5 echoes
SOURCE_LINK_RE = re.compile(r"\]\((?:\.\./)?(?:books/)?(sources/[^)#\s]+?\.(txt|md|pdf|png|jpg|jpeg|webp))(?:#page=(\d+))?\)", re.I)  # L6 build_graph_data
MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")                                                            # L7 note_fill Transcript
ELSEWHERE_RE = re.compile(r"\]\(([^)]+)\)\s*(.*)$")                                                    # L8 note_fill xc_key
SUBJECT_LINK_RE = re.compile(r"\]\(\.\./subjects/([a-z0-9-]+)\.md\)")                                  # L9 build_db
SWEEP_NOTE_RE = re.compile(r"\]\(\.\./videos/([^)]+?)\.md\)")                                          # L10 onboard_check
ANY_NOTE_LINK_RE = re.compile(r"\]\((?:\.\./)?(?:(?:videos|books)/)?([^)#/]+?)\.md")                     # L11 build_graph_data (cross-check targets)
NOTE_CITE_LINK_RE = re.compile(r"\]\((?:\.\./)?(?:videos/|books/)?([A-Za-z0-9][^)#/\s]*?)\.md(?:#[^)]*)?\)")  # L12 build_graph_data (note-to-note citations)
RESEARCH_LINK_RE = re.compile(r"\]\((?:\.\./)?research/([^)#/]+?)\.md")                                  # L13 build_graph_data (links to research pages)
NOTE_FILE_LINK_RE = re.compile(r"\]\((?:\.\./)?((?:videos|books)/[^)#\s]+\.md)")                         # L14 build_graph_data (leads' sources)
ROW_NUM_RE = re.compile(r"^\| (\d+) \|", re.M)                                                          # R1


LEAD_ROW_RE = re.compile(r"^\| (\d+) \| (.*?) \|", re.M)                                                # R3 adoption_check


def has_section(txt, heading):
    """S4c: a `## <heading>` line whose heading ends at a word boundary (narratives --check)."""
    return bool(re.search(r"^## " + re.escape(heading) + r"\b", txt, re.M))


def tl_citation_re(slug, old_id):
    """The citation of a timeline row from another page: a link to the note (its slug) followed within 120 characters by `tl N` or
    `timeline N`, N not followed by a decimal digit (timeline_relocate)."""
    return re.compile(r"(" + re.escape(slug) + r"\.md\)[^\n|]{0,120}?\b(?:tl|timeline)\s+)" + re.escape(old_id) + r"(?![\d.]*\d)")


def tl_bare_re(old_id):
    """A bare `tl N` inside the note itself (timeline_relocate)."""
    return re.compile(r"\btl " + re.escape(old_id) + r"(?![\d.]*\d)")


TL_HISTORY_RE = re.compile(r"(\(was tl [\d.]+ until [^)]*\))")


def row_numbers(txt):
    """R1: every `| N |` row number in the text, as ints (registers)."""
    return [int(m) for m in ROW_NUM_RE.findall(txt)]


def row_match(txt, n, tail=r"[^\n]*\n"):
    """R2: the match of the row `| <n> |...` (tail `[^\\n]*\\n` keeps the newline; ` .*$` the integrate and reopen form)."""
    return re.search(r"^\| " + str(n) + (r" \|" + tail), txt, re.M)


# ============================================================================================================ unit pointers (U)
UNIT_PTR_RE = re.compile(r"\[u (\d{3}):(\d+)(?:-(\d+))?\]")
UNIT_MARK_RE = re.compile(r"\[u (\d{3})")
INVENTORY_CODE_RE = re.compile(r"^\|\s*([A-Z]{1,3}\d{1,3}[a-z]?)\s*\|\s*(.+?)\s*\|")
CLAIMS_ROW_RE = re.compile(r"^\|\s*\d+(?:\.\d+)?\s*\|")


# ============================================================================================================ the actor and polity register (A)
# The pack's [actors] register page in the core form: actor rows (a header beginning `#` with a Polity column and a chain column, and
# the headerless continuation tables of the same width whose first cell is a row id) and polity statements (a header with Inside
# and Opposed columns). Read by tools/build_db.py into the actors and polity_statements tables; the parse and the placement rules
# were tools/build_graph_data.py's (_tg_tables and the order-of-battle reading, phase 5), moved here unchanged (2026-10-22).
ACTOR_ID_RE = re.compile(r"[A-Z]?\d+[a-z]?")
CLUSTER_CODE_RE = re.compile(r"\b[A-Z]+(?:-[A-Z]+)?\d+\b")
CLUSTER_ROW_RE = re.compile(r"[A-Z]+(?:-[A-Z]+)?\d+")
OOB_ROLE_RE = re.compile(r"(member|outside|opposed|subordinate)\b\s*(?:to|of)?\s*[:,]?\s*(.*)", re.I)
BODY_KIND_RE = re.compile(r"([a-z][a-z /-]{1,30}?)\s*:\s*(.*)", re.I)


def _register_table_kind(h):
    low = [x.lower() for x in h]
    if any(x.startswith("inside") for x in low) and any(x.startswith("opposed") for x in low): return "stm"
    if any(x.startswith("polity") for x in low) and any("chain" in x for x in low) and low[0] == "#": return "act"
    return None


def actor_register(path, errors="strict"):
    """A: (actor rows, polity statements) of the register page, each a list of (line number, the heading the table sits under,
    {column header: cell}). A headerless continuation table takes the last actor table's header when its width matches and its first
    cell is a row id; any other table is skipped. tools/build_db.py (the reading tools/build_graph_data.py's _tg_tables had)."""
    act, stm, cur, last_act, head = [], [], None, None, ""
    for ln, line in enumerate(iter_lines(path, errors) if path and os.path.exists(path) else [], 1):
        if not line.startswith("|"):
            cur = None
            if line.startswith("#"): head = line.strip().lstrip("#").strip()
            continue
        c = split_row(line)
        if cur is None:
            k = _register_table_kind(c)
            if k: cur = (k, c); last_act = c if k == "act" else last_act; continue
            if last_act and len(c) == len(last_act) and ACTOR_ID_RE.fullmatch(c[0] or ""): cur = ("act", last_act)
            else: cur = ("skip", c); continue
        if cur[0] == "skip" or set("".join(c)) <= set("-: "): continue
        (act if cur[0] == "act" else stm).append((ln, head, {h: (c[i] if i < len(c) else "") for i, h in enumerate(cur[1])}))
    return act, stm


def reg_col(row, *prefixes):
    """A: the first cell whose header begins with one of the prefixes (lower case), else ""."""
    for h, v in row.items():
        if h.lower().startswith(prefixes): return v
    return ""


def reg_col_has(row, word):
    """A: the first cell whose header contains the word (lower case), else ""."""
    for h, v in row.items():
        if word in h.lower(): return v
    return ""


def reg_kind_cell(row):
    """A: an actor row's second cell (the kind as the teller names it)."""
    return list(row.values())[1] if len(row) > 1 else ""


def polity_names(polities):
    """A: {code: name} from a pack's declared polities (pack.toml [actors] polities, each `<code> <name>`: `P1 the state`), the code set
    of a pack that keeps no clusters page (the pilot pack, 2026-10-23)."""
    out = {}
    for p in polities or []:
        m = re.match(r"^\s*([A-Z]+(?:-[A-Z]+)?\d+)\s+(.*\S)", str(p))
        if m and m.group(1) not in out: out[m.group(1)] = m.group(2)
    return out


def cluster_names(path, errors="strict"):
    """A: {code: name} from the first column of the clusters page's tables (codes like B1 or GD-B1; the name is the second cell's
    first clause, markup and links removed, at most 70 characters); the first definition of a code wins."""
    out = {}
    for line in (iter_lines(path, errors) if path and os.path.exists(path) else []):
        if not line.startswith("|"): continue
        c = split_row(line)
        if len(c) > 1 and CLUSTER_ROW_RE.fullmatch(c[0]) and c[0] not in out: out[c[0]] = re.split(r";", re.sub(r"\*+|\[[^\]]*\]", "", c[1]))[0].strip()[:70]
    return out


def polity_norm(t):
    """A: a polity name as a key: quotes and markup dropped, spaces folded, end punctuation stripped, lower case, 80 characters."""
    return re.sub(r"\s+", " ", re.sub(r"[\"'“”‘’*`]", "", t or "")).strip(" .,;:-").lower()[:80]


class ActorPlacer:
    """A: the order-of-battle reading of the register. An actor is a cluster code the clusters page defines: a row's own codes in its
    cluster column, else the actor vocabulary (the pack's kinds of being with their aliases) matched in its kind cell, each word taken
    to the cluster the single-coded rows that carry it are most often filed under (ties to the lower code). A polity cell or statement
    whose head is empty or begins with one of the `unplaced` words places nothing."""

    def __init__(self, clusters, actors, aliases, unplaced, act_rows=(), polity_codes=False):
        self.clusters = clusters
        self.polity_codes = polity_codes   # the codes are the pack's declared polities (no clusters page): a row is placed by its polity cell
        def forms(name, al):
            out = set()
            for f in {name, *al}:
                out.add(f)
                if f.lower().endswith("ies"): out.add(f[:-3] + "y")
                elif f.lower().endswith("s") and len(f) > 3: out.add(f[:-1])
            return out
        self.rx = [(a, re.compile(r"(?<![A-Za-z])(?:" + "|".join(sorted(map(re.escape, forms(a, aliases.get(a, []))), key=lambda x: (-len(x), x))) + r")s?(?![A-Za-z])", re.I)) for a in actors]
        self.unplaced_words = [x.lower() for x in unplaced]
        counts = {}
        for row in act_rows:
            cs = self.codes_in(reg_col_has(row, "cluster"))
            if len(cs) == 1:
                for w in self.vocabulary_in(reg_kind_cell(row)): counts.setdefault(w, {}).setdefault(cs[0], 0); counts[w][cs[0]] += 1
        self.word_cluster = {w: min(c.items(), key=lambda kv: (-kv[1], kv[0]))[0] for w, c in counts.items()}

    def codes_in(self, text):
        return [x for x in dict.fromkeys(CLUSTER_CODE_RE.findall(text or "")) if x in self.clusters]

    def vocabulary_in(self, text):
        return [a for a, rx in self.rx if rx.search(text or "")]

    def actors_of(self, text, cluster_cell=""):
        return [*self.codes_in(cluster_cell)] or [x for x in dict.fromkeys(self.word_cluster.get(w) for w in self.vocabulary_in(text)) if x]

    def unplaced(self, head):
        low = polity_norm(head)
        return (not low) or any(low == u or (u and re.match(re.escape(u) + r"\b", low)) for u in self.unplaced_words)

    def place_actor_row(self, row):
        """{codes, placed (the clusters), placed_by (cluster code, vocabulary or unplaced), role, polity} for one actor row; role and
        polity are "" when the row is unplaced or its polity cell places nothing."""
        codes = self.codes_in(reg_col_has(row, "cluster"))
        acts = self.actors_of(reg_kind_cell(row), reg_col_has(row, "cluster"))
        out = dict(codes=codes, placed=acts, placed_by=("cluster code" if codes else "vocabulary") if acts else "unplaced", role="", polity="")
        if not acts and self.polity_codes:   # a pack with no clusters page: the polity codes the row's polity cell names place it
            pc = self.codes_in(reg_col(row, "polity"))
            if pc: out.update(codes=pc, placed=pc, placed_by="polity code", role="member", polity="; ".join(self.clusters[c] for c in pc))
            return out
        if not acts: return out
        head = re.split(r";", reg_col(row, "polity"))[0].strip()
        if not self.unplaced(head):
            m = OOB_ROLE_RE.match(head)
            role = m.group(1).lower() if m else "placed"; name = (m.group(2) if m else head)
            name = re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()
            if name and not self.unplaced(name): out.update(role=role, polity=name)
        return out

    def place_statement(self, row):
        """{body_kind, polity, member, outside, opposed} for one polity statement: the body's kind and name from the Body cell's head
        ("kind: name"), and the clusters each of the Inside, Outside and Opposed cells places; polity is "" (and nothing is placed)
        when the body's head or name places nothing."""
        head = re.split(r";", reg_col(row, "body"))[0].strip()
        m = BODY_KIND_RE.match(head)
        bkind = (m.group(1).strip().lower() if m else "other"); name = (m.group(2) if m and m.group(2).strip() else head)
        out = dict(body_kind=bkind, polity="", member=[], outside=[], opposed=[])
        if self.unplaced(head) or self.unplaced(name): return out
        out["polity"] = name
        for role, cell in (("member", reg_col(row, "inside")), ("outside", reg_col(row, "outside")), ("opposed", reg_col(row, "opposed"))):
            if not self.unplaced(cell): out[role] = self.actors_of(cell)
        return out


# ============================================================================================================ the note object
class Note:
    """A page parsed once: text, lines, headings, sections, tables, metadata, citations. Every accessor is computed on first use
    and cached; the forms are those named above (S1 to S6, T1 to T3, M1)."""

    def __init__(self, path=None, text=None, errors="strict"):
        self.path = path
        self.text = normalise(text) if text is not None else read_text(path, errors)
        self.lines = self.text.split("\n")

    # ---- structure
    @cached_property
    def headings(self):
        return headings(self.lines)

    @cached_property
    def sections(self):
        """[(heading text, start line, end line)] for every `## ` line, end at the next `## ` line (exclusive)."""
        out = []
        for i, l in enumerate(self.lines):
            if l.startswith("## "): out.append((l[3:].strip(), i, h2_end(self.lines, i)))
        return out

    @cached_property
    def section_lines(self):
        """[(heading text after `## ` stripped, 1-based line)] as build_db stores them in `sections`."""
        return [(h, i + 1) for h, i, _ in self.sections]

    def section_start(self, heading):
        return section_start(self.lines, heading)

    def section(self, prefix):
        return section_bounds(self.lines, prefix)

    def span(self, heading, level=2):
        return section_span(self.lines, heading, level, self.headings)

    def section_text(self, heading, latest=False):
        return section_text(self.text, heading, latest)

    # ---- tables
    def find_table(self, start, header_prefix, end=None):
        return find_table(self.lines, start, header_prefix, end)

    def tables(self, start=0, end=None):
        return tables(self.lines, start, len(self.lines) if end is None else end)

    def table_in(self, heading, header_prefix, legacy=()):
        """The schema table under `## heading` (S1, then legacy headings in turn) by T1: (section start, Table or None), or (None, None)."""
        s = self.section_start(heading)
        for h in legacy:
            if s is not None: break
            s = self.section_start(h)
        if s is None: return None, None
        return s, self.find_table(s, header_prefix)

    def block(self, name, start=0, end=None):
        """Line indices (s, e) of `<!-- name:start ...` ... `<!-- name:end -->` within the range, or None (note_fill's generated blocks)."""
        end = len(self.lines) if end is None else end
        s = e = None
        for i in range(start, end):
            t = self.lines[i].strip()
            if s is None and t.startswith(f"<!-- {name}:start"): s = i
            elif s is not None and t == f"<!-- {name}:end -->": e = i; break
        return (s, e) if s is not None and e is not None else None

    # ---- metadata, citations
    def meta_rows(self, limit=80):
        return meta_rows(self.lines, limit)

    @cached_property
    def citations(self):
        return citations(self.text)

    @cached_property
    def words(self):
        return len(self.text.split())

    def save(self, path=None):
        """Write the lines back with LF endings."""
        write_lines(path or self.path, self.lines)


# ============================================================================================================ the schema parse
OQ_STATUS = ("open", "checked", "closed", "standing", "superseded")
XC_KIND = ("answers", "corroborates", "contradicts", "extends", "fills", "chain")
XC_VERDICT = ("direct", "partial", "same-subject", "inference")
CLAIMS_HDR = ("#", "time", "speaker", "topic", "claim", "source", "move")
AUDIT_HDR = ("#", "time", "asked", "question", "answer", "move", "basis")
PEOPLE_HDR = ("name", "role", "time", "relation", "detail")
WORKS_HDR = ("title", "author", "kind", "time")
_OBJECT_WATCH = {}
_OBJECT_LABEL = {}


def object_watch(root=None):
    """(heading, header prefix) of a note's object watch (schema section 6), from the active pack: [objects] watch_heading, and the
    criteria column's first word (criteria_column, lower-cased) in the header; the core's ("## Object watch", "<reference object>
    criteria met") without a pack. Read once per project root (phase 7a: the reference object's name is pack data, not core)."""
    try:
        from . import paths as _P
    except ImportError:
        import paths as _P
    r = root or _P.root()
    if r not in _OBJECT_WATCH:
        heading, column, label = "## Object watch", "<reference object> criteria met", "object watch"
        try:
            import tomllib
            with open(os.path.join(r, "ledger.toml"), "rb") as f: pack = (tomllib.load(f).get("pack") or {}).get("path")
            if pack:
                with open(os.path.join(r, pack, "pack.toml"), "rb") as f: o = tomllib.load(f).get("objects") or {}
                heading, column = o.get("watch_heading", heading), o.get("criteria_column", column)
                with open(os.path.join(r, pack, "pack.toml"), "rb") as f: label = (tomllib.load(f).get("names") or {}).get("section.object_watch") or label
        except (OSError, ValueError, ImportError):
            pass
        _OBJECT_WATCH[r] = (heading, ("time", "object", "witness", "custody", column.split()[0].lower(), "strength", "register"))
        _OBJECT_LABEL[r] = label
    return _OBJECT_WATCH[r]


def object_watch_label(root=None):
    """The object watch's section label in the build report: "object watch", or the pack's [names] "section.object_watch" (7b2)."""
    try:
        from . import paths as _P
    except ImportError:
        import paths as _P
    r = root or _P.root(); object_watch(r)
    return _OBJECT_LABEL[r]
TRACKER_HDR = ("name", "seats", "degree", "kind")
OQ_HDR = ("#", "kind", "question", "bears", "what would settle", "status", "answer", "answered by", "answered on")
XC_HDR = ("#", "kind", "this note", "elsewhere", "verdict", "note")
TL_HDR = ("#", "date", "sortable", "event", "speaker", "chain", "database link", "agreement")
AUDIT_HEADINGS = ("## Candour audit", "## Forthrightness audit")   # the candour audit (schema section 3, renamed 2026-10-22); the legacy heading the notes carry


def parse_note(path, root, note=None):
    """A note in the house schema (tools/schema.md) as the dict tools/build_db.py loads: id, file (relative to root), words, meta,
    subjects, tags, claims (8 cells + attribution, chain), audit (8), counts, people (5), works (5), objects (8, the object watch), quotes (n, time,
    text), cands (5), oq (n + 9), xc (n + 5 + markers), tl (12), sections, report (section, status, rows)."""
    nt = note or Note(path)
    lines = nt.lines; text = nt.text
    vid = os.path.basename(path)[:-3]
    out = {"id": vid, "file": os.path.relpath(path, root), "words": len(text.split()), "meta": {}, "subjects": [], "tags": [],
           "claims": [], "audit": [], "counts": None, "people": [], "works": [], "objects": [], "quotes": [], "cands": [], "oq": [], "xc": [], "tl": [], "sections": [], "report": []}
    out["meta"]["title"] = title_line0(lines, vid)
    for key, val, _ in meta_rows(lines, 80):
        out["meta"][key.lower()] = val
    out["subjects"] = SUBJECT_LINK_RE.findall(out["meta"].get("subjects", ""))
    out["tags"] = [t.strip() for t in out["meta"].get("tags", "").split(",") if t.strip()]
    out["sections"] = list(nt.section_lines)
    def rep(sec, status, n): out["report"].append((sec, status, n))
    def padded(t, n): return [r + [""] * (n - len(r)) for r in t.row_cells]
    # claims ledger
    s, t = nt.table_in("## Claims ledger", CLAIMS_HDR)
    if s is not None:
        if t:
            for r in padded(t, 8):
                attr, chain = attribution_chain(r[7])
                out["claims"].append(r[:8] + [attr, chain])
            rep("claims", "ok", len(t.rows))
        else: rep("claims", "heading found, table not in schema", 0)
    else: rep("claims", "missing", 0)
    # audit
    s, t = nt.table_in(AUDIT_HEADINGS[0], AUDIT_HDR, legacy=AUDIT_HEADINGS[1:])
    if s is not None:
        if t:
            for r in padded(t, 8): out["audit"].append(r[:8])
            rep("audit", "ok", len(t.rows))
        else: rep("audit", "heading found, table not in schema", 0)
        mm = COUNTS_RE.search("\n".join(lines[s:s + 400]))
        if mm: out["counts"] = [int(x) for x in mm.groups()]; rep("audit counts", "ok", 1)
        else: rep("audit counts", "missing", 0)
    else: rep("audit", "missing", 0)
    # people
    s = nt.section_start("## People")
    if s is not None and not lines[s].lower().startswith("## people and works"):
        t = nt.find_table(s, PEOPLE_HDR)
        if t:
            for r in padded(t, 5): out["people"].append(r[:5])
            rep("people", "ok", len(t.rows))
        else: rep("people", "heading found, table not in schema", 0)
    else: rep("people", "missing", 0)
    # works, the object watch (its heading and criteria column are the pack's)
    watch_heading, watch_hdr = object_watch(root)
    for heading, hdr, n, key, label in (("## Works", WORKS_HDR, 5, "works", "works"), (watch_heading, watch_hdr, 8, "objects", object_watch_label(root))):
        s, t = nt.table_in(heading, hdr)
        if s is not None:
            if t:
                for r in padded(t, n): out[key].append(r[:n])
                rep(label, "ok", len(t.rows))
            else: rep(label, "heading found, table not in schema", 0)
        else: rep(label, "missing", 0)
    # quotes
    s = nt.section_start("## Notable quotes")
    if s is not None:
        n = 0
        for l in lines[s + 1:]:
            if l.startswith("## "): break
            mm = QUOTE_RE.match(l) or QUOTE_LOC_RE.match(l)
            if mm: out["quotes"].append((int(mm.group(1)), mm.group(2), mm.group(3).strip())); n += 1
        rep("quotes", "ok" if n else "heading found, no items in schema form", n)
    else: rep("quotes", "missing", 0)
    # tracker candidates
    s, t = nt.table_in("## Tracker candidates", TRACKER_HDR)
    if s is not None and t:
        for r in padded(t, 5): out["cands"].append(r[:5])
        rep("tracker candidates", "ok", len(t.rows))
    # open questions (schema section 9); an empty table is valid for a note that recorded none
    s, t = nt.table_in("## Open questions", OQ_HDR)
    if s is not None:
        if t:
            has_asked = any(h.lower().startswith("asked by") for h in t.header)
            bad = 0
            for r in t.row_cells:
                if not has_asked: r = r[:2] + ["note"] + r[2:]
                r = r + [""] * (10 - len(r))
                try: n = int(r[0])
                except ValueError: n = None
                if not r[6].lower().startswith(OQ_STATUS): bad += 1
                out["oq"].append((n, *r[1:10]))
            rep("open questions", "ok", len(t.rows))
            if bad: rep("open questions status", "not open/checked/closed/standing/superseded", bad)
        else: rep("open questions", "heading found, table not in schema", 0)
    else: rep("open questions", "missing", 0)
    # cross-checks (schema section 10); optional until a retrofit reaches the note, so "missing" is not a schema gap
    s, t = nt.table_in("## Cross-checks", XC_HDR)
    if s is not None:
        if t:
            bad = 0
            for r in padded(t, 6):
                n = r[0].strip() if re.fullmatch(r"\d+(\.\d+)?", r[0].strip()) else None   # split rows carry decimal ids (schema 10, 2026-10-01)
                if r[1].lower() not in XC_KIND or r[4].lower() not in XC_VERDICT: bad += 1
                out["xc"].append((n, *r[1:6], *xc_markers(r[5])))
            rep("cross checks", "ok", len(t.rows))
            if bad: rep("cross checks values", "Kind or Verdict not in schema section 10", bad)
        else: rep("cross checks", "heading found, table not in schema", 0)
    else: rep("cross checks", "missing", 0)
    # dated timeline (schema section 11); optional until the retrofit reaches the note
    s, t = nt.table_in("## Dated timeline", TL_HDR)
    if s is not None:
        if t:
            bad = 0
            for r in padded(t, 8):
                # row IDs are permanent decimal IDs (schema section 11, 2026-09-28): 12, 12.1, 12.15 ...
                n = r[0].strip()
                if not re.fullmatch(r"\d+(\.\d+)?", n): bad += 1; n_sort = None
                else: n_sort = float(n)
                sortable = r[2].strip(); approx = 1 if sortable.startswith("~") else 0
                key = sort_key(sortable)
                ak = r[7].strip().lower().split(":")[0].split(" ")[0] if r[7].strip() else ""
                if ak not in ("matches", "drifts", "contradicts", "new"): bad += 1
                out["tl"].append((n, n_sort, r[1], sortable, key, approx, r[3], r[4], r[5], r[6], r[7], ak))
            rep("timeline", "ok", len(t.rows))
            if bad: rep("timeline values", "Agreement not matches/drifts/contradicts/new, or a row ID not a decimal ID", bad)
        else: rep("timeline", "heading found, table not in schema", 0)
    else: rep("timeline", "missing", 0)
    return out


def register_rows(path, heading, header_prefix, width):
    """A register page's table under `heading` (S1 then T1): [(n, cell 1 .. cell width-1)] for rows whose first cell is an integer,
    padded to `width` cells (build_db: the object register, leads, relations, the ties tracker)."""
    lines = read_lines(path)
    s = section_start(lines, heading)
    t = find_table(lines, s, header_prefix)
    out = []
    for r in (t.row_cells if t else []):
        try: n = int(r[0])
        except Exception: continue
        r = r + [""] * (width - len(r)); out.append((n, *r[1:width]))
    return out
