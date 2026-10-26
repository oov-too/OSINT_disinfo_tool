"""`ledger integrate`'s actor step (tools/ledger/cli.py actor_append, 2026-10-23): the register's actor table is found by the header
forms in use (the core's two and a pack's own, [names] "actors.header_column"), and a new project's register is started at its first actor row from the report's own actor_rows_header."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger import cli, notes

PILOT_HEADER = ("| # | Actor as named (teller's spelling) | Kind | Polity | Order of battle (part of, run by, funded by, contracted by, instructed by, "
                "a front for) with date | Teller and note row | Firsthand / relayed (chain) | Goals or role as told | Posture toward the referent "
                "(intent, capability) as told | Confidence |")
ROW = "| 1 | the Authority | state actor | P2 | none stated, 2018 | Castellan; claims 16 | 2: Castellan <- Authority statement | operator | denies any fault | med |"


class ActorRegister(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def report(self, **kw):
        p = os.path.join(self.d, "report.json")
        json.dump(dict({cli.actor_register()[1]: [ROW]}, **kw), open(p, "w"))   # the active pack's rows key
        return p

    def test_a_missing_register_is_started_from_the_reports_header(self):
        reg = os.path.join(self.d, "research", "actor-polity-register.md")
        self.assertEqual(cli.actor_append(self.report(actor_rows_header=PILOT_HEADER), register=reg), (1, 0))
        lines = notes.read_text(reg).split("\n")
        self.assertEqual(cli._actor_header(lines)[1], "Actor as named (teller's spelling)")
        self.assertIn("| 1 | the Authority | state actor | P2 |", notes.read_text(reg))
        self.assertEqual(cli.actor_append(self.report(actor_rows_header=PILOT_HEADER), register=reg), (0, 1))   # a re-run adds nothing

    def test_without_a_header_the_core_form_is_used(self):
        reg = os.path.join(self.d, "actors.md")
        cli._start_actor_register(reg, {})
        self.assertEqual(cli._actor_header(notes.read_text(reg).split("\n")), cli.CORE_ACTOR_HEADER)

    def test_an_existing_registers_header_is_matched(self):
        # a pack's own earlier header form is matched through its [names] "actors.header_column" (tools/ledger/tests/test_core_7b2.py)
        reg = os.path.join(self.d, "actors-existing.md")
        notes.write_text(reg, "# Register\n\n| # | Actor as named | Teller and note row |\n|---|---|---|\n| 3 | a | b |\n")
        p = os.path.join(self.d, "r2.json"); json.dump({cli.actor_register()[1]: ["| new | c | d |"]}, open(p, "w"))
        self.assertEqual(cli.actor_append(p, register=reg), (1, 0))
        self.assertIn("| 4 | c | d |", notes.read_text(reg))


class PolityStatements(unittest.TestCase):
    """polity_append (2026-10-23): a pack naming no single polity has its intakes' statements appended, whatever dict shape the writer
    returned; a key with no column is kept, never dropped; a pack naming one polity keeps its statements by hand."""
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.reg = os.path.join(self.d, "actors.md")
        cli._start_actor_register(self.reg, {})
        self.saved = cli._actors_section

    def tearDown(self): cli._actors_section = self.saved

    def test_dict_shapes_are_mapped_and_nothing_dropped(self):
        a = cli.statement_cells({"polity": "P2", "statement": "denies any fault", "by": "Castellan", "note_row": 132, "aside": "x"}, "note-a")
        self.assertEqual(a[0], "Castellan (note-a, row 132)"); self.assertEqual(a[1], "P2"); self.assertIn("denies any fault", a[5]); self.assertIn("[aside: x]", a[5])
        b = cli.statement_cells({"polity": "P2", "posture": "operator", "teller": "the notes"}, "note-b")
        self.assertEqual((b[0], b[5]), ("the notes (note-b)", "operator"))
        c = cli.statement_cells("P2 the operator's coalition: denies any fault (row 7)", "note-c")
        self.assertEqual((c[1], c[5]), ("P2 the operator's coalition", "denies any fault (row 7)"))
        self.assertEqual(cli.statement_cells("a sentence with no polity id", "note-d")[5], "a sentence with no polity id")

    def test_appended_once_and_numbered(self):
        cli._actors_section = lambda: {"polity_key": "polity_statements"}
        p = os.path.join(self.d, "r.json"); json.dump({"file": "books/note-a.md", "polity_statements": [{"polity": "P2", "statement": "s1"}, {"polity": "P3", "statement": "s2"}]}, open(p, "w"))
        self.assertEqual(cli.polity_append(p, register=self.reg), (2, 0))
        self.assertEqual(cli.polity_append(p, register=self.reg), (0, 2))
        t = notes.read_text(self.reg)
        self.assertIn("| 1 | not stated (note-a) | P2 |", t); self.assertIn("| 2 | not stated (note-a) | P3 |", t)

    def test_a_named_polity_pack_is_left_alone(self):
        cli._actors_section = lambda: {"polity_name": "The Named Body", "polity_key": "named_body"}
        p = os.path.join(self.d, "r.json"); json.dump({"named_body": [{"polity": "x"}]}, open(p, "w"))
        self.assertEqual(cli.polity_append(p, register=self.reg), (0, 0))


class PolityCodePlacement(unittest.TestCase):
    """notes.ActorPlacer with a pack's declared polities and no clusters page (2026-10-23): a row is placed by the codes its polity cell
    names; with a clusters page the polity cell never places a row by itself."""
    def test_placed_by_polity_code(self):
        names = notes.polity_names(["P1 the state", "P2 the operator's coalition"])
        self.assertEqual(names, {"P1": "the state", "P2": "the operator's coalition"})
        row = {"#": "1", "Actor as named (teller's spelling)": "the Authority", "Kind": "state actor", "Polity": "P2"}
        p = notes.ActorPlacer(names, ["the Authority"], {}, ["unknown", ""], [row], polity_codes=True).place_actor_row(row)
        self.assertEqual((p["placed"], p["placed_by"], p["role"], p["polity"]), (["P2"], "polity code", "member", "the operator's coalition"))
        q = notes.ActorPlacer(names, ["the Authority"], {}, ["unknown", ""], [row]).place_actor_row(row)
        self.assertEqual(q["placed_by"], "unplaced")


if __name__ == "__main__":
    unittest.main()
