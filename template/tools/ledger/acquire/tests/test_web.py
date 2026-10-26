#!/usr/bin/env python3
"""Tests of the web adapter on local files (file:// URLs, no network): a page, an RSS and an Atom feed, a paged thread, bytes from
another route, a re-capture, and the completion decision generalised from tools/reddit_rss_patch.py, tried on synthetic held pairs."""
import glob, os, pathlib, re, unittest
import _common as C
from ledger.acquire import base as B, web as W


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


PAGE = """<!doctype html><html><head><title>Example Page</title>
<meta property="og:site_name" content="Example Site"><meta property="article:published_time" content="2026-03-04T10:00:00Z">
<meta name="author" content="A. Writer"><style>body{color:red}</style><script>var x = 1;</script></head>
<body><h1>Heading</h1><p>First paragraph with <a href="https://example.org/x">a link</a> and <strong>bold</strong> text.</p>
<ul><li>one</li><li>two</li></ul><blockquote>quoted</blockquote></body></html>"""
RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Example Feed</title>
<item><title>Post one</title><link>https://example.org/1</link><author>a@example.org (A)</author><pubDate>Tue, 03 Mar 2026 10:00:00 GMT</pubDate>
<description>&lt;p&gt;Body of post one.&lt;/p&gt;</description></item>
<item><title>Post two</title><link>https://example.org/2</link><pubDate>Wed, 04 Mar 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Body of post two, cut mid</description></item>
</channel></rss>"""
ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Example</title>
<entry><title>Entry A</title><link href="https://example.org/a"/><author><name>B. Author</name></author><published>2026-02-01T00:00:00Z</published>
<content type="html">&lt;div class="md"&gt;&lt;p&gt;Reddit-style body.&lt;/p&gt;&lt;/div&gt; &lt;!-- SC_ON --&gt;</content></entry></feed>"""


