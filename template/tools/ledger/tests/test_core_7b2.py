"""The core fixes of phase 7b2 (2026-10-23, the pilot report's section 10): the polity statement row shape (defect 6), the speaker
ledgers' integrate step (7), the openness entry read from a note (10), build_db's subject page warning and stale tables (20), the core
identifiers a pack may rename (21), and the rewrite route for documents copied into another project. Fixtures are invented; nothing
of any corpus is named.
  python3 tools/ledger/tests/test_core_7b2.py"""
import json, os, sqlite3, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
from ledger import cli, notes as LN, speakers, openness

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def project(d, pack_toml='[ledger]\nname = "t"\n', pack_dir=None):
    """A temporary project: ledger.toml naming a pack (pack_dir, or a pack written from pack_toml under packs/t)."""
    if pack_dir is None:
        pack_dir = os.path.join(d, "packs", "t"); os.makedirs(pack_dir, exist_ok=True)
        with open(os.path.join(pack_dir, "pack.toml"), "w", encoding="utf-8") as f: f.write(pack_toml)
    with open(os.path.join(d, "ledger.toml"), "w", encoding="utf-8") as f: f.write(f'[ledger]\nname = "t"\n[pack]\npath = "{pack_dir}"\n')
    for sub in ("videos", "books", "subjects", "research"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def run(args, root, **kw):
    env = dict(os.environ, LEDGER_ROOT=root)
    return subprocess.run([sys.executable] + args, cwd=root, capture_output=True, text=True, env=env, **kw)


class PolityShape(unittest.TestCase):
    """Defect 6: one row shape for polity statements, the register's statement table, named in the core slot default."""
    def test_slot_default_names_the_statement_header(self):
        from ledger import briefs
        try: p = os.path.join(briefs.templates_dir(ROOT), "slots-default.toml")   # the templates the renderer itself would take
        except FileNotFoundError: self.skipTest("no brief templates found for this project")
        with open(p, "rb") as f: slot = tomllib.load(f)["slots"]["actor_register"]
        self.assertIn("| " + " | ".join(cli.STATEMENT_HEADER) + " |", slot)
        for k in ("pirs", "referent"):
            with open(p, "rb") as f: self.assertIn(k, tomllib.load(f)["slots"])

    def test_a_row_in_the_shape_is_taken_as_it_is(self):
        row = "| # | Castellan (note, row 4) | P1 the Authority | the Board | | the harbour users | weighs the risk | 2018 | \"a matter for later\" | 2: Castellan <- minutes |"
        self.assertEqual(len(cli.statement_cells(row, "n")), len(cli.STATEMENT_HEADER) - 1)


class SpeakerLedgers(unittest.TestCase):
    """Defect 7: a report's values for the pack's ledgered speakers appended to each speaker's page, once."""
    LED = [{"name": "Iris Castellan", "page": "research/castellan-ledger.md", "report_keys": ["castellan_section"]},
           {"name": "Ambrose Thale", "page": "research/thale-ledger.md", "report_keys": ["thale_section"]}]

    def test_entries_sections_absent_and_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "research"))
            LN.write_text(os.path.join(d, "research", "thale-ledger.md"), "# Speaker ledger: Ambrose Thale\n\n## Ledger\n\ngrid\n\n## Delta\n\nd\n")
            rep = {"castellan_section": [{"row": 3, "what": "told the board in 2018"}, "relayed by the minutes (row 9)"],
                   "thale_section": "### Harbour Talks, 2019\n\n- firsthand, rows 1 to 4"}
            done = speakers.append(rep, "note-a", self.LED, d, {"research/thale-ledger.md": "\n## Delta"}, today="2026-10-23")
            self.assertEqual(done, [("research/castellan-ledger.md", "castellan_section", 2), ("research/thale-ledger.md", "thale_section", "section")])
            c = LN.read_text(os.path.join(d, "research", "castellan-ledger.md"))
            self.assertIn(speakers.ENTRIES_HEADING, c); self.assertIn("### note-a, castellan_section, appended 2026-10-23", c)
            self.assertIn("- row: 3; what: told the board in 2018", c)
            t = LN.read_text(os.path.join(d, "research", "thale-ledger.md"))
            self.assertLess(t.index("### Harbour Talks, 2019"), t.index("## Delta"))
            again = speakers.append(rep, "note-a", self.LED, d, {"research/thale-ledger.md": "\n## Delta"})
            self.assertEqual([w for _, _, w in again], ["held", "held"])
            self.assertEqual(speakers.append({"castellan_section": "does not speak (not named)"}, "note-b", self.LED, d), [("research/castellan-ledger.md", "castellan_section", "absent")])


