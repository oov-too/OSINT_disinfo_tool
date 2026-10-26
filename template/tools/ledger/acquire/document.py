"""The document adapter (phase 3 of tools/platform-plan.md, 2026-10-22; follow-up 2 from the pilot's first live use,
wip/platform-phase6b/adapter-findings.md): a PDF or a scan, held byte-for-byte in <hold root>/document/<slug>/ (or a set folder)
with its text in the house per-page form and the README.

For a PDF:
1. the scan profile (finding 10): per page, whether a full-page image is drawn (an image XObject with the page's proportions and at
   least 600 pixels on its short side), the fonts, the text layer's length; for the document, the producer and creator and the
   text layer's origin: `born-digital` (text, no page images), `OCR text layer under page images` (the publisher's OCR, or anyone's
   but ours: the iText, OmniPage, Acrobat Paper Capture layers of the pilot's exhibits), `scan without a text layer`, or `mixed`;
2. the text layer: pypdf, every page, in the form the held text layers under books/sources/ have, held once: as `text.txt` when it
   is the reading text on every page (no page's text came from OCR), else as `text-layer.txt` beside `text.txt` (the metadata's
   `text_layer_file` names which; 7b2 item 19);
3. each page judged: `empty` (under 20 non-space characters); `index` (a transcript's word index: 30% or more of its tokens are
   page/line references, `12/3`, `[4]`, `(5)` or `12:3`, and no junk; finding 7), never sent to OCR; `garbled` (junk characters:
   replacement characters, `(cid:N)` codes, private-use or control characters over 1%; or, on a page image only, under 45% plain
   words, tools/stargate_index.py's measure); `low-words` (a born-digital page with few plain words and no junk: a table, a list of
   names; kept, not sent to OCR, since OCR of a born-digital page can only be worse); or `good`;
4. OCR (ocr.py: PyMuPDF or pdftoppm to render at 3x; Apple Vision on macOS through tools/ocr_vision.swift, Tesseract elsewhere):
   the pages that need it (garbled, or an empty page image) are OCRed and their OCR becomes the reading text; and the pages whose
   text layer is someone else's OCR are OCRed as a second witness (`witness`, default on when a renderer and a backend are
   present): the witness goes to `ocr.txt` beside the text layer, the reading text stays the text layer, and `witness.json`
   compares the two word by word (agreement per page, the words that differ), so the verbatim gate can see where a quotation rests
   on a word only one witness reads;
5. `text.txt` (the reading copy, the record's `text`), `pages.tsv` (per page: verdict, quality, junk, image, the source of the reading text, the
   witness's agreement).
The capture tool names only what ran (pypdf with its version; the renderer and OCR backend only when they ran, finding 15); the
machine's renderer and OCR availability are in the `machine` metadata key.

For an image scan (png, jpg, webp, tif): OCR directly (no render), one page; the OCR is the reading text, held once as `text.txt`
(the metadata's `ocr_file`).

By URL (finding 5): `fetch_url(url)` fetches through the web adapter (its robots policy, user agent and gate) and holds the
response bytes with `how` = the HTTP response line and `provenance` = the URL; `fetch_page(page_url, rules=...)` (finding 16) holds
a catalogue's landing page with its attachments as one item, the page's fields read by a small rule file (JSON: `attachments`, a
regex for the links to fetch; `fields`, {name: regex with one group} over the page's HTML; `title`, `date`, `identifier` among them).
`link_over=N` (finding 17) holds a PDF larger than N bytes fetched by URL by link: its URL, size and SHA-256 recorded, the bytes not
stored, the text layer and the rest held.

    python3 tools/ledger/acquire/document.py <file.pdf|image> [--title T] [--date YYYY-MM-DD] [--author A] [--venue V]
        [--provenance URL] [--set NAME] [--ocr auto|never|always] [--no-witness] [--root DIR] [--hold-root DIR]
    python3 tools/ledger/acquire/document.py --url URL [...]          fetch the PDF through the web adapter, then as above
    python3 tools/ledger/acquire/document.py --page URL --rules FILE   a landing page and its attachments as one item
    python3 tools/ledger/acquire/document.py --detect                  the renderer and OCR backend of this machine
"""
import difflib, importlib, json, os, re, sys, tempfile, urllib.parse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B
from ledger.acquire import ocr as O

