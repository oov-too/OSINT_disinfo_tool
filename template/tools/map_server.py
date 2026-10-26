#!/usr/bin/env python3
"""Serve the ledger's local map so that it saves into the project folder (owner, 2026-10-03).

  python3 tools/map_server.py [port]        default port 8770, bound to 127.0.0.1 only
  then open  http://127.0.0.1:8770/research/figures/map/database-map.html

Static files come from the project root. The map's notes and investigations are read and written through
  GET /api/store/<notes|investigations|snapshots>  -> owner/<kind>.json
  PUT /api/store/<notes|investigations|snapshots>  <- the whole {id: document} map; the markdown mirrors are regenerated
so nothing the owner writes on the local map stays only in the browser. Opened any other way (a plain file, another
server) the local map falls back to the browser's storage.
"""
import http.server, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owner_store
ROOT = owner_store.ROOT
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def _kind(self):
        p = self.path.split("?")[0]
        if p.startswith("/api/store/"):
            k = p[len("/api/store/"):]
            return k if k in owner_store.KINDS else ""
        return None
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8"); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        k = self._kind()
        if k is None: return super().do_GET()
        if not k: return self._json(404, {"error": "unknown store"})
        self._json(200, owner_store.load(k))
    def do_PUT(self):
        k = self._kind()
        if not k: return self._json(404, {"error": "unknown store"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20_000_000: return self._json(413, {"error": "too large"})
            docs = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(docs, dict) or not all(isinstance(v, dict) for v in docs.values()): raise ValueError("expected {id: document}")
        except (ValueError, UnicodeDecodeError) as e: return self._json(400, {"error": str(e)})
        owner_store.save(k, docs); owner_store.export(); self._json(200, {"saved": len(docs)})
    def end_headers(self):
        if not self.path.startswith("/api/"): self.send_header("Cache-Control", "no-cache")
        super().end_headers()
    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""): sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))
if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv: sys.exit(__doc__)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    print(f"{__import__('packload').ledger_title()} map: http://127.0.0.1:{port}/research/figures/map/database-map.html  (saving to {os.path.join(ROOT, 'owner')})")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
