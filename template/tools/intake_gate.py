#!/usr/bin/env python3
"""The two script gates of the staged intake (tools/intake-staged.md, 2026-10-16).

Gate 1, after the read phase:
  python3 tools/intake_gate.py --findings --wip wip/<task> [--min-words 4] [--strict] [--mark] [--json] [--units 003-011] [--budget R]
    every unit of wip/<task>/units/manifest.md has wip/<task>/findings/NNN.md in the fixed form (tools/intake-staged.md section 3);
    its `unit:` line is the unit file's own header; status is complete; every required section is present; every quotation in
    the file (any double-quoted span of --min-words or more words, and every item of `## Quotations` whatever its length) occurs
    verbatim in that unit's text; every `[u NNN:L]` pointer names this unit and a line inside it; a quotation's pointer is within
    two lines of where the words are; a claim's pointer leads to lines that hold three content words of the claim (a warning,
    a failure with --strict). A `## Quotations` item in the compact form (2026-10-23: `[u NNN:L-M] speaker | words: <first four> ...
    <last four> | use: ...`, no text) must carry a pointer, and its anchors must occur in that order on the pointer's lines (two
    lines' slack either side; tools/ledger/quote.py, the same matching `ledger quote --words` uses); an item in the older form (the
    words in quotation marks) is checked as before.
    The size check is the item allowance (2026-10-23, the owner's ruling after wip/compact-findings/REPORT.md section 4): the
    findings file's words are at most 200 + 35 per Claims item + 30 per Questions item + 20 per Quotations item + 25 per item of
    every other section (Dated events, Names, Documents and works cited, the objects heading, the actors heading, Relations,
    Tensions, Open threads, Blocked). An item is a `- ` line of its section other than `- none ...`. A unit over its allowance
    fails gate 1 unless its head carries a valid exception line in the checkable form
      size: over budget: <section>: <n> items over <cap> words: <reason>
    valid when the section is one of the file's item sections (its heading, or a prefix of it naming one), <cap> is at least that
    section's per-item allowance, at least <n> of its items run over <cap> words, the reason is not density ("dense" is never a
    reason: the allowance grows with the items), and the file is within the allowance once that section's excess (its items'
    words less its items times its per-item allowance) is excused. An exception that names no section, a wrong section (one
    whose excess does not explain the overrun) or a reason only is invalid, and the unit fails.
    --budget R replaces the allowance with the older ratio check (findings words against R times the unit's words), for
    archived findings only: a unit over it is a warning, a failure with --strict, and any `size: over budget: <reason>` line
    is honoured, as before 2026-10-23. Off by default.
    Exit 1 when any unit fails, naming the units (the workflow resumes the reader on those units).
    --mark sets `findings written` in the manifest for every unit that passes. --units limits the check to a range (a fanout reader).
  python3 tools/intake_gate.py --findings --wip wip/<task> --status
    the units still without a passing findings file (the resume point), nothing else.
  python3 tools/intake_gate.py --findings --wip wip/<task> --size [--units 003-011] [--budget R]
    the size check alone, one line per unit (findings words, the allowance and how it is made, the items per section, the unit's
    words and the ratio, and the state: within, over with a valid exception, over without one, over with an invalid one); exit 1
    when a unit is over with no valid exception line (the reader's check before it marks a unit done).
  python3 tools/intake_gate.py --findings --wip <archived run> --legacy-findings <parts/findings.md>
    the dry-run form: an old single findings file headed `## NNN` is split by unit and the quotation and coverage checks applied
    (the section checks do not apply to the old form and are reported as skipped).

Gate 2, after the write phase and again after the finish phase:
  python3 tools/intake_gate.py --note books/<note>.md --wip wip/<task> [--min-words 5] [--json] [--para-cites] [--strict]
    every quotation in the note (double-quoted spans of --min-words or more words, outside `[BLOCKED:` rows) occurs verbatim in
    some unit of the source (in the sections that quote other notes, Cross-checks and the like, a miss is a warning, not a
    failure); every unit is cited at least once in the note (a `[u NNN` marker; a code of the note's inventory table whose post
    or document the unit holds; an h:mm:ss inside a transcript unit's span; a page inside a page span) or is named in the note's
    line `Units with nothing to row: NNN (reason); ...` wherever it stands in the note (writer A puts it directly above the
    `## Claims ledger` heading; a list dash or bold markers around the label are allowed; a reason may hold `;` or brackets); every claims-ledger row that carries a unit line (`[u NNN:L]` or
    `[u NNN:L-M]` in any cell) points at lines that hold three content words of its Claim cell (fuzzy: word stems of four
    letters or more). Exit 1 on any failure, listing the rows and units. --para-cites also resolves the legacy citation forms
    `<code> para. <k>` and `<code> § <heading>` through the inventory table to source lines (the dry run on a document note).

  python3 tools/intake_gate.py --note books/<note>.md --wip wip/<task> --quotes-only [--json]
    the quotation check alone (2026-10-24, the forms measurement: a single-agent note's rows carry no pointer and no unit marker, so
    the coverage and claim-line checks do not apply): every quotation of the note verbatim in some unit, as above; the report says
    the other two checks were not run. The single-agent workflow (tools/workflows/guarded-intake.js) runs it after the agent's reply
    and resumes the agent with the report on failure (2026-10-25).

Gate 2, parts mode, after each unit writer (the unit-writers form, 2026-10-24; wip/intake-staged/phases/write-unit.md):
  python3 tools/intake_gate.py --note-parts wip/<task>/parts --wip wip/<task> --units A-B [--nothing-to-row <json>] [--start-row N]
                               [--start-audit M] [--min-words 5] [--json]
    the parts u<NNN>-ledger.md (claims rows) and u<NNN>-audit.md (audit rows) of every unit of the manifest inside A-B, table rows
    only, checked as gate 2 checks a note: every quotation (a double-quoted span of --min-words or more words) verbatim in the unit
    its row's pointer names (the part's own unit when the row has none); every claims row ends its Note cell with a pointer
    `[u NNN:L]` or `[u NNN:L-M]` (several when a row joins fragments) whose lines hold three content words of the Claim cell; every
    audit row carries a pointer whose lines hold content words of its question and answer (none at all is a failure, fewer than
    three a warning); the rows numbered on without gaps or repeats across the range in unit order (from --start-row and
    --start-audit when given; a decimal row such as 48.1 stands between its neighbours); every unit of the range cited by a row's
    pointer or named in the nothing-to-row list. --nothing-to-row takes the unit writer's reply field: a JSON list of
    {"unit": "NNN", "reason": "..."} (or {"NNN": "reason"}, or `@file` holding either). A heading, prose line or table header in a
    part, a row of other than eight cells, or a missing ledger part for a unit not in the list fails; other ranges' parts are not read. The JSON line carries rows, audit_rows, last_row
    and last_audit_row (the next writer starts at last + 1) and failing_units. Report wip/<task>/gate-parts-A-B.md.

Both gates write a full report (wip/<task>/gate-findings.md, wip/<task>/gate-note.md; `--out <dir>` elsewhere) and print a summary; --json prints one
JSON object instead (the workflow's probe agent relays it). Matching normalises whitespace, curly quotes, dashes and case,
drops bracketed insertions `[sic]`, `[the DIA]`, and lets an ellipsis split a quotation into segments that must appear in
order within 600 characters. The gates read; they never edit a note or a findings file.

The caption rule (owner 2026-10-25, wip/quote-tool-adoption/), in gate 2 (--note, --quotes-only, --note-parts): a quotation the
match above does not find is matched again by word keys (tools/ledger/quote.py: lower case, apostrophes and the punctuation
between words not counted, a number's digit-group commas dropped, the source's bracketed words tried kept and dropped, a
caption's timestamp never a word), in the same segments and order. Keys identical in order: `punctuation only`, forgiven (a
quotation from an unpunctuated caption may add punctuation and capitals), listed apart under `## Punctuation only` and counted
as quote_punct, never a failure. Otherwise `changed words` (a word changed, added or dropped): a failure, counted as quote_fails,
with the nearest window's difference. The JSON line also carries quote_exact; the summary reads `N quotations (E exact, P
punctuation only (forgiven), F changed words, W warnings)`. Gate 1 is unchanged.
"""
import sys, os, re, json, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import quote as LQ    # pointers and anchors of the compact findings form (tools/ledger/quote.py, 2026-10-23)

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)

