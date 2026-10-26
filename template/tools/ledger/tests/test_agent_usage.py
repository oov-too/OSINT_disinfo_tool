"""tools/agent_usage.py --task <key> --records on a synthetic run folder: only the task's agents (the key one of a label's
colon-separated parts) are summed, by records and per phase, in one JSON line (the figure staged-intake.js's maxRecords is
checked against; 2026-10-23, wip/split-write/).
  python3 tools/ledger/tests/test_agent_usage.py"""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))


def agent(run, aid, label, phase, reads):
    """an agent transcript whose assistant records carry the given cache-read figures (two records may share one call id)"""
    with open(os.path.join(run, f"agent-{aid}.meta.json"), "w", encoding="utf-8") as f:
        json.dump({"description": label, "workflowPhase": phase, "model": "opus"}, f)
    with open(os.path.join(run, f"agent-{aid}.jsonl"), "w", encoding="utf-8") as f:
        for k, (mid, r) in enumerate(reads):
            f.write(json.dumps({"type": "assistant", "timestamp": f"2026-10-23T10:00:{k:02d}Z",
                                "message": {"id": mid, "model": "opus", "usage": {"cache_read_input_tokens": r, "input_tokens": 1}, "content": []}}) + "\n")


class TaskRecords(unittest.TestCase):
    def test_task_filter_and_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = os.path.join(tmp, "wf_test-1")
            os.makedirs(run)
            agent(run, "a1", "read:t-one:001-002", "Read", [("m1", 100), ("m1", 100), ("m2", 300)])
            agent(run, "a2", "resume1:write-a:t-one", "Resume", [("m3", 1000)])
            agent(run, "a3", "gate2:t-one:write-a:0", "Gate 2", [("m4", 5)])
            agent(run, "a4", "write-a:t-one-b", "Write A", [("m5", 7000)])      # another task whose key only starts the same
            r = subprocess.run([sys.executable, os.path.join(TOOLS, "agent_usage.py"), run, "--task", "t-one", "--records"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            js = json.loads(r.stdout.strip().split("\n")[-1])
            self.assertEqual(js["agents"], 3)
            self.assertEqual(js["records"], 100 + 100 + 300 + 1000 + 5)   # by records: streamed blocks of one call counted again
            self.assertEqual(js["by_phase"], {"Read": 500, "Resume": 1000, "Gate 2": 5})
            self.assertTrue(js["ok"]); self.assertIn("t-one", js["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
