"""The sample reading's core (2026-10-25, wip/sample-phase/): `ledger sample draw` (twenty claims rows by seed, spread over the units,
each beside its span; the single-agent form's rows by their Time cell and the first --find hit), `ledger sample tally` (the reader's
TSV into report.json's sample_reading, the redraw under .redraw), the threshold from the pack's [intake] sample_threshold (packload;
the briefs' slot pack.sample_threshold), and the cost log's sample line that `ledger integrate` writes and the status page reads.
  python3 tools/ledger/tests/test_sample.py"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
from ledger import sample as SM, briefs as BR

HEAD = "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |\n|---|---|---|---|---|---|---|---|\n"


def rd(p):
    with open(p, encoding="utf-8") as f: return f.read()


def unit(n, lines):
    return f"[unit {n}/002 | lisle-memo-2015.txt lines 1-{len(lines)}]\n" + "\n".join(lines) + "\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ledger-sample-test-"); self.addCleanup(shutil.rmtree, self.d, True)
        with open(os.path.join(self.d, "ledger.toml"), "w") as f: f.write('[ledger]\nname = "t"\n[pack]\npath = "packs/t"\n')
        os.makedirs(os.path.join(self.d, "packs", "t"))
        with open(os.path.join(self.d, "packs", "t", "pack.toml"), "w") as f: f.write('[pack]\nname = "t"\n\n[intake]\nsample_threshold = 5\n')
        self.wip = os.path.join(self.d, "wip", "t1"); os.makedirs(os.path.join(self.wip, "units"))
        u1 = [f"Line {i} of the memo says the harbour lease was signed on day {i}." for i in range(2, 42)]
        u2 = [f"Line {i} of the annex records that the inspector visited berth {i}." for i in range(2, 22)]
        with open(os.path.join(self.wip, "units", "001.txt"), "w") as f: f.write(unit("001", u1))
        with open(os.path.join(self.wip, "units", "002.txt"), "w") as f: f.write(unit("002", u2))
        rows = [f"| {k} | p. 1 | Lisle | lease | Says the lease was \"signed on day {k + 1}\" | host | closed-subtle | attribution: Lisle; chain: 1: memo. [u 001:{k + 1}] |" for k in range(1, 31)]
        rows += [f"| {k} | annex | Lisle | inspection | The inspector \"visited berth {k - 29}\" | host | n/a | [u 002:{k - 29}-{k - 28}] |" for k in range(31, 41)]
        self.note = os.path.join(self.d, "books", "lisle-memo-2015.md"); os.makedirs(os.path.dirname(self.note))
        with open(self.note, "w") as f: f.write("# Lisle memo\n\n## Claims ledger\n\n" + HEAD + "\n".join(rows) + "\n\n## Forthrightness audit\n\n| 1 | x |\n")

    def cli(self, *a):
        env = dict(os.environ, LEDGER_ROOT=self.d)
        return subprocess.run([sys.executable, os.path.join(ROOT, "ledger.py"), "sample", *a], cwd=self.d, capture_output=True, text=True, env=env)


class Draw(Fixture):
    def test_twenty_rows_by_seed_spread_over_the_units_each_beside_its_span(self):
        r = SM.draw(self.note, self.wip, root=self.d)
        self.assertTrue(r["ok"]); self.assertEqual((r["rows"], r["total"]), (20, 40))
        self.assertEqual(r["seed"], SM.default_seed("lisle-memo-2015")); self.assertEqual(r["spread"], {"001": [15, 30], "002": [5, 10]})
        text = rd(os.path.join(self.wip, "sample.md"))
        head = text.split("\n")[0]
        self.assertIn("`books/lisle-memo-2015.md`: 20 of 40 claims rows, seed", head); self.assertIn("unit 001 15 of 30, unit 002 5 of 10", head)
        self.assertEqual(len(re.findall(r"^## Row \d+", text, re.M)), 20)
        m = re.search(r"^## Row (\d+) \(note line (\d+)\)\n\n.*\n.*\n(\| \1 \|.*)\n\nSpan of pointer \[u 001:(\d+)\]: \[u 001:(\d+)-(\d+)\]", text, re.M)
        self.assertTrue(m, text[:1500])
        a, lo, hi = int(m.group(4)), int(m.group(5)), int(m.group(6))
        self.assertEqual((lo, hi), (max(2, a - 2), min(41, a + 2)))   # two lines either side, clamped to the unit's body
        self.assertIn(f"signed on day {a}.", text)
        # the same seed draws the same rows; another seed or round others
        self.assertEqual(SM.draw(self.note, self.wip, out=os.path.join(self.wip, "again.md"), root=self.d)["seed"], r["seed"])
        self.assertEqual(rd(os.path.join(self.wip, "again.md")).split("\n")[2:], text.split("\n")[2:])
        r2 = SM.draw(self.note, self.wip, rnd=2, root=self.d)
        self.assertEqual(r2["file"], "wip/t1/sample-2.md"); self.assertNotEqual(r2["seed"], r["seed"])

    def test_one_row_per_unit_while_twenty_allow(self):
        picked, spread = SM.draw_rows(SM.claims_rows(self.note), 3, 1)
        self.assertEqual({u: t for u, (t, _) in spread.items()}, {"001": 2, "002": 1})

    def test_rows_without_pointers_get_the_time_cell_and_the_first_find_hit(self):
        rows = ['| 1 | 00:01:10 | Lisle | lease | Says the lease was "signed on day 7" | firsthand | open | from the call |',
                '| 2 | 00:02:00 | Lisle | lease | Says "nothing like this is in the memo" | host | open | |',
                '| 3 | 00:03:00 | Lisle | lease | Speaks of the berth | host | open | |']
        with open(self.note, "w") as f: f.write("# x\n\n## Claims ledger\n\n" + HEAD + "\n".join(rows) + "\n")
        r = SM.draw(self.note, self.wip, root=self.d)
        self.assertEqual((r["rows"], r["pointers"], r["found_by_find"]), (3, False, 1))
        text = rd(os.path.join(self.wip, "sample.md"))
        self.assertIn("no pointer 3 of 3", text.split("\n")[0]); self.assertIn("Time cell: `00:01:10`", text)
        self.assertIn('First `--find` hit for "signed on day 7": [u 001:7-7]', text)
        self.assertIn("No `--find` hit for a quoted stretch of this row: locate", text)
        self.assertIn("(it quotes nothing)", text)

    def test_the_command(self):
        r = self.cli("draw", "books/lisle-memo-2015.md", "--wip", "wip/t1", "--seed", "11", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = json.loads(r.stdout.strip().split("\n")[-1])
        self.assertEqual((j["seed"], j["rows"], j["file"], j["threshold"]), (11, 20, "wip/t1/sample.md", 5))   # the pack's [intake] sample_threshold


class Tally(Fixture):
    def tsv(self, name, kinds):
        lines = ["row\tverbatim\tsupport\tgrain\tclass_move\tchain\tverdict\tkind\towner"]
        for i, k in enumerate(kinds, 1):
            lines.append(f"{i}\tpass\tok\tok\tok\tok\tsound\t\t" if k == "s" else f"{i}\tpass\toverstates\tok\tok\tok\tfaulty\t{'meaning' if k == 'm' else 'formal'}\t{'reader' if k == 'm' else 'writer'}")
        with open(os.path.join(self.wip, name), "w") as f: f.write("\n".join(lines) + "\n")

    def test_the_tsv_into_report_json_and_the_redraw_beside_it(self):
        with open(os.path.join(self.wip, "report.json"), "w") as f: json.dump({"file": "books/lisle-memo-2015.md"}, f)
        SM.draw(self.note, self.wip, root=self.d)
        self.tsv("sample-reading.tsv", "s" * 14 + "fff" + "mmm")
        r = SM.tally(self.wip, thr=3, root=self.d)
        self.assertTrue(r["ok"]); self.assertEqual((r["rows"], r["sound"], r["formal"], r["meaning"]), (20, 14, 3, 3))
        self.assertEqual(r["by_owner"], {"reader": 3, "writer": 3, "form": 0}); self.assertEqual(r["meaning_rows"], ["18", "19", "20"])
        self.assertEqual((r["over_threshold"], r["action"]), (True, "check"))
        rep = json.loads(rd(os.path.join(self.wip, "report.json")))
        sr = rep["sample_reading"]; self.assertEqual(sr["seed"], SM.default_seed("lisle-memo-2015")); self.assertIn("wip/t1/sample-reading.tsv", sr["files"])
        self.assertEqual(rep["file"], "books/lisle-memo-2015.md")
        SM.draw(self.note, self.wip, rnd=2, root=self.d); self.tsv("sample-reading-2.tsv", "s" * 19 + "m")
        r2 = SM.tally(self.wip, rnd=2, thr=3, on_threshold="flag", root=self.d)
        self.assertEqual((r2["meaning"], r2["action"]), (1, "none"))
        sr = json.loads(rd(os.path.join(self.wip, "report.json")))["sample_reading"]
        self.assertEqual((sr["meaning"], sr["redraw"]["meaning"], sr["redraw"]["round"]), (3, 1, 2))
        # the report check accepts what the tally wrote
        import importlib.util
        spec = importlib.util.spec_from_file_location("rc_s", os.path.join(TOOLS, "report_check.py")); RC = importlib.util.module_from_spec(spec); spec.loader.exec_module(RC)
        self.assertEqual(RC.check_sample({"sample_reading": sr}, "integrate")[0], [])
        self.assertEqual(SM.summary_line(sr), "sample: meaning 3 of 20 (sound 14, formal 3; reader 3, writer 3, form 0); threshold 3 reached (check); "
                                              "after the check: meaning 1 of 20 (sound 19, formal 0; reader 1, writer 0, form 0)")

    def test_the_reply_when_there_is_no_tsv_and_the_difference_when_both(self):
        reply = {"rows": 20, "sound": 18, "formal": 1, "meaning": 1, "by_owner": {"reader": 0, "writer": 2, "form": 0}, "meaning_rows": [4], "files": []}
        r = SM.tally(self.wip, thr=3, reply=reply, root=self.d)
        self.assertEqual((r["source"], r["meaning"], r["meaning_rows"], r["action"]), ("reply", 1, ["4"], "none"))
        self.tsv("sample-reading.tsv", "s" * 18 + "mm")
        r = SM.tally(self.wip, thr=3, reply=reply, root=self.d)
        self.assertEqual(r["source"], "tsv"); self.assertIn("meaning 1 in the reply, 2 in the TSV", r["reply_differs"])
        self.assertFalse(SM.tally(os.path.join(self.d, "wip"), root=self.d)["ok"])   # nothing to count

    def test_the_command_takes_the_pack_threshold(self):
        self.tsv("sample-reading.tsv", "s" * 16 + "mmmm")
        r = self.cli("tally", "--wip", "wip/t1", "--on-threshold", "flag", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = json.loads(r.stdout.strip().split("\n")[-1])
        self.assertEqual((j["meaning"], j["threshold"], j["over_threshold"], j["action"]), (4, 5, False, "none"))


class CostLogAndSlot(Fixture):
    def test_integrate_writes_the_line_and_the_status_page_reads_it_back(self):
        log = os.path.join(self.d, "research", "cost-log.md"); os.makedirs(os.path.dirname(log))
        with open(log, "w") as f: f.write("# Cost log\n\n" + "\n".join(SM.COST_HEADER) + "\n| wf_1 | 2026-10-25 | intake:t1 | Intake | opus | 1 | 1 | 1k | 1k | 1k | 1k | 1k | 0h01m | ok |\n")
        rp = os.path.join(self.wip, "report.json")
        sr = {"rows": 20, "sound": 17, "formal": 2, "meaning": 1, "by_owner": {"reader": 0, "writer": 3, "form": 0}, "meaning_rows": ["9"], "files": []}
        with open(rp, "w") as f: json.dump({"file": "books/lisle-memo-2015.md", "sample_reading": sr}, f)
        os.environ["LEDGER_ROOT"] = self.d
        try:
            msg = SM.record_cost_log(rp, run="pilot-1026", path=log, day="2026-10-26")
            self.assertIn("line appended", msg)
            sr["meaning"] = 2; sr["meaning_rows"] = ["9", "10"]; sr["sound"] = 16
            with open(rp, "w") as f: json.dump({"file": "books/lisle-memo-2015.md", "sample_reading": sr}, f)
            self.assertIn("line replaced", SM.record_cost_log(rp, run="pilot-1026", path=log, day="2026-10-26"))
        finally: os.environ.pop("LEDGER_ROOT")
        lines = rd(log).split("\n")
        self.assertEqual(sum(1 for l in lines if "**sample reading, t1**" in l), 1)
        row = next(l for l in lines if "**sample reading, t1**" in l)
        self.assertEqual(len(row.strip().strip("|").split("|")), 14)   # the cost log's fourteen columns
        got = SM.cost_log_readings(log)
        self.assertEqual(list(got), ["books/lisle-memo-2015.md"])
        task, run, day, res = got["books/lisle-memo-2015.md"]
        self.assertEqual((task, run, day), ("t1", "pilot-1026", "2026-10-26")); self.assertTrue(res.startswith("sample: meaning 2 of 20"))
        self.assertEqual(SM.summary_line(None), "none"); self.assertEqual(SM.summary_line({"skipped": "sample false"}), "skipped (sample false)")

    def test_the_slot_comes_from_the_pack_toml_intake_table_else_the_core_default(self):
        try: tdir = BR.templates_dir(ROOT)   # the plugin's templates as the renderer finds them (in an installed project, the bundle's plugin)
        except FileNotFoundError: self.skipTest("no brief templates on this machine")
        self.assertEqual(BR.slot_values(self.d, templates=tdir)["sample_threshold"], (5, "pack"))
        self.assertEqual(BR.slot_values(self.d, templates=tdir, defaults_only=True)["sample_threshold"], (3, "core default"))
        r = BR.render(self.d, templates=tdir, only=["staged/sample.md"], check=True)
        self.assertEqual(r["missing"], []); self.assertIn("sample_threshold", r["from_pack"])

    def test_packload_reads_the_threshold_with_default_3(self):
        code = "import packload; print(packload.sample_threshold(), packload.intake()['sample_threshold'])"
        for toml, want in (('[pack]\nname = "t"\n\n[intake]\nsample_threshold = 5\n', "5 5"), ('[pack]\nname = "t"\n', "3 3")):
            with open(os.path.join(self.d, "packs", "t", "pack.toml"), "w") as f: f.write(toml)
            r = subprocess.run([sys.executable, "-c", code], cwd=self.d, capture_output=True, text=True, env=dict(os.environ, LEDGER_ROOT=self.d, PYTHONPATH=TOOLS))
            self.assertEqual(r.stdout.strip(), want, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
