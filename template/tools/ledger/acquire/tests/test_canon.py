#!/usr/bin/env python3
"""Tests of the canon adapter on the synthetic casebook corpus (tools/ledger/tests/casebook_corpus.py): a verse-form text held in
verse units and cited; a multi-witness file; tools/fetch_kjv.py run through the redirecting runner on a small local input (offline),
with a project's held kjv.txt, if it has one, unchanged; the runner's write guard; the headings scheme a manifesto or treatise uses;
the lines and page-lines schemes."""
import os, tempfile, unittest
import _common as C
import casebook_corpus as CC
from ledger.acquire import base as B, canon as K, _scripts

KJV = os.path.join(C.ROOT, "books/sources/kjv.txt")

MANIFESTO = """An Example Manifesto
Front matter that belongs to no unit.

PART I
Chapter 1
1. The first section of the first chapter.
It runs on to a second line.
2. The second section.
Chapter 2
1. Chapter two opens here.
PART II
Chapter 1
1. The second part begins.
2. And ends.
"""


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class VerseUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="ledger-acquire-canon-")
        cls.corpus = CC.build(os.path.join(cls.root, "corpus")); cls.text = cls.corpus["verses"]
        cls.ad = K.CanonAdapter(root=cls.root, log=lambda m: None)
        cls.row = cls.ad.hold_text(cls.text, "charter-1888", title="The Harrowmere Waterworks Charter (1888)", scheme="verse")
        cls.f = os.path.join(cls.root, cls.row["hold"])

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.root, True)

    def test_hold(self):
        self.assertEqual(self.row["hold"], "sources/canon/charter-1888")
        self.assertEqual(C.sha(os.path.join(self.f, "charter-1888.txt")), C.sha(self.text))
        md = B.load_hold(self.f)["record"]["metadata"]
        self.assertEqual(md["units"], 7); self.assertEqual(md["level_values"]["book"], 2); self.assertEqual(md["lines_outside_units"], 0)
        self.assertEqual(B.verify_hold(self.f), [])

    def test_units_resolve_to_the_held_lines(self):
        lines = B.LN.read_text(self.text).split("\n")
        units = K.load_units(self.f)
        for u in units: self.assertEqual(lines[u["start"] - 1], f"{u['address']}\t{u['text']}")

    def test_cite(self):
        (a, s, e, t), = K.cite(self.f, "Charter 2:1")
        self.assertTrue(t.startswith("No report of a defect")); self.assertEqual(s, e)
        self.assertEqual([x[0] for x in K.cite(self.f, "Charter 1:1-3")], ["Charter 1:1", "Charter 1:2", "Charter 1:3"])
        self.assertEqual(len(K.cite(self.f, "Minutes 1")), 2)
        self.assertEqual(K.cite(self.f, "Nope 1:1"), [])


class Witnesses(unittest.TestCase):
    def test_multi_scroll_file_with_witness_prefix(self):
        p = CC.build(os.path.join(C.temp_root(self), "corpus"))["witnesses"]   # two editions of the charter, each line prefixed
        sch = K.make_scheme("verse"); units = sch.units(B.LN.read_text(p).split("\n"))
        self.assertEqual(sch.skipped, []); self.assertTrue(units[0].address.startswith(units[0].levels["witness"] + " "))


