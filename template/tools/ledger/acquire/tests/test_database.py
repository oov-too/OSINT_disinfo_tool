#!/usr/bin/env python3
"""Tests of the database adapter on a sample SQLite database generated from three notes of the synthetic casebook corpus under a deliberately
different schema (records, attachments, transcript_rows, annotations; tests/make_sample_db.py): introspection, the proposed
mapping, the mapping file round trip, a dry run of five records with READMEs in the hold form, a full run, re-runs, a re-scan
against a changed schema and changed records; and the CSV engine with the five-record cap of the dry run."""
import copy, json, os, shutil, sqlite3, unittest
import _common as C
import make_sample_db
from ledger.acquire import base as B, database as D, _toml as T


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


def strip_comments(x):
    if isinstance(x, dict): return {k: strip_comments(v) for k, v in x.items() if k != "__comment__"}
    if isinstance(x, list): return [strip_comments(v) for v in x]
    return x


class Sample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.root = tempfile.mkdtemp(prefix="ledger-acquire-db-")
        with open(os.path.join(cls.root, "ledger.toml"), "w", encoding="utf-8", newline="\n") as f: f.write('[ledger]\nname = "db-test"\n')
        cls.db = make_sample_db.build(os.path.join(cls.root, "sample.db"))
        cls.eng = D.connect(cls.db)
        cls.rep = D.introspect(cls.eng, cls.db)
        cls.corpus = make_sample_db.corpus_root(cls.db)                    # the synthetic casebook corpus the database was built from
        cls.m = D.propose(cls.rep, name="sample records", source=cls.db, base_dir=cls.corpus)
        cls.mp = D.save_mapping(cls.m, os.path.join(cls.root, "mapping.toml"))

    @classmethod
    def tearDownClass(cls):
        cls.eng.close(); shutil.rmtree(cls.root, True)

    def tab(self, name): return next(t for t in self.rep["tables"] if t["name"] == name)

    # ---------------------------------------------------------------------------------------------------- introspection
    def test_introspection(self):
        self.assertEqual(sorted(t["name"] for t in self.rep["tables"]), ["annotations", "attachments", "records", "transcript_rows"])
        self.assertEqual((self.tab("records")["rows"], self.tab("attachments")["rows"], self.tab("annotations")["rows"]), (3, 4, 24))
        self.assertGreater(self.tab("transcript_rows")["rows"], 100)
        self.assertEqual(sorted(r["table"] for r in self.tab("records")["referenced_by"]), ["annotations", "attachments", "transcript_rows"])
        self.assertTrue(all(fk["declared"] for t in self.rep["tables"] for fk in t["foreign_keys"]))
        aired = next(c for c in self.tab("records")["columns"] if c["name"] == "aired")
        self.assertEqual((aired["shape"]["date"], aired["shape"]["date_format"], aired["shape"]["date_ambiguous"]), (1.0, "%d/%m/%Y", False))
        for t in self.rep["tables"]:
            for c in t["columns"]:
                if c["null_share"] is not None and c["null_share"] < 1: self.assertTrue(c["samples"], f"{t['name']}.{c['name']}")
        rp = os.path.join(self.root, "introspection.json")
        with B.LN.open_write(rp) as f: json.dump(self.rep, f)
        self.assertEqual(B.read_json(rp)["fingerprint"], self.rep["fingerprint"])

    # ---------------------------------------------------------------------------------------------------- proposal
    def test_proposal(self):
        m = self.m; F = m["fields"]
        self.assertEqual((m["record"]["table"], m["record"]["key"]), ("records", "rec_no"))
        self.assertEqual(F["identifier"]["column"], "rec_no")
        self.assertEqual(F["title"]["column"], "headline")
        self.assertEqual((F["date"]["column"], F["date"]["format"]), ("aired", "%d/%m/%Y")); self.assertNotIn("ambiguous", F["date"])
        self.assertEqual(F["venue"]["column"], "outlet")
        self.assertEqual(F["media_link"]["column"], "src_link")
        self.assertEqual(set(F["speaker_or_author"]["columns"]), {"participants", "presenter"})
        self.assertEqual((F["media_kind"]["column"], dict(F["media_kind"]["value_map"])), ("kind_code", {"VID": "video", "RPT": "document"}))
        alts = F["text"]["alternatives"]                              # the text's sources, tried in order per record (handoff H1)
        seg = alts[0]["segments"]
        self.assertEqual((seg["table"], seg["key"], seg["order"], seg["start"], seg["text"]), ("transcript_rows", "rec_no", "seq", "t_offset", "utterance"))
        self.assertEqual(seg["description"], "blurb")                 # the channel description cell, short beside the transcript (H2)
        self.assertEqual(alts[1], {"fallback": "media_text", "all": True})
        self.assertEqual([(x["table"], x["path"], x["mime"]) for x in m["media"]], [("attachments", "location", "mime")])
        a = m["annotations"][0]
        self.assertEqual((a["table"], a["register"], a["text"], a["author"], a["kind"]), ("annotations", "claims", "body", "coder", "code"))
        self.assertIn("their database", a["teller"]); self.assertEqual(a["reading"], "the group's reading")
        self.assertEqual(set(m["metadata"]["columns"]), {"keywords", "entered", "run_time"})
        self.assertIn({"column": "entered", "format": "%Y-%m-%d", "target": "metadata"}, m["dates"])
        for f, spec in F.items(): self.assertIn("confidence", spec, f)

    def test_mapping_file_round_trip(self):
        self.assertEqual(D.load_mapping(self.mp), json.loads(json.dumps(strip_comments(self.m))))
        self.assertTrue(B.read_raw(self.mp).startswith("# mapping.toml: the schema mapping of setup stage 2"))

    # ---------------------------------------------------------------------------------------------------- dry run
    def test_dry_run_five_records_in_the_hold_form(self):
        ad = D.DatabaseAdapter(self.mp, root=self.root, log=lambda m: None)
        rows = ad.dry_run(5)
        self.assertEqual([(r["identifier"], r["status"]) for r in rows], [("records/1", "new"), ("records/2", "new"), ("records/3", "new")])
        out = os.path.join(self.root, "wip", "db-dry-run", "sample-records")
        self.assertFalse(os.path.exists(os.path.join(self.root, "sources")))         # the hold proper is untouched by a dry run
        holds = {r["identifier"]: os.path.join(out, r["hold"]) for r in rows}
        for ident, f in holds.items():
            self.assertEqual(B.verify_hold(f), [], ident)
            readme = B.read_raw(os.path.join(f, "README.md"))
            self.assertIn(f"| Identifier | {ident} |", readme); self.assertIn("SELECT * FROM \"records\" WHERE \"rec_no\" = ", readme)
            self.assertIn("| record.json | held |", readme); self.assertIn("## Captures", readme)
            rj = B.read_json(os.path.join(f, "record.json"))
            self.assertEqual(rj["table"], "records"); self.assertIn("annotations", rj["related"])
            ann = B.read_json(os.path.join(f, "annotations.json"))
            self.assertEqual(len(ann), 8); self.assertTrue(all(a["register"] == "claims" and "their database" in a["teller"] for a in ann))
        h1 = B.load_hold(holds["records/1"])["record"]
        self.assertEqual((h1["media_kind"], h1["date"], h1["date_raw"], h1["text"], h1["venue"]),
                         ("video", "2019-11-05", "05/11/2019", "transcript.md", "Harrowmere Inquiry"))
        self.assertEqual(h1["speaker_or_author"].count("Petra Vanecek"), 1)
        self.assertEqual(h1["metadata"]["entered_iso"], "2026-10-20")
        t1 = B.read_raw(os.path.join(holds["records/1"], "transcript.md"))
        self.assertTrue(t1.startswith("# Transcript: Harrowmere Inquiry"))
        self.assertIn("- Captions: from their database (sample-records.transcript_rows", t1); self.assertIn("\n\n---\n\n**[00:00:", t1)
        self.assertEqual(C.sha(os.path.join(holds["records/1"], "Hx12Day12Aa.md")), C.sha(os.path.join(self.corpus, "transcripts/Hx12Day12Aa.md")))
        self.assertEqual(C.sha(os.path.join(holds["records/2"], "media-1-1.md")), C.sha(os.path.join(self.corpus, "transcripts/-HbrTalks20.md")))  # a leading '-' renamed
        h3 = B.load_hold(holds["records/3"])["record"]
        self.assertEqual((h3["media_kind"], h3["date"], h3["text"]), ("document", "2018-05-14", "report-on-the-harrowmere-event.txt"))
        self.assertTrue(os.path.isfile(os.path.join(holds["records/3"], "held-README.md")))   # their README attachment, not the hold's
        self.assertTrue(os.path.isfile(os.path.join(out, "sources/db/sample-records/README.md")))
        self.assertEqual(sorted(B.read_json(os.path.join(out, "sources/db/sample-records/state.json"))), ["records/1", "records/2", "records/3"])

    # ---------------------------------------------------------------------------------------------------- run and rescan
    def test_run_rerun_and_rescan(self):
        root = C.temp_root(self)
        ad = D.DatabaseAdapter(self.mp, root=root, log=lambda m: None)
        self.assertEqual([r["status"] for r in ad.run()], ["new"] * 3)
        self.assertEqual([r["status"] for r in ad.run()], ["unchanged"] * 3)
        q = B.read_raw(os.path.join(root, "sources/db/sample-records/queue.tsv")).strip().split("\n")
        self.assertEqual(len(q), 4)                                                        # header and the three new records
        self.assertEqual(B.read_raw(os.path.join(root, "sources/db/sample-records/mapping.toml")), B.read_raw(self.mp))
        self.assertTrue(D.rescan(self.mp, engine=self.eng)["unchanged"])

        def changed_copy(name, sql):
            p = os.path.join(root, name); shutil.copy(self.db, p)
            con = sqlite3.connect(p); con.executescript(sql); con.commit(); con.close()
            m2 = copy.deepcopy(D.load_mapping(self.mp)); m2["mapping"]["source"] = p
            eng = D.connect(p); self.addCleanup(eng.close)
            return D.rescan(m2, engine=eng, records=True, root=root)

        # the scheduled re-read: a record edited and a record added, the schema as it was (the copy's path differs: not a change)
        rep = changed_copy("edited.db", "UPDATE records SET headline = headline || ' (revised)' WHERE rec_no = 2;"
                                        "INSERT INTO records (rec_no, headline, aired, kind_code) VALUES (4, 'A fourth record', '01/02/2003', 'RPT');")
        self.assertTrue(rep["unchanged"]); self.assertEqual(rep["mapping_breaks"], []); self.assertEqual(rep["row_counts"]["records"], [3, 4])
        self.assertEqual((rep["records_new"], rep["records_changed"]), (["records/4"], ["records/2"]))
        # a schema change: a mapped column renamed and a column added; every record's rows now read differently
        rep = changed_copy("altered.db", "ALTER TABLE records RENAME COLUMN outlet TO channel_name; ALTER TABLE records ADD COLUMN licence TEXT;")
        self.assertFalse(rep["unchanged"])
        self.assertIn("column records.outlet is gone (mapped)", rep["mapping_breaks"])
        self.assertEqual(rep["columns_added"], {"records": ["channel_name", "licence"]}); self.assertEqual(rep["columns_removed"], {"records": ["outlet"]})
        self.assertIn("records.licence", rep["unmapped_new_columns"])
        self.assertEqual((rep["records_new"], rep["records_changed"]), ([], ["records/1", "records/2", "records/3"]))