SI = importlib.import_module("stargate_index")    # tools/stargate_index.py: quality(), the plain-word share
MIN_CHARS = 20
MIN_QUALITY = 0.45
MAX_JUNK = 0.01
INDEX_SHARE = 0.30
OCR_BATCH = 16                                    # pages rendered and OCRed at a time (a 400-page judgment never sits rendered whole)
REF_TOKEN = re.compile(r"^(\d+/\d+|\[\d+\]|\(\d+\)|\d+:\d+)[,;.]?$")
JUNK_RE = re.compile(r"[�-\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _quiet_pypdf():
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)   # pypdf's font-map warnings ("odd-length line") are noise, not failures


def text_layer(pdf):
    """The pypdf text of every page (a page with no text gives "")."""
    import pypdf
    _quiet_pypdf()
    r = pypdf.PdfReader(pdf)
    return [(pg.extract_text() or "") for pg in r.pages]


def per_page_form(pages, sep="\n\n"):
    """The house per-page form: {page number: text} or a list (pages 1..n) -> `--- page N ---` blocks, no trailing newline.
    Two joins are held in the first project's document sets (measured 2026-10-22, pypdf 6.19): a blank line between pages (one
    release's files, the default here) and a single newline (an earlier release's files, made on another day); both are
    reproduced exactly by pypdf's text with the matching `sep`."""
    items = pages.items() if isinstance(pages, dict) else enumerate(pages, 1)
    return sep.join(f"--- page {n} ---\n{t}" for n, t in items)


def parse_per_page(text, sep="\n\n"):
    """{page: text} from the house per-page form written with `sep`."""
    out = {}; parts = re.split(r"(?m)^--- page (\d+) ---\n", text)
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out[int(parts[i])] = body[:-len(sep)] if i + 2 < len(parts) and body.endswith(sep) else body
    return out


# ============================================================================================================ the scan profile (finding 10)
def _images(xobjects, depth=0):
    out = []
    for k in list(xobjects.keys()) if xobjects else []:
        try: o = xobjects[k].get_object()
        except Exception: continue
        st = o.get("/Subtype")
        if st == "/Image": out.append((int(o.get("/Width") or 0), int(o.get("/Height") or 0)))
        elif st == "/Form" and depth < 2:
            res = o.get("/Resources") or {}
            out += _images((res.get("/XObject") or {}), depth + 1)
    return out


def _image_coverage(pdf):
    """Per page, the share of the page's area covered by its largest drawn image (PyMuPDF's image bounding boxes), or None when
    PyMuPDF is not installed or cannot read the file."""
    fitz = O._pymupdf()
    if fitz is None: return None
    try:
        doc = fitz.open(pdf); out = []
        for page in doc:
            area = abs(page.rect) or 1.0; best = 0.0
            for info in page.get_image_info():
                bb = fitz.Rect(info.get("bbox")) & page.rect
                best = max(best, abs(bb) / area)
            out.append(round(best, 3))
        doc.close()
        return out
    except Exception:
        return None


def scan_profile(pdf, layer=None):
    """{producer, creator, pages, pages_with_image, pages_with_text, fonts_seen, origin, per_page: [{image, fonts, text_chars}]}."""
    import pypdf
    _quiet_pypdf()
    r = pypdf.PdfReader(pdf); md = r.metadata or {}
    layer = layer if layer is not None else [(pg.extract_text() or "") for pg in r.pages]
    coverage = _image_coverage(pdf)                  # PyMuPDF: the share of each page the largest drawn image covers
    per = []
    for i, pg in enumerate(r.pages):
        res = pg.get("/Resources") or {}
        try: imgs = _images(res.get("/XObject") or {})
        except Exception: imgs = []
        w, h = float(pg.mediabox.width or 1), float(pg.mediabox.height or 1)
        page_ar = max(w, h) / max(1.0, min(w, h))
        if coverage is not None and i < len(coverage):
            full = coverage[i] >= 0.8                     # an image drawn over 80% or more of the page: a page image
        else:                                             # pypdf only: a large image of about the page's proportions (an A4 scan on a
            full = any(min(iw, ih) >= 600 and abs(max(iw, ih) / max(1, min(iw, ih)) - page_ar) / page_ar < 0.15 for iw, ih in imgs)   # Letter page is 11% off)
        try: fonts = len((res.get("/Font") or {}).keys())
        except Exception: fonts = 0
        per.append(dict(image=full, images=len(imgs), fonts=fonts, text_chars=len(re.sub(r"\s", "", layer[i] if i < len(layer) else ""))))
    n = len(per) or 1
    wi = sum(p["image"] for p in per); wt = sum(p["text_chars"] >= MIN_CHARS for p in per)
    both = sum(p["image"] and p["text_chars"] >= MIN_CHARS for p in per)
    if both >= 0.5 * n: origin = "OCR text layer under page images"
    elif wi >= 0.5 * n and wt < 0.1 * n: origin = "scan without a text layer"
    elif wi == 0 and wt: origin = "born-digital"
    elif not wt and not wi: origin = "no text and no page images"
    else: origin = "mixed"
    return dict(producer=str(md.get("/Producer") or "") or None, creator=str(md.get("/Creator") or "") or None, pages=len(per),
                pages_with_image=wi, pages_with_text=wt, origin=origin, per_page=per)


