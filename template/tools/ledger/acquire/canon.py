"""The canon adapter (phase 3 of tools/platform-plan.md, 2026-10-22; the canon layer is core, which texts are the canon and the unit
scheme per text are the pack's): a foundational text held in addressable units, so that a row can cite "Isa 14:12", "II.3.4" or
"p.12 l.4-9" and the citation resolves to the held lines.

A canon hold, sources/canon/<text id>/:
    <source file>    the text as obtained, byte-for-byte (the fetcher's output, or the held file it was copied from)
    <input file>     the fetcher's local input when there was one (e.g. pg10.txt), byte-for-byte; the source is then derived from it
    units.jsonl      derived: one unit per line, {address, levels, start, end, text}; start and end are 1-based line numbers of the
                     source file, so a unit's text is exactly those lines (verbatim citation by line holds)
    scheme.json      derived: the unit scheme used, with its parameters (a re-run with it reproduces units.jsonl)
    README.md, hold.json

Unit schemes (SCHEMES; each a class with units(lines) -> [Unit]):
- verse: one unit per line `[<witness> ]<book> <chapter>:<verse><TAB>text` (the four scripture fetchers' form; the optional
  witness prefix is the scroll acronym of a multi-scroll file). Address "Gen 1:1" or "1QIsaa Is 1:1"; levels book, chapter, verse.
- headings: levels named in order with a regex each for its heading line (part, chapter, section; book, canto; article, clause),
  the text between headings the unit at the deepest level reached; a heading resets the counters below it. Address from a format
  ("{part}.{chapter}.{section}"). This is the scheme for a manifesto, a treatise or a doctrine: see "Adding a text" below.
- lines: every line its own unit (address "L12"), or fixed ranges of n lines ("L1-20"), or blank-line paragraphs ("P7"); the default
  for held text layers whose structure is not yet fixed (packs/ufo/canon/texts.md: the Hermetic, Platonic and grimoire texts).
- page-lines: the house per-page form of a text layer (`--- page N ---`); unit = the page, address "p.N"; cite("p.4 l.3-9") narrows to
  lines within the page.

Fetchers (FETCHERS): tools/fetch_kjv.py, fetch_tanakh.py, fetch_samaritan.py, fetch_isaiah_scroll.py are wrapped by running each as
its own entry point (they execute at import) through ledger.acquire._scripts.run_tool, which redirects their one write
(ledger.paths.new_hold) into a staging folder and refuses any other write: the held books/sources/*.txt are never touched. Their
arguments pass through (--from-dir for a local download, --books, --source, --scroll, --out).

Adding a text (a manifesto, a treatise, a doctrine), with no code change:
1. hold the text (document.py for a PDF or scan, web.py for a page, or a plain file);
2. write a scheme file, packs/<pack>/canon/schemes/<text id>.json:
       {"id": "example-manifesto", "title": "...", "author": "...", "date": "1848",
        "scheme": {"kind": "headings", "levels": [
            {"name": "part",    "pattern": "^(?:PART|Part) ([IVXLC]+|\\\\d+)\\\\b"},
            {"name": "chapter", "pattern": "^(?:CHAPTER|Chapter) (\\\\d+|[IVXLC]+)\\\\b"},
            {"name": "section", "pattern": "^(\\\\d+)\\\\.\\\\s"}],
          "address": "{part}.{chapter}.{section}", "keep_heading": true}}
   (a pattern's first group is the level's label; with no group the level is counted 1, 2, 3 under its parent);
3. python3 tools/ledger/acquire/canon.py hold <file> --scheme packs/<pack>/canon/schemes/<text id>.json
4. check the report: units, levels seen, lines outside any unit (front matter), and resolve a few addresses with `cite`.

    python3 tools/ledger/acquire/canon.py hold <file> --id ID [--title T] [--scheme verse|lines|page-lines|<scheme.json>] [--root DIR]
    python3 tools/ledger/acquire/canon.py fetch kjv|tanakh-wlc|samaritan-pentateuch|isaiah-1qisaa [-- <the fetcher's arguments>]
    python3 tools/ledger/acquire/canon.py cite <hold folder> "Gen 1:1-3"
"""
import json, os, re, sys, tempfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B
from ledger.acquire import _scripts


