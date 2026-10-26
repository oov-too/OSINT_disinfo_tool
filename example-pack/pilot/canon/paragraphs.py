"""packs/pilot/canon/paragraphs.py: the pilot pack's paragraph marker for judgments (a pack plugin of the canon layer).

A judgment's unit is the numbered paragraph ("at [123]"). The held judgments are scans whose text layer is the publisher's OCR, so
a paragraph number at the start of a line can be damaged ("1.This", "1 1.", "l2.") and numbered sub-lists, tables of contents and
footnotes also start lines with a number. The core canon adapter's `headings` scheme matches a pattern line by line and cannot
require the numbers to run in order (finding 11 of wip/platform-phase6b/adapter-findings.md), so this plugin finds the paragraph
starts first and the core scheme then cuts the units:

1. candidates: lines that open with a number (OCR letters O, o, l, I, | read as digits; inner spaces dropped) followed by `.` or
   `,` (or a lone number on its own line followed by text);
2. the chain: walking the text in order, a candidate is a paragraph start only if its number is the next expected one or at most
   GAP numbers beyond it (the first must be paragraph 1 exactly, so hearing dates and case numbers in the front matter cannot
   start the chain); anything else (a sub-list "1.", a footnote, a contents line) is left as text;
3. output: the text with one marker line `¶ <n>` inserted before each paragraph start; no line of the text is changed, so a
   verbatim quotation of the text layer still matches; and a report of the paragraphs found, the numbers missing from the chain
   (their text stays inside the previous paragraph's unit), the candidates rejected, and the first line of each paragraph.

The scheme file packs/pilot/canon/schemes/<text id>.json then has one level, pattern `^¶ (\\d+)$`, keep_heading false.

    python3 -I packs/pilot/canon/paragraphs.py <text-layer.txt> <marked.txt> <report.json> [--gap 3] [--first 1] [--start-after REGEX]
"""
import json, re, sys

GAP = 3
CAND = re.compile(r"^\s*([0-9OoIl|][0-9OoIl| ]{0,5}?)\s?[.,]\s?(?=\S)")
ALONE = re.compile(r"^\s*([0-9OoIl|][0-9OoIl| ]{0,5}?)\s?[.,]?\s*$")
OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})


def as_number(s):
    s = s.translate(OCR_DIGITS).replace(" ", "")
    return int(s) if s.isdigit() and len(s) <= 4 else None


def find_paragraphs(lines, gap=GAP, first=1, start_after=None):
    """[(line index 0-based, paragraph number)] of the chain; rejected candidates; missing numbers. `start_after`: a regex for the
    line after which the judgment's text begins (e.g. "^Lord Justice Holroyde"); when the first paragraph's number was lost in the
    OCR, the first non-empty line after it is taken as paragraph `first` (recorded in the report)."""
    chain = []; rejected = []; missing = []; expect = first; begin = 0; self_start = None
    if start_after:
        rx = re.compile(start_after)
        k = next((i for i, l in enumerate(lines) if rx.search(l)), None)
        if k is not None:
            begin = k + 1
            nonempty = [i for i in range(begin, len(lines)) if lines[i].strip()][:6]
            numbered_first = any((m := CAND.match(lines[i])) and as_number(m.group(1)) == first for i in nonempty)
            j = nonempty[0] if nonempty else None
            if j is not None and not numbered_first:     # only when no line near the start carries the first number
                chain.append((j, first)); expect = first + 1; self_start = j + 1
    for i, line in enumerate(lines):
        if i < begin: continue
        if line.startswith("--- page "): continue
        m = CAND.match(line)
        n = as_number(m.group(1)) if m else None
        if n is None:
            m2 = ALONE.match(line)
            if m2 and i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith("--- page "):
                n = as_number(m2.group(1))
        if n is None: continue
        if (n == expect) if not chain else (expect <= n <= expect + gap):     # the first paragraph must be `first` exactly
            missing.extend(range(expect, n)); chain.append((i, n)); expect = n + 1
        else:
            rejected.append((i + 1, n))
    find_paragraphs.self_start = self_start
    return chain, rejected, missing


def mark(text, gap=GAP, first=1, start_after=None):
    lines = text.split("\n")
    chain, rejected, missing = find_paragraphs(lines, gap, first, start_after)
    starts = {i: n for i, n in chain}; out = []
    for i, line in enumerate(lines):
        if i in starts: out.append(f"¶ {starts[i]}")
        out.append(line)
    report = dict(paragraphs=len(chain), last=chain[-1][1] if chain else 0, missing=missing, gap=gap,
                  rejected_candidates=len(rejected), rejected_first=rejected[:40],
                  first_lines={str(n): lines[i][:100] for i, n in chain[:5]},
                  start_after=start_after, first_paragraph_unnumbered_at_line=getattr(find_paragraphs, "self_start", None),
                  rule="a candidate is a paragraph start only if its number is the next expected or at most `gap` beyond it; "
                       "missing numbers stay inside the previous paragraph's unit")
    return "\n".join(out), report


def main(argv):
    src, dst, rep = argv[:3]
    gap = int(argv[argv.index("--gap") + 1]) if "--gap" in argv else GAP
    first = int(argv[argv.index("--first") + 1]) if "--first" in argv else 1
    start_after = argv[argv.index("--start-after") + 1] if "--start-after" in argv else None
    text = open(src, encoding="utf-8").read().replace("\r\n", "\n")
    marked, report = mark(text, gap, first, start_after)
    with open(dst, "w", encoding="utf-8", newline="\n") as f: f.write(marked)
    with open(rep, "w", encoding="utf-8", newline="\n") as f: json.dump(report, f, indent=1, ensure_ascii=False); f.write("\n")
    print(json.dumps({k: report[k] for k in ("paragraphs", "last", "missing", "rejected_candidates")}))


if __name__ == "__main__":
    main(sys.argv[1:])
