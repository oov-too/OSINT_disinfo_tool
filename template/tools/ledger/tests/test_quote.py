"""`ledger quote` (tools/ledger/cli.py quote_cmd, tools/ledger/quote.py; the compact findings form, 2026-10-23): the source's words
by pointer, on synthetic units cut by tools/chunk_source.py from the casebook corpus's sentences (tools/ledger/tests/casebook_corpus.py;
nothing real is named). A pointer prints the unit's header and its lines verbatim; --words prints exactly the words between the
anchors, punctuation and line breaks as the unit has them; --quotations resolves a findings file's compact items; a bad pointer or
anchors not found exit 1. --find (2026-10-25) locates a phrase by word keys in every unit and prints the sentence or caption line
that holds it with its pointer, every hit, and on a miss exit 1 with the near miss.
  python3 tools/ledger/tests/test_quote.py"""
import os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import casebook_corpus as CC
from ledger import quote as Q


def run(args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "ledger.py"), "quote"] + args, cwd=ROOT, capture_output=True, text=True)


class Quote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wip = os.path.join(cls.tmp.name, "task")
        src = os.path.join(cls.tmp.name, "site-record.md")
        # one paragraph broken over two lines, so a span crosses a line break
        paras = [" ".join(CC.SENTENCES[(k + j) % len(CC.SENTENCES)] for j in range(3)) for k in range(12)]
        paras[3] = CC.SENTENCES[0] + "\n" + CC.SENTENCES[1]
        with open(src, "w", encoding="utf-8", newline="\n") as f: f.write("# Site record\n\n" + "\n\n".join(paras) + "\n")
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "chunk_source.py"), src, "--wip", cls.wip, "--words", "5000"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        with open(os.path.join(cls.wip, "units", "001.txt"), encoding="utf-8") as f: cls.lines = f.read().split("\n")
        cls.k = next(i for i, l in enumerate(cls.lines, 1) if l == CC.SENTENCES[0])   # the first of the two broken lines

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_span_is_verbatim_with_the_header(self):
        k = self.k
        r = run(["--wip", self.wip, "u", f"001:{k}-{k + 1}"])
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.split("\n")
        self.assertEqual(out[0], f"[u 001:{k}-{k + 1}] {self.lines[0]}")
        self.assertEqual(out[1:3], self.lines[k - 1:k + 1])

    def test_pointer_forms_and_several_pointers(self):
        r = run(["--wip", self.wip, f"[u 001:{self.k}]", f"u001:{self.k + 1}", "--numbered"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"{self.k:6d}\t{self.lines[self.k - 1]}", r.stdout)
        self.assertIn(f"{self.k + 1:6d}\t{self.lines[self.k]}", r.stdout)

    def test_bad_pointers_exit_1(self):
        for p in (["u", "001:1"], ["u", "001:999"], ["u", "002:5"], ["u", f"001:{self.k + 1}-{self.k}"]):
            with self.subTest(p):
                r = run(["--wip", self.wip] + p)
                self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(run(["--wip", self.wip, "line", "12"]).returncode, 1)

    def test_words_between_anchors_across_a_line_break(self):
        first = " ".join(CC.SENTENCES[0].split()[-4:])      # the last four words of line k ...
        last = " ".join(CC.SENTENCES[1].split()[:4])        # ... to the first four of line k+1
        r = run(["--wip", self.wip, "u", f"001:{self.k}-{self.k + 1}", "--words", f"{first} ... {last}"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split("\n", 1)[1].rstrip("\n"), first + "\n" + last)

    def test_words_keep_the_units_punctuation_and_forgive_case(self):
        w = CC.SENTENCES[0].split()   # "... August 2009 after the weather held the work back."
        r = run(["--wip", self.wip, "u", f"001:{self.k}", "--words", f"{' '.join(w[:4]).upper()} ... the work back"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split("\n", 1)[1].rstrip("\n"), CC.SENTENCES[0][:-1])   # ends at "back", the full stop not a word

    def test_words_not_there_exit_1(self):
        r = run(["--wip", self.wip, "u", f"001:{self.k}", "--words", "the left wall of ... the zebra work back"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("are not on lines", r.stderr)

    def test_quotations_of_a_findings_file(self):
        os.makedirs(os.path.join(self.wip, "findings"), exist_ok=True)
        w = CC.SENTENCES[1].split()
        items = [f"- [u 001:{self.k + 1}] Counsel | words: {' '.join(w[:4])} ... {' '.join(w[-4:])} | use: notable quote",
                 f'- [u 001:{self.k}] Diary | "{" ".join(CC.SENTENCES[0].split()[:6])}" | use: document\'s phrase']
        with open(os.path.join(self.wip, "findings", "001.md"), "w", encoding="utf-8") as f:
            f.write("# Findings: unit 001 of 001\n\n## Claims\n\n- none\n\n## Quotations\n\n" + "\n".join(items) + "\n\n## Names\n\n- none\n")
        r = run(["--wip", self.wip, "--quotations", "001"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(CC.SENTENCES[1][:-1], r.stdout)
        self.assertIn("use: notable quote", r.stdout)
        self.assertIn("the older form", r.stdout)

    def test_library_agrees_with_the_gate_slack(self):
        w = CC.SENTENCES[0].split()
        self.assertIsNotNone(Q.locate(self.lines, self.k + 2, self.k + 2, " ".join(w[:4])))      # two lines' slack
        self.assertIsNone(Q.locate(self.lines, self.k + 6, self.k + 6, " ".join(w[:4])))


class Masking(unittest.TestCase):
    """Pilot defect 11 (7b2, 2026-10-23): only page markers, bare bracketed URLs and a markdown link's target are masked in a unit's
    lines; link text and a transcript's own bracketed words are words a quotation may carry; a writer's [sic] in the anchors is still
    passed over."""
    LINES = ["[unit 001/001] source: x | span: lines 1-6 | words: 40",
             "--- page 3 ---",
             "The minister [promised to introduce legislation](https://example.org/2024/01/08/a_b(c)/), as well as compensation.",
             "Q. And the clause in the [harbour lease], did you read it?",
             "The inspector recieved the ledger on the Tuesday.",
             "[page 4]"]

    def test_link_text_is_quotable(self):
        loc = Q.locate(self.LINES, 3, 3, "promised to introduce legislation as well as compensation")
        self.assertIsNotNone(loc)
        self.assertEqual(Q.text_between(self.LINES, *loc), "promised to introduce legislation](https://example.org/2024/01/08/a_b(c)/), as well as compensation")

    def test_bracketed_source_words_are_quotable(self):
        self.assertIsNotNone(Q.locate(self.LINES, 4, 4, "the clause in the [harbour lease], did you read it"))
        self.assertIsNotNone(Q.locate(self.LINES, 4, 4, "the clause in the harbour lease"))

    def test_writers_sic_is_passed_over(self):
        self.assertIsNotNone(Q.locate(self.LINES, 5, 5, "The inspector recieved [sic] the ledger"))

    def test_page_markers_and_urls_are_not_words(self):
        toks = [t[0] for t in Q._tokens(self.LINES, 2, 6)]
        self.assertNotIn("page", toks); self.assertNotIn("https", toks); self.assertNotIn("example", toks)
        self.assertIn("harbour", toks); self.assertIn("legislation", toks)


class Find(unittest.TestCase):
    """`ledger quote --find "<a few of the words>"` (2026-10-25): word keys as the gate's caption rule reads them."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        sys.path.insert(0, HERE)
        import test_intake_gate as G
        cls.cap = G.caption_wip(cls.tmp.name)          # one hand-made unit: two unpunctuated caption lines, one punctuated line
        cls.cap_lines = [None, None] + G.CAPTION        # cap_lines[L] is the unit file's line L (line 1 the header)
        cls.wip = os.path.join(cls.tmp.name, "doc")
        src = os.path.join(cls.tmp.name, "site-record.md")
        paras = [" ".join(CC.SENTENCES[(k + j) % len(CC.SENTENCES)] for j in range(3)) for k in range(12)]
        paras[3] = CC.SENTENCES[0] + "\n" + CC.SENTENCES[1]
        with open(src, "w", encoding="utf-8", newline="\n") as f: f.write("# Site record\n\n" + "\n\n".join(paras) + "\n")
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "chunk_source.py"), src, "--wip", cls.wip, "--words", "5000"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        with open(os.path.join(cls.wip, "units", "001.txt"), encoding="utf-8") as f: cls.lines = f.read().split("\n")
        cls.k = next(i for i, l in enumerate(cls.lines, 1) if l == CC.SENTENCES[0])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_typed_phrase_finds_the_unpunctuated_caption_line(self):
        r = run(["--wip", self.cap, "--find", "Well, the survey team came out in August"])
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.rstrip("\n").split("\n")
        self.assertTrue(out[0].startswith("[u 001:2] [unit 001/001]"), out[0])
        self.assertEqual(out[1], self.cap_lines[2])                       # the whole caption line, verbatim
        self.assertEqual(out[2], "phrase [u 001:2]: well the survey team came out in august")

    def test_a_phrase_across_a_caption_break_and_its_timestamp(self):
        r = run(["--wip", self.cap, "--find", "before the rain. And I told the foreman"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("[u 001:2-4] "), r.stdout)
        self.assertIn("phrase [u 001:2-4]: before the rain\n\n**[00:01:05]** and i told the foreman", r.stdout)

    def test_the_sentence_of_a_punctuated_line(self):
        r = run(["--wip", self.cap, "--find", "gave the cost as $1500"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("\nIt named the foreman, Mr. Hale, and gave the cost as $1,500 for the repair.\n", r.stdout)   # one sentence, not the line; Mr. is not an end

    def test_a_sentence_across_a_line_break(self):
        w = CC.SENTENCES[1].split()
        r = run(["--wip", self.wip, "--find", " ".join(w[:5])])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(CC.SENTENCES[1], r.stdout)

    def test_every_hit_is_printed_with_its_pointer(self):
        w = CC.SENTENCES[2].split()                       # the corpus repeats its sentences: several hits
        r = run(["--wip", self.wip, "--find", " ".join(w[:6])])
        self.assertEqual(r.returncode, 0, r.stderr)
        m = re.match(r'--find ".*": (\d+) hits', r.stdout)
        self.assertTrue(m, r.stdout[:200]); n = int(m.group(1)); self.assertGreater(n, 1)
        self.assertEqual(len(re.findall(r"^phrase \[u 001:\d+(?:-\d+)?\]: ", r.stdout, re.M)) + len(re.findall(r"^hit \d+ of \d+: \[u", r.stdout, re.M)), n)

    def test_a_changed_word_exits_1_with_the_near_miss(self):
        r = run(["--wip", self.cap, "--find", "the survey team came out in July"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("no unit under", r.stderr); self.assertIn("nearest: [u 001:2]", r.stderr)
        self.assertIn('the source has "august" where the quotation has "july"', r.stderr)

    def test_a_dropped_word_exits_1_with_the_near_miss(self):
        r = run(["--wip", self.cap, "--find", "he said no fine and we poured"])
        self.assertEqual(r.returncode, 1); self.assertIn('the quotation drops "its"', r.stderr)

    def test_nothing_near_says_so(self):
        r = run(["--wip", self.cap, "--find", "zebra quartz violin harbour"])
        self.assertEqual(r.returncode, 1); self.assertIn("no near miss", r.stderr)

    def test_several_finds_run_in_turn(self):
        r = run(["--wip", self.cap, "--find", "we poured anyway", "--find", "zebra quartz violin", "--find", "Mr. Hale"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("phrase [u 001:4]: we poured anyway", r.stdout); self.assertIn("phrase [u 001:6]: Mr. Hale", r.stdout)

    def test_find_takes_no_pointer(self):
        self.assertEqual(run(["--wip", self.cap, "u", "001:2", "--find", "we poured"]).returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