class Unit:
    __slots__ = ("address", "levels", "start", "end", "text")

    def __init__(self, address, levels, start, end, text):
        self.address = address; self.levels = levels; self.start = start; self.end = end; self.text = text

    def as_dict(self):
        return dict(address=self.address, levels=self.levels, start=self.start, end=self.end, text=self.text)


# ============================================================================================================ unit schemes
class VerseScheme:
    kind = "verse"
    # book, chapter and verse are any non-space labels: a fragment not placed in a book carries the scroll's id as its book and a
    # fragment label as its chapter ("Mur1 Mur1 f6i:1", "5/6hev1a 5/6Hev1a f4:1" in books/sources/judaean-desert-scrolls.txt)
    LINE = re.compile(r"^(?:(?P<witness>\S+) )?(?P<book>\S+) (?P<chapter>[^\s:]+):(?P<verse>[^\s:]+)\t(?P<text>.*)$")

    def __init__(self, **params): self.params = params

    def units(self, lines):
        out = []; self.skipped = []
        for i, l in enumerate(lines, 1):
            m = self.LINE.match(l)
            if not m:
                if l.strip() and not l.startswith("#"): self.skipped.append(i)
                continue
            lv = {k: m.group(k) for k in ("witness", "book", "chapter", "verse") if m.group(k)}
            addr = (lv["witness"] + " " if "witness" in lv else "") + f"{lv['book']} {lv['chapter']}:{lv['verse']}"
            out.append(Unit(addr, lv, i, i, m.group("text")))    # the verse's text; the line itself is lines[start - 1]
        return out

    def describe(self): return dict(kind=self.kind, line=self.LINE.pattern, **self.params)


class HeadingsScheme:
    kind = "headings"

    def __init__(self, levels, address=None, keep_heading=True, **params):
        self.levels = [dict(name=l["name"], pattern=l["pattern"], rx=re.compile(l["pattern"])) for l in levels]
        self.address = address or ".".join("{" + l["name"] + "}" for l in levels)
        self.keep_heading = keep_heading; self.params = params

    def units(self, lines):
        out = []; cur = {}; counters = {}; start = None; body = []; self.skipped = []; self.seen = {l["name"]: 0 for l in self.levels}
        deepest = self.levels[-1]["name"]

        def close(end):
            """A unit is emitted when it has text below its heading, or is at the deepest level (a bare section heading still
            addresses a section); a bare part or chapter heading followed by a lower heading is not a unit of its own."""
            if start is None: return
            text_lines = body
            content = body[1:] if self.keep_heading else body
            at_deepest = deepest in cur
            if text_lines and (any(t.strip() for t in content) or (at_deepest and any(t.strip() for t in text_lines))):
                lv = {l["name"]: cur[l["name"]] for l in self.levels if l["name"] in cur}
                addr = self._addr(lv)
                out.append(Unit(addr, lv, start, end, "\n".join(text_lines)))

        for i, l in enumerate(lines, 1):
            hit = None
            for depth, lev in enumerate(self.levels):
                m = lev["rx"].match(l)
                if m: hit = (depth, lev, m); break
            if hit:
                depth, lev, m = hit
                close(i - 1)
                parent = tuple(cur.get(x["name"]) for x in self.levels[:depth])
                counters[(lev["name"], parent)] = counters.get((lev["name"], parent), 0) + 1
                cur[lev["name"]] = m.group(1) if m.groups() and m.group(1) else str(counters[(lev["name"], parent)])
                for x in self.levels[depth + 1:]: cur.pop(x["name"], None)
                self.seen[lev["name"]] += 1
                start = i; body = [l] if self.keep_heading else []
                if not self.keep_heading: start = i + 1
            elif start is not None:
                body.append(l)
            elif l.strip():
                self.skipped.append(i)
        close(len(lines))
        # a unit with no heading text kept and no body (a heading directly followed by a lower heading) is dropped by close()
        return out

    def _addr(self, lv):
        names = [l["name"] for l in self.levels]
        parts = []
        for n in names:
            if n in lv: parts.append(lv[n])
            else: break
        try:
            return self.address.format(**{n: lv.get(n, "") for n in names}).rstrip(".:,; ") if len(parts) == len(names) else ".".join(parts)
        except (KeyError, IndexError):
            return ".".join(parts)

    def describe(self):
        return dict(kind=self.kind, levels=[dict(name=l["name"], pattern=l["pattern"]) for l in self.levels], address=self.address,
                    keep_heading=self.keep_heading, **self.params)