import packload   # the findings headings for objects and actors are the pack's (phase 4 handoff 2; core defaults "object watch", "Actors and polities")
REQUIRED_SECTIONS = ["Summary", "Dated events", "Claims", "Quotations", "Questions, declines, walls and stated limits", "Names",
                     "Documents and works cited", f"Objects ({packload.objects()['watch_name']})", packload.actors_findings_heading(), "Relations"]
OPTIONAL_SECTIONS = ["Tensions inside the source", "Open threads the unit raises", "Nothing to row", "Blocked"]
WARN_SECTIONS_NOTE = ["Cross-checks", "What this settles, and what it does not", "What this contests", "What it concedes", "Echo watch",
                      "Who hosts, who relays", "Open questions", "Tracker candidates", "Divergences, read four ways",
                      "What the ledger holds that the post does not use", "Verification of every citation"]
STOP = set("""a an the and or but of to in on at by for with from as is are was were be been being this that these those it its
he she they them his her their we our you your i me my not no nor so if then than there here which who whom whose what when where
why how all any each every some such only own same other another more most much many few less least very just also about into
over under between among through during before after above below up down out off again further once said says say told tells
one two three four five six seven eight nine ten first second third new old had has have having do does did done will would
shall should can could may might must per via etc""".split())
STRIP_NUM = re.compile(r"\d")


