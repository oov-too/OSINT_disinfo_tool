"""`ledger acquire batch <list.toml>`: hold a list of sources through the acquire adapters in two stages, so no URL is fetched twice
(2026-10-22; the general part of wip/platform-phase6b/hold_pilot.py, phase 6b handoff 13).

    ledger acquire batch <list.toml> [fetch|hold|all] [--cache DIR] [--only id,id] [--list]
        fetch   every item's URL through the web adapter's rate gate (per host; the item's or the list's gap) into its own folder
                under the cache, with <name>.meta.json beside each file (URL, final URL, HTTP status, content type, bytes, SHA-256,
                fetch time); a file already cached is not fetched again
        hold    each item from the cached bytes through its adapter (web, document, canon; a thread is fetched by the thread adapter
                at hold time, through the same gate), into the hold root; every hold verified (base.verify_hold); one manifest row
                per item appended to the list's manifest; one line per event in the run log
        all     fetch, then hold (the default)
        --list  print the items and stop

The list (TOML; paths relative to the project root):

    [batch]
    hold_root = "sources/pilot"            # where the holds go (default: ledger.toml [acquire] hold_root, else sources)
    cache = "wip/<task>/cache"             # the fetch cache (or --cache)
    manifest = "wip/<task>/hold-manifest.tsv"
    log = "wip/<task>/hold-run.jsonl"      # default: beside the manifest
    state_dir = "wip/<task>/acquire-state" # the rate gates' lock and stamp files (default: the adapters' own, shared by sessions)
    gap = 10                               # seconds between requests to one host (default 10)

    [[item]]
    id = "p-cw-2009"                       # unique; names the cache folder and the manifest row
    kind = "web"                           # web | thread | document | canon
    url = "https://..."                    # or path = "<a local file>" (document, canon)
    title = "..."                          # optional (web: the page's own title when absent)
    date = "2009-05-11"                    # optional; with date_basis
    date_basis = "..."
    gap = 30                               # optional: this host's gap
    folder = "sources/pilot/web/..."       # optional: the hold folder (default: the adapter's name under the hold root)
    metadata = { circle = "the press" }    # optional: added to the record's metadata
    # document: identifier, author (string or list), venue, ocr = "auto" | "never" | "always"
    # thread: max_pages (default 50)
    # canon: text_id, scheme (a scheme name, a dict, or a scheme .json path), author; a PDF source is held with its pypdf text
    #        layer (the house per-page form) as the text the scheme cuts

Nothing here is domain-specific: what a site's pages link to, or how a pack names its folders, is the list's to say."""
import json, os, sys

from ledger import paths as LP
from ledger import notes as LN

KINDS = ("web", "thread", "document", "canon")


def _load(path):
    import tomllib
    with open(path, "rb") as f: d = tomllib.load(f)
    items = d.get("item") or []
    ids = [i.get("id") for i in items]
    probs = [f"item {k + 1}: no id" for k, i in enumerate(ids) if not i]
    probs += [f"id {i!r} given twice" for i in sorted({i for i in ids if i and ids.count(i) > 1})]
    for it in items:
        if it.get("kind") not in KINDS: probs.append(f"{it.get('id')}: kind {it.get('kind')!r} is not one of {', '.join(KINDS)}")
        if not (it.get("url") or it.get("path")): probs.append(f"{it.get('id')}: neither url nor path")
        if it.get("kind") in ("web", "thread") and not it.get("url"): probs.append(f"{it.get('id')}: a {it.get('kind')} item needs a url")
        if it.get("kind") == "canon" and not it.get("text_id"): probs.append(f"{it.get('id')}: a canon item needs a text_id")
    if probs: raise SystemExit("ledger acquire batch: " + "; ".join(probs))
    return d.get("batch") or {}, items


