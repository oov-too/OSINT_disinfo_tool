"""Spans of a staged intake's units by pointer (the compact findings form, 2026-10-23; wip/compact-findings/).

The reader's findings file carries pointers, not text: a claim is `[u NNN:L]` (or `[u NNN:L-M]`) with key words, a quotation is the
pointer with its first four and last four words (`words: <first four> ... <last four>`). The writer and the finisher pull the
source's words by pointer with `ledger quote`, which calls this module; tools/intake_gate.py locates the same anchors with it, so
the gate and the command agree on what a pointer and its anchors mean.

  span(wip, n, a, b)                   the unit's header line and lines a..b of wip/units/NNN.txt (`cat -n` numbering, line 1 the
                                       header), verbatim
  words(wip, n, a, b, anchors)         the exact words between the first-four and last-four anchors on those lines (two lines'
                                       slack either side, as gate 1 allows a quotation's pointer)
  locate(lines, a, b, anchors)         where the anchors are: ((line, char), (line, char)) or None
  quotation_items(findings_path)       the `## Quotations` items of a findings file: pointer, speaker, anchors, use

Words are matched as tokens: case, curly quotes and dashes do not count, punctuation between words does not count, an inline URL
token `[http...]` and a bracketed insertion of three or more characters (`[sic]`, `[the DIA]`) are not words, and the content of a
one- or two-character insertion (`[M]y`) is. Nothing else is forgiven: a dropped or changed word fails.

The word-key matcher (2026-10-25, the owner's caption rule; wip/quote-tool-adoption/): `ledger quote --find` and gate 2's second
tier (tools/intake_gate.py) compare word keys only, so the two agree on what "the same words" means:

  key_tokens(raw)                      [(key, start, end)] of one line: a key is the word lower-cased with its apostrophes dropped
                                       (an apostrophe is punctuation: `its` = `it's`, as a caption writes it); a number's digit-group
                                       commas are dropped (`1,500` = `1500`); a bracketed span of three to sixty
                                       characters (`[sic]`, `[the DIA]`) is not words, nor are a caption's timestamp
                                       `[00:01:12]`, an inline URL and a markdown link target; a one- or two-character insertion's
                                       content is (`[M]y` = `My`), and so is a markdown link's text (`[the report](...)`); with
                                       keep_brackets a source's own bracketed words are words too, and the matcher tries a unit
                                       both ways (dropped, then kept), so `[harbour lease]` in a unit is quotable with or without
  unit_keys(lines)                     the keys of a unit's body (line 1, the header, and page-marker lines are not words)
  phrase_segments(text)                a quotation or phrase as key lists, split at ellipses and at three-to-sixty-character insertions
  match_segments(keys, segs)           where the segments occur in order (each contiguous, at most GAP keys apart), or None
  near_miss(units, keys)               the best-aligned window and the word differences (a changed, added or dropped word)
  find(wip, phrase)                    every hit of a phrase in the task's units, with the sentence or caption line that holds it
  sentence_span(lines, start, end)     the whole sentence (or the caption line, when the line has no sentence punctuation) around
                                       a hit, as ((first line, char), (last line, char))

Two strings whose keys are identical in order differ by punctuation, capitals, curly quotes, dashes or spacing only: the caption
rule forgives exactly that. A changed, added or dropped word is a different key sequence."""
import difflib, os, re

from ledger import notes as LN

