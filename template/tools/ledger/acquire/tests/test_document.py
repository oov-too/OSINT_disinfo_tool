#!/usr/bin/env python3
"""Tests of the document adapter on the synthetic casebook corpus (tools/ledger/tests/casebook_corpus.py): the text layer of a held
PDF against the held per-page .txt beside it (both joins), the page judgement, the hold of a paper-capture scan (page images under
someone else's OCR), a blank born-digital page, and the OCR backend of this machine (Apple Vision through tools/ocr_vision.swift,
compiled into the test's temporary root, on the fixture image tests/fixtures/casebook-page.png)."""
import glob, io, json, os, platform, shutil, tempfile, unittest
import _common as C
import casebook_corpus as CC
from ledger.acquire import base as B, document as D, ocr as O

CB = {}   # the corpus, built once for the module


def setUpModule():
    C.block_network()
    CB.update(CC.build(os.path.join(tempfile.mkdtemp(prefix="ledger-acquire-document-"), "corpus")))
    CB["scan_txt"] = CB["pdfs"]["scan"][:-4] + ".txt"


def tearDownModule():
    C.allow_network(); shutil.rmtree(os.path.dirname(CB["root"]), True)


class TextLayer(unittest.TestCase):
    def test_held_pdf_text_layer_matches_the_held_txt(self):
        got = D.per_page_form(D.text_layer(CB["pdfs"]["scan"]))
        self.assertEqual(got, B.read_raw(CB["scan_txt"]))

    def test_every_held_pdf_matches_under_one_of_the_two_joins(self):
        pdfs = sorted(glob.glob(os.path.join(CB["root"], CB["set"], "*.pdf")))
        res = {}
        for p in pdfs:
            held = B.read_raw(p[:-4] + ".txt"); pages = D.text_layer(p)
            res[os.path.basename(p)] = next((name for name, sep in (("blank line", "\n\n"), ("newline", "\n")) if D.per_page_form(pages, sep) == held), None)
        self.assertEqual(res, {"review-2018-annex.pdf": "newline", "review-2018-scan.pdf": "blank line", "review-2018.pdf": "blank line"})

    def test_parse_per_page_round_trip(self):
        pages = ["a\nb", "", "c\n"]
        for sep in ("\n\n", "\n"):
            self.assertEqual(D.parse_per_page(D.per_page_form(pages, sep), sep), {1: "a\nb", 2: "", 3: "c\n"})

    def test_judge(self):
        self.assertEqual(D.judge("   ")[0], "empty")
        self.assertEqual(D.judge("The quick brown fox jumps over the lazy dog, and the dog sleeps on.")[0], "good")
        front = "\n".join(B.LN.read_text(CB["garbled"]).split("\n")[3:40])   # a scan's front matter, OCRed as noise
        self.assertEqual(D.judge(front)[0], "garbled")
        self.assertEqual(D.judge("(cid:3)(cid:4)(cid:5) Some words here and there (cid:6)(cid:7) more words")[0], "garbled")