class LinesScheme:
    kind = "lines"

    def __init__(self, size=1, paragraphs=False, **params):
        self.size = int(size); self.paragraphs = paragraphs; self.params = params

    def units(self, lines):
        out = []; self.skipped = []
        if self.paragraphs:
            n = 0; start = None; buf = []
            for i, l in enumerate(lines + [""], 1):
                if l.strip():
                    if start is None: start = i
                    buf.append(l)
                elif start is not None:
                    n += 1; out.append(Unit(f"P{n}", {"paragraph": str(n)}, start, i - 1, "\n".join(buf))); start = None; buf = []
            return out
        for s in range(0, len(lines), self.size):
            e = min(len(lines), s + self.size)
            addr = f"L{s + 1}" if self.size == 1 else f"L{s + 1}-{e}"
            out.append(Unit(addr, {"line": str(s + 1)}, s + 1, e, "\n".join(lines[s:e])))
        return out

    def describe(self): return dict(kind=self.kind, size=self.size, paragraphs=self.paragraphs, **self.params)


class PageLinesScheme:
    kind = "page-lines"
    HEAD = re.compile(r"^--- page (\d+) ---$")

    def __init__(self, **params): self.params = params

    def units(self, lines):
        out = []; self.skipped = []; page = None; start = None
        for i, l in enumerate(lines, 1):
            m = self.HEAD.match(l)
            if m:
                if page is not None: out.append(self._unit(page, start, i - 1, lines))
                page = m.group(1); start = i + 1
            elif page is None and l.strip():
                self.skipped.append(i)
        if page is not None: out.append(self._unit(page, start, len(lines), lines))
        return out

    @staticmethod
    def _unit(page, start, end, lines):
        while end >= start and not lines[end - 1].strip(): end -= 1    # the blank join line between pages is not page text
        return Unit(f"p.{page}", {"page": page}, start, end, "\n".join(lines[start - 1:end]))

    def describe(self): return dict(kind=self.kind, **self.params)


