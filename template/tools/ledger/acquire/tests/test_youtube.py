#!/usr/bin/env python3
"""Tests of the YouTube adapter with no network call: fetch_transcript.py's API and HTTP calls and fetch_description.py's watch-page
request are replaced by fakes, the rate gate runs on a fake clock, and hold_local is tried on a held transcript."""
import importlib, json, os, unittest, urllib.request
from unittest import mock
import _common as C
from ledger.acquire import base as B, youtube as Y


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class Seg:
    def __init__(self, text, start, duration): self.text = text; self.start = start; self.duration = duration


def fake_segments(n=60):
    return [Seg(f"segment {i} says word{i} and a few more words to fill it out", i * 7.5, 7.0) for i in range(n)] + [Seg("[Music]", n * 7.5, 2.0)]


class FakeTranscript:
    language_code = "en"; is_generated = True
    def fetch(self): return fake_segments()


class FakeList:
    def __iter__(self): return iter([FakeTranscript()])
    def find_transcript(self, codes): return FakeTranscript()


class FakeApi:
    def list(self, vid): return FakeList()


class FakeResp:
    ok = True
    def __init__(self, data=None, text=""): self._d = data; self.text = text
    def json(self): return self._d


def fake_get(url, params=None, headers=None, timeout=None):
    if "oembed" in url: return FakeResp({"title": "A Test Talk [Music] edition", "author_name": "Test Channel"})
    return FakeResp(text='... "uploadDate":"2026-01-02T08:00:00-08:00" ...')


class FakeUrlopen:
    def __init__(self, req, timeout=None): self.req = req
    def read(self):
        pr = {"videoDetails": {"shortDescription": "First line of the description.\n\nSecond paragraph.", "title": "A Test Talk",
                               "author": "Test Channel", "lengthSeconds": "452"},
              "microformat": {"playerMicroformatRenderer": {"uploadDate": "2026-01-02"}}}
        return ("<html><script>var ytInitialPlayerResponse = " + json.dumps(pr) + ";</script></html>").encode("utf-8")


class YouTube(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self); self.now = [5000.0]; self.slept = []

    def clock(self): return self.now[0]
    def sleep(self, s): self.slept.append(s); self.now[0] += s

    def test_cleaning_regex_is_fetch_videos(self):
        src = B.read_raw(os.path.join(C.TOOLS, "fetch_video.py"))
        self.assertIn(Y.TAGS_RE, src)

    def test_video_id(self):
        self.assertEqual(Y.video_id("https://www.youtube.com/watch?v=-HbrTalks20&t=3"), "-HbrTalks20")
        self.assertEqual(Y.video_id("https://youtu.be/Hx12Day12Aa"), "Hx12Day12Aa")
        self.assertEqual(Y.video_id("Hx12Day12Aa"), "Hx12Day12Aa")
        self.assertIsNone(Y.video_id("not an id"))

    def test_offline_fetch_two_videos_sequential_with_the_gap(self):
        ft = importlib.import_module("fetch_transcript")
        with mock.patch.object(ft, "YouTubeTranscriptApi", FakeApi), mock.patch.object(ft.requests, "get", fake_get), \
                mock.patch.object(urllib.request, "urlopen", FakeUrlopen):
            ad = Y.YouTubeAdapter(root=self.root, gap=10, clock=self.clock, sleep=self.sleep, log=lambda m: None)
            rows = ad.acquire(["https://www.youtube.com/watch?v=AAAAAAAAAAA", "BBBBBBBBBBB"])
        self.assertEqual([r["status"] for r in rows], ["new", "new"])
        self.assertEqual(ad.gate.waits, [0.0, 10.0, 10.0, 10.0])          # transcript, description, transcript, description
        f = os.path.join(self.root, rows[0]["hold"])
        self.assertEqual(rows[0]["hold"], "sources/video/yt-AAAAAAAAAAA")
        t = B.read_raw(os.path.join(f, "transcript.md"))
        self.assertTrue(t.startswith("# Transcript: A Test Talk  edition\n\n- Channel: Test Channel\n- URL: https://www.youtube.com/watch?v=AAAAAAAAAAA\n- Uploaded: 2026-01-02\n"))
        self.assertIn("**[00:00:00]** segment 0", t)
        self.assertIn("## Video description (as posted by the channel)\n\n> First line of the description.\n>\n> Second paragraph.\n", t)
        self.assertNotIn("[Music]", t)
        h = B.load_hold(f); r = h["record"]
        self.assertEqual((r["identifier"], r["media_kind"], r["date"], r["venue"], r["text"]), ("AAAAAAAAAAA", "video", "2026-01-02", "Test Channel", "transcript.md"))
        self.assertEqual(h["files"][0]["role"], "derived")
        self.assertIn("gap 10 s", r["capture_tool"])
        self.assertEqual(B.verify_hold(f), [])

    def test_already_held_is_not_fetched(self):
        os.makedirs(os.path.join(self.root, "transcripts"))
        B.LN.write_text(os.path.join(self.root, "transcripts", "CCCCCCCCCCC.md"), "# Transcript: x\n")
        ad = Y.YouTubeAdapter(root=self.root, clock=self.clock, sleep=self.sleep, log=lambda m: None)
        self.assertEqual(ad.acquire(["CCCCCCCCCCC"]), []); self.assertEqual(ad.gate.waits, [])

    def test_gap_under_ten_refused_on_the_command_line(self):
        import contextlib, io
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
            Y.main(["XXXXXXXXXXX", "--gap", "3", "--root", self.root])
        self.assertIn("at least 10 seconds", err.getvalue())

    def test_hold_local_on_a_held_transcript(self):
        import casebook_corpus as CC
        src = os.path.join(CC.build(os.path.join(C.temp_root(self), "corpus"))["root"], "transcripts", "-HbrTalks20.md")   # synthetic
        ad = Y.YouTubeAdapter(root=self.root, log=lambda m: None)
        row = ad.hold_local(src)
        self.assertEqual(row["hold"], "sources/video/yt--HbrTalks20")          # an id starting with '-' under the yt- prefix
        f = os.path.join(self.root, row["hold"])
        self.assertEqual(C.sha(os.path.join(f, "transcript.md")), C.sha(src))
        h = B.load_hold(f); hdr = Y.parse_transcript_header(B.LN.read_text(src))
        self.assertEqual(h["record"]["title"], hdr["title"]); self.assertEqual(h["record"]["date"], hdr["uploaded"])
        self.assertEqual(h["files"][0]["role"], "held")
        self.assertEqual(B.verify_hold(f), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
