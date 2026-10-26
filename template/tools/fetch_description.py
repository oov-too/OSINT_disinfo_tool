#!/usr/bin/env python3
"""Fetch a YouTube video's full description (and title, channel, upload date, length) from the watch page and
append it to the transcript file as a '## Video description' block (idempotent).
Usage: fetch_description.py <video_id> [transcripts_dir]"""
import json, re, sys, urllib.request, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
vid = sys.argv[1]; tdir = sys.argv[2] if len(sys.argv) > 2 else "transcripts"
req = urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
m = re.search(r'var ytInitialPlayerResponse = (\{.*?\});(?:</script>|var )', page, re.S)
desc = title = author = date = length = None
if m:
    try:
        d = json.loads(m.group(1)); vd = d.get("videoDetails", {}); mf = d.get("microformat", {}).get("playerMicroformatRenderer", {})
        desc = vd.get("shortDescription"); title = vd.get("title"); author = vd.get("author"); length = vd.get("lengthSeconds")
        date = mf.get("uploadDate") or mf.get("publishDate")
    except Exception as e:
        print("json parse failed:", e, file=sys.stderr)
if desc is None:
    mm = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', page)
    if mm: desc = json.loads('"' + mm.group(1) + '"')
if desc is None:
    sys.exit(f"{vid}: no description found")
desc = html.unescape(desc).strip()
path = f"{tdir}/{vid}.md"
s = LN.read_text(path)
block = "\n\n---\n\n## Video description (as posted by the channel)\n\n" + "\n".join(("> " + l) if l.strip() else ">" for l in desc.split("\n")) + "\n"
if "## Video description (as posted by the channel)" in s:
    s = s.split("\n\n---\n\n## Video description (as posted by the channel)")[0].rstrip("\n") + block
else:
    s = s.rstrip("\n") + block
LN.write_text(path, s)
print(f"{vid}: {title!r} | {author} | {date} | {length}s | description {len(desc.split())} words -> {path}")
