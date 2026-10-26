#!/usr/bin/env python3
"""The assembly step of the unit-writers form (2026-10-24; wip/intake-staged/phases/write-unit.md; tools/workflows/staged-intake.js
`form: "unit-writers"`): a script, not an agent, builds the note from the skeleton and the unit writers' parts.

    python3 tools/assemble_parts.py --wip wip/<task> --note books/<note>.md [--nothing-to-row <json>] [--json]

What it writes, and only this:
  - the skeleton (wip/<task>/skeleton.md) with every exemplar line it carries dropped (each line marked `<!-- example`, and the
    Notable quotes example items `N. (h:mm:ss) "..."`: their quotations are another note's and fail gate 2 against this source);
  - a `Status` row at the end of the metadata table: `in progress (assembled from the unit writers' parts; writer B and the finish
    to follow)`; every other metadata cell as the skeleton gives it, for writer B;
  - the line `Units with nothing to row: NNN (reason); ...` directly above `## Claims ledger`, from --nothing-to-row (the unit
    writers' reply fields, merged: a JSON list of {"unit", "reason"}, a {"NNN": "reason"} object, or `@file` holding either);
  - under `## Claims ledger`, below its header row and separator, every row of wip/<task>/parts/u<NNN>-ledger.md in unit order;
    under `## Forthrightness audit`, likewise, every row of the u<NNN>-audit.md parts; the audit's counts line, its comments and
    its prose headings stay as the skeleton gives them (writer B writes the prose; the finish phase generates the counts).
Rows are copied as written: none is renumbered, generated or changed. wip/<task>/ledger-notes.md is left as the unit writers wrote
it, for writer B. The note is overwritten only when it does not exist or is an earlier assembly (its Status row says so); a note
past assembly is never touched. One JSON line on stdout: ok, note, claims_rows, audit_rows, units, nothing_to_row, words.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN
import intake_gate as G

STATUS = "in progress (assembled from the unit writers' parts; writer B and the finish to follow)"
EXAMPLE_QUOTE = re.compile(r'^\d+\. \(\d+:\d\d(:\d\d)?\) "')


def rows_of(path):
    return [l for l in LN.read_lines(path, errors="replace") if l.strip()] if os.path.exists(path) else []


def assemble(wip, note, nothing_arg=None):
    skel = LN.read_lines(os.path.join(wip, "skeleton.md"))
    if os.path.exists(note) and STATUS not in LN.read_text(note):
        return {"ok": False, "note": note, "summary": f"{note} exists and is not an earlier assembly; nothing written"}
    units = sorted(G.load_manifest(wip))
    parts = os.path.join(wip, "parts")
    ledger, audit = [], []
    for n in units:
        ledger += rows_of(os.path.join(parts, f"u{n}-ledger.md"))
        audit += rows_of(os.path.join(parts, f"u{n}-audit.md"))
    nothing = G.nothing_list(nothing_arg)
    out, sec, i = [], None, 0
    in_meta = False; meta_done = False
    while i < len(skel):
        l = skel[i]
        if "<!-- example" in l or EXAMPLE_QUOTE.match(l): i += 1; continue
        # the metadata table: the first `| | |` table before the first `## ` heading; a Status row at its end
        if not meta_done and sec is None and l.startswith("| **"):
            in_meta = True
        if in_meta and not l.startswith("|"):
            if not any(re.match(r"^\|\s*\*\*Status\*\*", x) for x in out): out.append(f"| **Status** | {STATUS} |")
            in_meta = False; meta_done = True
        if l.startswith("## "):
            sec = l[3:].strip()
            if sec == "Claims ledger" and nothing:
                while out and not out[-1].strip(): out.pop()
                out += ["", "Units with nothing to row: " + "; ".join(f"{k} ({v or 'no claim'})" for k, v in sorted(nothing.items())), ""]
        out.append(l)
        # the header row and separator of the ledger and the audit: the rows go directly below
        if sec in ("Claims ledger", "Forthrightness audit") and LN.is_sep(l) and i > 0 and skel[i - 1].lstrip().startswith("| #"):
            out += ledger if sec == "Claims ledger" else audit
            sec = sec + " (filled)"
        i += 1
    text = "\n".join(out).rstrip("\n") + "\n"
    os.makedirs(os.path.dirname(note) or ".", exist_ok=True)
    LN.write_text(note, text)
    words = len(re.findall(r"\S+", text))
    return {"ok": True, "note": note, "claims_rows": len(ledger), "audit_rows": len(audit), "units": len(units),
            "nothing_to_row": sorted(nothing), "words": words,
            "summary": f"assembled {note}: {len(ledger)} claims rows, {len(audit)} audit rows from {len(units)} units' parts; nothing to row: {', '.join(sorted(nothing)) or 'none'}; {words} words"}


def main():
    a = sys.argv[1:]
    def opt(name):
        return a[a.index(name) + 1] if name in a else None
    if not opt("--wip") or not opt("--note"): sys.exit(__doc__)
    r = assemble(opt("--wip"), opt("--note"), opt("--nothing-to-row"))
    print(json.dumps(r) if "--json" in a else r["summary"])
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__": main()
