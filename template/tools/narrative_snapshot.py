#!/usr/bin/env python3
"""Snapshot narrative pages before a step so the next attacker can be given a row-level diff (owner 2026-10-09, token point 6).
Usage: python3 tools/narrative_snapshot.py <label> <page> [<page> ...]   -> research/tasks/tool-feedback/snapshots/<stem>.<label>.md
       python3 tools/narrative_snapshot.py --latest <page>               -> prints the newest snapshot path for that page"""
import sys, os, shutil, glob
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
D = "research/tasks/tool-feedback/snapshots"; os.makedirs(D, exist_ok=True)
if sys.argv[1] == "--latest":
    stem = os.path.basename(sys.argv[2])[:-3]; fs = sorted(glob.glob(f"{D}/{stem}.*.md"), key=os.path.getmtime); print(fs[-1] if fs else ""); sys.exit(0)
label = sys.argv[1]
for p in sys.argv[2:]:
    stem = os.path.basename(p)[:-3]; dest = f"{D}/{stem}.{label}.md"; shutil.copy2(p, dest); print(f"{p} -> {dest}")