class CSVSource(unittest.TestCase):
    def test_csv_folder_inferred_key_and_the_five_record_cap(self):
        root = C.temp_root(self); src = os.path.join(root, "export"); os.makedirs(src)
        rows = [f"{i},Item number {i} of the export,2024-01-{i:02d},Author {i % 3},{'A body of text. ' * 12}" for i in range(1, 9)]
        B.LN.write_text(os.path.join(src, "items.csv"), "id,title,published,author,body\n" + "\n".join(rows) + "\n")
        B.LN.write_text(os.path.join(src, "item_tags.csv"), "tag_id,items_id,tag\n" + "\n".join(f"{i},{(i % 8) + 1},tag{i % 2}" for i in range(1, 11)) + "\n")
        eng = D.connect("csv:" + src); self.addCleanup(eng.close)
        rep = D.introspect(eng, "csv:" + src)
        tags = next(t for t in rep["tables"] if t["name"] == "item_tags")
        self.assertEqual(tags["foreign_keys"], [dict(column="items_id", ref_table="items", ref_column="id", declared=False)])
        m = D.propose(rep, name="export", source="csv:" + src)
        self.assertEqual((m["record"]["table"], m["fields"]["title"]["column"], m["fields"]["date"]["column"]), ("items", "title", "published"))
        self.assertEqual(m["annotations"][0]["register"], "subjects")
        mp = D.save_mapping(m, os.path.join(root, "mapping.toml"))
        rows = D.DatabaseAdapter(mp, root=root, log=lambda m: None).dry_run()
        self.assertEqual(len(rows), 5)
        f = os.path.join(root, "wip/db-dry-run/export", rows[0]["hold"])
        self.assertEqual(B.verify_hold(f), []); self.assertEqual(B.load_hold(f)["record"]["text"], "text.md")

    def test_engines(self):
        with self.assertRaises(NotImplementedError) as cm: D.connect("postgresql://user:secret@db.example/research")
        self.assertIn("psycopg", str(cm.exception))
        self.assertEqual(D.redact("postgresql://user:secret@db.example/research"), "postgresql://user:***@db.example/research")
        self.assertEqual({e["status"] for e in D.ENGINE_TABLE if e["engine"] in ("SQLite", "CSV export")}, {"built"})


if __name__ == "__main__":
    import unittest as U
    U.main(verbosity=2)
