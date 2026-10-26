#!/usr/bin/env python3
"""Pull a whole released collection from one bulk item of the Internet Archive (the pack's [tools.stargate_bulk]: the item's
URL, its zips, the index file and its columns, the header and the folders; phase 7b, 2026-10-22), extracting only each
document's own OCR .TXT into <out>/<id>.txt with a provenance header, and deleting each zip after extraction. Per-document
fetches from archive.org throttle after a few hundred requests; a few large downloads do not.

  python3 tools/stargate_bulk.py [--keep-zips] [--only <zip name> ...]
Documents that have no .TXT in the zips are listed in <out>/NO-TXT.tsv (fetch those with tools/stargate_mirror.py at a slow
rate, or read their PDFs).
"""
import argparse, os, sys, time, zipfile, io, json, urllib.request, urllib.error
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
import packload; _D = packload.tool_data("stargate_bulk")   # the pack's collection
OUT = os.path.join(ROOT, _D["out"])
SCRATCH = os.environ.get(_D["scratch_env"], os.path.join(ROOT, _D["scratch"]))
UA = _D["user_agent"]
ZIPS = list(_D["zips"])   # the item's zip files, in order
HEADER = _D["header"]   # the provenance lines above each text ({esdn}, {zipname}, {member}, {title}, {folder}, {pages})

def load_meta():
    import openpyxl
    ws = openpyxl.load_workbook(os.path.join(ROOT, _D["index"]), read_only=True).active
    hdr = None; meta = {}
    for row in ws.iter_rows(values_only=True):
        if hdr is None: hdr = row; continue
        r = dict(zip(hdr, row)); e = str(r.get(_D["id_column"]) or "").strip()
        if e.startswith(_D["id_prefix"]): meta[e] = (str(r.get(_D["title_column"]) or ""), str(r.get(_D["folder_column"]) or ""), r.get(_D["pages_column"]) or "")
    return meta

def download(name, dest):
    url = _D["url"].format(name=name)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            have = os.path.getsize(dest) if os.path.exists(dest) else 0
            if have: req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=300) as h, open(dest, "ab" if have else "wb") as f:
                while True:
                    chunk = h.read(1 << 20)
                    if not chunk: break
                    f.write(chunk)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 416:  # range past the end: the file is already complete
                return True
            print(f"  download error (HTTP {e.code}); retry in 60 s", flush=True); time.sleep(60)
        except Exception as e:
            print(f"  download error ({e}); retry in 60 s", flush=True); time.sleep(60)
    return False

def extract(zpath, name, meta, seen):
    n_txt = 0; n_docs = 0
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        docs = {}
        for m in names:
            base = os.path.basename(m); stem, ext = os.path.splitext(base)
            if stem.startswith(_D["id_prefix"]): docs.setdefault(stem, set()).add(ext.upper())
        for stem, exts in docs.items():
            n_docs += 1
            member = next((m for m in names if os.path.basename(m).upper() == stem.upper() + ".TXT"), None)
            if member is None:
                seen["notxt"].append((stem, name)); continue
            out = os.path.join(OUT, stem + ".txt")
            text = z.read(member).decode("utf-8", "ignore")
            title, folder, pages = meta.get(stem, ("", "", ""))
            with LN.open_write(LP.new_hold(out)) as f:
                f.write(HEADER.format(esdn=stem, zipname=name, member=member, title=title, folder=folder, pages=pages) + text)
            n_txt += 1
    return n_docs, n_txt

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--keep-zips", action="store_true"); ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True); os.makedirs(SCRATCH, exist_ok=True)
    meta = load_meta(); seen = {"notxt": []}
    done_path = os.path.join(SCRATCH, "done.json")
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    for name in (a.only or ZIPS):
        if name in done: print(f"{name}: done earlier ({done[name]})", flush=True); continue
        dest = os.path.join(SCRATCH, name)
        print(f"{name}: downloading", flush=True); t0 = time.time()
        if not download(name, dest): print(f"{name}: FAILED download", flush=True); continue
        try:
            n_docs, n_txt = extract(dest, name, meta, seen)
        except zipfile.BadZipFile:
            print(f"{name}: bad zip, removing for re-download", flush=True); os.remove(dest); continue
        done[name] = f"{n_docs} documents, {n_txt} with text, {int(time.time()-t0)} s"
        json.dump(done, open(done_path, "w"), indent=1)
        print(f"{name}: {done[name]}", flush=True)
        if not a.keep_zips: os.remove(dest)
    with open(os.path.join(OUT, "NO-TXT.tsv"), "a") as f:
        for stem, name in seen["notxt"]: f.write(f"{stem}\t{name}\n")
    print(f"finished; {len(seen['notxt'])} documents without a .TXT in this run (all/NO-TXT.tsv)", flush=True)

if __name__ == "__main__":
    main()