PTR_RE = re.compile(r"^\[?u?\s*(\d{1,3}):(\d+)(?:-(\d+))?\]?$")
SEP_RE = re.compile(r"\s*(?:\.\.\.|…)\s*")
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
# Masked in a unit's lines (pilot defect 11, 7b2 2026-10-23): page markers (chunk_source's PAGE_RE forms), a bare bracketed URL and a
# markdown link's target `](...)`; never bracketed text, so link text and a transcript's own bracketed words stay words. The unit
# header is line 1, which no pointer reaches.
PAGE_LINE_RE = re.compile(r"^\s*(?:--- ?page \d+ ?---|=== ?page[ -]?\d+(?:\.[A-Za-z0-9]+)?(?: ?===)?|\[page \d+\]|<!-- ?page \d+ ?-->)\s*$")
SRC_MASK_RE = re.compile(r"\[https?://[^\]\s]+\]|(?<=\])\((?:[^()\s]|\([^()\s]*\))*\)")
# In a quotation's anchors a bracketed insert ([sic], [...], a correction) may be the writer's, not the source's: the anchors are tried
# with bracketed text kept first, then masked as before (MASK_RE).
MASK_RE = re.compile(r"\[https?://[^\]\s]+\]|\[[^\]]{3,60}\]")
SLACK = 2


class PointerError(ValueError):
    """A pointer that names no unit, or lines outside the unit, or anchors not found on its lines."""


def parse_pointers(args):
    """Pointers from command-line tokens: `u 003:12-14`, `u003:12`, `[u 003:12-14]`, `003:12`; a bare `u` joins the next token.
    Returns [(unit 'NNN', a, b)]; raises PointerError on a token that is not a pointer."""
    out, toks = [], [t for t in args]
    i = 0
    while i < len(toks):
        t = toks[i].strip()
        if t in ("u", "[u"):
            if i + 1 >= len(toks): raise PointerError(f"`{t}` with no NNN:L after it")
            t = toks[i + 1].strip(); i += 1
        m = PTR_RE.match(t)
        if not m: raise PointerError(f"not a pointer: {t!r} (the form is u NNN:L or u NNN:L-M)")
        a = int(m.group(2)); b = int(m.group(3) or a)
        out.append((f"{int(m.group(1)):03d}", a, b))
        i += 1
    return out


def unit_path(wip, n):
    return os.path.join(wip, "units", f"{n}.txt")


def unit_lines(wip, n):
    """The unit file's lines as gate 1 reads them (a trailing empty line dropped); PointerError when the unit does not exist."""
    p = unit_path(wip, n)
    if not os.path.isfile(p): raise PointerError(f"no unit {n}: {p} does not exist")
    lines = LN.read_text(p, errors="replace").split("\n")
    if lines and lines[-1] == "": lines = lines[:-1]
    return lines


def check_range(lines, n, a, b):
    if a < 2 or b < a or b > len(lines):
        raise PointerError(f"[u {n}:{a}{'-' + str(b) if b != a else ''}] is outside unit {n} (body lines 2 to {len(lines)})")


def span(wip, n, a, b):
    """(header line, [lines a..b]) verbatim."""
    lines = unit_lines(wip, n)
    check_range(lines, n, a, b)
    return lines[0], lines[a - 1:b]


def _norm_word(w):
    return w.lower().replace("’", "'")


def _tokens(lines, a, b):
    """[(word, line, start, end)] over lines a..b (1-based), masked spans not words, offsets in the raw line."""
    out = []
    for ln in range(a, b + 1):
        raw = lines[ln - 1]
        if PAGE_LINE_RE.match(raw): continue
        masked = SRC_MASK_RE.sub(lambda m: " " * len(m.group(0)), raw)
        masked = masked.replace("[", " ").replace("]", " ")
        for m in WORD_RE.finditer(masked):
            out.append((_norm_word(m.group(0)), ln, m.start(), m.end()))
    return out


def anchor_words(text, keep_brackets=False):
    t = (SRC_MASK_RE.sub(" ", text) if keep_brackets else MASK_RE.sub(" ", text)).replace("[", " ").replace("]", " ")
    return [_norm_word(w) for w in WORD_RE.findall(t)]


def split_anchors(anchors, keep_brackets=False):
    """`<first four> ... <last four>` -> (first words, last words); a short quotation given whole (no `...`) -> (words, None)."""
    parts = [p for p in SEP_RE.split(anchors.strip()) if p.strip()]
    if not parts: return [], None
    if len(parts) == 1: return anchor_words(parts[0], keep_brackets), None
    return anchor_words(parts[0], keep_brackets), anchor_words(parts[-1], keep_brackets)


