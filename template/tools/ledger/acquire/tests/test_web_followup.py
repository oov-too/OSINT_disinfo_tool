#!/usr/bin/env python3
"""Tests of the web adapter's follow-up from the pilot (wip/platform-phase6b/adapter-findings.md): the item's date from the page's
own markup, never the fetch date (finding 9); main content (14); the canonical link and the <title> (18); text/plain decoding (8);
thread_capture with metadata (12, handoff 16) and Hacker News's reply chain (13); a published-transcript video item (6). file://
pages only: no network."""
import os, pathlib, unittest
import _common as C
from ledger.acquire import base as B, web as W, published as P


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


def page(head="", body="<p>text</p>", title="A Page"):
    return f"<!doctype html><html><head><title>{title}</title>{head}</head><body>{body}</body></html>"


HN = """<html><head><title>Story title | Hacker News</title></head><body><table>
<tr class="athing submission" id="100"><td><span class="titleline"><a href="https://example.org/story">Story title</a></span></td></tr>
<tr><td class="subtext"><span class="score" id="score_100">42 points</span> by <a href="user?id=alice" class="hnuser">alice</a>
<span class="age" title="2024-01-16T10:00:00 1705399200"><a href="item?id=100">1 day ago</a></span></td></tr>
<tr class="athing comtr" id="101"><td><table><tr><td class="ind" indent="0"></td><td>
<a href="user?id=bob" class="hnuser">bob</a> <span class="age" title="2024-01-16T11:00:00 1705402800">x</span>
<div class="comment"><div class="commtext c00">First comment.</div><div class="reply">reply</div></div></td></tr></table></td></tr>
<tr class="athing comtr" id="102"><td><table><tr><td class="ind" indent="1"></td><td>
<a href="user?id=carol" class="hnuser">carol</a> <span class="age" title="2024-01-16T12:00:00 1705406400">x</span>
<div class="comment"><div class="commtext c00">A reply to bob.</div><div class="reply">reply</div></div></td></tr></table></td></tr>
<tr class="athing comtr" id="103"><td><table><tr><td class="ind" indent="0"></td><td>
<a href="user?id=dave" class="hnuser">dave</a> <span class="age" title="2024-01-17T09:00:00 1705482000">x</span>
<div class="comment"><div class="commtext c00">Second top-level.</div><div class="reply">reply</div></div></td></tr></table></td></tr>
</table></body></html>"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.site = os.path.join(self.root, "site"); os.makedirs(self.site)
        self.w = W.WebAdapter(root=self.root, gap=0, sleep=lambda s: None, log=lambda m: None)

    def put(self, name, data):
        p = os.path.join(self.site, name)
        with open(p, "wb") as f: f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return pathlib.Path(p).as_uri()

    def held(self, row): return B.load_hold(os.path.join(self.root, row["hold"]))


class Dates(Base):
    def test_json_ld_date(self):
        row = self.w.page(self.put("a.html", page('<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"NewsArticle","datePublished":"2009-05-11T09:00:00Z"}]}</script>')))[0]
        r = self.held(row)["record"]
        self.assertEqual((r["date"], r["date_raw"], r["metadata"]["date_basis"]), ("2009-05-11", "2009-05-11T09:00:00Z", "the page's JSON-LD datePublished"))
        self.assertEqual(row["hold"], "sources/web/2009-05-11-a-page")

    def test_visible_dateline(self):
        r = self.held(self.w.page(self.put("b.html", page(body="<p>Terms of reference</p><p>Published 1 June 2021</p>")))[0])["record"]
        self.assertEqual(r["date"], "2021-06-01"); self.assertIn("a visible dateline ('Published 1 June 2021", r["metadata"]["date_basis"])
        self.assertEqual(W.iso_date("Published: 11 May 2009".split(": ")[1]), "2009-05-11"); self.assertEqual(W.iso_date("May 11th, 2009"), "2009-05-11")

    def test_no_date_is_never_the_fetch_date(self):
        row = self.w.page(self.put("c.html", page()))[0]; r = self.held(row)["record"]
        self.assertIsNone(r["date"]); self.assertTrue(r["metadata"]["date_basis"].startswith("none found"))
        self.assertEqual(row["hold"], "sources/web/undated-a-page"); self.assertNotIn(B.utc_now()[:10], row["hold"])

    def test_caller_date(self):
        r = self.held(self.w.page(self.put("d.html", page()), date="2021-06-01", date_basis="the Key Documents page: Published 1 June 2021")[0])["record"]
        self.assertEqual((r["date"], r["metadata"]["date_basis"]), ("2021-06-01", "the Key Documents page: Published 1 June 2021"))


class Content(Base):
    def test_main_content_and_the_full_page(self):
        body = ("<nav><a href='/'>Home</a> <a href='/x'>Menu item</a></nav><article><h1>Headline</h1><p>" + "The article text. " * 30
                + "</p></article><aside><p>Related: another story</p></aside><footer>Cookie notice</footer>")
        row = self.w.page(self.put("e.html", page(body=body)))[0]
        f = os.path.join(self.root, row["hold"]); t = B.read_raw(os.path.join(f, "text.md")); full = B.read_raw(os.path.join(f, "page-full.md"))
        self.assertIn("# Headline", t); self.assertNotIn("Menu item", t); self.assertNotIn("Cookie notice", t)
        self.assertIn("Menu item", full); self.assertIn("Cookie notice", full)
        self.assertEqual(self.held(row)["record"]["metadata"]["text_extent"], "the largest <article> element")
        self.assertEqual(B.verify_hold(f), [])

    def test_canonical_and_title(self):
        head = "<meta property='og:title' content='The og title'><link rel='canonical' href='https://example.org/canonical/1351047'>"
        r = self.held(self.w.page(self.put("f.html", page(head=head, title="The tag title")))[0])["record"]
        self.assertEqual(r["title"], "The og title")
        self.assertEqual((r["metadata"]["canonical_url"], r["metadata"]["page_title"]), ("https://example.org/canonical/1351047", "The tag title"))

    def test_text_plain_in_cp1252_with_crlf(self):
        data = "Line one costs £5.\r\nLine two.\r\n".encode("cp1252")
        row = self.w.page(self.put("g.txt", data))[0]; h = self.held(row); f = os.path.join(self.root, row["hold"])
        self.assertEqual(B.read_bytes(os.path.join(f, "page.txt")), data)                          # held as obtained
        self.assertEqual(h["record"]["text"], "text.txt"); self.assertEqual(B.read_raw(os.path.join(f, "text.txt")), "Line one costs £5.\nLine two.\n")
        self.assertIn("cp1252", next(x for x in h["files"] if x["name"] == "text.txt")["tool"])
        plain = self.held(self.w.page(self.put("h.txt", b"utf-8 already\n"))[0])
        self.assertEqual(plain["record"]["text"], "page.txt")


class Threads(Base):
    def test_hn_reply_chain_and_metadata(self):
        url = self.put("item.html", HN)
        cap = self.w.thread_capture(url, metadata={"class": "forum", "circle": "the public"})
        self.assertEqual(cap.record.date, "2024-01-16"); self.assertIn("span.age", cap.record.metadata["date_basis"])
        t = next(f.text for f in cap.files if f.name == "text.md")
        self.assertIn("[101] bob, 2024-01-16T11:00:00, depth 0, reply to the story", t)
        self.assertIn("[102] carol, 2024-01-16T12:00:00, depth 1, reply to [101]\n\nA reply to bob.", t)
        self.assertIn("[103] dave, 2024-01-17T09:00:00, depth 0, reply to the story", t)
        self.assertNotIn("reply\n", t.split("[101]")[1].split("[102]")[0])                      # the reply links dropped
        row = self.w.hold(cap); h = self.held(row)
        self.assertEqual((h["record"]["metadata"]["class"], h["record"]["metadata"]["circle"]), ("forum", "the public"))   # handoff 16
        self.assertEqual(h["record"]["metadata"]["thread_renderer"], "Hacker News")
        self.assertEqual(row["hold"], "sources/web/2024-01-16-story-title-hacker-news")

    def test_thread_folder_argument(self):
        row = self.w.thread(self.put("t.html", page()), folder="sources/pilot/web/my-thread")[0]
        self.assertEqual(row["hold"], "sources/pilot/web/my-thread")


class Published(Base):
    def test_hearing_with_its_own_transcript(self):
        p = P.PublishedTranscriptAdapter(root=self.root, gap=0, sleep=lambda s: None, log=lambda m: None)
        page_url = self.put("hearing.html", page(title="Hearing day 1", body="<p>Published: 9 April 2024</p>"))
        txt = self.put("day1.txt", "Witness: £ figures\r\n  1   Q. Good morning.\r\n".encode("cp1252"))
        row = p.published(page_url, [txt], media_links=[("Day 1 AM", "https://youtu.be/AAAAAAAAAAA"), ("Day 1 PM", "https://youtu.be/BBBBBBBBBBB")],
                          identifier="INQ0001", title="Hearing day 1")
        h = B.load_hold(os.path.join(self.root, row["hold"])); r = h["record"]
        self.assertEqual((r["media_kind"], r["date"], r["text"], r["media_link"]), ("video", "2024-04-09", "transcript.txt", "https://youtu.be/AAAAAAAAAAA"))
        self.assertEqual(r["metadata"]["media_links"], ["Day 1 AM: https://youtu.be/AAAAAAAAAAA", "Day 1 PM: https://youtu.be/BBBBBBBBBBB"])
        self.assertEqual(r["metadata"]["media_status"], "linked, not downloaded"); self.assertIn("control", r["metadata"]["transcription"])
        self.assertEqual(B.read_raw(os.path.join(self.root, row["hold"], "transcript.txt")), "Witness: £ figures\n  1   Q. Good morning.\n")
        self.assertEqual(row["hold"], "sources/video/2024-04-09-inq0001-hearing-day-1")
        self.assertEqual(B.verify_hold(os.path.join(self.root, row["hold"])), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
