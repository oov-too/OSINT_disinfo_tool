"""The narrative tools (7b2 part 1, items 14 to 16, 2026-10-23), each over a small fixture project in a temporary folder:
- tools/narrative_pack.py names its lanes from the pack's [display.viewer.lanes] when the pack's [tools.narrative_pack] gives no lane
  names, keeps the core's lane wording only for a pack lane of the same name, and takes the agency mark from the rows' own agency tags
  (the `agency divergence:` prefix and a div tag's party=), with the agency bonus on cross-checks as the page's formula states;
- tools/narrative_apply.py keys its relation dedupe on (a, b, kind, when), so a dated variant of an edge is kept;
- tools/narratives.py reads `(reading: n)` in a Depends-on cell as a reading edge: out of the downstream closure, counted.
Run: python3 tools/ledger/tests/test_narrative_tools.py (from the project root)."""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, TOOLS)

VIEWER_LANES = {"A": "The system", "B": "Prosecutions and recovery", "C": "Disclosure", "D": "The critics", "E": "Money and contracts",
                "F": "Government", "G": "The courts", "H": "Organisations"}


def tmpdir(test):
    d = tempfile.mkdtemp(); test.addCleanup(shutil.rmtree, d, True); return d


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(text)


def make_project(d, tools_table=""):
    """A project with a pack that declares eight viewer lanes, one era from 2000 and an empty thesis list, and a notes.db holding
    three timeline rows, three contradicting cross-checks and nothing else."""
    write(os.path.join(d, "ledger.toml"), '[ledger]\nname = "fixture"\n[pack]\npath = "packs/fx"\n')
    lanes = "\n".join(f'{k} = "{v}"' for k, v in VIEWER_LANES.items())
    write(os.path.join(d, "packs", "fx", "pack.toml"),
          '[eras]\nnarrative_from = 2000\n[[eras.era]]\nid = "e1"\nfrom = 2000\nto = 2100\n\n[narratives]\ntheses = "packs/fx/theses.json"\n\n'
          f'[display.viewer.lanes]\n{lanes}\n\n{tools_table}')
    write(os.path.join(d, "packs", "fx", "theses.json"), json.dumps({"theses": []}))
    write(os.path.join(d, "research", "figures", "openness-dataset.json"), json.dumps({"sources": [], "cells": []}))
    con = sqlite3.connect(os.path.join(d, "notes.db"))
    con.executescript("""
        CREATE TABLE videos(id TEXT, file TEXT, title TEXT, guest TEXT, host TEXT, speakers TEXT, recorded TEXT, uploaded TEXT);
        CREATE TABLE video_subjects(video TEXT, subject TEXT);
        CREATE TABLE claims(video TEXT, n TEXT, topic TEXT, speaker TEXT, source_class TEXT, move TEXT, claim TEXT, time TEXT);
        CREATE TABLE timeline(video TEXT, n TEXT, sortable TEXT, sort_key TEXT, event TEXT, speaker_basis TEXT, link TEXT, chain TEXT,
                              date_stated TEXT, agreement_kind TEXT, agreement TEXT);
        CREATE TABLE cross_checks(video TEXT, n TEXT, kind TEXT, verdict TEXT, this_note TEXT, elsewhere TEXT, note TEXT);
        CREATE TABLE leads(n TEXT, kind TEXT, lead TEXT, settles TEXT, status TEXT, sources TEXT);
        CREATE TABLE relations(n TEXT, a TEXT, b TEXT, kind TEXT, a_canon TEXT, b_canon TEXT, when_ TEXT, confidence TEXT);
        CREATE TABLE audit_rows(video TEXT, n TEXT, move TEXT, basis TEXT, note TEXT, question TEXT, answer TEXT, time TEXT);""")
    con.execute("INSERT INTO videos VALUES ('doc-a', 'books/doc-a.md', 'Doc A', 'none', 'none', '', '2015', '2015')")
    tl = [("1", "2010-03", "The hearing heard testimony on the system", "Jane Roe", "", ""),
          ("2", "2011-05", "The contract was paid at 2 million", "Jane Roe", "", ""),
          ("3", "2013-07", "The firm said the defect was found in 2011", "Doc A", "contradicts",
           "contradicts: point: date; agency divergence: the firm's 2013 line against its 2010 notes [div: dir=self; core=core; stab=varied; "
           "indep=yes; timing=after-challenge; path=document; party=Post Office Ltd]")]
    for n, srt, ev, sb, ak, ag in tl:
        con.execute("INSERT INTO timeline VALUES ('doc-a', ?, ?, ?, ?, ?, '', '', ?, ?, ?)", (n, srt, srt, ev, sb, srt, ak, ag))
    xc = [("1", "point: substance; agency divergence: the Board's denial of 2009 against the judgment [div: dir=self; core=core; party=Fair Water Board]"),
          ("2", "point: count; the article's figure against the court's [div: dir=neutral; core=periphery; party=Jane Roe]"),
          ("3", "point: substance; the firm's line against its notes [div: dir=self; core=core; party=Vale Water Authority]")]
    for n, note in xc:
        con.execute("INSERT INTO cross_checks VALUES ('doc-a', ?, 'contradicts', 'contradicts', 'this telling', 'elsewhere', ?)", (n, note))
    con.commit(); con.close()


