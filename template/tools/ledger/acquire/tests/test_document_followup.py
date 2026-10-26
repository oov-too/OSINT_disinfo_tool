#!/usr/bin/env python3
"""Tests of the document adapter's follow-up from the pilot (wip/platform-phase6b/adapter-findings.md), on PDFs the test builds with
PyMuPDF (no corpus file read): the scan profile and the text layer's origin (finding 10), the word-index and born-digital verdicts
(7), the second witness on an image page under someone else's OCR layer (10), the capture tool naming only what ran (15), a PDF
fetched by URL (5) and held by link (17), a landing page with its attachments (16)."""
import io, json, os, pathlib, unittest
import _common as C
from ledger.acquire import base as B, document as D, ocr as O

FITZ = O._pymupdf()


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


def born_digital(path, pages):
    doc = FITZ.open()
    for text in pages:
        p = doc.new_page(width=612, height=792); y = 72
        for line in text.split("\n"): p.insert_text((72, y), line, fontsize=11); y += 14
    doc.save(path); doc.close()
    return path


def image_under_layer(path, image_text, layer_text):
    """One page: an image of `image_text` drawn over the whole page, and an invisible text layer (render mode 3) saying
    `layer_text`, as a publisher's OCR file has it."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1700, 2200), "white"); d = ImageDraw.Draw(img)
    font = None
    for f in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.isfile(f): font = ImageFont.truetype(f, 56); break
    font = font or ImageFont.load_default(size=56)
    y = 200
    for line in image_text.split("\n"): d.text((150, y), line, fill="black", font=font); y += 90
    buf = io.BytesIO(); img.save(buf, "PNG")
    doc = FITZ.open(); p = doc.new_page(width=612, height=792)
    p.insert_image(p.rect, stream=buf.getvalue())
    y = 90
    for line in layer_text.split("\n"): p.insert_text((54, y), line, fontsize=20, render_mode=3); y += 32
    doc.save(path); doc.close()
    return path


class Verdicts(unittest.TestCase):
    def test_word_index_is_not_garbled(self):
        index = " ".join(f"word{i} [{i % 5 + 1}] {i}/{i % 25 + 1} {i + 3}/{(i * 7) % 25 + 1}" for i in range(40))
        self.assertEqual(D.judge(index, image_page=False)[0], "index")
        self.assertEqual(D.judge(index, image_page=True)[0], "index")              # never sent to OCR, scan or not

    def test_born_digital_low_words_kept_and_junk_still_garbled(self):
        table = "\n".join(f"{i:04d}  {i * 3.5:9.2f}  {i * 11:7d}  X{i}" for i in range(30))
        self.assertEqual(D.judge(table, image_page=False)[0], "low-words")
        self.assertEqual(D.judge(table, image_page=True)[0], "garbled")
        self.assertEqual(D.judge("Plain words here and there " * 4 + "�" * 10, image_page=False)[0], "garbled")
        self.assertEqual(D.judge("Plain words here  and there " * 3, image_page=False)[0], "garbled")   # private-use: a failed decoding

    def test_witness_comparison(self):
        c = D.compare_witnesses("The Fuiitsu system recorded the shortfall.", "The Fujitsu system recorded the shortfall.")
        self.assertEqual(c["substitutions"], [("fuiitsu", "fujitsu")]); self.assertEqual(c["layer_only"], 1); self.assertLess(c["agreement"], 1)


@unittest.skipIf(FITZ is None, "PyMuPDF is not installed")
class Profiles(unittest.TestCase):
    def setUp(self): self.root = C.temp_root(self)

    def test_born_digital_profile_and_capture_tool(self):
        pdf = born_digital(os.path.join(self.root, "memo.pdf"), ["A memorandum about the budget for the survey work.", ""])
        prof = D.scan_profile(pdf)
        self.assertEqual((prof["origin"], prof["pages_with_image"]), ("born-digital", 0)); self.assertIn("PyMuPDF", prof["producer"] or "PyMuPDF")
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None)
        row = ad.hold(ad.capture_file(pdf, title="Memo")); h = B.load_hold(os.path.join(self.root, row["hold"]))
        import pypdf
        self.assertEqual(h["record"]["capture_tool"], f"ledger.acquire.document 1.0 (pypdf {pypdf.__version__})")   # only what ran
        md = h["record"]["metadata"]
        self.assertEqual(md["text_layer_origin"], "born-digital"); self.assertIn("renderer", md["machine"]); self.assertIn("ocr_backend", md["machine"])
        tsv = B.read_raw(os.path.join(self.root, row["hold"], "pages.tsv")).strip().split("\n")
        self.assertIn("\tempty\tno\t", tsv[2]); self.assertTrue(tsv[2].split("\t")[7] == "text layer")   # a blank born-digital page: not OCRed

    def test_image_page_profile(self):
        pdf = image_under_layer(os.path.join(self.root, "scan.pdf"), "The Fujitsu system recorded\nthe shortfall at the branch.",
                                "The Fuiitsu system recorded\nthe shortfall at the branch.")
        prof = D.scan_profile(pdf)
        self.assertEqual((prof["origin"], prof["pages_with_image"]), ("OCR text layer under page images", 1))

    @unittest.skipUnless(C.has_ocr(), "no renderer and OCR backend on this machine")
    def test_second_witness_on_someone_elses_ocr(self):
        pdf = image_under_layer(os.path.join(self.root, "scan.pdf"), "The Fujitsu system recorded\nthe shortfall at the branch.",
                                "The Fuiitsu system recorded\nthe shortfall at the branch.")
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None)
        row = ad.hold(ad.capture_file(pdf, title="Scan", identifier="SCAN-1")); f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        md = h["record"]["metadata"]
        self.assertTrue(md["text_layer_origin"].startswith("OCR text layer under page images"))
        self.assertEqual(md["witness"]["pages"], 1)
        w = B.read_json(os.path.join(f, "witness.json"))["1"]
        self.assertIn(["fuiitsu", "fujitsu"], w["substitutions"])                                 # the publisher's misreading found
        self.assertIn("Fuiitsu", B.read_raw(os.path.join(f, "text.txt")))                       # the reading text stays the layer
        self.assertIn("Fujitsu", B.read_raw(os.path.join(f, "ocr.txt")))
        self.assertIn("OCR vision", h["record"]["capture_tool"]); self.assertIn("rendered by PyMuPDF", h["record"]["capture_tool"])
        tsv = B.read_raw(os.path.join(f, "pages.tsv")).strip().split("\n"); head = tsv[0].split("\t"); r1 = dict(zip(head, tsv[1].split("\t")))
        self.assertEqual((r1["source"], r1["image"]), ("text layer (someone else's OCR)", "yes")); self.assertTrue(r1["witness"].startswith("ocr: vision"))
        self.assertEqual(B.verify_hold(f), [])
        ad2 = D.DocumentAdapter(root=self.root, witness=False, log=lambda m: None)
        h2 = ad2.capture_file(pdf, title="Scan", identifier="SCAN-2")
        self.assertFalse(any(x.name == "ocr.txt" for x in h2.files))                             # witness off: no OCR ran


@unittest.skipIf(FITZ is None, "PyMuPDF is not installed")
class ByURL(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.site = os.path.join(self.root, "site"); os.makedirs(self.site)

    def test_fetch_url_and_hold_by_link(self):
        pdf = born_digital(os.path.join(self.site, "report.pdf"), ["The report's only page of text, long enough to judge."])
        url = pathlib.Path(pdf).as_uri()
        ad = D.DocumentAdapter(root=self.root, witness=False, link_over=0, log=lambda m: None)
        row = ad.fetch_url(url, title="Report", identifier="R-1", date="2020-01-02")
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        held = next(x for x in h["files"] if x["name"] == "report.pdf")
        self.assertEqual(held["role"], "linked"); self.assertEqual(held["link"], url); self.assertEqual(held["sha256"], C.sha(pdf))
        self.assertTrue(held["how"].startswith(f"HTTP 200 response body of {url}, application/pdf"))
        self.assertFalse(os.path.exists(os.path.join(f, "report.pdf")))                          # the bytes stay at the source
        self.assertEqual(h["record"]["provenance"], url); self.assertIn("robots", h["record"]["metadata"])
        self.assertIn("held by link", B.read_raw(os.path.join(f, "README.md"))); self.assertEqual(B.verify_hold(f), [])
        self.assertEqual(h["size"]["linked_bytes"], os.path.getsize(pdf))

    def test_landing_page_with_attachments(self):
        born_digital(os.path.join(self.site, "EX0001.pdf"), ["An exhibit with enough plain words to be judged good text."])
        with open(os.path.join(self.site, "EX0001.txt"), "wb") as f: f.write("Exhibit text £ cp1252\r\n".encode("cp1252"))
        with open(os.path.join(self.site, "evidence.html"), "w", encoding="utf-8") as f:
            f.write("<html><head><title>Evidence EX0001</title></head><body><h1>Advice on the evidence</h1>"
                    "<p>URN: <span>EX0001</span></p><p>Document date: <span>15/07/2013</span></p><p>Type: Advice</p>"
                    "<a href='EX0001.pdf'>PDF</a> <a href='EX0001.txt'>Text</a> <a href='other.html'>other</a></body></html>")
        rules = {"fields": {"identifier": r"URN:\s*<span>([^<]+)</span>", "title": r"<h1>(.*?)</h1>", "doc_date": r"Document date:\s*<span>([^<]+)</span>",
                            "evidence_type": r"Type:\s*([^<]+)</p>"}, "attachments": r"\.(pdf|txt)$"}
        ad = D.DocumentAdapter(root=self.root, witness=False, log=lambda m: None)
        row = ad.fetch_page(pathlib.Path(os.path.join(self.site, "evidence.html")).as_uri(), rules=rules, date="2013-07-15")
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f); r = h["record"]
        self.assertEqual((r["identifier"], r["title"], r["date"]), ("EX0001", "Advice on the evidence", "2013-07-15"))
        self.assertEqual((r["metadata"]["evidence_type"], r["metadata"]["doc_date"]), ("Advice", "15/07/2013"))
        names = {x["name"] for x in h["files"]}
        self.assertTrue({"EX0001.pdf", "EX0001.txt", "EX0001.utf8.txt", "landing-page.html", "landing-page.md", "text.txt"} <= names)
        self.assertEqual(len(r["metadata"]["attachments"]), 2); self.assertEqual(B.verify_hold(f), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
