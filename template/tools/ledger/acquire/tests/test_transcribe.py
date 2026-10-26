#!/usr/bin/env python3
"""Tests of local transcription: the transcript form is tools/fetch_transcript.py's byte for byte; with no engine the media are
held and queued; with a stand-in openai-whisper or faster-whisper module the transcript and the settings are recorded, the weights
come from the configured folder (a path is passed, never a model name), and missing weights stop before any load."""
import importlib, os, sys, types, unittest, urllib.request
from unittest import mock
import _common as C
import test_youtube as TY
from ledger.acquire import base as B, transcribe as TR


def setUpModule(): C.block_network()
def tearDownModule(): C.allow_network()


class Form(unittest.TestCase):
    def test_same_form_as_fetch_transcript(self):
        root = C.temp_root(self); ft = importlib.import_module("fetch_transcript")
        argv = sys.argv
        try:
            sys.argv = ["fetch_transcript.py", "AAAAAAAAAAA", root]
            with mock.patch.object(ft, "YouTubeTranscriptApi", TY.FakeApi), mock.patch.object(ft.requests, "get", TY.fake_get), \
                    mock.patch("sys.stdout"):
                ft.main()
        finally:
            sys.argv = argv
        theirs = B.read_raw(os.path.join(root, "AAAAAAAAAAA.md"))
        segs = [(s.start, s.duration, s.text) for s in TY.fake_segments()]
        ours = TR.format_transcript("A Test Talk [Music] edition", "Test Channel", "https://www.youtube.com/watch?v=AAAAAAAAAAA", "2026-01-02",
                                    "en (auto-generated)", segs)
        self.assertEqual(ours, theirs)


def fake_whisper(calls):
    m = types.ModuleType("whisper"); m.__version__ = "stand-in"
    class Model:
        def transcribe(self, media, **opts):
            calls.append(("transcribe", media, opts))
            return {"language": "en", "segments": [{"start": 0.0, "end": 4.0, "text": " Hello and welcome."},
                                                   {"start": 4.0, "end": 9.5, "text": " Today we talk about held sources."}]}
    def load_model(name, device=None):
        calls.append(("load_model", name, device)); return Model()
    m.load_model = load_model
    return m


def fake_faster_whisper(calls):
    m = types.ModuleType("faster_whisper"); m.__version__ = "stand-in"
    class Seg:
        def __init__(self, s, e, t): self.start = s; self.end = e; self.text = t
    class Info: language = "en"; duration = 6.0
    class WhisperModel:
        def __init__(self, path, device=None, compute_type=None, local_files_only=None):
            calls.append(("model", path, device, compute_type, local_files_only))
        def transcribe(self, media, beam_size=None, language=None):
            return iter([Seg(0.0, 3.0, " One."), Seg(3.0, 6.0, " Two.")]), Info()
    m.WhisperModel = WhisperModel
    return m


class Adapter(unittest.TestCase):
    def setUp(self):
        self.root = C.temp_root(self)
        self.media = os.path.join(self.root, "talk.wav")
        with open(self.media, "wb") as f: f.write(b"RIFF\x24\x00\x00\x00WAVEfmt " + bytes(28))
        self.weights = os.path.join(self.root, "weights"); os.makedirs(self.weights)

    def no_engines(self):
        return mock.patch.dict(sys.modules, {"whisper": None, "faster_whisper": None})

    def test_no_engine_holds_the_media_and_queues_it(self):
        with self.no_engines():
            ad = TR.TranscribeAdapter(root=self.root, log=lambda m: None)
            row = ad.hold(ad.capture_media(self.media, title="A talk"))
        f = os.path.join(self.root, row["hold"])
        self.assertEqual(C.sha(os.path.join(f, "talk.wav")), C.sha(self.media))
        h = B.load_hold(f)
        self.assertIsNone(h["record"]["text"]); self.assertEqual(h["record"]["media_kind"], "audio")
        self.assertEqual(h["record"]["metadata"]["transcription"], "transcriber missing")
        self.assertIn("queued for transcription", h["status_note"]); self.assertEqual(B.verify_hold(f), [])

    def test_openai_whisper_from_local_weights(self):
        open(os.path.join(self.weights, "small.pt"), "wb").close()
        calls = []
        with mock.patch.dict(sys.modules, {"whisper": fake_whisper(calls)}), mock.patch.object(TR.shutil, "which", lambda n: "/stand-in/ffmpeg" if n == "ffmpeg" else None), \
                mock.patch.object(TR, "gpu", lambda: None):
            ad = TR.TranscribeAdapter(root=self.root, model="small", weights=self.weights, log=lambda m: None)
            row = ad.hold(ad.capture_media(self.media, title="A talk", venue="A seminar", date="2026-10-01"))
        self.assertEqual(calls[0], ("load_model", os.path.join(self.weights, "small.pt"), "cpu"))   # a path, never a name
        f = os.path.join(self.root, row["hold"]); t = B.read_raw(os.path.join(f, "transcript.md"))
        self.assertTrue(t.startswith("# Transcript: A talk\n\n- Channel: A seminar\n- URL: talk.wav\n- Uploaded: 2026-10-01\n"
                                     "- Captions: en (local transcription: openai-whisper small, cpu)\n- Length: ~00:00:09, ~10 words\n\n---\n\n"))   # the timestamp counts as a word, as fetch_transcript.py counts
        self.assertIn("**[00:00:00]** Hello and welcome. Today we talk about held sources.", t)
        st = B.load_hold(f)["record"]["metadata"]["transcription"]
        self.assertEqual((st["engine"], st["model"], st["device"], st["weights"], st["fp16"]), ("openai-whisper", "small", "cpu", os.path.join(self.weights, "small.pt"), False))
        self.assertEqual(B.verify_hold(f), [])

    def test_faster_whisper_local_files_only(self):
        d = os.path.join(self.weights, "faster-whisper-small"); os.makedirs(d); open(os.path.join(d, "model.bin"), "wb").close()
        calls = []
        with mock.patch.dict(sys.modules, {"whisper": None, "faster_whisper": fake_faster_whisper(calls)}), mock.patch.object(TR, "gpu", lambda: None):
            ad = TR.TranscribeAdapter(root=self.root, model="small", weights=self.weights, log=lambda m: None)
            row = ad.hold(ad.capture_media(self.media, title="A talk"))
        self.assertEqual(calls[0], ("model", d, "cpu", "int8", True))
        self.assertIn("**[00:00:00]** One. Two.", B.read_raw(os.path.join(self.root, row["hold"], "transcript.md")))

    def test_missing_weights_stop_before_any_load(self):
        calls = []
        with mock.patch.dict(sys.modules, {"whisper": fake_whisper(calls)}):
            ad = TR.TranscribeAdapter(root=self.root, model="medium", weights=self.weights, log=lambda m: None)
            row = ad.hold(ad.capture_media(self.media))
        self.assertEqual(calls, [])
        self.assertEqual(B.load_hold(os.path.join(self.root, row["hold"]))["record"]["metadata"]["transcription"], "weights missing: no local weights for model 'medium' in " + self.weights)

    def test_detect(self):
        rep = TR.detect(self.root)
        self.assertIn(rep["engine"], ("missing", "openai-whisper", "faster-whisper")); self.assertEqual(rep["device_default"], "cpu")
        print("\n    " + str(rep))


if __name__ == "__main__":
    unittest.main(verbosity=2)
