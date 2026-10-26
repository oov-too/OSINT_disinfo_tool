"""The basis audit and the unused-rows check (tools/narratives.md section 8e, owner 2026-10-25), over a small fixture project in a
temporary folder (a witness note, a held document note, a press note, and a two-node narrative page):
- tools/narratives.py reads the Nodes table's Basis column when it is there and as before when it is not; the score line takes the
  optional trailing `thin nodes N of N`; --check needs a class in every Basis cell and an axis that agrees with the cells; --audit's
  Basis section sets the class each node's rows carry beside the page's cell; the row classifier gives document, record,
  recollection, inference and press from a row's Source class, chain and note kind;
- tools/report_check.py accepts the axis and the optional thin_nodes key;
- tools/build_db.py stores the Basis cell in narrative_nodes;
- tools/narrative_unused.py lists the held rows a page never cites, earlier dates first, keeps every cited row (a short reference
  included) out, states its cap, and exits 2 on a page with no Nodes table.
Run: python3 tools/ledger/tests/test_basis_audit.py (from the project root)."""
import importlib.util, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, TOOLS)

SCORE_V04 = ("Narrative scores: clusters 2, rows 3, roots 2, circle roots 2, reading roots 2, contradictions 0, load 0.0, max downstream 0, "
             "unaffiliated roots 1 of 2, survive under rival 1 of 2, tests 1")
DOC = "doc-abc01234-2010-07-01-ledger-memo"; HEAR = "hearing-2024-03-05-ann-witness-day-9"; PRESS = "press-2011-02-01-vendor-denies"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(text)


def page(basis=True, axis=", thin nodes 1 of 2", node1_basis="document", extra=""):
    b_head, b_sep = (" Basis |", "---|") if basis else ("", "")
    c1 = f" {node1_basis} |" if basis else ""; c2 = " press; thin |" if basis else ""
    return f"""# Narrative: fixture

| | |
|---|---|
| **Kind** | narrative |
| **Mode** | mainline |
| **Thesis** | The vendor knew of the ledger fault. |
| **Alternative** | The vendor did not know. |
| **Status** | built |

## Thesis

The vendor knew.

## Nodes

| # | Date | Lane | Node | Carriers (independent roots) | Rows |{b_head} Depends on | Role |
|---|---|---|---|---|---|{b_sep}---|---|
| 1 | 2009 to 2010-07 | A | The memo records the vendor's ledger fault, and Ann Witness saw ledger entries amended at the depot | Ann Witness (firsthand); the memo | [{HEAR} claims 1] (firsthand); [{DOC} claims 1] (host) |{c1} | cause |
| 2 | about 2011 | D | The vendor denies the ledger fault in the press | the vendor (via the press) | [{PRESS} claims 1] (host) |{c2} 1 | cover |

## Contradiction ledger

| # | Node | Contradiction | Side taken | Other side | Weight | Downstream | Why survivable | Fork | Flare |
|---|---|---|---|---|---|---|---|---|---|

## Synchrony

none

## Carriers

| Carrier | Root or relay | Openness on this narrative's topics | Affiliations (dated) | Echo overlap | Note |
|---|---|---|---|---|---|
| Ann Witness | root | open | none | none | |

## Interests

none

## Objections

The counsel's own question at [{HEAR} claims 2] was read, and claims 5 too.{extra}

## Score card

{SCORE_V04}{axis}.

## Forks

none

## Tests

1. Ask the vendor for the depot log.

## Leads returned

none

## Relations returned

none
"""


