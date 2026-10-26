"""The bulk-archive adapter (phase 3 of tools/platform-plan.md, 2026-10-22): mirror every item of an archive release named by an
index file, and build a full-text index over the mirrored texts. Generalises tools/stargate_mirror.py (the mirror) and
tools/stargate_index.py (the index), importing their request and quality logic.

A set hold, not a folder per item (tools/hold-schema.md section 4):

    sources/archive/<set>/
        README.md       generated: the release, how it was mirrored, one row per item (identifier, title, date, file, bytes, SHA-256, URL)
        items.jsonl     the machine record: one line per item with its index metadata, file, bytes, SHA-256, URL, capture time
        items/<id>.<ext> each item's bytes exactly as served (no header prepended: the metadata lives in items.jsonl and the index)
        FAILED.tsv      items that failed this run (retried on the next; the file is rewritten per run)
        index.db        SQLite, local, never on a share: docs (id, title, date, venue, pages, chars, ocr_quality, meta JSON) and an
                        FTS5 table over title, venue and text (porter unicode61), as the first archive's index database has it

The index file names the items: .xlsx/.xlsm (openpyxl), .csv/.tsv, or .json (a list of objects); `id_column` holds the item id,
`id_filter` a regex an id must match (a run may keep only one agency's document numbers), and `columns` maps the hold fields title,
date, venue and pages to index columns. `url` is a template over the item's columns ({id} the identifier), e.g.
https://archive.org/download/{id}/{id}_djvu.txt; file:// templates work, so the tests mirror a local folder.

Requests: tools/stargate_mirror.py's fetch() (a shared 60 s cooldown for every worker on any 5xx, 404 not retried), with
`workers` threads (default 4, the tested ceiling for archive.org) and `pause` seconds after each item. The YouTube rule does not
apply here; a service with its own rule sets workers=1 and its gap as pause.

The first archive mirror predates the byte-for-byte rule: its files carry a four-line header the mirror wrote above the OCR text. This
adapter keeps headers out of held bytes; the existing mirror is unchanged (the alias table serves it under sources/archive/).

    python3 tools/ledger/acquire/bulk.py mirror --set NAME --index FILE --id-column COL --url TEMPLATE [--ext txt]
        [--id-filter REGEX] [--title-column C] [--date-column C] [--venue-column C] [--pages-column C] [--workers 4] [--pause 0.5]
        [--limit N] [--release "how the release is named"] [--root DIR]
    python3 tools/ledger/acquire/bulk.py index --set NAME [--root DIR]
    python3 tools/ledger/acquire/bulk.py search --set NAME 'query' [--limit 30] [--min-quality 0.5]
"""
import concurrent.futures as cf
import csv, importlib, json, os, re, sqlite3, sys, threading, time, urllib.error, urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B

SI = importlib.import_module("stargate_index")          # quality(): the plain-word share (a rough handwriting detector)
try:
    SM = importlib.import_module("stargate_mirror")      # fetch(): the shared-cooldown request (needs openpyxl at import)
    fetch = SM.fetch
except ImportError:                                      # openpyxl absent: the same request logic, without the tool's import
    SM = None
    _COOL = {"until": 0.0}; _COOL_LOCK = threading.Lock()

    def fetch(url, tries=6):
        err = None
        for i in range(tries):
            wait = _COOL["until"] - time.time()
            if wait > 0: time.sleep(wait)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ledger.acquire.bulk/1.0"}), timeout=120) as h:
                    return h.read(), None
            except urllib.error.HTTPError as e:
                if e.code == 404: return None, "404"
                err = f"HTTP {e.code}"
                if e.code >= 500:
                    with _COOL_LOCK: _COOL["until"] = max(_COOL["until"], time.time() + 60)
            except Exception as e:
                err = str(e)[:80]; time.sleep(5)
        return None, err