class Fetcher(unittest.TestCase):
    def test_fetch_kjv_wrapped_offline_and_the_held_text_untouched(self):
        root = C.temp_root(self)
        mini = os.path.join(root, "pg10-mini.txt")
        B.LN.write_text(mini, "\n".join([
            "The Project Gutenberg eBook of The King James Bible", "", "The First Book of Moses: Called Genesis", "The Gospel According to Saint John", "",
            "The First Book of Moses: Called Genesis", "", "1:1 In the beginning God created the heaven and the earth.",
            "", "1:2 And the earth was without form, and void; 1:3 And God said, Let there be light: and there was light.", "", "", "", "", "", "", "",
            "The Gospel According to Saint John", "", "3:16 For God so loved the world.", "", "*** END OF THE PROJECT GUTENBERG EBOOK"]) + "\n")
        before = C.sha(KJV) if os.path.isfile(KJV) else None
        ad = K.CanonAdapter(root=root, log=lambda m: None)
        row = ad.fetch_canon("kjv", [mini], offline=True)
        f = os.path.join(root, row["hold"])
        self.assertEqual(B.read_raw(os.path.join(f, "kjv.txt")).split("\n")[1:5],
                         ["Gen 1:1\tIn the beginning God created the heaven and the earth.", "Gen 1:2\tAnd the earth was without form, and void;",
                          "Gen 1:3\tAnd God said, Let there be light: and there was light.", "John 3:16\tFor God so loved the world."])
        h = B.load_hold(f); roles = {x["name"]: x["role"] for x in h["files"]}
        self.assertEqual(roles["pg10-mini.txt"], "held"); self.assertEqual(roles["kjv.txt"], "derived")
        self.assertIn("tools/fetch_kjv.py", h["record"]["capture_tool"])
        self.assertEqual(h["record"]["metadata"]["units"], 4)
        if before: self.assertEqual(C.sha(KJV), before)                        # the held books/sources/kjv.txt never touched

    def test_runner_refuses_writes_outside_staging_and_the_network(self):
        root = C.temp_root(self); staging = os.path.join(root, "staging"); outside = os.path.join(root, "outside.txt")
        script = os.path.join(root, "bad_tool.py")
        B.LN.write_text(script, f"open({outside!r}, 'w').write('x')\n")
        rc, out, err, red = _scripts.run_tool(script, [], staging)
        self.assertNotEqual(rc, 0); self.assertIn("PermissionError", err); self.assertFalse(os.path.exists(outside))
        net = os.path.join(root, "net_tool.py")
        B.LN.write_text(net, "import urllib.request\nurllib.request.urlopen('https://example.org', timeout=5)\n")
        rc, out, err, red = _scripts.run_tool(net, [], staging, offline=True)
        self.assertNotEqual(rc, 0); self.assertIn("network refused", err)


class Schemes(unittest.TestCase):
    def test_headings_for_a_manifesto(self):
        root = C.temp_root(self); p = os.path.join(root, "manifesto.txt"); B.LN.write_text(p, MANIFESTO)
        scheme = {"kind": "headings", "address": "{part}.{chapter}.{section}", "levels": [
            {"name": "part", "pattern": r"^PART ([IVXLC]+)\b"}, {"name": "chapter", "pattern": r"^Chapter (\d+)\b"},
            {"name": "section", "pattern": r"^(\d+)\.\s"}]}
        ad = K.CanonAdapter(root=root, log=lambda m: None)
        row = ad.hold_text(p, "example-manifesto", title="An Example Manifesto", scheme=scheme)
        f = os.path.join(root, row["hold"]); units = K.load_units(f)
        self.assertEqual([u["address"] for u in units], ["I.1.1", "I.1.2", "I.2.1", "II.1.1", "II.1.2"])
        self.assertEqual(units[0]["text"], "1. The first section of the first chapter.\nIt runs on to a second line.")
        self.assertEqual([x[0] for x in K.cite(f, "I.1")], ["I.1.1", "I.1.2"])
        self.assertEqual(B.load_hold(f)["record"]["metadata"]["lines_outside_units"], 2)   # the title and the front matter
        self.assertEqual(B.read_json(os.path.join(f, "scheme.json"))["levels"][1]["name"], "chapter")

    def test_lines_and_paragraphs(self):
        lines = ["a", "b", "", "c", "d", "e", "", "", "f"]
        self.assertEqual([u.address for u in K.make_scheme({"kind": "lines", "paragraphs": True}).units(lines)], ["P1", "P2", "P3"])
        self.assertEqual([u.address for u in K.make_scheme({"kind": "lines", "size": 4}).units(lines)], ["L1-4", "L5-8", "L9-9"])

    def test_page_lines_on_a_held_text_layer(self):
        root = C.temp_root(self); p = CC.build(os.path.join(root, "corpus"))["report_txt"]   # a per-page text layer
        ad = K.CanonAdapter(root=root, log=lambda m: None)
        f = os.path.join(root, ad.hold_text(p, "harrowmere-review-2018", scheme="page-lines")["hold"])
        self.assertEqual([u["address"] for u in K.load_units(f)], ["p.1", "p.2", "p.3", "p.4"])
        (a, s, e, t), = K.cite(f, "p.1 l.1-2")
        self.assertEqual(t, "REPORT ON THE HARROWMERE EVENT\nVale Water Authority, 2018"); self.assertEqual((s, e), (2, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