def make_project(d):
    write(os.path.join(d, "ledger.toml"), '[ledger]\nname = "fixture"\n[pack]\npath = "packs/fx"\n')
    write(os.path.join(d, "packs", "fx", "pack.toml"), '[eras]\nnarrative_from = 2000\n[[eras.era]]\nid = "e1"\nfrom = 2000\nto = 2100\n\n'
          '[audit]\ntopics = [{id = "ledger-access", label = "Ledger access"}, {id = "other", label = "Other"}]\n')
    write(os.path.join(d, "research", "source-kinds.md"), "# Source kinds\n\n| Stem | Kind | Channel | Note |\n|---|---|---|---|\n"
          f"| {DOC} | document | the vendor | override |\n| {PRESS} | document | a paper | override |\n| {HEAR} | witness | the inquiry | override |\n")
    con = sqlite3.connect(os.path.join(d, "notes.db"))
    con.executescript("""
        CREATE TABLE videos(id TEXT PRIMARY KEY, file TEXT, title TEXT, channel TEXT, host TEXT, guest TEXT, speakers TEXT);
        CREATE TABLE claims(video TEXT, n TEXT, time TEXT, speaker TEXT, topic TEXT, claim TEXT, source_class TEXT, move TEXT, note TEXT,
                            attribution TEXT, chain TEXT);
        CREATE TABLE timeline(video TEXT, n TEXT, n_sort REAL, date_stated TEXT, sortable TEXT, sort_key TEXT, approx INTEGER, event TEXT,
                              speaker_basis TEXT, chain TEXT, link TEXT, agreement TEXT, agreement_kind TEXT);
        CREATE TABLE audit_rows(video TEXT, n TEXT, time TEXT, asked_by TEXT, question TEXT, answer TEXT, move TEXT, basis TEXT, note TEXT);
        CREATE TABLE cross_checks(video TEXT, n TEXT, kind TEXT, verdict TEXT, this_note TEXT, elsewhere TEXT, note TEXT);
        CREATE TABLE leads(n TEXT, kind TEXT, lead TEXT, settles TEXT, status TEXT, sources TEXT);
        CREATE TABLE relations(n TEXT, a TEXT, b TEXT, kind TEXT, hierarchy TEXT, when_ TEXT, what TEXT, confidence TEXT, a_canon TEXT, b_canon TEXT);""")
    con.executemany("INSERT INTO videos VALUES (?,?,?,?,?,?,?)", [
        (DOC, f"books/{DOC}.md", 'The vendor, "Ledger fault memo of July" (ABC01234, 2010)', "the vendor", "none (the vendor)", "none (one memo)", ""),
        (PRESS, f"books/{PRESS}.md", "A paper, vendor denies (2011)", "a paper", "none (a reporter)", "none (one web article: a news report)", ""),
        (HEAR, f"videos/{HEAR}.md", "Ann Witness, Day 9", "the inquiry", "Chair Person (chair)", "Ann Witness", "Ann Witness; Mr Counsel")])
    claims = [
        (HEAR, "1", "Ann Witness", "ledger-access", "Says she saw ledger entries amended at the depot in 2009", "firsthand", "", ""),
        (HEAR, "2", "Mr Counsel", "ledger-access", "Reads the letter REF00055555 on the depot", "read", "", "2: Mr Counsel <- REF00055555, a letter (document)"),
        (HEAR, "3", "Mr Counsel", "ledger-access", "Reads the memo on the vendor's ledger fault", "read", "", "2: Mr Counsel <- ABC01234, the memo (document)"),
        (HEAR, "4", "Mr Counsel", "ledger-access", "Says the inquiry holds papers showing the vendor could amend depot entries before 2004", "read", "",
         "2: Mr Counsel <- the inquiry's papers (document, unnamed)"),
        (HEAR, "5", "Ann Witness", "ledger-access", "Thinks the vendor must have known of the amended entries", "inference", "", ""),
        (HEAR, "6", "Ann Witness", "other", "Says the weather was fine in 2009", "firsthand", "", ""),
        (HEAR, "7", "Bob Rival", "ledger-access", "Says no depot entries were ever amended, in 2010", "hearsay", "", "2: Ann Witness <- Bob Rival (basis not stated)"),
        (DOC, "1", "the vendor", "ledger-access", "The memo records a ledger fault at the depot", "host", "", ""),
        (DOC, "2", "the vendor", "ledger-access", "The memo says depot entries were amended to correct the ledger fault in 2010", "firsthand", "", ""),
        (PRESS, "1", "the reporter", "ledger-access", "The vendor denies any ledger fault", "host", "", ""),
        (PRESS, "2", "the reporter", "ledger-access", "Says the court papers show the depot entries", "host", "", "2: the reporter <- the court papers (document)")]
    con.executemany("INSERT INTO claims VALUES (?,?,'',?,?,?,?,'','',?,?)", [(v, n, sp, t, c, sc, a, ch) for v, n, sp, t, c, sc, a, ch in claims])
    filler = ["harbour boats", "fishing nets", "market prices", "river tides", "school buses", "garden fences", "choir rehearsals", "bakery ovens"]
    con.execute("INSERT INTO videos VALUES ('filler-2020-talks', 'videos/filler-2020-talks.md', 'Talks', 'a channel', 'none (no host)', 'Carol Other', '')")
    con.executemany("INSERT INTO claims VALUES ('filler-2020-talks', ?, '', 'Carol Other', 'other', ?, 'firsthand', '', '', '', '')",
                    [(str(i), f"Talks about the {filler[i % 8]} and the {filler[(i * 3 + 1) % 8]}, item {i}") for i in range(1, 81)])   # a corpus's frequencies
    con.execute("INSERT INTO timeline VALUES (?, '1', 1, 'in 2009', '2009', '1000002009-00-00', 0, 'Ann Witness sees entries amended', "
                "'Mr Counsel, reading the letter (read)', '', '', '', '')", (HEAR,))
    con.execute("INSERT INTO audit_rows VALUES (?, '1', '', 'Mr Counsel (counsel)', 'Did you see entries amended?', 'Yes, in 2009', 'open', '', '')", (HEAR,))
    con.commit(); con.close()
    write(os.path.join(d, "research", "narrative-fixture.md"), page())


