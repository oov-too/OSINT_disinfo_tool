"""Page rendering and OCR backends for the document adapter (phase 3 of tools/platform-plan.md, 2026-10-22; Portability).

Renderer (a PDF page to an image): PyMuPDF (`fitz`) when installed; else poppler's `pdftoppm` when on the PATH; else none, and
the document adapter records 'renderer missing' for every page that needed OCR. PyMuPDF replaces the old render_pdf.swift.

OCR backend, chosen by platform.system():
- Darwin: Apple Vision through the existing tools/ocr_vision.swift, compiled, never rewritten. The binary is looked for at
  $LEDGER_OCR_VISION_BIN, ledger.toml [acquire] ocr_vision_bin, tools/bin/ocr_vision, <project>/.ledger/bin/ocr_vision and
  /tmp/ocr (the build line in the tool's own header); `compile_vision()` builds it with that same line
  (`swiftc -O -o <dest> tools/ocr_vision.swift`) into <project>/.ledger/bin/ (the install step of the bundle on macOS).
- Linux, Windows (and Darwin when Vision is unavailable): Tesseract through pytesseract when installed, else the `tesseract`
  binary on the PATH ($LEDGER_TESSERACT_CMD overrides), language from $LEDGER_TESSERACT_LANG (default eng).

Both backends return the same thing: {image path: recognised text, one line per text line}, and the document adapter writes it in
the house per-page form (`--- page N ---`). `detect()` is stage 0's report: platform, renderer, backend and what is missing.
"""
import os, platform, re, shutil, subprocess, sys, tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VISION_SRC = os.path.join(TOOLS, "ocr_vision.swift")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".heic"}


def _config_value(root, key):
    try:
        import tomllib
        p = os.path.join(root, "ledger.toml")
        if os.path.isfile(p):
            with open(p, "rb") as f: return (tomllib.load(f).get("acquire") or {}).get(key)
    except Exception: pass
    return None


def _project_root():
    try:
        if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
        from ledger import paths as LP
        return LP.root()
    except Exception:
        return os.path.dirname(TOOLS)


# ============================================================================================================ renderer
def _pymupdf():
    """The PyMuPDF module (`pymupdf`, the name since 1.24; `fitz`, its older and now deprecated name), or None."""
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        pass
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import fitz
        return fitz
    except ImportError:
        return None


def renderer():
    """'pymupdf', 'pdftoppm' or None."""
    if _pymupdf() is not None: return "pymupdf"
    return "pdftoppm" if shutil.which("pdftoppm") else None


def renderer_label():
    """The renderer with its version, for a capture tool that names what ran."""
    m = _pymupdf()
    if m is not None: return f"PyMuPDF {getattr(m, 'VersionBind', None) or getattr(m, '__version__', '')}".strip()
    return "pdftoppm" if shutil.which("pdftoppm") else None