def norm(t, brackets=True):
    """whitespace, curly quotes, dashes, case; every quote mark becomes an apostrophe (inner quoting style is not a copying error);
    inline URL tokens `[http...]` (the held captures' form) are dropped; a bracketed insertion of one or two characters (`[M]y`)
    keeps its content and a longer one (`[Carpenter]`, `[sic]`) is dropped, on the quotation and on the source alike"""
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    t = t.replace("…", "...").replace(" ", " ").replace('"', "'")
    t = re.sub(r"\[https?://[^\]\s]+\]", " ", t)
    if brackets:
        t = re.sub(r"\[([^\]]{1,2})\]", r"\1", t)
        t = re.sub(r"\[[^\]]{3,60}\]", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return t.strip().lower()


def quote_segments(q):
    """a quotation's text split at ellipses and at bracketed insertions into segments to match in order"""
    q = norm(q, brackets=False)
    q = re.sub(r"\[([^\]]{1,2})\]", r"\1", q)
    segs = [s.strip(" ,;:.!?'") for s in re.split(r"\s*(?:\.\.\.|…|\[[^\]]{3,60}\])\s*", q)]
    return [s for s in segs if s and re.search(r"\w", s)]


def find_quote(segs, text, window=600):
    """position of the quotation in normalised text, or -1; segments must appear in order within window chars of each other"""
    if not segs: return -1
    start = 0
    while True:
        p = text.find(segs[0], start)
        if p < 0: return -1
        pos = p + len(segs[0]); ok = True
        for s in segs[1:]:
            q = text.find(s, pos)
            if q < 0 or q - pos > window: ok = False; break
            pos = q + len(s)
        if ok: return p
        start = p + 1


def content_words(t):
    out = []
    for w in re.findall(r"[a-z][a-z'\-]+", norm(t)):
        w = w.strip("'-")
        if len(w) >= 4 and w not in STOP: out.append(w[:5])
    return out


def fuzzy_hit(claim, window_text, need=3):
    cw = content_words(claim)
    if not cw: return True, 0, 0
    need = min(need, len(set(cw)))
    ww = set(content_words(window_text))
    hits = len(set(cw) & ww)
    return hits >= need, hits, need


def best_line(segs, lines):
    """the line whose content words overlap the quotation most (for the report, when a quotation is not found)"""
    if not segs: return None
    cw = set(content_words(" ".join(segs)))
    best, score = None, 0
    for i, l in enumerate(lines, 1):
        s = len(cw & set(content_words(l)))
        if s > score: best, score = i, s
    return best


def word_match(q, unit):
    """the caption rule (owner 2026-10-25): the quotation's word keys occur in the unit in order (ellipses and bracketed
    insertions cut it into segments, as for the exact match); punctuation, capitals, curly quotes and dashes do not count"""
    if unit is None: return False
    segs = LQ.phrase_segments(q)
    return any(LQ.match_segments(unit[k], segs, idx=unit[i]) is not None for k, i in (("keys", "kidx"), ("keys_kept", "kidx_kept")))


def quote_tier(q, segs, units):
    """'exact' (verbatim under norm), 'punctuation only' (the same words in order: forgiven) or 'changed words' (a word changed,
    added or dropped: a failure), against the units given"""
    if any(u and find_quote(segs, u["text"]) >= 0 for u in units): return "exact"
    if any(word_match(q, u) for u in units): return "punctuation only"
    return "changed words"


def nearest_words(q, units):
    """`; nearest: unit NNN line L: <the word differences>` for a changed-words failure, or '' when no window holds most of its words"""
    segs = LQ.phrase_segments(q)
    units = [u for u in units if u]
    qk = [k for seg in segs for k in seg]
    if len(segs) > 1:
        # a quotation cut by an ellipsis: the first part not found word for word is the one to correct
        bad = next((seg for seg in segs if not any(LQ.match_segments(u[k], [seg], idx=u[i]) for u in units for k, i in (("keys", "kidx"), ("keys_kept", "kidx_kept")))), None)
        if bad is None: return f"; nearest: every part is in the units word for word, but not in this order within {LQ.GAP} words of each other"
        qk = bad
    nm = LQ.near_miss([(u["n"], u["keys"]) for u in units], qk)
    if not nm: return ""
    u = next(x for x in units if x and x["n"] == nm["unit"])
    la, lb = u["keys"][nm["first"]][1], u["keys"][nm["last"]][1]
    return f"; nearest: [u {nm['unit']}:{la}{'-' + str(lb) if lb != la else ''}]: {LQ.describe_ops(nm['ops']) or 'the words are there, cut differently'}"


# ---------------------------------------------------------------- units and manifest

HDR = re.compile(r"^\[unit (\d{3})/(\d{3})(?: continues)?\] source: (.+?) \| span: (.+?) \| words: ([\d,]+)\s*$")


def load_manifest(wip):
    mp = os.path.join(wip, "units", "manifest.md")
    if not os.path.exists(mp): sys.exit(f"no manifest at {mp}")
    units = {}
    for line in LN.iter_lines(mp):
        m = re.match(r"^\|\s*(\d{3})\s*\|(.*)\|\s*$", line)
        if not m: continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 4: continue
        units[m.group(1)] = {"source": cells[0], "span": cells[1], "words": cells[2], "status": cells[3], "notes": cells[4] if len(cells) > 4 else ""}
    return units


def load_unit(wip, n):
    p = os.path.join(wip, "units", f"{n}.txt")
    if not os.path.exists(p): return None
    raw = LN.read_text(p, errors="replace")
    lines = raw.split("\n")
    if lines and lines[-1] == "": lines = lines[:-1]
    headers = []   # (unit line index 1-based, source file, a, b, span)
    for i, l in enumerate(lines, 1):
        m = HDR.match(l)
        if m:
            sp = m.group(4); mm = re.search(r"lines (\d+)-(\d+)", sp)
            headers.append((i, m.group(3), int(mm.group(1)) if mm else None, int(mm.group(2)) if mm else None, sp))
    # a blockquote's `> ` markers are the source's layout, not its words: a quotation that runs across the lines of a quoted block
    # (a video description held as `> ` lines, which note_skeleton joins into the Description candidate) matches without them
    body_lines = [("" if HDR.match(l) else re.sub(r"^\s*>(?:\s|$)", "", l)) for l in lines]
    # the normalised text is the normalised lines joined by one space, with each line's start offset kept, so a match
    # position maps back to a unit line and a quotation may run across a line break
    line_norm = [norm(l) for l in body_lines]
    offsets = []; pos = 0; parts = []
    for ln in line_norm:
        offsets.append(pos)
        if ln: parts.append(ln); pos += len(ln) + 1      # an empty line adds nothing, so a quotation runs across a paragraph break
    keys, keys_kept = LQ.unit_keys(lines), LQ.unit_keys(lines, keep_brackets=True)   # the caption rule's word keys (tools/ledger/quote.py, 2026-10-25)
    return {"n": n, "path": p, "lines": lines, "body_lines": body_lines, "header": lines[0] if lines else "", "headers": headers,
            "text": " ".join(parts), "offsets": offsets, "nlines": len(lines), "keys": keys, "kidx": LQ._index(keys),
            "keys_kept": keys_kept, "kidx_kept": LQ._index(keys_kept)}


def line_at(unit, pos):
    """the 1-based unit line holding a position of unit['text']"""
    import bisect
    return bisect.bisect_right(unit["offsets"], pos)


def unit_line_of_source(unit, src_file, src_line):
    """unit line for a source (file, line), through the unit's header lines; None when the unit does not hold it"""
    for (pos, f, a, b, _) in unit["headers"]:
        if a is None: continue
        if (f == src_file or f.endswith("/" + src_file) or src_file.endswith("/" + f)) and a <= src_line <= b:
            return pos + (src_line - a) + 1
    return None


# ---------------------------------------------------------------- gate 1: findings

PTR = LN.UNIT_PTR_RE   # form U1
DQ = re.compile(r'(?<![\w])"(\S(?:[^"\n]*?\S)?)"(?![\w])')


def quotes_in(line):
    """double-quoted spans of a line, cell by cell for table rows"""
    out = []
    for cell in (line.split("|") if line.lstrip().startswith("|") else [line]):
        for m in DQ.finditer(cell): out.append(m.group(1))
    return out


def parse_findings(path):
    raw = LN.read_text(path, errors="replace")
    lines = raw.split("\n")
    head = {}; head_lines = set()
    for i, l in enumerate(lines[:8], 1):
        m = re.match(r"^(unit|status|reader|size):\s*(.*)$", l)
        if m: head[m.group(1)] = m.group(2).strip(); head_lines.add(i)
    sections = {}; cur = None
    for i, l in enumerate(lines, 1):
        m = re.match(r"^##\s+(.+?)\s*$", l)
        if m: cur = m.group(1); sections.setdefault(cur, []); continue
        if cur is not None: sections[cur].append((i, l))
    return {"raw": raw, "lines": lines, "head": head, "head_lines": head_lines, "sections": sections}


def split_legacy(path):
    """an old parts/findings.md headed `## NNN (...)`: unit -> pseudo findings file text"""
    out = {}; cur = None
    for l in LN.read_lines(path, errors="replace"):
        m = re.match(r"^##\s+(\d{3})\b", l)
        if m: cur = m.group(1); out[cur] = []; continue
        if cur: out[cur].append(l)
    return {k: "\n".join(v) for k, v in out.items()}


def check_findings_unit(n, unit, fd, legacy, min_words, strict):
    """returns (fails, warns, counts) for one unit"""
    fails, warns = [], []
    counts = {}
    if unit is None:
        fails.append(f"unit file units/{n}.txt missing"); return fails, warns, counts
    if not legacy:
        if fd["head"].get("unit", "") != unit["header"]:
            fails.append(f"`unit:` line is not the unit file's header (findings: {fd['head'].get('unit', '')[:80]!r}; unit: {unit['header'][:80]!r})")
        st = fd["head"].get("status", "")
        if not st.startswith("complete"): fails.append(f"status is {st!r}, not complete")
        for s in REQUIRED_SECTIONS:
            if s not in fd["sections"]: fails.append(f"section missing: ## {s}")
        for s in fd["sections"]:
            if s not in REQUIRED_SECTIONS and s not in OPTIONAL_SECTIONS: warns.append(f"section not in the form: ## {s}")
        for s in REQUIRED_SECTIONS:
            items = [l for (_, l) in fd["sections"].get(s, []) if l.startswith("- ")]
            counts[s] = len(items)
        has_claims = counts.get("Claims", 0) > 0
        nothing = "Nothing to row" in fd["sections"] and any(l.strip() for (_, l) in fd["sections"]["Nothing to row"])
        if not has_claims and not nothing: fails.append("no claims and no `## Nothing to row` reason")
    # pointers
    for m in PTR.finditer(fd["raw"]):
        u, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        if u != n: fails.append(f"pointer {m.group(0)} names another unit")
        elif not (2 <= a <= unit["nlines"]) or b < a or b > unit["nlines"]: fails.append(f"pointer {m.group(0)} outside the unit (lines 2 to {unit['nlines']})")
    # quotations: every double-quoted span of min_words+ anywhere; every Quotations item whatever its length
    checked = set()
    def check_q(qtext, line_no, ptr, where, always):
        key = (norm(qtext), where)
        if key in checked: return
        checked.add(key)
        segs = quote_segments(qtext)
        words = sum(len(s.split()) for s in segs)
        if not always and words < min_words: return
        counts["quotations checked"] = counts.get("quotations checked", 0) + 1
        pos = find_quote(segs, unit["text"])
        if pos < 0:
            bl = best_line(segs, unit["body_lines"])
            fails.append(f"line {line_no} ({where}): not verbatim in unit {n}: \"{qtext[:90]}{'...' if len(qtext) > 90 else ''}\"" + (f"; nearest line {bl}: {unit['body_lines'][bl - 1][:120]!r}" if bl else ""))
            return
        if ptr:
            a, b = ptr
            found_line = line_at(unit, pos)
            if not (a - 2 <= found_line <= b + 2):
                fails.append(f"line {line_no} ({where}): quotation pointer [u {n}:{a}{'-' + str(b) if b != a else ''}] but the words are at unit line {found_line}")
    # compact Quotations items (2026-10-23): pointer and anchors, no text; located on the pointer's lines
    if not legacy:
        for (i, l) in fd["sections"].get("Quotations", []):
            if not l.startswith("- "): continue
            anc = LQ.words_field(l)
            if anc is None: continue
            counts["quotations checked"] = counts.get("quotations checked", 0) + 1
            pm = PTR.search(l)
            if not pm: fails.append(f"line {i} (Quotations): a `words:` item without its [u {n}:L-M] pointer"); continue
            a, b = int(pm.group(2)), int(pm.group(3) or pm.group(2))
            if pm.group(1) != n or not (2 <= a <= unit["nlines"]) or b < a or b > unit["nlines"]: continue   # failed above
            first, last = LQ.split_anchors(anc)
            if not first: fails.append(f"line {i} (Quotations): `words:` is empty"); continue
            if LQ.locate(unit["lines"], a, b, anc) is None:
                fails.append(f"line {i} (Quotations): the words {anc[:90]!r} are not on lines {max(2, a - LQ.SLACK)} to {min(unit['nlines'], b + LQ.SLACK)} of unit {n} in that order (first {' '.join(first)!r}" + (f", last {' '.join(last)!r})" if last else ")"))
    for i, l in enumerate(fd["lines"], 1):
        # the head lines (`unit:`, `status:`, `reader:`) are not quotations: `unit:` is a copy of the unit's header, compared with it
        # above, and a header's span may carry `under "<heading>"` for a heading that opened in an earlier unit (2026-10-22)
        if i in fd.get("head_lines", ()): continue
        sec = None
        for s, items in fd["sections"].items():
            if any(li == i for (li, _) in items): sec = s; break
        if sec == "Quotations" and LQ.words_field(l) is not None: continue   # a compact item: its anchors are located above
        pm = PTR.search(l); ptr = (int(pm.group(2)), int(pm.group(3) or pm.group(2))) if pm else None
        for q in quotes_in(l):
            check_q(q, i, ptr, sec or "head", always=(sec == "Quotations"))
    # claims pointers: fuzzy
    for (i, l) in fd["sections"].get("Claims", []):
        if not l.startswith("- "): continue
        pm = PTR.search(l)
        if not pm: warns.append(f"line {i} (Claims): no [u {n}:L] pointer"); continue
        a, b = int(pm.group(2)), int(pm.group(3) or pm.group(2))
        cm = re.search(r"claim:\s*(.+?)(?:\s*\|\s*(?:attribution|attr|chain|loc|note|class|move|topic):|$)", l)
        claim = cm.group(1) if cm else l[pm.end():]
        if not (2 <= a <= unit["nlines"]): continue
        window = "\n".join(unit["body_lines"][max(0, a - 2):min(unit["nlines"], b + 1)])
        ok, hits, need = fuzzy_hit(claim, window)
        if not ok:
            msg = f"line {i} (Claims): pointer [u {n}:{a}{'-' + str(b) if b != a else ''}] leads to lines holding {hits} of {need} content words of the claim: \"{claim[:80]}\""
            (fails if strict else warns).append(msg)
    return fails, warns, counts


# the item allowance (2026-10-23): words per item by section; every other item section 25; the head and summary 200
ALLOW_HEAD = 200
ALLOW_RATE = {"Claims": 35, "Questions, declines, walls and stated limits": 30, "Quotations": 20}
ALLOW_OTHER = 25
ALLOW_SECTIONS = REQUIRED_SECTIONS[1:] + ["Tensions inside the source", "Open threads the unit raises", "Blocked"]   # not Summary, not Nothing to row
EXC_RE = re.compile(r"^over budget:\s*(?P<sec>.+?)\s*:\s*(?P<n>\d+)\s+items?\s+over\s+(?P<cap>\d+)\s+words?\s*:\s*(?P<reason>.*)$", re.I)
DENSE_RE = re.compile(r"\bdens(?:e|er|ely|ity)\b", re.I)


def rate_of(section):
    return ALLOW_RATE.get(section, ALLOW_OTHER)


def items_of(fd, section):
    """the items of a section: its `- ` lines other than `- none ...` (the empty section's line, with or without the nearest objects)"""
    return [(i, l) for (i, l) in fd["sections"].get(section, []) if l.startswith("- ") and not re.match(r"^-\s+none\b", l, re.I)]


def item_words(line):
    return len(line.split()) - 1   # the words of the item, the list dash not counted


def allowance_of(fd):
    """(allowance, {section: items}) for a findings file"""
    items = {s: len(items_of(fd, s)) for s in ALLOW_SECTIONS if s in fd["sections"]}
    return ALLOW_HEAD + sum(rate_of(s) * k for s, k in items.items()), items


def check_exception(fd, exc, fw, allowance):
    """(valid, why) for the head's `size:` line against a unit over its allowance; why names what makes it invalid, or what it excuses"""
    if not exc: return False, "no exception line"
    m = EXC_RE.match(exc.strip())
    if not m: return False, "the exception line is not in the form `size: over budget: <section>: <n> items over <cap> words: <reason>`"
    name, n, cap, reason = m.group("sec").strip().strip("#").strip(), int(m.group("n")), int(m.group("cap")), m.group("reason").strip()
    present = [s for s in ALLOW_SECTIONS if s in fd["sections"]]
    sec = next((s for s in present if s.lower() == name.lower()), None)
    if sec is None:
        pre = [s for s in present if s.lower().startswith(name.lower())]
        sec = pre[0] if len(pre) == 1 else None
    if sec is None: return False, f"the exception names {name!r}, which is not an item section of this file"
    if not reason: return False, "the exception gives no reason"
    if DENSE_RE.search(reason): return False, f"the reason {reason!r} is density, which is never a reason (the allowance grows with the items)"
    rate = rate_of(sec)
    if cap < rate: return False, f"the cap {cap} is under {sec}'s per-item allowance of {rate} words"
    its = items_of(fd, sec)
    over_cap = sum(1 for (_, l) in its if item_words(l) > cap)
    if over_cap < n: return False, f"{over_cap} of {sec}'s {len(its)} items run over {cap} words, not {n}"
    excess = max(0, sum(item_words(l) for (_, l) in its) - rate * len(its))
    if fw - excess > allowance:
        return False, f"{sec}'s excess of {excess} words does not explain the overrun of {fw - allowance} (wrong section: another section is over)"
    return True, f"{sec}: {over_cap} items over {cap} words, excess {excess} excused"


def size_of(n, unit_meta, unit, fd, budget=None):
    """the size check of one findings file: a dict of findings words, unit words, ratio, allowance, items per section, over, the
    exception line, whether it is valid and why. budget None: the item allowance; a number: the older ratio (archived findings)"""
    try: uw = int(str(unit_meta.get("words", "")).replace(",", ""))
    except ValueError: uw = 0
    if not uw and unit: uw = sum(len(l.split()) for l in unit["body_lines"])
    fw = len(fd["raw"].split()) if fd else 0
    ratio = fw / uw if uw else 0.0
    exc = (fd or {}).get("head", {}).get("size", "")
    allowance, items = allowance_of(fd) if fd else (ALLOW_HEAD, {})
    out = {"findings words": fw, "unit words": uw, "ratio": ratio, "allowance": allowance, "items": items, "exception": exc}
    if budget is not None:
        out["over"] = ratio > budget
        out["valid"], out["why"] = (bool(exc), "the ratio mode honours any exception line") if out["over"] else (True, "")
        return out
    out["over"] = fw > allowance
    out["valid"], out["why"] = check_exception(fd, exc, fw, allowance) if out["over"] else (True, "")
    return out


def size_state(c, budget=None):
    if not c["over"]: return "within"
    by = f"over by {c['findings words'] - c['allowance']:,}" if budget is None else f"over the ratio {budget:.2f}"
    if not c["exception"]: return f"{by} (no exception line)"
    return f"{by}, exception {'valid' if c['valid'] else 'INVALID'}: {c['why']}"


def gate_findings(wip, legacy=None, min_words=4, strict=False, mark=False, rng=None, as_json=False, status_only=False, out_dir=None,
                  budget=None, size_only=False):
    units = load_manifest(wip)
    keys = sorted(units)
    if rng:
        a, b = rng
        keys = [k for k in keys if a <= int(k) <= b]
    fdir = os.path.join(wip, "findings")
    legacy_map = split_legacy(legacy) if legacy else None
    per = {}
    for n in keys:
        unit = load_unit(wip, n)
        if legacy_map is not None:
            if n not in legacy_map: per[n] = {"fails": [f"no `## {n}` block in {legacy}"], "warns": [], "counts": {}}; continue
            txt = legacy_map[n]
            fd = {"raw": txt, "lines": txt.split("\n"), "head": {}, "sections": {"legacy": [(i, l) for i, l in enumerate(txt.split("\n"), 1)]}}
            fails, warns, counts = check_findings_unit(n, unit, fd, True, min_words, strict)
        else:
            fp = os.path.join(fdir, f"{n}.md")
            if not os.path.exists(fp): per[n] = {"fails": [f"findings/{n}.md missing"], "warns": [], "counts": {}}; continue
            fd = parse_findings(fp)
            if size_only: fails, warns, counts = [], [], {}
            else: fails, warns, counts = check_findings_unit(n, unit, fd, False, min_words, strict)
            sz = size_of(n, units[n], unit, fd, budget)
            counts.update({"findings words": sz["findings words"], "unit words": sz["unit words"], "ratio": sz["ratio"], "allowance": sz["allowance"],
                           "items": sz["items"], "size over": sz["over"] and not sz["valid"], "size state": size_state(sz, budget)})
            if sz["over"] and sz["exception"] and sz["valid"]: counts["size exception"] = sz["exception"]
            if budget is not None:
                if sz["over"] and not sz["exception"]:
                    msg = f"size: findings {sz['findings words']:,} words against the unit's {sz['unit words']:,} ({sz['ratio']:.2f}), over the budget of {budget:.2f}; cut items to pointers and key words, or record the exception line `size: over budget: <reason>` in the head"
                    (fails if strict else warns).append(msg)
            elif sz["over"] and not sz["valid"]:
                fails.append(f"size: findings {sz['findings words']:,} words over the item allowance of {sz['allowance']:,} (" + ", ".join(f"{s} {k}" for s, k in sz["items"].items() if k) +
                             f"); {sz['why']}. Cut fields to the form (key words, no sentences, nothing repeated from the item above), never an item; or, for a section whose items cannot be cut and stay exact, the head line `size: over budget: <section>: <n> items over <cap> words: <reason>`")
        per[n] = {"fails": fails, "warns": warns, "counts": counts}
    failing = [n for n in keys if per[n]["fails"]]
    if size_only:
        over = []
        for n in keys:
            c = per[n]["counts"]
            if "ratio" not in c: print(f"{n}: {'; '.join(per[n]['fails'])}"); over.append(n); continue
            if c["size over"]: over.append(n)
            made = f"{ALLOW_HEAD} + " + " + ".join(f"{s.split(' (')[0].split(',')[0]} {k}x{rate_of(s)}" for s, k in c["items"].items() if k)
            its = ", ".join(f"{s.split(' (')[0].split(',')[0]} {k}" for s, k in c["items"].items())
            lim = f"allowance {c['allowance']:,} ({made})" if budget is None else f"budget {budget:.2f} of the unit = {int(budget * c['unit words']):,}"
            print(f"{n}: findings {c['findings words']:,} words; {lim}; items: {its}; unit {c['unit words']:,} words ({c['ratio']:.2f}): {c['size state']}")
        tf = sum(per[n]["counts"].get("findings words", 0) for n in keys); tu = sum(per[n]["counts"].get("unit words", 0) for n in keys)
        ta = sum(per[n]["counts"].get("allowance", 0) for n in keys)
        print(f"all: findings {tf:,} words; " + (f"allowance {ta:,}" if budget is None else f"budget {budget:.2f}") + f"; units {tu:,} words ({tf / tu if tu else 0:.2f}); {len(over)} unit(s) over without a valid exception: {', '.join(over) or 'none'}")
        return 1 if over else 0
    if status_only:
        print(f"{len(failing)} of {len(keys)} unit(s) without a passing findings file: {', '.join(failing) or 'none'}")
        if failing: print(f"resume at unit {failing[0]}: {os.path.join(wip, 'units', failing[0] + '.txt')}")
        return 1 if failing else 0
    # report
    rep = [f"# Gate 1 (findings): {wip}", "", f"- units checked: {len(keys)} ({keys[0]} to {keys[-1]})" if keys else "- no units",
           f"- form: {'legacy single file ' + legacy + ' (section checks skipped)' if legacy else 'findings/NNN.md (tools/intake-staged.md section 3)'}",
           f"- quotation threshold: {min_words} words (Quotations items: any length; compact items located by their anchors); claim pointers: {'failures' if strict else 'warnings'}; size: " + (f"the item allowance ({ALLOW_HEAD} + claims {ALLOW_RATE['Claims']}, questions {ALLOW_RATE['Questions, declines, walls and stated limits']}, quotations {ALLOW_RATE['Quotations']}, other items {ALLOW_OTHER} words each), over it without a valid exception line a failure" if budget is None else f"the ratio {budget:.2f} of the unit's words ({'failures' if strict else 'warnings'})"),
           f"- failing units: {len(failing)}: {', '.join(failing) or 'none'}", ""]
    tot_fail = sum(len(per[n]["fails"]) for n in keys); tot_warn = sum(len(per[n]["warns"]) for n in keys)
    tot_q = sum(per[n]["counts"].get("quotations checked", 0) for n in keys)
    rep.append(f"- quotations checked: {tot_q}; failures: {tot_fail}; warnings: {tot_warn}")
    tf = sum(per[n]["counts"].get("findings words", 0) for n in keys); tu = sum(per[n]["counts"].get("unit words", 0) for n in keys)
    size_over = [n for n in keys if per[n]["counts"].get("size over")]
    ta = sum(per[n]["counts"].get("allowance", 0) for n in keys)
    rep.append(f"- size: findings {tf:,} words against the units' {tu:,} ({tf / tu if tu else 0:.2f})" + (f" and the allowance {ta:,}" if budget is None else "") + f"; over without a valid exception: {', '.join(size_over) or 'none'}")
    if not legacy:
        rep.append("")
        rep.append("| unit | " + " | ".join(REQUIRED_SECTIONS[1:]) + " | quotations checked | findings words | allowance | ratio | size | fails | warns |")
        rep.append("|---|" + "---|" * (len(REQUIRED_SECTIONS) - 1) + "---|---|---|---|---|---|---|")
        for n in keys:
            c = per[n]["counts"]
            ratio = f"{c['ratio']:.2f}" if "ratio" in c else ""
            rep.append(f"| {n} | " + " | ".join(str(c.get(s, "")) for s in REQUIRED_SECTIONS[1:]) + f" | {c.get('quotations checked', '')} | {c.get('findings words', '')} | {c.get('allowance', '')} | {ratio} | {c.get('size state', '')} | {len(per[n]['fails'])} | {len(per[n]['warns'])} |")
    for n in keys:
        if per[n]["fails"] or per[n]["warns"]:
            rep.append(f"\n## unit {n}: {'FAIL' if per[n]['fails'] else 'pass with warnings'}")
            for f in per[n]["fails"]: rep.append(f"- FAIL: {f}")
            for w in per[n]["warns"]: rep.append(f"- warn: {w}")
    out = os.path.join(out_dir or wip, "gate-findings.md")
    LN.write_text(out, "\n".join(rep) + "\n")
    marked = []
    if mark and not legacy:
        for n in keys:
            if per[n]["fails"]: continue
            if units[n]["status"] in ("", "read"):
                r = subprocess.run([sys.executable, os.path.join(_T, "chunk_source.py"), "--wip", wip, "--mark", n, "findings written"], capture_output=True, text=True)
                if r.returncode == 0: marked.append(n)
    summary = {"gate": "findings", "ok": not failing, "units": len(keys), "failing_units": failing, "fails": tot_fail, "warns": tot_warn,
               "quotations_checked": tot_q, "report": out, "marked": marked, "findings_words": tf, "unit_words": tu, "size_over": size_over,
               "summary": f"{len(keys) - len(failing)} of {len(keys)} units pass; {tot_fail} failure(s), {tot_warn} warning(s); report {out}"}
    if as_json: print(json.dumps(summary))
    else:
        print(summary["summary"])
        for n in failing: print(f"  {n}: " + "; ".join(x[:140] for x in per[n]["fails"][:4]) + (f"; and {len(per[n]['fails']) - 4} more" if len(per[n]["fails"]) > 4 else ""))
        if marked: print(f"marked findings written: {', '.join(marked)}")
    return 0 if not failing else 1


# ---------------------------------------------------------------- gate 2: note

def note_sections(lines):
    """line index -> section title (## headings) (form S6 of the parser library)"""
    return LN.line_sections(lines)


def inventory_codes(lines):
    """code -> (title, date) from the note's inventory table (| Code | Section (held text) | ...)"""
    codes = {}
    for l in lines:
        m = LN.INVENTORY_CODE_RE.match(l)   # form U3
        if not m: continue
        cell = m.group(2)
        t = re.search(r'"(.+?)"', cell); d = re.search(r"\((\d{4}-\d{2}-\d{2})\)", cell)
        codes[m.group(1)] = (norm(t.group(1)) if t else norm(cell), d.group(1) if d else None)
    return codes


def units_of_code(code, codes, units_meta):
    """units whose span names the code's post title (or date)"""
    if code not in codes: return []
    title, date = codes[code]
    out = []
    for n, u in units_meta.items():
        sp = norm(u["span"])
        if title and norm(f'post "{title}"') in sp: out.append(n)
        elif date and f"({date})" in sp and not title: out.append(n)
    return sorted(set(out))


def paragraphs_of_source(path):
    """[(k, first_line, last_line)] of body paragraphs: blank-separated blocks after the header block, image-only blocks skipped"""
    lines = LN.read_lines(path, errors="replace")
    blocks = []; cur = None
    for i, l in enumerate(lines, 1):
        if l.strip():
            if cur is None: cur = [i, i]
            else: cur[1] = i
        else:
            if cur: blocks.append(tuple(cur)); cur = None
    if cur: blocks.append(tuple(cur))
    body = []
    for (a, b) in blocks:
        txt = "\n".join(lines[a - 1:b])
        if lines[a - 1].startswith("# ") or re.match(r"^(Published|URL):", lines[a - 1]): continue
        words = re.sub(r"\[https?://[^\]\s]+\]", " ", txt).split()
        if len(words) < 3: continue
        if a == b and len(words) <= 12 and not txt.rstrip().endswith((".", "!", "?", '"', "”", ":", ")")): continue   # a caption or a heading line
        body.append((a, b))
    return body, lines


NOTHING_RE = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*|__)?Units with nothing to row:?(?:\*\*|__)?:?\s*(.*)$")
NOTHING_ITEM_RE = re.compile(r"\b(\d{3})\s*\(((?:[^()]|\([^()]*\))*)\)")


