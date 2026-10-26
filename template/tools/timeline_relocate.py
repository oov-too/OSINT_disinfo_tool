#!/usr/bin/env python3
"""Retire or relocate Dated timeline rows under the decimal-ID rule (schema section 11), updating every citation.

  python3 tools/timeline_relocate.py <note.md> --move ID [ID ...] [--dry]
      Moves each row into its chronological place with a new decimal ID (via tools/timeline_insert.py's logic);
      its Agreement cell ends "(was tl N until <date>)"; every hand-written citation of the old ID is updated.
  python3 tools/timeline_relocate.py <note.md> --retire ID --to NEWID [--dry]
      Removes a duplicate row; the note's Dated timeline intro records "tl ID retired <date> (duplicate of tl NEWID); the ID is not reused";
      citations of the old ID are pointed at NEWID.
Citations are found as a link to the note (its slug) followed within 120 characters by "tl N" or "timeline N" (N not followed
by a decimal digit), in research/*.md (except the generated timeline-master.md), subjects/*.md, videos/*.md and books/*.md;
inside the note itself, bare "tl N" in Note cells is updated. The generated master timeline is rebuilt by build_timeline.py.
"""
import sys, re, os, glob, json, datetime, importlib.util
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools")); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
spec = importlib.util.spec_from_file_location("ti", os.path.join(_T, "timeline_insert.py")); ti = importlib.util.module_from_spec(spec); spec.loader.exec_module(ti)
from decimal import Decimal
TODAY = datetime.date.today().isoformat()
args = sys.argv[1:]; dry = "--dry" in args; args = [a for a in args if a != "--dry"]
note = args[0]; slug = os.path.basename(note)[:-3]
def table_bounds(L):
    b = LN.hash_table_bounds(L, "## dated timeline")   # form T3 (section by form S1)
    if b is None: raise StopIteration("no ## Dated timeline section")
    return b
def cite_pages():
    pages = [p for p in glob.glob("research/*.md") if not p.endswith("timeline-master.md")] + glob.glob("research/corrections/*.md")
    pages += glob.glob("subjects/*.md") + glob.glob("videos/*.md") + glob.glob("books/*.md")
    return [p for p in pages if os.path.abspath(p) != os.path.abspath(note)]
def update_citations(old, new):
    pat = LN.tl_citation_re(slug, old)
    total = 0
    for p in cite_pages():
        s = LN.read_text(p); s2, n = pat.subn(lambda m: m.group(1) + new, s)
        if n:
            total += n; print(f"  citation {p}: {n}")
            if not dry: LN.write_text(p, s2)
    # inside the note: bare 'tl N' in Note cells and prose
    s = LN.read_text(note)
    # never rewrite the history markers themselves ("Retired IDs:" lines and "(was tl N until ...)")
    out, n = [], 0
    for line in s.split("\n"):
        if line.startswith("Retired IDs:"): out.append(line); continue
        parts = LN.TL_HISTORY_RE.split(line)
        for k in range(0, len(parts), 2):
            parts[k], c = LN.tl_bare_re(old).subn("tl " + new, parts[k]); n += c
        out.append("".join(parts))
    s2 = "\n".join(out)
    if n and not dry: LN.write_text(note, s2)
    print(f"  in-note references: {n}"); return total + n
L = LN.read_lines(note)
if "--retire" in args:
    rid = args[args.index("--retire") + 1]; to = args[args.index("--to") + 1]
    s, h, st, en = table_bounds(L)
    i = next(i for i in range(st, en) if L[i].split("|")[1].strip() == rid)
    print("retiring:", L[i][:120]); del L[i]
    intro = f"Retired IDs: tl {rid} retired {TODAY} (duplicate of tl {to}; owner's decision); the ID is not reused."
    j = next((k for k in range(s + 1, h) if L[k].startswith("Retired IDs:")), None)
    if j is None: L.insert(h, intro); L.insert(h + 1, "")
    else: L[j] = L[j].rstrip() + " " + intro[len("Retired IDs: "):]
    if not dry: LN.write_lines(note, L)
    update_citations(rid, to)
elif "--move" in args:
    ids = args[args.index("--move") + 1:]
    for rid in ids:
        L = LN.read_lines(note)
        s, h, st, en = table_bounds(L)
        i = next(i for i in range(st, en) if L[i].split("|")[1].strip() == rid)
        c = LN.split_row(L[i])
        del L[i]
        tmp = note + ".reloc.tmp"; LN.write_lines(tmp, L)
        row = {"date_stated": c[1], "sortable": c[2], "event": c[3], "speaker_basis": c[4], "chain": c[5], "link": c[6], "agreement": c[7] + f" (was tl {rid} until {TODAY})"}
        rj = note + ".reloc.json"; json.dump([row], open(rj, "w"))
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(_T, "timeline_insert.py"), tmp, rj] + (["--dry"] if dry else []), capture_output=True, text=True)
        m = re.search(r"tl (\S+)\s+at position", r.stdout); new = m.group(1) if m else None
        print(f"move tl {rid} -> tl {new}")
        if not dry: os.replace(tmp, note)
        else: os.remove(tmp)
        os.remove(rj)
        if new and new != rid: update_citations(rid, new)
else:
    sys.exit(__doc__)