def render_pages(pdf, pages, out_dir, zoom=3.0):
    """Render 1-based `pages` of `pdf` to PNG files in out_dir at `zoom` x 72 dpi (3x, the render the held OCRs were made at).
    Returns {page: png path}; raises RuntimeError('renderer missing') when there is no renderer."""
    r = renderer(); out = {}
    if r is None: raise RuntimeError("renderer missing (install PyMuPDF: pip install pymupdf; or poppler's pdftoppm)")
    os.makedirs(out_dir, exist_ok=True)
    if r == "pymupdf":
        fitz = _pymupdf()
        doc = fitz.open(pdf)
        for p in pages:
            pix = doc[p - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            path = os.path.join(out_dir, f"page-{p:04d}.png"); pix.save(path); out[p] = path
        doc.close()
    else:
        dpi = str(int(72 * zoom))
        for p in pages:
            stem = os.path.join(out_dir, f"page-{p:04d}")
            subprocess.run(["pdftoppm", "-r", dpi, "-f", str(p), "-l", str(p), "-png", "-singlefile", pdf, stem], check=True, capture_output=True)
            out[p] = stem + ".png"
    return out


# ============================================================================================================ Apple Vision
def vision_candidates(root=None):
    root = root or _project_root()
    c = [os.environ.get("LEDGER_OCR_VISION_BIN"), _config_value(root, "ocr_vision_bin"), os.path.join(TOOLS, "bin", "ocr_vision"),
         os.path.join(root, ".ledger", "bin", "ocr_vision"), "/tmp/ocr"]
    return [x if os.path.isabs(x) else os.path.join(root, x) for x in c if x]


def vision_binary(root=None):
    for p in vision_candidates(root):
        if os.path.isfile(p) and os.access(p, os.X_OK): return p
    return None


def compile_vision(dest=None, root=None):
    """Build tools/ocr_vision.swift with its own build line into dest (default <project>/.ledger/bin/ocr_vision). macOS only."""
    if platform.system() != "Darwin": raise RuntimeError("Apple Vision is macOS only")
    if not shutil.which("swiftc"): raise RuntimeError("swiftc missing (install the Xcode command line tools)")
    dest = dest or os.path.join(root or _project_root(), ".ledger", "bin", "ocr_vision")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = subprocess.run(["swiftc", "-O", "-o", dest, VISION_SRC], capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("swiftc failed: " + (r.stderr.strip()[-400:] or "no message"))
    return dest


def parse_vision_output(stdout, images):
    """tools/ocr_vision.swift prints '=== <file name>' then one line per recognised text line; map back to the image paths."""
    by_name = {os.path.basename(p): p for p in images}; out = {p: "" for p in images}; cur = None; buf = []
    for line in stdout.split("\n"):
        m = re.match(r"^=== (.+)$", line)
        if m and m.group(1) in by_name:
            if cur: out[cur] = "\n".join(buf).rstrip("\n")
            cur = by_name[m.group(1)]; buf = []
        elif cur is not None:
            buf.append(line)
    if cur: out[cur] = "\n".join(buf).rstrip("\n")
    return out


def ocr_vision(images, binary):
    if len({os.path.basename(p) for p in images}) != len(images): raise ValueError("image file names must be distinct for the Vision tool")
    r = subprocess.run([binary] + list(images), capture_output=True, text=True)
    if r.returncode != 0 and not r.stdout: raise RuntimeError("ocr_vision failed: " + r.stderr.strip()[-300:])
    return parse_vision_output(r.stdout, images), r.stderr.strip()


# ============================================================================================================ Tesseract
def tesseract_kind():
    """'pytesseract', 'cli' or None."""
    try:
        import pytesseract  # noqa: F401
        if shutil.which(os.environ.get("LEDGER_TESSERACT_CMD") or "tesseract"): return "pytesseract"
    except ImportError:
        pass
    return "cli" if shutil.which(os.environ.get("LEDGER_TESSERACT_CMD") or "tesseract") else None


def ocr_tesseract(images, lang=None):
    lang = lang or os.environ.get("LEDGER_TESSERACT_LANG", "eng"); kind = tesseract_kind(); out = {}
    if kind is None: raise RuntimeError("tesseract missing (pip install pytesseract and the tesseract binary with its language data)")
    cmd = os.environ.get("LEDGER_TESSERACT_CMD") or "tesseract"
    if kind == "pytesseract":
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = shutil.which(cmd)
        for p in images: out[p] = _lines(pytesseract.image_to_string(Image.open(p), lang=lang))
    else:
        for p in images:
            r = subprocess.run([cmd, p, "stdout", "-l", lang], capture_output=True, text=True)
            if r.returncode != 0: raise RuntimeError("tesseract failed: " + r.stderr.strip()[-300:])
            out[p] = _lines(r.stdout)
    return out, ""


def _lines(text):
    """Tesseract's output in the Vision form: one line per text line, blank runs and trailing form feeds dropped."""
    return "\n".join(l.rstrip() for l in text.replace("\f", "").split("\n") if l.strip())


# ============================================================================================================ choice and report
def backend(root=None):
    """The OCR backend for this machine: ('vision', binary) on macOS when built; ('vision-compilable', None) on macOS when swiftc
    can build it; ('tesseract', kind); or (None, reason)."""
    if platform.system() == "Darwin":
        b = vision_binary(root)
        if b: return "vision", b
        if shutil.which("swiftc") and os.path.isfile(VISION_SRC): return "vision-compilable", None
    k = tesseract_kind()
    if k: return "tesseract", k
    return None, "no OCR backend: " + ("build tools/ocr_vision.swift (swiftc) or install tesseract" if platform.system() == "Darwin" else "install tesseract and pytesseract")


def ocr_images(images, root=None, allow_compile=True):
    """OCR image files with this machine's backend. Returns (texts {path: text}, backend name, note)."""
    name, detail = backend(root)
    if name == "vision-compilable" and allow_compile:
        detail = compile_vision(root=root); name = "vision"
    if name == "vision":
        texts, err = ocr_vision(images, detail); return texts, "vision (tools/ocr_vision.swift)", err
    if name == "tesseract":
        texts, err = ocr_tesseract(images); return texts, f"tesseract ({detail})", err
    raise RuntimeError(detail or "ocr backend missing")


def detect(root=None):
    """Stage 0's detection report for this machine."""
    name, detail = backend(root)
    rep = dict(platform=platform.system(), machine=platform.machine(), python=platform.python_version(),
               renderer=renderer() or "missing", ocr_backend=name or "missing", ocr_detail=detail,
               vision_source=os.path.isfile(VISION_SRC), vision_binary=vision_binary(root), swiftc=shutil.which("swiftc"),
               tesseract=tesseract_kind() or "missing")
    try:
        import pypdf; rep["pypdf"] = pypdf.__version__
    except ImportError:
        rep["pypdf"] = "missing"
    m = _pymupdf()
    rep["pymupdf"] = (getattr(m, "VersionBind", None) or getattr(m, "__version__", None) or "installed") if m is not None else "missing"
    missing = []
    if rep["pypdf"] == "missing": missing.append("pypdf (text layers)")
    if rep["renderer"] == "missing": missing.append("a PDF renderer (PyMuPDF, or poppler's pdftoppm) for scanned pages")
    if rep["ocr_backend"] == "missing": missing.append("an OCR backend")
    rep["missing"] = missing
    return rep


if __name__ == "__main__":
    import json
    rep = detect()
    if "--compile" in sys.argv and rep["ocr_backend"] == "vision-compilable": rep["compiled"] = compile_vision(); rep = dict(detect(), compiled=rep["compiled"])
    print(json.dumps(rep, indent=1))
