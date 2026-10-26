#!/usr/bin/env python3
"""Apply the `## Leads returned` and `## Relations returned` tables of narrative pages (tools/narratives.md) to the registers.
Usage: python3 tools/narrative_apply.py research/narrative-synchrony-2009-2016.md [more pages] [--dry]
Leads: rows go through tools/add_leads.py's rules (permanent number, skip when the first 60 characters already exist); Asked by is the
page id (`page <stem>`), kind as given. Relations: appended to research/relations-register.md with the next number, skipped when the
same (a, b, kind, when) already sits in the register (7b2 item 15, 2026-10-23: the When cell is part of the key, so dated variants of one
edge are kept; tools/integrate_report.py add_relations keys on a, b and kind). Prints what it added.
After applying, the page's lead rows get their numbers filled in place, so the page and the register agree. Run build_db.py after.
"""
import re, sys, os, json, datetime, subprocess
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
DRY = "--dry" in sys.argv; pages = [a for a in sys.argv[1:] if a.endswith(".md")]
today = datetime.date.today().isoformat()
def table_rows(txt, heading, stop_re=r"^## "):
    body = LN.section_text_until(txt, heading, stop_re)   # form S4 with the caller's stop
    if body is None: return None, []
    return LN.loose_table(body, with_lines=True)          # form T2c
for p in pages:
    stem = os.path.basename(p)[:-3]; txt = LN.read_text(p)
    hdr, lrows = table_rows(txt, "Leads returned")
    items = []
    for line, r in lrows:
        if not r.get("lead"): continue
        if r.get("#", "").strip(): continue  # already numbered
        items.append({"lead": r["lead"], "kind": r.get("kind") or "lead", "sources": r.get("sources", ""), "settles": r.get("what would settle it", ""), "asked_by": f"page {stem}"})
    added_nums = []
    if items and not DRY:
        tmp = f"wip/narratives-apply-{stem}.json"; json.dump(items, LN.open_write(tmp), ensure_ascii=False)
        before = LN.read_text("research/leads-and-inferences.md")
        n0 = max(LN.row_numbers(before))
        out = subprocess.run([sys.executable, os.path.join(_T, "add_leads.py"), tmp, "--kind", "lead", "--label", f"page {stem}"], capture_output=True, text=True)
        print(p, "leads:", out.stdout.strip(), out.stderr.strip()[-300:])
        after = LN.read_text("research/leads-and-inferences.md")
        # fill the page's blank numbers by matching lead text prefixes against the register
        reg = {m.group(2)[:60]: m.group(1) for m in re.finditer(r"^\| (\d+) \| ([^|]*) \|", after, re.M)}
        new_txt = txt
        for line, r in lrows:
            if r.get("#", "").strip() or not r.get("lead"): continue
            num = reg.get(r["lead"][:60])
            if num:
                new_txt = new_txt.replace(line, re.sub(r"^\|\s*\|", f"| {num} |", line, count=1), 1); added_nums.append(num)  # blank first cell may be "|  |" or "| |" 
        if new_txt != txt: LN.write_text(p, new_txt); txt = new_txt
        os.remove(tmp)
    print(p, "lead rows:", len(items), "numbered on page:", len(added_nums))
    hdr, rrows = table_rows(txt, "Relations returned")
    rp = "research/relations-register.md"; rs = LN.read_text(rp)
    existing = set()
    for m in re.finditer(r"^\| \d+ \|[^\n]*", rs, re.M):   # # | A | B | Kind | Hierarchy | When | ...; cells split (an empty cell is `| |`)
        c = LN.split_row(m.group(0)) + [""] * 6
        existing.add((c[1], c[2], c[3], c[5]))
    n = max(LN.row_numbers(rs)); n0 = n; new = ""
    for line, r in rrows:
        a, b, kind, when = r.get("a", "").strip(), r.get("b", "").strip(), r.get("kind", "").strip(), r.get("when", "").strip()
        if not a or not b: continue
        key = (a, b, kind.replace("|", "/"), when)   # dated variants of one edge are distinct rows (7b2 item 15)
        if key in existing: continue
        n += 1; existing.add(key)
        src = r.get("source", "") or f"[{stem}](../research/{stem}.md)"
        new += "| " + " | ".join([str(n), a, b, kind.replace("|", "/"), r.get("hierarchy", ""), r.get("when", ""), r.get("what", ""), src, r.get("chain", ""), r.get("confidence", "") or "medium", today]) + " |\n"
    if new and not DRY:
        anchor = re.search(r"^\| " + str(n0) + r" \|[^\n]*\n", rs, re.M)
        rs = rs[:anchor.end()] + new + rs[anchor.end():]; LN.write_text(rp, rs)
    print(p, "relations added:", n - n0, "of", len(rrows))