def gate_note(note, wip, min_words=5, para_cites=False, strict=False, as_json=False, out_dir=None, quotes_only=False):
    units_meta = load_manifest(wip)
    loaded = {n: load_unit(wip, n) for n in units_meta}
    nl = LN.read_lines(note, errors="replace")
    sec = note_sections(nl)
    fails, warns = [], []
    # 1. quotations
    checked = 0; q_fail = 0; q_warn = 0; q_exact = 0; punct = []
    seen = set()
    own_titles = {norm(l[3:]) for l in nl if l.startswith("## ")} | {norm(l[4:]) for l in nl if l.startswith("### ")}
    units = [loaded[n] for n in loaded if loaded[n]]
    for i, l in enumerate(nl, 1):
        if "[BLOCKED:" in l: continue
        s = sec[i]
        for q in quotes_in(l):
            segs = quote_segments(q)
            if sum(len(x.split()) for x in segs) < min_words: continue
            key = norm(q)
            if key in seen or key in own_titles: continue
            seen.add(key); checked += 1
            tier = quote_tier(q, segs, units)
            if tier == "exact": q_exact += 1; continue
            if tier == "punctuation only":
                punct.append(f"line {i} ({s}): punctuation only (the same words in order; forgiven by the caption rule): \"{q[:100]}{'...' if len(q) > 100 else ''}\""); continue
            warn = any(s.startswith(w) for w in WARN_SECTIONS_NOTE) or ("quoted from:" in l)
            msg = f"line {i} ({s}): changed words (not in any unit word for word): \"{q[:100]}{'...' if len(q) > 100 else ''}\"" + nearest_words(q, units)
            if warn: warns.append(msg); q_warn += 1
            else: fails.append(msg); q_fail += 1
    qc = {"checked": checked, "exact": q_exact, "punct": punct, "fail": q_fail, "warn": q_warn}
    if quotes_only: return note_quotes_report(note, wip, units_meta, min_words, qc, fails, warns, strict, as_json, out_dir)
    # 2. unit coverage
    text_all = "\n".join(nl)
    cited = {n: set() for n in units_meta}
    for m in LN.UNIT_MARK_RE.finditer(text_all):   # form U2
        if m.group(1) in cited: cited[m.group(1)].add("marker")
    codes = inventory_codes(nl)
    code_units = {c: units_of_code(c, codes, units_meta) for c in codes}
    for c, us in code_units.items():
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(c) + r"(?![A-Za-z0-9])", text_all):
            for n in us: cited[n].add(f"code {c}")
    for n, u in units_meta.items():
        sp = u["span"]
        for tm in re.finditer(r"(\d{1,2}:\d{2}:\d{2})-(\d{1,2}:\d{2}:\d{2})", sp):
            def secs(t): h, mi, se = [int(x) for x in t.split(":")]; return h * 3600 + mi * 60 + se
            a, b = secs(tm.group(1)), secs(tm.group(2))
            for t in re.findall(r"\b(\d{1,2}:\d{2}:\d{2})\b", text_all):
                if a <= secs(t) <= b: cited[n].add("timestamp"); break
        pm = re.search(r"pages? (\d+)(?:-(\d+))?", sp)
        if pm:
            a, b = int(pm.group(1)), int(pm.group(2) or pm.group(1))
            for p in re.findall(r"\b(?:p\.|page)\s*(\d+)\b", text_all):
                if a <= int(p) <= b: cited[n].add("page"); break
    nothing = {}
    for l in nl:
        # anywhere in the note (writer A puts it directly above `## Claims ledger`); a list dash or bold markers allowed; a reason
        # may hold `;` and one level of brackets
        m = NOTHING_RE.match(l)
        if m:
            for pm in NOTHING_ITEM_RE.finditer(m.group(1)): nothing[pm.group(1)] = pm.group(2)
    uncited = [n for n in sorted(units_meta) if not cited[n] and n not in nothing]
    for n in uncited: fails.append(f"unit {n} cited nowhere in the note and not in `Units with nothing to row:` ({units_meta[n]['span'][:90]})")
    # 3. claims rows with a unit line
    rows_with, rows_without, line_fails = 0, 0, 0
    in_claims = False; legacy_cites = 0; legacy_resolved = 0
    para_cache = {}
    section_heads = {}
    for l in nl:
        for m in re.finditer(r"\|\s*([A-Z]{1,3}\d{1,3}[a-z]?)\s+§\s*([^|]+?)\s*\|", l): section_heads.setdefault(m.group(1), set()).add(m.group(2))
    for i, l in enumerate(nl, 1):
        if l.startswith("## "): in_claims = l.startswith("## Claims ledger")
        if not in_claims or not LN.CLAIMS_ROW_RE.match(l): continue   # form U4
        cells = LN.split_row(l)
        if len(cells) < 5: continue
        claim = cells[4]; time_cell = cells[1]
        pm = PTR.search(l)
        target = None  # (unit, a, b, how)
        if pm:
            n, a, b = pm.group(1), int(pm.group(2)), int(pm.group(3) or pm.group(2))
            target = (n, a, b, pm.group(0))
        elif para_cites:
            m1 = re.match(r"^([A-Z]{1,3}\d{1,3}[a-z]?)\s+para\.\s*(\d+)", time_cell)
            m2 = re.match(r"^([A-Z]{1,3}\d{1,3}[a-z]?)\s+§\s*(.+)$", time_cell)
            if m1 or m2:
                legacy_cites += 1
                code = (m1 or m2).group(1)
                us = code_units.get(code, [])
                if us:
                    # the source file of the code's post, from the first unit's headers
                    src = None
                    for (pos, f, a0, b0, sp) in loaded[us[0]]["headers"]:
                        if codes[code][0] and norm(f'post "{codes[code][0]}"') in norm(sp): src = f; break
                    if src is None: src = loaded[us[0]]["headers"][0][1]
                    spath = os.path.join(ROOT, src)
                    if spath not in para_cache and os.path.exists(spath): para_cache[spath] = paragraphs_of_source(spath)
                    if spath in para_cache:
                        paras, slines = para_cache[spath]
                        rng = None
                        if m1:
                            k = int(m1.group(2))
                            if 1 <= k <= len(paras): rng = (paras[max(0, k - 2)][0], paras[min(len(paras), k + 1) - 1][1])   # +-1 paragraph: the writer counted by eye
                        else:
                            # a section runs from its heading line to the next heading the note cites for the same post, else the post's end
                            h = norm(m2.group(2))
                            def heading_line(hh):
                                idx = [j for j, sl in enumerate(slines, 1) if norm(sl).strip("# ") == hh or (hh and norm(sl).startswith(hh) and len(sl) < len(hh) + 12)]
                                return idx[0] if idx else None
                            a0 = heading_line(h)
                            if a0:
                                others = sorted(x for x in (heading_line(norm(hh)) for hh in section_heads.get(code, set())) if x and x > a0)
                                rng = (a0, (others[0] - 1) if others else len(slines))
                        if rng:
                            for n in us:
                                ua = unit_line_of_source(loaded[n], src, rng[0]); ub = unit_line_of_source(loaded[n], src, rng[1])
                                if ua or ub:
                                    ua = ua or 2; ub = ub or loaded[n]["nlines"]
                                    target = (n, ua, ub, time_cell); legacy_resolved += 1; break
        if not target: rows_without += 1; continue
        rows_with += 1
        n, a, b, how = target
        u = loaded.get(n)
        if not u: fails.append(f"claims row {cells[0]}: {how} names a unit that does not exist"); line_fails += 1; continue
        if not (2 <= a <= u["nlines"]): fails.append(f"claims row {cells[0]}: {how} is outside unit {n} (lines 2 to {u['nlines']})"); line_fails += 1; continue
        window = "\n".join(u["body_lines"][max(0, a - 2):min(u["nlines"], b + 1)])
        ok, hits, need = fuzzy_hit(claim, window)
        if not ok:
            line_fails += 1
            fails.append(f"claims row {cells[0]} ({how}): unit {n} lines {a}-{b} hold {hits} of {need} content words of the claim: \"{claim[:90]}\"")
    rep = [f"# Gate 2 (note): {note}", "", f"- units: {len(units_meta)} under {wip}/units; quotation threshold {min_words} words",
           quote_line(qc),
           f"- unit coverage: {len(units_meta) - len(uncited) - len([n for n in nothing if n in units_meta])} cited, {len([n for n in nothing if n in units_meta])} declared nothing-to-row, {len(uncited)} uncited",
           f"- claims rows: {rows_with} with a unit line ({legacy_resolved} resolved from legacy citations of {legacy_cites} seen) and checked; {rows_without} without one (not checked); line failures: {line_fails}",
           f"- inventory codes found: {len(codes)}; units reached by a code: {sum(1 for n in cited if any(x.startswith('code') for x in cited[n]))}", ""]
    if fails: rep.append("## Failures"); rep += [f"- FAIL: {f}" for f in fails]
    if warns: rep.append("\n## Warnings"); rep += [f"- warn: {w}" for w in warns]
    rep += punct_section(qc)
    rep.append("\n## Unit coverage")
    for n in sorted(units_meta): rep.append(f"- {n}: {', '.join(sorted(cited[n])) or ('nothing to row: ' + nothing[n] if n in nothing else 'UNCITED')}")
    out = os.path.join(out_dir or wip, "gate-note.md")
    LN.write_text(out, "\n".join(rep) + "\n")
    ok = not fails and not (strict and warns)
    summary = {"gate": "note", "ok": ok, "quotations_checked": checked, "quote_exact": q_exact, "quote_punct": len(punct), "quote_fails": q_fail, "quote_warns": q_warn, "uncited_units": uncited,
               "claims_rows_checked": rows_with, "claims_rows_without_unit_line": rows_without, "line_fails": line_fails, "report": out,
               "summary": f"{'PASS' if ok else 'FAIL'}: {quote_counts(qc)}, {len(uncited)} uncited unit(s), {line_fails} claim line failure(s) of {rows_with} rows checked ({rows_without} rows carry no unit line); report {out}"}
    if as_json: print(json.dumps(summary))
    else:
        print(summary["summary"])
        for f in fails[:25]: print("  FAIL: " + f[:200])
        if len(fails) > 25: print(f"  ... and {len(fails) - 25} more in {out}")
    return 0 if ok else 1