def _find_seq(toks, seq, start=0):
    if not seq: return -1
    n = len(seq)
    for i in range(start, len(toks) - n + 1):
        if all(toks[i + k][0] == seq[k] for k in range(n)): return i
    return -1


def locate(lines, a, b, anchors, slack=SLACK):
    """((line, char), (line, char)) of the span from the first anchor's first word to the last anchor's last word, searched on lines
    a-slack..b+slack (never the header line); None when the anchors are not there in order."""
    lo, hi = max(2, a - slack), min(len(lines), b + slack)
    toks = _tokens(lines, lo, hi)
    for keep in (True, False):   # bracketed text in the anchors as the source's own words first, then as the writer's insert
        found = _locate(toks, *split_anchors(anchors, keep))
        if found: return found
    return None


def _locate(toks, first, last):
    i = _find_seq(toks, first)
    while i >= 0:
        if last is None:
            j = i + len(first) - 1
        else:
            k = _find_seq(toks, last, i + len(first))
            if k < 0:
                k = _find_seq(toks, last, i)   # a short span whose anchors overlap
            j = k + len(last) - 1 if k >= 0 else -1
        if j >= i:
            return (toks[i][1], toks[i][2]), (toks[j][1], toks[j][3])
        i = _find_seq(toks, first, i + 1)
    return None


def text_between(lines, start, end):
    (la, ca), (lb, cb) = start, end
    if la == lb: return lines[la - 1][ca:cb]
    return "\n".join([lines[la - 1][ca:]] + lines[la:lb - 1] + [lines[lb - 1][:cb]])


def words(wip, n, a, b, anchors):
    """(header line, the exact source text between the anchors); PointerError when the pointer or the anchors fail."""
    lines = unit_lines(wip, n)
    check_range(lines, n, a, b)
    loc = locate(lines, a, b, anchors)
    if not loc: raise PointerError(f"[u {n}:{a}{'-' + str(b) if b != a else ''}]: the words {anchors!r} are not on lines {max(2, a - SLACK)} to {min(len(lines), b + SLACK)} of unit {n} in that order")
    return lines[0], text_between(lines, *loc)


FIELD_RE = re.compile(r"(?:^|\|)\s*words:\s*([^|]+?)\s*(?=\||$)")
USE_RE = re.compile(r"(?:^|\|)\s*use:\s*([^|]+?)\s*(?=\||$)")


def words_field(item):
    """The `words:` field of a findings item, or None (an item in the older form, with the words in quotation marks)."""
    m = FIELD_RE.search(item)
    return m.group(1) if m else None


def quotation_items(findings_path):
    """[(line no, pointer (n, a, b) or None, anchors or None, use, the raw line)] for the `## Quotations` items of a findings file."""
    out, cur = [], None
    for i, l in enumerate(LN.read_lines(findings_path, errors="replace"), 1):
        m = re.match(r"^##\s+(.+?)\s*$", l)
        if m: cur = m.group(1); continue
        if cur != "Quotations" or not l.startswith("- "): continue
        pm = LN.UNIT_PTR_RE.search(l)
        ptr = (pm.group(1), int(pm.group(2)), int(pm.group(3) or pm.group(2))) if pm else None
        um = USE_RE.search(l)
        out.append((i, ptr, words_field(l), um.group(1) if um else "", l))
    return out



# ---------------------------------------------------------------- word keys (2026-10-25; the caption rule and --find)

