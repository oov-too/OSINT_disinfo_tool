#!/usr/bin/env python3
"""Tests of the database adapter on a mixed catalogue (neutral synthetic data written by the test; the traps of phase 6a's stranger
database, wip/platform-phase6a/handoffs.md): the text in three places by kind (H1), chapter labels and the description block (H2),
a date split by precision across columns (H3), the proposer's kind map, author separator, register and identifier (H6), every text
attachment named in hold.json (H8); the old single-source forms still run; the new forms round-trip through mapping.toml and are
seen by the re-scan."""
import copy, json, os, sqlite3, unittest
import _common as C
from ledger.acquire import base as B, database as D, transcribe as TR


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


CODES = ["VID", "WEB", "PST", "THR", "DOC", "SCN", "CAN", "ARC"]
KINDS = {"VID": "video", "WEB": "web-page", "PST": "post", "THR": "thread", "DOC": "document", "SCN": "document", "CAN": "canon", "ARC": "archive-item"}
WORDS = "river stone harbour lantern meadow orchard granite willow beacon compass ledger canvas".split()


def prose(n, seed):
    return " ".join(WORDS[(seed * 7 + i * 3) % len(WORDS)] for i in range(n)) + "."


def build(root):
    """The catalogue: 12 records, eight kind codes (the first five distinct values seen are VID WEB PST THR DOC, so a five-value
    sample never sees SCN CAN ARC), attachments in a store folder, transcript rows with chapter labels for one video, annotations and
    people with no declared key."""
    db = os.path.join(root, "catalogue.sqlite"); store = os.path.join(root, "store"); os.makedirs(store)
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE records (id INTEGER PRIMARY KEY, acc_ref TEXT UNIQUE NOT NULL, kind_code TEXT, headline TEXT, published_on TEXT,
                              pub_month TEXT, pub_year INTEGER, outlet TEXT, author_field TEXT, body TEXT, src_url TEXT, entered_at TEXT, cataloguer TEXT);
        CREATE TABLE attachments (att_id INTEGER PRIMARY KEY, record_id INTEGER REFERENCES records(id), path TEXT, mime TEXT, bytes INTEGER);
        CREATE TABLE transcript_rows (row_id INTEGER PRIMARY KEY, record_id INTEGER REFERENCES records(id), seq INTEGER, started_at_seconds INTEGER,
                                      spoken TEXT, section_label TEXT);
        CREATE TABLE annotations (id INTEGER PRIMARY KEY, record_id INTEGER, coder TEXT, coded_on TEXT, claim_text TEXT, speaker TEXT, tag TEXT);
        CREATE TABLE people (pid INTEGER PRIMARY KEY, record_id INTEGER, written_as TEXT, normal_form TEXT, role_note TEXT);
    """)
    order = ["VID", "WEB", "PST", "THR", "DOC", "VID", "SCN", "CAN", "ARC", "WEB", "VID", "DOC"]
    dates = {1: "03/24/2021", 2: "11/05/2019", 3: "07/14/2020", 4: "01/30/2022", 6: "02/16/2023", 7: None, 8: None, 9: "12/19/2018",
             10: "04/18/2024", 11: "09/27/2017", 12: None, 5: "06/21/2016"}
    split = {7: ("Sep", 1952), 8: (None, 1908), 12: (None, None)}            # month and year; year only; no date at all
    for i, code in enumerate(order, 1):
        rid = 100 + i
        body = None
        if code == "VID": body = "Line one of the channel description.\n\nSee the links below." if i != 6 else "> Already quoted.\n>\n> Second line."
        if code in ("WEB", "PST", "THR"): body = prose(120, i)
        pm, py = split.get(i, (None, None))
        con.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, f"RG/2024/{i:04d}", code, f"Item {i}: a {KINDS[code]}", dates[i], pm, py, f"Outlet {i % 3}",
                     ["Doe, Jane / Roe, Richard", "Poe, Edgar A.", "Smith, Ann / Jones, Bo / Lee, Cy", "Moe, Max"][i % 4], body,
                     f"https://example.org/item/{i}", f"2026-10-{(i % 9) + 10}T08:00:00", "AK"))
        if code == "VID":
            for s in range(6):
                label = (f"Chapter {1 + s // 3}: {'Opening' if s < 3 else 'Middle'}") if i == 1 else None
                con.execute("INSERT INTO transcript_rows (record_id, seq, started_at_seconds, spoken, section_label) VALUES (?,?,?,?,?)",
                            (rid, s + 1, 30 * s, prose(125, i * 10 + s), label))
        files = {"DOC": ["report.pdf", "report.txt", "README.md"], "SCN": ["scan-a.txt", "scan-b.txt", "README.md"],
                 "CAN": ["volume-2.txt", "volume-1.txt"], "ARC": ["item-a.txt", "item-b.txt"]}.get(code, [])
        for fn in files:
            d = os.path.join(store, f"RG-{i:04d}"); os.makedirs(d, exist_ok=True); p = os.path.join(d, fn)
            data = (b"%PDF-1.4 stand-in\n" if fn.endswith(".pdf") else (f"{fn} of item {i}\n" + prose(60, i)).encode("utf-8"))
            with open(p, "wb") as f: f.write(data)
            con.execute("INSERT INTO attachments (record_id, path, mime, bytes) VALUES (?,?,?,?)",
                        (rid, f"store/RG-{i:04d}/{fn}", "application/pdf" if fn.endswith(".pdf") else ("text/markdown" if fn.endswith(".md") else "text/plain"), len(data)))
        for a in range(3):
            con.execute("INSERT INTO annotations (record_id, coder, coded_on, claim_text, speaker, tag) VALUES (?,?,?,?,?,?)",
                        (rid, ["AK", "MB"][a % 2], f"2026/10/{10 + a:02d}", prose(14, i + a), "Jane Doe", "OWN_ROLE"))
        con.execute("INSERT INTO people (record_id, written_as, normal_form, role_note) VALUES (?,?,?,?)", (rid, "J. Doe", "Doe, Jane", "author"))
    con.commit(); con.close()
    return db


class Mixed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.root = tempfile.mkdtemp(prefix="ledger-acquire-mixed-")
        with open(os.path.join(cls.root, "ledger.toml"), "w", encoding="utf-8", newline="\n") as f: f.write('[ledger]\nname = "mixed"\n')
        cls.db = build(cls.root)
        cls.eng = D.connect(cls.db)
        cls.rep = D.introspect(cls.eng, cls.db)
        cls.m = D.propose(cls.rep, name="mixed", source=cls.db, engine=cls.eng)
        cls.mp = D.save_mapping(cls.m, os.path.join(cls.root, "mapping.toml"))
        cls.rows = D.DatabaseAdapter(cls.mp, root=cls.root, log=lambda m: None).dry_run(n=100)
        cls.out = os.path.join(cls.root, "wip", "db-dry-run", "mixed")
        cls.by = {r["identifier"]: os.path.join(cls.out, r["hold"]) for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        import shutil
        cls.eng.close(); shutil.rmtree(cls.root, True)

    def hold(self, i): return B.load_hold(self.by[f"RG/2024/{i:04d}"])
    def read(self, i, name): return B.read_raw(os.path.join(self.by[f"RG/2024/{i:04d}"], name))

    # ---------------------------------------------------------------------------------------------------- H6: the proposer
    def test_kind_map_from_every_distinct_value(self):
        recs = next(t for t in self.rep["tables"] if t["name"] == "records")
        kc = next(c for c in recs["columns"] if c["name"] == "kind_code")
        self.assertEqual(len(kc["samples"]), 5); self.assertEqual(sorted(v for v, n in kc["values"]), sorted(CODES))
        self.assertEqual(dict(self.m["fields"]["media_kind"]["value_map"]), KINDS)
        self.assertEqual({D._guess_kind(v) for v in ("thread", "Forum thread", "canon", "Scripture", "archive item", "pst")},
                         {"thread", "canon", "archive-item", "post"})

    def test_author_separator_identifier_register(self):
        F = self.m["fields"]
        self.assertEqual((F["speaker_or_author"]["columns"], F["speaker_or_author"]["split"]), (["author_field"], " / "))
        self.assertEqual((F["identifier"]["column"], F["identifier"]["prefix"], F["identifier"]["alternatives"]), ("acc_ref", "", ["id"]))
        anns = {a["table"]: a for a in self.m["annotations"]}
        self.assertEqual((anns["annotations"]["register"], anns["annotations"]["text"], anns["annotations"]["author"], anns["annotations"]["date"]),
                         ("claims", "claim_text", "coder", "coded_on"))
        self.assertEqual((anns["people"]["register"], anns["people"]["text"]), ("people", "written_as"))   # as written, not the normal form
        self.assertIn("id", self.m["metadata"]["columns"]); self.assertNotIn("body", self.m["metadata"]["columns"])

    def test_separator_rules(self):
        col = lambda seps, vals: {"shape": {"separators": seps}, "samples": vals}
        self.assertEqual(D._separator([col({"; ": 3, ";": 3}, [])]), ";")
        self.assertEqual(D._separator([col({", ": 4}, ["Doe, Jane", "Roe, Rick"])]), ";")            # a lone comma is Surname, Given
        self.assertEqual(D._separator([col({", ": 2}, ["Ann, Bo, Cy", "Di, Ed, Fay"])]), ", ")

    # ---------------------------------------------------------------------------------------------------- H3: the date
    def test_date_chain_proposed(self):
        d = self.m["fields"]["date"]
        self.assertEqual(d["column"], "published_on"); self.assertEqual(d["format"], "%m/%d/%Y")
        self.assertEqual([dict(s) for s in d["alternatives"]], [{"column": "published_on", "format": "%m/%d/%Y"},
                                                               {"template": "{pub_month} {pub_year}", "format": "%b %Y"},
                                                               {"column": "pub_year", "format": "%Y"}])
        self.assertNotIn("entered_at", [s.get("column") for s in d["alternatives"]])     # the catalogue's entry time is never the date
        self.assertIn({"column": "entered_at", "format": "%Y-%m-%dT%H:%M:%S", "target": "metadata"}, self.m["dates"])

    def test_dates_by_precision_with_raw_and_basis(self):
        r1 = self.hold(1)["record"]
        self.assertEqual((r1["date"], r1["date_raw"]), ("2021-03-24", "03/24/2021"))
        self.assertEqual(r1["metadata"]["date_basis"], "records.published_on (%m/%d/%Y)")
        r7 = self.hold(7)["record"]
        self.assertEqual((r7["date"], r7["date_raw"]), ("1952-09", "Sep 1952"))
        self.assertIn("template", r7["metadata"]["date_basis"]); self.assertIn("%b %Y", r7["metadata"]["date_basis"])
        r8 = self.hold(8)["record"]
        self.assertEqual((r8["date"], r8["date_raw"]), ("1908", "1908")); self.assertEqual(r8["metadata"]["date_basis"], "records.pub_year (%Y)")
        r12 = self.hold(12)["record"]
        self.assertIsNone(r12["date"]); self.assertTrue(r12["metadata"]["date_basis"].startswith("no date: records.published_on empty"))

    def test_formats_list_on_one_source(self):
        ad = D.DatabaseAdapter(self.m, root=self.root, engine=self.eng)
        spec = {"column": "d", "formats": ["%d/%m/%Y", "%Y"]}
        self.assertEqual(ad._date(spec, {"d": "1931"}, {})[:2], ("1931", "1931"))
        self.assertEqual(ad._date(spec, {"d": "24/03/2021"}, {})[0], "2021-03-24")
        iso, raw, basis = ad._date(spec, {"d": "spring 1931"}, {})
        self.assertIsNone(iso); self.assertEqual(raw, "spring 1931"); self.assertIn("did not parse", basis)

    # ---------------------------------------------------------------------------------------------------- H1: the text by kind
    def test_text_sources_proposed_in_order(self):
        alts = self.m["fields"]["text"]["alternatives"]
        self.assertEqual(list(alts[0]), ["segments"])
        seg = alts[0]["segments"]
        self.assertEqual((seg["table"], seg["order"], seg["start"], seg["text"], seg["heading"], seg["description"]),
                         ("transcript_rows", "seq", "started_at_seconds", "spoken", "section_label", "body"))
        self.assertEqual(alts[1:], [{"column": "body"}, {"fallback": "media_text", "all": True}])

    def test_each_kind_takes_its_own_text(self):
        for i, code in enumerate(["VID", "WEB", "PST", "THR", "DOC", "VID", "SCN", "CAN", "ARC", "WEB", "VID", "DOC"], 1):
            r = self.hold(i)["record"]
            self.assertEqual(r["media_kind"], KINDS[code], i)
            want = {"VID": "transcript.md", "WEB": "text.md", "PST": "text.md", "THR": "text.md"}.get(code)
            if want: self.assertEqual(r["text"], want, i)
            self.assertTrue(r["text"], i); self.assertEqual(B.verify_hold(self.by[f"RG/2024/{i:04d}"]), [], i)
        self.assertEqual(self.read(2, "text.md").strip(), prose(120, 2))
        self.assertEqual(self.hold(2)["record"]["metadata"]["text_basis"], "records.body")

    # ---------------------------------------------------------------------------------------------------- H2: chapters and description
    def test_chapters_and_description_in_the_transcript(self):
        t = self.read(1, "transcript.md")
        body = t.split("\n---\n\n", 1)[1]
        self.assertTrue(body.startswith("### Chapter 1: Opening\n\n**[00:00:00]** "))
        self.assertEqual(body.count("### Chapter"), 2); self.assertIn("\n\n### Chapter 2: Middle\n\n**[00:01:30]** ", body)
        self.assertTrue(t.endswith("\n\n---\n\n## Video description (as posted by the channel)\n\n> Line one of the channel description.\n>\n> See the links below.\n"))
        self.assertIn("chapters from section_label", t)
        t6 = self.read(6, "transcript.md")                               # a description already in the quoted form is not quoted twice
        self.assertTrue(t6.endswith("## Video description (as posted by the channel)\n\n> Already quoted.\n>\n> Second line.\n"))
        self.assertNotIn("body", self.hold(1)["record"]["metadata"])     # the description closes the transcript, not the metadata

    # ---------------------------------------------------------------------------------------------------- H8: every text attachment
    def test_texts_list_names_every_text_attachment(self):
        self.assertEqual(self.hold(8)["texts"], ["volume-2.txt", "volume-1.txt"])                  # attachment order
        self.assertEqual(self.hold(8)["record"]["text"], "volume-2.txt")
        self.assertEqual(self.hold(7)["texts"], ["scan-a.txt", "scan-b.txt"])                    # the provenance README is not a text
        self.assertEqual(self.hold(5)["texts"], ["report.txt"])
        self.assertTrue(os.path.isfile(os.path.join(self.by["RG/2024/0005"], "held-README.md")))
        self.assertIn("| Texts | volume-2.txt; volume-1.txt |", self.read(8, "README.md"))
        self.assertNotIn("texts", self.hold(2))

    # ---------------------------------------------------------------------------------------------------- compatibility, round trip, rescan
    def test_mapping_round_trip_with_alternatives(self):
        back = D.load_mapping(self.mp)
        self.assertEqual(back["fields"]["text"]["alternatives"], json.loads(json.dumps(self.m["fields"]["text"]["alternatives"])))
        self.assertEqual(back["fields"]["date"]["alternatives"], json.loads(json.dumps(self.m["fields"]["date"]["alternatives"])))

    def test_old_single_source_forms_still_run(self):
        m = copy.deepcopy(D.load_mapping(self.mp))
        seg = dict(m["fields"]["text"]["alternatives"][0]["segments"]); seg.pop("heading"); seg.pop("description")
        m["fields"]["text"] = {"segments": seg, "fallback": "media_text"}                         # the form of phase 3's first turn
        m["fields"]["date"] = {"column": "published_on", "format": "%m/%d/%Y"}
        m["metadata"]["columns"] = m["metadata"]["columns"] + ["body", "pub_month", "pub_year"]  # as a first-turn proposal listed them
        m["mapping"]["database"] = "mixed-legacy"
        rows = D.DatabaseAdapter(m, root=self.root, engine=self.eng, log=lambda x: None).dry_run(n=100)
        by = {r["identifier"]: B.load_hold(os.path.join(self.root, "wip/db-dry-run/mixed-legacy", r["hold"])) for r in rows}
        self.assertEqual(by["RG/2024/0001"]["record"]["text"], "transcript.md")
        self.assertEqual(by["RG/2024/0008"]["record"]["text"], "volume-2.txt"); self.assertNotIn("texts", by["RG/2024/0008"])
        self.assertIsNone(by["RG/2024/0002"]["record"]["text"])           # one source: a web record with no rows and no text attachment
        self.assertIsNone(by["RG/2024/0007"]["record"]["date"])
        self.assertIn("body", by["RG/2024/0002"]["record"]["metadata"])

    def test_rescan_sees_the_new_sources(self):
        import shutil
        p = os.path.join(self.root, "renamed.sqlite"); shutil.copy(self.db, p)
        con = sqlite3.connect(p)
        con.executescript("ALTER TABLE records RENAME COLUMN pub_month TO month_of_pub; ALTER TABLE transcript_rows RENAME COLUMN section_label TO chapter;")
        con.commit(); con.close()
        m = copy.deepcopy(D.load_mapping(self.mp)); m["mapping"]["source"] = p
        eng = D.connect(p); self.addCleanup(eng.close)
        rep = D.rescan(m, engine=eng)
        self.assertIn("column records.pub_month is gone (mapped)", rep["mapping_breaks"])
        self.assertIn("column transcript_rows.section_label is gone (mapped)", rep["mapping_breaks"])


class Form(unittest.TestCase):
    def test_headings_and_description_in_format_transcript(self):
        segs = [(0, 5, "one two", "Part A"), (5, 5, "three", "Part A"), (10, 5, "four", "Part B")]
        t = TR.format_transcript("T", "C", "U", "2026-01-01", "x", segs, description="Hello\n\nWorld")
        self.assertIn("---\n\n### Part A\n\n**[00:00:00]** one two three\n\n### Part B\n\n**[00:00:10]** four\n", t)
        self.assertIn("- Length: ~00:00:15, ~6 words\n", t)                                 # headings are not counted as words
        self.assertTrue(t.endswith("**[00:00:10]** four\n\n---\n\n## Video description (as posted by the channel)\n\n> Hello\n>\n> World\n"))
        plain = TR.format_transcript("T", "C", "U", "2026-01-01", "x", [(0, 5, "one two"), (5, 5, "three")])
        self.assertNotIn("###", plain); self.assertNotIn("Video description", plain)

    def test_description_block_is_fetch_descriptions(self):
        """The block equals what tools/fetch_description.py appends (its construction, read from its source)."""
        src = B.read_raw(os.path.join(C.TOOLS, "fetch_description.py"))
        self.assertIn('block = "\\n\\n---\\n\\n## Video description (as posted by the channel)\\n\\n" + "\\n".join(("> " + l) if l.strip() else ">" for l in desc.split("\\n")) + "\\n"', src)
        desc = "A\n\nB c"
        theirs = "\n\n---\n\n## Video description (as posted by the channel)\n\n" + "\n".join(("> " + l) if l.strip() else ">" for l in desc.split("\n")) + "\n"
        self.assertEqual(TR.description_block(desc), theirs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