class NumberedScheme:
    """Numbered paragraphs (a judgment's `[123]`; finding 11 of wip/platform-phase6b/adapter-findings.md; the core form of the pilot
    pack's packs/pilot/canon/paragraphs.py). A line opening with a number (OCR letters O o I l | read as digits, inner spaces
    dropped) and `.` or `,` is a candidate, as is a lone number on its own line followed by text; walking the text in order, a
    candidate starts a paragraph only if its number is the next expected or at most `gap` beyond it (the first must be `first`
    exactly, so dates and case numbers in the front matter cannot start the chain); numbered sub-lists, contents lines and footnotes
    are left as text. `start_after`: a regex for the line after which the text begins (when the first paragraph's number was lost to
    the OCR, the first non-empty line after it is paragraph `first`); `end_before`: a regex for the line where the paragraphs end
    (tail matter after it is outside the units, reported, not folded into the last paragraph). Units are cut on the held lines
    themselves, no line changed or inserted. The report: paragraphs, the last number, the numbers missing from the chain (their text
    stays in the previous unit), the candidates rejected, where the chain began and ended."""
    kind = "numbered"
    CAND = re.compile(r"^\s*([0-9OoIl|][0-9OoIl| ]{0,5}?)\s?[.,]\s?(?=\S)")
    ALONE = re.compile(r"^\s*([0-9OoIl|][0-9OoIl| ]{0,5}?)\s?[.,]?\s*$")
    OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})

    def __init__(self, gap=3, first=1, start_after=None, end_before=None, **params):
        self.gap = int(gap); self.first = int(first); self.start_after = start_after; self.end_before = end_before; self.params = params

    def _num(self, s):
        s = s.translate(self.OCR_DIGITS).replace(" ", "")
        return int(s) if s.isdigit() and len(s) <= 4 else None

    def units(self, lines):
        chain = []; rejected = []; missing = []; expect = self.first; begin = 0; end = len(lines); self_start = None
        if self.end_before:
            rx = re.compile(self.end_before)
            k = next((i for i, l in enumerate(lines) if rx.search(l)), None)
            if k is not None: end = k
        if self.start_after:
            rx = re.compile(self.start_after)
            k = next((i for i, l in enumerate(lines[:end]) if rx.search(l)), None)
            if k is not None:
                begin = k + 1
                nonempty = [i for i in range(begin, end) if lines[i].strip()][:6]
                numbered_first = any((m := self.CAND.match(lines[i])) and self._num(m.group(1)) == self.first for i in nonempty)
                if nonempty and not numbered_first:          # the first paragraph's number lost: its first line starts it
                    chain.append((nonempty[0], self.first)); expect = self.first + 1; self_start = nonempty[0] + 1
        for i in range(begin, end):
            line = lines[i]
            if line.startswith("--- page ") or (chain and chain[-1][0] == i): continue
            m = self.CAND.match(line)
            n = self._num(m.group(1)) if m else None
            if n is None:
                m2 = self.ALONE.match(line)
                if m2 and i + 1 < end and lines[i + 1].strip() and not lines[i + 1].startswith("--- page "): n = self._num(m2.group(1))
            if n is None: continue
            if (n == expect) if not chain else (expect <= n <= expect + self.gap):
                missing.extend(range(expect, n)); chain.append((i, n)); expect = n + 1
            else:
                rejected.append((i + 1, n))
        out = []
        for k, (i, n) in enumerate(chain):
            stop = chain[k + 1][0] if k + 1 < len(chain) else end
            while stop > i + 1 and not lines[stop - 1].strip(): stop -= 1
            out.append(Unit(str(n), {"para": str(n)}, i + 1, stop, "\n".join(lines[i:stop])))
        inside = set()
        for u in out: inside.update(range(u.start, u.end + 1))
        self.skipped = [i for i in range(1, len(lines) + 1) if i not in inside and lines[i - 1].strip() and not lines[i - 1].startswith("--- page ")]
        self.report = dict(paragraphs=len(chain), last=chain[-1][1] if chain else 0, missing=missing, gap=self.gap,
                           rejected_candidates=len(rejected), rejected_first=rejected[:40], start_after=self.start_after,
                           end_before=self.end_before, first_paragraph_unnumbered_at_line=self_start,
                           tail_lines_outside_units=sum(1 for i in range(end, len(lines)) if lines[i].strip()),
                           rule="a candidate starts a paragraph only if its number is the next expected or at most `gap` beyond it; "
                                "missing numbers stay inside the previous paragraph's unit")
        return out

    def describe(self):
        return dict(kind=self.kind, gap=self.gap, first=self.first, start_after=self.start_after, end_before=self.end_before,
                    candidate=self.CAND.pattern, alone=self.ALONE.pattern, ocr_digits="O o -> 0; I l | -> 1", **self.params)


SCHEMES = {"verse": VerseScheme, "headings": HeadingsScheme, "lines": LinesScheme, "page-lines": PageLinesScheme, "numbered": NumberedScheme}


