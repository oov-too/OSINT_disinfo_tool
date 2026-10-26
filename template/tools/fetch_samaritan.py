#!/usr/bin/env python3
"""Extract the Samaritan Pentateuch from the CACCHT Text-Fabric dataset (github.com/DT-UCPH/sp; Christian Canu Højgaard,
Martijn Naaijer and Stefan Schorch, 2023; text supplied by the Samaritanus project at Halle, based on MS Dublin Chester
Beatty 751 with MS Garizim 1 for the end of Deuteronomy; CC BY-NC 4.0, for research and education) and write
books/sources/samaritan-pentateuch.txt, one verse per line: "<book> c:v<TAB>consonantal text" in Hebrew square-script
letters as the dataset transcribes them, the dataset's morpheme splits rejoined into written words.
Usage: python3 tools/fetch_samaritan.py [--from-dir <dir with the .tf files>] [--version 7.2.4]"""
import re, sys, os, urllib.request, bisect, unicodedata
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
FROM = sys.argv[sys.argv.index("--from-dir") + 1] if "--from-dir" in sys.argv else None
VER = sys.argv[sys.argv.index("--version") + 1] if "--version" in sys.argv else "7.2.4"
BASE = f"https://raw.githubusercontent.com/DT-UCPH/sp/main/tf/{VER}/"
BOOK = {"Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut"}
POINTS = re.compile(r"[֑-ֽֿ-ׇׂׅׄ]")
def get(name):
    if FROM: return open(os.path.join(FROM, name + ".tf"), encoding="utf-8").read()
    return urllib.request.urlopen(BASE + name + ".tf", timeout=120).read().decode("utf-8")
def node_feature(name):
    vals = {}; node = 0; body = get(name).split("\n\n", 1)[1]
    for line in body.split("\n"):
        if "\t" in line: n, v = line.split("\t", 1); node = int(n)
        else: node += 1; v = line
        vals[node] = v
    return vals
otype = get("otype").split("\n\n", 1)[1]; ranges = {}
for line in otype.split("\n"):
    m = re.match(r"(\d+)-(\d+)\t(\w+)", line)
    if m: ranges[m.group(3)] = (int(m.group(1)), int(m.group(2)))
B0, B1 = ranges["book"]; C0, C1 = ranges["chapter"]; V0, V1 = ranges["verse"]; W0, W1 = ranges["word"]
first = {}; node = None
for line in get("oslots").split("\n\n", 1)[1].split("\n"):
    if not line: continue
    if "\t" in line: n, v = line.split("\t", 1); node = int(n)
    else: node += 1; v = line
    if B0 <= node <= B1 or C0 <= node <= C1 or V0 <= node <= V1 or W0 <= node <= W1: first[node] = int(v.split(",")[0].partition("-")[0])
book = node_feature("book"); chapter = node_feature("chapter"); verse = node_feature("verse"); cons = node_feature("g_cons_utf8"); trailer = node_feature("trailer")
def lookup(nodes):
    starts = sorted((first[n], n) for n in nodes if n in first); keys = [s for s, n in starts]
    return lambda slot: starts[bisect.bisect_right(keys, slot) - 1][1]
bookof = lookup(range(B0, B1 + 1)); chapof = lookup(range(C0, C1 + 1)); verseof = lookup(range(V0, V1 + 1))
byverse = {}; order = []; cur = None
for w in range(W0, W1 + 1):
    if w not in first: continue
    s = first[w]; ref = f"{BOOK.get(book[bookof(s)], book[bookof(s)])} {chapter[chapof(s)]}:{verse[verseof(s)]}"
    text = POINTS.sub("", unicodedata.normalize("NFKD", cons.get(w, ""))).strip()  # the dataset uses precomposed shin and sin (U+FB2A, U+FB2B); decompose, then drop the dots
    if not text: continue
    if ref not in byverse: byverse[ref] = []; order.append(ref); cur = None
    if cur is not None and cur == ref and byverse[ref] and not joined_done: byverse[ref][-1] += text
    else: byverse[ref].append(text)
    joined_done = bool(trailer.get(w, "").strip()) or trailer.get(w, "") == " "  # a space in the trailer ends the written word
    cur = ref
out = ["# The Samaritan Pentateuch, consonantal text by verse (book chapter:verse, tab, text), in Hebrew square-script letters as the dataset transcribes it (the Samaritan script has no final forms; the transcription's final forms are the editors').",
       "# Source: the CACCHT Text-Fabric dataset of the Samaritan Pentateuch, github.com/DT-UCPH/sp (Højgaard, Naaijer and Schorch 2023; text from the Samaritanus project, Halle, after MS Dublin Chester Beatty 751 and MS Garizim 1); CC BY-NC 4.0, used for research.",
       f"# Extracted by tools/fetch_samaritan.py (dataset version {VER}); the dataset's morpheme splits are rejoined into written words by its trailer feature.", ""]
for ref in order: out.append(ref + "\t" + " ".join(byverse[ref]))
LN.write_text(LP.new_hold("books/sources/samaritan-pentateuch.txt"), "\n".join(out) + "\n")
print(f"wrote books/sources/samaritan-pentateuch.txt: {len(order)} verses, {sum(len(v) for v in byverse.values())} words")
