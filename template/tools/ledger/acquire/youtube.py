"""The YouTube adapter (phase 3 of tools/platform-plan.md, 2026-10-22): a video's transcript, metadata and channel description,
held in sources/video/yt-<id>/ with its README.

Wraps the existing fetch tools' logic by import, changing none of them:
- tools/fetch_transcript.py (import-safe): its main() fetches oEmbed, the watch page and the caption track and writes the
  timestamped markdown transcript; run in-process with its argv set and its output folder a staging folder;
- tools/fetch_video.py's cleaning step: the same tag regex (TAGS_RE below; tests/test_youtube.py checks it against the tool's
  source so the two cannot drift);
- tools/fetch_description.py (a script that runs at import): run in-process through runpy with its argv set, appending the
  "## Video description (as posted by the channel)" block to the staged transcript, as it does in transcripts/.

The rate rule (standing rule of 2026-09-27; memory youtube-rate-limit): never burst YouTube. One request step at a time, with at
least `gap` seconds (default 10) between steps and between videos, enforced by a RateGate whose lock is an atomic directory
create, so two runs on one machine cannot interleave. Never run in parallel with itself or with the underlying tools.

A video already held (transcripts/<id>.md, or sources/video/yt-<id>.md through the alias table, or a hold folder) is not fetched
again unless force=True; hold_local() holds an existing transcript file in the new layout without a network call.

    python3 tools/ledger/acquire/youtube.py <id-or-url> [...] [--gap 10] [--force] [--root DIR]
    python3 tools/ledger/acquire/youtube.py --local transcripts/<id>.md [--root DIR]
"""
import contextlib, io, json, os, re, runpy, sys, tempfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ledger.acquire import base as B

TAGS_RE = r"\[(Music|Applause|Laughter|music|applause|laughter|sighs|clears throat)\]"   # tools/fetch_video.py's cleaning step
ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")
BARE_ID_RE = re.compile(r"^([A-Za-z0-9_-]{11})$")
HEADER_RE = {"channel": r"^- Channel: (.*)$", "url": r"^- URL: (.*)$", "uploaded": r"^- Uploaded: (.*)$",
             "captions": r"^- Captions: (.*)$", "length": r"^- Length: (.*)$"}


def video_id(s):
    """The 11-character id of a URL or a bare id (tools/fetch_video.py's two patterns), or None."""
    m = ID_RE.search(s) or BARE_ID_RE.search(s.strip())
    return m.group(1) if m else None


def parse_transcript_header(text):
    """The header lines tools/fetch_transcript.py writes: title, channel, url, uploaded, captions, length, words."""
    out = {}
    m = re.search(r"^# Transcript: (.*)$", text, re.M)
    if m: out["title"] = m.group(1).strip()
    for k, rx in HEADER_RE.items():
        m = re.search(rx, text, re.M)
        if m: out[k] = m.group(1).strip()
    m = re.search(r"~([\d,]+) words", out.get("length", ""))
    if m: out["words"] = int(m.group(1).replace(",", ""))
    out["has_description"] = "## Video description (as posted by the channel)" in text
    return out


