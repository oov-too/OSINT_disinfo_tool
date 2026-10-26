"""The openness dataset's entry for one audited note, from the note itself (pilot defect 10, 7b2 2026-10-23): `openness_counts` from the
note's audit counts line and `openness_cells` one per scored audit row, in the shapes tools/integrate_report.py reads.

    python3 tools/ledger/openness.py <note.md> [--root PROJECT]     prints {"openness_counts": {...}, "openness_cells": [...]} as JSON

A cell is {topic, class, evidence, basis}: the class is the row's Move (the first class named; n/a rows are not cells), the topic the
claims ledger's topic for the rows whose Note names `Audit N` (the most frequent), else the claims rows at the audit row's time, else
`other`; the evidence is the audit row's number with the start of its answer summary. The counts are the counts line's six numbers
(the line tools/note_fill.py generates from the table). A note with no audit table or no counts line gives nothing."""
import collections, json, os, re, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ledger import notes as LN
else:
    from . import notes as LN

CLASSES = ("open", "partial", "contested", "closed-subtle", "closed-outright")
KEYS = ("open", "partial", "closed_outright", "closed_subtle", "stated_declines", "pseudo_declines")


def _move(m):
    m = (m or "").strip().lower().split(" then ")[0].split(";")[0].strip()
    m = {"closed outright": "closed-outright", "closed subtle": "closed-subtle"}.get(m, m)
    return m if m in CLASSES else None


def _time_key(t):
    m = re.match(r"\s*(\d+:\d\d:\d\d|\d+:\d\d|p\.\s*\d+|\d+:\d+)", t or "")
    return m.group(1) if m else None


def from_note(path, root=None):
    """(openness_counts dict or {}, openness_cells list) for the note at path."""
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(path)))
    o = LN.parse_note(path, root)
    counts = dict(zip(KEYS, (int(x or 0) for x in o["counts"]))) if o.get("counts") else {}
    if not counts or not o.get("audit"): return {}, []
    by_audit, by_time = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for c in o["claims"]:
        time, topic, note = c[1], c[3], c[7]
        for a in re.findall(r"[Aa]udit\s+(\d+)", note or ""): by_audit[a][topic] += 1
        k = _time_key(time)
        if k and topic and topic != "other": by_time[k][topic] += 1
    cells = []
    for r in o["audit"]:
        n, time, asked, q, answer, move, basis = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        cls = _move(move)
        if cls is None: continue
        num = re.sub(r"[^\d.]", "", str(n))
        topic = (by_audit[num].most_common(1)[0][0] if by_audit.get(num) else
                 by_time[_time_key(time)].most_common(1)[0][0] if _time_key(time) and by_time.get(_time_key(time)) else "other")
        ev = " ".join((answer or q or "").split())
        cells.append({"topic": topic, "class": cls, "evidence": f"audit {n}: {ev[:160]}", "basis": (basis or "n/a").strip() or "n/a"})
    return counts, cells


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0 if a else 2
    root = a[a.index("--root") + 1] if "--root" in a else None
    counts, cells = from_note(a[0], root)
    print(json.dumps({"openness_counts": counts, "openness_cells": cells}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
