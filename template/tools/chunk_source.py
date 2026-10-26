#!/usr/bin/env python3
"""chunk_source.py: pre-cut a held source into numbered reading units.

    python3 tools/chunk_source.py <source file(s) or dir> --wip wip/<task> [--words 2500] [--by auto|page|post|heading|timestamp|words] [--set B]
    python3 tools/chunk_source.py --wip wip/<task> --verify
    python3 tools/chunk_source.py --wip wip/<task> --status
    python3 tools/chunk_source.py --wip wip/<task> --mark 007 read [--note "..."]

Writes wip/<task>/units/NNN.txt (one header line, then the exact source text of
the unit) and wip/<task>/units/manifest.md (a table the agent fills as it reads).
Units break on natural boundaries, never mid-sentence: page markers, post files,
markdown headings, capitalised OCR section lines and transcript timestamps, then
paragraphs and sentences as the fallback; --words is the target size and 1.5x
the hard ceiling. Doc: tools/chunk_source.md.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)

# Boundary strengths (lower is stronger).
L_PAGE, L_HEADING, L_SECTION, L_PARA, L_SENT, L_WORD = 0, 1, 2, 3, 4, 5
LEVEL_NAMES = {L_PAGE: 'page/post', L_HEADING: 'heading', L_SECTION: 'timestamp/section',
               L_PARA: 'paragraph', L_SENT: 'sentence', L_WORD: 'word (forced)'}

# === page N === and the Apple Vision OCR form === page-001.png (page, optional hyphen, digits, optional extension, optional trailing ===; 2026-10-22)
PAGE_RE = re.compile(r'^(?:--- ?page (\d+) ?---|=== ?page[ -]?(\d+)(?:\.[A-Za-z0-9]+)?(?: ?===)?|\[page (\d+)\]|<!-- ?page (\d+) ?-->)[ \t]*$', re.M)
HEADING_RE = re.compile(r'^(#{1,6})[ \t]+(\S.*?)[ \t]*$', re.M)
TS_RE = re.compile(r'^(?:\*\*\[(\d{1,2}:\d{2}:\d{2})\]\*\*|\[(\d{1,2}:\d{2}:\d{2})\]|(\d{1,2}:\d{2}:\d{2})\b)', re.M)
CAPS_RE = re.compile(r'^[A-Z][A-Z0-9 ,.;:\'’&/()\-]{3,80}$')
SENT_END_RE = re.compile(r'(?<=[.!?…])["”’)\]]*[ \t]+|(?<=[.!?…]["”’)\]])\n|(?<=[.!?…])\n')
HEADER_RE = re.compile(r'^\[unit (\d+)/(\d+)(?: continues)?\] source: (.+?) \| span: (.*?) \| words: (\d+)[ \t]*$')
UNIT_SPLIT_RE = re.compile(r'^\[unit \d+/\d+(?: continues)?\] source: .*? \| span: .*? \| words: \d+[ \t]*\n', re.M)

STATUS_VALUES = ('', 'read', 'findings written', 'rowed')


def words(s):
    return len(s.split())


def fmt(n):
    return f'{n:,}'


def read_text(path):
    # the parser library's reader (phase 2): CRLF and a lone CR become LF, so a unit's line numbers are the ones every other
    # reader of the unit counts (intake_gate, the agents); the bytes are otherwise kept (surrogateescape)
    return LN.read_text(path, errors='surrogateescape')


def write_text(path, s):
    with open(path, 'w', encoding='utf-8', errors='surrogateescape', newline='\n') as f:   # LF on every platform
        f.write(s)


def rel(path):
    try:
        r = os.path.relpath(path)
        return r if not r.startswith('..') else path
    except ValueError:
        return path


class Leaf:
    __slots__ = ('start', 'end', 'level', 'meta', 'file')

    def __init__(self, start, end, level, meta, file):
        self.start, self.end, self.level, self.meta, self.file = start, end, level, dict(meta), file


# ---------------------------------------------------------------- splitting

def _split_at(text, s, e, positions):
    """Cut [s, e) at the given positions (sorted, each > s and < e)."""
    out, prev = [], s
    for p in positions:
        if s < p < e:
            out.append((prev, p))
            prev = p
    out.append((prev, e))
    return out


def split_pages(text, s, e):
    cuts, nums = [], {}
    for m in PAGE_RE.finditer(text, s, e):
        n = next(g for g in m.groups() if g)
        cuts.append(m.start())
        nums[m.start()] = int(n)
    segs = []
    for a, b in _split_at(text, s, e, cuts):
        segs.append((a, b, {'page': nums.get(a), 'starts_page': a in nums}))
    return segs, len(cuts)


def split_headings(text, s, e):
    cuts, titles = [], {}
    for m in HEADING_RE.finditer(text, s, e):
        cuts.append(m.start())
        titles[m.start()] = m.group(2)
    segs = []
    for a, b in _split_at(text, s, e, cuts):
        segs.append((a, b, {'heading': titles.get(a), 'starts_heading': a in titles}))
    return segs, len(cuts)


def split_timestamps(text, s, e):
    cuts, stamps = [], {}
    for m in TS_RE.finditer(text, s, e):
        ts = next(g for g in m.groups() if g)
        cuts.append(m.start())
        stamps[m.start()] = ts
    segs = []
    for a, b in _split_at(text, s, e, cuts):
        segs.append((a, b, {'ts': stamps.get(a), 'starts_ts': a in stamps}))
    return segs, len(cuts)


def split_caps(text, s, e):
    """Capitalised section lines (OCR scans without markers): a line of capitals
    preceded by a blank line or the segment start."""
    cuts, titles = [], {}
    pos = s
    prev_blank = True
    while pos < e:
        nl = text.find('\n', pos, e)
        line_end = e if nl < 0 else nl
        line = text[pos:line_end]
        stripped = line.strip()
        if (stripped and prev_blank and CAPS_RE.match(stripped) and sum(c.isalpha() for c in stripped) >= 4
                and not re.match(r'^[A-Z]{1,4}[:;]', stripped)):
            cuts.append(pos)
            titles[pos] = re.sub(r'\s+', ' ', stripped)
        prev_blank = (stripped == '')
        pos = line_end + 1
    segs = []
    for a, b in _split_at(text, s, e, cuts):
        segs.append((a, b, {'heading': titles.get(a), 'starts_heading': a in titles, 'caps': a in titles}))
    return segs, len(cuts)


def split_paragraphs(text, s, e):
    """Blank-line separated blocks; the blank lines stay with the block before."""
    cuts = []
    for m in re.finditer(r'\n(?:[ \t]*\n)+', text[s:e]):
        p = s + m.end()
        if p < e:
            cuts.append(p)
    return [(a, b, {}) for a, b in _split_at(text, s, e, cuts)]


def split_sentences(text, s, e):
    cuts = []
    for m in SENT_END_RE.finditer(text, s, e):
        p = m.end()
        if s < p < e:
            cuts.append(p)
    return [(a, b, {}) for a, b in _split_at(text, s, e, cuts)]


def split_words_forced(text, s, e, ceiling):
    """Last resort for a sentence over the ceiling: cut at a space every ~ceiling/2 words."""
    cuts, count, pos = [], 0, s
    step = max(50, ceiling // 2)
    for m in re.finditer(r'\s+', text[s:e]):
        count += 1
        if count >= step:
            cuts.append(s + m.end())
            count = 0
    return [(a, b, {'forced': True}) for a, b in _split_at(text, s, e, cuts)]


# The court and inquiry transcript form (2026-10-22, phase 6b handoff 3): every page is numbered lines 1 to 25 (the number alone at
# the line's left, the text after it) and the page number stands alone on its own line, far indented, after the page (a footer, as
# the inquiry's pdftotext transcripts print it, the next page opening with a form feed) or before it (a header). Units are cut on
# pages and each span carries the transcript's own page:line (Day 117, 159:24).
TRANSCRIPT_LINE_RE = re.compile(r'^\f?[ \t]{0,16}(\d{1,2})(?=[ \t]|$)', re.M)
TRANSCRIPT_PAGE_RE = re.compile(r'^\f?[ \t]{20,}(\d{1,5})[ \t]*$', re.M)


def split_transcript_pages(text, s, e):
    """[(start, end, meta)], page count: the transcript form's pages, or ([(s, e, {})], 0) when the text is not in that form (fewer
    than two page numbers, page numbers not consecutive, or fewer than five numbered lines per page)."""
    pages = [(m.start(), m.end(), int(m.group(1))) for m in TRANSCRIPT_PAGE_RE.finditer(text, s, e)]
    nums = [m for m in TRANSCRIPT_LINE_RE.finditer(text, s, e) if 1 <= int(m.group(1)) <= 50]
    if len(pages) < 2 or any(b[2] != a[2] + 1 for a, b in zip(pages, pages[1:])) or len(nums) < 5 * len(pages):
        return [(s, e, {})], 0
    footer = nums[0].start() < pages[0][0]   # numbered lines before the first page number: the number closes its page
    if footer:
        cuts = [b + 1 for _, b, _ in pages if b + 1 < e and text[b + 1:e].strip()]   # each page ends after its number's line (trailing blank lines stay with the last page)
        label = {a: n for a, n in zip([s] + cuts, [n for _, _, n in pages])}
    else:
        cuts = [a for a, _, _ in pages]
        label = {a: n for a, _, n in pages}
    segs = []
    for a, b in _split_at(text, s, e, cuts):
        n = label.get(a)
        segs.append((a, b, {'page': n, 'starts_page': n is not None, 'tp': True}))
    # each page must carry its numbered lines in order: a run 1, 2, 3, ... of at least ten on four pages in five (an OCR'd document
    # with a stray indented number and a numbered list is not a transcript)
    def numbered(a, b):
        run = 0
        for m in TRANSCRIPT_LINE_RE.finditer(text, a, b):
            v = int(m.group(1))
            if v == run + 1: run = v
            elif v == 1: run = 1
            if run >= 10: return True
        return False
    labelled = [(a, b) for a, b, m in segs if m['page'] is not None]
    if sum(1 for a, b in labelled if numbered(a, b)) < 0.8 * len(labelled):
        return [(s, e, {})], 0
    return segs, len(pages)


def make_leaves(text, fi, ceiling, by, counts, base_meta=None):
    """Hierarchical split of one file into leaves (paragraph-sized or smaller),
    each tagged with the strongest boundary at its start and its context meta."""
    base_meta = base_meta or {}
    e = len(text)
    counts.setdefault('pages', 0); counts.setdefault('headings', 0)
    counts.setdefault('timestamps', 0); counts.setdefault('caps', 0)
    counts.setdefault('para_over_ceiling', 0); counts.setdefault('forced', 0)

    # level 0: pages
    if by in ('auto', 'page'):
        page_segs, n = split_pages(text, 0, e)
        if n == 0:
            page_segs, n = split_transcript_pages(text, 0, e)
            counts['transcript'] = n > 0
        counts['pages'] = n
    else:
        page_segs, n = [(0, e, {})], 0
    if n == 0:
        page_segs = [(0, e, {})]
    level0 = [(a, b, dict(base_meta, **m), L_PAGE) for a, b, m in page_segs]

    leaves = []
    heading_ctx = {'heading': None}
    ts_ctx = {'ts': None}

    def descend_heading(a, b, meta, lvl):
        if by in ('auto', 'page', 'post', 'heading'):
            segs, n = split_headings(text, a, b)
            counts['headings'] += n
        else:
            segs, n = [(a, b, {})], 0
        first = True
        for sa, sb, m in segs:
            if m.get('starts_heading'):
                heading_ctx['heading'] = m['heading']
                ts_ctx['ts'] = None
            mm = dict(meta, **m)
            mm['heading'] = heading_ctx['heading']
            descend_section(sa, sb, mm, lvl if first else L_HEADING)
            first = False

    def descend_section(a, b, meta, lvl):
        if by in ('auto', 'page', 'post', 'heading', 'timestamp'):
            segs, n = split_timestamps(text, a, b)
            counts['timestamps'] += n
        else:
            segs, n = [(a, b, {})], 0
        if n == 0 and by in ('auto', 'page', 'post', 'heading') and not meta.get('page'):
            # caps section lines only matter where nothing better exists
            csegs, cn = split_caps(text, a, b)
            counts['caps'] += cn
            if cn > 0:
                first = True
                for sa, sb, m in csegs:
                    if m.get('starts_heading'):
                        heading_ctx['heading'] = m['heading']
                    mm = dict(meta, **m)
                    mm['heading'] = heading_ctx['heading']
                    descend_para(sa, sb, mm, lvl if first else L_SECTION)
                    first = False
                return
        first = True
        for sa, sb, m in segs:
            if m.get('starts_ts'):
                ts_ctx['ts'] = m['ts']
            mm = dict(meta, **m)
            mm['ts'] = ts_ctx['ts']
            descend_para(sa, sb, mm, lvl if first else L_SECTION)
            first = False

    def descend_para(a, b, meta, lvl):
        first = True
        rest = {k: (False if k.startswith('starts_') else v) for k, v in meta.items()}
        for pa, pb, m in split_paragraphs(text, a, b):
            l = lvl if first else L_PARA
            if not first:
                meta = rest
            first = False
            if words(text[pa:pb]) <= ceiling:
                leaves.append(Leaf(pa, pb, l, meta, fi))
                continue
            counts['para_over_ceiling'] += 1
            sfirst = True
            for sa, sb, _ in split_sentences(text, pa, pb):
                l2 = l if sfirst else L_SENT
                if not sfirst:
                    meta = rest
                sfirst = False
                if words(text[sa:sb]) <= ceiling:
                    leaves.append(Leaf(sa, sb, l2, meta, fi))
                    continue
                wfirst = True
                for wa, wb, wm in split_words_forced(text, sa, sb, ceiling):
                    counts['forced'] += 1
                    leaves.append(Leaf(wa, wb, l2 if wfirst else L_WORD, dict(meta, **wm), fi))
                    wfirst = False

    for a, b, meta, lvl in level0:
        descend_heading(a, b, meta, lvl)

    # a leaf that starts a page keeps that fact even after the descent
    for lf in leaves:
        lf.meta['starts_page'] = bool(lf.meta.get('starts_page')) and lf.start in {a for a, _, _, _ in level0}
    return leaves


# ---------------------------------------------------------------- packing

def pack(leaves, texts, target, ceiling, allow_cross_file):
    """Greedy packing with a look-ahead window: a unit closes at the strongest
    boundary available between 0.6x target and the ceiling, nearest the target
    on ties. Never crosses a file unless allowed (post sets), and then only
    when the earlier file ends with a newline."""
    wc = [words(texts[lf.file][lf.start:lf.end]) for lf in leaves]
    n = len(leaves)
    units, i = [], 0
    while i < n:
        # the stretch this unit may draw from: same file, or across files when allowed
        stop = n
        for k in range(i + 1, n):
            if leaves[k].file != leaves[k - 1].file:
                if not allow_cross_file or not texts[leaves[k - 1].file].endswith('\n'):
                    stop = k
                    break
        remaining = sum(wc[i:stop])
        if remaining <= ceiling and remaining <= target * 1.25:
            units.append(leaves[i:stop]); i = stop; continue
        cum, j, best = 0, i, None
        while j < stop:
            if cum + wc[j] > ceiling and j > i:
                break
            cum += wc[j]; j += 1
            after = L_PAGE if j == stop else leaves[j].level
            if cum >= target * 0.6 or j == stop:
                score = (after, abs(cum - target))
                if best is None or score < best[0]:
                    best = (score, j)
        if best is None:
            best = ((9, 0), j)
        units.append(leaves[i:best[1]]); i = best[1]
    return units


# ---------------------------------------------------------------- spans

def line_of(text, pos, line_starts):
    """1-based line number of char offset pos (bisect over line starts)."""
    import bisect
    return bisect.bisect_right(line_starts, pos)


def line_starts_of(text):
    starts = [0]
    for m in re.finditer(r'\n', text):
        starts.append(m.end())
    return starts


def describe(group, text, line_starts, next_leaf, post_meta):
    """Span text for the leaves of one source file inside a unit."""
    first, last = group[0], group[-1]
    end_pos = last.end
    while end_pos > first.start and text[end_pos - 1] in '\r\n':
        end_pos -= 1
    l1 = line_of(text, first.start, line_starts)
    l2 = line_of(text, max(first.start, end_pos - 1), line_starts)
    parts = []
    if post_meta:
        title, date = post_meta
        whole = first.start == 0 and (next_leaf is None or next_leaf.file != first.file)
        p = f'post "{title}" ({date})' if date else f'post "{title}"'
        if not whole:
            if first.start == 0:
                p += ', beginning'
            elif next_leaf is None or next_leaf.file != first.file:
                p += ', end'
            else:
                p += ', middle'
        parts.append(p)
    p1, p2 = first.meta.get('page'), last.meta.get('page')
    if first.meta.get('tp') or last.meta.get('tp'):
        # the transcript form: its own page:line, from the first and last numbered lines in the unit
        nl = list(TRANSCRIPT_LINE_RE.finditer(text, first.start, last.end))
        a, b = (nl[0].group(1), nl[-1].group(1)) if nl else ('?', '?')
        if p1 is None and p2 is None: s = 'after the last transcript page'
        elif p1 is None: s = f'front matter to transcript page {p2} (to {p2}:{b})'
        elif p2 is None: s = f'transcript page {p1} on, then text after the last page ({p1}:{a} on)'
        elif p1 == p2: s = f'transcript page {p1} ({p1}:{a} to {p2}:{b})'
        else: s = f'transcript pages {p1}-{p2} ({p1}:{a} to {p2}:{b})'
        flags = []
        if p1 is not None and not first.meta.get('starts_page'):
            flags.append('starts mid-page')
        if next_leaf is not None and next_leaf.file == last.file and next_leaf.meta.get('page') == p2 and p2 is not None:
            flags.append('ends mid-page')
        if flags:
            s += f' ({", ".join(flags)})'
        parts.append(s)
    elif p1 is not None or p2 is not None:
        if p1 is None:
            s = f'front matter to page {p2}'
        elif p1 == p2:
            s = f'page {p1}'
        else:
            s = f'pages {p1}-{p2}'
        flags = []
        if p1 is not None and not first.meta.get('starts_page'):
            flags.append('starts mid-page')
        if next_leaf is not None and next_leaf.file == last.file and next_leaf.meta.get('page') == p2 and p2 is not None:
            flags.append('ends mid-page')
        if flags:
            s += f' ({", ".join(flags)})'
        parts.append(s)
    stamps = [lf.meta.get('ts') for lf in group if lf.meta.get('ts')]
    has_ts = bool(stamps)
    if has_ts:
        s = f'{stamps[0]}-{stamps[-1]}' if stamps[0] != stamps[-1] else stamps[0]
        first_ts_leaf = next(lf for lf in group if lf.meta.get('ts'))
        if not first_ts_leaf.meta.get('starts_ts'):
            s = f'from within {stamps[0]} to {stamps[-1]}' if stamps[0] != stamps[-1] else f'within {stamps[0]}'
        if first.meta.get('ts') is None:
            s = 'header, then ' + s
        if last.meta.get('ts') is None and last.meta.get('heading'):
            s += f', then "{last.meta["heading"]}"'
        parts.append(s)
    h1, h2 = first.meta.get('heading'), last.meta.get('heading')
    if (h1 or h2) and not has_ts and not post_meta:
        h1s = f'"{h1}"' if h1 else 'before the first heading'
        if h1 == h2:
            parts.append(f'under {h1s}')
        else:
            parts.append(f'from {h1s} to "{h2}"')
    mid = []
    if first.start > 0 and text[first.start - 1] != '\n':
        mid.append('starts mid-line')
    if last.end < len(text) and text[last.end - 1] != '\n':
        mid.append('ends mid-line')
    if mid:
        parts.append(f'lines {l1}-{l2} ({", ".join(mid)}: a sentence cut inside a paragraph over the ceiling)')
    else:
        parts.append(f'lines {l1}-{l2}')
    if any(lf.meta.get('forced') for lf in group):
        parts.append('contains a forced mid-sentence cut (sentence over the ceiling)')
    return ', '.join(parts), l1, l2


def _first_ts(group):
    for lf in group:
        if lf.meta.get('ts'):
            return lf.meta['ts']
    return '?'


# ---------------------------------------------------------------- sources

def gather_sources(paths, by, set_key):
    """Return (list of (path, post_meta or None), mode_note)."""
    out, notes = [], []
    for p in paths:
        if os.path.isdir(p) or os.path.basename(p) == 'sets.json':
            d = p if os.path.isdir(p) else os.path.dirname(p)
            sets_path = os.path.join(d, 'sets.json')
            entries = None
            if os.path.exists(sets_path):
                sets = json.load(open(sets_path, encoding='utf-8'))
                if set_key:
                    if set_key not in sets:
                        sys.exit(f'chunk_source: key {set_key!r} not in {sets_path}; keys: {", ".join(sets)}')
                    entries = sets[set_key]
                    notes.append(f'{rel(d)}: {len(entries)} posts from sets.json key {set_key}')
                elif by == 'post':
                    notes.append(f'{rel(d)}: sets.json present but no --set given; taking every .txt in name order')
            if entries is not None:
                for ent in entries:
                    date, title, url, fname = ent[0], ent[1], ent[2], ent[3]
                    out.append((os.path.join(d, fname), (title, date)))
            else:
                files = sorted(f for f in os.listdir(d) if f.endswith('.txt'))
                if not files:
                    sys.exit(f'chunk_source: no .txt files in {d}')
                for f in files:
                    out.append((os.path.join(d, f), post_meta_from_file(os.path.join(d, f))))
                if by == 'post':
                    notes.append(f'{rel(d)}: {len(files)} .txt files in name order')
        else:
            if not os.path.exists(p):
                sys.exit(f'chunk_source: no such file {p}')
            out.append((p, post_meta_from_file(p) if by == 'post' else None))
    return out, notes


def post_meta_from_file(path):
    title, date = None, None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for _ in range(6):
            line = f.readline()
            if not line:
                break
            m = re.match(r'^#\s+(.*\S)\s*$', line)
            if m and title is None:
                title = m.group(1)
            m = re.match(r'^Published:\s*(\S.*?)\s*$', line)
            if m:
                date = m.group(1)
    return (title or os.path.basename(path), date)


# ---------------------------------------------------------------- build

def build(args):
    wip = args.wip
    udir = os.path.join(wip, 'units')
    if os.path.exists(os.path.join(udir, 'manifest.md')) and not args.force and not args.dry_run:
        sys.exit(f'chunk_source: {udir}/manifest.md exists; a running task must not be re-split. Use --force to rebuild (statuses are lost).')
    target = args.words
    ceiling = args.ceiling or int(round(target * 1.5))
    sources, notes = gather_sources(args.paths, args.by, args.set)
    if not sources:
        sys.exit('chunk_source: nothing to split')
    texts, leaves, per_file = [], [], []
    for fi, (path, post_meta) in enumerate(sources):
        text = read_text(path)
        texts.append(text)
        counts = {}
        lv = make_leaves(text, fi, ceiling, args.by, counts)
        leaves.extend(lv)
        per_file.append({'path': path, 'post': post_meta, 'words': words(text), 'counts': counts,
                         'line_starts': line_starts_of(text), 'lines': text.count('\n') + (0 if text.endswith('\n') else 1)})
    # decide what to say about the split basis
    for pf in per_file:
        c = pf['counts']
        basis = []
        if c['pages'] and c.get('transcript'):
            basis.append(f"{c['pages']} transcript pages (numbered lines, the page number alone on a line; spans give the transcript's page:line)")
        elif c['pages']:
            basis.append(f"{c['pages']} page markers")
        if pf['post']:
            basis.append('post file')
        if c['headings']:
            basis.append(f"{c['headings']} markdown headings")
        if c['timestamps']:
            basis.append(f"{c['timestamps']} timestamp lines")
        if c['caps']:
            basis.append(f"{c['caps']} capitalised section lines (weak boundaries)")
        if args.by in ('page', 'heading', 'timestamp') and not c[{'page': 'pages', 'heading': 'headings', 'timestamp': 'timestamps'}[args.by]]:
            basis.insert(0, f'--by {args.by} asked but no such markers in this file; fell back to the finer boundaries')
        if not basis:
            basis.append('no markers found: paragraphs and sentences only')
        elif not c['pages'] and not c['timestamps'] and not pf['post'] and not c['headings']:
            basis.insert(0, 'no page markers and no markdown headings')
        extra = ''
        if c['para_over_ceiling']:
            extra += f"; {c['para_over_ceiling']} paragraph(s) over the ceiling split at sentence ends"
        if c['forced']:
            extra += f"; {c['forced']} forced mid-sentence cut(s) (a sentence over the ceiling)"
        pf['basis'] = ', '.join(basis) + extra
    allow_cross = args.by == 'post' or any(pf['post'] for pf in per_file)
    units = pack(leaves, texts, target, ceiling, allow_cross)
    total = len(units)
    width = max(3, len(str(total)))

    rows, files_out = [], []
    for ui, unit in enumerate(units, 1):
        num = str(ui).zfill(width)
        # group by file, in order
        groups = []
        for lf in unit:
            if groups and groups[-1][0] == lf.file:
                groups[-1][1].append(lf)
            else:
                groups.append((lf.file, [lf]))
        chunks, src_cells, span_cells, uwords = [], [], [], 0
        for gi, (fi, group) in enumerate(groups):
            pf = per_file[fi]
            text = texts[fi]
            # the leaf after this group (for mid-page / mid-post detection)
            last_idx = leaves.index(group[-1])
            next_leaf = leaves[last_idx + 1] if last_idx + 1 < len(leaves) else None
            span, l1, l2 = describe(group, text, pf['line_starts'], next_leaf, pf['post'])
            body = text[group[0].start:group[-1].end]
            w = words(body)
            uwords += w
            tag = f'[unit {num}/{str(total).zfill(width)}]' if gi == 0 else f'[unit {num}/{str(total).zfill(width)} continues]'
            header = f'{tag} source: {rel(pf["path"])} | span: {span} | words: {w}'
            chunks.append(header + '\n' + body)
            src_cells.append(os.path.basename(pf['path']))
            span_cells.append(span)
        files_out.append((f'{num}.txt', ''.join(chunks)))
        rows.append((num, '; '.join(src_cells), '; '.join(span_cells), uwords))

    sizes = [r[3] for r in rows]
    total_words = sum(pf['words'] for pf in per_file)
    cmd = 'python3 tools/chunk_source.py ' + ' '.join(sys.argv[1:])
    head = [f'# Units: {wip}', '']
    head.append(f'- Built: {dt.datetime.now().strftime("%Y-%m-%d %H:%M")} by `{cmd}`')
    head.append(f'- Sources: {len(per_file)} file(s), {fmt(total_words)} words, {fmt(sum(pf["lines"] for pf in per_file))} lines; split mode `{args.by}`')
    if len(per_file) <= 6:
        for pf in per_file:
            head.append(f'  - `{rel(pf["path"])}`: {fmt(pf["words"])} words; {pf["basis"]}')
    else:
        big = [pf for pf in per_file if pf['words'] > ceiling]
        head.append(f'  - {len(per_file)} post files under `{rel(os.path.dirname(per_file[0]["path"]))}`; each post is a boundary; '
                    + (f'{len(big)} post(s) longer than the ceiling ({", ".join(os.path.basename(pf["path"]) for pf in big)}) split at paragraph ends' if big else 'none longer than the ceiling'))
    for n in notes:
        head.append(f'  - {n}')
    head.append(f'- Units: {total}; target {fmt(target)} words, ceiling {fmt(ceiling)}; largest {fmt(max(sizes))}, smallest {fmt(min(sizes))}, mean {fmt(round(sum(sizes) / len(sizes)))}')
    over = [r[0] for r in rows if r[3] > ceiling]
    if over:
        head.append(f'- Over the ceiling (a single leaf larger than the ceiling): units {", ".join(over)}')
    head.append('- Status values, filled by the reading agent: blank = unread; `read`; `findings written` (recorded in parts/findings.md); `rowed` (rows written to the note). '
                f'`python3 tools/chunk_source.py --wip {wip} --mark NNN "findings written" [--note "..."]` sets a cell by command; `--status` lists the units still without findings; `--verify` checks the units against the source.')
    head.append('- Read units in manifest order; before each large output copy the unit in hand by shell: '
                f'`cp {wip}/units/NNN.txt {wip}/current-unit.md`. Never re-split the source.')
    head.append('')
    head.append('| unit | source | span | words | status | notes |')
    head.append('|---|---|---|---|---|---|')
    for num, src, span, w in rows:
        head.append(f'| {num} | {src} | {span} | {fmt(w)} |  |  |')
    manifest = '\n'.join(head) + '\n'

    print(f'chunk_source: {len(per_file)} source file(s), {fmt(total_words)} words -> {total} units '
          f'(target {fmt(target)}, ceiling {fmt(ceiling)}; largest {fmt(max(sizes))}, smallest {fmt(min(sizes))}, mean {fmt(round(sum(sizes)/len(sizes)))})')
    if len(per_file) <= 6:
        for pf in per_file:
            print(f'  {rel(pf["path"])}: {pf["basis"]}')
    else:
        print(f'  {len(per_file)} files; {sum(1 for pf in per_file if pf["words"] > ceiling)} longer than the ceiling and split inside')
    for n in notes:
        print(f'  {n}')
    if args.dry_run:
        for num, src, span, w in rows:
            print(f'  {num}  {fmt(w):>6}  {span}' + ('' if len(per_file) == 1 else f'  [{src}]'))
        return
    os.makedirs(udir, exist_ok=True)
    if args.force:
        for f in os.listdir(udir):
            if re.match(r'^\d+\.txt$', f) or f == 'manifest.md':
                os.remove(os.path.join(udir, f))
    for name, content in files_out:
        write_text(os.path.join(udir, name), content)
    write_text(os.path.join(udir, 'manifest.md'), manifest)
    print(f'  wrote {total} unit files and manifest.md under {udir}')
    ok = verify(args, quiet=False)
    if not ok:
        sys.exit(2)


# ---------------------------------------------------------------- verify / status / mark

def unit_files(udir):
    names = sorted(f for f in os.listdir(udir) if re.match(r'^\d+\.txt$', f))
    return names


def verify(args, quiet=False):
    udir = os.path.join(args.wip, 'units')
    if not os.path.isdir(udir):
        sys.exit(f'chunk_source: no units directory at {udir}')
    names = unit_files(udir)
    per_source = {}   # path -> list of (unit, text)
    order = []
    header_words_ok = True
    for name in names:
        content = read_text(os.path.join(udir, name))
        pieces = UNIT_SPLIT_RE.split(content)
        headers = UNIT_SPLIT_RE.findall(content)
        if pieces[0] != '' or len(headers) != len(pieces) - 1:
            print(f'verify: {name}: malformed header line(s)')
            return False
        for h, body in zip(headers, pieces[1:]):
            m = HEADER_RE.match(h.rstrip('\n'))
            if not m:
                print(f'verify: {name}: unparsable header: {h.strip()}')
                return False
            src = m.group(3)
            declared = int(m.group(5))
            if words(body) != declared:
                header_words_ok = False
                print(f'verify: {name}: header says {declared} words, body has {words(body)}')
            if src not in per_source:
                per_source[src] = []
                order.append(src)
            per_source[src].append((name, body))
    all_ok = header_words_ok
    for src in order:
        if not os.path.exists(src):
            print(f'verify: source not found: {src}')
            all_ok = False
            continue
        original = read_text(src)
        rebuilt = ''.join(b for _, b in per_source[src])
        if rebuilt == original:
            if not quiet and len(order) <= 6:
                print(f'verify: {src}: {len(per_source[src])} unit part(s), {fmt(words(original))} words: exact match')
        else:
            all_ok = False
            k = next((i for i, (a, b) in enumerate(zip(rebuilt, original)) if a != b), min(len(rebuilt), len(original)))
            line = original.count('\n', 0, k) + 1
            print(f'verify: {src}: MISMATCH at char {k} (source line {line}); rebuilt {len(rebuilt)} chars, source {len(original)} chars')
    print(f'verify: {len(names)} units, {len(order)} source file(s): ' + ('OK, units concatenate back to the source exactly' if all_ok else 'FAILED'))
    return all_ok


def read_manifest(wip):
    path = os.path.join(wip, 'units', 'manifest.md')
    if not os.path.exists(path):
        sys.exit(f'chunk_source: no manifest at {path}')
    lines = read_text(path).split('\n')
    rows = []
    for i, line in enumerate(lines):
        if re.match(r'^\| \d+ \|', line):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 6:
                rows.append({'i': i, 'unit': cells[0], 'source': cells[1], 'span': cells[2], 'words': cells[3],
                             'status': cells[4], 'notes': cells[5]})
    return path, lines, rows


def status(args):
    path, lines, rows = read_manifest(args.wip)
    done = [r for r in rows if r['status'] in ('findings written', 'rowed')]
    read_only = [r for r in rows if r['status'] == 'read']
    unread = [r for r in rows if r['status'] == '']
    odd = [r for r in rows if r['status'] not in STATUS_VALUES]
    pending = [r for r in rows if r['status'] not in ('findings written', 'rowed')]
    print(f'status: {len(rows)} units; {len(done)} with findings written or rowed; {len(read_only)} read without findings; {len(unread)} unread'
          + (f'; {len(odd)} with a non-standard status ({", ".join(r["unit"] + ":" + r["status"] for r in odd)})' if odd else ''))
    if not pending:
        print('status: every unit has findings; nothing to resume')
        return
    first = pending[0]
    print(f'resume at unit {first["unit"]}: {first["span"]} ({first["words"]} words' + (f'; status {first["status"]}' if first['status'] else '') + ')')
    print(f'  file: {os.path.join(args.wip, "units", first["unit"] + ".txt")}')
    print('units still without findings:')
    for r in pending:
        print(f'  {r["unit"]}  {r["words"]:>6}  {r["span"]}' + (f'  [status: {r["status"]}]' if r['status'] else '') + (f'  notes: {r["notes"]}' if r['notes'] else ''))


def mark(args):
    unit, new_status = args.mark
    path, lines, rows = read_manifest(args.wip)
    if new_status not in STATUS_VALUES:
        print(f'chunk_source: status {new_status!r} is not one of {STATUS_VALUES[1:]}; recording it anyway')
    hit = None
    for r in rows:
        if r['unit'] == unit or r['unit'].lstrip('0') == unit.lstrip('0'):
            hit = r
            break
    if hit is None:
        sys.exit(f'chunk_source: unit {unit} not in manifest')
    note = hit['notes'] if args.note is None else args.note.replace('|', '/')
    lines[hit['i']] = f'| {hit["unit"]} | {hit["source"]} | {hit["span"]} | {hit["words"]} | {new_status} | {note} |'
    write_text(path, '\n'.join(lines))
    print(f'marked unit {hit["unit"]} {new_status!r}' + (f' (note: {note})' if note else ''))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*', help='source file(s), a directory of posts, or a sets.json')
    ap.add_argument('--wip', required=True, help='wip/<task> folder; units go to wip/<task>/units/')
    ap.add_argument('--words', type=int, default=2500, help='target unit size in words (default 2500)')
    ap.add_argument('--ceiling', type=int, default=None, help='hard ceiling in words (default 1.5x target)')
    ap.add_argument('--by', choices=['auto', 'page', 'post', 'heading', 'timestamp', 'words'], default='auto',
                    help='top-level boundary; auto tries page markers, then headings, timestamps, capitalised section lines, paragraphs')
    ap.add_argument('--set', default=None, help='sets.json key when the source is a post directory (e.g. A or B)')
    ap.add_argument('--verify', action='store_true', help='check that the units concatenate back to the source exactly')
    ap.add_argument('--status', action='store_true', help='list the units still without findings (resume helper)')
    ap.add_argument('--mark', nargs=2, metavar=('UNIT', 'STATUS'), help='set a unit\'s status cell in manifest.md')
    ap.add_argument('--note', default=None, help='with --mark: text for the notes cell')
    ap.add_argument('--force', action='store_true', help='rebuild over an existing units/ folder')
    ap.add_argument('--dry-run', action='store_true', help='print the plan without writing')
    args = ap.parse_args()
    if args.verify:
        sys.exit(0 if verify(args) else 2)
    if args.status:
        status(args); return
    if args.mark:
        mark(args); return
    if not args.paths:
        ap.error('give source path(s), or one of --verify, --status, --mark')
    if args.by == 'post' and not any(os.path.isdir(p) or os.path.basename(p) == 'sets.json' for p in args.paths) and args.set:
        ap.error('--set needs a post directory or a sets.json path')
    build(args)


if __name__ == '__main__':
    main()