def quote_counts(qc):
    return (f"{qc['checked']} quotations ({qc['exact']} exact, {len(qc['punct'])} punctuation only (forgiven), {qc['fail']} changed words"
            + (f", {qc['warn']} warnings" if 'warn' in qc else "") + ")")


def quote_line(qc):
    return (f"- quotations checked: {qc['checked']}; exact {qc['exact']}; punctuation only {len(qc['punct'])} (the same words in order: "
            f"forgiven by the caption rule, not failures); changed words: {qc['fail']} failure(s) in source-bound sections"
            + (f", {qc['warn']} warning(s) in sections that quote other notes ({', '.join(WARN_SECTIONS_NOTE[:4])}, ...)" if 'warn' in qc else ""))


def punct_section(qc):
    return (["\n## Punctuation only (forgiven: the same words in order, punctuation or capitals added; not failures)"] + [f"- {p}" for p in qc["punct"]]) if qc["punct"] else []


def note_quotes_report(note, wip, units_meta, min_words, qc, fails, warns, strict, as_json, out_dir):
    """gate 2 --quotes-only: the quotation check's report and JSON line (the coverage and claim-line checks not run)"""
    rep = [f"# Gate 2 (note, quotations only): {note}", "", f"- units: {len(units_meta)} under {wip}/units; quotation threshold {min_words} words",
           quote_line(qc),
           "- unit coverage and claim lines: not checked (--quotes-only: the note's rows carry no unit pointer)", ""]
    if fails: rep.append("## Failures"); rep += [f"- FAIL: {f}" for f in fails]
    if warns: rep.append("\n## Warnings"); rep += [f"- warn: {w}" for w in warns]
    rep += punct_section(qc)
    out = os.path.join(out_dir or wip, "gate-note-quotes.md")
    LN.write_text(out, "\n".join(rep) + "\n")
    ok = not fails and not (strict and warns)
    summary = {"gate": "note-quotes", "ok": ok, "quotations_checked": qc["checked"], "quote_exact": qc["exact"], "quote_punct": len(qc["punct"]), "quote_fails": qc["fail"], "quote_warns": qc["warn"], "report": out,
               "summary": f"{'PASS' if ok else 'FAIL'}: {quote_counts(qc)}; coverage and claim lines not checked (--quotes-only); report {out}"}
    if as_json: print(json.dumps(summary))
    else:
        print(summary["summary"])
        for f in fails[:25]: print("  FAIL: " + f[:200])
        if len(fails) > 25: print(f"  ... and {len(fails) - 25} more in {out}")
    return 0 if ok else 1