NOTE = "\n".join([
    "# A hearing", "", "| | |", "|---|---|", "| **Subjects** | [x](../subjects/harbour.md) |", "",
    "## Claims ledger", "", "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|",
    "| 1 | 0:01:00 | Castellan | disclosure | c1 | firsthand | open | Audit 2 |", "| 2 | 0:02:00 | Castellan | funding | c2 | host | closed-subtle | x |", "",
    "## Forthrightness audit", "", "| # | Time | Asked by | Question or prompt | Answer summary | Move | Basis | Note |", "|---|---|---|---|---|---|---|---|",
    "| 1 | 0:02:00 | counsel | q1 | answered | open | n/a | |", "| 2 | 0:03:00 | counsel | q2 | declined | closed-outright | legal privilege | declines |",
    "| 3 | 0:04:00 | counsel | q3 | a joke | n/a | n/a | |", "",
    "<!-- audit-counts:start -->", "Audit counts: open 1, partial 0, closed-outright 1, closed-subtle 0, stated declines 1, pseudo-declines 0.", "<!-- audit-counts:end -->", ""])


class OpennessFromNote(unittest.TestCase):
    """Defect 10: openness_counts from the counts line, openness_cells one per scored audit row."""
    def test_counts_and_cells(self):
        with tempfile.TemporaryDirectory() as d:
            project(d); p = os.path.join(d, "videos", "h.md"); LN.write_text(p, NOTE)
            counts, cells = openness.from_note(p, d)
            self.assertEqual(counts, {"open": 1, "partial": 0, "closed_outright": 1, "closed_subtle": 0, "stated_declines": 1, "pseudo_declines": 0})
            self.assertEqual([(c["topic"], c["class"], c["basis"]) for c in cells], [("funding", "open", "n/a"), ("disclosure", "closed-outright", "legal privilege")])


class BuildDb(unittest.TestCase):
    """Defects 20 and 21: a subject page whose table is not loaded is named; a table the build does not make is dropped; the object
    watch table takes the pack's name."""
    def test_warning_stale_table_and_table_name(self):
        import packload
        with tempfile.TemporaryDirectory() as d:
            project(d, pack_dir=packload.pack_dir())
            LN.write_text(os.path.join(d, "subjects", "harbour.md"), "# Harbour\n\n## Videos in this subject\n\n| Uploaded | Video | Speaker | Core position |\n|---|---|---|---|\n| 2019 | v | a | b |\n")
            LN.write_text(os.path.join(d, "subjects", "loose.md"), "# Loose\n\nprose only\n")
            db = os.path.join(d, "t.db")
            con = sqlite3.connect(db); con.execute("CREATE TABLE zz_left_over(x)"); con.commit(); con.close()
            r = run([os.path.join(TOOLS, "build_db.py"), "--db", db], d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("subjects/harbour.md: the table under `## Videos in this subject` is not headed", r.stderr)
            self.assertIn("subjects/loose.md: no `## Videos in this subject` section", r.stderr)
            self.assertIn("dropped the stale table zz_left_over", r.stderr)
            tables = {t for (t,) in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}
            self.assertIn(packload.name("table.object_watch"), tables); self.assertNotIn("zz_left_over", tables)


class PackNames(unittest.TestCase):
    """Defect 21: the core's neutral names, and a pack that keeps earlier ones by [names]."""
    CODE = ("import sys, json; sys.path.insert(0, sys.argv[1]); import packload; from ledger import cli; "
            "print(json.dumps([packload.name('table.object_watch'), packload.name('baseline.actor_rows'), list(cli._actor_columns()), "
            "cli.actor_cells({'beast': 'gull', 'teller': 'T'}, ['#', 'Beast or kind', 'Teller and note row'])]))")

    def test_core_names_and_a_pack_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            project(d)
            r = run(["-c", self.CODE.replace("{'beast': 'gull', 'teller': 'T'}, ['#', 'Beast or kind', 'Teller and note row']", "{'teller': 'T'}, ['#', 'Actor or kind', 'Teller and note row']"), TOOLS], d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), ["object_watch", "actor_rows", ["actor or kind", "actor as named"], ["", "T"]])
        with tempfile.TemporaryDirectory() as d:
            project(d, '[names]\n"table.object_watch" = "beast_watch"\n"baseline.actor_rows" = "beast_rows"\n"actors.header_column" = "beast or kind"\n'
                       '"actors.key_synonyms" = { beast = "beastorkind" }\n')
            r = run(["-c", self.CODE, TOOLS], d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), ["beast_watch", "beast_rows", ["actor or kind", "actor as named", "beast or kind"], ["gull", "T"]])