def run(d, tool, *args):
    env = dict(os.environ, LEDGER_ROOT=d)
    return subprocess.run([sys.executable, os.path.join(TOOLS, tool)] + list(args), cwd=d, env=env, capture_output=True, text=True)


def py(d, code):
    env = dict(os.environ, LEDGER_ROOT=d, PYTHONPATH=TOOLS)
    r = subprocess.run([sys.executable, "-c", code], cwd=d, env=env, capture_output=True, text=True)
    if r.returncode: raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d, True); make_project(self.d)
        self.page = os.path.join("research", "narrative-fixture.md")

    def set_page(self, text): write(os.path.join(self.d, self.page), text)


class ScoreLine(unittest.TestCase):
    def test_the_axis_is_optional(self):
        import narratives as N
        with_axis = N.SCORE_RE.findall(SCORE_V04 + ", thin nodes 3 of 33.")[0]; without = N.SCORE_RE.findall(SCORE_V04 + ".")[0]
        k = N.SCORE_KEYS.index("thin")
        self.assertEqual((with_axis[k], with_axis[k + 1]), ("3", "33"))
        self.assertEqual((without[k], without[k + 1]), ("", ""))
        self.assertEqual(with_axis[:k], without[:k])
        self.assertEqual(len(N.SCORE_KEYS), len(with_axis))

    def test_basis_cells(self):
        import narratives as N
        self.assertEqual(N.basis_cell("document"), ("document", False))
        self.assertEqual(N.basis_cell("recollection; thin"), ("recollection", True))
        self.assertEqual(N.basis_cell("Inference"), ("inference", True))
        self.assertEqual(N.basis_cell(""), ("", False))

    def test_report_check_accepts_the_axis_and_the_optional_key(self):
        spec = importlib.util.spec_from_file_location("report_check_b", os.path.join(TOOLS, "report_check.py"))
        RC = importlib.util.module_from_spec(spec); spec.loader.exec_module(RC)
        self.assertTrue(RC.SCORE.match(SCORE_V04 + "."))
        self.assertTrue(RC.SCORE.match(SCORE_V04 + ", thin nodes 2 of 33."))
        self.assertFalse(RC.SCORE.match(SCORE_V04 + ", thin nodes 2."))
        rep = {"page": "p", "citations_checked": 1, "citation_misses": 0, "broken_nodes": [], "roots_author": 1, "roots_attacker": 1,
               "missing_contradictions": 0, "flares_disputed": 0, "rowless_edges_struck": 0, "objections": 0, "leads": 0,
               "score_line": "attacker: " + SCORE_V04 + ", thin nodes 2 of 33.", "notes": "", "blocked_passages": []}
        self.assertEqual(RC.check_form(rep, "attack"), [])
        self.assertEqual(RC.check_form(dict(rep, thin_nodes=2), "attack"), [])
        self.assertTrue(any("thin_nodes" in p for p in RC.check_form(dict(rep, thin_nodes="2"), "attack")))


