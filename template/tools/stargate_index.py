#!/usr/bin/env python3
"""Full-text index over a mirrored bulk archive (the pack's [tools.stargate_index]: the mirror folder, the database, the index
file and its columns; phase 7b, 2026-10-22). quality() is core: ledger.acquire.bulk and ledger.acquire.document import it.

Builds the pack's database: table docs (esdn, title, folder, date, pages, chars, ocr_quality = share of tokens that are plain
dictionary-looking words, a rough handwriting detector) and an FTS5 table over the text, with metadata from the index file.

  python3 tools/stargate_index.py --build [--index <index.xlsx>]
  python3 tools/stargate_index.py --search '"core sample"' [--limit 30]
  python3 tools/stargate_index.py --search 'core NEAR/5 sample' --min-quality 0.5
  python3 tools/stargate_index.py --terms SPILLWAY CORE CERTIFICATE   # title/folder/text hit counts per term

FTS5 query syntax: phrases in double quotes, AND/OR/NOT, NEAR/n, prefix*. Results show the document id, the index title, the
date, the OCR quality and a snippet. Handwritten pages OCR as garbage, so a low quality score means the scan must be read by eye.
"""
import argparse, os, re, sqlite3, sys, datetime
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
sys.path.insert(0, _T); import packload; _D = packload.tool_data("stargate_index")   # the pack's archive: folders and index columns
ALL = os.path.join(ROOT, _D["all"])
DB = os.path.join(ROOT, _D["db"])
_C = _D["columns"]   # the index file's columns: id, date, title, folder, pages, box
WORD = re.compile(r"[A-Za-z]{3,}")

def quality(text):
    toks = re.findall(r"\S+", text)
    if not toks: return 0.0
    good = sum(1 for t in toks if WORD.fullmatch(t.strip(".,;:()'\"")))
    return round(good / len(toks), 3)

def load_meta(index):
    import openpyxl
    ws = openpyxl.load_workbook(index, read_only=True).active
    hdr = None; meta = {}
    for row in ws.iter_rows(values_only=True):
        if hdr is None: hdr = row; continue
        r = dict(zip(hdr, row)); e = str(r.get(_C["id"]) or "").strip()
        if not e.startswith(_D["id_prefix"]): continue
        d = r.get(_C["date"])
        # the first archive's index swaps day and month where both fit; store the raw value and a best-guess ISO date
        if isinstance(d, datetime.datetime):
            iso = d.date().isoformat(); raw = d.strftime("%d/%m/%Y")
            if d.day <= 12: iso = datetime.date(d.year, d.day, d.month).isoformat() + "?"
        else:
            raw = str(d or ""); iso = ""
        meta[e] = (str(r.get(_C["title"]) or ""), str(r.get(_C["folder"]) or ""), raw, iso, r.get(_C["pages"]) or 0, str(r.get(_C["box"]) or ""))
    return meta

def build(index):
    meta = load_meta(index)
    if os.path.exists(DB): os.remove(DB)
    con = sqlite3.connect(DB); c = con.cursor()
    c.execute("CREATE TABLE docs(esdn TEXT PRIMARY KEY, title TEXT, folder TEXT, date_raw TEXT, date_iso TEXT, pages INT, box TEXT, chars INT, ocr_quality REAL)")
    c.execute("CREATE VIRTUAL TABLE fts USING fts5(esdn UNINDEXED, title, folder, text, tokenize='porter unicode61')")
    n = 0
    for f in sorted(os.listdir(ALL)):
        if not f.endswith(".txt"): continue
        e = f[:-4]; t = open(os.path.join(ALL, f), encoding="utf-8", errors="ignore").read()
        body = t.split("\n\n", 1)[1] if "\n\n" in t else t
        title, folder, raw, iso, pages, box = meta.get(e, ("", "", "", "", 0, ""))
        c.execute("INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?)", (e, title, folder, raw, iso, pages, box, len(body), quality(body)))
        c.execute("INSERT INTO fts VALUES(?,?,?,?)", (e, title, folder, body)); n += 1
    con.commit(); con.close(); print(f"indexed {n} documents into {DB}")

def search(q, limit, minq):
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT f.esdn, d.title, d.date_iso, d.pages, d.ocr_quality, snippet(fts, 3, '[', ']', ' … ', 18) FROM fts f JOIN docs d ON d.esdn=f.esdn WHERE fts MATCH ? AND d.ocr_quality >= ? ORDER BY bm25(fts) LIMIT ?", (q, minq, limit)).fetchall()
    total = con.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (q,)).fetchone()[0]
    print(f"{total} documents match; showing {len(rows)}")
    for e, t, d, p, ql, sn in rows:
        print(f"{e} | {d} | {p}pp | q={ql} | {t[:70]}\n    {' '.join(sn.split())[:300]}")

def terms(words):
    con = sqlite3.connect(DB)
    for w in words:
        tt = con.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (f'title:{w} OR folder:{w}',)).fetchone()[0]
        tx = con.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (f'text:{w}',)).fetchone()[0]
        print(f"{w:16} titles/folders={tt:5}  text={tx:5}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--build", action="store_true"); ap.add_argument("--index", default=os.path.join(ROOT, _D["index"]))
    ap.add_argument("--search"); ap.add_argument("--limit", type=int, default=30); ap.add_argument("--min-quality", type=float, default=0.0); ap.add_argument("--terms", nargs="*")
    a = ap.parse_args()
    if a.build: build(a.index)
    if a.search: search(a.search, a.limit, a.min_quality)
    if a.terms: terms(a.terms)
