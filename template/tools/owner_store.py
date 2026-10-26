#!/usr/bin/env python3
"""The owner's notes and investigations, kept in the project folder (owner, 2026-10-03).

Canonical local store: owner/notes.json and owner/investigations.json, each {id: document}, in the shapes the map writes
(research/figures/map/README.md). Readable mirrors are regenerated from them: owner/notes.md and owner/investigations/<id>-<slug>.md; owner/snapshots.json
(pictures inserted into investigations) is mirrored as owner/snapshots/<id>.jpg.
tools/build_db.py loads both JSON files into notes.db (tables owner_notes, owner_investigations).

Two routes feed the store:
  - the local map, when it is served by tools/map_server.py, saves straight into these files;
  - the published artifact keeps its own database; its documents are fetched with the ArtifactData tool (action list, out_dir <dir>)
    and merged here with `pull`.

Usage:
  python3 tools/owner_store.py pull <dir> [--mirror]   merge <dir>/notes/*.json and <dir>/investigations/*.json; the newer `updated` wins;
                                                       --mirror also removes local documents that are not in <dir> (use only after a full listing)
  python3 tools/owner_store.py export                  rewrite the markdown mirrors
  python3 tools/owner_store.py status                  counts and the newest document of each kind
"""
import json, os, re, sys, glob, datetime
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); OWN = os.path.join(ROOT, "owner")
KINDS = ("notes", "investigations", "snapshots")   # snapshots: pictures inserted into investigations, one document each ({img: data URL, caption, view, inv})
def path(kind): return os.path.join(OWN, kind + ".json")
def load(kind):
    try: return json.load(open(path(kind), encoding="utf-8"))
    except (OSError, ValueError): return {}
def save(kind, docs):
    os.makedirs(OWN, exist_ok=True); tmp = path(kind) + ".tmp"
    json.dump(docs, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False, sort_keys=True); os.replace(tmp, path(kind))
def slug(t): return re.sub(r"[^a-z0-9]+", "-", (t or "untitled").lower()).strip("-")[:60] or "untitled"
def links_md(links): return "; ".join(f"{l.get('t')}: {l.get('label') or l.get('id')}" for l in (links or []))
def export():
    notes = load("notes"); inv = load("investigations"); os.makedirs(os.path.join(OWN, "investigations"), exist_ok=True)
    L = ["# The owner's notes (mirror of owner/notes.json; regenerated, do not edit here)", "", f"{len(notes)} notes, exported {datetime.date.today().isoformat()}.", ""]
    for i, n in sorted(notes.items(), key=lambda x: x[1].get("updated", ""), reverse=True):
        L += [f"## {n.get('title') or 'Untitled note'}", "", f"- id: {i}", f"- tags: {', '.join(n.get('tags') or []) or 'none'}", f"- linked to: {links_md(n.get('links')) or 'nothing'}",
              f"- created {str(n.get('created',''))[:10]}, updated {str(n.get('updated',''))[:10]}", "", n.get("body") or "", ""]
    open(os.path.join(OWN, "notes.md"), "w", encoding="utf-8").write("\n".join(L))
    keep = set()
    for i, d in inv.items():
        name = f"{re.sub(r'[^A-Za-z0-9._-]+', '_', i)}-{slug(d.get('title'))}.md"; keep.add(name)
        head = [f"# {d.get('title') or 'Untitled investigation'}", "", "| | |", "|---|---|", f"| **Id** | {i} |", f"| **Origin** | {d.get('origin') or 'owner'} |"]
        if d.get("base"): head.append(f"| **Edit of** | {d.get('file') or d['base']} (the agent's page stays as written) |")
        head += [f"| **Created** | {str(d.get('created',''))[:10]} |", f"| **Updated** | {str(d.get('updated',''))[:10]} |", "", "> Mirror of owner/investigations.json, regenerated; edit on the map. Links of the form (ledger:kind:id) point into the ledger.", "", ""]
        open(os.path.join(OWN, "investigations", name), "w", encoding="utf-8").write("\n".join(head) + (d.get("body") or "") + "\n")
    for f in os.listdir(os.path.join(OWN, "investigations")):
        if f.endswith(".md") and f not in keep: os.remove(os.path.join(OWN, "investigations", f))
    snaps = load("snapshots"); sd = os.path.join(OWN, "snapshots"); os.makedirs(sd, exist_ok=True); keep = set()
    import base64
    for i, d in snaps.items():
        m = re.match(r"data:image/(jpeg|png);base64,(.*)$", d.get("img") or "", re.S)
        if not m: continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", i) + (".jpg" if m.group(1) == "jpeg" else ".png"); keep.add(name)
        fp = os.path.join(sd, name)
        if not os.path.exists(fp): open(fp, "wb").write(base64.b64decode(m.group(2)))
    for f in os.listdir(sd):
        if f not in keep: os.remove(os.path.join(sd, f))
    return len(notes), len(inv)
def doc_of(obj):
    """ArtifactData's saved files may wrap the document; accept {data: {...}}, {fields: {...}} or the bare document."""
    if isinstance(obj, dict):
        for k in ("data", "fields", "document"):
            if isinstance(obj.get(k), dict) and ("body" in obj[k] or "title" in obj[k]): return obj[k]
    return obj
def pull(src, mirror=False):
    out = {}
    for kind in KINDS:
        docs = load(kind); seen = set(); added = updated = 0; d = os.path.join(src, kind)
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            i = os.path.basename(f)[:-5]; seen.add(i)
            try: new = doc_of(json.load(open(f, encoding="utf-8")))
            except ValueError: continue
            if not isinstance(new, dict): continue
            new = {k: v for k, v in new.items() if not k.startswith("__")}
            cur = docs.get(i)
            if cur is None: docs[i] = new; added += 1
            elif str(new.get("updated", "")) > str(cur.get("updated", "")): docs[i] = new; updated += 1
        removed = 0
        if mirror and os.path.isdir(d):
            for i in [k for k in docs if k not in seen]: del docs[i]; removed += 1
        save(kind, docs); out[kind] = dict(total=len(docs), added=added, updated=updated, removed=removed)
    export(); return out
def status():
    for kind in KINDS:
        docs = load(kind); newest = max(docs.values(), key=lambda x: str(x.get("updated", "")), default=None)
        print(f"{kind}: {len(docs)}" + (f"; newest: {newest.get('title')!r}, updated {str(newest.get('updated',''))[:16]}" if newest else ""))
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    if a[0] == "pull" and len(a) >= 2: print(json.dumps(pull(a[1], "--mirror" in a)))
    elif a[0] == "export": print("notes %d, investigations %d" % export())
    elif a[0] == "status": status()
    else: sys.exit(__doc__)