class Parser(Base):
    def parsed(self):
        out = os.path.join(self.d, "p.json"); r = run(self.d, "narratives.py", self.page, "--json", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as f: return json.load(f)[0]

    def test_the_basis_column_is_read(self):
        p = self.parsed()
        self.assertTrue(p["has_basis"]); self.assertEqual(p["basis"], {"1": "document", "2": "press"})
        self.assertEqual((p["thin_nodes"], p["thin_node_list"]), (1, [2])); self.assertEqual(p["basis_tally"], {"document": 1, "press": 1})
        self.assertEqual((p["score_lines"][-1]["thin"], p["score_lines"][-1]["thin_all"]), (1.0, 2.0))

    def test_a_page_without_the_column_reads_as_before(self):
        self.set_page(page(basis=False, axis=""))
        p = self.parsed()
        self.assertFalse(p["has_basis"]); self.assertEqual((p["thin_nodes"], p["basis"]), (0, {}))
        self.assertEqual(p["nodes"], 2); self.assertIsNone(p["score_lines"][-1]["thin"])

    def test_check(self):
        self.assertEqual(run(self.d, "narratives.py", "--check", self.page).returncode, 0)
        self.set_page(page(axis=", thin nodes 2 of 2")); r = run(self.d, "narratives.py", "--check", self.page)
        self.assertEqual(r.returncode, 1); self.assertIn("thin nodes 2 of 2", r.stdout)
        self.set_page(page(axis="")); r = run(self.d, "narratives.py", "--check", self.page)
        self.assertEqual(r.returncode, 1); self.assertIn("no `thin nodes N of N` axis", r.stdout)
        self.set_page(page(node1_basis="strong")); r = run(self.d, "narratives.py", "--check", self.page)
        self.assertEqual(r.returncode, 1); self.assertIn("naming no class", r.stdout)
        self.set_page(page(basis=False, axis="")); self.assertEqual(run(self.d, "narratives.py", "--check", self.page).returncode, 0)

    def test_audit_basis_section(self):
        out = os.path.join(self.d, "audit.md"); r = run(self.d, "narratives.py", "--audit", self.page, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as f: t = f.read()
        self.assertIn("## 6. Basis", t)
        self.assertRegex(t, r"\| 1 \| cause \| document \| document \| no \|")
        self.assertRegex(t, r"\| 2 \| cover \| press; thin \| press \| no \|")
        self.assertIn("thin nodes 1 of 2 (agrees)", t)
        self.set_page(page(node1_basis="record", axis=", thin nodes 1 of 2")); run(self.d, "narratives.py", "--audit", self.page, "--out", out)
        with open(out, encoding="utf-8") as f: self.assertRegex(f.read(), r"\| 1 \| cause \| record \| document \| page weaker than its rows \|")

    def test_row_classes(self):
        got = py(self.d, "import json, narratives as N\ncon = N._db(); nk = N.NoteKinds(con)\n"
                         f"refs = [('{HEAR}', 'claims', n) for n in '1234567'] + [('{DOC}', 'claims', '1'), ('{DOC}', 'claims', '2'), "
                         f"('{PRESS}', 'claims', '1'), ('{PRESS}', 'claims', '2'), ('{HEAR}', 'tl', '1'), ('{HEAR}', 'audit', '1')]\n"
                         "print(json.dumps([N.row_basis(con, nk, *r)[0] for r in refs] + [nk.kind[k] for k in sorted(nk.kind)]))")
        self.assertEqual(got[:13], ["recollection", "record", "document", "record", "inference", "recollection", "recollection",
                                    "document", "document", "press", "record", "record", "recollection"])
        self.assertEqual(got[13:], ["document", "witness", "witness", "press"])   # doc-, filler-, hearing-, press-, sorted


class BuildDb(Base):
    def test_narrative_nodes_carry_the_basis(self):
        got = py(self.d, "import json, build_db\nnv, nn, nc = build_db.parse_narratives()\nprint(json.dumps([r[-1] for r in nn]))")
        self.assertEqual(got, ["document", "press; thin"])
        self.set_page(page(basis=False, axis=""))
        self.assertEqual(py(self.d, "import json, build_db\nnv, nn, nc = build_db.parse_narratives()\nprint(json.dumps([r[-1] for r in nn]))"), ["", ""])

    def test_the_schema_has_the_column(self):
        import build_db
        self.assertRegex(build_db.SCHEMA, r"CREATE TABLE narrative_nodes\([^)]*role TEXT, basis TEXT\)")


class Unused(Base):
    def unused(self, *args):
        out = os.path.join(self.d, "unused.md"); js = os.path.join(self.d, "unused.json")
        r = run(self.d, "narrative_unused.py", self.page, "--out", out, "--json", js, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as f, open(js, encoding="utf-8") as g: return f.read(), json.load(g)

    def test_an_earlier_held_row_is_listed_first_and_cited_rows_never(self):
        md, js = self.unused()
        n1 = js["nodes"][0]; rows = [r["row"] for r in n1["rows"]]
        self.assertEqual(n1["node"], 1)
        self.assertEqual(rows[0], f"[{HEAR} claims 4]"); self.assertEqual(n1["rows"][0]["cls"], "earlier date")
        self.assertIn("2004 before the node's 2009", n1["rows"][0]["why"])
        cited = {f"[{HEAR} claims 1]", f"[{HEAR} claims 2]", f"[{HEAR} claims 5]", f"[{DOC} claims 1]", f"[{PRESS} claims 1]"}
        for nd in js["nodes"]: self.assertFalse(cited & {r["row"] for r in nd["rows"]}, nd["node"])   # claims 5: a short reference, bound
        self.assertNotIn(f"[{HEAR} claims 6]", rows)   # nothing shared with the node but a year
        self.assertIn("| Row | Date | Speaker | Class | What it says | Why it bears |", md)
        self.assertIn("Cap 12 rows per node", md)

    def test_the_document_and_the_other_side(self):
        md, js = self.unused()
        n1 = {r["row"]: r for r in js["nodes"][0]["rows"]}
        self.assertEqual(n1[f"[{DOC} claims 2]"]["cls"], "document")
        self.assertEqual(n1[f"[{HEAR} claims 7]"]["cls"], "other side")
        self.assertIn("Bob Rival is not among the node's carriers", n1[f"[{HEAR} claims 7]"]["why"])
        self.assertNotIn("Mr Counsel is not among", json.dumps(js))   # an examiner is no side

    def test_the_cap_is_stated_and_what_it_cut_indexed(self):
        md, js = self.unused("--cap", "1", "--node", "1")
        self.assertEqual(len(js["nodes"]), 1); n1 = js["nodes"][0]
        self.assertEqual(n1["shown"], 1); self.assertEqual(n1["cut"], n1["matched"] - 1); self.assertGreater(n1["cut"], 0)
        self.assertIn("Cut by the cap", md); self.assertIn(f"{HEAR}: claims", md.split("Cut by the cap", 1)[1])
        self.assertIn("cap 1", md)

    def test_no_nodes_table_exits_2(self):
        self.set_page("# Not a narrative\n\n## Thesis\n\nnone\n")
        r = run(self.d, "narrative_unused.py", self.page)
        self.assertEqual(r.returncode, 2); self.assertIn("no Nodes table", r.stderr)

    def test_the_launcher_names_the_command(self):
        from ledger import cli
        self.assertIn(("unused", "narrative_unused"), [(a, b) for a, b, _ in cli.LAYERS["narrate"]] if hasattr(cli, "LAYERS") else
                      [(a, b) for layer in [v for k, v in vars(cli).items() if isinstance(v, dict) and "narrate" in v] for a, b, _ in layer["narrate"]])


if __name__ == "__main__":
    unittest.main()
