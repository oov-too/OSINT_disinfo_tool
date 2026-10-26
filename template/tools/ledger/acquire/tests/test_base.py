#!/usr/bin/env python3
"""Tests of the hold schema, the base adapter (hold, README, versions, names, the rate gate) and the hold names of tools/ledger/hold.py.
  python3 tools/ledger/acquire/tests/test_base.py      (or python3 -m unittest discover -s tools/ledger/acquire/tests)"""
import json, os, re, unittest
import _common as C
from ledger.acquire import base as B, schema as S
from ledger import paths as LP
from ledger import hold as H


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class Probe(B.Adapter):
    name = "probe"
    def fetch(self, caps): return caps


class Schema(unittest.TestCase):
    def test_document_and_code_agree(self):
        """tools/hold-schema.md's field table names the fields of schema.py with the same required column."""
        doc = B.read_raw(os.path.join(C.TOOLS, "hold-schema.md"))
        sec = doc.split("## 2. Fields", 1)[1].split("\n## ", 1)[0]
        rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.split("\n") if l.startswith("| `")]
        got = {re.sub(r"`", "", r[0]): r[3] for r in rows}
        self.assertEqual(list(got), S.FIELD_NAMES)
        for f in S.FIELDS: self.assertEqual(got[f["name"]], f["required"], f["name"])

    def test_synonyms(self):
        self.assertEqual(S.name_tokens("recNo"), ["rec", "no"]); self.assertEqual(S.name_tokens("upload_date"), ["upload", "date"])
        self.assertEqual(S.synonym_score("rec_no", "identifier"), 1.0)
        self.assertGreaterEqual(S.synonym_score("UploadDate", "date"), 0.85)
        self.assertEqual(S.synonym_score("headline", "title"), 1.0)
        self.assertEqual(S.synonym_score("zzz", "title"), 0.0)

    def test_record_problems(self):
        self.assertEqual(B.Record("x", "video", "T").problems(), [])
        self.assertTrue(B.Record(None, "video", "T").problems())
        self.assertTrue(B.Record("x", "film", "T").problems())
        self.assertTrue(B.Record("x", "video", "T", date="18 July 2008").problems())
        self.assertEqual(B.Record("x", "record", "T", date="1995-07?").problems(), [])


