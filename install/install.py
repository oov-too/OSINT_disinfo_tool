#!/usr/bin/env python3
"""Install check and offline install of the ledger bundle (written by tools/build_bundle.py). Nothing is fetched: every check is
local, and the wheels install with pip --no-index from this bundle only.

    python3 install/install.py                  check: OS, checksums, Python, Claude Code, Node, the OCR backend, transcription, test render
    python3 install/install.py --apply --project DIR
                                                the check, then: the project template laid into DIR (a file already there is never
                                                overwritten), a virtual environment DIR/.ledger/venv made with the standard library (no
                                                network) and the wheels installed into it (pip --no-index --find-links wheels), and on
                                                macOS the Vision OCR compiled into DIR/.ledger/bin
    python3 install/install.py --apply --system the wheels installed into the running Python instead of a project venv
    python3 install/install.py --write-checksums  recompute CHECKSUMS.sha256 after the administrator staged platform files
Exit 0 when nothing required is missing; 1 otherwise (the report says what to stage)."""
import argparse, filecmp, glob, hashlib, json, os, platform, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); BUNDLE = os.path.dirname(HERE)
OSNAME = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system(), platform.system().lower())


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def checksums(write=False):
    p = os.path.join(BUNDLE, "CHECKSUMS.sha256"); rows = []
    for dp, dns, fs in os.walk(BUNDLE):
        dns[:] = sorted(d for d in dns if d not in ("__pycache__",))
        for f in sorted(fs):
            fp = os.path.join(dp, f); rel = os.path.relpath(fp, BUNDLE).replace(os.sep, "/")
            if rel == "CHECKSUMS.sha256": continue
            rows.append((rel, sha256(fp)))
    if write:
        with open(p, "w", encoding="utf-8", newline="\n") as fh: fh.write("".join(f"{h}  {r}\n" for r, h in rows))
        return {"written": len(rows)}
    want = {}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if line.strip(): h, r = line.rstrip("\n").split("  ", 1); want[r] = h
    have = dict(rows)
    return {"files": len(want), "mismatch": sorted(r for r in want if have.get(r) != want[r]), "missing": sorted(r for r in want if r not in have),
            "unlisted": sorted(r for r in have if r not in want)}


def which_version(cmd, args=("--version",)):
    exe = shutil.which(cmd)
    if not exe: return None
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=20)
        return ((r.stdout or r.stderr).strip().splitlines() or ["?"])[0]
    except Exception as e:
        return f"present ({e.__class__.__name__})"


def lay_template(project):
    """The bundle's template/ copied into the project folder: a file not there is copied, an identical one counted, a different one
    left as it is and named (the project's own edits are never overwritten)."""
    src = os.path.join(BUNDLE, "template"); rep = {"copied": 0, "same": 0, "kept_different": []}
    for dp, dns, fs in os.walk(src):
        dns.sort()
        for f in sorted(fs):
            s = os.path.join(dp, f); rel = os.path.relpath(s, src); d = os.path.join(project, rel)
            if not os.path.exists(d):
                os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(s, d); rep["copied"] += 1
            elif filecmp.cmp(s, d, shallow=False): rep["same"] += 1
            else: rep["kept_different"].append(rel.replace(os.sep, "/"))
    return rep