def make_scheme(spec):
    """A scheme from a name ("verse"), a dict ({"kind": ..., params}), or a scheme file (.json) holding {"scheme": {...}}."""
    if isinstance(spec, str) and spec.endswith(".json"):
        d = B.read_json(spec); spec = d.get("scheme", d)
    if isinstance(spec, str): spec = {"kind": spec}
    spec = dict(spec); kind = spec.pop("kind")
    if kind not in SCHEMES: raise ValueError(f"unit scheme {kind!r}: one of {', '.join(SCHEMES)}")
    return SCHEMES[kind](**spec)


# ============================================================================================================ fetchers
FETCHERS = {
    "kjv": dict(script="fetch_kjv.py", output="kjv.txt", title="The King James Version (Project Gutenberg eBook #10)",
                scheme="verse", input="the downloaded Project Gutenberg eBook #10 text (pg10.txt), the fetcher's first argument",
                licence="public domain", args_note="<pg10.txt>"),
    "tanakh-wlc": dict(script="fetch_tanakh.py", output="tanakh-wlc.txt", scheme="verse",
                       title="The Westminster Leningrad Codex, consonantal text (UXLC or OSHB)",
                       input="tanach.us (UXLC) or github.com/openscriptures/morphhb, or --from-dir with the downloaded XML",
                       licence="text of the Codex; markup CC BY 4.0", args_note="[--source uxlc|oshb] [--books ...] [--from-dir DIR]"),
    "samaritan-pentateuch": dict(script="fetch_samaritan.py", output="samaritan-pentateuch.txt", scheme="verse",
                                 title="The Samaritan Pentateuch, consonantal text (CACCHT Text-Fabric)",
                                 input="github.com/DT-UCPH/sp, or --from-dir with the .tf files", licence="CC BY-NC 4.0",
                                 args_note="[--from-dir DIR] [--version 7.2.4]"),
    "isaiah-1qisaa": dict(script="fetch_isaiah_scroll.py", output="isaiah-1qisaa.txt", scheme="verse",
                          title="The Great Isaiah Scroll (1QIsa-a), consonantal text (ETCBC/dss)",
                          input="github.com/ETCBC/dss, or --from-dir with the .tf files", licence="CC BY-NC 4.0",
                          args_note="[--from-dir DIR] [--scroll 1Qisaa[,...]] [--out FILE]"),
}