class Hold(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.ad = Probe(root=self.root)

    def cap(self, data=b"line one\r\nline two\r\n", text="derived\r\ntext", ident="item-1", title="An item: one", **kw):
        rec = B.Record(ident, "text", title, date="2026-10-22", provenance="test", **kw)
        return B.Capture(rec, [B.HeldFile("source.txt", data=data, how="test bytes"),
                               B.HeldFile("text.md", text=text, role="derived", derived_from="source.txt", tool="test")])

    def test_held_bytes_unchanged_derived_lf_and_readme_generated(self):
        row = self.ad.hold(self.cap())
        self.assertEqual(row["status"], "new")
        f = os.path.join(self.root, row["hold"])
        self.assertTrue(row["hold"].startswith("sources/text/"))
        self.assertEqual(B.read_bytes(os.path.join(f, "source.txt")), b"line one\r\nline two\r\n")   # held: CRLF kept
        self.assertEqual(B.read_bytes(os.path.join(f, "text.md")), b"derived\ntext")                  # derived: LF
        h = B.read_json(os.path.join(f, "hold.json"))
        self.assertEqual(B.read_raw(os.path.join(f, "README.md")), B.readme_text(h))
        self.assertNotIn("\r", B.read_raw(os.path.join(f, "README.md")))
        self.assertEqual(B.verify_hold(f), [])
        readme = B.read_raw(os.path.join(f, "README.md"))
        for label in ("| Identifier | item-1 |", "| Media kind | text |", "| Date | 2026-10-22 |", "## Files", "## Captures", "| source.txt | held |"):
            self.assertIn(label, readme)

    def test_recapture_identical_and_changed(self):
        r1 = self.ad.hold(self.cap()); f = os.path.join(self.root, r1["hold"])
        first = C.sha(os.path.join(f, "source.txt"))
        r2 = self.ad.hold(self.cap()); self.assertEqual(r2["status"], "unchanged"); self.assertEqual(r2["written"], [])
        r3 = self.ad.hold(self.cap(data=b"line one\r\nline two, revised\r\n"))
        self.assertEqual(r3["status"], "changed")
        self.assertEqual(C.sha(os.path.join(f, "source.txt")), first)                  # the first capture is never overwritten
        sib = [n for n in os.listdir(f) if re.fullmatch(r"source\.\d{8}T\d{6}Z\.txt", n)]
        self.assertEqual(len(sib), 1)
        h = B.load_hold(f); self.assertEqual([c["status"] for c in h["captures"]], ["new", "unchanged", "changed"])
        self.assertEqual(B.verify_hold(f), [])

    def test_identifier_collision_gets_its_own_folder(self):
        a = self.ad.hold(self.cap(ident="same title", title="Same")); b = self.ad.hold(self.cap(ident="same-title", title="Same"))
        self.assertNotEqual(a["hold"], b["hold"]); self.assertTrue(b["hold"].startswith(a["hold"] + "-"))

    def test_reserved_and_refused_names(self):
        rec = B.Record("r", "text", "R", provenance="t")
        row = self.ad.hold(B.Capture(rec, [B.HeldFile("README.md", data=b"theirs"), B.HeldFile("x.txt", data=b"x")]))
        f = os.path.join(self.root, row["hold"])
        self.assertEqual(B.read_bytes(os.path.join(f, "held-README.md")), b"theirs")
        self.assertEqual(B.verify_hold(f), [])
        bad = self.ad.hold(B.Capture(B.Record("s", "text", "S"), [B.HeldFile("CON.txt", data=b"x")]))
        self.assertEqual(bad["status"], "failed"); self.assertIn("device name", bad["note"])
        none = self.ad.hold(B.Capture(B.Record("t", "text", "T"), []))
        self.assertEqual(none["status"], "failed")

    def test_dry_writes_nothing(self):
        ad = Probe(root=self.root, dry=True); row = ad.hold(self.cap())
        self.assertFalse(os.path.exists(os.path.join(self.root, row["hold"])))

    def test_manifest(self):
        rows = self.ad.acquire([self.cap(), self.cap(ident="item-2", title="Two")])
        p = B.write_manifest(rows, os.path.join(self.root, "m.tsv"))
        lines = B.read_raw(p).split("\n")
        self.assertEqual(lines[0].split("\t"), B.MANIFEST_COLUMNS); self.assertEqual(len([l for l in lines if l]), 3)


class Gate(unittest.TestCase):
    def test_gap_is_enforced_and_lock_released(self):
        root = C.temp_root(self); now = [1000.0]; slept = []
        def clock(): return now[0]
        def sleep(s): slept.append(s); now[0] += s
        g = B.RateGate("svc", 10, os.path.join(root, ".ledger"), clock=clock, sleep=sleep)
        with g: pass
        now[0] += 3
        with g: pass
        self.assertEqual(g.waits, [0.0, 7.0])
        self.assertFalse(os.path.exists(g.lock))
        g2 = B.RateGate("svc", 10, os.path.join(root, ".ledger"), clock=clock, sleep=sleep)   # another process: same stamp file
        with g2: pass
        self.assertEqual(g2.waits, [10.0])


class HoldNames(unittest.TestCase):
    """tools/ledger/hold.py as the acquire layer uses it."""

    def test_slug_and_path(self):
        self.assertEqual(H.safe_slug("Réunion — Ŝtrange: Title!"), "reunion-strange-title")
        self.assertEqual(H.safe_slug("con"), "con-file")
        long = H.safe_slug("word " * 40, 80); self.assertLessEqual(len(long), 80); self.assertFalse(long.endswith("-"))
        self.assertEqual(H.hold_path("video", "-HbrTalks20", "ignored"), "sources/video/yt--HbrTalks20")
        self.assertEqual(H.hold_path("web/my set", "2026-10-22", "A Page"), "sources/web/my-set/2026-10-22-a-page")
        with self.assertRaises(ValueError): H.hold_path("films", "x", "y")
        for t in ["A" * 300, "Report on the Harrowmere Event - Vale Water Authority Review of the Spillway", "LPT1", "...dots...", "  "]:
            p = H.hold_path("text", t, t) + "/README.md"
            self.assertEqual(LP.name_problems(p), [], p)
            self.assertTrue(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p.split("/")[2]))

    def test_base_uses_hold_module(self):
        self.assertEqual(B.HOLD_MODULE, "ledger.hold"); self.assertIs(B.hold_path, H.hold_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
