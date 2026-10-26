#!/usr/bin/env python3
"""Tests of 7b2 item 19 (the pilot report, 2026-10-23): the document adapter holds the text layer once (text.txt, the metadata's
text_layer_file) unless OCR replaced pages; an image's OCR is held once; a normalised copy (the published transcript's
transcript.txt, a web page's text.txt) is marked in hold.json (normalised, normalised_copy_of) and in the README; the one-off
dedupe tool (dedupe_holds.py) removes an unreferenced byte-identical derived duplicate, keeps a referenced or held one, records
the removal in hold.json and the README, marks a normalised copy, is a dry run by default and idempotent, and the record of a
removal outlives a re-capture. No network."""
import json, os, pathlib, unittest
import _common as C
import casebook_corpus as CC
import tempfile, shutil
from ledger.acquire import base as B, document as D, published as P, web as W, dedupe_holds as DH

CB = {}


def setUpModule():
    C.block_network()
    CB.update(CC.build(os.path.join(tempfile.mkdtemp(prefix="ledger-acquire-dedupe-"), "corpus")))


def tearDownModule():
    C.allow_network(); shutil.rmtree(os.path.dirname(CB["root"]), True)


def names(folder): return {f["name"] for f in B.load_hold(folder)["files"]}


class DocumentHoldsTheLayerOnce(unittest.TestCase):
    def setUp(self): self.root = C.temp_root(self)

    def test_born_digital_pdf_one_text_file(self):
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None, witness=False)
        row = ad.hold(ad.capture_file(CB["pdfs"]["review-2018"], title="Review", identifier="HI-1"))
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        self.assertNotIn("text-layer.txt", names(f)); self.assertFalse(os.path.exists(os.path.join(f, "text-layer.txt")))
        self.assertEqual(h["record"]["text"], "text.txt"); self.assertEqual(h["record"]["metadata"]["text_layer_file"], "text.txt")
        self.assertEqual(B.read_raw(os.path.join(f, "text.txt")), D.per_page_form(D.text_layer(CB["pdfs"]["review-2018"])))
        tool = next(x for x in h["files"] if x["name"] == "text.txt")["tool"]
        self.assertIn("pypdf", tool); self.assertIn("held once", tool)
        self.assertEqual(B.verify_hold(f), [])

    def test_ocr_replacing_pages_keeps_both(self):
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None, ocr="always", witness=False)
        ad._ocr_pages = lambda pdf, pages: ({p: f"OCR reading of page {p}" for p in pages}, "fake-ocr", None)
        row = ad.hold(ad.capture_file(CB["pdfs"]["review-2018"], title="Review", identifier="HI-2"))
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        self.assertTrue({"text-layer.txt", "text.txt", "ocr.txt"} <= names(f))
        self.assertNotEqual(B.read_raw(os.path.join(f, "text-layer.txt")), B.read_raw(os.path.join(f, "text.txt")))
        self.assertEqual(h["record"]["metadata"]["text_layer_file"], "text-layer.txt"); self.assertEqual(h["record"]["text"], "text.txt")
        self.assertEqual(B.verify_hold(f), [])

    def test_witness_names_the_file_holding_the_layer(self):
        ad = D.DocumentAdapter(root=self.root, log=lambda m: None)
        # force a second witness on every image page, whatever this machine has
        import ledger.acquire.ocr as O
        saved = (O.renderer, O.backend)
        O.renderer = lambda *a, **k: "fake"; O.backend = lambda *a, **k: ("vision", "fake")
        try:
            ad._ocr_pages = lambda pdf, pages: ({p: "a witness reading" for p in pages}, "fake-ocr", None)
            row = ad.hold(ad.capture_file(CB["pdfs"]["scan"], title="Scan", identifier="HI-3"))
        finally:
            O.renderer, O.backend = saved
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        self.assertNotIn("text-layer.txt", names(f))                       # a witness does not replace the reading text
        w = next(x for x in h["files"] if x["name"] == "witness.json")
        self.assertEqual(w["derived_from"], "text.txt (the text layer) and ocr.txt")
        self.assertEqual(B.verify_hold(f), [])