class Web(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.site = os.path.join(self.root, "site"); os.makedirs(self.site)
        self.w = W.WebAdapter(root=self.root, gap=0, sleep=lambda s: None, log=lambda m: None)

    def put(self, name, text):
        p = os.path.join(self.site, name)
        with open(p, "w", encoding="utf-8", newline="") as f: f.write(text)
        return pathlib.Path(p).as_uri()

    def test_page(self):
        url = self.put("page.html", PAGE.replace("\n", "\r\n"))
        row = self.w.page(url)[0]; f = os.path.join(self.root, row["hold"])
        self.assertEqual(row["hold"], "sources/web/2026-03-04-example-page")
        self.assertEqual(B.read_bytes(os.path.join(f, "page.html")), PAGE.replace("\n", "\r\n").encode("utf-8"))   # byte-for-byte, CRLF kept
        t = B.read_raw(os.path.join(f, "text.md"))
        self.assertIn("# Heading", t); self.assertIn("[a link](https://example.org/x)", t); self.assertIn("**bold**", t)
        self.assertIn("- one", t); self.assertNotIn("color:red", t); self.assertNotIn("var x", t); self.assertNotIn("\r", t)
        r = B.load_hold(f)["record"]
        self.assertEqual((r["title"], r["date"], r["venue"], r["speaker_or_author"]), ("Example Page", "2026-03-04", "Example Site", ["A. Writer"]))
        self.assertEqual(B.verify_hold(f), [])

    def test_rss_and_atom(self):
        row = self.w.feed(self.put("feed.xml", RSS))[0]; f = os.path.join(self.root, row["hold"])
        md = B.load_hold(f)["record"]["metadata"]
        self.assertEqual((md["entries"], md["truncation_suspects"]), (2, 1))
        e = B.read_raw(os.path.join(f, "entries.md"))
        self.assertIn("## 1. Post one", e); self.assertIn("Body of post one.", e); self.assertIn("- Date: 2026-03-03", e)
        row = self.w.feed(self.put("atom.xml", ATOM))[0]; f = os.path.join(self.root, row["hold"])
        self.assertIn("Reddit-style body.", B.read_raw(os.path.join(f, "entries.md")))
        self.assertEqual(B.load_hold(f)["record"]["speaker_or_author"], ["B. Author"])

    def test_thread_pages_until_missing(self):
        for i in (1, 2, 3): self.put(f"t-{i}.html", f"<html><head><title>Thread</title></head><body><p>post on page {i}</p></body></html>")
        tpl = pathlib.Path(os.path.join(self.site, "t-{page}.html")).as_uri().replace("%7B", "{").replace("%7D", "}")
        row = self.w.thread(tpl)[0]; f = os.path.join(self.root, row["hold"])
        self.assertEqual(sorted(n for n in os.listdir(f) if n.startswith("page-")), ["page-001.html", "page-002.html", "page-003.html"])
        t = B.read_raw(os.path.join(f, "text.md"))
        self.assertTrue(t.startswith("--- page 1 ---\npost on page 1\n\n--- page 2 ---\n"))
        self.assertIn("request failed", B.load_hold(f)["record"]["metadata"]["stopped"])

    def test_thread_follows_next_links_and_stops_on_repeat(self):
        u2 = self.put("n2.html", "<html><head><link rel='next' href='n1.html'></head><body><p>two</p></body></html>")
        u1 = self.put("n1.html", "<html><head><title>N</title><link rel='next' href='n2.html'></head><body><p>one</p></body></html>")
        row = self.w.thread(u1)[0]
        self.assertEqual(B.load_hold(os.path.join(self.root, row["hold"]))["record"]["metadata"]["pages"], 2)

    def test_hold_bytes_from_another_route(self):
        data = b"%PDF-1.7\n% a stand-in body\n"
        row = self.w.hold_bytes("https://example.gov/doc.pdf", data, tool="the browser pane (saved by hand)")
        f = os.path.join(self.root, row["hold"])
        self.assertEqual(B.read_bytes(os.path.join(f, "page.pdf")), data)
        self.assertIn("browser pane", B.load_hold(f)["record"]["capture_tool"])

    def test_recapture_keeps_both_and_records_the_decision(self):
        first = "<html><head><title>Long post</title></head><body><p>" + " ".join(f"word{i}" for i in range(400)) + " and then it stops mid</p></body></html>"
        url = self.put("post.html", first)
        row = self.w.page(url)[0]; folder = row["hold"]
        self.put("post.html", first.replace(" and then it stops mid", " and then it goes on " + " ".join(f"more{i}" for i in range(300)) + "."))
        r2 = self.w.recapture(folder); f = os.path.join(self.root, folder)
        self.assertEqual(r2["status"], "changed")
        self.assertEqual(B.read_raw(os.path.join(f, "page.html")), first)                              # the first capture stays
        self.assertEqual(len([n for n in os.listdir(f) if re.fullmatch(r"page\.\d{8}T\d{6}Z\.html", n)]), 1)
        c = B.load_hold(f)["record"]["metadata"]["completion"]
        self.assertEqual(c["decision"], "completes"); self.assertGreaterEqual(c["containment"], 0.98)
        self.assertEqual(B.verify_hold(f), [])


class Completion(unittest.TestCase):
    def test_decisions(self):
        base = " ".join(f"w{i}" for i in range(300))
        self.assertEqual(W.compare(base, base)["decision"], "identical")
        self.assertEqual(W.compare(base, base[:100])["decision"], "not-longer")
        self.assertEqual(W.compare(base + " end", base + " end and more " + " ".join(f"x{i}" for i in range(200)))["decision"], "completes")
        self.assertEqual(W.compare(base, " ".join(f"z{i}" for i in range(900)))["decision"], "different")
        self.assertTrue(W.is_truncated("it ends mid")); self.assertFalse(W.is_truncated("It ends."))

    def test_on_a_held_reddit_pair(self):
        """The first-posted state of each held post against the completed copy beside it (synthetic pairs of the casebook corpus):
        the generalised decision is the tool's. tools/reddit_rss_patch.py patched a copy on its own only at 0.85 containment or
        above (here: completes or revises); the copies it patched only with --force-ids after a reading (their header says
        "verified by the orchestrator by reading") come out 'different', left for a reading, as the tool left them."""
        import casebook_corpus as CC
        sibs = sorted(glob.glob(os.path.join(CC.build(os.path.join(C.temp_root(self), "corpus"))["blog"], "*.first-posted-state.md")))
        if not sibs: self.skipTest("no held Reddit pair")
        RP = W.RP; seen = {"auto": 0, "forced": 0}
        for s in sibs:
            full = s.replace(".first-posted-state.md", ".md")
            if not os.path.isfile(full): continue
            hdr, later = RP.split(full); _, held = RP.split(s)
            c = W.compare(held, later)
            if "verified by the orchestrator by reading" in hdr:
                self.assertEqual(c["decision"], "different", (os.path.basename(s), c)); seen["forced"] += 1
            else:
                self.assertIn(c["decision"], ("completes", "revises"), (os.path.basename(s), c)); seen["auto"] += 1
        self.assertGreater(seen["auto"], 0)
        print(f"\n    held Reddit pairs: {seen['auto']} completed or revised as the tool decided, {seen['forced']} left for a reading as the tool left them")


if __name__ == "__main__":
    unittest.main(verbosity=2)
