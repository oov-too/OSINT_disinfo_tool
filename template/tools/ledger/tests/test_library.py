#!/usr/bin/env python3
"""Tests of the parser library and the paths module (phase 2 of tools/platform-plan.md) on the synthetic casebook corpus
(tools/ledger/tests/casebook_corpus.py, phase 7a): a project folder with notes, transcripts, held sets, a pack and its own folder rows,
built in a temporary folder, so the tests name nothing real and run on any machine. Writes only under temporary folders.
  python3 tools/ledger/tests/test_library.py        (or python3 -m unittest discover tools/ledger/tests)"""
import os, sys, json, shutil, tempfile, unittest, glob

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, TOOLS); sys.path.insert(0, HERE)
from ledger import notes as LN
from ledger import paths as LP
import casebook_corpus as CC

_TMP = tempfile.mkdtemp(prefix="ledger-library-test-")
ROOT = CC.build(os.path.join(_TMP, "project"))["root"]
LONG = "books/sources/web/harrowmere-2018/harrowmere-inquiry-hearing-day-12-evidence-of-the-site-engineer-on-the-2009-pour-and-the-site-diary-exhibit-hi-114-transcription.md"   # a held file over the stem cap
for rel, text in ((LONG, "x\n"), ("books/sources/web/harrowmere-2018/HI-114-Site-Diary.txt", "the site diary\n")):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as _f: _f.write(text)
LP.set_root(ROOT)
LP.write_alias_table(LP.build_alias_rows(today="2026-10-22"))

HELD = sorted(CC.NOTES)


def tearDownModule(): shutil.rmtree(_TMP, True)