class CanonAdapter(B.Adapter):
    name = "canon"

    def capture_text(self, path, text_id, title=None, scheme="lines", author=None, date=None, provenance=None, input_path=None,
                     tool=None, metadata=None, how=None):
        ap = self.abs(path); data = B.read_bytes(ap)
        text = data.decode("utf-8"); lines = B.lf(text).split("\n")
        if lines and lines[-1] == "": lines = lines[:-1]
        sch = make_scheme(scheme); units = sch.units(lines)
        if not units: raise ValueError(f"{path}: the {sch.kind} scheme found no units")
        src_name = os.path.basename(ap) if len(os.path.basename(ap)) <= B.INNER_NAME_CAP else "source" + os.path.splitext(ap)[1]
        inside = ap.startswith(self.root + os.sep)
        files = []
        if input_path:
            iap = self.abs(input_path)
            files.append(B.HeldFile(os.path.basename(iap), src=iap, how=f"the fetcher's local input, copied byte-for-byte from {input_path}"))
            files.append(B.HeldFile(src_name, data=data, role="derived", derived_from=os.path.basename(iap), tool=tool or "the fetcher",
                                    how=how or "the fetcher's output"))
        else:
            files.append(B.HeldFile(src_name, data=data, how=how or f"copied byte-for-byte from {self.rel(ap) if inside else ap}"))
        files.append(B.HeldFile("units.jsonl", text="".join(json.dumps(u.as_dict(), ensure_ascii=False) + "\n" for u in units),
                                role="derived", derived_from=src_name, tool=f"ledger.acquire.canon {sch.kind} scheme"))
        files.append(B.HeldFile("scheme.json", text=json.dumps(sch.describe(), indent=1, ensure_ascii=False) + "\n", role="derived",
                                derived_from=src_name, tool="ledger.acquire.canon"))
        if getattr(sch, "report", None):
            files.append(B.HeldFile("units-report.json", text=json.dumps(sch.report, indent=1, ensure_ascii=False) + "\n", role="derived",
                                    derived_from=src_name, tool=f"ledger.acquire.canon {sch.kind} scheme"))
        levels = {}
        for u in units:
            for k, v in u.levels.items(): levels.setdefault(k, set()).add(v)
        md = dict(metadata or {}); md.update(unit_scheme=sch.kind, units=len(units), source_lines=len(lines),
                                              lines_outside_units=len(getattr(sch, "skipped", [])),
                                              level_values={k: len(v) for k, v in levels.items()})
        if getattr(sch, "skipped", None): md["first_lines_outside_units"] = sch.skipped[:10]
        if getattr(sch, "report", None):
            md.update(numbered_last=sch.report["last"], numbered_missing=sch.report["missing"],
                      numbered_rejected_candidates=sch.report["rejected_candidates"], tail_lines_outside_units=sch.report["tail_lines_outside_units"])
        rec = B.Record(text_id, "canon", title or text_id, date=date, speaker_or_author=author, text=src_name,
                       provenance=provenance or (self.rel(ap) if inside else ap), capture_tool=tool and f"{self.tool} via {tool}", metadata=md)
        return B.Capture(rec, files, folder=self.hold_path("canon", text_id, ""))

    def hold_text(self, path, text_id, **kw):
        """Hold a canon text; a PDF is held as the input and its text layer (document.text_layer, the house per-page form) derived
        first and cut into units (finding 11)."""
        if str(path).lower().endswith(".pdf"):
            return self.hold(self.capture_pdf(path, text_id, **kw))
        return self.hold(self.capture_text(path, text_id, **kw))

    def capture_pdf(self, path, text_id, **kw):
        import pypdf
        from ledger.acquire import document as D
        ap = self.abs(path)
        with tempfile.TemporaryDirectory() as tmp:
            tl = os.path.join(tmp, "text-layer.txt")
            B.LN.write_text(tl, D.per_page_form(D.text_layer(ap)))
            prof = D.scan_profile(ap)
            md = dict(kw.pop("metadata", None) or {}); md.update(text_layer_origin=prof["origin"], pdf_producer=prof["producer"])
            return self.capture_text(tl, text_id, input_path=ap, tool=kw.pop("tool", None) or f"pypdf {pypdf.__version__} (the PDF's text layer)",
                                     how=kw.pop("how", None) or f"the text layer of {os.path.basename(ap)}, in the house per-page form", metadata=md, **kw)

    def fetch_canon(self, text_id, args=(), offline=False, input_path=None):
        """Run the named fetcher with its writes redirected, then hold its output in units. Returns the manifest row."""
        f = FETCHERS[text_id]
        with tempfile.TemporaryDirectory() as staging:
            rc, out, err, red = _scripts.run_tool(f["script"], list(args), staging, offline=offline)
            produced = os.path.join(staging, f["output"])
            if text_id == "isaiah-1qisaa" and "--out" in args: produced = os.path.join(staging, os.path.basename(args[list(args).index("--out") + 1]))
            if rc != 0 or not os.path.isfile(produced):
                raise RuntimeError(f"tools/{f['script']} failed (exit {rc}): {(err.strip().splitlines() or ['no output'])[-1][:300]}")
            if input_path is None and text_id == "kjv" and args: input_path = args[0]
            return self.hold_text(produced, text_id, title=f["title"], scheme=f["scheme"], input_path=input_path,
                                  tool=f"tools/{f['script']} {' '.join(args)}".strip(),
                                  provenance=f"tools/{f['script']} {' '.join(args)} (input: {f['input']})",
                                  metadata={"licence": f["licence"], "fetcher_stdout": out.strip()[-300:]},
                                  how=f"written by tools/{f['script']} (run with its writes redirected to a staging folder)")


def load_units(folder):
    p = os.path.join(folder, "units.jsonl")
    return [json.loads(l) for l in B.LN.read_text(p).split("\n") if l.strip()]


