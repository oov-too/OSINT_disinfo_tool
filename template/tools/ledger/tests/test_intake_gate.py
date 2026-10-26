"""Gate 1 of the staged intake (tools/intake_gate.py --findings) on synthetic units cut by tools/chunk_source.py from the casebook
corpus's sentences (tools/ledger/tests/casebook_corpus.py; nothing real is named).

The case (2026-10-22, the round-trip run): a heading whose section runs on into the next unit puts `under "<heading>"` in that
unit's header span; the findings file's head line `unit:` copies the header exactly, and the quotation scan must not demand the
quoted heading verbatim in the unit's body. The `unit:` line is compared with the header instead.
The compact findings form (2026-10-23, wip/compact-findings/): a `## Quotations` item carries its pointer and the first four and
last four words of the span (`words: <first four> ... <last four>`), never the text; the gate locates the anchors in order on the
pointer's lines.
The item allowance (2026-10-23, the owner's ruling after wip/compact-findings/REPORT.md section 4): a findings file's words are at
most 200 + 35 per claim item + 30 per question item + 20 per quotation item + 25 per other item; over it, gate 1 fails unless the
head carries a valid exception line `size: over budget: <section>: <n> items over <cap> words: <reason>` (the section present, at
least n of its items over the cap, the cap at least the section's rate, a reason that is not density, and the file within the
allowance once that section's excess is excused). --budget R keeps the older ratio check for archived findings (a warning, a
failure with --strict, any exception line honoured). Gate 2 accepts the `Units with nothing to row:` line anywhere in the note.
Gate 2's parts mode (2026-10-24, the unit writers): `--note-parts <dir> --wip <wip> --units A-B` checks u<NNN>-ledger.md and
u<NNN>-audit.md as gate 2 checks a note (quotations verbatim in the pointer's unit, pointers holding the row's words, numbering on
without gaps, every unit cited or in the nothing-to-row list); `--quotes-only` checks a note's quotations and nothing else.
The caption rule (owner 2026-10-25, wip/quote-tool-adoption/): in gate 2 (a note, --quotes-only, the parts) a quotation whose word
keys are the unit's in order passes as `punctuation only` (punctuation, capitals and apostrophes added to an unpunctuated caption),
reported apart and never a failure; a changed, added or dropped word fails as `changed words`, with the nearest window's difference.
  python3 tools/ledger/tests/test_intake_gate.py"""
import json, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import casebook_corpus as CC

HEADING = "The spillway wall and its night pour"   # over the gate's four-word quotation threshold, never in the second unit's body


def source_text():
    paras = []
    for k in range(18):   # one heading's section long enough to run across units at --words 120
        paras.append(" ".join(CC.SENTENCES[(k + j) % len(CC.SENTENCES)] for j in range(3)))
    return "# Site record\n\n## " + HEADING + "\n\n" + "\n\n".join(paras) + "\n"


def run(args):
    return subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True)