class YouTubeAdapter(B.Adapter):
    name = "youtube"

    def __init__(self, root=None, gap=10.0, force=False, clock=None, sleep=None, **kw):
        super().__init__(root=root, **kw)
        import time
        self.gap = float(gap); self.force = force
        self.gate = B.RateGate("youtube", self.gap, self.state_dir, clock=clock or time.time, sleep=sleep or time.sleep)

    def already_held(self, vid):
        """The path of a held transcript of this video, or None: the legacy transcripts/<id>.md, its layout alias, a hold folder."""
        for rel in (f"transcripts/{vid}.md", f"sources/video/yt-{vid}.md", f"{self.hold_root}/video/yt-{vid}/transcript.md"):
            p = self.abs(rel)
            if os.path.isfile(p): return rel
            try:
                rp = B.LP.resolve(rel) if self.root == B.LP.root() else None
                if rp and os.path.isfile(rp): return B.LP.rel(rp)
            except Exception: pass
        return None

    # ---------------------------------------------------------------------------------------------------- the two steps
    def _transcript_step(self, vid, staging):
        import importlib
        ft = importlib.import_module("fetch_transcript")
        out = io.StringIO(); err = io.StringIO(); argv = sys.argv
        try:
            sys.argv = ["fetch_transcript.py", vid, staging]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): ft.main()
        except BaseException as e:   # the tool raises on a missing caption track; SystemExit from the library is caught too
            return None, f"{type(e).__name__}: {str(e)[:200]}"
        finally:
            sys.argv = argv
        meta = {}
        for line in out.getvalue().splitlines()[::-1]:
            try: meta = json.loads(line); break
            except ValueError: continue
        return meta, None

    def _description_step(self, vid, staging):
        path = os.path.join(B.TOOLS, "fetch_description.py")
        out = io.StringIO(); err = io.StringIO(); argv = sys.argv
        try:
            sys.argv = [path, vid, staging]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): runpy.run_path(path, run_name="__main__")
            return out.getvalue().strip(), None
        except BaseException as e:
            return None, f"{type(e).__name__}: {str(e)[:200] or err.getvalue().strip()[-200:]}"
        finally:
            sys.argv = argv

    # ---------------------------------------------------------------------------------------------------- fetch
    def fetch(self, items):
        caps = []
        for n, item in enumerate(items):
            vid = video_id(item)
            if not vid:
                caps.append(B.Capture(B.Record(item, "video", None), [], status_note=f"not a YouTube id or URL: {item!r}")); continue
            held = self.already_held(vid)
            if held and not self.force:
                self.log(f"{vid}: already held at {held}; not fetched (force=True to capture again)")
                continue
            with tempfile.TemporaryDirectory() as staging:
                with self.gate: meta, err = self._transcript_step(vid, staging)
                tp = os.path.join(staging, f"{vid}.md")
                if err or not os.path.isfile(tp):
                    rec = B.Record(vid, "video", f"[YouTube video {vid}]", media_link=f"https://www.youtube.com/watch?v={vid}",
                                   provenance=f"https://www.youtube.com/watch?v={vid}")
                    caps.append(B.Capture(rec, [], status_note=f"transcript step failed: {err or 'no file written'}"))
                    self.log(f"{vid} FAILED transcript: {err}"); continue
                s = B.LN.read_text(tp); s = re.sub(TAGS_RE, "", s); B.LN.write_text(tp, s)
                with self.gate: desc_out, derr = self._description_step(vid, staging)
                caps.append(self._capture(vid, B.LN.read_text(tp), meta or {}, derr))
                self.log(f"{vid} transcript OK; description {'OK' if not derr else 'FAILED: ' + derr}")
        return caps

    def _capture(self, vid, text, meta, desc_err=None, src=None):
        h = parse_transcript_header(text)
        url = h.get("url") or f"https://www.youtube.com/watch?v={vid}"
        up = meta.get("uploaded") or h.get("uploaded")
        date = up if up and re.fullmatch(r"\d{4}-\d{2}-\d{2}", up) else None
        md = {"captions": h.get("captions"), "length": h.get("length"), "words": meta.get("words", h.get("words")),
              "description_appended": h.get("has_description"), "date_basis": "uploaded (watch page uploadDate)"}
        if meta.get("generated") is not None: md["captions_auto_generated"] = meta["generated"]
        if desc_err: md["description_step"] = f"failed: {desc_err}"
        rec = B.Record(vid, "video", meta.get("title") or h.get("title") or f"[YouTube video {vid}]", date=date, date_raw=up,
                       venue=meta.get("channel") or h.get("channel"), media_link=url, text="transcript.md",
                       provenance=(f"{url} (copied from {src})" if src else
                                   f"{url}: oEmbed and the watch page for metadata, the caption track through youtube-transcript-api, "
                                   "the watch page's player response for the description"),
                       metadata={k: v for k, v in md.items() if v is not None})
        if src:
            files = [B.HeldFile("transcript.md", src=self.abs(src), how=f"copied byte-for-byte from {src}")]
            rec.capture_tool = f"{self.tool} (hold_local)"
        else:
            files = [B.HeldFile("transcript.md", text=text, role="derived",
                                derived_from="YouTube's caption track (not held: the tool keeps only its rendering)",
                                tool="tools/fetch_transcript.py, the tag strip of tools/fetch_video.py, tools/fetch_description.py",
                                how="timestamped paragraphs of about 120 words, then the channel description block")]
            rec.capture_tool = f"{self.tool} via tools/fetch_transcript.py and tools/fetch_description.py (gap {self.gap:g} s)"
        return B.Capture(rec, files)

    def hold_local(self, path, vid=None):
        """Hold an existing transcript file (the house form) in sources/video/yt-<id>/ without a network call."""
        ap = self.abs(path)
        vid = vid or video_id(os.path.basename(path)[:-3] if path.endswith(".md") else path) or video_id(B.LN.read_text(ap))
        if not vid: raise ValueError(f"no YouTube id in {path}")
        inside = ap.startswith(self.root + os.sep)
        return self.hold(self._capture(vid, B.LN.read_text(ap), {}, src=self.rel(ap) if inside else ap))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("items", nargs="*"); ap.add_argument("--gap", type=float, default=10.0); ap.add_argument("--force", action="store_true")
    ap.add_argument("--local", help="hold an existing transcript file instead of fetching"); ap.add_argument("--root")
    a = ap.parse_args(argv)
    if a.gap < 10: ap.error("the YouTube gap is at least 10 seconds (standing rule of 2026-09-27)")
    ad = YouTubeAdapter(root=a.root, gap=a.gap, force=a.force)
    rows = [ad.hold_local(a.local)] if a.local else ad.acquire(a.items)
    for r in rows: print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