def cite(folder, ref):
    """The units a citation names: an exact address ("Gen 1:1"), a verse range in one chapter ("Gen 1:1-3"), a chapter ("Gen 1"), a
    headings prefix ("II.3" = every unit under it), "p.4" or "p.4 l.3-9" (lines within the page), "L10" or "L10-20". Returns
    [(address, start line, end line, text)]."""
    units = load_units(folder); ref = ref.strip()
    m = re.fullmatch(r"p\.(\d+)(?: l\.(\d+)(?:-(\d+))?)?", ref)
    if m:
        u = next((u for u in units if u["address"] == f"p.{m.group(1)}"), None)
        if not u: return []
        if not m.group(2): return [(u["address"], u["start"], u["end"], u["text"])]
        a = int(m.group(2)); b = int(m.group(3) or a); ls = u["text"].split("\n")[a - 1:b]
        return [(f"p.{m.group(1)} l.{a}" + (f"-{b}" if b != a else ""), u["start"] + a - 1, u["start"] + a - 1 + len(ls) - 1, "\n".join(ls))]
    m = re.fullmatch(r"L(\d+)(?:-(\d+))?", ref)
    if m:
        a = int(m.group(1)); b = int(m.group(2) or a)
        return [(u["address"], u["start"], u["end"], u["text"]) for u in units if u["end"] >= a and u["start"] <= b]
    exact = [u for u in units if u["address"] == ref]
    if exact: return [(u["address"], u["start"], u["end"], u["text"]) for u in exact]
    m = re.fullmatch(r"(.+ )?(\S+) (\d+):(\d+)-(\d+)", ref)
    if m:
        pre = (m.group(1) or ""); book, ch, a, b = m.group(2), m.group(3), int(m.group(4)), int(m.group(5))
        return [(u["address"], u["start"], u["end"], u["text"]) for u in units
                if u["address"].startswith(pre) and u["levels"].get("book") == book and u["levels"].get("chapter") == ch
                and re.match(r"\d+", u["levels"].get("verse", "")) and a <= int(re.match(r"\d+", u["levels"]["verse"]).group(0)) <= b]
    m = re.fullmatch(r"(.+ )?(\S+) (\d+)", ref)
    if m and any("book" in u["levels"] for u in units[:1]):
        pre = (m.group(1) or "")
        return [(u["address"], u["start"], u["end"], u["text"]) for u in units
                if u["address"].startswith(pre) and u["levels"].get("book") == m.group(2) and u["levels"].get("chapter") == m.group(3)]
    return [(u["address"], u["start"], u["end"], u["text"]) for u in units if u["address"].startswith(ref + ".")]


def main(argv=None):
    import argparse
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv: k = argv.index("--"); extra = argv[k + 1:]; argv = argv[:k]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["hold", "fetch", "cite"]); ap.add_argument("target"); ap.add_argument("ref", nargs="?")
    ap.add_argument("--id"); ap.add_argument("--title"); ap.add_argument("--scheme", default="lines"); ap.add_argument("--author")
    ap.add_argument("--date"); ap.add_argument("--root")
    a = ap.parse_args(argv)
    c = CanonAdapter(root=a.root)
    if a.cmd == "hold":
        sch = a.scheme; meta = {}
        if sch.endswith(".json"):
            d = B.read_json(sch); meta = {k: v for k, v in d.items() if k not in ("scheme",)}
        print(json.dumps(c.hold_text(a.target, a.id or meta.get("id") or os.path.splitext(os.path.basename(a.target))[0],
                                     title=a.title or meta.get("title"), scheme=sch, author=a.author or meta.get("author"),
                                     date=a.date or meta.get("date")), ensure_ascii=False))
    elif a.cmd == "fetch":
        print(json.dumps(c.fetch_canon(a.target, extra), ensure_ascii=False))
    else:
        for addr, s, e, t in cite(c.abs(a.target), a.ref): print(f"{addr}\t(lines {s}-{e})\t{t}")


if __name__ == "__main__":
    main()
