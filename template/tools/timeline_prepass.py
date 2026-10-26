#!/usr/bin/env python3
"""Date-keyed pre-pass for the Dated timeline (schema section 11): every date expression a source carries, with the held
timeline rows on or near that date, so an intake agent rules the Agreement column (matches / drifts / contradicts / new) from
one list instead of searching notes.db per date.

Usage:
  python3 tools/timeline_prepass.py <source file(s) or units dir> --wip wip/<task> [--window 3] [--year-window 1]
                                    [--cap 25] [--note <stem>] [--exclude-note <stem>] [--source-date YYYY-MM-DD]
                                    [--db notes.db] [--summary]

Writes wip/<task>/timeline-candidates.md (and timeline-candidates-overflow.md when a date has more than --cap candidates).
Steps: (1) extract every date expression with its location and sentence and record its precision (day, month, year, decade,
century, range, approx for BC and "years ago", relative for "the next day" and "six years later" anchored to a stated date);
(2) for each distinct date load the held rows of the `timeline` table whose span intersects the date (full dates within
--window days, month-year in the same month, years within --year-window, decades and ranges over their span), rank them by
keyword overlap with the source sentence (tools/rows_search.py's FTS5 index breaks ties) and mark the echo signal (a rare word
or a figure shared between sentence and event) and the held row's own [div: ...] tags; (3) print the groups in source order,
each with its era page, its nearest held master rows and the decimal ID tools/timeline_insert.py would give (--note <stem>
for a held note; a new note numbers its rows 1..N in date order); (4) a Summary line at the top; dates with no held row
listed again at the end. Nothing is dropped: beyond --cap candidates the rest go to the overflow file with a pointer.
Name-keyed context (people, documents, identifiers) is tools/context_pack.py's job, not this tool's. Reads notes.db read-only.
Documentation: tools/timeline_prepass.md."""
import argparse, collections, datetime, os, re, sqlite3, sys
from decimal import Decimal

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
from ledger import notes as LN        # the parser library (tools/ledger/notes.py, phase 2)
import rows_search                      # search(): FTS5 ranking; date_key(): sort_key encoding
import timeline_insert                  # sort_key(), between(), fmt(): the decimal-ID rules
try: import source_balance              # guess(stem, channel): the kind for a stem research/source-kinds.md does not list yet
except Exception: source_balance = None

DB = os.path.join(ROOT, "notes.db")
KINDS_PAGE = os.path.join(ROOT, "research", "source-kinds.md")
# the consolidated era pages (research/timeline-consolidated-<era>.md), by sort year: the pack's boundaries (pack.toml [eras]; moved 2026-10-22)
import packload
ERAS = packload.eras("pages")
MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
          "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11,
          "november": 11, "dec": 12, "december": 12}
MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
YEAR = r"(?:1[0-9]{3}|20[0-9]{2})"
DAY = r"(?:[0-3]?[0-9])(?:st|nd|rd|th)?"
NUMW = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
DECW = {"twenties": 20, "thirties": 30, "forties": 40, "fifties": 50, "sixties": 60, "seventies": 70, "eighties": 80, "nineties": 90}
NOT_YEAR_AFTER = r"(?!\s*(?:feet|ft|foot|pounds?|lbs?|miles?|mph|km|kilomet|met(?:er|re)s?|hours?|minutes?|seconds?|people|men|pages?|dollars|percent|%|rounds|tons?|acres|degrees|words|copies|troops|soldiers|aircraft|times|x\b|×))"
STOP = set("""a an the and or but if of to in on at by for from with without into onto over under about after before between during
through than then that this these those there here it its he she they them his her their we you our your i me my is are was were be
been being has have had do does did not no nor so as also only just very more most much many some any each other such own same
same both few all every one two three four five six seven eight nine ten first second third new old said says say told tell
report reported reports reporting according who whom whose which what when where why how will would can could may might shall
should must year years month months day days week weeks time times later earlier early late mid ago since until till while
because though although however yet still even also well way thing things like get got made make makes make making go went goes
part parts per via versus up down out off again further once around near date dated states state stated statement
""".split())
RELATIVE = [
    (re.compile(r"\b(?:the\s+)?(next|following|previous|preceding)\s+(day|morning|night|evening|week|month|year|decade)\b", re.I), "nf"),
    (re.compile(r"\bthe\s+(day|week|month|year)\s+(after|before)\b", re.I), "ab"),
    (re.compile(r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|\d{1,3})\s+(?:and\s+a\s+half\s+)?(day|week|month|year|decade)s?\s+(later|earlier|after|before|afterwards|prior|on)\b", re.I), "n"),
    (re.compile(r"\b(?:later\s+)?(?:that|the)\s+same\s+(day|night|morning|evening|week|month|year)\b", re.I), "same"),
    (re.compile(r"\blater\s+that\s+(day|night|morning|evening|week|month|year)\b", re.I), "same"),
    (re.compile(r"\bthat\s+(night|morning|evening|afternoon|day|year)\b", re.I), "same"),
]


# ---------------------------------------------------------------- date arithmetic in the sort_key encoding

def spelled_number(words):
    """A spelled-out count: "two thousand" 2000, "twelve thousand" 12000, "five hundred" 500, "a thousand" 1000, "two hundred
    thousand" 200000, "twenty-five" 25; 0 when no word is a number."""
    total = cur = 0; seen = False
    for w in words:
        if w in NUMW: cur += NUMW[w]; seen = True
        elif w == "hundred": cur = (cur or 1) * 100; seen = True
        elif w in ("thousand", "million", "billion"):
            total += (cur or 1) * {"thousand": 1000, "million": 10**6, "billion": 10**9}[w]; cur = 0; seen = True
    return total + cur if seen else 0

def key(y, m=0, d=0):
    """The timeline sort_key encoding: year + 1,000,000,000 (ten digits), then -MM-DD with 00 for unknown."""
    yv = max(-999_999_999, min(int(y), 8_000_000_000))
    return f"{yv + 1_000_000_000:010d}-{int(m):02d}-{int(d):02d}"

def key_year(k):
    return int(k[:10]) - 1_000_000_000

def shift_days(y, m, d, n):
    try:
        dt = datetime.date(y, m, d) + datetime.timedelta(days=n)
        return dt.year, dt.month, dt.day
    except (ValueError, OverflowError):
        return y, m, max(1, min(31, d + n))

def shift_months(y, m, n):
    t = y * 12 + (m - 1) + n
    return t // 12, t % 12 + 1

def parse_sortable(s):
    """A note's Sortable cell to (start_key, end_key, precision, approx). `?` and unparsable cells return None."""
    s = (s or "").strip(); approx = s.startswith("~"); s = s.lstrip("~ ").strip()
    if not s or s.startswith("?"): return None
    parts = [p.strip() for p in re.split(r"\s*\.\.\s*", s, maxsplit=1)]
    def one(p, end):
        m = re.match(r"(-?\d{1,9})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", p)
        if not m: return None
        y = int(m.group(1)); mo = int(m.group(2)) if m.group(2) else 0; d = int(m.group(3)) if m.group(3) else 0
        prec = "day" if d else ("month" if mo else "year")
        if end: return key(y, mo or 12, d or 31), prec
        return key(y, mo, d), prec
    a = one(parts[0], False)
    if not a: return None
    b = one(parts[-1], True) if len(parts) > 1 else one(parts[0], True)
    if not b: b = (a[0], a[1])
    prec = a[1] if len(parts) == 1 else "range"
    return a[0], b[0], prec, approx


# ---------------------------------------------------------------- the source: units, lines, locations

def read_units(paths):
    """Each file is a unit; a directory is its sorted .md/.txt files. Returns [(label, text, header_text)]."""
    units = []
    for p in paths:
        if os.path.isdir(p):
            files = sorted(f for f in os.listdir(p) if f.lower().endswith((".md", ".txt")) and not f.startswith(".") and f.lower() != "manifest.md")
            for f in files: units.append((os.path.join(os.path.basename(p.rstrip("/")), f), LN.read_text(os.path.join(p, f), errors="replace")))
        else:
            units.append((os.path.basename(p), LN.read_text(p, errors="replace")))
    return units

def split_header(text):
    """A transcript (tools/fetch_video.py) or a held web text opens with metadata; the body starts after the first `---` rule
    (transcripts) or after the leading `Published:`/`URL:` lines. Returns (header, body, body_offset)."""
    m = re.search(r"^# Transcript:.*?\n---\s*\n", text, re.S)
    if m: return text[:m.end()], text[m.end():], m.end()
    m = re.match(r"\[unit \d+/\d+[^\n]*\n", text)                 # tools/chunk_source.py's unit header
    if m: return text[:m.end()], text[m.end():], m.end()
    m = re.match(r"(#[^\n]*\n(?:(?:Published|URL|Source|Fetched|Author|Title)[^\n]*\n)+)", text)
    if m: return m.group(1), text[m.end():], m.end()
    return "", text, 0

def source_date(header, text, override):
    """The source's own date: --source-date, else Uploaded:/Published:/Recorded: in the header, else the first full date in
    the first 60 lines, else today. Anchors "N years ago" and bare two-digit years."""
    if override: return override, "--source-date"
    for lab in ("Recorded", "Published", "Uploaded", "Date"):
        m = re.search(rf"^-?\s*{lab}:\s*(\d{{4}}-\d{{2}}-\d{{2}})", header, re.M | re.I)
        if m: return m.group(1), f"{lab}: line of the header"
    head = "\n".join(text.split("\n")[:60])
    for rx in (re.compile(rf"\b({YEAR})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\b"),
               re.compile(rf"\b({MON})\s+([0-3]?[0-9]),?\s+({YEAR})\b", re.I), re.compile(rf"\b([0-3]?[0-9])\s+({MON}),?\s+({YEAR})\b", re.I),
               re.compile(rf"\b({MON})\s+({YEAR})\b", re.I)):
        m = rx.search(head)
        if m:
            g = m.groups()
            if len(g) == 3 and g[0].isdigit() and len(g[0]) == 4: return f"{g[0]}-{g[1]}-{g[2]}", "first full date in the source's first 60 lines"
            if len(g) == 3 and g[0][0].isalpha(): return f"{g[2]}-{MONTHS[g[0].lower().rstrip('.')]:02d}-{int(g[1]):02d}", "first full date in the source's first 60 lines"
            if len(g) == 3: return f"{g[2]}-{MONTHS[g[1].lower().rstrip('.')]:02d}-{int(g[0]):02d}", "first full date in the source's first 60 lines"
            return f"{g[1]}-{MONTHS[g[0].lower().rstrip('.')]:02d}", "first month-year in the source's first 60 lines"
    return datetime.date.today().isoformat(), "today (no date found in the source)"

def line_index(text):
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n": starts.append(i + 1)
    return starts

def pos_to_line(starts, pos):
    import bisect
    return bisect.bisect_right(starts, pos)      # 1-based line number

def locate(text, starts, pos, pages):
    """Human location of a character offset: a transcript's [hh:mm:ss], a document's page and line, else the line."""
    ln = pos_to_line(starts, pos)
    line = text[starts[ln - 1]: starts[ln] - 1 if ln < len(starts) else len(text)]
    m = re.match(r"\*\*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\*\*", line)
    if m: return f"[{m.group(1)}]"
    pg = None
    for p_line, p_no in pages:
        if p_line <= ln: pg = p_no
        else: break
    return f"page {pg}, line {ln}" if pg is not None else f"line {ln}"

def sentence_at(text, start, end, width=200):
    """The sentence around a match, trimmed to about `width` characters, the match kept whole."""
    lo = max(0, start - 400); hi = min(len(text), end + 400)
    seg = text[lo:hi]; s0 = start - lo; e0 = end - lo
    # sentence boundaries: ., ?, !, newline, or a bullet
    bs = [m.end() for m in re.finditer(r"(?<=[.?!])\s+(?=[A-Z\"“(\[])|\n+|^\s*[*•-]\s+", seg) if m.end() <= s0]
    be = [m.start() for m in re.finditer(r"(?<=[.?!])\s+(?=[A-Z\"“(\[])|\n+", seg) if m.start() >= e0]
    a = bs[-1] if bs else 0; b = be[0] if be else len(seg)
    sent = seg[a:b]; ms = s0 - a; me = e0 - a
    sent = re.sub(r"^\*\*\[\d{1,2}:\d{2}(?::\d{2})?\]\*\*\s*", "", sent)      # a transcript stamp at the sentence start
    shift = len(seg[a:b]) - len(sent); ms -= shift; me -= shift
    if len(sent) > width:
        room = width - (me - ms)
        left = max(0, ms - room // 2); right = min(len(sent), me + room - (ms - left))
        left = max(0, min(left, ms))
        cut = sent[left:right]
        if left > 0: cut = "…" + cut.lstrip()
        if right < len(sent): cut = cut.rstrip() + "…"
        sent = cut
    return re.sub(r"\s+", " ", sent).strip()


# ---------------------------------------------------------------- date extraction

class Hit:
    __slots__ = ("start", "end", "text", "prec", "lo", "hi", "approx", "note", "y", "m", "d", "y2", "m2", "d2", "unit", "sentence", "loc", "anchor")
    def __init__(self, start, end, text, prec, y, m=0, d=0, y2=None, m2=None, d2=None, approx=False, note=""):
        lead = len(text) - len(text.lstrip()); start += lead; text = text.strip()
        self.start, self.end, self.text, self.prec = start, end, text, prec
        self.y, self.m, self.d = y, m, d
        self.y2 = y if y2 is None else y2; self.m2 = m if m2 is None else m2; self.d2 = d if d2 is None else d2
        self.approx, self.note, self.anchor = approx, note, None
        self.recompute()
    def recompute(self):
        if self.prec == "day": self.lo, self.hi = key(self.y, self.m, self.d), key(self.y2, self.m2, self.d2)
        elif self.prec == "month": self.lo, self.hi = key(self.y, self.m, 0), key(self.y2, self.m2, 31)
        else: self.lo, self.hi = key(self.y, self.m, self.d), key(self.y2, self.m2 or 12, self.d2 or 31)
    def sortable(self):
        def one(y, m, d):
            s = str(y)
            if m: s += f"-{m:02d}"
            if d: s += f"-{d:02d}"
            return s
        a = one(self.y, self.m, self.d); b = one(self.y2, self.m2, self.d2)
        s = a if a == b else f"{a}..{b}"
        return ("~" if self.approx else "") + s
    def group_key(self):
        return (self.sortable().lstrip("~"), "day" if self.prec == "relative-day" else self.prec)

def century(n, bc=False):
    if bc: return -(n * 100) + 1, -(n * 100 - 100) if n > 1 else -1
    return (n - 1) * 100 + 1, n * 100

def two_digit_year(t, source_year):
    v = int(t); piv = source_year % 100 + 1
    return 2000 + v if v <= piv else 1900 + v

def extract(text, offset, source_year):
    """Every date expression in `text` as Hits with absolute offsets (offset added). Specific forms first; a later pattern
    never matches inside an earlier match."""
    hits = []; taken = []
    def free(a, b):
        return all(b <= s or a >= e for s, e in taken)
    def add(h):
        if not free(h.start, h.end): return
        taken.append((h.start, h.end)); hits.append(h)
    def skip_context(m):
        # inside a URL, a page marker, a transcript stamp or an identifier like GAO/NSIAD-95-187
        a = max(0, m.start() - 40); ctx = text[a:m.start()]
        tok_a = text.rfind(" ", 0, m.start()) + 1; tok_b = text.find(" ", m.end()); tok_b = len(text) if tok_b < 0 else tok_b
        token = text[tok_a:tok_b]
        if "://" in token or "www." in token: return True
        if re.search(r"---\s*page\s*$", ctx, re.I): return True
        if re.search(r"[\[:]\d{2}$", ctx): return True
        return False
    def valid_day(d):
        return 1 <= d <= 31
    def mk(m, prec, y, mo=0, d=0, **kw):
        if skip_context(m): return
        add(Hit(m.start() + offset, m.end() + offset, m.group(0), prec, y, mo, d, **kw))
    # 1. ISO full
    for m in re.finditer(rf"\b({YEAR})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\b", text):
        mk(m, "day", int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # 2. ISO month (not followed by -dd)
    for m in re.finditer(rf"\b({YEAR})-(0[1-9]|1[0-2])\b(?!-\d)", text):
        mk(m, "month", int(m.group(1)), int(m.group(2)))
    # 3. day month year ("8th of July, 1947", "9 Jul 1947")
    for m in re.finditer(rf"\b({DAY})(?:\s+of)?\s+({MON}),?\s+({YEAR})\b", text, re.I):
        d = int(re.sub(r"\D", "", m.group(1)))
        if valid_day(d): mk(m, "day", int(m.group(3)), MONTHS[m.group(2).lower().rstrip(".")], d)
    # 4. month day, year ("July 8, 1947", "Sept. 29 1995")
    for m in re.finditer(rf"\b({MON})\s+({DAY}),?\s+({YEAR})\b", text, re.I):
        d = int(re.sub(r"\D", "", m.group(2)))
        if valid_day(d): mk(m, "day", int(m.group(3)), MONTHS[m.group(1).lower().rstrip(".")], d)
    # 5. numeric m/d/y and m-d-yyyy (US order assumed)
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b", text):
        mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
        y = int(y) if len(y) == 4 else two_digit_year(y, source_year)
        if 1 <= mo <= 12 and valid_day(d) and 1000 <= y <= 2099: mk(m, "day", y, mo, d, note="numeric, month/day/year assumed")
    for m in re.finditer(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", text):
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and valid_day(d) and 1000 <= y <= 2099: mk(m, "day", y, mo, d, note="numeric, month-day-year assumed")
    # 6. 9/11
    for m in re.finditer(r"(?<![\d/])9/11(?![\d/])", text):
        mk(m, "day", 2001, 9, 11, note="9/11 read as 11 September 2001")
    # 7. year ranges joined by a dash or a word ("1946-47", "1992–1994", "1946 to 1947", "between 1992 and 1994", "from 1992 through 1995")
    for m in re.finditer(rf"\b({YEAR})\s*(?:[-–—]|to|through|thru|until|till|and)\s*({YEAR}|\d{{2}})\b(?!\s*(?:percent|%|million|billion|thousand|feet|miles|pounds|people|men))", text, re.I):
        y1 = int(m.group(1)); y2 = m.group(2)
        joiner = m.group(0)[len(m.group(1)):-len(y2)].strip().lower()
        if joiner == "and" and not re.search(r"between\s+$", text[max(0, m.start() - 12):m.start()], re.I): continue
        y2 = int(y2) if len(y2) == 4 else (y1 // 100) * 100 + int(y2)
        if y2 < y1 and len(m.group(2)) == 2: y2 += 100
        if y2 <= y1: continue
        if y2 - y1 > 400: continue       # "1947 and 2548" is not a range of years
        mk(m, "range", y1, 0, 0, y2=y2, m2=0, d2=0)
    # 8. month year ("July 1947", "July of 1947", "Jul. 1947")
    for m in re.finditer(rf"\b({MON})(?:\s+of)?,?\s+({YEAR})\b", text, re.I):
        mk(m, "month", int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")])
    # 9. decades ("the early 1950s", "the '50s", "the fifties", "1950's")
    for m in re.finditer(r"\b(?:the\s+)?(early|mid|late)?[-\s]*(?:(1[89][0-9]|20[0-9])0'?s|'([2-9])0s|(twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties))\b", text, re.I):
        if not (m.group(2) or m.group(3) or m.group(4)): continue
        if m.group(2): y0 = int(m.group(2)) * 10
        elif m.group(3): y0 = 1900 + int(m.group(3)) * 10
        else: y0 = 1900 + DECW[m.group(4).lower()]
        part = (m.group(1) or "").lower()
        a, b = {"early": (0, 3), "mid": (4, 6), "late": (7, 9)}.get(part, (0, 9))
        note = "decade" + (f", {part}" if part else "") + ("; 1900s assumed" if not m.group(2) else "")
        mk(m, "decade", y0 + a, 0, 0, y2=y0 + b, m2=0, d2=0, approx=bool(part), note=note)
    # 10. centuries
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)\s+century(\s+(?:BC|BCE|B\.C\.))?\b", text, re.I):
        a, b = century(int(m.group(1)), bool(m.group(2)))
        mk(m, "century", a, 0, 0, y2=b, m2=0, d2=0)
    # 11. BC years ("9,000 BC", "280 BCE")
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})+|\d+)\s*(?:BC|BCE|B\.C\.E?\.?)\b", text):
        n = int(m.group(1).replace(",", "")); w = max(1, n // 10)
        mk(m, "approx", -n, 0, 0, approx=True, note=f"BC; window ±{w} years")
    # 12. years ago ("12,000 years ago", "50 years ago", "two thousand years ago")
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})+|\d+|[a-z]+(?:[\s-][a-z]+)?)\s+(?:(thousand|million|billion)\s+)?years\s+ago\b", text, re.I):   # the multiplier takes its own space ("two hundred thousand" matched from "hundred"; fixed 2026-10-22)
        raw = m.group(1).replace(",", "").lower()
        if raw.isdigit(): n = int(raw)
        else:
            n = spelled_number(re.split(r"[\s-]", raw))   # "two thousand" is 2,000 (it read as two; phase 4 handoff 5, fixed 2026-10-22)
            if n == 0: continue
        mult = (m.group(2) or "").strip().lower(); n *= {"thousand": 1000, "million": 10**6, "billion": 10**9}.get(mult, 1)
        y = source_year - n; w = max(1, n // 10)
        mk(m, "approx", y, 0, 0, approx=True, note=f"{n:,} years before the source date {source_year}; window ±{w} years")
    # 13. spelled-out years ("nineteen forty-seven", "two thousand and five")
    for m in re.finditer(r"\b(nineteen|eighteen)[\s-](ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-](one|two|three|four|five|six|seven|eight|nine))?\b", text, re.I):
        y = {"nineteen": 1900, "eighteen": 1800}[m.group(1).lower()] + NUMW[m.group(2).lower()] + (NUMW[m.group(3).lower()] if m.group(3) else 0)
        mk(m, "year", y, note="spelled out")
    for m in re.finditer(r"\btwo\s+thousand(?:\s+and)?(?:[\s-](one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty(?:[\s-](?:one|two|three|four|five|six|seven|eight|nine))?))?\b(?!\s+(?:years|people|men|feet|miles|dollars|pounds))", text, re.I):
        tail = (m.group(1) or "").lower(); y = 2000 + sum(NUMW.get(w, 0) for w in re.split(r"[\s-]", tail) if w)
        mk(m, "year", y, note="spelled out")
    # 14. FY09, FY 2010, fiscal year 09
    for m in re.finditer(r"\b(?:FY|fiscal\s+years?)\s*'?(\d{4}|\d{2})\b", text, re.I):
        y = int(m.group(1)) if len(m.group(1)) == 4 else two_digit_year(m.group(1), source_year)
        mk(m, "year", y, note="fiscal year (October to September)")
    # 15. apostrophe years ("'93", "'94-ish")
    for m in re.finditer(r"(?<![\w])[’'](\d{2})\b(?!\s*s\b)", text):
        mk(m, "year", two_digit_year(m.group(1), source_year), note="two-digit year")
    # 16. year only
    for m in re.finditer(rf"(?<![\$#@/.\-:\d,])\b({YEAR})\b(?![,.]\d){NOT_YEAR_AFTER}(?!\s*(?:-|–)\s*\d)(?!\s*(?:hours|hrs|z\b|local))", text):
        if re.search(r"\b(?:room|rm|suite|box|number|no|nos|bldg|building|code|route|hwy|highway|apt|unit|ext|extension|form|af form|dd form|order|chapter|section|sec|para|paragraph|item|serial|model|flight|runway|hangar|grid)\.?\s*$", text[max(0, m.start() - 14):m.start()], re.I): continue
        mk(m, "year", int(m.group(1)))
    # 17. "in 93": a bare two-digit year after "in"
    for m in re.finditer(r"\bin\s+(?:the\s+(?:year|fall|spring|summer|winter)\s+(?:of\s+)?)?'?([3-9]\d)\b(?!\s*(?:percent|%|minutes?|seconds?|hours?|days?|weeks?|months?|years?|times|miles?|feet|people|men|cases|of|or|to|and|different|separate|countries|states|out))", text, re.I):
        mk(m, "year", 1900 + int(m.group(1)), note="bare two-digit year, 1900s assumed")
    # 18. day and month without a year ("July 9", "the 9th of July"): the year comes from the nearest earlier dated hit
    for m in re.finditer(rf"\b({DAY})(?:\s+of)?\s+({MON})\b(?!\s*,?\s*\d)", text, re.I):
        d = int(re.sub(r"\D", "", m.group(1)))
        if valid_day(d): mk(m, "day-noyear", 0, MONTHS[m.group(2).lower().rstrip(".")], d)
    for m in re.finditer(rf"\b({MON})\s+({DAY})\b(?!\s*,?\s*\d)(?!\s*(?:percent|%|million|billion|thousand|years|months|days|weeks|hours|minutes|times|of))", text, re.I):
        d = int(re.sub(r"\D", "", m.group(2)))
        if valid_day(d) and m.group(1).lower() not in ("may", "mar", "sep", "jun", "jul", "aug", "oct", "nov", "dec", "jan", "feb", "apr"): mk(m, "day-noyear", 0, MONTHS[m.group(1).lower().rstrip(".")], d)
        elif valid_day(d) and m.group(1)[0].isupper(): mk(m, "day-noyear", 0, MONTHS[m.group(1).lower().rstrip(".")], d)
    # 19. relative forms
    for rx, kind in RELATIVE:
        for m in rx.finditer(text):
            if not free(m.start() + offset, m.end() + offset): continue
            if kind == "ab" and re.match(r"\s+[A-Z][a-z]", text[m.end():m.end() + 12]): continue   # "the day after Harrowmere": an event, not a date
            h = Hit(m.start() + offset, m.end() + offset, m.group(0), "relative", 0)
            h.note = kind
            add(h)
    hits.sort(key=lambda h: h.start)
    return hits

def resolve_relative(hits, text_offset, text, source_year):
    """Give day-noyear hits a year and relative hits a date from the nearest earlier dated hit in the same unit (within
    1,500 characters for a year, 800 for a relative phrase). Unresolved hits keep prec 'unanchored'."""
    resolved = []
    for h in hits:
        if h.prec not in ("day-noyear", "relative"):
            resolved.append(h); continue
        window = 1500 if h.prec == "day-noyear" else 800
        anchors = [a for a in resolved if a.prec in ("day", "month", "year", "relative-day", "range") and a.y and a.end <= h.start and h.start - a.end <= window]
        if h.prec == "day-noyear":
            if anchors:
                a = anchors[-1]; h.y = h.y2 = a.y2 if a.prec == "range" else a.y; h.prec = "day"; h.m2, h.d2 = h.m, h.d
                h.note = f"year from \"{a.text}\""; h.anchor = a.text; h.recompute()
            else:
                h.prec = "unanchored"; h.note = "day and month without a year; no dated anchor within 1,500 characters"
            resolved.append(h); continue
        kind = h.note; t = h.text.lower(); words = re.findall(r"[a-z]+", t)
        unit = next((w for w in words if w in ("day", "morning", "night", "evening", "afternoon", "week", "month", "year", "decade")), "day")
        if unit in ("morning", "night", "evening", "afternoon"): unit = "day"
        if kind == "nf": n = 1 if words[0] in ("next", "following") or words[1] in ("next", "following") else -1
        elif kind == "ab": n = 1 if "after" in words else -1
        elif kind == "n":
            q = re.match(r"(\w+)", t).group(1); n = int(q) if q.isdigit() else NUMW.get(q, 1)
            if any(w in words for w in ("earlier", "before", "prior")): n = -n
        else: n = 0
        if not anchors:
            h.prec = "unanchored"; h.note = f"relative ({h.text}); no dated anchor within 800 characters"; resolved.append(h); continue
        a = anchors[-1]
        ay, am, ad = (a.y2, a.m2, a.d2) if a.prec == "range" and n > 0 else (a.y, a.m, a.d)
        aprec = "day" if ad else ("month" if am else "year")
        if unit == "day":
            if aprec == "day": y, m, d = shift_days(ay, am, ad, n); h.prec = "relative-day"; h.y, h.m, h.d = y, m, d; h.y2, h.m2, h.d2 = y, m, d
            else:
                h.prec = aprec; h.y, h.m, h.d = ay, am, ad; h.y2, h.m2, h.d2 = ay, am, ad; h.approx = True
                h.note = f"relative ({h.text}) to \"{a.text}\", which has no day; kept at the anchor's precision"
        elif unit == "week":
            if aprec == "day": y, m, d = shift_days(ay, am, ad, 7 * n); h.prec = "relative-day"; h.y, h.m, h.d = y, m, d; h.y2, h.m2, h.d2 = y, m, d; h.approx = True
            else: h.prec = aprec; h.y, h.m, h.d = ay, am, ad; h.y2, h.m2, h.d2 = ay, am, ad; h.approx = True
        elif unit == "month":
            if aprec in ("day", "month"): y, m = shift_months(ay, am, n); h.prec = "month"; h.y, h.m, h.d = y, m, 0; h.y2, h.m2, h.d2 = y, m, 0
            else: h.prec = "year"; h.y = h.y2 = ay; h.m = h.d = h.m2 = h.d2 = 0; h.approx = True
        else:
            step = 10 if unit == "decade" else 1
            h.prec = "year"; h.y = h.y2 = ay + n * step; h.m = h.d = h.m2 = h.d2 = 0; h.approx = h.approx or unit == "decade"
        if not h.note.startswith("relative"):
            h.note = f"relative ({h.text}) to \"{a.text}\"" + (f", {n:+d} {unit}" + ("s" if abs(n) != 1 else "") if n else ", same " + unit)
        h.anchor = a.text; h.recompute(); resolved.append(h)
    return resolved


# ---------------------------------------------------------------- the held rows

def load_rows(con, exclude=None):
    rows = []
    for r in con.execute("SELECT video, n, n_sort, date_stated, sortable, sort_key, approx, event, speaker_basis, chain, link, agreement, agreement_kind FROM timeline"):
        if exclude and r[0] == exclude: continue
        p = parse_sortable(r[4])
        rows.append({"video": r[0], "n": r[1], "n_sort": r[2], "date_stated": r[3] or "", "sortable": r[4] or "", "sort_key": r[5], "event": r[7] or "",
                     "speaker": r[8] or "", "agreement": r[11] or "", "agreement_kind": r[12] or "", "span": p})
    return rows

def load_kinds(con=None):
    """stem -> source kind from research/source-kinds.md; a stem not on the page gets source_balance.guess() marked '(guessed)'."""
    kinds = {}
    if os.path.exists(KINDS_PAGE):
        for line in LN.iter_lines(KINDS_PAGE):
            c = LN.split_row(line)
            if len(c) >= 2 and c[0] and c[0] not in ("Stem", "---") and not c[0].startswith("-"): kinds[c[0]] = c[1]
    if con is not None and source_balance is not None:
        for stem, channel in con.execute("SELECT id, channel FROM videos"):
            if stem not in kinds: kinds[stem] = source_balance.guess(stem, channel) + " (guessed)"
    return kinds

def tokens(s):
    return [t for t in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", str(s if s is not None else "").lower())]

def div_tags(agreement):
    return re.findall(r"\[div:[^\]]*\]", agreement or "")

def trim(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


# ---------------------------------------------------------------- matching, ranking, IDs

def query_span(h, window, year_window):
    """The span of sort keys a group's candidates must intersect."""
    if h.prec in ("day", "relative-day"):
        y1, m1, d1 = shift_days(h.y, h.m, h.d, -window); y2, m2, d2 = shift_days(h.y2, h.m2, h.d2, window)
        return key(y1, m1, d1), key(y2, m2, d2)
    if h.prec == "month": return key(h.y, h.m, 0), key(h.y2, h.m2, 31)
    if h.prec == "year": return key(h.y - year_window, 0, 0), key(h.y2 + year_window, 12, 31)
    if h.prec == "approx":
        w = max(1, abs(source_delta(h)) // 10); return key(h.y - w, 0, 0), key(h.y2 + w, 12, 31)
    return h.lo, h.hi

def source_delta(h):
    m = re.search(r"([\d,]+) years before the source date (\d+)", h.note)
    if m: return int(m.group(1).replace(",", ""))
    m = re.search(r"window ±(\d+)", h.note)
    return int(m.group(1)) * 10 if m else max(1, abs(h.y))

def tier(h, row):
    """0 the row speaks of the same date at the source's precision (or closer), 1 one step coarser or a neighbouring year, 2 coarser
    still, 3 a held span far wider than the source's date (a century, "the 40s onward"), which merely contains it."""
    s, e, prec, _ = row["span"]
    span_years = key_year(e) - key_year(s)
    if h.prec in ("day", "relative-day", "month") and span_years >= 2: return 3
    if h.prec == "year" and span_years >= 10: return 3
    if h.prec in ("decade", "century", "range", "approx") and span_years > 3 * max(1, key_year(h.hi) - key_year(h.lo)) + 2: return 3
    if h.prec in ("day", "relative-day"):
        return {"day": 0, "month": 1, "year": 2, "range": 1 if key_year(e) - key_year(s) <= 1 else 2}[prec]
    if h.prec == "month": return {"day": 0, "month": 0, "year": 1, "range": 1}[prec]
    if h.prec == "year": return 0 if key_year(s) <= h.y <= key_year(e) else 1
    return 0

def rank_group(con, group, rows, df, window, year_window):
    """Candidates for a group of hits sharing one date: the held rows whose span intersects the query span, scored by keyword
    overlap with the group's sentences (rare words and figures weigh 3, other keywords 1, closeness bonus 6/3/0), FTS5 bm25
    rank as the tie-breaker. Returns (candidates sorted, exact_count, fts_used)."""
    h = group[0]; qlo, qhi = query_span(h, window, year_window)
    cands = [r for r in rows if r["span"] and r["span"][0] <= qhi and r["span"][1] >= qlo]
    if not cands: return [], 0, False
    # keywords: per occurrence, so a date stated thirty times does not match everything
    date_words = set()
    for g in group:
        date_words |= set(tokens(g.text)); date_words |= {str(g.y), str(abs(g.y)), str(g.y2)}
    occ_terms = []
    for g in group:
        ts = set(t for t in tokens(g.sentence) if t not in STOP and t not in date_words and (len(t) >= 3 or t.isdigit()) and not (t.isdigit() and len(t) < 2))
        occ_terms.append(ts)
    all_terms = set().union(*occ_terms) if occ_terms else set()
    def rare(t): return (t in df and df[t] <= 3 and not t.isdigit() and len(t) >= 4) or (any(ch.isdigit() for ch in t) and len(t) >= 2)
    # FTS ranking as tie-breaker
    fts_rank = {}; fts_used = False
    fts_terms = sorted((t for t in all_terms if t in df), key=lambda t: df[t])[:30]
    if fts_terms:
        q = " OR ".join('"' + t.replace('"', "") + '"' for t in fts_terms)
        try:
            d_from = f"{key_year(qlo)}-{qlo[11:13]}-{qlo[14:16]}".replace("-00-00", "").replace("-00", "")
            d_to = f"{key_year(qhi)}-{qhi[11:13]}-{qhi[14:16]}"
            _, res = rows_search.search(con, q, kinds=["tl"], d_from=d_from, d_to=d_to, limit=3000)
            for i, r in enumerate(res): fts_rank[(r["video"], r["n"])] = i
            fts_used = True
        except (sqlite3.OperationalError, SystemExit):
            fts_used = False
    scored = []
    for r in cands:
        ev = set(tokens(r["event"] + " " + r["speaker"]))
        best = 0; best_shared = set()
        for ts in occ_terms:
            shared = ts & ev
            sc = sum(3 if rare(t) else 1 for t in shared)
            if sc > best: best, best_shared = sc, shared
        t = tier(h, r); bonus = {0: 6, 1: 3, 2: 0, 3: -3}[t]
        echo = sorted(x for x in best_shared if rare(x))
        r2 = dict(r); r2["score"] = best + bonus; r2["tier"] = t; r2["echo"] = echo; r2["shared"] = sorted(best_shared)
        r2["fts"] = fts_rank.get((r["video"], r["n"]), 10**6)
        scored.append(r2)
    scored.sort(key=lambda r: (-r["score"], r["tier"], r["fts"], r["span"][0], r["video"], r["n_sort"] or 0))
    exact = sum(1 for r in scored if r["tier"] == 0)
    return scored, exact, fts_used

def master_neighbours(rows, qlo, qhi):
    before = max((r for r in rows if r["span"] and r["span"][0] < qlo), key=lambda r: r["span"][0], default=None)
    after = min((r for r in rows if r["span"] and r["span"][0] > qhi), key=lambda r: r["span"][0], default=None)
    return before, after

def note_rows(rows_all, con, stem):
    """The held note's own rows in table order (n_sort), for the decimal-ID computation; from notes.db, so the note as last built."""
    rs = con.execute("SELECT n, sortable FROM timeline WHERE video=? ORDER BY n_sort", (stem,)).fetchall()
    return [(Decimal(n), timeline_insert.sort_key(s or "?")) for n, s in rs]

def insert_id(table, sortable):
    """The ID tools/timeline_insert.py would give one new row with this Sortable in a note whose table is `table`
    ([(Decimal id, sort key)] in table order). Mirrors timeline_insert.main(): legacy out-of-order rows are ignored."""
    if not table: return "1", None, None
    ids = [t[0] for t in table]; keys = [t[1] for t in table]; taken = set(ids)
    def prec(kk): return 10 if kk.endswith("-00-00") else (13 if kk.endswith("-00") else 16)
    mask, hi = [], None
    for kk in keys:
        ok = hi is None or kk[:prec(kk)] >= hi[:prec(kk)]
        mask.append(ok)
        if ok and (hi is None or kk > hi): hi = kk
    k = timeline_insert.sort_key(sortable)
    inplace = [i for i, m in enumerate(mask) if m]
    after = [i for i in inplace if keys[i] <= k]; nxt = [i for i in inplace if keys[i] > k]
    ia = after[-1] if after else None; a = ids[ia] if after else Decimal(0)
    b = ids[nxt[0]] if nxt else None
    if b is not None and b <= a: b = None
    higher = [x for x in taken if x > a]
    if higher and (b is None or min(higher) < b):
        b = min(higher) if b is not None or ia is None or ids[ia] != max(taken) else None
    new_id = timeline_insert.between(a, b, taken)
    return timeline_insert.fmt(new_id), (timeline_insert.fmt(a) if ia is not None else None), (timeline_insert.fmt(b) if b is not None else None)

def eras_for(lo, hi):
    y1, y2 = key_year(lo), key_year(hi)
    return [name for name, a, b in ERAS if a <= y2 and b >= y1]


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="source files (transcript, held text) or a units directory")
    ap.add_argument("--wip", required=True, help="wip/<task>; the output goes to <wip>/timeline-candidates.md")
    ap.add_argument("--window", type=int, default=1, help="days either side of a full date (default 1; was 3 until 2026-10-22)")
    ap.add_argument("--year-window", type=int, default=0, help="years either side of a year-only date (default 0; was 1)")
    ap.add_argument("--cap", type=int, default=4, help="candidates printed per date; the rest go to the overflow file (default 4; was 25)")
    ap.add_argument("--coarse-inline", action="store_true", help="keep year, decade, century, range and approximate dates in the main file (default: timeline-candidates-coarse.md)")
    ap.add_argument("--budget-words", type=int, default=30000, help="the main file's word budget; the summary names the date sections over their share (default 30000)")
    ap.add_argument("--note", help="stem of the held note the rows will be inserted into: prints the decimal ID timeline_insert.py would give")
    ap.add_argument("--exclude-note", help="stem whose own rows are left out of the candidates (testing a held source)")
    ap.add_argument("--source-date", help="YYYY-MM-DD of the source itself, the anchor for 'N years ago' (default: the header's date)")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--summary", action="store_true", help="print the Summary line only; write nothing")
    a = ap.parse_args()

    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    rows = load_rows(con, a.exclude_note)
    undated = sum(1 for r in rows if not r["span"])
    rows_dated = [r for r in rows if r["span"]]
    kinds = load_kinds(con)
    # document frequency of event-text tokens, over distinct notes, for the rare-word (echo) signal
    df = collections.Counter()
    for vid, ts in {(r["video"], t) for r in rows for t in set(tokens(r["event"]))}: df[ts] += 1
    db_built = datetime.datetime.fromtimestamp(os.path.getmtime(a.db)).strftime("%Y-%m-%d %H:%M")

    units = read_units(a.sources)
    all_hits = []; src_date = None; src_basis = None
    for label, text in units:
        header, body, off = split_header(text)
        if src_date is None:
            src_date, src_basis = source_date(header, text, a.source_date)
        source_year = int(src_date[:4])
        starts = line_index(text)
        pages = [(pos_to_line(starts, m.start()), int(m.group(1))) for m in re.finditer(r"^--- page (\d+) ---", text, re.M)]
        hits = extract(body, off, source_year)
        hits = resolve_relative(hits, off, text, source_year)
        for h in hits:
            h.unit = label; h.sentence = sentence_at(text, h.start, h.end); h.loc = locate(text, starts, h.start, pages)
        all_hits += hits

    # groups: one per distinct (sortable, precision), in source order of first occurrence
    groups = collections.OrderedDict(); unresolved = []
    for h in all_hits:
        if h.prec == "unanchored": unresolved.append(h); continue
        groups.setdefault(h.group_key(), []).append(h)
    prec_counts = collections.Counter("day" if h.prec == "relative-day" else h.prec for h in all_hits if h.prec != "unanchored")
    rel_anchored = sum(1 for h in all_hits if h.anchor and not h.note.startswith("year from"))
    noyear_anchored = sum(1 for h in all_hits if h.note.startswith("year from"))

    table = note_rows(rows, con, a.note) if a.note else None
    if a.note and not table: print(f"warning: --note {a.note}: no timeline rows in notes.db; IDs start at 1", file=sys.stderr)

    results = []
    for gk, group in groups.items():
        cands, exact, fts_used = rank_group(con, group, rows_dated, df, a.window, a.year_window)
        results.append((gk, group, cands, exact, fts_used))
    n_cands = sum(len(c) for _, _, c, _, _ in results); n_exact = sum(e for _, _, _, e, _ in results)
    none_rows = [(gk, g) for gk, g, c, e, _ in results if not c]
    none_exact = [(gk, g) for gk, g, c, e, _ in results if c and not e and g[0].prec in ("day", "relative-day", "month", "year")]
    overflow_n = sum(max(0, len(c) - a.cap) for _, _, c, _, _ in results)
    chrono = sorted(results, key=lambda r: r[1][0].lo); chrono_pos = {r[0]: i + 1 for i, r in enumerate(chrono)}

    summary = (f"Summary: {len(all_hits)} date expressions ({', '.join(f'{k} {v}' for k, v in sorted(prec_counts.items()))}"
               f"{'; ' + str(len(unresolved)) + ' unanchored' if unresolved else ''}; {rel_anchored} relative forms anchored, {noyear_anchored} day-month forms given a year); "
               f"{len(groups)} distinct dates; {n_cands} candidate rows ({n_exact} at the source's precision); "
               f"{len(none_rows)} dates with no held row, {len(none_exact)} with held rows only at a coarser precision or a neighbouring year"
               f"{'; ' + str(overflow_n) + ' candidates beyond the cap in timeline-candidates-overflow.md' if overflow_n else ''}.")
    print(summary)
    if a.summary: return

    os.makedirs(a.wip, exist_ok=True)
    out = os.path.join(a.wip, "timeline-candidates.md"); over = os.path.join(a.wip, "timeline-candidates-overflow.md")
    srcs = ", ".join(os.path.relpath(p, ROOT) if os.path.abspath(p).startswith(ROOT) else p for p in a.sources)
    L = [f"# Timeline candidates: {srcs}", "", summary, "",
         f"Generated {datetime.date.today().isoformat()} by `python3 tools/timeline_prepass.py {' '.join(a.sources)} --wip {a.wip}"
         f"{' --window ' + str(a.window) if a.window != 1 else ''}{' --year-window ' + str(a.year_window) if a.year_window != 0 else ''}{' --cap ' + str(a.cap) if a.cap != 4 else ''}{' --coarse-inline' if a.coarse_inline else ''}"
         f"{' --note ' + a.note if a.note else ''}{' --exclude-note ' + a.exclude_note if a.exclude_note else ''}` "
         f"from {os.path.relpath(a.db, ROOT)} (built {db_built}; {len(rows_dated)} dated timeline rows, {undated} undated rows not searchable by date"
         f"{'; rows of ' + a.exclude_note + ' excluded' if a.exclude_note else ''}). Source date {src_date} ({src_basis}), the anchor for \"years ago\" and two-digit years. "
         f"Full dates matched within ±{a.window} days, month-years in their month, years within ±{a.year_window}, decades, centuries and ranges over their span, BC and \"years ago\" within a tenth of their distance.",
         "",
         "How to read: one section per distinct date in source order (the year, decade, century, range and approximate dates in timeline-candidates-coarse.md unless --coarse-inline); the source sentences first, one line per unit (the first sentence that states the date, then where else in the unit it recurs), then the held rows ranked by keyword overlap "
         "with the sentence (rare words and figures weigh 3, other keywords 1, plus 6 for a row at the source's precision, 3 one step coarser; tools/rows_search.py's "
         "bm25 breaks ties). Each candidate: `[<stem> tl N] | date as stated (Sortable) | speaker, basis | event | kind: <source kind> | <agreement kind>`, then "
         "`div:` with the row's own [div: ...] tags and `echo:` with the rare words or figures the event shares with the sentence (the echo signal: check "
         "independence before counting it as corroboration). Rule the Agreement cell from these rows (read each one you cite in its own note); search beyond this "
         "file only for a date listed under \"Dates with no held row\". The era page is where the orchestrator will place the row. The ID line gives the decimal "
         "ID tools/timeline_insert.py would assign" + (f" in {a.note}" if a.note else " (a new note numbers its rows 1..N in date order, one whole number per date found here; fewer rows renumber nothing, they just close up; pass --note <stem> for a held note)") + ".", ""]
    OV = [f"# Timeline candidates, overflow: {srcs}", "", f"Candidates beyond the first {a.cap} of each date in timeline-candidates.md, in the same order: candidates {a.cap + 1} to {5 * a.cap} in the same form, the rest in index form (one line: citation, Sortable, the event's opening, kind, agreement kind, tier). Nothing is dropped.", ""]
    COARSE = ("year", "decade", "century", "range", "approx")
    coarse_of = lambda h: (not a.coarse_inline) and h.prec in COARSE
    coarse = os.path.join(a.wip, "timeline-candidates-coarse.md")
    C = [f"# Timeline candidates, coarse dates: {srcs}", "", "The dates stated at year, decade, century, range or approximate precision (BC, \"years ago\"), in the same form as "
         "timeline-candidates.md and with the same section numbers; their candidates beyond the cap are in timeline-candidates-overflow.md. A coarse date rarely decides "
         "an Agreement cell on its own: read these after the full dates and month-years.", ""]
    sec_words = []   # (section number, date, words) of the main file's date sections, for the budget summary
    for i, (gk, group, cands, exact, fts_used) in enumerate(results, 1):
        h = group[0]; qlo, qhi = query_span(h, a.window, a.year_window)
        T = C if coarse_of(h) else L; start = len(T)
        forms = collections.Counter(g.text for g in group)
        prec_label = "day" if h.prec == "relative-day" else h.prec
        T += [f"## {i}. {h.sortable()} ({prec_label}) — first stated as \"{h.text}\"", ""]
        T.append("Stated forms: " + "; ".join(f"\"{t}\" ×{n}" if n > 1 else f"\"{t}\"" for t, n in forms.most_common()) + ".")
        notes = sorted({g.note for g in group if g.note})
        if notes: T.append("Reading: " + "; ".join(notes) + ".")
        eras = eras_for(h.lo, h.hi)
        before, after = master_neighbours(rows_dated, qlo, qhi)
        def cite(r): return f"[{r['video']} tl {r['n']}] ({r['sortable']}: {trim(r['event'], 60)})"
        T.append("Era page" + ("s" if len(eras) > 1 else "") + ": " + ", ".join(f"research/timeline-consolidated-{e}.md" for e in eras) + ".")
        T.append("Master neighbours outside the window: " + (cite(before) if before else "none before") + " < here < " + (cite(after) if after else "none after") + ".")
        if table is not None:
            nid, lo_id, hi_id = insert_id(table, h.sortable())
            gap = f"between tl {lo_id} and tl {hi_id}" if lo_id and hi_id else (f"after tl {lo_id}" if lo_id else (f"before tl {hi_id}" if hi_id else "empty table"))
            T.append(f"ID in {a.note}: tl {nid} ({gap}; a second row in the same gap takes the next free decimal, as timeline_insert.py computes it).")
        else:
            T.append(f"ID: row {chrono_pos[gk]} of {len(groups)} in date order.")
        # one occurrence line per unit: the first sentence that states the date there, and where else in the unit it recurs
        by_unit = collections.OrderedDict()
        for g in group: by_unit.setdefault(g.unit, []).append(g)
        T.append(""); T.append(f"Occurrences ({len(group)} in {len(by_unit)} unit{'s' if len(by_unit) != 1 else ''}; one line per unit):")
        for unit, gs in by_unit.items():
            g = gs[0]
            T.append(f"- {unit} {g.loc}: \"{g.sentence}\"" + (f" [{g.note}]" if g.note and g.note.startswith(("relative", "year from")) else "")
                     + (f" (and {len(gs) - 1} more in this unit: {', '.join(x.loc for x in gs[1:6])}{' ...' if len(gs) > 6 else ''})" if len(gs) > 1 else ""))
        T.append("")
        if not cands:
            T.append(f"Candidates: none. No held timeline row falls in this date's window; a row here is a `new` candidate (listed again at the end of timeline-candidates.md)."); T.append("")
        else:
            tiers = collections.Counter(r["tier"] for r in cands)
            shown = cands[:a.cap]; rest = cands[a.cap:]
            T.append(f"Candidates ({len(shown)} of {len(cands)}; {tiers.get(0, 0)} at the source's precision, {tiers.get(1, 0)} one step coarser or a neighbouring year, {tiers.get(2, 0)} coarser, {tiers.get(3, 0)} wide spans that merely contain the date"
                     + ("; no row at the source's precision" if exact == 0 and prec_label in ("day", "month", "year") else "")
                     + (f"; the remaining {len(rest)} in timeline-candidates-overflow.md section {i}" if rest else "") + "):")
            def render(r):
                s = (f"- [{r['video']} tl {r['n']}] | {trim(r['date_stated'], 50)} ({r['sortable']}) | {trim(r['speaker'], 70)} | {trim(r['event'], 180)} | kind: {kinds.get(r['video'], '?')}"
                     f" | {r['agreement_kind'] or '?'}")
                tags = div_tags(r["agreement"])
                if tags: s += " | div: " + " ".join(tags)
                if r["echo"]: s += " | echo: " + ", ".join(r["echo"])
                elif r["shared"]: s += " | shared: " + ", ".join(r["shared"][:6])
                return s
            for r in shown: T.append(render(r))
            T.append("")
            if rest:
                OV += [f"## {i}. {h.sortable()} ({prec_label}) — \"{h.text}\": candidates {a.cap + 1} to {len(cands)}", ""]
                full, index = rest[:4 * a.cap], rest[4 * a.cap:]
                for r in full: OV.append(render(r))
                if index:
                    OV += ["", f"Index form for candidates {a.cap + len(full) + 1} to {len(cands)} (citation, Sortable, event opening, kind, agreement kind, tier 0 to 3):"]
                    for r in index: OV.append(f"- [{r['video']} tl {r['n']}] {r['sortable']} | {trim(r['event'], 80)} | {kinds.get(r['video'], '?').replace(' (guessed)', '')} | {r['agreement_kind'] or '?'} | t{r['tier']}" + (" | echo: " + ", ".join(r["echo"]) if r["echo"] else ""))
                OV.append("")
        if T is L: sec_words.append((i, h.sortable(), len(" ".join(L[start:]).split())))
    n_coarse = sum(1 for r in results if coarse_of(r[1][0]))
    if n_coarse:
        L += [f"## Coarse dates", "", f"{n_coarse} dates stated at year, decade, century, range or approximate precision are in timeline-candidates-coarse.md (same form, same section numbers).", ""]
    where = lambda gk, g: f"section {results.index(next(r for r in results if r[0] == gk)) + 1}" + (" (coarse file)" if coarse_of(g[0]) else "")
    L += ["## Dates with no held row", ""]
    if none_rows:
        L.append(f"{len(none_rows)} dates: no held timeline row falls in their window, so a row for them is a `new` candidate (still check the claims ledgers with tools/rows_search.py before ruling `new`).")
        L.append("")
        for gk, g in none_rows:
            L.append(f"- {g[0].sortable()} ({'day' if g[0].prec == 'relative-day' else g[0].prec}), {where(gk, g)}: " + "; ".join(f"{x.unit} {x.loc} \"{trim(x.sentence, 120)}\"" for x in g[:3]) + (f"; and {len(g) - 3} more" if len(g) > 3 else ""))
    else: L.append("None: every date found has at least one held row in its window.")
    L.append("")
    if none_exact:
        L += ["## Dates held only at a coarser precision or a neighbouring year", "",
              f"{len(none_exact)} dates whose candidates are all month-only or year-only rows, or rows of a neighbouring year: the event may still be held under a looser date; a `new` ruling needs the candidates read first.", ""]
        for gk, g in none_exact:
            L.append(f"- {g[0].sortable()} ({'day' if g[0].prec == 'relative-day' else g[0].prec}), {where(gk, g)}: \"{trim(g[0].sentence, 120)}\"")
        L.append("")
    if unresolved:
        L += ["## Unresolved date expressions (no anchor)", "", f"{len(unresolved)} expressions whose date could not be fixed from the text (a day and month with no year nearby, or a relative phrase with no stated date before it). Nothing is dropped: read each in place; if the context gives the date, search it with `python3 tools/rows_search.py --table timeline --from --to`.", ""]
        for h in unresolved: L.append(f"- {h.unit} {h.loc}: \"{h.sentence}\" [{h.note}]")
        L.append("")
    # the word budget (2026-10-22): the main file against --budget-words, and the date sections over an equal share of it
    total = len("\n".join(L).split()); share = a.budget_words / max(1, len(sec_words))
    over_s = sorted((x for x in sec_words if x[2] > share), key=lambda x: -x[2])
    budget = (f"Budget: {total:,} words in this file against --budget-words {a.budget_words:,}" + (" (within)" if total <= a.budget_words else f" (over by {total - a.budget_words:,})")
              + f"; {len(sec_words)} date sections here, an equal share {share:,.0f} words each; "
              + (f"{len(over_s)} over their share: " + ", ".join(f"section {i} ({d}, {w:,})" for i, d, w in over_s[:12]) + (f" and {len(over_s) - 12} more" if len(over_s) > 12 else "") if over_s else "none over its share")
              + (f". Coarse file {len(chr(10).join(C).split()):,} words." if n_coarse else ".") + " Narrow with a smaller --cap, --window or --year-window.")
    L.insert(3, budget); L.insert(4, "")
    print(budget)
    LN.write_text(out, "\n".join(L))
    if n_coarse: LN.write_text(coarse, "\n".join(C))
    elif os.path.exists(coarse): os.remove(coarse)
    if overflow_n: LN.write_text(over, "\n".join(OV))
    elif os.path.exists(over): os.remove(over)
    print(f"wrote {os.path.relpath(out)} ({len(groups) - n_coarse} dates, {n_cands} candidates in all)" + (f", {os.path.relpath(coarse)} ({n_coarse} coarse dates)" if n_coarse else "") + (f" and {os.path.relpath(over)} ({overflow_n} rows)" if overflow_n else ""))
if __name__ == "__main__":
    main()
