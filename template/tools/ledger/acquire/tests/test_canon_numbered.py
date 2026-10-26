#!/usr/bin/env python3
"""Tests of the canon adapter's `numbered` scheme (finding 11 of wip/platform-phase6b/adapter-findings.md: a judgment cited by
numbered paragraph, its text layer someone else's OCR) and of holding a PDF canon text directly, on a synthetic judgment the test
writes (no corpus file read)."""
import os, unittest
import _common as C
from ledger.acquire import base as B, canon as K, ocr as O

JUDGMENT = """Neutral Citation Number: [2019] EWHC 1 (QB)
Case No: HQ00X00001
Date: 16 December 2019
Contents
1. Introduction .......... 3
2. Background .......... 5
Mr Justice Example:
Introduction
1.This is the first paragraph of the judgment.
It runs on to a second line.
2. The second paragraph lists two things:
1. a numbered sub-item, not a paragraph;
2. another sub-item.
3. The third paragraph.
--- page 2 ---
5. The fifth paragraph (the fourth was lost in the OCR).
6, The sixth, its full stop read as a comma.
7. The seventh.
8. The eighth.
9. The ninth.
l0. The tenth, its 1 read as an l.
1 1. The eleventh, with a space inside the number.
Annex A
1. Annex text that is not a paragraph of the judgment.
2. More annex text.
"""


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class Numbered(unittest.TestCase):
    def scheme(self, **kw):
        return K.make_scheme(dict(kind="numbered", start_after=r"^Mr Justice Example", end_before=r"^Annex A", **kw))

    def test_chain(self):
        s = self.scheme(); lines = JUDGMENT.rstrip("\n").split("\n"); units = s.units(lines)
        self.assertEqual([u.address for u in units], ["1", "2", "3", "5", "6", "7", "8", "9", "10", "11"])
        self.assertEqual(s.report["missing"], [4]); self.assertEqual(s.report["last"], 11)
        self.assertEqual(units[0].text, "1.This is the first paragraph of the judgment.\nIt runs on to a second line.")
        self.assertIn("1. a numbered sub-item", units[1].text)                     # sub-items stay inside their paragraph
        self.assertGreaterEqual(s.report["rejected_candidates"], 2)
        self.assertEqual(s.report["tail_lines_outside_units"], 3)                   # the annex: outside the units, not in paragraph 11
        self.assertNotIn("Annex", units[-1].text)
        for u in units: self.assertEqual(u.text, "\n".join(lines[u.start - 1: u.end]))   # units are the held lines, none changed

    def test_front_matter_cannot_start_the_chain(self):
        s = K.make_scheme(dict(kind="numbered")); units = s.units(JUDGMENT.split("\n"))
        self.assertEqual(units[0].address, "1"); self.assertEqual(units[0].text.split("\n")[0], "1. Introduction .......... 3")
        # without start_after the contents line is taken as paragraph 1: the anchor is what tells front matter from text
        self.assertIn(4, s.report["missing"])

    def test_unnumbered_first_paragraph(self):
        text = "Lord Justice Example:\nThe first paragraph lost its number.\n2. The second.\n3. The third.\n"
        s = K.make_scheme(dict(kind="numbered", start_after=r"^Lord Justice Example")); units = s.units(text.rstrip("\n").split("\n"))
        self.assertEqual([u.address for u in units], ["1", "2", "3"]); self.assertEqual(s.report["first_paragraph_unnumbered_at_line"], 2)

    def test_hold_cite_and_report(self):
        root = C.temp_root(self); p = os.path.join(root, "judgment.txt"); B.LN.write_text(p, JUDGMENT)
        ad = K.CanonAdapter(root=root, log=lambda m: None)
        row = ad.hold_text(p, "example-v-example", scheme=dict(kind="numbered", start_after=r"^Mr Justice Example", end_before=r"^Annex A"))
        f = os.path.join(root, row["hold"]); md = B.load_hold(f)["record"]["metadata"]
        self.assertEqual((md["units"], md["numbered_missing"], md["numbered_last"]), (10, [4], 11))
        self.assertEqual(B.read_json(os.path.join(f, "units-report.json"))["missing"], [4])
        (addr, s, e, t), = K.cite(f, "10")
        self.assertTrue(t.startswith("l0. The tenth")); self.assertEqual(B.verify_hold(f), [])


@unittest.skipIf(O._pymupdf() is None, "PyMuPDF is not installed")
class PDFCanon(unittest.TestCase):
    def test_a_pdf_is_held_as_the_input_and_its_text_layer_cut(self):
        fitz = O._pymupdf(); root = C.temp_root(self); pdf = os.path.join(root, "judgment.pdf")
        doc = fitz.open()
        for chunk in (JUDGMENT.split("--- page 2 ---\n")):
            pg = doc.new_page(width=612, height=792); y = 60
            for line in chunk.rstrip("\n").split("\n"): pg.insert_text((60, y), line, fontsize=10); y += 13
        doc.save(pdf); doc.close()
        ad = K.CanonAdapter(root=root, log=lambda m: None)
        row = ad.hold_text(pdf, "example-pdf", scheme=dict(kind="numbered", start_after=r"^Mr Justice Example", end_before=r"^Annex A"))
        f = os.path.join(root, row["hold"]); h = B.load_hold(f)
        roles = {x["name"]: x["role"] for x in h["files"]}
        self.assertEqual((roles["judgment.pdf"], roles["text-layer.txt"]), ("held", "derived"))
        self.assertTrue(B.read_raw(os.path.join(f, "text-layer.txt")).startswith("--- page 1 ---\n"))
        self.assertEqual(h["record"]["metadata"]["text_layer_origin"], "born-digital")
        self.assertEqual([u["address"] for u in K.load_units(f)], ["1", "2", "3", "5", "6", "7", "8", "9", "10", "11"])
        self.assertEqual(B.verify_hold(f), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