@unittest.skipUnless(os.path.isfile(os.path.join(TOOLS, "build_bundle.py")), "the rewrite route runs in the project that builds the bundle")
class RewriteRoute(unittest.TestCase):
    """A document the bundle rewrites reaches another project only through build_bundle --doc; any other file copied into another
    project by `ledger file copy` is copied as it is."""
    def test_doc_rewrite_and_copy_guard(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "other")); other = project(os.path.join(d, "other"))
            out = os.path.join(other, "tools", "schema.md")
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "build_bundle.py"), "--doc", "tools/schema.md", "--out", out], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertTrue(os.path.isfile(out))
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "build_bundle.py"), "--doc", "tools/ledger/cli.py", "--out", os.path.join(d, "x")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            led = [sys.executable, os.path.join(ROOT, "ledger.py"), "file", "copy"]
            r = subprocess.run(led + ["tools/schema.md", os.path.join(other, "tools", "schema2.md")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1); self.assertIn("--doc tools/schema.md", r.stderr); self.assertFalse(os.path.exists(os.path.join(other, "tools", "schema2.md")))
            clean = os.path.join(d, "clean.txt"); LN.write_text(clean, "a harbour, a gull, a ledger\n")
            r = subprocess.run(led + [clean, os.path.join(other, "clean.txt")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr); self.assertTrue(os.path.isfile(os.path.join(other, "clean.txt")))
            self.assertEqual([f for f in os.listdir(other) if f.startswith(".ledger-copy-")], [])   # the copy leaves no temporary file behind


class FirstUtterance(unittest.TestCase):
    """The merge ruling (`--supersede`, 7b2) and the idempotent `--apply` (the pilot's fix 7, confirmed)."""
    REG = ("# First-utterance register\n\n| ID | Event | Claim | Rows | Earliest held telling | Earliest known public telling | Catalyst before held | Tellings | Pages | Status |\n"
           "|---|---|---|---|---|---|---|---|---|---|\n"
           "| FU-1 | 2018 | the harbour board denied the fault | [n claims 1] | | | | | managed:1 | |\n"
           "| FU-2 | 2018 | the harbour board denied the fault | [n claims 1]; [n claims 3] | | | | | managed:1, managed:4 | |\n"
           "| FU-3 | 2019 | the gull count fell | [n claims 2] | | | | | | |\n")

    def test_supersede_cite_refresh_and_apply(self):
        import packload
        with tempfile.TemporaryDirectory() as d:
            project(d, pack_dir=packload.pack_dir())
            cat = run(["-c", "import sys; sys.path.insert(0, sys.argv[1]); import packload; print(packload.pack()['catalysts']['page'])", TOOLS], d).stdout.strip()
            os.makedirs(os.path.dirname(os.path.join(d, cat)), exist_ok=True); LN.write_text(os.path.join(d, cat), "# Catalysts\n")
            LN.write_text(os.path.join(d, "research", "first-utterance-register.md"), self.REG)
            LN.write_text(os.path.join(d, "research", "harbour-page.md"), "# Leads\n\nsee FU-2 and FU-21 and FU-2.\n")
            self.assertEqual(run([os.path.join(TOOLS, "build_db.py")], d).returncode, 0)
            fu = [os.path.join(TOOLS, "first_utterance.py")]
            r = run(fu + ["--supersede", "FU-2=FU-1", "--cite"], d); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1 rows marked", r.stdout)
            self.assertEqual(LN.read_text(os.path.join(d, "research", "harbour-page.md")), "# Leads\n\nsee FU-1 and FU-21 and FU-1.\n")
            reg = lambda: {LN.split_row(l)[0]: LN.split_row(l) for l in LN.read_lines(os.path.join(d, "research", "first-utterance-register.md")) if l.startswith("| FU-")}
            self.assertTrue(reg()["FU-2"][9].startswith("superseded by FU-1"))
            self.assertEqual(reg()["FU-1"][3], "[n claims 1]; [n claims 3]"); self.assertEqual(reg()["FU-1"][8], "managed:1, managed:4")
            self.assertEqual(run(fu + ["--refresh"], d).returncode, 0)
            self.assertTrue(reg()["FU-2"][9].startswith("superseded by FU-1"))
            self.assertIn("0 rows marked", run(fu + ["--supersede", "FU-2=FU-1"], d).stdout)
            rep = os.path.join(d, "report.json")
            with open(rep, "w") as f:
                json.dump({"first_telling_rows": [{"cluster": "new: the pier was closed", "row": "[n claims 5]", "date": "2020-01-01"},
                                                  {"cluster": "FU-2", "row": "[n claims 6]"}]}, f)
            self.assertEqual(run(fu + ["--apply", rep], d).returncode, 0); once = reg()
            self.assertEqual(run(fu + ["--apply", rep], d).returncode, 0); twice = reg()
            self.assertEqual(once, twice); self.assertEqual(len(twice), 4)
            self.assertIn("[n claims 6]", twice["FU-1"][3]); self.assertNotIn("[n claims 6]", twice["FU-2"][3])


if __name__ == "__main__":
    unittest.main()
