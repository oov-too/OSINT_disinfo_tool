"""Local transcription of audio and video (phase 3 of tools/platform-plan.md, 2026-10-22; Portability: binaries and weights per
platform, nothing fetched). The media file is held byte-for-byte in sources/audio/<slug>/ or sources/video/<slug>/ and the
transcript is written in the form tools/fetch_transcript.py writes (header lines, `---`, paragraphs of about 120 words each opening
with **[HH:MM:SS]**), so every tool that reads a YouTube transcript reads this one; the README records the engine, model, weights,
device and settings.

Engines, the first installed wins: openai-whisper (`import whisper`; decodes with the ffmpeg binary) or faster-whisper
(`import faster_whisper`; decodes with PyAV, no ffmpeg binary). Device: CPU by default; CUDA when torch reports a GPU
(device="auto"); "mps" only when asked. Weights come from a configured folder and are never downloaded:
- the folder: weights_dir=, else $LEDGER_WHISPER_WEIGHTS, else ledger.toml [acquire] whisper_weights;
- openai-whisper: <folder>/<model>.pt (e.g. small.pt, medium.en.pt), passed to whisper.load_model as a path, which loads the file
  and never reaches the network;
- faster-whisper: <folder>/faster-whisper-<model>/ or <folder>/<model>/ (a CTranslate2 model folder with model.bin), opened with
  local_files_only=True.
With no engine, no weights or no decoder the media are still held and the status says what is missing ('transcriber missing',
'weights missing', 'ffmpeg missing'), so the item is queued, not lost.

    python3 tools/ledger/acquire/transcribe.py <media file> [--title T] [--model small] [--weights DIR] [--device auto|cpu|cuda|mps]
        [--language en] [--venue V] [--date YYYY-MM-DD] [--root DIR]
    python3 tools/ledger/acquire/transcribe.py --detect
"""
import html, json, os, shutil, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg", ".3gp"}
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT


def ts(sec):
    """tools/fetch_transcript.py's timestamp: HH:MM:SS from seconds, truncated."""
    sec = int(sec); return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"


DESCRIPTION_HEAD = "## Video description (as posted by the channel)"   # tools/fetch_description.py's block heading


def description_block(desc):
    """The channel description block as tools/fetch_description.py appends it: a rule, the heading, the description quoted line by
    line (`> line`, a bare `>` for a blank line). A description already in that quoted form (every non-blank line starting with
    `>`) is kept as it is, so a catalogue that stored the block's body does not get it quoted twice."""
    d = str(desc).replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = d.split("\n")
    quoted = all(l.startswith(">") for l in lines if l.strip())
    body = d if quoted else "\n".join(("> " + l) if l.strip() else ">" for l in lines)
    return "\n\n---\n\n" + DESCRIPTION_HEAD + "\n\n" + body + "\n"


def format_transcript(title, channel, url, uploaded, captions, segments, description=None):
    """The transcript in tools/fetch_transcript.py's form, from segments [(start seconds, duration seconds, text)] or
    [(start, duration, text, heading)]. The paragraph rule, the skipped [Music] and [Applause] segments, the word count (which counts
    each paragraph's timestamp as a word, as the tool does) and the length (the last segment's start plus its duration) are the
    tool's; tests/test_transcribe.py checks the two agree byte for byte on the same segments.
    A heading (a chapter label) is written as the held transcripts with chapters write it (tools/fetch_transcript.py's form): a
    `### <heading>` line before the paragraph that opens the chapter, the paragraph in progress closed first; it is written when
    the label changes, and its words are not counted. `description` closes the transcript with the channel description block of
    tools/fetch_description.py."""
    paras, buf, start, words = [], [], None, 0
    heading = None; total = 0
    for seg in segments:
        s_start, s_dur, s_text = seg[0], seg[1], seg[2]
        h = seg[3] if len(seg) > 3 else None
        txt = html.unescape(s_text).replace("\n", " ").strip()
        if not txt or txt in ("[Music]", "[Applause]"): continue
        if h not in (None, "") and h != heading:
            if buf: paras.append(f"**[{ts(start)}]** " + " ".join(buf)); total += len(paras[-1].split()); buf, start, words = [], None, 0
            paras.append(f"### {str(h).strip()}"); heading = h
        if start is None: start = s_start
        buf.append(txt); words += len(txt.split())
        if words >= 120:
            paras.append(f"**[{ts(start)}]** " + " ".join(buf)); total += len(paras[-1].split()); buf, start, words = [], None, 0
    if buf: paras.append(f"**[{ts(start)}]** " + " ".join(buf)); total += len(paras[-1].split())
    last = segments[-1] if segments else (0, 0, "")
    dur = ts(last[0] + (last[1] or 0))
    out = (f"# Transcript: {title}\n\n"
           f"- Channel: {channel}\n- URL: {url}\n- Uploaded: {uploaded}\n"
           f"- Captions: {captions}\n"
           f"- Length: ~{dur}, ~{total:,} words\n\n---\n\n" + "\n\n".join(paras) + "\n")
    if description not in (None, "") and str(description).strip():
        out = out.rstrip("\n") + description_block(description)
    return out