class Hold(unittest.TestCase):
    def setUp(self): self.root = C.temp_root(self)

    def test_hold_a_paper_capture_scan(self):
        scan = CB["pdfs"]["scan"]
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None)
        row = ad.hold(ad.capture_file(scan, title="Report on the Harrowmere Event", identifier="HI-201", date="2018-05-14"))
        f = os.path.join(self.root, row["hold"])
        self.assertEqual(row["hold"], "sources/document/2018-05-14-hi-201-report-on-the-harrowmere-event")
        self.assertEqual(C.sha(os.path.join(f, os.path.basename(scan))), C.sha(scan))
        self.assertFalse(os.path.exists(os.path.join(f, "text-layer.txt")))     # the text layer is the reading text: held once (7b2 item 19)
        self.assertEqual(B.read_raw(os.path.join(f, "text.txt")), B.read_raw(CB["scan_txt"]))
        self.assertEqual(B.load_hold(f)["record"]["metadata"]["text_layer_file"], "text.txt")
        lines = B.read_raw(os.path.join(f, "pages.tsv")).strip().split("\n"); head = lines[0].split("\t")
        tsv = [dict(zip(head, l.split("\t"))) for l in lines[1:]]
        self.assertEqual(len(tsv), 4)
        # a paper-capture file: page images under an OCR text layer, the text layer kept as the reading text
        self.assertTrue(all(r["verdict"] == "good" and r["image"] == "yes" and r["source"] == "text layer (someone else's OCR)" for r in tsv))
        md = B.load_hold(f)["record"]["metadata"]
        self.assertTrue(md["text_layer_origin"].startswith("OCR text layer under page images")); self.assertIn("Paper Capture", md["pdf_producer"])
        self.assertEqual(B.verify_hold(f), [])

    def test_a_blank_born_digital_page_is_not_sent_to_ocr(self):
        import pypdf
        w = pypdf.PdfWriter(); r = pypdf.PdfReader(CB["pdfs"]["review-2018"]); w.add_page(r.pages[0]); w.add_blank_page(612, 792)
        p = os.path.join(self.root, "two-pages.pdf")
        with open(p, "wb") as f: w.write(f)
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None, allow_compile=False)
        row = ad.hold(ad.capture_file(p, title="Two pages"))
        f = os.path.join(self.root, row["hold"]); tsv = B.read_raw(os.path.join(f, "pages.tsv")).strip().split("\n")
        self.assertIn("\tgood\t", tsv[1]); self.assertIn("\tempty\tno\t", tsv[2])
        self.assertTrue(tsv[2].split("\t")[7] == "text layer")          # an empty page with no page image: nothing to OCR
        self.assertEqual(B.verify_hold(f), [])


class OCR(unittest.TestCase):
    def test_parse_vision_output(self):
        out = "=== page-0001.png\nline one\nline two\n=== page-0002.png\nother\n"
        got = O.parse_vision_output(out, ["/x/page-0001.png", "/x/page-0002.png", "/x/page-0003.png"])
        self.assertEqual(got, {"/x/page-0001.png": "line one\nline two", "/x/page-0002.png": "other", "/x/page-0003.png": ""})

    def test_detection_report(self):
        rep = O.detect()
        self.assertEqual(rep["platform"], platform.system())
        self.assertIn(rep["ocr_backend"], ("vision", "vision-compilable", "tesseract", "missing"))
        if platform.system() == "Darwin" and shutil.which("swiftc"): self.assertIn(rep["ocr_backend"], ("vision", "vision-compilable"))
        print("\n    " + json.dumps(rep))

    @unittest.skipUnless(platform.system() == "Darwin" and shutil.which("swiftc"), "Apple Vision needs macOS and swiftc")
    def test_vision_on_a_held_image(self):
        img = CB["image"]                                                    # a rendered casebook page (tests/fixtures/casebook-page.png)
        root = C.temp_root(self)
        ad = D.DocumentAdapter(root=root, log=lambda m: None)
        os.environ.pop("LEDGER_OCR_VISION_BIN", None)
        binary = O.vision_binary(root) or O.compile_vision(root=root)        # tools/ocr_vision.swift, compiled, not rewritten
        self.assertTrue(os.path.isfile(binary))
        row = ad.hold(ad.capture_file(img, title="A casebook page"))
        f = os.path.join(root, row["hold"]); t = B.read_raw(os.path.join(f, "text.txt"))      # the OCR, held once (7b2 item 19)
        self.assertFalse(os.path.exists(os.path.join(f, "ocr.txt"))); self.assertEqual(B.load_hold(f)["record"]["metadata"]["ocr_file"], "text.txt")
        self.assertTrue(t.startswith("--- page 1 ---\n")); self.assertGreater(len(t.split()), 20)
        self.assertEqual(B.load_hold(f)["record"]["metadata"]["ocr_backend"], "vision (tools/ocr_vision.swift)")
        self.assertEqual(B.verify_hold(f), [])
        print(f"\n    Vision OCR of casebook-page.png: {len(t.split())} words; first line: {t.splitlines()[1][:70]!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