# ============================================================================================================ the page verdict (finding 7)
def judge(text, image_page=True):
    """(verdict, quality, junk share) of one page's text layer: empty, index, garbled, low-words or good (module docstring).
    image_page: the page is a page image (a scan); for a born-digital page (image_page=False) a low word share alone is not
    garbling. The default keeps the first turn's behaviour for callers that do not know the page's profile."""
    s = text.strip()
    if len(re.sub(r"\s", "", s)) < MIN_CHARS: return "empty", 0.0, 0.0
    q = SI.quality(s)
    junk = (len(JUNK_RE.findall(s)) + 4 * len(re.findall(r"\(cid:\d+\)", s))) / max(1, len(s))
    toks = s.split()
    refs = sum(bool(REF_TOKEN.match(t)) for t in toks) / max(1, len(toks))
    if refs >= INDEX_SHARE and junk == 0: return "index", q, round(junk, 4)
    if junk > MAX_JUNK: return "garbled", q, round(junk, 4)
    if q < MIN_QUALITY: return ("garbled" if image_page else "low-words"), q, round(junk, 4)
    return "good", q, round(junk, 4)


# ============================================================================================================ the witness comparison
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*")


def _words(t):
    return [w.strip(".-'’").lower() for w in WORD_RE.findall(t or "") if w.strip(".-'’")]


def compare_witnesses(layer, ocr):
    """Word-by-word comparison of two readings of one page: agreement (difflib ratio over the word lists), the words in each
    reading not matched in the other, and up to 40 one-for-one substitutions (layer word, OCR word), the class of error a quotation
    carries silently ('Fuiitsu' for 'Fujitsu')."""
    a, b = _words(layer), _words(ocr)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    subs = []; only_a = only_b = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal": continue
        only_a += i2 - i1; only_b += j2 - j1
        if op == "replace" and i2 - i1 == j2 - j1:
            subs += [(a[i1 + k], b[j1 + k]) for k in range(i2 - i1)]
    return dict(agreement=round(sm.ratio(), 4), layer_words=len(a), ocr_words=len(b), layer_only=only_a, ocr_only=only_b,
                substitutions=subs[:40], substitution_count=len(subs))


