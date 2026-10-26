"""The single-agent workflow script (tools/workflows/guarded-intake.js) in a dry run outside the Workflow runtime: the blocked-output
guard and the quotation gate after the reply (gate 2 --quotes-only by a probe; the agent resumed with the report up to
maxGateResumes; 2026-10-25, wip/quote-tool-adoption/). The cases are in tools/workflows/tests/test_guarded_intake.mjs, run with node;
the harness is tools/workflows/tests/dryrun.mjs. Skipped when node is not installed. The single-agent form is the legacy project's
and is not shipped in the bundle.
  python3 tools/ledger/tests/test_guarded_intake_workflow.py"""
import os, shutil, subprocess, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))


class GuardedIntakeDryRun(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_dry_runs_pass(self):
        r = subprocess.run(["node", os.path.join(TOOLS, "workflows", "tests", "test_guarded_intake.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(\d+) of \1 passed")


if __name__ == "__main__":
    unittest.main(verbosity=1)
