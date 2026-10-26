"""The staged-intake workflow script (tools/workflows/staged-intake.js) in a dry run outside the Workflow runtime: the split write
(writer A, the ledger; writer B, the sections; splitWrite false keeps one writer), the gate-2 fix loop per writer, the resume text
per writer's parts, and the per-task maxRecords cap between phases and inside the guard (2026-10-23, wip/split-write/). The cases
are in tools/workflows/tests/test_staged_intake.mjs, run with node; the harness is tools/workflows/tests/dryrun.mjs. Skipped
when node is not installed.
  python3 tools/ledger/tests/test_staged_intake_workflow.py"""
import os, shutil, subprocess, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))


class StagedIntakeDryRun(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_dry_runs_pass(self):
        r = subprocess.run(["node", os.path.join(TOOLS, "workflows", "tests", "test_staged_intake.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(\d+) of \1 passed")


if __name__ == "__main__":
    unittest.main(verbosity=1)
