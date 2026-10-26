#!/usr/bin/env python3
"""Mirror the OCR text of every document of a released collection from the Internet Archive (the pack's [tools.stargate_mirror]:
the index columns, the id prefix, the URL template, the header and the user agent; phase 7b, 2026-10-22). fetch() is core:
ledger.acquire.bulk imports it; the core bulk adapter (python3 tools/ledger/acquire/bulk.py mirror) is the general form.

Reads the collection's index (xlsx/xlsm), fetches the URL template for each id, sequentially, with a pause between requests and
backoff on errors, and writes <out>/<id>.txt. Resumable: existing non-empty files are skipped. Failures are logged to FAILED.tsv
and retried on the next run.

  python3 tools/stargate_mirror.py --index <index.xlsm> [--workers 16] [--pause 0] [--limit N]
Archive.org tolerates a few parallel fetches but throttles with 503 after a burst of a few hundred
(tested 2026-09-30: 16 workers stalled after ~280 documents; the block lifted within 40 s). Default is
4 workers with a shared 60 s cooldown on any 5xx; the YouTube 10-second rule is not needed here.
"""
import argparse, os, sys, time, urllib.request, urllib.error, csv, threading
import concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
import openpyxl
import packload; _D = packload.tool_data("stargate_mirror")   # the pack's collection: index columns, id prefix, URL, header, user agent

UA = _D["user_agent"]
HEADER = _D["header"]   # the provenance lines written above each mirrored text ({esdn}, {title}, {folder}, {pages})

COOLDOWN = {"until": 0.0}
COOL_LOCK = threading.Lock()

def fetch(url, tries=6):
    """Fetch with a shared cooldown: any 5xx (archive.org's throttle after a burst, which lifts within
    about a minute) makes every worker wait 60 s before its next request, then retry."""
    for i in range(tries):
        wait = COOLDOWN["until"] - time.time()
        if wait > 0: time.sleep(wait)
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(r, timeout=120) as h:
                return h.read(), None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "404"
            err = f"HTTP {e.code}"
            if e.code >= 500:
                with COOL_LOCK: COOLDOWN["until"] = max(COOLDOWN["until"], time.time() + 60)
        except Exception as e:
            err = str(e)[:80]; time.sleep(5)
    return None, err

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", default=_D["out"])
    ap.add_argument("--pause", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ws = openpyxl.load_workbook(a.index, read_only=True).active
    hdr = None; rows = []
    for row in ws.iter_rows(values_only=True):
        if hdr is None: hdr = row; continue
        r = dict(zip(hdr, row))
        e = str(r.get(_D["id_column"]) or "").strip()
        if e.startswith(_D["id_prefix"]): rows.append(r)
    failed_path = os.path.join(a.out, "FAILED.tsv")
    if os.path.exists(failed_path): os.remove(failed_path)
    todo = [r for r in rows if not (os.path.exists(os.path.join(a.out, r[_D["id_column"]].strip() + ".txt")) and os.path.getsize(os.path.join(a.out, r[_D["id_column"]].strip() + ".txt")) > 0)]
    if a.limit: todo = todo[:a.limit]
    print(f"{len(rows)} in index, {len(rows)-len(todo)} already held, {len(todo)} to fetch, workers={a.workers}", flush=True)
    lock = threading.Lock(); stats = {"done": 0, "failed": 0}
    def work(r):
        e = r[_D["id_column"]].strip(); out = os.path.join(a.out, e + ".txt")
        data, err = fetch(_D["url"].format(id=e))
        with lock:
            if data is None:
                stats["failed"] += 1
                with LN.open_append(failed_path) as f: f.write(f"{e}\t{err}\n")
            else:
                text = data.decode("utf-8", "ignore")
                with LN.open_write(LP.new_hold(out)) as f:
                    f.write(HEADER.format(esdn=e, title=r.get(_D["title_column"]), folder=r.get(_D["folder_column"]), pages=r.get(_D["pages_column"])) + text)
                stats["done"] += 1
            n = stats["done"] + stats["failed"]
            if n % 100 == 0: print(f"{n}/{len(todo)} fetched={stats['done']} failed={stats['failed']}", flush=True)
        if a.pause: time.sleep(a.pause)
    with cf.ThreadPoolExecutor(a.workers) as ex: list(ex.map(work, todo))
    print(f"finished: fetched={stats['done']} failed={stats['failed']} of {len(todo)} (rerun to retry failures)", flush=True)

if __name__ == "__main__":
    main()