class Gate1CarriedHeading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wip = os.path.join(cls.tmp.name, "task")
        src = os.path.join(cls.tmp.name, "site-record.md")
        with open(src, "w", encoding="utf-8", newline="\n") as f: f.write(source_text())
        r = run([os.path.join(TOOLS, "chunk_source.py"), src, "--wip", cls.wip, "--words", "120"])
        assert r.returncode == 0, r.stdout + r.stderr
        sys.path.insert(0, TOOLS)
        import importlib.util
        spec = importlib.util.spec_from_file_location("intake_gate_t", os.path.join(TOOLS, "intake_gate.py"))
        cls.G = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.G)
        cls.units = sorted(f[:-4] for f in os.listdir(os.path.join(cls.wip, "units")) if f.endswith(".txt"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def unit_lines(self, n):
        with open(os.path.join(self.wip, "units", f"{n}.txt"), encoding="utf-8") as f: return f.read().split("\n")

    def write_findings(self, n, unit_line=None, quote=None):
        lines = self.unit_lines(n)
        k = next(i for i, l in enumerate(lines[1:], 2) if len(l.split()) >= 8)   # a body line to quote and point at
        words = quote or " ".join(lines[k - 1].split()[:6])
        body = [f"unit: {unit_line if unit_line is not None else lines[0]}", "status: complete", "reader: test", ""]
        for s in self.G.REQUIRED_SECTIONS:
            body += [f"## {s}", ""]
            if s == "Claims": body.append(f"- claim: {words} [u {n}:{k}]")
            elif s == "Quotations": body.append(f'- "{words}" [u {n}:{k}]')
            else: body.append("- none in this unit")
            body.append("")
        os.makedirs(os.path.join(self.wip, "findings"), exist_ok=True)
        with open(os.path.join(self.wip, "findings", f"{n}.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))

    def gate(self):
        os.makedirs(os.path.join(self.tmp.name, "out"), exist_ok=True)   # the gate's --out folder must exist
        return run([os.path.join(TOOLS, "intake_gate.py"), "--findings", "--wip", self.wip, "--out", os.path.join(self.tmp.name, "out")])

    def test_fixture_carries_the_heading(self):
        later = [n for n in self.units[1:] if f'under "{HEADING}"' in self.unit_lines(n)[0]]
        self.assertTrue(later, "the fixture must put a carried heading in a later unit's header")
        self.assertTrue(all(HEADING not in "\n".join(self.unit_lines(n)[1:]) for n in later))

    def test_header_copy_passes(self):
        for n in self.units: self.write_findings(n)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unit_line_must_equal_the_header(self):
        for n in self.units: self.write_findings(n)
        n = self.units[-1]
        self.write_findings(n, unit_line=self.unit_lines(n)[0].replace("lines", "line"))
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        rep = open(os.path.join(self.tmp.name, "out", "gate-findings.md"), encoding="utf-8").read()
        self.assertIn("`unit:` line is not the unit file's header", rep)

    def test_a_misquote_still_fails(self):
        for n in self.units: self.write_findings(n)
        self.write_findings(self.units[-1], quote="words the unit never carries at all")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        rep = open(os.path.join(self.tmp.name, "out", "gate-findings.md"), encoding="utf-8").read()
        self.assertIn("not verbatim in unit", rep)


class Gate1CompactForm(unittest.TestCase):
    """The compact quotation item and the size check, on the same synthetic units."""
    @classmethod
    def setUpClass(cls):
        # units of about 1,500 words, so a findings file of a few items sits inside the quarter budget
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wip = os.path.join(cls.tmp.name, "task")
        src = os.path.join(cls.tmp.name, "site-record.md")
        paras = [" ".join(CC.SENTENCES[(k + j) % len(CC.SENTENCES)] for j in range(3)) for k in range(80)]
        with open(src, "w", encoding="utf-8", newline="\n") as f: f.write("# Site record\n\n" + "\n\n".join(paras) + "\n")
        r = run([os.path.join(TOOLS, "chunk_source.py"), src, "--wip", cls.wip, "--words", "1500"])
        assert r.returncode == 0, r.stdout + r.stderr
        import importlib.util
        spec = importlib.util.spec_from_file_location("intake_gate_c", os.path.join(TOOLS, "intake_gate.py"))
        cls.G = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.G)
        cls.units = sorted(f[:-4] for f in os.listdir(os.path.join(cls.wip, "units")) if f.endswith(".txt"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    unit_lines = Gate1CarriedHeading.unit_lines
    gate = Gate1CarriedHeading.gate

    def span_line(self, n):
        lines = self.unit_lines(n)
        return next(i for i, l in enumerate(lines[1:], 2) if len(l.split()) >= 14)

    def write_compact(self, n, words=None, pointer=True, head_extra=(), padding=0, quotes_line=None):
        lines = self.unit_lines(n)
        k = self.span_line(n)
        w = lines[k - 1].split()
        anchors = words if words is not None else " ".join(w[:4]) + " ... " + " ".join(w[-4:])
        claim = " ".join(w[:8])
        ptr = f"[u {n}:{k}] " if pointer else ""
        body = [f"unit: {lines[0]}", "status: complete", "reader: test", *head_extra, ""]
        for s in self.G.REQUIRED_SECTIONS:
            body += [f"## {s}", ""]
            if s == "Claims": body.append(f"- [u {n}:{k}] Counsel | other | read | n/a | claim: {claim} | chain: 0 | loc: para. 1" + (" filler" * padding))
            elif s == "Quotations": body.append(quotes_line if quotes_line is not None else f"- {ptr}Counsel | words: {anchors} | use: notable quote")
            else: body.append("- none in this unit")
            body.append("")
        os.makedirs(os.path.join(self.wip, "findings"), exist_ok=True)
        with open(os.path.join(self.wip, "findings", f"{n}.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))

    def report(self):
        return open(os.path.join(self.tmp.name, "out", "gate-findings.md"), encoding="utf-8").read()

    def gate_args(self, *extra):
        os.makedirs(os.path.join(self.tmp.name, "out"), exist_ok=True)
        return run([os.path.join(TOOLS, "intake_gate.py"), "--findings", "--wip", self.wip, "--out", os.path.join(self.tmp.name, "out"), *extra])

    def test_compact_quotation_passes(self):
        for n in self.units: self.write_compact(n)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("compact items located by their anchors", self.report())

    def test_short_quotation_given_whole_passes(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]; w = self.unit_lines(n)[self.span_line(n) - 1].split()
        self.write_compact(n, words=" ".join(w[2:7]))
        self.assertEqual(self.gate().returncode, 0)

    def test_changed_anchor_word_fails(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]; w = self.unit_lines(n)[self.span_line(n) - 1].split()
        self.write_compact(n, words=" ".join(w[:3]) + " zebra ... " + " ".join(w[-4:]))
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("are not on lines", self.report())

    def test_anchors_out_of_order_fail(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]; w = self.unit_lines(n)[self.span_line(n) - 1].split()
        self.write_compact(n, words=" ".join(w[-4:]) + " ... " + " ".join(w[:4]))
        self.assertEqual(self.gate().returncode, 1)

    def test_anchors_on_another_line_fail(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]; lines = self.unit_lines(n); k = self.span_line(n)
        far = next(i for i, l in enumerate(lines[1:], 2) if abs(i - k) > 4 and len(l.split()) >= 10)
        w = lines[far - 1].split()
        self.write_compact(n, words=" ".join(w[:4]) + " ... " + " ".join(w[-4:]))
        self.assertEqual(self.gate().returncode, 1)

    def test_compact_item_needs_its_pointer(self):
        for n in self.units: self.write_compact(n)
        self.write_compact(self.units[0], pointer=False)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("without its [u", self.report())

    def test_older_quotation_form_still_checked(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]; k = self.span_line(n); w = self.unit_lines(n)[k - 1].split()
        self.write_compact(n, quotes_line=f'- [u {n}:{k}] Counsel | "{" ".join(w[:6])}" | use: notable quote')
        self.assertEqual(self.gate().returncode, 0)
        self.write_compact(n, quotes_line=f'- [u {n}:{k}] Counsel | "{" ".join(w[:5])} never said" | use: notable quote')
        self.assertEqual(self.gate().returncode, 1)

    def test_over_the_allowance_fails_without_an_exception(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]
        self.write_compact(n, padding=900)
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)   # a failure of gate 1, not a warning, without --strict
        self.assertIn("over the item allowance", self.report())
        r = self.gate_args("--size")
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"{n}: findings", r.stdout); self.assertIn("(no exception line)", r.stdout)

    def test_within_the_allowance_passes(self):
        for n in self.units: self.write_compact(n)
        r = self.gate_args("--size")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("allowance", r.stdout); self.assertIn("within", r.stdout); self.assertIn("items: ", r.stdout)

    def test_a_free_text_exception_is_invalid(self):
        for n in self.units: self.write_compact(n)
        self.write_compact(self.units[0], padding=900, head_extra=["size: over budget: a dense question and answer"])
        self.assertEqual(self.gate().returncode, 1)
        r = self.gate_args("--size")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("exception INVALID", r.stdout)

    def test_budget_option_keeps_the_ratio_for_archived_findings(self):
        for n in self.units: self.write_compact(n)
        n = self.units[0]
        self.write_compact(n, padding=900)
        r = self.gate_args("--budget", "0.25")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)          # a warning in the ratio mode
        self.assertIn("over the budget of 0.25", self.report())
        self.assertEqual(self.gate_args("--budget", "0.25", "--strict").returncode, 1)
        self.assertEqual(self.gate_args("--size", "--budget", "50").returncode, 0)
        self.write_compact(n, padding=900, head_extra=["size: over budget: a dense question and answer"])
        self.assertEqual(self.gate_args("--budget", "0.25", "--strict").returncode, 0)   # any exception line honoured, as before


class Gate1ItemAllowance(unittest.TestCase):
    """The allowance's arithmetic and the exception line's checkable form, on one unit."""
    @classmethod
    def setUpClass(cls):
        Gate1CompactForm.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    unit_lines = Gate1CarriedHeading.unit_lines
    span_line = Gate1CompactForm.span_line
    report = Gate1CompactForm.report
    gate_args = Gate1CompactForm.gate_args

    def write(self, n, head=(), doc_words=120, docs=3, claim_pad=0):
        """one claim, one quotation, `docs` Documents items of about doc_words words each (report numbers that cannot be cut)"""
        lines = self.unit_lines(n); k = self.span_line(n); w = lines[k - 1].split()
        body = [f"unit: {lines[0]}", "status: complete", "reader: test", *head, ""]
        for s in self.G.REQUIRED_SECTIONS:
            body += [f"## {s}", ""]
            if s == "Claims": body.append(f"- [u {n}:{k}] Counsel | other | read | n/a | claim: {' '.join(w[:8])} | chain: 0 | loc: para. 1" + " filler" * claim_pad)
            elif s == "Quotations": body.append(f"- [u {n}:{k}] Counsel | words: {' '.join(w[:4])} ... {' '.join(w[-4:])} | use: notable quote")
            elif s == "Documents and works cited":
                for d in range(docs): body.append(f"- [u {n}:{k}] Report {d} | the authority | report | 1999 | for: the figures | id: " + " ".join(f"RN-{d}-{j:03d}" for j in range(doc_words - 12)))
            else: body.append("- none")
            body.append("")
        os.makedirs(os.path.join(self.wip, "findings"), exist_ok=True)
        with open(os.path.join(self.wip, "findings", f"{n}.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))

    def size(self, n, *extra):
        return self.gate_args("--size", "--units", f"{n}-{n}", *extra)

    def test_allowance_arithmetic(self):
        n = self.units[0]
        self.write(n, docs=2, doc_words=20)
        fd = self.G.parse_findings(os.path.join(self.wip, "findings", f"{n}.md"))
        allowance, items = self.G.allowance_of(fd)
        self.assertEqual(items["Claims"], 1); self.assertEqual(items["Quotations"], 1); self.assertEqual(items["Documents and works cited"], 2)
        self.assertEqual(items["Names"], 0)   # `- none` is not an item
        self.assertEqual(allowance, 200 + 35 + 20 + 2 * 25)
        q = self.G.REQUIRED_SECTIONS[4]
        self.assertEqual(self.G.rate_of(q), 30); self.assertEqual(self.G.rate_of("Relations"), 25); self.assertEqual(self.G.rate_of("Open threads the unit raises"), 25)

    def test_over_without_exception_fails(self):
        n = self.units[0]
        self.write(n)
        r = self.size(n)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("(no exception line)", r.stdout)

    def test_valid_exception_passes(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: Documents and works cited: 3 items over 25 words: report numbers and URLs"])
        r = self.size(n)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("exception valid", r.stdout)

    def test_a_prefix_naming_one_section_is_the_section(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: Documents: 3 items over 25 words: report numbers"])
        self.assertEqual(self.size(n).returncode, 0)

    def test_exception_naming_no_section_is_invalid(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: report numbers and URLs"])
        r = self.size(n)
        self.assertEqual(r.returncode, 1); self.assertIn("not in the form", r.stdout)

    def test_exception_naming_a_section_not_in_the_file_is_invalid(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: Footnotes: 3 items over 25 words: report numbers"])
        r = self.size(n)
        self.assertEqual(r.returncode, 1); self.assertIn("not an item section", r.stdout)

    def test_exception_naming_the_wrong_section_is_invalid(self):
        # the claim is over its cap by a few words, but the Documents items are what put the file over
        n = self.units[0]
        self.write(n, claim_pad=20, head=["size: over budget: Claims: 1 items over 35 words: the claim's wording is the point"])
        r = self.size(n)
        self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("wrong section", r.stdout)

    def test_too_few_items_over_the_cap_is_invalid(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: Documents and works cited: 5 items over 25 words: report numbers"])
        r = self.size(n)
        self.assertEqual(r.returncode, 1); self.assertIn("not 5", r.stdout)

    def test_a_cap_under_the_rate_is_invalid(self):
        n = self.units[0]
        self.write(n, head=["size: over budget: Documents and works cited: 3 items over 10 words: report numbers"])
        r = self.size(n)
        self.assertEqual(r.returncode, 1); self.assertIn("per-item allowance", r.stdout)

    def test_density_is_never_a_reason(self):
        n = self.units[0]
        for reason in ("dense", "a dense table of report numbers"):
            self.write(n, head=[f"size: over budget: Documents and works cited: 3 items over 25 words: {reason}"])
            r = self.size(n)
            self.assertEqual(r.returncode, 1, reason); self.assertIn("density", r.stdout)

    def test_the_gate_fails_the_unit_and_names_it(self):
        for m in self.units: Gate1CompactForm.write_compact(self, m)
        n = self.units[0]
        self.write(n, head=["size: over budget: dense"])
        r = self.gate_args("--json")
        self.assertEqual(r.returncode, 1)
        import json
        js = json.loads(r.stdout.strip().split("\n")[-1])
        self.assertIn(n, js["failing_units"]); self.assertIn(n, js["size_over"])
        self.write(n, head=["size: over budget: Documents and works cited: 3 items over 25 words: report numbers and URLs"])
        r = self.gate_args("--json")
        self.assertEqual(r.returncode, 0, r.stdout)


class Gate2NothingToRow(unittest.TestCase):
    """Gate 2 accepts the `Units with nothing to row:` line wherever it stands (writer A puts it directly above `## Claims ledger`)."""
    @classmethod
    def setUpClass(cls):
        Gate1CompactForm.setUpClass.__func__(cls)
        assert len(cls.units) >= 3, cls.units

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    unit_lines = Gate1CarriedHeading.unit_lines
    span_line = Gate1CompactForm.span_line

    def note(self, nothing_line, where="above"):
        rows = []
        for i, n in enumerate(self.units[:-1], 1):
            k = self.span_line(n); claim = " ".join(self.unit_lines(n)[k - 1].split()[:10])
            rows.append(f"| {i} | para. 1 | Counsel | other | {claim} | read | n/a | 0 | [u {n}:{k}] |")
        table = ["| # | Time | Speaker | Topic | Claim | Class | Move | Chain | Note |", "|---|---|---|---|---|---|---|---|---|"] + rows
        body = ["# A note", "", "## Summary", "", "The summary.", ""]
        if where == "above": body += [nothing_line, ""]
        body += ["## Claims ledger", "", *table, ""]
        if where == "end": body += ["## Open questions", "", nothing_line, ""]
        p = os.path.join(self.tmp.name, "note.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))
        os.makedirs(os.path.join(self.tmp.name, "out2"), exist_ok=True)
        return run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", os.path.join(self.tmp.name, "out2")])

    def test_line_above_the_claims_ledger(self):
        last = self.units[-1]
        r = self.note(f"Units with nothing to row: {last} (the closing page; no claim)")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_line_elsewhere_and_marked_up(self):
        last = self.units[-1]
        for line in (f"**Units with nothing to row:** {last} (a caption page (photographs only); no claim)", f"- Units with nothing to row: {last} (captions)"):
            r = self.note(line, where="end")
            self.assertEqual(r.returncode, 0, line + "\n" + r.stdout)

    def test_an_undeclared_unit_still_fails(self):
        r = self.note("Units with nothing to row: none")
        self.assertEqual(r.returncode, 1)
        self.assertIn("uncited unit", r.stdout)

class Gate2Parts(unittest.TestCase):
    """The parts mode of gate 2 (the unit writers, 2026-10-24) and --quotes-only, on the compact form's synthetic units."""
    @classmethod
    def setUpClass(cls):
        Gate1CompactForm.setUpClass.__func__(cls)
        assert len(cls.units) >= 3, cls.units

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    unit_lines = Gate1CarriedHeading.unit_lines
    span_line = Gate1CompactForm.span_line

    def claim_row(self, num, n, quote=True, pointer=None, words=None):
        k = self.span_line(n); w = self.unit_lines(n)[k - 1].split()
        claim = words or (f'Counsel says "{" ".join(w[:7])}"' if quote else " ".join(w[:8]))
        ptr = pointer if pointer is not None else f"[u {n}:{k}]"
        return f"| {num} | para. 1 | Counsel | other | {claim} | host | closed-subtle | attribution: none stated; chain: 1: Counsel (unsourced). {ptr} |"

    def audit_row(self, num, n):
        k = self.span_line(n); w = self.unit_lines(n)[k - 1].split()
        return f"| {num} | para. 1 | none; volunteered | (monologue) the point | {' '.join(w[:8])} | closed-subtle | none stated | [u {n}:{k}] |"

    def write_parts(self, rows_by_unit, audit_by_unit=None, folder="parts"):
        d = os.path.join(self.tmp.name, folder)
        if os.path.isdir(d):
            for f in os.listdir(d): os.remove(os.path.join(d, f))
        os.makedirs(d, exist_ok=True)
        for n, rows in rows_by_unit.items():
            with open(os.path.join(d, f"u{n}-ledger.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(rows) + "\n")
        for n, rows in (audit_by_unit or {}).items():
            with open(os.path.join(d, f"u{n}-audit.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(rows) + "\n")
        return d

    def gate(self, d, rng, *extra):
        out = os.path.join(self.tmp.name, "outp"); os.makedirs(out, exist_ok=True)
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note-parts", d, "--wip", self.wip, "--units", rng, "--out", out, "--json", *extra])
        import json
        return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])

    def good(self):
        u = self.units
        return {u[0]: [self.claim_row(1, u[0]), self.claim_row(2, u[0], quote=False)], u[1]: [self.claim_row(3, u[1])]}, {u[0]: [self.audit_row(1, u[0])], u[1]: [self.audit_row(2, u[1])]}

    def test_a_good_range_passes_and_names_its_last_rows(self):
        led, aud = self.good()
        code, j = self.gate(self.write_parts(led, aud), f"{self.units[0]}-{self.units[1]}")
        self.assertEqual(code, 0, j)
        self.assertEqual((j["rows"], j["audit_rows"], j["last_row"], j["last_audit_row"]), ("1-3", "1-2", 3, 2))

    def test_a_quotation_not_in_the_pointers_unit_fails(self):
        led, aud = self.good(); u = self.units
        k0 = self.span_line(u[0]); w0 = " ".join(self.unit_lines(u[0])[k0 - 1].split()[:8])
        led[u[0]].append(self.claim_row("2.1", u[0], words=f'{w0}; and "the quarry foreman never signed any such ledger"'))
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 1); self.assertEqual(j["quote_fails"], 1)
        self.assertIn(f"changed words (not word for word in unit {u[0]})", open(j["report"], encoding="utf-8").read())

    def test_a_quotation_in_another_unit_names_it(self):
        # two units of distinct text (the corpus repeats its sentences, so a small source of its own)
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        src = os.path.join(tmp.name, "two.md"); wip = os.path.join(tmp.name, "task")
        a = "The harbour master logged eleven barges before noon on the first day of the strike. " * 3
        b = "A second clerk counted the grain sacks twice and found the warehouse ledger short by forty. " * 3
        with open(src, "w", encoding="utf-8", newline="\n") as f: f.write(f"# Record\n\n{a}\n\n{b}\n")
        r = run([os.path.join(TOOLS, "chunk_source.py"), src, "--wip", wip, "--words", "40"]); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        units = sorted(f[:-4] for f in os.listdir(os.path.join(wip, "units")) if f.endswith(".txt"))
        lines = {n: open(os.path.join(wip, "units", f"{n}.txt"), encoding="utf-8").read().split("\n") for n in units}
        k = {n: next(i for i, l in enumerate(lines[n][1:], 2) if len(l.split()) >= 8) for n in units}
        first, last = units[0], units[-1]
        self.assertIn("harbour", lines[first][k[first] - 1]); self.assertIn("grain", lines[last][k[last] - 1])
        d = os.path.join(tmp.name, "parts"); os.makedirs(d)
        rows = {first: [f'| 1 | p. 1 | Clerk | other | The harbour master logged eleven barges; "found the warehouse ledger short by forty" | host | closed-subtle | [u {first}:{k[first]}] |'],
                last: [f'| 2 | p. 1 | Clerk | other | A second clerk counted the grain sacks twice | host | closed-subtle | [u {last}:{k[last]}] |']}
        for n, rr in rows.items():
            with open(os.path.join(d, f"u{n}-ledger.md"), "w", encoding="utf-8") as f: f.write("\n".join(rr) + "\n")
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note-parts", d, "--wip", wip, "--units", f"{first}-{last}", "--json",
                 "--nothing-to-row", json.dumps({n: "between" for n in units[1:-1]})])
        self.assertEqual(r.returncode, 1, r.stdout)
        rep = open(json.loads(r.stdout.strip().splitlines()[-1])["report"], encoding="utf-8").read()
        self.assertIn(f"it is in unit {last}: fix the pointer", rep)

    def test_a_row_without_a_pointer_fails(self):
        led, aud = self.good(); u = self.units
        led[u[0]][1] = self.claim_row(2, u[0], quote=False, pointer="")
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 1); self.assertIn(u[0], j["failing_units"])
        self.assertIn("carries no pointer", open(j["report"], encoding="utf-8").read())

    def test_a_pointer_off_the_words_fails(self):
        led, aud = self.good(); u = self.units
        led[u[0]][1] = self.claim_row(2, u[0], quote=False, words="Nothing of this kind stands anywhere in the record wholly invented")
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 1); self.assertEqual(j["line_fails"], 1)

    def test_a_gap_or_a_wrong_start_fails(self):
        led, aud = self.good(); u = self.units
        led[u[1]] = [self.claim_row(5, u[1])]
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 1); self.assertIn("rows run on without gaps", open(j["report"], encoding="utf-8").read())
        led, aud = self.good()
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}", "--start-row", "40")
        self.assertEqual(code, 1); self.assertIn("this writer starts at 40", open(j["report"], encoding="utf-8").read())

    def test_a_decimal_row_stands_between_its_neighbours(self):
        led, aud = self.good(); u = self.units
        led[u[0]].insert(1, self.claim_row("1.1", u[0], quote=False))
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 0, j)

    def test_an_uncited_unit_fails_unless_in_nothing_to_row(self):
        led, aud = self.good(); u = self.units
        d = self.write_parts(led, aud)
        code, j = self.gate(d, f"{u[0]}-{u[2]}")
        self.assertEqual(code, 1); self.assertEqual(j["uncited_units"], [u[2]])
        code, j = self.gate(d, f"{u[0]}-{u[2]}", "--nothing-to-row", '[{"unit": "%s", "reason": "a caption page"}]' % u[2])
        self.assertEqual(code, 0, j)
        code, j = self.gate(d, f"{u[0]}-{u[2]}", "--nothing-to-row", '{"%s": "a caption page"}' % int(u[2]))
        self.assertEqual(code, 0, j)

    def test_a_heading_or_header_in_a_part_fails(self):
        led, aud = self.good(); u = self.units
        led[u[0]] = ["## Claims ledger", "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|"] + led[u[0]]
        code, j = self.gate(self.write_parts(led, aud), f"{u[0]}-{u[1]}")
        self.assertEqual(code, 1); self.assertEqual(j["fails"], 3)

    def test_the_second_writer_starts_where_the_first_ended(self):
        u = self.units
        d = self.write_parts({u[0]: [self.claim_row(1, u[0])], u[1]: [self.claim_row(2, u[1])], u[2]: [self.claim_row(3, u[2])]})
        code, j = self.gate(d, f"{u[2]}-{u[2]}", "--start-row", "3")
        self.assertEqual(code, 0, j); self.assertEqual(j["last_row"], 3)

    def test_quotes_only_checks_quotations_alone(self):
        u = self.units
        body = ["# A note", "", "## Summary", "", "The summary.", "", "## Claims ledger", "",
                "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|",
                self.claim_row(1, u[0], pointer=""), ""]
        p = os.path.join(self.tmp.name, "legacy.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))
        out = os.path.join(self.tmp.name, "outq"); os.makedirs(out, exist_ok=True)
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", out])
        self.assertEqual(r.returncode, 1)                     # the full gate: uncited units
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", out, "--quotes-only"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("not checked (--quotes-only)", r.stdout)
        with open(p, "a", encoding="utf-8") as f: f.write('\n## Key claims and ideas\n\nHe said "these words appear in no unit of the record at all".\n')
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", out, "--quotes-only"])
        self.assertEqual(r.returncode, 1); self.assertIn("1 changed words", r.stdout)

CAPTION = ["**[00:00:01]** well the survey team came out in august and we measured the north wall twice before the rain",
           "",
           "**[00:01:05]** and i told the foreman it was cracked he said no its fine and we poured anyway in the dark",
           "",
           "The second report was filed on 3 May. It named the foreman, Mr. Hale, and gave the cost as $1,500 for the repair."]


def caption_wip(root):
    """a task folder with one hand-made unit: two unpunctuated caption lines and one punctuated line"""
    wip = os.path.join(root, "captask"); os.makedirs(os.path.join(wip, "units"), exist_ok=True)
    header = "[unit 001/001] source: sources/x/transcript.md | span: 00:00:01-00:02:00, lines 1-5 | words: 70"
    with open(os.path.join(wip, "units", "001.txt"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join([header] + CAPTION) + "\n")
    with open(os.path.join(wip, "units", "manifest.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Units\n\n| unit | source | span | words | status | notes |\n|---|---|---|---|---|---|\n| 001 | transcript.md | 00:00:01-00:02:00, lines 1-5 | 70 |  |  |\n")
    return wip


class Gate2CaptionRule(unittest.TestCase):
    """The caption rule: punctuation only is forgiven and reported apart; a changed, added or dropped word fails."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.wip = caption_wip(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def note(self, *quotes):
        rows = [f'| {i} | 00:00:01 | Team | other | He says "{q}" | firsthand | open | the act: measured. [u 001:2] |' for i, q in enumerate(quotes, 1)]
        body = ["# A note", "", "## Claims ledger", "", "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|"] + rows + [""]
        p = os.path.join(self.tmp.name, "note.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(body))
        out = os.path.join(self.tmp.name, "out"); os.makedirs(out, exist_ok=True)
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", out, "--quotes-only", "--json"])
        j = json.loads(r.stdout.strip().splitlines()[-1])
        with open(j["report"], encoding="utf-8") as f: rep = f.read()
        return r.returncode, j, rep

    def test_exact_is_exact(self):
        code, j, _ = self.note("the survey team came out in august")
        self.assertEqual((code, j["quote_exact"], j["quote_punct"], j["quote_fails"]), (0, 1, 0, 0))

    def test_added_punctuation_and_capitals_are_forgiven_and_reported_apart(self):
        code, j, rep = self.note("Well, the survey team came out in August, and we measured the north wall twice",
                                 "He said, \u201cNo, it\u2019s fine,\u201d and we poured anyway")
        self.assertEqual(code, 0, rep)
        self.assertEqual((j["quote_exact"], j["quote_punct"], j["quote_fails"]), (0, 2, 0))
        self.assertIn("## Punctuation only", rep); self.assertNotIn("## Failures", rep)
        self.assertIn("2 punctuation only (forgiven)", j["summary"])

    def test_across_a_caption_line_and_its_timestamp(self):
        code, j, rep = self.note("twice before the rain. And I told the foreman it was cracked")
        self.assertEqual((code, j["quote_punct"]), (0, 1), rep)

    def test_an_ellipsis_with_punctuation(self):
        code, j, rep = self.note("Well, the survey team came out ... we measured the north wall")
        self.assertEqual((code, j["quote_punct"]), (0, 1), rep)

    def test_a_changed_word_fails_and_names_the_difference(self):
        code, j, rep = self.note("the survey team came out in July and we measured")
        self.assertEqual((code, j["quote_fails"]), (1, 1))
        self.assertIn("changed words", rep); self.assertIn('the source has "august" where the quotation has "july"', rep)

    def test_a_dropped_word_fails(self):
        code, j, rep = self.note("Well, the survey team came in August and we measured")
        self.assertEqual((code, j["quote_fails"], j["quote_punct"]), (1, 1, 0))
        self.assertIn('the quotation drops "out"', rep)

    def test_an_added_word_fails(self):
        code, j, rep = self.note("the survey team came out early in august and we measured")
        self.assertEqual((code, j["quote_fails"]), (1, 1))
        self.assertIn('the quotation adds "early"', rep)

    def test_a_number_with_its_comma_and_a_punctuated_line(self):
        code, j, rep = self.note("It named the foreman, Mr. Hale, and gave the cost as $1500")
        self.assertEqual((code, j["quote_fails"], j["quote_punct"]), (0, 0, 1), rep)

    def test_the_full_gate_classes_the_same(self):
        p = os.path.join(self.tmp.name, "note.md"); self.note("Well, the survey team came out in August")
        out = os.path.join(self.tmp.name, "out")
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note", p, "--wip", self.wip, "--out", out, "--json"])
        j = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual((r.returncode, j["quote_punct"], j["quote_fails"]), (0, 1, 0), j)

    def test_the_parts_mode_classes_the_same(self):
        d = os.path.join(self.tmp.name, "parts"); os.makedirs(d, exist_ok=True)
        rows = ['| 1 | 00:00:01 | Team | other | He says "Well, the survey team came out in August" | firsthand | open | the act: measured. [u 001:2] |',
                '| 2 | 00:01:05 | Team | other | He says "and I told the foreman it was broken" | firsthand | open | told. [u 001:4] |']
        with open(os.path.join(d, "u001-ledger.md"), "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(rows) + "\n")
        out = os.path.join(self.tmp.name, "outparts"); os.makedirs(out, exist_ok=True)
        r = run([os.path.join(TOOLS, "intake_gate.py"), "--note-parts", d, "--wip", self.wip, "--units", "001-001", "--out", out, "--json"])
        j = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual((r.returncode, j["quote_punct"], j["quote_fails"]), (1, 1, 1), j)
        with open(j["report"], encoding="utf-8") as f: rep = f.read()
        self.assertIn('the source has "cracked" where the quotation has "broken"', rep); self.assertIn("## Punctuation only", rep)


if __name__ == "__main__":
    unittest.main(verbosity=1)
