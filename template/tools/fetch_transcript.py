#!/usr/bin/env python3
"""Fetch a YouTube transcript + metadata and write a cleaned, timestamped markdown transcript.

Usage: python3 fetch_transcript.py <youtube-url-or-id> [out_dir]
Writes: <out_dir>/<video_id>.md and prints metadata as JSON.
"""
import sys, json, re, html, os, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
from youtube_transcript_api import YouTubeTranscriptApi

def video_id(s):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else s.strip()

def ts(sec):
    sec = int(sec); return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"

def main():
    args = [a for a in sys.argv[1:] if a != "--"]
    vid = video_id(args[0]); out_dir = args[1] if len(args) > 1 else "."
    url = f"https://www.youtube.com/watch?v={vid}"
    meta, upload = None, "unknown"
    try:
        r = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, timeout=20)
        if r.ok: meta = r.json()
        page = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
        m = re.search(r'"uploadDate":"([^"]+)"', page) or re.search(r'itemprop="uploadDate" content="([^"]+)"', page)
        if m: upload = m.group(1)[:10]
    except Exception:
        pass
    if meta is None or upload == "unknown":  # fallback: yt-dlp metadata (oEmbed rate-limits bursts)
        import subprocess
        out = subprocess.run(["/opt/anaconda3/bin/yt-dlp", "--skip-download", "--print", "%(title)s\t%(uploader)s\t%(upload_date)s", url],
                             capture_output=True, text=True).stdout.strip().splitlines()
        if out:
            t, a, d = out[-1].split("\t")
            meta = meta or {"title": t, "author_name": a}
            if upload == "unknown" and d and d != "NA": upload = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    api = YouTubeTranscriptApi(); tl = api.list(vid)
    codes = [t.language_code for t in tl]
    t = tl.find_transcript([c for c in codes if c.startswith("en")] or codes)
    segs = t.fetch()
    paras, buf, start, words = [], [], None, 0
    for s in segs:
        txt = html.unescape(s.text).replace("\n", " ").strip()
        if not txt or txt in ("[Music]", "[Applause]"): continue
        if start is None: start = s.start
        buf.append(txt); words += len(txt.split())
        if words >= 120:
            paras.append(f"**[{ts(start)}]** " + " ".join(buf)); buf, start, words = [], None, 0
    if buf: paras.append(f"**[{ts(start)}]** " + " ".join(buf))
    total = sum(len(p.split()) for p in paras)
    dur = ts(segs[-1].start + (segs[-1].duration or 0))
    body = (f"# Transcript: {meta['title']}\n\n"
            f"- Channel: {meta['author_name']}\n- URL: {url}\n- Uploaded: {upload}\n"
            f"- Captions: {t.language_code} ({'auto-generated' if t.is_generated else 'manual'})\n"
            f"- Length: ~{dur}, ~{total:,} words\n\n---\n\n" + "\n\n".join(paras) + "\n")
    LN.write_text(LP.new_hold(f"{out_dir}/{vid}.md", kind="youtube"), body)   # a YouTube id; the layout name is yt-<id>.md
    print(json.dumps({"id": vid, "title": meta["title"], "channel": meta["author_name"], "uploaded": upload,
                      "duration": dur, "words": total, "generated": t.is_generated}))

if __name__ == "__main__": main()