# ============================================================================================================ detection
def engine():
    """('openai-whisper', version) | ('faster-whisper', version) | (None, None)."""
    try:
        import whisper
        return "openai-whisper", getattr(whisper, "__version__", "installed")
    except ImportError:
        pass
    try:
        import faster_whisper
        return "faster-whisper", getattr(faster_whisper, "__version__", "installed")
    except ImportError:
        return None, None


def gpu():
    try:
        import torch
        if torch.cuda.is_available(): return "cuda"
    except Exception:
        pass
    return None


def weights_dir(root=None, given=None):
    if given: return given
    if os.environ.get("LEDGER_WHISPER_WEIGHTS"): return os.environ["LEDGER_WHISPER_WEIGHTS"]
    try:
        import tomllib
        p = os.path.join(root or B.LP.root(), "ledger.toml")
        if os.path.isfile(p):
            with open(p, "rb") as f: v = (tomllib.load(f).get("acquire") or {}).get("whisper_weights")
            if v: return v if os.path.isabs(v) else os.path.join(os.path.dirname(p), v)
    except Exception:
        pass
    return None


def weights_path(eng, model, folder):
    """The local weights of `model` for the engine, or None (never a model name the engine would download)."""
    if not folder: return None
    if eng == "openai-whisper":
        p = model if model.endswith(".pt") and os.path.isfile(model) else os.path.join(folder, f"{model}.pt")
        return p if os.path.isfile(p) else None
    if eng == "faster-whisper":
        for p in (os.path.join(folder, f"faster-whisper-{model}"), os.path.join(folder, model)):
            if os.path.isfile(os.path.join(p, "model.bin")): return p
    return None


def detect(root=None, model="small", given=None):
    eng, ver = engine(); folder = weights_dir(root, given)
    return dict(engine=eng or "missing", engine_version=ver, device_default="cpu", gpu=gpu() or "none",
                ffmpeg=shutil.which("ffmpeg") or "missing", weights_dir=folder or "not configured", model=model,
                weights=weights_path(eng, model, folder) if eng else None)


