#!/usr/bin/env python3
"""Verbatim check: spans of a draft that reproduce a held source word for word (standing, 2026-10-02).

Long verbatim reproduction of a fetched text through the model's output is the most likely trigger of an API output block
and breaks the house quotation limit (a sentence or two). Agents run this on each note part before writing it; the
orchestrator runs it on every note at integration.

Usage: python3 tools/verbatim_check.py <draft.md> [--min 40] [--sources books/sources transcripts]
Defaults: 40 words (two long sentences) against books/sources/ (third-party texts); add transcripts to check interview quotations too.
Prints every span of >= min consecutive words (after normalisation) that also occurs in a file under the source folders,
with the source file; exit code 1 when any span is found.
"""
import sys, os, re, glob
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # project paths and the sources/ alias table
def norm_words(t):
    t = re.sub(r"\\(.)", r"\1", t); t = re.sub(r"https?://\S+", " ", t); t = re.sub(r"[^\w\s']", " ", t.lower())
    return t.split()
def main():
    a = sys.argv[1:]; draft = a[0]; n = int(a[a.index("--min") + 1]) if "--min" in a else 40
    src = a[a.index("--sources") + 1:] if "--sources" in a else ["books/sources"]
    dw = norm_words(LN.read_text(LP.resolve_arg(draft)))
    shingles = {}
    for i in range(len(dw) - n + 1): shingles.setdefault(" ".join(dw[i:i + n]), []).append(i)
    hits = []
    files = [f for s in src for f in glob.glob(os.path.join(LP.resolve_arg(os.path.join(ROOT, s)), "**", "*"), recursive=True) if os.path.isfile(f) and f.endswith((".md", ".txt"))]   # a sources/ layout folder resolves to the held folder
    for f in files:
        if os.path.abspath(f) == os.path.abspath(draft): continue
        try: sw = norm_words(LN.read_text(f, errors="replace"))
        except OSError: continue
        seen = set()
        for j in range(len(sw) - n + 1):
            k = " ".join(sw[j:j + n])
            if k in shingles and k not in seen: seen.add(k); hits.append((shingles[k][0], os.path.relpath(f, ROOT)))
    # merge overlapping draft positions into spans
    hits.sort(); spans = []
    for pos, f in hits:
        if spans and spans[-1][2] == f and pos <= spans[-1][1] + 1: spans[-1][1] = pos + n
        else: spans.append([pos, pos + n, f])
    for s, e, f in spans: print(f"{e - s} words at draft word {s}: \"{' '.join(dw[s:s + 12])} ...\"  <- {f}")
    print(f"{len(spans)} verbatim span(s) of >= {n} words" + (" (trim to the house limit, a sentence or two, or cite by pointer)" if spans else ""))
    sys.exit(1 if spans else 0)
if __name__ == "__main__": main()