def run_pack(d):
    env = dict(os.environ, LEDGER_ROOT=d)
    out = os.path.join(d, "out")
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "narrative_pack.py"), "--out", out, "--db", "notes.db"], cwd=d, env=env,
                       capture_output=True, text=True)
    if r.returncode: raise AssertionError(r.stderr[-2000:])
    def read(f):
        with open(os.path.join(out, f), encoding="utf-8") as h: return h.read()
    return read("synchrony-index.md"), read("synchrony/e1.md"), read("contradictions.md")


def node_rows(contradictions):
    """{(source, note row): (score, agency)} from the contradictions table."""
    out = {}
    for line in contradictions.split("\n"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 12 and c[0].isdigit(): out[(c[2], c[3])] = (float(c[1]), c[7])
    return out


class NarrativePackLanes(unittest.TestCase):
    def test_lanes_come_from_the_packs_viewer_table(self):
        d = tmpdir(self); make_project(d)
        index, era, _ = run_pack(d)
        self.assertIn("B Prosecutions and recovery", index)
        self.assertIn("D The critics", index)
        self.assertNotIn("Public record", index)
        self.assertIn("Lane names are the pack's own ([display.viewer.lanes])", index)
        self.assertIn("falls to lane D (The critics), marked lane-rule=fallback", index)
        # the core's public-record wording never places a row in a lane the pack named otherwise: the hearing row falls back
        self.assertRegex(era, r"### D The critics \(\d+\)\n(?:- .*\n)*- \[doc-a tl 1\][^\n]*lane-rule=fallback")
        # the core's money wording still places a row in the pack's lane of the same name
        self.assertRegex(era, r"### E Money and contracts \(1\)\n- \[doc-a tl 2\][^\n]*lane-rule=wording")

    def test_the_packs_own_lane_names_win(self):
        d = tmpdir(self)
        names = "\n".join(f'{k} = "Own {k}"' for k in "ABCDEFGH")
        make_project(d, tools_table=f"[tools.narrative_pack.lane_names]\n{names}\n")
        index, era, _ = run_pack(d)
        self.assertIn("B Own B", index)
        self.assertNotIn("Prosecutions", index)
        self.assertNotIn("Lane names are the pack's own", index)
        self.assertIn("### B Own B (1)\n- [doc-a tl 1]", era)   # the core's wording applies to the pack's own named lanes, as before


class NarrativePackAgency(unittest.TestCase):
    def test_the_agency_mark_comes_from_the_rows_tags(self):
        d = tmpdir(self); make_project(d)
        rows = node_rows(run_pack(d)[2])
        self.assertEqual(rows[("cross_check", "doc-a 1")], (1.1, "yes"))   # the `agency divergence:` prefix
        self.assertEqual(rows[("cross_check", "doc-a 3")], (1.1, "yes"))   # party= names an agency (pack agency word Authority)
        self.assertEqual(rows[("cross_check", "doc-a 2")], (0.6, ""))      # party= names a person
        self.assertEqual(rows[("timeline", "doc-a 3")], (1.5, "yes"))      # contradicts, core, independent, and the agency bonus


class NarrativeApplyDatedRelations(unittest.TestCase):
    def test_a_dated_variant_is_kept_and_an_exact_repeat_skipped(self):
        d = tmpdir(self)
        write(os.path.join(d, "ledger.toml"), '[ledger]\nname = "fixture"\n')
        reg = os.path.join(d, "research", "relations-register.md")
        write(reg, "# Relations\n\n| # | A | B | Kind | Hierarchy | When | What | Source | Chain | Confidence | Added |\n"
                   "|---|---|---|---|---|---|---|---|---|---|---|\n| 1 | Ann Lee | Acme | employer | | 2010 | staff | x | 1 | high | 2026-01-01 |\n")
        page = os.path.join(d, "research", "narrative-x.md")
        write(page, "# X\n\n## Relations returned\n\n| A | B | Kind | Hierarchy | When | What | Source | Chain | Confidence |\n|---|---|---|---|---|---|---|---|---|\n"
                    "| Ann Lee | Acme | employer | | 2010 | staff again | y | 1 | high |\n"
                    "| Ann Lee | Acme | employer | | 2015 to 2018 | rehired | y | 1 | high |\n"
                    "| Bo Kim | Acme | founder | | 2001 | founder | y | 1 | medium |\n")
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "narrative_apply.py"), "research/narrative-x.md"], cwd=d,
                           env=dict(os.environ, LEDGER_ROOT=d), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("relations added: 2 of 3", r.stdout)
        with open(reg, encoding="utf-8") as h: txt = h.read()
        self.assertIn("| 2 | Ann Lee | Acme | employer |  | 2015 to 2018 |", txt)
        self.assertIn("| 3 | Bo Kim | Acme | founder |", txt)
        self.assertEqual(txt.count("| 2010 |"), 1)