# ============================================================================================================ the adapter
class TranscribeAdapter(B.Adapter):
    name = "transcribe"

    def __init__(self, root=None, model="small", weights=None, device="auto", language=None, beam_size=5, compute_type=None, **kw):
        super().__init__(root=root, **kw)
        self.model = model; self.weights = weights; self.device_wanted = device; self.language = language
        self.beam_size = beam_size; self.compute_type = compute_type

    def device(self):
        if self.device_wanted == "auto": return gpu() or "cpu"
        return self.device_wanted

    def transcribe(self, media):
        """(segments [(start, duration, text)], settings dict) or raises RuntimeError naming what is missing."""
        eng, ver = engine()
        if not eng: raise RuntimeError("transcriber missing (install openai-whisper or faster-whisper, with weights in a local folder)")
        folder = weights_dir(self.root, self.weights); wp = weights_path(eng, self.model, folder)
        if not wp: raise RuntimeError(f"weights missing: no local weights for model {self.model!r} in {folder or 'an unconfigured folder'} "
                                      "(set --weights, $LEDGER_WHISPER_WEIGHTS or ledger.toml [acquire] whisper_weights; nothing is downloaded)")
        dev = self.device()
        settings = dict(engine=eng, engine_version=ver, model=self.model, weights=wp, device=dev, language=self.language or "detected",
                        beam_size=self.beam_size)
        if eng == "openai-whisper":
            if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg missing (openai-whisper decodes media with the ffmpeg binary)")
            import whisper
            m = whisper.load_model(wp, device=dev)
            opts = dict(beam_size=self.beam_size, fp16=(dev == "cuda"))
            if self.language: opts["language"] = self.language
            settings.update(fp16=opts["fp16"], temperature="whisper default fallback (0.0 to 1.0 by 0.2)")
            r = m.transcribe(media, **opts)
            settings["language"] = r.get("language") or settings["language"]
            segs = [(s["start"], s["end"] - s["start"], s["text"]) for s in r.get("segments", [])]
        else:
            from faster_whisper import WhisperModel
            ct = self.compute_type or ("float16" if dev == "cuda" else "int8")
            m = WhisperModel(wp, device=dev, compute_type=ct, local_files_only=True)
            it, info = m.transcribe(media, beam_size=self.beam_size, language=self.language)
            segs = [(s.start, s.end - s.start, s.text) for s in it]
            settings.update(compute_type=ct, language=getattr(info, "language", None) or settings["language"],
                            duration=getattr(info, "duration", None))
        return segs, settings

    def capture_media(self, path, title=None, identifier=None, venue=None, date=None, speakers=None, media_link=None,
                      provenance=None, metadata=None):
        ap = self.abs(path); base = os.path.basename(ap); stem, ext = os.path.splitext(base); ext = ext.lower()
        kind = "audio" if ext in AUDIO_EXT else "video"
        held_name = base if len(base) <= B.INNER_NAME_CAP and not B.LP.name_problems(base) else "media" + ext
        inside = ap.startswith(self.root + os.sep)
        files = [B.HeldFile(held_name, src=ap, how=f"copied byte-for-byte from {self.rel(ap) if inside else ap}")]
        md = dict(metadata or {}); note = ""
        title = title or stem
        try:
            segs, settings = self.transcribe(ap)
            captions = f"{settings['language']} (local transcription: {settings['engine']} {settings['model']}, {settings['device']})"
            text = format_transcript(title, venue or "unknown", media_link or (self.rel(ap) if inside else ap), date or "unknown", captions, segs)
            files.append(B.HeldFile("transcript.md", text=text, role="derived", derived_from=held_name,
                                    tool=f"{settings['engine']} {settings['engine_version']} model {settings['model']} on {settings['device']}",
                                    how="local transcription in the form of tools/fetch_transcript.py"))
            md["transcription"] = settings; md["segments"] = len(segs)
        except RuntimeError as e:
            md["transcription"] = str(e).split(" (")[0]; note = f"Not transcribed: {e}. The media are held; the item is queued for transcription."
        rec = B.Record(identifier or stem, kind, title, date=date, speaker_or_author=speakers, venue=venue,
                       text="transcript.md" if any(f.name == "transcript.md" for f in files) else None,
                       media_link=media_link or held_name, provenance=provenance or (self.rel(ap) if inside else ap), metadata=md)
        rec.capture_tool = f"{self.tool} ({md['transcription']['engine'] + ' ' + md['transcription']['model'] if isinstance(md['transcription'], dict) else md['transcription']})"
        return B.Capture(rec, files, folder=str(self.hold_path(kind, (date + " " if date else "") + B.safe_slug(identifier or stem, 40),
                                                             title if title != (identifier or stem) else "")).replace("\\", "/"),
                         status_note=note)

    def fetch(self, paths, **kw):
        return [self.capture_media(p, **kw) for p in paths]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*"); ap.add_argument("--title"); ap.add_argument("--model", default="small")
    ap.add_argument("--weights"); ap.add_argument("--device", default="auto"); ap.add_argument("--language")
    ap.add_argument("--venue"); ap.add_argument("--date"); ap.add_argument("--root"); ap.add_argument("--detect", action="store_true")
    a = ap.parse_args(argv)
    if a.detect: print(json.dumps(detect(a.root, a.model, a.weights), indent=1)); return
    t = TranscribeAdapter(root=a.root, model=a.model, weights=a.weights, device=a.device, language=a.language)
    for r in t.acquire(a.files, title=a.title, venue=a.venue, date=a.date): print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