class Batch:
    def __init__(self, list_path, cache=None):
        from ledger.acquire import base as B
        self.B = B
        self.root = LP.root()
        self.conf, self.items = _load(list_path)
        at = lambda p: p if os.path.isabs(p) else os.path.join(self.root, p)
        c = cache or self.conf.get("cache")
        if not c: raise SystemExit("ledger acquire batch: no cache folder ([batch] cache or --cache)")
        self.cache = at(c)
        self.manifest = at(self.conf.get("manifest") or os.path.join(os.path.dirname(os.path.abspath(list_path)), "hold-manifest.tsv"))
        self.runlog = at(self.conf.get("log") or os.path.join(os.path.dirname(self.manifest), "hold-run.jsonl"))
        self.hold_root = self.conf.get("hold_root")
        self.state_dir = at(self.conf["state_dir"]) if self.conf.get("state_dir") else None
        self.gap = float(self.conf.get("gap", 10.0))
        self._web = {}

    # ------------------------------------------------------------------------------------------------ plumbing
    def log(self, **kw):
        kw["time"] = self.B.utc_now()
        os.makedirs(os.path.dirname(self.runlog), exist_ok=True)
        with LN.open_append(self.runlog) as f: f.write(json.dumps(kw, ensure_ascii=False) + "\n")
        print(json.dumps(kw, ensure_ascii=False), flush=True)

    def web(self, gap):
        from ledger.acquire import web as W
        if gap not in self._web:
            self._web[gap] = W.WebAdapter(root=self.root, gap=gap, hold_root=self.hold_root, state_dir=self.state_dir)
        return self._web[gap]

    def gap_of(self, it):
        return float(it.get("gap", self.gap))

    @staticmethod
    def cache_name(it):
        if it["kind"] == "web": return "page"
        import re, urllib.parse
        u = it.get("url") or ""
        base = urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(u).path.rstrip("/"))) or "download"
        stem, ext = os.path.splitext(base)
        return (re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")[:80] or "download") + re.sub(r"[^A-Za-z0-9.]", "", ext)[:10]

    def cached(self, it):
        p = os.path.join(self.cache, it["id"], self.cache_name(it))
        return (p, self.B.read_json(p + ".meta.json")) if os.path.isfile(p) and os.path.isfile(p + ".meta.json") else (None, None)

    @staticmethod
    def how(meta):
        return f"HTTP {meta['status']} response body of {meta['final']}, {meta['ctype']}, fetched {meta['fetched']} by {meta['tool']}"

    # ------------------------------------------------------------------------------------------------ fetch
    def fetch(self, it):
        if it["kind"] == "thread" or not it.get("url"): return "not fetched here" if it["kind"] == "thread" else "local file"
        p, meta = self.cached(it)
        if p: return "cached"
        w = self.web(self.gap_of(it))
        data, ctype, final, status = w.get(it["url"])
        d = os.path.join(self.cache, it["id"]); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, self.cache_name(it))
        with open(p, "wb") as f: f.write(data)
        meta = dict(url=it["url"], final=final, status=status, ctype=ctype, bytes=len(data), sha256=self.B.sha256(data),
                    fetched=self.B.utc_now(), gap=self.gap_of(it), tool=f"{w.tool} WebAdapter.get (RateGate {self.gap_of(it):g} s per host)")
        LN.write_text(p + ".meta.json", json.dumps(meta, indent=1) + "\n")
        self.log(event="fetched", item=it["id"], url=it["url"], status=status, ctype=ctype, bytes=len(data))
        return "fetched"

    # ------------------------------------------------------------------------------------------------ hold
    def source(self, it):
        """(local path, meta or None): the cached download, or the item's local path."""
        if it.get("url"):
            p, meta = self.cached(it)
            if not p: raise RuntimeError(f"{it['id']}: not in the cache; run the fetch stage first")
            return p, meta
        p = it["path"] if os.path.isabs(it["path"]) else os.path.join(self.root, it["path"])
        if not os.path.isfile(p): raise RuntimeError(f"{it['id']}: {it['path']} not found")
        return p, None

    def finish(self, ad, cap, it):
        if it.get("folder"): cap.folder = it["folder"]
        row = ad.hold(cap)
        ok = row.get("hold") and row.get("status") != "failed"
        row["verify"] = "; ".join(self.B.verify_hold(os.path.join(self.root, row["hold"]))) or "intact" if ok else "not held"
        return row

    def hold_web(self, it):
        p, meta = self.source(it)
        w = self.web(self.gap_of(it))
        cap = w._page_capture(it["url"], self.B.read_bytes(p), meta["ctype"], meta["final"], meta["status"], how=self.how(meta),
                              metadata=dict(it.get("metadata") or {}, fetched=meta["fetched"]), date=it.get("date"),
                              date_basis=it.get("date_basis"))
        if it.get("title"): cap.record.title = it["title"]
        return self.finish(w, cap, it)

    def hold_thread(self, it):
        w = self.web(self.gap_of(it))
        rows = w.thread(it["url"], max_pages=int(it.get("max_pages", 50)), title=it.get("title"), metadata=it.get("metadata"),
                        folder=it.get("folder"), date=it.get("date"), date_basis=it.get("date_basis"))
        row = rows[0]
        row["verify"] = ("; ".join(self.B.verify_hold(os.path.join(self.root, row["hold"]))) or "intact") if row.get("hold") and row.get("status") != "failed" else "not held"
        return row

    def hold_document(self, it):
        from ledger.acquire import document as D
        p, meta = self.source(it)
        d = D.DocumentAdapter(root=self.root, ocr=it.get("ocr", "auto"), allow_compile=False, hold_root=self.hold_root, state_dir=self.state_dir)
        cap = d.capture_file(p, title=it.get("title"), identifier=it.get("identifier"), date=it.get("date"), author=it.get("author"),
                             venue=it.get("venue"), provenance=(meta or {}).get("final") or it.get("url"), metadata=it.get("metadata"),
                             how=self.how(meta) if meta else None, date_basis=it.get("date_basis"))
        return self.finish(d, cap, it)

    def hold_canon(self, it):
        from ledger.acquire import canon as C, document as D
        p, meta = self.source(it)
        ca = C.CanonAdapter(root=self.root, hold_root=self.hold_root, state_dir=self.state_dir)
        scheme = it.get("scheme", "lines")
        if isinstance(scheme, str) and scheme.endswith(".json") and not os.path.isabs(scheme): scheme = os.path.join(self.root, scheme)
        kw = dict(title=it.get("title"), scheme=scheme, author=it.get("author"), date=it.get("date"), provenance=(meta or {}).get("final") or it.get("url"),
                  metadata=it.get("metadata"))
        if self.B.read_bytes(p)[:5] == b"%PDF-":
            import pypdf
            work = os.path.join(self.cache, it["id"] + "-work"); os.makedirs(work, exist_ok=True)
            src = os.path.join(work, "text-layer.txt")
            LN.write_text(src, self.B.lf(D.per_page_form(D.text_layer(p))) + "\n")
            cap = ca.capture_text(src, it["text_id"], input_path=p, tool=f"pypdf {pypdf.__version__} text layer (document.text_layer, per_page_form)",
                                  how="derived: the PDF's pypdf text layer in the house per-page form", **kw)
        else:
            cap = ca.capture_text(p, it["text_id"], how=self.how(meta) if meta else None, **kw)
        if meta:
            for f in cap.files:
                if f.role == "held": f.how = self.how(meta)
        return self.finish(ca, cap, it)

    def hold(self, it):
        row = {"web": self.hold_web, "thread": self.hold_thread, "document": self.hold_document, "canon": self.hold_canon}[it["kind"]](it)
        row["batch_id"] = it["id"]
        self.B.write_manifest([row], self.manifest)
        self.log(event="held", item=it["id"], hold=row.get("hold"), status=row.get("status"), files=row.get("files"), bytes=row.get("bytes"),
                 verify=row.get("verify"), note=row.get("note"))
        return row


