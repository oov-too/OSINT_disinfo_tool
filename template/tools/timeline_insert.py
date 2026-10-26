#!/usr/bin/env python3
"""Insert rows into a note's `## Dated timeline` in date order, without renumbering anything.

Row IDs are permanent decimal IDs (schema section 11, owner ruling 2026-09-28), in the manner of the Dewey decimal system:
a row that belongs between rows 12 and 13 becomes 12.1; between 12 and 12.1 it becomes 12.01; between 12.1 and 12.2, 12.15.
Existing IDs never change and are never reused, so every citation of the form "tl 12" stays valid forever, and the table
stays in chronological order as new dates arrive. A row that belongs after the last row takes the next whole number.

Usage:
  python3 tools/timeline_insert.py <note.md> <rows.json> [--dry]
rows.json is a list of objects with the table's columns:
  {"date_stated": "...", "sortable": "1987-07", "event": "...", "speaker_basis": "...", "chain": "...", "link": "...", "agreement": "new"}
Prints each new row's ID and position. With --dry nothing is written.
"""
import sys, re, json, os
from decimal import Decimal, ROUND_FLOOR
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)

sort_key = LN.sort_key   # form Q6: the schema's sort key (year + 1,000,000,000, ten digits, -MM-DD)

def fmt(d):
    s = format(d.normalize(), "f")
    return s

def between(a, b, taken):
    """Smallest-digit decimal strictly between a and b (b may be None for 'after a'), not in taken."""
    if b is None:
        c = (a.to_integral_value(rounding=ROUND_FLOOR)) + 1
        while c in taken: c += 1
        return c
    for k in range(1, 9):
        step = Decimal(1).scaleb(-k)
        c = (a / step).to_integral_value(rounding=ROUND_FLOOR) * step + step
        while c < b and c in taken: c += step
        if a < c < b and c not in taken: return c
    raise SystemExit(f"no room between {a} and {b}")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; dry = "--dry" in sys.argv
    if len(args) != 2: sys.exit(__doc__)
    path, rows_path = args
    new_rows = json.load(open(rows_path, encoding="utf-8"))
    L = LN.read_lines(path)
    b = LN.hash_table_bounds(L, "## dated timeline")   # form T3 (section by form S1)
    if b is None: sys.exit("no ## Dated timeline section")
    s, h, start, end = b
    parse = LN.split_row   # form F2
    table = [parse(L[i]) for i in range(start, end)]
    ids = [Decimal(c[0]) for c in table]
    keys = [sort_key(c[2]) for c in table]
    taken = set(ids)
    out = []
    def in_place_mask():
        # a row is out of place if its date is earlier than some row above it (legacy rows appended at the end);
        # positions are computed over the in-place rows only, so appended stragglers do not pull new rows to the end
        # compare only at the precision the lower row gives: a year-only "2007" or a range starting 2007 under
        # "2007-01-08" is in place (fixed 2026-09-28 after the B2 report)
        def prec(kk): return 10 if kk.endswith("-00-00") else (13 if kk.endswith("-00") else 16)
        mask, hi = [], None
        for kk in keys:
            ok = hi is None or kk[:prec(kk)] >= hi[:prec(kk)]
            mask.append(ok)
            if ok and (hi is None or kk > hi): hi = kk
        return mask
    for r in new_rows:
        k = sort_key(r["sortable"])
        mask = in_place_mask()
        inplace = [i for i, m in enumerate(mask) if m]
        after = [i for i in inplace if keys[i] <= k]
        nxt = [i for i in inplace if keys[i] > k]
        if after:
            ia = after[-1]; a = ids[ia]; pos = ia + 1
        else:
            ia = None; a = Decimal(0); pos = inplace[0] if inplace else 0
        if nxt:
            b = ids[nxt[0]]
            if b <= a: b = None
            if ia is not None: pos = min(nxt[0], ia + 1) if nxt[0] > ia else ia + 1
            else: pos = nxt[0]
        else:
            b = None
            if ia is not None: pos = ia + 1
        # never collide with or overtake an existing ID: the upper bound is the smallest taken ID above a
        higher = [x for x in taken if x > a]
        if higher and (b is None or min(higher) < b): b = min(higher) if b is not None or ia is None or ids[ia] != max(taken) else None
        new_id = between(a, b, taken)
        taken.add(new_id)
        cells = [fmt(new_id), r["date_stated"], r["sortable"], r["event"], r["speaker_basis"], r["chain"], r["link"], r["agreement"]]
        cells = [str(x).replace("|", "/").replace("\n", " ") for x in cells]
        table.insert(pos, cells); ids.insert(pos, new_id); keys.insert(pos, k)
        print(f"tl {fmt(new_id)}  at position {pos + 1}  ({r['sortable']}: {r['event'][:70]})")
    if dry: return
    rendered = ["| " + " | ".join(c) + " |" for c in table]
    L[start:end] = rendered
    LN.write_lines(path, L)
    print(f"wrote {len(new_rows)} rows into {path}")

if __name__ == "__main__":
    main()
