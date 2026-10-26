"""The assembly step of the unit-writers form (tools/assemble_parts.py, 2026-10-24) on synthetic units cut by tools/chunk_source.py
from the casebook corpus's sentences (nothing real is named): the skeleton's exemplar lines dropped, a Status row added, the
nothing-to-row line above the claims ledger, the parts' rows under the two headers in unit order, nothing else changed; a finished
note never overwritten; the assembled note passes gate 2. And gate 2's matching across a blockquote's `> ` lines.
  python3 tools/ledger/tests/test_assemble_parts.py"""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
import casebook_corpus as CC

SKELETON = """# <title>

<!-- skeleton: test -->

| | |
|---|---|
| **Channel** | <the issuing body> |
| **Speakers** | <every speaker> |

> Note: <the standing note>

## One-paragraph summary
<!-- form section -->

## Claims ledger
<!-- tools/schema.md section 2 -->

| # | Time | Speaker | Topic | Claim | Source class | Move | Note |
|---|---|---|---|---|---|---|---|
| 114 | p3 | Board staff | record-existence | 27 May 1981: "The board approves the survey of the north wall" | record | open | x <!-- example row, delete --> |

## Forthrightness audit
<!-- tools/schema.md section 3 -->

| # | Time | Asked by | Question or prompt | Answer summary | Move | Basis | Note |
|---|---|---|---|---|---|---|---|
| 24 | SGBP | none | Can it stand alone? | "Survey Information Should not Stand Alone" | open | n/a | x <!-- example row, delete --> |

Audit counts: open N, partial N, closed-outright N, closed-subtle N, stated declines N, pseudo-declines N.  <!-- numbers only -->

### (a) Public-record checks

## Notable quotes

1. (0:01:02) "an exemplar's quotation that is in no unit of this source"
2. (0:02:03) "another exemplar quotation from elsewhere entirely" <!-- example row, delete -->

## Open questions
"""


def run(args):
    return subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)


class AssembleParts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wip = os.path.join(cls.tmp.name, "task")
        src = os.path.join(cls.tmp.name, "site-record.md")
        paras = [" ".join(CC.SENTENCES[(k + j) % len(CC.SENTENCES)] for j in range(3)) for k in range(40)]
        with open(src, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Site record\n\n" + "\n\n".join(paras) + "\n\n> The quoted block opens here\n>\n> and it closes on this line.\n")
        r = run([os.path.join(TOOLS, "chunk_source.py"), src, "--wip", cls.wip, "--words", "700"])
        assert r.returncode == 0, r.stdout + r.stderr
        cls.units = sorted(f[:-4] for f in os.listdir(os.path.join(cls.wip, "units")) if f.endswith(".txt"))
        assert len(cls.units) >= 3, cls.units
        with open(os.path.join(cls.wip, "skeleton.md"), "w", encoding="utf-8") as f: f.write(SKELETON)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def lines(self, n):
        return open(os.path.join(self.wip, "units", f"{n}.txt"), encoding="utf-8").read().split("\n")

    def row(self, num, n):
        ls = self.lines(n); k = next(i for i, l in enumerate(ls[1:], 2) if len(l.split()) >= 14)
        return f'| {num} | para. 1 | Counsel | other | Counsel says "{" ".join(ls[k - 1].split()[:7])}" | host | closed-subtle | chain: 1: Counsel (unsourced). [u {n}:{k}] |', k

    def parts(self):
        d = os.path.join(self.wip, "parts"); os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d, f))
        u = self.units; rows = {}
        num = 1
        for n in u[:-1]:
            r1, k = self.row(num, n); r2, _ = self.row(num + 1, n); num += 2
            with open(os.path.join(d, f"u{n}-ledger.md"), "w", encoding="utf-8") as f: f.write(r1 + "\n\n" + r2 + "\n")
            rows[n] = (r1, r2)
        with open(os.path.join(d, f"u{u[0]}-audit.md"), "w", encoding="utf-8") as f:
            f.write(f"| 1 | para. 1 | none; volunteered | (monologue) the point | {' '.join(self.lines(u[0])[self.row(1, u[0])[1] - 1].split()[:8])} | closed-subtle | none stated | [u {u[0]}:{self.row(1, u[0])[1]}] |\n")
        return rows

    def assemble(self, note, nothing=None):
        args = [os.path.join(TOOLS, "assemble_parts.py"), "--wip", self.wip, "--note", note, "--json"] + (["--nothing-to-row", nothing] if nothing else [])
        r = run(args)
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])

    def test_the_note_as_the_form_gives_it(self):
        rows = self.parts(); u = self.units
        note = os.path.join(self.tmp.name, "note.md")
        code, j = self.assemble(note, json.dumps([{"unit": u[-1], "reason": "a closing page (photographs only)"}]))
        self.assertEqual(code, 0, j)
        self.assertEqual((j["claims_rows"], j["audit_rows"]), (2 * (len(u) - 1), 1))
        t = open(note, encoding="utf-8").read().split("\n")
        self.assertNotIn("example", "\n".join(t)); self.assertFalse(any(l.startswith("1. (0:01:02)") for l in t))
        self.assertTrue(any(l.startswith("| **Status** | in progress (assembled") for l in t))
        i = t.index("## Claims ledger")
        self.assertEqual(t[i - 2], f"Units with nothing to row: {u[-1]} (a closing page (photographs only))")
        hdr = t.index("| # | Time | Speaker | Topic | Claim | Source class | Move | Note |")
        got = [l for l in t[hdr + 2:] if l.startswith("| ")][:2 * (len(u) - 1)]
        self.assertEqual(got, [r for n in u[:-1] for r in rows[n]])
        a = t.index("| # | Time | Asked by | Question or prompt | Answer summary | Move | Basis | Note |")
        self.assertTrue(t[a + 2].startswith("| 1 | para. 1 | none; volunteered"))
        self.assertIn("Audit counts: open N", "\n".join(t)); self.assertIn("### (a) Public-record checks", t)
        out = os.path.join(self.tmp.name, "out"); os.makedirs(out, exist_ok=True)
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", note, "--wip", self.wip, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_reassembly_yes_a_finished_note_never(self):
        self.parts()
        note = os.path.join(self.tmp.name, "note2.md")
        self.assertEqual(self.assemble(note)[0], 0)
        self.assertEqual(self.assemble(note)[0], 0)          # an earlier assembly is replaced (the fix loop)
        t = open(note, encoding="utf-8").read().replace("in progress (assembled", "complete (")
        with open(note, "w", encoding="utf-8") as f: f.write(t)
        code, j = self.assemble(note)
        self.assertEqual(code, 1); self.assertIn("not an earlier assembly", j["summary"])
        self.assertEqual(open(note, encoding="utf-8").read(), t)

    def test_a_quotation_across_blockquote_lines_matches(self):
        sys.path.insert(0, TOOLS)
        import importlib.util
        spec = importlib.util.spec_from_file_location("intake_gate_b", os.path.join(TOOLS, "intake_gate.py"))
        G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
        last = G.load_unit(self.wip, self.units[-1])
        self.assertGreaterEqual(G.find_quote(G.quote_segments("The quoted block opens here and it closes on this line"), last["text"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