def main(argv):
    """the batch of a list.toml: fetch to a cache through the rate gate, hold from the cache, verify, manifest"""
    a = list(argv)
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0 if a else 2
    def opt(f):
        if f in a: i = a.index(f); v = a[i + 1]; del a[i:i + 2]; return v
        return None
    cache = opt("--cache"); only = opt("--only"); show = "--list" in a
    if show: a.remove("--list")
    lst = a[0]; stage = a[1] if len(a) > 1 else "all"
    if stage not in ("fetch", "hold", "all"): print(f"ledger acquire batch: stage {stage!r}: fetch, hold or all", file=sys.stderr); return 2
    if not os.path.isfile(lst): print(f"ledger acquire batch: {lst} not found", file=sys.stderr); return 2
    if show:
        conf, items = _load(lst)
        for it in items: print(f"{it['id']:24} {it['kind']:9} {it.get('url') or it.get('path')}")
        return 0
    b = Batch(lst, cache)
    items = b.items
    if only:
        want = only.split(","); missing = [i for i in want if i not in {x["id"] for x in items}]
        if missing: print(f"ledger acquire batch: no item {', '.join(missing)}", file=sys.stderr); return 2
        items = [x for x in items if x["id"] in want]
    bad = 0
    for st in (("fetch", "hold") if stage == "all" else (stage,)):
        for it in items:
            try:
                if st == "fetch": b.fetch(it)
                else:
                    row = b.hold(it)
                    if row.get("status") == "failed" or row.get("verify") not in ("intact",): bad += 1
            except Exception as e:
                import traceback
                bad += 1
                b.log(event="error", item=it["id"], stage=st, error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
    print(f"ledger acquire batch: {len(items)} item(s), {bad} with a failure or an unverified hold; manifest {os.path.relpath(b.manifest, b.root)}, log {os.path.relpath(b.runlog, b.root)}")
    return 1 if bad else 0