class LineEndings(unittest.TestCase):
    """Readers normalise line endings; writers emit LF (portability rule)."""

    def variants(self, text):
        return {"crlf": text.replace("\n", "\r\n"), "cr": text.replace("\n", "\r"), "bom": "﻿" + text, "bom+crlf": "﻿" + text.replace("\n", "\r\n")}

    def test_held_notes_parse_identically_under_any_line_ending(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in HELD:
                src = os.path.join(ROOT, rel); base = LN.parse_note(src, ROOT)
                text = open(src, encoding="utf-8").read()
                for k, v in self.variants(text).items():
                    p = os.path.join(d, os.path.basename(rel))
                    with open(p, "w", encoding="utf-8", newline="") as f: f.write(v)
                    got = LN.parse_note(p, ROOT)            # the project root: its pack names the object watch's heading and column
                    got["file"] = base["file"]
                    self.assertEqual(got, base, f"{rel} as {k}")

    def test_writers_emit_lf(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.md")
            LN.write_text(p, "a\nb\n"); LN.append_text(p, "c\n")
            with LN.open_append(p) as f: f.write("d\n")
            self.assertEqual(open(p, "rb").read(), b"a\nb\nc\nd\n")
            LN.write_lines(p, ["x", "y"]); self.assertEqual(open(p, "rb").read(), b"x\ny")

    def test_iter_lines_and_first_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.md")
            with open(p, "wb") as f: f.write("﻿# T\r\n| a | b |\rlast".encode("utf-8"))
            self.assertEqual(list(LN.iter_lines(p)), ["# T\n", "| a | b |\n", "last"])
            self.assertEqual(LN.first_line(p), "# T\n")
            self.assertEqual(LN.read_lines(p), ["# T", "| a | b |", "last"])


class Forms(unittest.TestCase):
    NOTE = "\n".join([
        "# Title: a test", "", "| | |", "|---|---|", "| **Channel** | C |", "| **Subjects** | [x](../subjects/infrastructure-safety.md) |", "| **Tags** | a, b |", "",
        "## Claims ledger", "", "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|",
        "| 1 | 0:00:01 | A | other | c1 | hearsay | open | attribution: told; chain: 2: A <- B (basis not stated). More. |",
        "| 2 | 0:00:02 | A | other | c2 | host | n/a |", "",
        "## Dated timeline", "", "| # | Date (as stated) | Sortable | Event | Speaker, basis (time) | Chain | Database link | Agreement |", "|---|---|---|---|---|---|---|---|",
        "| 1 | 1947 | 1947 | e | A | 1: A (unsourced) | new | new |", "| 1.1 | about 12,000 years ago | ~-10000 | e2 | A | x | new | drifts: older |", "",
        "## Open questions", "", "| # | Kind | Question | Bears on | What would settle it | Status | Answer | Answered by | Answered on |", "|---|---|---|---|---|---|---|---|---|",
        "| 1 | question | q? | other; 0:00:01 | unknown | open | | | |", "",
        "## Cross-checks", "", "| # | Kind | This note (time, row, claim) | Elsewhere (note, row) | Verdict | Note |", "|---|---|---|---|---|---|",
        "| 1 | contradicts | t | [o](o.md) claims 2 | direct | point: date; settled 2026-10-01: x; was: extends |", ""])

    def test_parse_note_forms(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.md"); LN.write_text(p, self.NOTE)
            o = LN.parse_note(p, d)
            self.assertEqual(o["meta"]["title"], "Title: a test")
            self.assertEqual(o["subjects"], ["infrastructure-safety"]); self.assertEqual(o["tags"], ["a", "b"])
            self.assertEqual(o["claims"][0][8:], ["told", "2: A <- B (basis not stated)"])
            self.assertEqual(len(o["claims"][1]), 10)
            self.assertEqual(o["tl"][1][0:5], ("1.1", 1.1, "about 12,000 years ago", "~-10000", "0999990000-00-00"))
            self.assertEqual(o["tl"][1][5], 1); self.assertEqual(o["tl"][1][11], "drifts")
            self.assertEqual(o["oq"][0][:3], (1, "question", "note"))   # no Asked by column: "note" is filled in
            self.assertEqual(o["xc"][0][6:], ("date", "2026-10-01", "", "extends"))
            self.assertIn(("audit", "missing", 0), o["report"])

    def test_sections_and_tables(self):
        L = self.NOTE.split("\n")
        self.assertEqual(LN.section_start(L, "## dated timeline"), 15)
        self.assertEqual(LN.section_bounds(L, "## Open"), (22, 28))
        self.assertEqual(LN.section_span(L, "Open questions"), (22, 28))
        self.assertIsNone(LN.section_span(L, "Open"))
        t = LN.find_table(L, 8, ("#", "time", "speaker")); self.assertEqual((t.header_line, t.row_lines), (10, [12, 13]))
        self.assertIsNone(LN.find_table(L, 8, ("nonexistent",)))
        self.assertEqual(len(LN.tables(L, 0, len(L))), 5)
        b = LN.hash_table_bounds(L, "## dated timeline"); self.assertEqual(b, (15, 17, 19, 21))
        txt = self.NOTE
        self.assertTrue(LN.section_text(txt, "Open").startswith("\n| # | Kind |"))
        self.assertEqual(LN.loose_table(LN.section_text(txt, "Cross-checks"))[0]["verdict"], "direct")
        self.assertEqual(LN.first_table(LN.section_text(txt, "Claims ledger"))[1]["#"], "2")
        self.assertEqual([h for h, _ in LN.sections_text(txt)], ["Claims ledger", "Dated timeline", "Open questions", "Cross-checks"])
        self.assertEqual(LN.line_sections(L)[14], "Claims ledger")
        self.assertEqual(LN.meta_rows(L)[0][:2], ("Channel", "C"))

    def test_keys_and_citations(self):
        self.assertEqual(LN.sort_key("2008-07-18"), "1000002008-07-18")
        self.assertEqual(LN.sort_key("~1990s"), "1000001990-00-00")
        self.assertEqual(LN.sort_key("?"), LN.UNDATED_KEY)
        self.assertEqual(LN.date_key("2010-12", end=True), "1000002010-12-31")
        self.assertIsNone(LN.date_key("July 2010"))
        self.assertEqual(LN.citations("[gao-x tl 3, 4.1] and [b claims 9]"), [("gao-x", "tl", "3"), ("gao-x", "tl", "4.1"), ("b", "claims", "9")])
        self.assertEqual(LN.cite("people", "v", "A B"), "[v people A B]")
        self.assertEqual(LN.attribution_chain("attribution: none stated; chain: 1: G (unsourced). Rest"), ("none stated", "1: G (unsourced)"))
        self.assertEqual(LN.row_numbers("| 1 | a |\n| 22 | b |\nx | 3 |"), [1, 22])


class Paths(unittest.TestCase):
    def test_alias_table_resolves(self):
        if not LP.aliases(): self.skipTest("no sources/aliases.tsv")
        r = lambda p: os.path.relpath(LP.resolve(p), ROOT).replace(os.sep, "/")
        self.assertEqual(r("sources/video/yt--HbrTalks20.md"), "transcripts/-HbrTalks20.md")
        self.assertEqual(r("sources/text/charter-1888.txt"), "books/sources/charter-1888.txt")
        self.assertEqual(r("sources/web/blog"), "books/sources/web/blog")
        self.assertEqual(r("sources/sets/harrowmere-2018/README.md"), "books/sources/web/harrowmere-2018/README.md")   # the pack's row
        self.assertEqual(r("books/sources/charter-1888.txt"), "books/sources/charter-1888.txt")   # no alias: itself
        some = "HI-114-Site-Diary.txt"                                                           # a held name with upper case
        self.assertEqual(r("sources/sets/harrowmere-2018/" + some.lower()), "books/sources/web/harrowmere-2018/" + some)
        self.assertEqual(LP.layout_name("transcripts/-HbrTalks20.md"), "sources/video/yt--HbrTalks20.md")
        self.assertEqual(LP.layout_name("books/sources/web/harrowmere-2018/" + some), "sources/sets/harrowmere-2018/" + some.lower())
        self.assertEqual([a for a, t, w in LP.pack_layout_folders()], ["sources/sets/harrowmere-2018/"])
        self.assertEqual(LP.check_aliases(), [])

    def test_every_alias_target_exists_and_every_transcript_has_one(self):
        if not LP.aliases(): self.skipTest("no sources/aliases.tsv")
        targets = {t for a, t in LP.aliases().items() if not a.endswith("/")}
        for fn in os.listdir(os.path.join(ROOT, "transcripts")):
            if fn.endswith(".md"): self.assertIn("transcripts/" + fn, targets)

    def test_name_rules(self):
        self.assertEqual(LP.name_problems("books/sources/charter-1888.txt"), [])
        self.assertTrue(LP.name_problems("books/sources/a:b.txt"))
        self.assertTrue(LP.name_problems("books/sources/-x.txt"))
        self.assertTrue(LP.name_problems("books/sources/aux.txt"))
        self.assertTrue(LP.name_problems("books/sources/x.txt."))
        self.assertTrue(LP.name_problems("books/sources/" + "a" * 81 + ".txt"))
        self.assertTrue(LP.name_problems("x/" * 90 + "a.txt"))
        self.assertEqual(LP.name_problems("transcripts/-HbrTalks20.md", kind="youtube"), [])
        self.assertTrue(LP.name_problems("transcripts/not-an-id.md", kind="youtube"))
        self.assertEqual(LP.hold_name("New folder:bad?.txt"), "New folder-bad.txt")
        self.assertEqual(LP.hold_name("CON.txt"), "CON-file.txt")
        n = LP.hold_name("w" * 50 + "-" + "x" * 50 + ".txt"); self.assertLessEqual(len(n), LP.BASENAME_CAP); self.assertEqual(LP.name_problems("books/sources/" + n), [])
        self.assertEqual(LP.slug("The Memo Nobody Read: a Warning About Harrowmere Two Years Before the Flood, and What the Inquiry Made of It Later"),
                         "the-memo-nobody-read-a-warning-about-harrowmere-two-years-before-the-flood-and")
        self.assertLessEqual(len(LP.slug("word " * 40)), LP.STEM_CAP)

    def test_new_hold(self):
        self.assertEqual(LP.new_hold("books/sources/charter-1888.txt"), "books/sources/charter-1888.txt")   # exists: never renamed
        self.assertEqual(LP.new_hold(LONG), LONG)                                         # exists, over the cap: kept
        self.assertEqual(LP.new_hold("books/sources/p2-new-hold-test.txt"), "books/sources/p2-new-hold-test.txt")
        self.assertNotEqual(LP.new_hold("books/sources/p2:bad?.txt"), "books/sources/p2:bad?.txt")
        with self.assertRaises(SystemExit): LP.new_hold("transcripts/bad id.md", kind="youtube")
        with self.assertRaises(SystemExit): LP.new_hold("books/sources/p2:bad?.txt", fix=False)


class Hold(unittest.TestCase):
    def test_safe_slug_and_hold_path(self):
        from ledger import hold as H
        self.assertEqual(H.safe_slug("Petra Vaněček: Evidence to the Inquiry"), "petra-vanecek-evidence-to-the-inquiry")
        self.assertEqual(H.safe_slug("CON"), "con-file"); self.assertEqual(H.safe_slug(""), "untitled")
        self.assertLessEqual(len(H.safe_slug("word " * 60)), H.STEM_CAP)
        self.assertEqual(H.hold_path("video", "-HbrTalks20", ""), "sources/video/yt--HbrTalks20")
        self.assertEqual(H.hold_path("web/Ostley Gazette", "2017-10-09", "Memo: Two Years On"), "sources/web/ostley-gazette/2017-10-09-memo-two-years-on")
        p = H.hold_path("document/" + "s" * 40, "x" * 80, "t" * 80)
        self.assertLessEqual(len(p), H.PATH_CAP - 1 - H.FILE_ROOM); self.assertEqual(LP.name_problems(p + "/a.txt"), [])
        with self.assertRaises(ValueError): H.hold_path("nope", "x", "")
        with self.assertRaises(ValueError): H.hold_path("", "x", "")


class ActorRegister(unittest.TestCase):
    """Form A on a synthetic register (the actor table, a headerless continuation, a table that is neither, the polity statements)
    and a synthetic clusters page; the placement rules are those tools/build_graph_data.py applied to the page (2026-10-22)."""
    PAGE = "\r\n".join([
        "# Register", "", "## Actors", "",
        "| # | Kind (teller's name) | Body | Teller and note row | Firsthand / relayed (chain) | Polity (member / outside) | Matches cluster |",
        "|---|---|---|---|---|---|---|",
        "| 1 | Small fronts | short | Ann Teller | firsthand | member: the Council (as told) | B1 |",
        "| 2 | Tall fronts, unnamed | tall | Bob | relayed: Bob <- Ann | opposed to the Council | none |",
        "| 3 | Robed figures | robes | Cy | firsthand | unknown | none |",
        "", "### Appended", "",
        "| 4 | A front at the door | small | Dee | firsthand | outside: the Council | B1, B9 |",
        "", "| Field | Value |", "|---|---|", "| a | b |", "",
        "## Statements", "",
        "| # | Teller | Body (federation, council) | Inside / members | Outside | Opposed | Humanity's standing | Time | Quote | Chain | Upstream |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        "| F1 | Ann | council: the Council | fronts | humans | none | ward | 1990 | \"we\" | firsthand | Ann |",
        "| F2 | Bob | unknown | fronts | | | | | | | |", ""])
    CLUSTERS = "| Code | Name |\n|---|---|\n| B1 | **The fronts**; small |\n| B2 | Others |\n"

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = os.path.join(self.d, "register.md"); self.cl = os.path.join(self.d, "clusters.md")
        open(self.reg, "w", encoding="utf-8", newline="").write(self.PAGE); open(self.cl, "w", encoding="utf-8").write(self.CLUSTERS)

    def test_parse_and_place(self):
        act, stm = LN.actor_register(self.reg)
        self.assertEqual([(ln, r["#"]) for ln, _, r in act], [(7, "1"), (8, "2"), (9, "3"), (13, "4")])
        self.assertEqual([sec for _, sec, _ in act], ["Actors", "Actors", "Actors", "Appended"])
        self.assertEqual(list(act[3][2]), list(act[0][2]))                  # the continuation takes the actor table's header
        self.assertEqual([(ln, r["#"]) for ln, _, r in stm], [(23, "F1"), (24, "F2")])
        cl = LN.cluster_names(self.cl)
        self.assertEqual(cl, {"B1": "The fronts", "B2": "Others"})
        pl = LN.ActorPlacer(cl, ["fronts"], {"fronts": ["front"]}, ["unknown", "none"], [r for _, _, r in act])
        self.assertEqual(pl.word_cluster, {"fronts": "B1"})
        got = [pl.place_actor_row(r) for _, _, r in act]
        self.assertEqual([(g["codes"], g["placed"], g["placed_by"]) for g in got],
                         [(["B1"], ["B1"], "cluster code"), ([], ["B1"], "vocabulary"), ([], [], "unplaced"), (["B1"], ["B1"], "cluster code")])
        self.assertEqual([(g["role"], g["polity"]) for g in got], [("member", "the Council"), ("opposed", "the Council"), ("", ""), ("outside", "the Council")])
        s1, s2 = (pl.place_statement(r) for _, _, r in stm)
        self.assertEqual((s1["body_kind"], s1["polity"], s1["member"], s1["outside"], s1["opposed"]), ("council", "the Council", ["B1"], [], []))
        self.assertEqual((s2["polity"], s2["member"]), ("", []))
        self.assertEqual(LN.polity_norm(' "The  Council". '), "the council")


class StagedNoteCells(unittest.TestCase):
    """The staged notes' cells (2026-10-23, the pilot run): a unit pointer after an unclosed chain stays out of the chain, and a document
    note's quote locator other than a time is read when a quotation mark follows it."""
    def test_pointer_after_chain(self):
        self.assertEqual(LN.attribution_chain("attribution: none stated; chain: 1: Appendix 1 notes (unsourced) [u 001:22-23]"), ("none stated", "1: Appendix 1 notes (unsourced)"))
        self.assertEqual(LN.attribution_chain("attribution: x; chain: 2: A <- B (document). Rest [u 001:5]"), ("x", "2: A <- B (document)"))

    def test_document_quote_locator(self):
        self.assertTrue(LN.QUOTE_LOC_RE.match('3. (p. 17, App. 4 §1.10) "The words" (Castellan) [u 002:4]'))
        self.assertIsNone(LN.QUOTE_LOC_RE.match("3. (see below) the words, unquoted"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
