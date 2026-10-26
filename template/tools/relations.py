#!/usr/bin/env python3
"""Query the relations register in notes.db.

Usage:
  python3 tools/relations.py "Petra Vanecek"           edges of a person or organisation, then the two-hop neighbourhood
  python3 tools/relations.py "Calloway Ashdown Civil" --org      everyone tied to an organisation
  python3 tools/relations.py "Gareth Lisle" --kind employer
Matching resolves the term through tools/name_aliases.json to a canonical name and matches relations.a_canon / b_canon exactly; if nothing matches exactly it falls back to a case-insensitive substring on the canonical columns. Reads notes.db only (run tools/build_db.py first).
"""
import sqlite3, sys, os
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args: sys.exit(__doc__)
name = args[0]; kind = None
if "--kind" in sys.argv: kind = sys.argv[sys.argv.index("--kind") + 1]
con = sqlite3.connect(os.path.join(ROOT, "notes.db"))
import json, re
_ALIAS = {}
_ap = os.path.join(ROOT, "tools", "name_aliases.json")
if os.path.exists(_ap):
    for _k, _vs in json.load(open(_ap, encoding="utf-8")).items():
        if _k == "_comment": continue
        _ALIAS[_k.lower()] = _k
        for _v in _vs: _ALIAS[_v.lower()] = _k
def canon(term):
    t = re.sub(r"^(?:Dr\.?|Rep\.?|Col\.?|Colonel|Major|Gen\.?|Lt\.?|Adm\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+", "", term.strip(), flags=re.I)
    return _ALIAS.get(t.lower(), t)
def edges(term):
    c = canon(term)
    q = "SELECT n, a, b, kind, hierarchy, when_, what, source, chain, confidence, a_canon, b_canon FROM relations WHERE (a_canon = ? OR b_canon = ?)"
    p = [c, c]
    if kind: q += " AND lower(kind) = ?"; p.append(kind.lower())
    rows = con.execute(q + " ORDER BY n", p).fetchall()
    if not rows:
        q = "SELECT n, a, b, kind, hierarchy, when_, what, source, chain, confidence, a_canon, b_canon FROM relations WHERE (lower(a_canon) LIKE ? OR lower(b_canon) LIKE ?)"
        p = [f"%{c.lower()}%", f"%{c.lower()}%"]
        if kind: q += " AND lower(kind) = ?"; p.append(kind.lower())
        rows = con.execute(q + " ORDER BY n", p).fetchall()
    return [r for r in rows]
cname = canon(name)
first = edges(name)
print(f"{name} (canonical: {cname}): {len(first)} edge(s)")
for n, a, b, k, h, w, what, src, ch, conf, ac, bc in first:
    print(f"  #{n} {a} -> {b} [{k}{('; ' + h) if h.strip() else ''}; {w}; {conf}] {what[:120]}\n      source: {src[:100]} | chain: {ch[:80]}")
seen = {cname}; hop2 = []
firstn = {f[0] for f in first}
for n, a, b, k, h, w, what, src, ch, conf, ac, bc in first:
    for other in (ac, bc):
        if other in seen: continue
        seen.add(other)
        for e in edges(other):
            if e[0] not in firstn and e not in [h[1] for h in hop2]: hop2.append((other, e))
if hop2:
    print(f"two hops away ({len(hop2)}):")
    for via, (n, a, b, k, h, w, what, src, ch, conf, ac, bc) in hop2[:60]:
        print(f"  via {via}: #{n} {a} -> {b} [{k}; {w}; {conf}] {what[:90]}")
