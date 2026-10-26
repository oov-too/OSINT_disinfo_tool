#!/usr/bin/env python3
"""Tests of the base's follow-up from the pilot (wip/platform-phase6b/adapter-findings.md): the hold root and the gates' state dir,
from arguments and from ledger.toml [acquire] (findings 1, 2); files held by link and the size class (17); a manifest begun with an
older header (17); text decoding for derived UTF-8 LF copies (8)."""
import os, unittest
import _common as C
from ledger.acquire import base as B, web as W


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class Probe(B.Adapter):
    name = "probe"


def cap(ident="item", files=None):
    return B.Capture(B.Record(ident, "text", f"Item {ident}", provenance="test"), files or [B.HeldFile("a.txt", data=b"abc\n")])


class Roots(unittest.TestCase):
    def setUp(self): self.root = C.temp_root(self)

    def test_hold_root_argument_and_config(self):
        row = Probe(root=self.root, hold_root="sources/pilot").hold(cap())
        self.assertEqual(row["hold"], "sources/pilot/text/item-item-item")          # identifier `item`, then the title `Item item`
        with open(os.path.join(self.root, "ledger.toml"), "a", encoding="utf-8") as f: f.write('[acquire]\nhold_root = "sources/second"\nstate_dir = "wip/gates"\n')
        p = Probe(root=self.root)
        self.assertEqual(p.hold_root, "sources/second"); self.assertEqual(p.state_dir, os.path.join(self.root, "wip", "gates"))
        self.assertEqual(p.hold(cap("b"))["hold"], "sources/second/text/b-item-b")
        w = W.WebAdapter(root=self.root, log=lambda m: None)
        self.assertEqual(w.folder(None, "A Page", "https://example.org/x"), "sources/second/web/undated-a-page")
        self.assertEqual(Probe(root=self.root, state_dir="/tmp/elsewhere").state_dir, "/tmp/elsewhere")

    def test_default_state_dir_is_shared(self):
        self.assertEqual(Probe(root=self.root).state_dir, os.path.join(self.root, ".ledger", "acquire"))


class Linked(unittest.TestCase):
    def setUp(self): self.root = C.temp_root(self)

    def test_linked_file_recorded_not_stored(self):
        big = b"x" * 5000
        c = cap("big", [B.HeldFile("scan.pdf", data=big, role="linked", link="https://example.org/scan.pdf", how="the original"),
                        B.HeldFile("text.txt", text="the text layer\n", role="derived", derived_from="scan.pdf", tool="t")])
        row = Probe(root=self.root).hold(c); f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        e = next(x for x in h["files"] if x["name"] == "scan.pdf")
        self.assertEqual((e["role"], e["link"], e["bytes"], e["sha256"]), ("linked", "https://example.org/scan.pdf", 5000, B.sha256(big)))
        self.assertFalse(os.path.exists(os.path.join(f, "scan.pdf")))
        self.assertEqual(h["size"], {"bytes": 15, "size_class": "small", "linked_bytes": 5000})
        self.assertEqual((row["bytes"], row["size_class"]), (15, "small"))
        readme = B.read_raw(os.path.join(f, "README.md"))
        self.assertIn("| scan.pdf | linked | 5,000 |", readme); self.assertIn("kept at https://example.org/scan.pdf", readme)
        self.assertIn("held by link", readme); self.assertEqual(B.verify_hold(f), [])
        with self.assertRaises(ValueError): B.HeldFile("x.pdf", data=b"1", role="linked")         # a linked file needs its link

    def test_size_classes(self):
        self.assertEqual([B.size_class(n) for n in (0, 10 * 1024 * 1024 - 1, 10 * 1024 * 1024, 120 * 1024 * 1024)], ["small", "small", "medium", "large"])

    def test_old_readmes_unchanged(self):
        """A hold.json without the new keys (size, texts, linked files) renders exactly as before, so holds made earlier still verify."""
        row = Probe(root=self.root).hold(cap("old")); f = os.path.join(self.root, row["hold"]); h = B.load_hold(f)
        del h["size"]
        self.assertNotIn("Size ", B.readme_text(h)); self.assertNotIn("held by link", B.readme_text(h))


class Manifest(unittest.TestCase):
    def test_appending_to_a_manifest_with_an_older_header(self):
        root = C.temp_root(self); p = os.path.join(root, "m.tsv")
        old = ["identifier", "media_kind", "title", "date", "hold", "status", "files", "bytes", "captured", "adapter", "note"]
        B.LN.write_text(p, "\t".join(old) + "\n")
        B.write_manifest([Probe(root=root).hold(cap())], p)
        lines = B.read_raw(p).rstrip("\n").split("\n")                              # (a row's last cell may be empty: keep its tab)
        self.assertEqual(lines[0].split("\t"), old); self.assertEqual(len(lines[1].split("\t")), len(old))
        p2 = os.path.join(root, "m2.tsv"); B.write_manifest([Probe(root=root).hold(cap("z"))], p2)
        self.assertIn("size_class", B.read_raw(p2).split("\n")[0].split("\t"))


class Decoding(unittest.TestCase):
    def test_decode_text(self):
        self.assertEqual(B.decode_text("a £ b\r\nc".encode("cp1252"))[:2], ("a £ b\nc", "cp1252"))
        t, enc, note = B.decode_text("café\n".encode("utf-8")); self.assertEqual((t, enc), ("café\n", "utf-8")); self.assertEqual(note, "decoded as UTF-8")
        self.assertEqual(B.decode_text("﻿x\r\n".encode("utf-8"))[0], "x\n")
        self.assertEqual(B.decode_text("café".encode("latin-1"), "iso-8859-1")[1], "iso-8859-1")
        self.assertIn("not valid utf-8", B.decode_text(b"\xa3")[2])

    def test_needs_text_copy(self):
        self.assertFalse(B.needs_text_copy(b"plain ascii\n")); self.assertTrue(B.needs_text_copy(b"crlf\r\n"))
        self.assertTrue(B.needs_text_copy(b"\xa3 cp1252")); self.assertTrue(B.needs_text_copy("é".encode("latin-1"), "iso-8859-1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
