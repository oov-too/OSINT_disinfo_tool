#!/usr/bin/env python3
"""Tests of the web adapter's fetching policy (the owner's, 2026-10-22; handoff 8 and finding 3 of wip/platform-phase6b): the honest
user agent, robots.txt for the ledger's token and Claude-User (RFC 9309: groups, longest match, Allow on a tie, wildcards), the
refusal with its deciding line, Crawl-delay, the robots.txt fetch statuses, and the retry rules (finding 4). file:// sites and
mocked requests only: no network."""
import io, json, os, pathlib, ssl, unittest, urllib.error
from unittest import mock
import _common as C
from ledger.acquire import base as B, web as W, robots as R


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


ROBOTS = """# the site's rules
User-agent: *
Disallow: /private/
Allow: /private/open.html

User-agent: Claude-User
Disallow: /news/
Crawl-delay: 30

User-agent: LedgerAcquire
User-agent: OtherBot
Disallow: /drafts/*.html$
"""


class Matcher(unittest.TestCase):
    def setUp(self): self.r = R.Robots(ROBOTS, source="robots.txt")

    def test_groups_longest_match_and_ties(self):
        ok, why = self.r.check("https://s.example/private/x.html", "SomeBot")
        self.assertFalse(ok); self.assertIn("line 3 `Disallow: /private/`", why)
        ok, why = self.r.check("https://s.example/private/open.html", "SomeBot")
        self.assertTrue(ok); self.assertIn("line 4 `Allow: /private/open.html`", why)      # the longer rule wins
        tie = R.Robots("User-agent: *\nDisallow: /a\nAllow: /a\n")
        self.assertTrue(tie.check("https://s.example/a", "X")[0])                         # an Allow wins a tie
        # a named group replaces the * group for its agent: LedgerAcquire is not bound by /private/
        self.assertTrue(self.r.check("https://s.example/private/x.html", "LedgerAcquire")[0])
        self.assertTrue(self.r.check("https://s.example/private/x.html", "ledgeracquire")[0])   # case-insensitive product token

    def test_wildcards_and_end_anchor(self):
        self.assertFalse(self.r.check("https://s.example/drafts/a/b.html", "LedgerAcquire")[0])
        self.assertTrue(self.r.check("https://s.example/drafts/a/b.html?x=1", "LedgerAcquire")[0])     # $ ends the path
        self.assertTrue(self.r.check("https://s.example/robots.txt", "Claude-User")[0])
        self.assertTrue(R.Robots("User-agent: *\nDisallow:\n").check("https://s.example/any", "X")[0])  # an empty Disallow allows

    def test_verdict_for_both_agents_and_crawl_delay(self):
        v = self.r.verdict("https://s.example/news/today", ("LedgerAcquire", "Claude-User"))
        self.assertFalse(v["allowed"]); self.assertEqual(v["refused_by"], "Claude-User")
        self.assertIn("line 7 `Disallow: /news/`", v["decisions"]["Claude-User"])             # line 1 is the comment
        self.assertEqual(self.r.crawl_delay(("LedgerAcquire", "Claude-User")), (30.0, "line 8 `Crawl-delay: 30`"))
        self.assertIn("disallowed for Claude-User", R.summary(v))

    def test_unreachable_and_absent(self):
        self.assertFalse(R.Robots(status="disallow-all", note="HTTP 503").check("https://s.example/", "X")[0])
        self.assertTrue(R.Robots(status="allow-all", note="HTTP 404").check("https://s.example/", "X")[0])