PAGE = """# Narrative: fixture

## Nodes

| # | Date | Lane | Node | Carriers (independent roots) | Rows | Depends on | Role |
|---|---|---|---|---|---|---|---|
| 1 | 2010 | A | first | Ann Lee | | none | cause |
| 2 | 2011 | A | second | Ann Lee | | 1 | effect |
| 3 | 2012 | A | third | Ann Lee | | 2 (reading: 1) | effect |
| 4 | 2013 | A | fourth | Ann Lee | | (reading: node three, the 2010 notes; no row joins them) | effect |
| 5 | 2014 | A | fifth | Ann Lee | | (reading: the join is not in the rows) | effect |

## Contradiction ledger

| # | Node | Contradiction | Side taken | Other side | Weight | Downstream | Why survivable | Fork | Flare |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | c | s | o | 1.0 | 2 | w | no | no |
| 2 | 3 | c | s | o | 0.5 | 0 | w | no | no |
"""


class NarrativesReadingEdges(unittest.TestCase):
    def test_depends_on_cells(self):
        import narratives as N
        self.assertEqual(N.depends_on("3, 4"), ([3, 4], [], 0))
        self.assertEqual(N.depends_on("(reading: 14)"), ([], [14], 0))
        self.assertEqual(N.depends_on("5 (reading: node fourteen, the review of 2013; no row joins them)"), ([5], [14], 0))
        self.assertEqual(N.depends_on("(reading: nodes 3 and twenty-five)"), ([], [3, 25], 0))
        self.assertEqual(N.depends_on("parent 7; 2 (reading: the join is unsupported)"), ([7, 2], [], 1))   # other forms read as before

    def test_a_reading_edge_is_out_of_the_closure_and_counted(self):
        import narratives as N
        d = tmpdir(self); p = os.path.join(d, "narrative-fixture.md"); write(p, PAGE)
        r = N.parse(p)
        led = {l["n"]: l for l in r["ledger"]}
        self.assertEqual(led["1"]["downstream_computed"], 2)   # node 1 -> 2 -> 3; the reading edges 3 <- 1 and 4 <- 3 add nothing
        self.assertEqual(led["2"]["downstream_computed"], 0)   # node 4's reading edge on 3 is not a dependency
        self.assertEqual(r["reading_edges"], 2)
        self.assertEqual(r["reading_edges_unresolved"], 1)


if __name__ == "__main__":
    unittest.main()
