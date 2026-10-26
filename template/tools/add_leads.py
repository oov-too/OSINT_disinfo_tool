#!/usr/bin/env python3
"""Append proposed leads from an agent report to the lead register with permanent numbers.
Usage: python3 tools/add_leads.py <report.json> --kind divergence --label "<who proposed>"
Each item needs lead; optional kind, sources, settles. 'Asked by' is the first linked note in sources, else the label.
Leads whose first 60 characters already appear in the register are skipped."""
import json, re, sys, os, datetime
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
rep = json.load(open(sys.argv[1], encoding="utf-8"))
kind = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "lead"
label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "agent report"
items = rep if isinstance(rep, list) else (rep.get("leads") or rep.get("proposed_leads") or [])
p = "research/leads-and-inferences.md"; s = LN.read_text(p)
n0 = max(LN.row_numbers(s)); n = n0
anchor = LN.row_match(s, n0).group(0); new = ""; today = datetime.date.today().isoformat()
for it in items:
    lead = str(it.get("lead", "")).strip()
    if not lead or lead[:60] in s: continue
    src = str(it.get("sources", "")); m = re.search(r"\[([^\]]+)\]\((\.\./(?:videos|books)/[^)]+\.md)\)", src)
    asked = f"note: [{m.group(1)}]({m.group(2)})" if m else label
    n += 1
    new += "| " + " | ".join([str(n), lead.replace("|", "/"), it.get("kind", kind), asked, (src + ("; " if src else "") + f"proposed by {label}").replace("|", "/"), str(it.get("settles", "unknown")).replace("|", "/"), "open", "", "", "", today]) + " |\n"
if new: s = s.replace(anchor, anchor + new, 1); LN.write_text(p, s)
print(f"leads added: {n - n0} (now {n})")
