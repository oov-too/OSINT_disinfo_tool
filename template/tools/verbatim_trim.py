#!/usr/bin/env python3
"""Make long verbatim quotations referential (owner's rule, 2026-10-03): a quoted passage of 40 or more words that is held in full
under books/sources/ keeps its first 25 words in the note and points to the held copy; the one full copy is the source file.

Usage: python3 tools/verbatim_trim.py <note.md> [--min 40] [--keep 25] [--apply]
Finds every quoted span (straight or curly quotes) of >= min words whose 8-word shingles occur (>= 90%) in a file under
books/sources/ (books/sources/reddit, books/sources/web and their subfolders), and rewrites it as
  “<first keep words> …” [full passage in the held copy: <path>]
Dry run prints each trim; --apply writes the note. Idempotent (trimmed spans are shorter than min).
"""
import sys, os, re, glob
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
def norm_words(t):
    t = re.sub(r"\\(.)", r"\1", t); t = re.sub(r"https?://\S+", " ", t); t = re.sub(r"[^\w\s']", " ", t.lower()); return t.split()
def shingles(w, n=8): return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
def main():
    a = sys.argv[1:]; note = a[0]; mn = int(a[a.index("--min") + 1]) if "--min" in a else 40; keep = int(a[a.index("--keep") + 1]) if "--keep" in a else 25
    s = open(note, encoding="utf-8").read()
    srcs = {}
    for f in glob.glob(os.path.join(ROOT, "books/sources/**/*"), recursive=True):
        if f.endswith((".md", ".txt")) and os.path.isfile(f):
            try: srcs[os.path.relpath(f, ROOT)] = shingles(norm_words(open(f, encoding="utf-8", errors="replace").read()))
            except OSError: pass
    # note-relative pointer (notes live in books/ or videos/)
    rel = lambda p: os.path.relpath(os.path.join(ROOT, p), os.path.dirname(os.path.abspath(note)))
    pat = re.compile(r"([\"“])([^\"“”]{150,}?)([\"”])")
    trims = []
    def sub(m):
        q = m.group(2); w = q.split()
        if len(w) < mn: return m.group(0)
        sh = shingles(norm_words(q))
        if not sh: return m.group(0)
        best = max(srcs, key=lambda k: len(sh & srcs[k]) / len(sh)); score = len(sh & srcs[best]) / len(sh)
        if score < 0.9: return m.group(0)
        trims.append((len(w), best, " ".join(w[:8])))
        return f"{m.group(1)}{' '.join(w[:keep])} …{m.group(3)} [full passage in the held copy: {rel(best)}]"
    out = pat.sub(sub, s)
    for n, src, head in trims: print(f"  {n} words -> {keep}: “{head} …”  ({src})")
    print(f"{os.path.basename(note)}: {len(trims)} span(s) trimmed" + ("" if "--apply" in a else " (dry run)"))
    if "--apply" in a and trims: open(note, "w", encoding="utf-8").write(out)
if __name__ == "__main__": main()