def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if OSNAME == "windows" else os.path.join(venv, "bin", "python3")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--project"); ap.add_argument("--write-checksums", action="store_true")
    ap.add_argument("--system", action="store_true", help="with --apply: install the wheels into the running Python, not a project venv")
    a = ap.parse_args()
    if a.project: a.project = os.path.abspath(a.project)
    if a.write_checksums: print(json.dumps(checksums(write=True))); return 0
    rep = {"os": OSNAME, "platform": f"{platform.system()} {platform.release()} {platform.machine()}", "python": platform.python_version(),
           "python_ok": sys.version_info >= (3, 11), "missing": [], "notes": []}
    rep["checksums"] = checksums()
    if rep["checksums"]["mismatch"] or rep["checksums"]["missing"]: rep["missing"].append("the bundle's files do not match CHECKSUMS.sha256")
    if not rep["python_ok"]: rep["missing"].append("Python 3.11 or later")
    rep["claude_code"] = which_version("claude")
    if not rep["claude_code"]: rep["missing"].append("Claude Code (`claude` on PATH), staged by the administrator")
    rep["python3_on_path"] = bool(shutil.which("python3"))
    if not rep["python3_on_path"]: rep["missing"].append("`python3` on PATH (the plugin's hooks run python3)")
    rep["node"] = which_version("node")   # Claude Code's npm install needs Node 18 or later; its native installer needs none
    if not rep["node"]: rep["notes"].append("Node.js not found: needed only if Claude Code is installed through npm (the native installer needs none)")
    ms = os.environ.get("LEDGER_MANAGED_SETTINGS") or {"macos": "/Library/Application Support/ClaudeCode/managed-settings.json", "linux": "/etc/claude-code/managed-settings.json",
          "windows": "C:\\Program Files\\ClaudeCode\\managed-settings.json"}.get(OSNAME)   # $LEDGER_MANAGED_SETTINGS: a test file, as setup stage 0 reads it
    rep["managed_settings"] = {"path": ms, "present": bool(ms and os.path.isfile(ms)), "from": "LEDGER_MANAGED_SETTINGS" if os.environ.get("LEDGER_MANAGED_SETTINGS") else "the OS path"}
    if not rep["managed_settings"]["present"]: rep["missing"].append(f"the managed settings file at {ms} (managed-settings/{OSNAME}.json, edited)")
    # the package: importable straight from the wheel for the checks below (pure Python)
    whl = sorted(glob.glob(os.path.join(BUNDLE, "wheels", "ledger-*.whl")))
    rep["wheel"] = os.path.basename(whl[-1]) if whl else None
    if whl: sys.path.insert(0, whl[-1])
    try:
        import contextlib, io
        from ledger.acquire import ocr as O, transcribe as TR
        with contextlib.redirect_stdout(io.StringIO()):   # PyMuPDF 1.28 prints a deprecation line when imported as fitz
            rep["ocr"] = O.detect(a.project); rep["transcription"] = TR.detect(a.project)
    except Exception as e:
        rep["ocr"] = {"error": f"{e.__class__.__name__}: {e}"}; rep["missing"].append("the ledger package could not be imported from the wheel")
    # the OCR backend: Vision on macOS (compiled from the carried source), Tesseract elsewhere
    if OSNAME == "macos":
        src = os.path.join(BUNDLE, "platform", "macos", "ocr_vision.swift")
        rep["ocr_backend"] = "vision" if shutil.which("swiftc") and os.path.isfile(src) else ("tesseract" if shutil.which("tesseract") else "missing")
        if rep["ocr_backend"] == "vision" and not (a.apply and a.project): rep["notes"].append("Vision OCR: the source is compiled by --apply --project (until then the test render's OCR step has no binary)")
        if a.apply and a.project and rep["ocr_backend"] == "vision":
            dest = os.path.join(a.project, ".ledger", "bin"); os.makedirs(dest, exist_ok=True)
            r = subprocess.run(["swiftc", "-O", "-o", os.path.join(dest, "ocr_vision"), src], capture_output=True, text=True)
            rep["notes"].append("Vision OCR compiled into " + dest if r.returncode == 0 else "Vision compile failed: " + r.stderr[-400:])
    else:
        staged = glob.glob(os.path.join(BUNDLE, "platform", OSNAME, "tesseract", "tesseract*"))
        rep["ocr_backend"] = "tesseract" if (shutil.which("tesseract") or staged) else "missing"
        if staged and not shutil.which("tesseract"): rep["notes"].append(f"set LEDGER_TESSERACT_CMD={staged[0]}")
    if rep["ocr_backend"] == "missing": rep["missing"].append(f"an OCR backend (platform/{OSNAME}/MANIFEST.md)")
    if (rep.get("transcription") or {}).get("engine") == "missing": rep["notes"].append(f"no transcription engine: recordings wait until it is staged (platform/{OSNAME}/MANIFEST.md)")
    py = sys.executable
    if a.apply and a.project:
        rep["template"] = lay_template(a.project)
        if not a.system:   # a project venv from the standard library (venv and ensurepip carry pip; nothing is fetched)
            venv = os.path.join(a.project, ".ledger", "venv")
            if not os.path.isfile(venv_python(venv)):
                r = subprocess.run([sys.executable, "-m", "venv", venv], capture_output=True, text=True)
                if r.returncode != 0: rep["missing"].append("a virtual environment (python -m venv): " + (r.stderr or r.stdout)[-300:])
            if os.path.isfile(venv_python(venv)): py = venv_python(venv); rep["venv"] = venv
    if a.apply:
        if not whl: rep["missing"].append("wheels/ledger-*.whl")
        else:
            links = ["--no-index", "--find-links", os.path.join(BUNDLE, "wheels"), "--find-links", os.path.join(BUNDLE, "wheels", "deps")]
            r = subprocess.run([py, "-m", "pip", "install", *links, whl[-1]], capture_output=True, text=True)
            if r.returncode == 0:   # a re-install of the same version is a no-op for pip: the package is replaced from this bundle's wheel
                r = subprocess.run([py, "-m", "pip", "install", "--force-reinstall", "--no-deps", *links, whl[-1]], capture_output=True, text=True)
            rep["pip"] = "ledger installed" if r.returncode == 0 else ("ledger failed: " + (r.stderr or r.stdout)[-600:])
            # the dependencies one by one, so a wheel not staged for this platform is named and the rest still install
            req = os.path.join(BUNDLE, "wheels", "requirements.txt"); rep["deps"] = {}
            if os.path.isfile(req):
                for line in open(req, encoding="utf-8"):
                    spec = line.split("#")[0].strip()
                    if not spec: continue
                    r = subprocess.run([py, "-m", "pip", "install", *links, spec], capture_output=True, text=True)
                    rep["deps"][spec] = "installed" if r.returncode == 0 else "not staged for this platform (wheels/TO-STAGE.md)"
    # the test render: a one-page PDF, rendered and recognised (after --apply, by the interpreter it installed into, with what it
    # installed and compiled; the project's own tools/ first on the path when the template is laid)
    code = ("import json, sys; sys.path[:0] = [p for p in sys.argv[2:] if p]; from ledger import setup_stages as SU; "
            "import contextlib, io\nwith contextlib.redirect_stdout(io.StringIO()): r = SU.test_render(sys.argv[1], allow_compile=False)\nprint(json.dumps(r, default=str))")
    paths = [os.path.join(a.project, "tools")] if a.project and os.path.isdir(os.path.join(a.project, "tools")) else ([whl[-1]] if whl and py == sys.executable and not a.apply else [])
    try:
        r = subprocess.run([py, "-c", code, a.project or tempfile.gettempdir(), *paths], capture_output=True, text=True, timeout=300)
        rep["test_render"] = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {"error": (r.stderr or r.stdout)[-600:]}
    except Exception as e:
        rep["test_render"] = {"error": f"{e.__class__.__name__}: {e}"}
    rep["interpreter"] = py
    rep["next"] = ([f"use the project's interpreter: {py} (or put {os.path.dirname(py)} first on PATH)"] if a.apply and py != sys.executable else []) + [
                   f"install managed-settings/{OSNAME}.json (edited) at {ms}",
                   f"claude plugin marketplace add {BUNDLE}", "claude plugin install ledger@ledger-local",
                   "or, for a seed: CLAUDE_CODE_PLUGIN_CACHE_DIR=<seed> claude plugin marketplace add <bundle>; ... claude plugin install ledger@ledger-local; then CLAUDE_CODE_PLUGIN_SEED_DIR=<seed> on each machine",
                   "in the project folder: /ledger:setup (the administrator runs stage 0)"]
    out = os.path.join(a.project, ".ledger", "install-report.json") if a.project else None
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh: json.dump(rep, fh, indent=1)
    print(json.dumps(rep, indent=1, default=str))
    return 1 if rep["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