def read_index(path):
    """The rows of an index file as dicts (xlsx/xlsm, csv, tsv, json)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True).active; hdr = None; out = []
        for row in ws.iter_rows(values_only=True):
            if hdr is None: hdr = [str(h) if h is not None else "" for h in row]; continue
            out.append(dict(zip(hdr, row)))
        return out
    if ext in (".csv", ".tsv"):
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter="\t" if ext == ".tsv" else ","))
    if ext == ".json":
        return B.read_json(path)
    raise ValueError(f"{path}: an index is .xlsx, .xlsm, .csv, .tsv or .json")


def _plain(v):
    if v is None: return None
    if hasattr(v, "isoformat"): return v.isoformat()
    return v if isinstance(v, (int, float, bool)) else str(v)


class BulkArchiveAdapter(B.Adapter):
    name = "bulk"

    def __init__(self, set_name, root=None, **kw):
        super().__init__(root=root, **kw)
        self.set_name = B.safe_slug(set_name, 40)
        self.folder = f"{self.hold_root}/archive/{self.set_name}"
        self.afolder = self.abs(self.folder)
        self.items_dir = os.path.join(self.afolder, "items")
        self.jsonl = os.path.join(self.afolder, "items.jsonl")

    def item_name(self, ident, ext):
        """The item's file name: the id as the archive spells it when it meets the portability rules, else its compliant form."""
        name = f"{ident}.{ext}"
        if B.LP.name_problems(f"{self.folder}/items/{name}") and hasattr(B.LP, "hold_name"): name = B.LP.hold_name(name)
        return name

    def records(self):
        """{id: item record} from items.jsonl (the last line of an id wins)."""
        out = {}
        if os.path.isfile(self.jsonl):
            for line in B.LN.read_text(self.jsonl).split("\n"):
                if line.strip(): r = json.loads(line); out[r["identifier"]] = r
        return out

    # ---------------------------------------------------------------------------------------------------- mirror
    def mirror(self, index, id_column, url, ext="txt", id_filter=None, columns=None, workers=4, pause=0.5, limit=0, release=None):
        columns = columns or {}
        rows = []
        for r in read_index(index):
            ident = str(r.get(id_column) or "").strip()
            if not ident or (id_filter and not re.search(id_filter, ident)): continue
            rows.append((ident, {k: _plain(v) for k, v in r.items()}))
        os.makedirs(self.items_dir, exist_ok=True)
        held = self.records()
        failed_path = os.path.join(self.afolder, "FAILED.tsv")
        if os.path.exists(failed_path): os.remove(failed_path)
        todo = [(i, r) for i, r in rows if not (i in held and os.path.isfile(os.path.join(self.afolder, held[i]["file"])))]
        if limit: todo = todo[:limit]
        self.log(f"{len(rows)} in index, {len(rows) - len(todo)} already held, {len(todo)} to fetch, workers={workers}")
        lock = threading.Lock(); stats = {"done": 0, "failed": 0}; manifest = []

        def work(item):
            ident, r = item
            fmt = {re.sub(r"\W", "_", k): v for k, v in r.items() if k}; fmt["id"] = ident
            u = url.format(**fmt)
            data, err = fetch(u)
            with lock:
                if data is None:
                    stats["failed"] += 1
                    with B.LN.open_append(failed_path) as f: f.write(f"{ident}\t{err}\n")
                    manifest.append(dict(identifier=ident, media_kind="archive-item", hold=self.folder, status="failed", note=err, adapter=self.tool))
                else:
                    name = self.item_name(ident, ext); p = os.path.join(self.items_dir, name)
                    if os.path.exists(p) and B.file_sha256(p) != B.sha256(data):
                        stamp = B.utc_now().replace("-", "").replace(":", ""); stem, e = os.path.splitext(name); name = f"{stem}.{stamp}{e}"
                        p = os.path.join(self.items_dir, name)
                    if not os.path.exists(p):
                        with open(p, "wb") as f: f.write(data)
                    rec = dict(identifier=ident, media_kind="archive-item", file=f"items/{name}", bytes=len(data), sha256=B.sha256(data),
                               url=u, captured=B.utc_now(), tool=self.tool + (" via tools/stargate_mirror.py fetch()" if SM else ""),
                               title=_plain(r.get(columns.get("title"))) if columns.get("title") else None,
                               date=_plain(r.get(columns.get("date"))) if columns.get("date") else None,
                               venue=_plain(r.get(columns.get("venue"))) if columns.get("venue") else None,
                               pages=_plain(r.get(columns.get("pages"))) if columns.get("pages") else None, index_row=r)
                    with B.LN.open_append(self.jsonl) as f: f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    stats["done"] += 1
                    manifest.append(dict(identifier=ident, media_kind="archive-item", title=rec["title"], date=rec["date"], hold=self.folder,
                                         status="new", files=1, bytes=len(data), captured=rec["captured"], adapter=self.tool, note=rec["file"]))
                n = stats["done"] + stats["failed"]
                if n % 100 == 0: self.log(f"{n}/{len(todo)} fetched={stats['done']} failed={stats['failed']}")
            if pause: time.sleep(pause)

        if workers <= 1:
            for t in todo: work(t)
        else:
            with cf.ThreadPoolExecutor(workers) as ex: list(ex.map(work, todo))
        self.log(f"finished: fetched={stats['done']} failed={stats['failed']} of {len(todo)} (rerun to retry failures)")
        self.write_readme(release or f"Bulk mirror of the items named in {os.path.basename(index)}", index, id_column, url)
        return manifest

    def write_readme(self, release, index=None, id_column=None, url=None):
        recs = sorted(self.records().values(), key=lambda r: r["identifier"])
        intro = (f"{release}. Mirrored by {self.tool} from the item list in {index or 'the index file'} (column {id_column or 'id'}); "
                 f"each item fetched from {url or 'its URL'} and held byte-for-byte under items/ (no header added; the index metadata is in "
                 f"items.jsonl and index.db). {len(recs)} items held; failures of the last run in FAILED.tsv.")
        cols = ["Identifier", "Title", "Date", "File", "Bytes", "SHA-256", "Captured", "URL"]
        rows = [{"Identifier": r["identifier"], "Title": r.get("title"), "Date": r.get("date"), "File": r["file"], "Bytes": f"{r['bytes']:,}",
                 "SHA-256": r["sha256"], "Captured": r["captured"], "URL": r["url"]} for r in recs]
        B.LN.write_text(os.path.join(self.afolder, "README.md"), B.set_readme_text(f"Archive set: {self.set_name}", intro, cols, rows, self.tool))

    # ---------------------------------------------------------------------------------------------------- index
    def index(self):
        """Build index.db over the held items (stargate_index.py's tables, generalised). Returns the number indexed."""
        db = os.path.join(self.afolder, "index.db")
        if os.path.exists(db): os.remove(db)
        con = sqlite3.connect(db); c = con.cursor()
        c.execute("CREATE TABLE docs(id TEXT PRIMARY KEY, title TEXT, date TEXT, venue TEXT, pages TEXT, file TEXT, chars INT, ocr_quality REAL, meta TEXT)")
        c.execute("CREATE VIRTUAL TABLE fts USING fts5(id UNINDEXED, title, venue, text, tokenize='porter unicode61')")
        n = 0
        for r in sorted(self.records().values(), key=lambda r: r["identifier"]):
            p = os.path.join(self.afolder, r["file"])
            if not os.path.isfile(p): continue
            t = B.read_bytes(p).decode("utf-8", "ignore")
            c.execute("INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?)", (r["identifier"], r.get("title") or "", r.get("date") or "", r.get("venue") or "",
                                                                    str(r.get("pages") or ""), r["file"], len(t), SI.quality(t),
                                                                    json.dumps(r.get("index_row") or {}, ensure_ascii=False, sort_keys=True)))
            c.execute("INSERT INTO fts VALUES(?,?,?,?)", (r["identifier"], r.get("title") or "", r.get("venue") or "", t)); n += 1
        con.commit(); con.close()
        self.log(f"indexed {n} items into {self.rel(db)}")
        return n

    def search(self, q, limit=30, min_quality=0.0):
        con = sqlite3.connect(os.path.join(self.afolder, "index.db"))
        rows = con.execute("SELECT f.id, d.title, d.date, d.pages, d.ocr_quality, snippet(fts, 3, '[', ']', ' … ', 18) FROM fts f "
                           "JOIN docs d ON d.id=f.id WHERE fts MATCH ? AND d.ocr_quality >= ? ORDER BY bm25(fts) LIMIT ?", (q, min_quality, limit)).fetchall()
        total = con.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (q,)).fetchone()[0]
        con.close()
        return total, rows


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["mirror", "index", "search"]); ap.add_argument("query", nargs="?")
    ap.add_argument("--set", required=True); ap.add_argument("--index"); ap.add_argument("--id-column"); ap.add_argument("--url")
    ap.add_argument("--ext", default="txt"); ap.add_argument("--id-filter")
    for k in ("title", "date", "venue", "pages"): ap.add_argument(f"--{k}-column")
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--pause", type=float, default=0.5); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--release"); ap.add_argument("--min-quality", type=float, default=0.0); ap.add_argument("--root")
    a = ap.parse_args(argv)
    b = BulkArchiveAdapter(a.set, root=a.root)
    if a.cmd == "mirror":
        cols = {k: getattr(a, f"{k}_column") for k in ("title", "date", "venue", "pages") if getattr(a, f"{k}_column")}
        b.mirror(a.index, a.id_column, a.url, ext=a.ext, id_filter=a.id_filter, columns=cols, workers=a.workers, pause=a.pause,
                 limit=a.limit, release=a.release)
    elif a.cmd == "index":
        b.index()
    else:
        total, rows = b.search(a.query, a.limit or 30, a.min_quality)
        print(f"{total} items match; showing {len(rows)}")
        for i, t, d, p, q, sn in rows: print(f"{i} | {d} | {p}pp | q={q} | {t[:70]}\n    {' '.join(sn.split())[:300]}")


if __name__ == "__main__":
    main()