class NormalisedCopies(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.site = os.path.join(self.root, "site"); os.makedirs(self.site)

    def put(self, name, data):
        p = os.path.join(self.site, name)
        with open(p, "wb") as f: f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return pathlib.Path(p).as_uri()

    def test_steps(self):
        self.assertEqual(B.normalised_steps("£\r\n".encode("cp1252"), "cp1252"),
                         ["decoded from cp1252 (not valid UTF-8), written as UTF-8", "CRLF line endings made LF"])
        self.assertEqual(B.normalised_steps(b"\xef\xbb\xbfa\rb", "utf-8"), ["CR line endings made LF", "byte-order mark dropped"])

    def test_published_transcript_is_marked_as_the_copy(self):
        p = P.PublishedTranscriptAdapter(root=self.root, gap=0, sleep=lambda s: None, log=lambda m: None)
        page_url = self.put("hearing.html", "<html><head><title>Day 1</title></head><body><p>Published: 9 April 2024</p></body></html>")
        txt = self.put("INQ0001.txt", "Witness: £ figures\r\n  1   Q. Good morning.\r\n".encode("cp1252"))
        row = p.published(page_url, [txt], identifier="INQ0001", title="Day 1")
        f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        e = next(x for x in h["files"] if x["name"] == "transcript.txt")
        self.assertEqual((e["role"], e["derived_from"], e["normalised_copy_of"]), ("derived", "INQ0001.txt", "INQ0001.txt"))
        self.assertIn("cp1252", e["normalised"]); self.assertIn("CRLF", e["normalised"]); self.assertIn("decode_text", e["tool"])
        self.assertEqual(h["record"]["text"], "transcript.txt")
        self.assertIn("A normalised copy of INQ0001.txt", B.read_raw(os.path.join(f, "README.md")))
        self.assertEqual(B.verify_hold(f), [])
        self.assertEqual(DH.counts(f, h)[1], len(B.read_raw(os.path.join(f, "transcript.txt")).split()) + len(B.read_raw(os.path.join(f, "page.md")).split()))

    def test_web_text_copy_is_marked(self):
        w = W.WebAdapter(root=self.root, gap=0, sleep=lambda s: None, log=lambda m: None)
        row = w.page(self.put("notice.txt", "Line one costs £5.\r\nLine two.\r\n".encode("cp1252")))[0]
        h = B.load_hold(os.path.join(self.root, row["hold"]))
        e = next(x for x in h["files"] if x["name"] == "text.txt")
        self.assertEqual(e["normalised_copy_of"], "page.txt")


class Dedupe(unittest.TestCase):
    """An old-form hold: the PDF's layer twice (text.txt, text-layer.txt), a cp1252 transcript and its unmarked copy, a third
    identical copy a note cites."""

    def setUp(self):
        self.root = C.temp_root(self)
        ad = B.Adapter(root=self.root, log=lambda m: None); ad.name = "document"
        layer = "--- page 1 ---\nThe Horizon system recorded a shortfall.\n"
        held_txt = "Day 1\r\n  1   Q. Good morning, £5.\r\n".encode("cp1252")
        files = [B.HeldFile("day1.pdf", data=b"%PDF-1.4 fake"), B.HeldFile("day1.txt", data=held_txt),
                 B.HeldFile("text-layer.txt", text=layer, role="derived", derived_from="day1.pdf", tool="pypdf"),
                 B.HeldFile("text.txt", text=layer, role="derived", derived_from="day1.pdf", tool="reading text"),
                 B.HeldFile("layer-copy.txt", text=layer, role="derived", derived_from="day1.pdf", tool="a copy a note cites"),
                 B.HeldFile("transcript.txt", text=held_txt.decode("cp1252"), role="derived", derived_from="day1.txt", tool="hand decode"),
                 B.HeldFile("witness.json", text="{}\n", role="derived", derived_from="text-layer.txt and ocr.txt", tool="w")]
        rec = B.Record("DAY1", "video", "Day 1", date="2024-04-09", text="transcript.txt",
                       metadata=dict(text_basis="the PDF's text layer (text.txt) is a second witness"))
        self.row = ad.hold(B.Capture(rec, files, folder="sources/pilot/video/2024-04-09-day1"))
        self.f = os.path.join(self.root, self.row["hold"])
        os.makedirs(os.path.join(self.root, "videos"))
        B.LN.write_text(os.path.join(self.root, "videos", "day-1.md"), "Source: sources/pilot/video/2024-04-09-day1/layer-copy.txt\n")
        self.src = os.path.join(self.root, "sources", "pilot")

    def run_tool(self, apply):
        return DH.run(self.src, root=self.root, apply=apply, log=os.path.join(self.root, "dedupe.jsonl"), out=lambda m: None)

    def test_dry_run_writes_nothing(self):
        before = {n: C.sha(os.path.join(self.f, n)) for n in os.listdir(self.f)}
        s = self.run_tool(False)[0]
        self.assertEqual([r["name"] for r in s["remove"]], ["text-layer.txt"])
        self.assertEqual([m["name"] for m in s["mark"]], ["transcript.txt"])
        self.assertEqual({n: C.sha(os.path.join(self.f, n)) for n in os.listdir(self.f)}, before)
        self.assertLess(s["words_after"], s["words_before"])

    def test_apply(self):
        s = self.run_tool(True)[0]
        self.assertFalse(os.path.exists(os.path.join(self.f, "text-layer.txt")))
        for n in ("text.txt", "layer-copy.txt", "day1.txt", "day1.pdf", "transcript.txt"): self.assertTrue(os.path.exists(os.path.join(self.f, n)))
        kept = {k["name"]: k["kept_because"] for k in s["kept_duplicates"]}
        self.assertEqual(kept, {"text.txt": "named in the record's metadata"})          # the note-cited copy is the keeper
        h = B.load_hold(self.f)
        rm = h["removed"][0]
        self.assertEqual((rm["name"], rm["identical_to"], rm["bytes"], rm["named_by"], rm["removed_by"]),
                         ("text-layer.txt", "layer-copy.txt", len(B.read_raw(os.path.join(self.f, "text.txt")).encode()), ["witness.json"], DH.TOOL))
        e = next(x for x in h["files"] if x["name"] == "transcript.txt")
        self.assertEqual(e["normalised_copy_of"], "day1.txt"); self.assertIn("CRLF", e["normalised"])
        self.assertEqual(h["size"]["bytes"], sum(x["bytes"] for x in h["files"]))
        self.assertIn("## Removed", B.read_raw(os.path.join(self.f, "README.md")))
        self.assertEqual(B.verify_hold(self.f), [])
        log = [json.loads(l) for l in B.read_raw(os.path.join(self.root, "dedupe.jsonl")).splitlines()]
        self.assertEqual(sorted(r["action"] for r in log), ["mark-normalised-copy", "remove"])
        again = self.run_tool(True)[0]                                                    # idempotent
        self.assertEqual((again["remove"], again["mark"]), ([], []))

    def test_held_file_never_removed(self):
        ad = B.Adapter(root=self.root, log=lambda m: None)
        data = b"plain text\n"
        ad.hold(B.Capture(B.Record("X", "text", "X"), [B.HeldFile("a.txt", data=data),
                                                       B.HeldFile("b.txt", text="plain text\n", role="derived", derived_from="a.txt", tool="t")],
                          folder="sources/pilot/text/x"))
        s = [r for r in self.run_tool(True) if r["hold"].endswith("/x")][0]
        self.assertEqual([r["name"] for r in s["remove"]], ["b.txt"])                    # the derived twin goes, the held file stays
        self.assertTrue(os.path.exists(os.path.join(self.root, "sources/pilot/text/x/a.txt")))

    def test_removed_record_outlives_a_recapture(self):
        self.run_tool(True)
        ad = B.Adapter(root=self.root, log=lambda m: None); ad.name = "document"
        rec = B.Record("DAY1", "video", "Day 1", date="2024-04-09", text="transcript.txt")
        ad.hold(B.Capture(rec, [B.HeldFile("day1.pdf", data=b"%PDF-1.4 fake")], folder="sources/pilot/video/2024-04-09-day1"))
        h = B.load_hold(self.f)
        self.assertEqual(h["removed"][0]["name"], "text-layer.txt"); self.assertEqual(B.verify_hold(self.f), [])

    def test_changed_bytes_leave_the_hold_alone(self):
        with open(os.path.join(self.f, "text-layer.txt"), "a", encoding="utf-8") as fh: fh.write("tampered\n")
        s = self.run_tool(True)[0]
        self.assertTrue(s["problems"]); self.assertEqual(s["applied"], False)
        self.assertTrue(os.path.exists(os.path.join(self.f, "text-layer.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
