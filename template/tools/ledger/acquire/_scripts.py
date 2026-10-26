"""Run one of the project's script-form tools as its own entry point with its writes redirected (phase 3, 2026-10-22).

Several existing fetchers do their work at module level (tools/fetch_kjv.py, fetch_tanakh.py, fetch_samaritan.py,
fetch_isaiah_scroll.py, fetch_description.py, fetch_video.py): importing them runs them, against fixed output paths among the held
sources. The acquire layer wraps their logic without editing them and without letting them touch a held file: the tool runs in a
child Python process (runpy, run_name "__main__", the argv it would get from a shell) in which

- ledger.paths.new_hold, the one function every tool calls before writing a new hold, returns a path in a staging folder with the
  same file name, so the tool's output lands there and the adapter holds it;
- ledger.notes' writers and the built-in open() refuse any write outside the staging folder (PermissionError), so a write the
  tool makes some other way fails loudly instead of landing in the project;
- with offline=True, sockets and urllib refuse to connect, so a test proves the run made no network call.

The redirected paths are reported in <staging>/.redirects.json and returned.
"""
import json, os, subprocess, sys

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOOTSTRAP = r'''
import builtins, json, os, runpy, sys
sys.dont_write_bytecode = True
cfg = json.loads(sys.argv[1])
staging = os.path.abspath(cfg["staging"]); sys.path.insert(0, cfg["tools"])
from ledger import paths as LP, notes as LN
redirects = []
def _inside(p):
    ap = os.path.abspath(p)
    return ap == staging or ap.startswith(staging + os.sep)
def new_hold(path, kind="file", fix=True):
    out = os.path.join(staging, os.path.basename(path)); redirects.append({"asked": str(path), "written": out}); return out
LP.new_hold = new_hold
_open = builtins.open
def guarded_open(file, mode="r", *a, **k):
    if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+") and not _inside(os.fsdecode(file)):
        raise PermissionError(f"write outside the staging folder refused: {file}")
    return _open(file, mode, *a, **k)
builtins.open = guarded_open
if cfg.get("offline"):
    import socket, urllib.request
    def refuse(*a, **k): raise ConnectionError("network refused: offline run (ledger.acquire._scripts)")
    socket.socket.connect = refuse; socket.create_connection = refuse; urllib.request.urlopen = refuse
sys.argv = [cfg["script"]] + cfg["args"]
os.chdir(cfg["cwd"])
try:
    runpy.run_path(cfg["script"], run_name="__main__")
finally:
    with _open(os.path.join(staging, ".redirects.json"), "w", encoding="utf-8", newline="\n") as f: json.dump(redirects, f, indent=1)
'''


def run_tool(script, args, staging, cwd=None, offline=False, timeout=3600, python=None):
    """Run tools/<script> with `args`, its new holds redirected into `staging`. Returns (returncode, stdout, stderr, redirects)."""
    path = script if os.path.isabs(script) else os.path.join(TOOLS, script)
    if not os.path.isfile(path): raise FileNotFoundError(path)
    os.makedirs(staging, exist_ok=True)
    cfg = dict(script=path, args=[str(a) for a in args], staging=os.path.abspath(staging), tools=TOOLS,
               cwd=os.path.abspath(cwd or os.path.dirname(TOOLS)), offline=offline)
    r = subprocess.run([python or sys.executable, "-c", BOOTSTRAP, json.dumps(cfg)], capture_output=True, text=True, timeout=timeout)
    rp = os.path.join(staging, ".redirects.json")
    redirects = []
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8") as f: redirects = json.load(f)
    return r.returncode, r.stdout, r.stderr, redirects