class DocumentAdapter(B.Adapter):
    name = "document"

    def __init__(self, root=None, ocr="auto", set_name=None, allow_compile=True, witness=True, link_over=None, **kw):
        super().__init__(root=root, **kw)
        if ocr not in ("auto", "never", "always"): raise ValueError("ocr: auto, never or always")
        self.ocr_mode = ocr; self.set_name = set_name; self.allow_compile = allow_compile
        self.witness = witness; self.link_over = link_over

    def _folder(self, ident, title, date):
        """<hold root>/document/[<set>/]<date>-<identifier>[-<title>]: the date first when known, as the web sets name their files."""
        kind = "document/" + B.safe_slug(self.set_name, 40) if self.set_name else "document"
        name = (date + " " if date else "") + B.safe_slug(ident, 40)
        return self.hold_path(kind, name, title if title and title != ident else "")

    def machine(self):
        name, detail = O.backend(self.root)
        return {"renderer": O.renderer_label() or "missing", "ocr_backend": name or "missing", "checked": B.utc_now()}

    def _ocr_pages(self, pdf, pages):
        """{page: text} for 1-based pages, rendered and OCRed OCR_BATCH at a time; (texts, label, error)."""
        texts = {}; label = None
        for k in range(0, len(pages), OCR_BATCH):
            batch = pages[k:k + OCR_BATCH]
            with tempfile.TemporaryDirectory() as tmp:
                try: imgs = O.render_pages(pdf, batch, tmp)
                except RuntimeError as e: return texts, label, f"renderer missing: {e}"
                got, lab, err = self._ocr(imgs.values())
                if err: return texts, label, err
                label = lab
                for p, img in imgs.items(): texts[p] = got.get(img, "")
        return texts, label, None

    def _ocr(self, images):
        """{path: text}, backend label, or the error when it failed."""
        try:
            texts, label, err = O.ocr_images(list(images), root=self.root, allow_compile=self.allow_compile)
            return texts, label, None
        except RuntimeError as e:
            return {}, None, ("ocr backend missing: " if "missing" in str(e) or "no OCR" in str(e) else "ocr failed: ") + str(e)

    def capture_file(self, path, title=None, identifier=None, date=None, author=None, venue=None, provenance=None, metadata=None,
                     how=None, link=None, date_basis=None):
        """The Capture of a local PDF or image. `how` (the held file's), `link` (the URL a large file is held by when link_over is set)."""
        import pypdf
        ap = self.abs(path); base = os.path.basename(ap); stem, ext = os.path.splitext(base); ext = ext.lower()
        data = B.read_bytes(ap)
        held_name = base if len(base) <= B.INNER_NAME_CAP and not B.LP.name_problems(base) else ("source" + ext)
        how = how or f"copied byte-for-byte from {self.rel(ap) if ap.startswith(self.root + os.sep) else ap}"
        if link and self.link_over is not None and len(data) > self.link_over:
            files = [B.HeldFile(held_name, data=data, role="linked", link=link, how=how + f"; held by link ({len(data):,} bytes over the {self.link_over:,} threshold)")]
        else:
            files = [B.HeldFile(held_name, data=data, how=how)]
        rows = []; md = dict(metadata or {}); notes = []; ran = [f"pypdf {pypdf.__version__}"] if ext == ".pdf" or data[:5] == b"%PDF-" else []
        if ext == ".pdf" or data[:5] == b"%PDF-":
            layer = text_layer(ap)
            prof = scan_profile(ap, layer)
            md.update(pdf_producer=prof["producer"], pdf_creator=prof["creator"], pages_with_image=prof["pages_with_image"],
                      text_layer_origin=prof["origin"] + (f" (producer {prof['producer']})" if prof["origin"].startswith("OCR") and prof["producer"] else ""))
            layer_tool = (f"pypdf {pypdf.__version__} (PdfReader, extract_text per page)"
                          + ("; the text layer is someone else's OCR under page images" if prof["origin"].startswith("OCR") else ""))
            need = []; witness_pages = []
            for n, t in enumerate(layer, 1):
                img = prof["per_page"][n - 1]["image"]
                verdict, q, junk = judge(t, image_page=img)
                rows.append(dict(page=n, text_layer_chars=len(t), quality=q, junk=junk, verdict=verdict, image="yes" if img else "no",
                                 source="text layer" + (" (someone else's OCR)" if img and verdict not in ("empty",) else "")))
                needs = self.ocr_mode == "always" or (self.ocr_mode == "auto" and (verdict == "garbled" or (verdict == "empty" and img)))
                if needs: need.append(n)
                elif img and verdict in ("good", "low-words", "index") and self.witness and self.ocr_mode != "never": witness_pages.append(n)
            md["page_verdicts"] = ", ".join(f"{k} {v}" for k, v in sorted({r['verdict']: sum(1 for x in rows if x['verdict'] == r['verdict']) for r in rows}.items()))
            ocr_text = {}; witness_text = {}
            backend = O.backend(self.root)[0]
            can_witness = O.renderer() is not None and (backend in ("vision", "tesseract") or (backend == "vision-compilable" and self.allow_compile))
            todo = need + (witness_pages if can_witness else [])
            if witness_pages and not can_witness:
                notes.append(f"{len(witness_pages)} page{'s' if len(witness_pages) != 1 else ''} carry someone else's OCR; no second witness "
                             f"(renderer {O.renderer() or 'missing'}, OCR backend {O.backend(self.root)[0] or 'missing'})")
            if todo:
                got, label, err = self._ocr_pages(ap, sorted(todo))
                for p in sorted(todo):
                    r = rows[p - 1]
                    if p in got:
                        if p in need: ocr_text[p] = got[p]; r["source"] = f"ocr: {label}"; r["ocr_chars"] = len(got[p])
                        else: witness_text[p] = got[p]; r["witness"] = f"ocr: {label}"; r["ocr_chars"] = len(got[p])
                    elif err and p in need: r["source"] = err.split(":")[0]
                if err: notes.append(f"{len([p for p in todo if p not in got])} page{'s' if len(todo) != 1 else ''} not OCRed: {err}")
                if got:
                    ran.append(f"rendered by {O.renderer_label()} at 3x (216 dpi)"); ran.append(f"OCR {label}")
                    md["ocr_backend"] = label
            # no page's reading text came from OCR: the reading text is the text layer, held once (item 19 of the 7b2 pilot report:
            # two byte-identical files made a word count over a hold count the text twice). text.txt keeps the name every reader
            # takes (record.text); the metadata's text_layer_file names the file that holds the text layer.
            layer_once = all(ocr_text[p] == layer[p - 1] for p in ocr_text)
            md["text_layer_file"] = "text.txt" if layer_once else "text-layer.txt"
            allocr = dict(sorted({**witness_text, **ocr_text}.items()))
            if allocr:
                files.append(B.HeldFile("ocr.txt", text=per_page_form(allocr), role="derived", derived_from=held_name,
                                        tool=f"{md.get('ocr_backend')} on pages rendered by {O.renderer_label()} at 3x"
                                             + ("; the pages with someone else's OCR as a second witness" if witness_text else "")))
            if witness_text:
                cmp = {p: compare_witnesses(layer[p - 1], witness_text[p]) for p in sorted(witness_text)}
                for p, c in cmp.items(): rows[p - 1]["witness_agreement"] = c["agreement"]
                words = sum(c["layer_words"] for c in cmp.values()) or 1
                differ = sum(c["layer_only"] for c in cmp.values())
                subs = [s for c in cmp.values() for s in c["substitutions"]]
                md["witness"] = dict(pages=len(cmp), agreement_mean=round(sum(c["agreement"] for c in cmp.values()) / len(cmp), 4),
                                     layer_words=words, layer_words_unmatched=differ, unmatched_share=round(differ / words, 4),
                                     substitutions=sum(c["substitution_count"] for c in cmp.values()))
                files.append(B.HeldFile("witness.json", text=json.dumps({str(p): c for p, c in cmp.items()}, indent=1, ensure_ascii=False) + "\n",
                                        role="derived", derived_from=f"{md['text_layer_file']} (the text layer) and ocr.txt",
                                        tool="ledger.acquire.document.compare_witnesses (word lists, difflib)"))
                notes.append(f"{len(cmp)} page{'s' if len(cmp) != 1 else ''} of someone else's OCR read again as a second witness (ocr.txt; "
                             f"witness.json: {md['witness']['unmatched_share']:.1%} of the layer's words unmatched)")
            best = {r["page"]: (ocr_text[r["page"]] if r["page"] in ocr_text else layer[r["page"] - 1]) for r in rows}
            if layer_once:
                files.append(B.HeldFile("text.txt", text=per_page_form(layer), role="derived", derived_from=held_name,
                                        tool=layer_tool + "; the reading text is the text layer on every page (no page's text came from "
                                                          "OCR), so the text layer is held once, as text.txt"))
            else:
                files.append(B.HeldFile("text-layer.txt", text=per_page_form(layer), role="derived", derived_from=held_name, tool=layer_tool))
                files.append(B.HeldFile("text.txt", text=per_page_form(best), role="derived", derived_from=held_name,
                                        tool="ledger.acquire.document: per page the text layer where it stands, the OCR where the layer failed (pages.tsv)"))
            md["pages"] = len(layer)
        elif ext in O.IMAGE_EXT:
            texts, label, err = self._ocr([ap])
            if err:
                rows.append(dict(page=1, verdict="image", source=err.split(":")[0])); notes.append(err)
            else:
                t = texts.get(ap, ""); rows.append(dict(page=1, verdict="image", source=f"ocr: {label}", ocr_chars=len(t)))
                # the OCR is the reading text: held once, as text.txt (7b2 item 19; ocr_file names it)
                files.append(B.HeldFile("text.txt", text=per_page_form([t]), role="derived", derived_from=held_name,
                                        tool=f"{label}; the OCR is the reading text, held once, as text.txt"))
                md["ocr_backend"] = label; md["ocr_file"] = "text.txt"; ran.append(f"OCR {label}")
            md["pages"] = 1
        else:
            raise ValueError(f"{path}: not a PDF or an image ({ext})")
        cols = ["page", "verdict", "image", "quality", "junk", "text_layer_chars", "ocr_chars", "source", "witness", "witness_agreement"]
        files.append(B.HeldFile("pages.tsv", text="\t".join(cols) + "\n" + "".join("\t".join(str(r.get(c, "")) for c in cols) + "\n" for r in rows),
                                role="derived", derived_from=held_name, tool="ledger.acquire.document.judge"))
        counts = {}
        for r in rows: counts[r["source"]] = counts.get(r["source"], 0) + 1
        md["page_sources"] = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        md["machine"] = self.machine()
        if date_basis: md["date_basis"] = date_basis
        if notes: md["status"] = "; ".join(notes)
        has_text = any(f.name == "text.txt" for f in files)
        rec = B.Record(identifier or stem, "document" if ext == ".pdf" or data[:5] == b"%PDF-" else "image", title or stem, date=date,
                       speaker_or_author=author, venue=venue, text="text.txt" if has_text else None,
                       provenance=provenance or (self.rel(ap) if ap.startswith(self.root + os.sep) else ap), metadata=md)
        rec.capture_tool = f"{self.tool} ({'; '.join(ran) or 'no tool ran'})"
        return B.Capture(rec, files, folder=self._folder(identifier or stem, title or stem, date),
                         status_note=("; ".join(notes) + ".") if notes else "")

    def fetch(self, paths, **kw):
        return [self.capture_file(p, **kw) for p in paths]

    # ---------------------------------------------------------------------------------------------------- by URL (findings 5, 16)
    def _web(self, web=None, gap=10.0):
        if web is not None: return web
        from ledger.acquire import web as W
        return W.WebAdapter(root=self.root, gap=gap, hold_root=self.hold_root, state_dir=self.state_dir, log=self.log)

    def fetch_url(self, url, web=None, folder=None, **kw):
        """Fetch a PDF (or image) through the web adapter and hold it: the held file's `how` is the HTTP response line, the
        provenance the URL; a refusal or failure gives a failed row."""
        from ledger.acquire import web as W
        w = self._web(web)
        try: g = w.get_full(url)
        except (W.RobotsRefusal, W.FetchFailure) as e: return w._failed(url, "document", kw.get("title"), e)
        name = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(g["final_url"]).path)) or "document.pdf"
        if not os.path.splitext(name)[1]: name += ".pdf" if g["data"][:5] == b"%PDF-" else ".bin"
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, B.LP.hold_name(name) if hasattr(B.LP, "hold_name") else name)
            with open(p, "wb") as f: f.write(g["data"])
            md = dict(kw.pop("metadata", None) or {}); md["robots"] = W.R.summary(g["robots"])
            if g["final_url"] != url: md["final_url"] = g["final_url"]
            cap = self.capture_file(p, provenance=url, metadata=md, how=f"HTTP {g['status']} response body of {g['final_url']}, {g['content_type']}",
                                    link=g["final_url"], **kw)
            if folder: cap.folder = folder
            return self.hold(cap)

    def fetch_page(self, page_url, rules=None, web=None, folder=None, **kw):
        """A catalogue's landing page and its attachments as one item (finding 16). `rules`: a dict or a JSON file with `attachments`
        (a regex the links to fetch must match; default PDF and text files), `fields` ({name: regex with one group, searched in the
        page's HTML}); fields named title, date, identifier, author and venue fill the record, the rest go to the metadata."""
        import html as H
        from ledger.acquire import web as W
        rules = B.read_json(rules) if isinstance(rules, str) else dict(rules or {})
        w = self._web(web)
        try: g = w.get_full(page_url)
        except (W.RobotsRefusal, W.FetchFailure) as e: return w._failed(page_url, "document", kw.get("title"), e)
        raw = g["data"].decode(g["charset"] or "utf-8", "replace")
        fields = {}
        for name, rx in (rules.get("fields") or {}).items():
            m = re.search(rx, raw, re.S | re.I)
            if m: fields[name] = H.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip()
        att_rx = re.compile(rules.get("attachments") or r"\.(pdf|txt)(\?|$)", re.I)
        links = []
        for m in re.finditer(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', raw):
            u = urllib.parse.urljoin(g["final_url"], H.unescape(m.group(1)))
            if att_rx.search(urllib.parse.urlsplit(u).path) and u not in links: links.append(u)
        if not links: return w._failed(page_url, "document", fields.get("title"), W.FetchFailure(page_url, "no attachment link matched the rules"))
        got = []; failures = []
        for u in links:
            try: got.append((u, w.get_full(u)))
            except (W.RobotsRefusal, W.FetchFailure) as e: failures.append(f"{u}: {e}")
        main = next(((u, x) for u, x in got if x["data"][:5] == b"%PDF-"), got[0] if got else None)
        if main is None: return w._failed(page_url, "document", fields.get("title"), W.FetchFailure(page_url, "; ".join(failures)))
        given = kw.pop("date", None)
        date = given or (W.iso_date(fields["date"]) if fields.get("date") else None)
        md = dict(kw.pop("metadata", None) or {}); md.update({k: v for k, v in fields.items() if k not in ("title", "date", "identifier", "author", "venue")})
        md.update(landing_page=page_url, attachments=[u for u, _ in got], robots=W.R.summary(g["robots"]))
        if failures: md["attachments_failed"] = failures
        if given: md["date_basis"] = "given by the caller"
        elif fields.get("date"): md["date_basis"] = f"the landing page's field `date` ({fields['date']!r})"
        else: md["date_basis"] = "none found (no date field matched on the landing page)"
        with tempfile.TemporaryDirectory() as tmp:
            mu, mx = main
            name = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(mx["final_url"]).path)) or "document.pdf"
            p = os.path.join(tmp, name)
            with open(p, "wb") as f: f.write(mx["data"])
            cap = self.capture_file(p, title=kw.pop("title", None) or fields.get("title"), identifier=kw.pop("identifier", None) or fields.get("identifier"),
                                    date=date, author=kw.pop("author", None) or fields.get("author"), venue=kw.pop("venue", None) or fields.get("venue"),
                                    provenance=page_url, metadata=md, how=f"HTTP {mx['status']} response body of {mx['final_url']}, {mx['content_type']}",
                                    link=mx["final_url"], **kw)
        cap.files.append(B.HeldFile("landing-page.html", data=g["data"], how=f"HTTP {g['status']} response body of {g['final_url']}, {g['content_type']}"))
        cap.files.append(B.HeldFile("landing-page.md", text=W.html_to_text(raw) + "\n", role="derived", derived_from="landing-page.html",
                                    tool="ledger.acquire.web.html_to_text"))
        for u, x in got:
            if u == mu: continue
            nm = os.path.basename(urllib.parse.unquote(urllib.parse.urlsplit(x["final_url"]).path)) or "attachment"
            nm = nm if len(nm) <= B.INNER_NAME_CAP and not B.LP.name_problems(nm) else B.LP.hold_name(nm)
            cap.files.append(B.HeldFile(nm, data=x["data"], how=f"HTTP {x['status']} response body of {x['final_url']}, {x['content_type']}"))
            if x["content_type"].startswith("text/") and B.needs_text_copy(x["data"], x["charset"]):
                cap.files.append(B.normalised_copy(os.path.splitext(nm)[0] + ".utf8.txt", x["data"], nm, x["charset"])[0])
        if folder: cap.folder = folder
        return self.hold(cap)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*"); ap.add_argument("--title"); ap.add_argument("--date"); ap.add_argument("--author")
    ap.add_argument("--venue"); ap.add_argument("--provenance"); ap.add_argument("--set"); ap.add_argument("--ocr", default="auto")
    ap.add_argument("--no-witness", action="store_true"); ap.add_argument("--url"); ap.add_argument("--page"); ap.add_argument("--rules")
    ap.add_argument("--link-over", type=int); ap.add_argument("--root"); ap.add_argument("--hold-root"); ap.add_argument("--detect", action="store_true")
    a = ap.parse_args(argv)
    if a.detect: print(json.dumps(O.detect(a.root), indent=1)); return
    d = DocumentAdapter(root=a.root, ocr=a.ocr, set_name=a.set, witness=not a.no_witness, link_over=a.link_over, hold_root=a.hold_root)
    kw = dict(title=a.title, date=a.date, author=a.author, venue=a.venue)
    if a.url: rows = [d.fetch_url(a.url, **kw)]
    elif a.page: rows = [d.fetch_page(a.page, rules=a.rules, **{k: v for k, v in kw.items() if v})]
    else: rows = d.acquire(a.files, provenance=a.provenance, **kw)
    for r in rows: print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
