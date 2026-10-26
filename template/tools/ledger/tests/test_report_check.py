"""tools/report_check.py against the lists `ledger integrate` reads (2026-10-22: two report shapes passed the check and then stopped
the integrate step). Fixtures: tools/ledger/tests/fixtures/report_lists.json, one good and one bad element per list, in the shapes
of archived intake reports with the casebook corpus's values. And the note the report names: an unfilled `<!-- fill -->` marker left
in it fails the intake forms (2026-10-23, the round-trip REPORT.md finding 5).
  python3 tools/ledger/tests/test_report_check.py"""
import json, os, subprocess, sys, tempfile, unittest, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
spec = importlib.util.spec_from_file_location("report_check_t", os.path.join(TOOLS, "report_check.py"))
RC = importlib.util.module_from_spec(spec); spec.loader.exec_module(RC)
FIX = json.load(open(os.path.join(HERE, "fixtures", "report_lists.json"), encoding="utf-8"))
LISTS = [k for k in FIX if not k.startswith("_")]

# the actor register's header as the actors step reads it (the register's own columns after #), the first-utterance ids and the
# notes that exist: injected, so the test does not depend on this project's registers
HEADER = ["#", "Actor or kind (teller's name)", "Body as described", "Teller and note row", "Firsthand / relayed (chain)", "Goals or role",
          "Polity", "Matches cluster", "Confidence"]


def ctx():
    return RC.Context(match_keys=["match to sample"], rows_key="actor_rows", header=HEADER, fu_ids={"FU-3"},
                      note_exists=lambda rel: rel in ("videos/harrowmere-day-12.md", "books/lisle-memo-2015.md"))


class Lists(unittest.TestCase):
    def test_every_list_has_a_good_and_a_bad_fixture(self):
        self.assertEqual(set(LISTS), {"register_new", "register_updates", "relations", "chain_leads", "first_telling_rows", "answered_questions", "actor_rows"})

    def test_good_elements_pass(self):
        for k in LISTS:
            with self.subTest(k):
                probs, warns = RC.check_lists({k: [FIX[k]["good"]]}, ctx())
                self.assertEqual(probs, [], k)

    def test_bad_elements_fail_with_index_and_example(self):
        for k in LISTS:
            with self.subTest(k):
                rep = {k: [FIX[k]["good"], FIX[k]["bad"]]}
                probs, _ = RC.check_lists(rep, ctx())
                self.assertEqual(len(probs), 1, probs)
                self.assertTrue(probs[0].startswith(f"{k}[1]: "), probs[0])           # the offending index
                self.assertIn(FIX[k]["bad_says"].split("[0]: ", 1)[-1], probs[0])
                self.assertIn("; accepted: ", probs[0])                                # a one-line example of the accepted shape

    def test_unknown_cluster_and_missing_note_fail(self):
        p, _ = RC.check_lists({"first_telling_rows": [dict(FIX["first_telling_rows"]["good"], cluster="FU-99")]}, ctx())
        self.assertIn("not in the first-utterance register", p[0])
        p, _ = RC.check_lists({"answered_questions": [dict(FIX["answered_questions"]["good"], note="videos/no-such-note.md")]}, ctx())
        self.assertIn("does not exist", p[0])

    def test_keys_the_step_does_not_read_are_warnings(self):
        it = dict(FIX["register_new"]["good"], note="a remark the register has no cell for")
        p, w = RC.check_lists({"register_new": [it]}, ctx())
        self.assertEqual(p, []); self.assertTrue(any("note" in x for x in w))
        it = dict(FIX["register_new"]["good"]); it["match to sample"] = it.pop("match")   # a pack alias of Match is read
        p, w = RC.check_lists({"register_new": [it]}, ctx())
        self.assertEqual((p, w), ([], []))

    def test_counts_under_the_narrative_forms_are_not_lists(self):
        p, _ = RC.check_lists({"leads": 4, "relations": 2}, ctx(), form="narrative")
        self.assertEqual(p, [])
        p, _ = RC.check_lists({"relations": 2}, ctx(), form="integrate")
        self.assertTrue(p and p[0].startswith("relations: int"))

    def test_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "report.json")
            with open(p, "w", encoding="utf-8") as f: json.dump({"file": "videos/harrowmere-day-12.md", "relations": [FIX["relations"]["good"], FIX["relations"]["bad"]]}, f)
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "report_check.py"), p, "--form", "integrate"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("relations[1]: no `a` and `b`", r.stdout)
            with open(p, "w", encoding="utf-8") as f: json.dump({"file": "videos/harrowmere-day-12.md", "relations": [FIX["relations"]["good"]], "sample_reading": SAMPLE}, f)
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "report_check.py"), p, "--form", "integrate"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