class Policy(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.site = os.path.join(self.root, "site"); os.makedirs(self.site)
        self.sleeps = []
        self.w = W.WebAdapter(root=self.root, gap=0, sleep=self.sleeps.append, log=lambda m: None)

    def put(self, name, text):
        p = os.path.join(self.site, name)
        with open(p, "w", encoding="utf-8", newline="") as f: f.write(text)
        return pathlib.Path(p).as_uri()

    def test_user_agent_is_honest(self):
        ua = self.w.ua
        self.assertTrue(ua.startswith("LedgerAcquire/")); self.assertIn("Claude-User", ua); self.assertNotIn("Mozilla", ua); self.assertNotIn("Chrome", ua)
        with open(os.path.join(self.root, "ledger.toml"), "a", encoding="utf-8") as f: f.write('title = "A Test Ledger"\n[acquire]\ncontact = "ledger@example.org"\n')
        ua2 = W.WebAdapter(root=self.root, log=lambda m: None).ua
        self.assertIn("ledger@example.org", ua2); self.assertIn("A Test Ledger", ua2)
        with self.assertRaises(TypeError): W.WebAdapter(root=self.root, user_agent="Mozilla/5.0")   # no browser-agent override exists

    def test_disallowed_url_fails_with_the_robots_line_and_nothing_is_held(self):
        self.put("robots.txt", "User-agent: Claude-User\nDisallow: /\n")
        url = self.put("page.html", "<html><head><title>T</title></head><body><p>text</p></body></html>")
        row = self.w.page(url)[0]
        self.assertEqual(row["status"], "failed"); self.assertIsNone(row["hold"])
        self.assertIn("refused by robots.txt", row["note"]); self.assertIn("line 2 `Disallow: /`", row["robots"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "sources")))
        log = [json.loads(l) for l in B.read_raw(os.path.join(self.w.state_dir, "robots-refusals.jsonl")).splitlines()]
        self.assertEqual(log[0]["url"], url); self.assertEqual(log[0]["verdict"]["refused_by"], "Claude-User")
        self.assertEqual(self.w.thread(url)[0]["status"], "failed")

    def test_allowed_page_records_the_verdict_and_crawl_delay_raises_the_gap(self):
        self.put("robots.txt", "User-agent: *\nDisallow: /nothing/\nCrawl-delay: 12\n")
        url = self.put("page.html", "<html><head><title>T</title><meta property='article:published_time' content='2026-01-02'></head><body><p>text</p></body></html>")
        row = self.w.page(url)[0]
        md = B.load_hold(os.path.join(self.root, row["hold"]))["record"]["metadata"]
        self.assertTrue(md["robots"].startswith("allowed by ")); self.assertIn("no rule matches", md["robots"])
        self.assertEqual(self.w.gate(url).gap, 12.0)

    def test_no_robots_file_allows(self):
        url = self.put("page.html", "<html><body><p>hello</p></body></html>")
        v = self.w.check(url)
        self.assertTrue(v["allowed"]); self.assertIn("no robots.txt", R.summary(v))

    # ---------------------------------------------------------------------------------------------------- robots.txt fetch statuses
    def http_error(self, code, body=b"", headers=None):
        return urllib.error.HTTPError("https://s.example/x", code, "err", headers or {}, io.BytesIO(body))

    def test_robots_fetch_statuses(self):
        with mock.patch.object(self.w, "_request", side_effect=self.http_error(404)):
            self.assertTrue(self.w.robots_for("https://a.example/x").check("https://a.example/x", "X")[0])
        with mock.patch.object(self.w, "_request", side_effect=self.http_error(503)):
            self.assertFalse(self.w.robots_for("https://b.example/x").check("https://b.example/x", "X")[0])
        with mock.patch.object(self.w, "_request", side_effect=urllib.error.URLError(OSError("unreachable"))):
            v = self.w.robots_for("https://c.example/x").verdict("https://c.example/x", self.w.robot_tokens)
            self.assertFalse(v["allowed"]); self.assertIn("unreachable", R.summary(v))

    # ---------------------------------------------------------------------------------------------------- retries (finding 4)
    def run_get(self, effects):
        resp = mock.Mock(); resp.headers = {"Content-Type": "text/html; charset=utf-8"}; resp.geturl.return_value = "https://d.example/x"
        seq = [e if isinstance(e, Exception) else (e, 200, resp) for e in effects]
        with mock.patch.object(self.w, "check", return_value=dict(allowed=True, refused_by=None, decisions={}, source="test")), \
                mock.patch.object(self.w, "_request", side_effect=seq):
            return self.w.get_full("https://d.example/x")

    def test_tls_failure_is_not_retried(self):
        with self.assertRaises(W.FetchFailure) as cm:
            self.run_get([urllib.error.URLError(ssl.SSLError(1, "handshake failure"))])
        self.assertIn("TLS failure, not retried", str(cm.exception)); self.assertEqual(self.sleeps, [])

    def test_protection_page_is_not_retried(self):
        with self.assertRaises(W.FetchFailure) as cm:
            self.run_get([self.http_error(503, b"<html><title>Just a moment...</title> cf-challenge </html>")])
        self.assertIn("protection page", str(cm.exception)); self.assertEqual(self.sleeps, [])

    def test_retry_after_is_honoured_once(self):
        out = self.run_get([self.http_error(503, b"busy", {"Retry-After": "7"}), b"<html>ok</html>"])
        self.assertEqual(out["data"], b"<html>ok</html>"); self.assertEqual(self.sleeps, [7.0]); self.assertEqual(out["charset"], "utf-8")
        with self.assertRaises(W.FetchFailure):
            self.run_get([self.http_error(429, b"slow", {"Retry-After": "2"}), self.http_error(429, b"slow", {"Retry-After": "2"})])

    def test_server_errors_retried_twice(self):
        self.sleeps.clear()
        out = self.run_get([self.http_error(500), self.http_error(502), b"<html>ok</html>"])
        self.assertEqual(self.sleeps, [20, 40]); self.assertEqual(out["status"], 200)
        with self.assertRaises(W.FetchFailure):
            self.run_get([self.http_error(500)] * 3)
        with self.assertRaises(W.FetchFailure) as cm: self.run_get([self.http_error(404)])
        self.assertIn("HTTP 404", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
