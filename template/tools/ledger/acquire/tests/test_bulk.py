#!/usr/bin/env python3
"""Tests of the bulk-archive adapter on a local "archive" (file:// URL template, no network): mirror with an id filter, a failed
item, resume, the set README and items.jsonl, the FTS5 index and search."""
import csv, json, os, pathlib, unittest
from unittest import mock
import _common as C
from ledger.acquire import base as B, bulk as K


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


TEXTS = {"DOC-0001": "The committee met on the ninth of March and discussed the budget for the survey.",
         "DOC-0002": "A memorandum on the spillway gauge programme and its survey targets, with attachments.",
         "DOC-0003": "Handwritten notes: ~~ ;; .. xq zv ## @@ illegible scrawl ## ;;",
         "SKIP-0004": "Not part of the release (filtered out by the id filter)."}


class Bulk(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.arch = os.path.join(self.root, "remote-archive")
        for ident, t in TEXTS.items():
            os.makedirs(os.path.join(self.arch, ident))
            with open(os.path.join(self.arch, ident, f"{ident}_djvu.txt"), "w", encoding="utf-8", newline="") as f: f.write(t + "\r\n")
        self.index = os.path.join(self.root, "index.csv")
        with open(self.index, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["Document ESDN", "Document Title", "Creation Date", "Pages"])
            for i, ident in enumerate(list(TEXTS) + ["DOC-0005"], 1): w.writerow([ident, f"Title of {ident}", f"0{i}/03/1980", i])
        self.url = pathlib.Path(self.arch).as_uri() + "/{id}/{id}_djvu.txt"

    def mirror(self, b):
        sleeps = mock.patch.object(K.SM.time if K.SM else K.time, "sleep", lambda s: None)   # the missing item's retries, without waiting
        with sleeps:
            return b.mirror(self.index, "Document ESDN", self.url, id_filter=r"^DOC-", workers=1, pause=0,
                            columns={"title": "Document Title", "date": "Creation Date", "pages": "Pages"}, release="A test release")

    def test_mirror_index_search(self):
        b = K.BulkArchiveAdapter("test release", root=self.root, log=lambda m: None)
        rows = self.mirror(b)
        self.assertEqual(sorted((r["identifier"], r["status"]) for r in rows),
                         [("DOC-0001", "new"), ("DOC-0002", "new"), ("DOC-0003", "new"), ("DOC-0005", "failed")])
        f = os.path.join(self.root, "sources/archive/test-release")
        for ident in ("DOC-0001", "DOC-0002", "DOC-0003"):
            self.assertEqual(B.read_bytes(os.path.join(f, "items", ident + ".txt")), (TEXTS[ident] + "\r\n").encode("utf-8"))   # no header
        self.assertFalse(os.path.exists(os.path.join(f, "items", "SKIP-0004.txt")))
        self.assertIn("DOC-0005", B.read_raw(os.path.join(f, "FAILED.tsv")))
        recs = b.records(); self.assertEqual(recs["DOC-0002"]["title"], "Title of DOC-0002"); self.assertEqual(recs["DOC-0002"]["date"], "02/03/1980")
        readme = B.read_raw(os.path.join(f, "README.md"))
        self.assertTrue(readme.startswith("# Archive set: test-release\n\nA test release."))
        self.assertIn("| DOC-0001 | Title of DOC-0001 |", readme)
        # resume: nothing fetched again
        self.assertEqual([r for r in self.mirror(b) if r["status"] == "new"], [])
        self.assertEqual(b.index(), 3)
        total, hits = b.search('"spillway gauge"')
        self.assertEqual(total, 1); self.assertEqual(hits[0][0], "DOC-0002")
        total, hits = b.search("committee OR scrawl", min_quality=0.5)
        self.assertEqual([h[0] for h in hits], ["DOC-0001"])                    # the handwritten item's OCR quality is below 0.5

    def test_index_reader_formats(self):
        rows = K.read_index(self.index); self.assertEqual(rows[0]["Document ESDN"], "DOC-0001")
        j = os.path.join(self.root, "index.json")
        B.LN.write_text(j, json.dumps([{"id": "X-1"}])); self.assertEqual(K.read_index(j), [{"id": "X-1"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