KEY_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?![\d])|[^\W_]+(?:['’][^\W_]+)*")
BRACKET_RE = re.compile(r"\[https?://[^\]\s]+\]|(?<=\])\((?:[^()\s]|\([^()\s]*\))*\)|\[([^\]\n]{1,60})\]")
UNIT_HDR_RE = re.compile(r"^\[unit \d{3}/\d{3}")
GAP = 100          # keys allowed between two segments of a quotation cut by an ellipsis (the char matcher's 600 characters)


def _key(w):
    w = w.lower().replace("’", "").replace("'", "")
    return w.replace(",", "") if w[:1].isdigit() else w


TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?$")


def _cleaned(raw, keep_brackets=False):
    """(clean text, index map clean -> raw) with URLs, link targets, caption timestamps and 3-60 character bracketed spans blanked
    and the brackets of a 1-2 character insertion removed (its content kept and joined to its neighbours); keep_brackets keeps the
    words of a 3-60 character bracketed span (a source's own bracketed words, as `ledger quote --words` reads them)"""
    out, mp, i = [], [], 0
    for m in BRACKET_RE.finditer(raw):
        for k in range(i, m.start()): out.append(raw[k]); mp.append(k)
        inner = m.group(1)
        if inner is not None and not inner.startswith("http") and not TIMESTAMP_RE.match(inner.strip()) and (
                len(inner) <= 2 or keep_brackets or raw[m.end():m.end() + 1] == "("):   # [M]y; a link's text; kept bracketed words
            pad = len(inner) > 2
            if pad: out.append(" "); mp.append(m.start())
            for k in range(m.start() + 1, m.start() + 1 + len(inner)): out.append(raw[k]); mp.append(k)
            if pad: out.append(" "); mp.append(m.end() - 1)
        else:
            out.append(" "); mp.append(m.start())
        i = m.end()
    for k in range(i, len(raw)): out.append(raw[k]); mp.append(k)
    return "".join(out), mp


def key_tokens(raw, keep_brackets=False):
    """[(key, start, end)] of one line, offsets in the raw line"""
    clean, mp = _cleaned(raw, keep_brackets)
    return [(_key(m.group(0)), mp[m.start()], mp[m.end() - 1] + 1) for m in KEY_RE.finditer(clean)]


def keys_of(text):
    return [k for (k, _, _) in key_tokens(text)]


def unit_keys(lines, keep_brackets=False):
    """[(key, line, start, end)] over a unit's body (line 1, its header, never; nor a page marker or a continuation header);
    keep_brackets: the source's own bracketed words are words (the matcher tries the units both ways)"""
    out = []
    for ln in range(2, len(lines) + 1):
        raw = lines[ln - 1]
        if PAGE_LINE_RE.match(raw) or UNIT_HDR_RE.match(raw): continue
        for (k, a, b) in key_tokens(raw, keep_brackets): out.append((k, ln, a, b))
    return out


SEG_SPLIT_RE = re.compile(r"\s*(?:\.\.\.|…|\[(?!https?://)[^\]\n]{3,60}\])\s*")


def phrase_segments(text):
    """a quotation or phrase as key lists, split at ellipses and at insertions of three to sixty characters"""
    return [ks for ks in (keys_of(p) for p in SEG_SPLIT_RE.split(text)) if ks]


def _index(keys):
    idx = {}
    for i, t in enumerate(keys): idx.setdefault(t[0] if isinstance(t, tuple) else t, []).append(i)
    return idx


def _contig(keys, seq, i):
    n = len(seq)
    if i + n > len(keys): return False
    return all((keys[i + k][0] if isinstance(keys[i + k], tuple) else keys[i + k]) == seq[k] for k in range(n))


def match_segments(keys, segs, gap=GAP, idx=None, start=0):
    """(first key index, last key index) where the segments occur in order, each contiguous and at most `gap` keys after the one
    before; None when they do not. `keys` is unit_keys() output or a plain key list; idx an _index of it (built when not given)."""
    if not segs: return None
    idx = idx if idx is not None else _index(keys)
    for p in idx.get(segs[0][0], []):
        if p < start or not _contig(keys, segs[0], p): continue
        pos, ok = p + len(segs[0]), True
        for s in segs[1:]:
            q = next((c for c in idx.get(s[0], []) if pos <= c <= pos + gap and _contig(keys, s, c)), None)
            if q is None: ok = False; break
            pos = q + len(s)
        if ok: return p, pos - 1
    return None


def all_matches(keys, segs, gap=GAP, idx=None):
    out, start = [], 0
    idx = idx if idx is not None else _index(keys)
    while True:
        m = match_segments(keys, segs, gap, idx, start)
        if not m: return out
        out.append(m); start = m[0] + 1


def near_miss(units, qkeys, min_share=0.6):
    """the best-aligned window for a key list that is not found word for word: units is [(name, unit_keys)]; returns
    {unit, first, last (key indexes), ops [(tag, quotation words, source words)], share} or None. Alignment by offset votes (each
    quotation key's occurrences vote for where the quotation would start), then a word diff over that window; share is the
    matched share of the quotation's keys, and below min_share there is no near miss."""
    if not qkeys: return None
    best = None
    for name, keys in units:
        idx = _index(keys)
        votes = {}
        for i, k in enumerate(qkeys):
            for p in idx.get(k, []): votes[p - i] = votes.get(p - i, 0) + 1
        for off, v in sorted(votes.items(), key=lambda x: -x[1])[:5]:
            if best is not None and v <= best["votes"] - 2: break
            lo, hi = max(0, off - 3), min(len(keys), off + len(qkeys) + 3)
            win = [keys[j][0] for j in range(lo, hi)]
            sm = difflib.SequenceMatcher(None, qkeys, win, autojunk=False)
            blocks = [b for b in sm.get_matching_blocks() if b.size]
            if not blocks: continue
            matched = sum(b.size for b in blocks)
            share = matched / len(qkeys)
            if best is None or share > best["share"]:
                # the window runs from where the quotation's first word would stand to where its last would, so an unmatched
                # first or last word shows as a changed word, not as one the quotation adds
                f = max(0, lo + blocks[0].b - blocks[0].a)
                l = min(len(keys) - 1, lo + blocks[-1].b + blocks[-1].size - 1 + (len(qkeys) - blocks[-1].a - blocks[-1].size))
                sm2 = difflib.SequenceMatcher(None, qkeys, [keys[j][0] for j in range(f, l + 1)], autojunk=False)
                ops = [(tag, qkeys[i1:i2], [keys[f + j][0] for j in range(j1, j2)]) for tag, i1, i2, j1, j2 in sm2.get_opcodes() if tag != "equal"]
                best = {"unit": name, "first": f, "last": l, "ops": ops, "share": share, "votes": v}
    if not best or best["share"] < min_share: return None
    return best


def describe_ops(ops, limit=4):
    """the word differences in plain words: `the source has "x" where the quotation has "y"`, `the quotation adds "z"`,
    `the quotation drops "w"`"""
    out = []
    for tag, q, s in ops[:limit]:
        if tag == "replace": out.append(f'the source has "{" ".join(s)}" where the quotation has "{" ".join(q)}"')
        elif tag == "delete": out.append(f'the quotation adds "{" ".join(q)}"')
        elif tag == "insert": out.append(f'the quotation drops "{" ".join(s)}"')
    if len(ops) > limit: out.append(f"and {len(ops) - limit} more difference(s)")
    return "; ".join(out)


CAPTION_LINE_RE = re.compile(r"^\s*(?:\*\*)?\[\d{1,2}:\d{2}(?::\d{2})?\]")
SENT_END_RE = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s|$)")
ABBREV = set("mr mrs ms dr st jr sr no vs etc col gen lt capt sgt prof rev inc co corp maj adm gov sen rep ft mt jan feb mar apr jun jul aug sep sept oct nov dec".split())
MAX_LINES = 6      # a sentence is followed at most this many lines before and after the hit's own lines


def _is_end(text, m):
    """a sentence end, not an abbreviation's or an initial's full stop"""
    if text[m.start()] != ".": return True
    w = re.search(r"([A-Za-z]+)\.?$", text[:m.start() + 1].rstrip("."))
    if not w: return True
    word = w.group(1)
    return not (len(word) == 1 or word.lower() in ABBREV)


def sentence_span(lines, start, end):
    """((line, char), (line, char)) of the sentence that holds start..end, inside its paragraph (blank lines, page markers and
    unit headers bound it, and at most MAX_LINES lines either side); where the hit's lines carry no sentence punctuation (an
    unpunctuated caption), the whole lines"""
    (la, ca), (lb, cb) = start, end
    def body(ln): return 2 <= ln <= len(lines) and lines[ln - 1].strip(" \t>") and not PAGE_LINE_RE.match(lines[ln - 1]) and not UNIT_HDR_RE.match(lines[ln - 1])
    hit_text = "\n".join(lines[la - 1:lb])
    if CAPTION_LINE_RE.match(lines[la - 1]) and not any(_is_end(hit_text, m) for m in SENT_END_RE.finditer(hit_text)):
        return (la, 0), (lb, len(lines[lb - 1]))
    p0 = la
    while p0 - 1 >= 2 and body(p0 - 1) and la - (p0 - 1) <= MAX_LINES and not CAPTION_LINE_RE.match(lines[p0 - 1]): p0 -= 1
    p1 = lb
    while p1 + 1 <= len(lines) and body(p1 + 1) and (p1 + 1) - lb <= MAX_LINES and not CAPTION_LINE_RE.match(lines[p1]): p1 += 1
    # the paragraph's text with each line's start offset, to map positions back to (line, char)
    starts, parts, pos = {}, [], 0
    for ln in range(p0, p1 + 1):
        starts[ln] = pos; parts.append(lines[ln - 1]); pos += len(lines[ln - 1]) + 1
    text = "\n".join(parts)
    hs, he = starts[la] + ca, starts[lb] + cb
    s0 = 0
    for m in SENT_END_RE.finditer(text, 0, hs):
        if m.end() <= hs and _is_end(text, m): s0 = m.end()
    while s0 < len(text) and text[s0].isspace(): s0 += 1
    e0 = len(text)
    for m in SENT_END_RE.finditer(text, he):
        if _is_end(text, m): e0 = m.end(); break
    def back(p):
        ln = max(l for l in starts if starts[l] <= p)
        return ln, p - starts[ln]
    a, b = back(s0), back(max(s0, e0 - 1))
    return a, (b[0], b[1] + 1)


def _units_of(wip):
    d = os.path.join(wip, "units")
    return sorted(f[:-4] for f in os.listdir(d) if re.match(r"^\d{3}\.txt$", f))


def find(wip, phrase, gap=GAP):
    """every hit of a phrase in the task's units, in manifest (file) order: [{unit, header, start (line, char), end, sentence
    ((line, char), (line, char)), phrase_text, sentence_text}]; ([], near miss or None) when nothing matches"""
    segs = phrase_segments(phrase)
    if not segs: raise PointerError(f"--find {phrase!r}: no words in the phrase")
    hits, cache = [], []
    for n in _units_of(wip):
        lines = unit_lines(wip, n)
        keys = unit_keys(lines)
        cache.append((n, keys, lines))
        found = {}
        for kk in (keys, unit_keys(lines, keep_brackets=True)):   # the source's bracketed words dropped, then kept
            for (i, j) in all_matches(kk, segs, gap):
                found.setdefault(((kk[i][1], kk[i][2]), (kk[j][1], kk[j][3])), None)
        for (st, en) in sorted(found):
            sa, sb = sentence_span(lines, st, en)
            hits.append({"unit": n, "header": lines[0], "start": st, "end": en, "sentence": (sa, sb),
                         "phrase_text": text_between(lines, st, en), "sentence_text": text_between(lines, sa, sb)})
    if hits: return hits, None
    nm = near_miss([(n, k) for (n, k, _) in cache], [k for s in segs for k in s])
    if nm:
        n, keys, lines = next(c for c in cache if c[0] == nm["unit"])
        st, en = (keys[nm["first"]][1], keys[nm["first"]][2]), (keys[nm["last"]][1], keys[nm["last"]][3])
        nm.update({"header": lines[0], "start": st, "end": en, "text": text_between(lines, st, en)})
    return [], nm
