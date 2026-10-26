#!/usr/bin/env python3
"""List every document, record or report a speaker says exists, across the database, as corroboration targets.

Usage:
  python3 tools/claimed_documents.py              all claimed documents, named and unnamed, grouped by speaker
  python3 tools/claimed_documents.py --unnamed    only documents claimed but not named
  python3 tools/claimed_documents.py --speaker Lisle
  python3 tools/claimed_documents.py --video harbour-talks-vanecek-2020
Reads notes.db only (run tools/build_db.py first). A row counts as a claimed document when its chain ends in
(document) or (document, unnamed), or its Source class is read with a named document in the attribution.
"""
import sqlite3, sys, os, re
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
con = sqlite3.connect(os.path.join(ROOT, "notes.db"))
unnamed = "--unnamed" in sys.argv
spk = sys.argv[sys.argv.index("--speaker") + 1] if "--speaker" in sys.argv else None
vid = sys.argv[sys.argv.index("--video") + 1] if "--video" in sys.argv else None
q = """SELECT c.video, c.n, c.time, c.speaker, c.claim, c.attribution, c.chain FROM claims c
       WHERE (c.chain LIKE '%(document, unnamed)%' OR c.chain LIKE '%(document)%'
              OR (c.source_class = 'read' AND c.attribution != '' AND c.attribution NOT LIKE 'none stated%'))"""
p = []
if unnamed: q += " AND (c.chain LIKE '%(document, unnamed)%' OR c.attribution LIKE 'document claimed, not named%')"
if spk: q += " AND lower(c.speaker) LIKE ?"; p.append(f"%{spk.lower()}%")
if vid: q += " AND c.video = ?"; p.append(vid)
rows = con.execute(q + " ORDER BY c.speaker, c.video, c.n", p).fetchall()
by = {}
for r in rows: by.setdefault(r[3], []).append(r)
print(f"{len(rows)} claimed-document rows across {len(by)} speakers" + (" (unnamed only)" if unnamed else ""))
for speaker, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(f"\n== {speaker} ({len(rs)})")
    for video, n, t, _, claim, attr, chain in rs:
        tag = "UNNAMED" if ("unnamed" in chain or attr.startswith("document claimed")) else "named"
        print(f"  [{tag}] {video} #{n} {t}: {claim[:110]}")
        print(f"          {attr[:130]}")