SAMPLE = {"rows": 20, "sound": 14, "formal": 4, "meaning": 2, "by_owner": {"reader": 1, "writer": 5, "form": 0}, "meaning_rows": ["7", "12"],
          "files": ["wip/t/sample.md", "wip/t/sample-reading.md", "wip/t/sample-reading.tsv"], "seed": 7, "threshold": 3, "over_threshold": False, "action": "none"}


class SampleReading(unittest.TestCase):
    """sample_reading is required under the intake forms from 2026-10-25 (the sample phase); --pre-sample for a check before it."""
    def test_missing_fails_naming_the_phase_unless_pre_sample(self):
        for form in RC.INTAKE_FORMS:
            p, n = RC.check_sample({}, form)
            self.assertEqual(len(p), 1); self.assertIn("missing key: sample_reading", p[0]); self.assertIn("the sample phase", p[0]); self.assertIn("ledger sample tally", p[0])
            p, n = RC.check_sample({}, form, pre_sample=True)
            self.assertEqual(p, []); self.assertTrue(n and "not yet in the report" in n[0])
        self.assertEqual(RC.check_sample({}, "narrative"), ([], []))

    def test_shapes(self):
        self.assertEqual(RC.check_sample({"sample_reading": SAMPLE}, "integrate")[0], [])
        self.assertEqual(RC.check_sample({"sample_reading": {**SAMPLE, "redraw": dict(SAMPLE)}}, "integrate")[0], [])
        self.assertEqual(RC.check_sample({"sample_reading": {"skipped": "sample false"}}, "intake-document")[0], [])
        bad = [({"rows": "20"}, "sample_reading.rows"), ({"meaning_rows": ["7"]}, "1 row(s) listed for meaning 2"), ({"by_owner": {"reader": 1}}, "by_owner"),
               ({"sound": 18}, "more than rows"), ({"files": "x"}, "files"), ({"redraw": {"rows": 20}}, "sample_reading.redraw.sound")]
        for over, want in bad:
            p = RC.check_sample({"sample_reading": {**SAMPLE, **over}}, "integrate")[0]
            self.assertTrue(any(want in x for x in p), (over, p))
        self.assertTrue(RC.check_sample({"sample_reading": 3}, "integrate")[0])
        self.assertTrue(RC.check_sample({"sample_reading": {"skipped": ""}}, "integrate")[0])

    def test_the_command_and_pre_sample(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ledger.toml"), "w") as f: f.write("")
            p = os.path.join(d, "report.json")
            with open(p, "w", encoding="utf-8") as f: json.dump({"file": "videos/none.md"}, f)
            env = dict(os.environ, LEDGER_ROOT=d)
            run = lambda *x: subprocess.run([sys.executable, os.path.join(TOOLS, "report_check.py"), p, "--form", "integrate", *x], cwd=d, capture_output=True, text=True, env=env)
            r = run(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("missing key: sample_reading (the sample phase", r.stdout)
            r = run("--pre-sample"); self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn("NOTE sample_reading not yet in the report", r.stdout)


class FillMarkers(unittest.TestCase):
    def note(self, d, text):
        os.makedirs(os.path.join(d, "videos"), exist_ok=True)
        with open(os.path.join(d, "videos", "harrowmere-day-12.md"), "w", encoding="utf-8") as f: f.write(text)

    def test_markers_in_the_note_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.note(d, "# Day 12\n\n| **Date** | <!-- fill --> |\n| **URL** | x |\n\n| 1 | <!-- fill --> | <!-- fill --> |\n")
            p = RC.fill_markers({"file": "videos/harrowmere-day-12.md"}, d)
            self.assertEqual(len(p), 1)
            self.assertIn("3 unfilled `<!-- fill -->` marker(s)", p[0]); self.assertIn("lines 3, 6", p[0])
            self.assertEqual(len(RC.fill_markers({"file": os.path.join(d, "videos", "harrowmere-day-12.md")}, "/nowhere")), 1)   # an absolute path

    def test_a_filled_note_and_no_note_pass(self):
        with tempfile.TemporaryDirectory() as d:
            self.note(d, "# Day 12\n\n| **Date** | 2015-03-02 |\n")
            self.assertEqual(RC.fill_markers({"file": "videos/harrowmere-day-12.md"}, d), [])
            self.assertEqual(RC.fill_markers({"file": "videos/no-such-note.md"}, d), [])
            self.assertEqual(RC.fill_markers({}, d), [])

    def test_the_command_fails_an_intake_report_on_markers(self):
        with tempfile.TemporaryDirectory() as d:
            self.note(d, "# Day 12\n\n| **Date** | <!-- fill --> |\n")
            with open(os.path.join(d, "ledger.toml"), "w") as f: f.write("")
            p = os.path.join(d, "report.json")
            with open(p, "w", encoding="utf-8") as f: json.dump({"file": "videos/harrowmere-day-12.md"}, f)
            env = dict(os.environ, LEDGER_ROOT=d)
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "report_check.py"), p, "--form", "integrate"], cwd=d, capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("unfilled `<!-- fill -->` marker", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