# ---------------------------------------------------------------- gate 2, parts mode (the unit writers, 2026-10-24)

ROWNUM_RE = re.compile(r"^\|\s*(\d+)(?:\.(\d+))?\s*\|")


def nothing_list(arg):
    """the unit writer's nothing_to_row field: a JSON list of {unit, reason}, a {NNN: reason} object, or @file holding either"""
    if not arg: return {}
    if arg.startswith("@"): arg = LN.read_text(arg[1:])
    try: v = json.loads(arg)
    except ValueError: sys.exit(f"--nothing-to-row: not JSON: {arg[:120]}")
    out = {}
    items = v.items() if isinstance(v, dict) else [((x.get("unit") if isinstance(x, dict) else x), (x.get("reason", "") if isinstance(x, dict) else "")) for x in v]
    for u, r in items:
        m = re.search(r"\d+", str(u))
        if m: out[m.group(0).zfill(3)] = str(r or "")
    return out


def gate_parts(parts_dir, wip, rng, nothing_arg=None, min_words=5, start_row=None, start_audit=None, as_json=False, out_dir=None):
    units_meta = load_manifest(wip)
    a, b = rng
    in_range = [n for n in sorted(units_meta) if a <= int(n) <= b]
    nothing = nothing_list(nothing_arg)
    loaded = {n: load_unit(wip, n) for n in units_meta}
    fails, warns = [], []
    unit_fail = set()
    def fail(n, msg): fails.append(msg); unit_fail.add(n)
    if not in_range: fail(f"{a:03d}", f"no unit of the manifest inside {a:03d}-{b:03d}")
    cited = {n: 0 for n in in_range}
    claims_nums, audit_nums, audit_refs = [], [], []
    q_checked = q_fail = q_exact = rows_checked = line_fails = 0; punct = []
    for n in in_range:
        for kind in ("ledger", "audit"):
            path = os.path.join(parts_dir, f"u{n}-{kind}.md")
            if not os.path.exists(path):
                if kind == "ledger" and n not in nothing: fail(n, f"unit {n}: no ledger part {path} and not in nothing_to_row")
                continue
            for i, l in enumerate(LN.read_lines(path, errors="replace"), 1):
                where = f"u{n}-{kind}.md line {i}"
                if not l.strip(): continue
                if not l.lstrip().startswith("|"): fail(n, f"{where}: not a table row (parts are table rows only, no headings or prose): \"{l[:80]}\""); continue
                if LN.is_sep(l) or re.match(r"^\|\s*#\s*\|", l): fail(n, f"{where}: a table header or separator line (parts are table rows only; the assembly adds the header)"); continue
                rm = ROWNUM_RE.match(l)
                if not rm: fail(n, f"{where}: a row without a number in its first cell: \"{l[:80]}\""); continue
                cells = LN.split_row(l)
                if len(cells) != 8: fail(n, f"{where}: row {cells[0]} has {len(cells)} cells; the {'claims ledger' if kind == 'ledger' else 'audit'} has 8"); continue
                num = (int(rm.group(1)), rm.group(2))
                (claims_nums if kind == "ledger" else audit_nums).append((num, n, where))
                if kind == "ledger":
                    for am in re.finditer(r"\bAudit (\d+)\b", cells[7]): audit_refs.append((cells[0], int(am.group(1)), n))
                if "[BLOCKED:" in l: cited[n] += 1; continue
                ptrs = [(m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), m.group(0)) for m in PTR.finditer(l)]
                if not ptrs:
                    fail(n, f"{where}: {kind} row {cells[0]} carries no pointer [u NNN:L] (every row ends its {'Note' if kind == 'ledger' else 'last'} cell with one)"); continue
                if not cells[7].rstrip(" .").endswith("]") or not PTR.search(cells[7]): warns.append(f"{where}: row {cells[0]}: the pointer is not at the end of the last cell")
                bad = False; window = []; units_named = []
                for (pu, pa, pb, raw) in ptrs:
                    u = loaded.get(pu)
                    if not u: fail(n, f"{where}: row {cells[0]}: {raw} names a unit that does not exist"); bad = True; continue
                    if not (2 <= pa <= pb <= u["nlines"]): fail(n, f"{where}: row {cells[0]}: {raw} is outside unit {pu} (lines 2 to {u['nlines']})"); bad = True; continue
                    if pu != n: warns.append(f"{where}: row {cells[0]}: {raw} points into unit {pu}, not the part's unit {n}")
                    if pu in cited: cited[pu] += 1
                    units_named.append(pu)
                    window.append("\n".join(u["body_lines"][max(0, pa - 2):min(u["nlines"], pb + 1)]))
                if bad: line_fails += 1; continue
                rows_checked += 1
                text = cells[4] if kind == "ledger" else cells[3] + " " + cells[4]
                ok, hits, need = fuzzy_hit(text, "\n".join(window))
                if not ok:
                    if kind == "ledger" or hits == 0:
                        line_fails += 1; fail(n, f"{where}: {kind} row {cells[0]} ({', '.join(p[3] for p in ptrs)}): the lines hold {hits} of {need} content words of the {'claim' if kind == 'ledger' else 'question and answer'}: \"{text[:90]}\"")
                    else: warns.append(f"{where}: audit row {cells[0]}: the pointer's lines hold {hits} of {need} content words of the question and answer")
                # quotations: in the unit(s) the pointers name
                for q in quotes_in(l):
                    segs = quote_segments(q)
                    if sum(len(x.split()) for x in segs) < min_words: continue
                    q_checked += 1
                    named = [loaded[pu] for pu in units_named]
                    tier = quote_tier(q, segs, named)
                    if tier == "exact": q_exact += 1; continue
                    if tier == "punctuation only":
                        punct.append(f"{where}: row {cells[0]}: punctuation only (the same words in order; forgiven by the caption rule): \"{q[:100]}{'...' if len(q) > 100 else ''}\""); continue
                    q_fail += 1
                    elsewhere = [m for m in loaded if loaded[m] and m not in units_named and quote_tier(q, segs, [loaded[m]]) != "changed words"]
                    fail(n, f"{where}: row {cells[0]}: changed words (not word for word in unit {', '.join(units_named)})" + (f" (it is in unit {', '.join(elsewhere)}: fix the pointer)" if elsewhere else nearest_words(q, named)) + f": \"{q[:100]}{'...' if len(q) > 100 else ''}\"")
    # numbering: on without gaps or repeats, decimals between their neighbours
    def numbering(nums, start, what):
        ints = [x for (x, _, _) in nums if x[1] is None]
        if not ints: return None, None
        first, prev = ints[0][0], None
        if start is not None and first != start: fail(nums[0][1], f"{what}: the first row is {first}; this writer starts at {start}")
        seen = set()
        for (x, n, where) in nums:
            key = f"{x[0]}.{x[1]}" if x[1] is not None else str(x[0])
            if key in seen: fail(n, f"{where}: {what} row {key} repeated")
            seen.add(key)
            if x[1] is not None:
                if prev is not None and x[0] != prev: fail(n, f"{where}: {what} row {key} does not follow row {prev}")
                continue
            if prev is not None and x[0] != prev + 1: fail(n, f"{where}: {what} row {x[0]} follows row {prev} (rows run on without gaps)")
            prev = x[0]
        return first, prev
    r0, r1 = numbering(claims_nums, start_row, "claims")
    a0, a1 = numbering(audit_nums, start_audit, "audit")
    audit_have = {x[0] for (x, _, _) in audit_nums}
    for (row, ref, n) in audit_refs:
        if ref not in audit_have and (a0 is None or not (start_audit or 1) <= ref <= (a1 or 0)): warns.append(f"claims row {row} (unit {n}) names Audit {ref}, which is not a row of this range's audit parts")
    uncited = [n for n in in_range if not cited[n] and n not in nothing]
    for n in uncited: fail(n, f"unit {n} cited by no row's pointer and not in nothing_to_row ({units_meta[n]['span'][:90]})")
    for n in nothing:
        if n in cited and cited[n]: warns.append(f"unit {n} is in nothing_to_row but rows point at it")
        if n not in units_meta: warns.append(f"nothing_to_row names unit {n}, which is not in the manifest")
    rows_s = f"{r0}-{r1}" if r0 is not None else ""; aud_s = f"{a0}-{a1}" if a0 is not None else ""
    qc = {"checked": q_checked, "exact": q_exact, "punct": punct, "fail": q_fail}
    rep = [f"# Gate 2 (parts): {parts_dir}, units {a:03d}-{b:03d}", "", f"- units in range: {', '.join(in_range)}; nothing to row: {', '.join(f'{k} ({v})' for k, v in sorted(nothing.items())) or 'none'}",
           f"- claims rows {len(claims_nums)} ({rows_s or 'none'}), audit rows {len(audit_nums)} ({aud_s or 'none'}); rows with pointers checked: {rows_checked}; line failures: {line_fails}",
           quote_line(qc) + " (in the unit each row's pointer names)", f"- uncited units: {', '.join(uncited) or 'none'}", ""]
    if fails: rep.append("## Failures"); rep += [f"- FAIL: {f}" for f in fails]
    if warns: rep.append("\n## Warnings"); rep += [f"- warn: {w}" for w in warns]
    rep += punct_section(qc)
    rep.append("\n## Unit coverage")
    for n in in_range: rep.append(f"- {n}: {cited[n]} row pointer(s)" + (f"; nothing to row: {nothing[n]}" if n in nothing else ""))
    out = os.path.join(out_dir or wip, f"gate-parts-{a:03d}-{b:03d}.md")
    LN.write_text(out, "\n".join(rep) + "\n")
    ok = not fails
    summary = {"gate": "parts", "ok": ok, "units": f"{a:03d}-{b:03d}", "rows": rows_s, "audit_rows": aud_s, "last_row": r1, "last_audit_row": a1,
               "claims_rows": len(claims_nums), "audit_rows_n": len(audit_nums), "quotations_checked": q_checked, "quote_exact": q_exact, "quote_punct": len(punct), "quote_fails": q_fail, "line_fails": line_fails,
               "uncited_units": uncited, "failing_units": sorted(unit_fail), "fails": len(fails), "warns": len(warns), "report": out,
               "summary": f"{'PASS' if ok else 'FAIL'}: units {a:03d}-{b:03d}: claims rows {rows_s or 'none'} ({len(claims_nums)}), audit rows {aud_s or 'none'} ({len(audit_nums)}); {quote_counts(qc)}, {line_fails} pointer failure(s), {len(uncited)} uncited unit(s), {len(fails)} failure(s), {len(warns)} warning(s); report {out}"}
    if as_json: print(json.dumps(summary))
    else:
        print(summary["summary"])
        for f in fails[:25]: print("  FAIL: " + f[:200])
        if len(fails) > 25: print(f"  ... and {len(fails) - 25} more in {out}")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    as_json = "--json" in a; strict = "--strict" in a
    wip = opt("--wip")
    if not wip: sys.exit(__doc__)
    rng = None
    if opt("--units"):
        m = re.match(r"(\d+)-(\d+)", opt("--units")); rng = (int(m.group(1)), int(m.group(2))) if m else (int(opt("--units")), int(opt("--units")))
    if "--findings" in a:
        sys.exit(gate_findings(wip, legacy=opt("--legacy-findings"), min_words=int(opt("--min-words", 4)), strict=strict, mark="--mark" in a, rng=rng, as_json=as_json, status_only="--status" in a, out_dir=opt("--out"),
                               budget=float(opt("--budget")) if opt("--budget") else None, size_only="--size" in a))
    if "--note-parts" in a:
        if not rng: sys.exit("--note-parts needs --units A-B")
        sys.exit(gate_parts(opt("--note-parts"), wip, rng, nothing_arg=opt("--nothing-to-row"), min_words=int(opt("--min-words", 5)),
                            start_row=int(opt("--start-row")) if opt("--start-row") else None, start_audit=int(opt("--start-audit")) if opt("--start-audit") else None,
                            as_json=as_json, out_dir=opt("--out")))
    if "--note" in a:
        sys.exit(gate_note(opt("--note"), wip, min_words=int(opt("--min-words", 5)), para_cites="--para-cites" in a, strict=strict, as_json=as_json, out_dir=opt("--out"),
                           quotes_only="--quotes-only" in a))
    sys.exit(__doc__)


if __name__ == "__main__": main()
