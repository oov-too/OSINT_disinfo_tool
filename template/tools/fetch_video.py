#!/usr/bin/env python3
"""Standard, rate-limited intake fetch for one or more YouTube videos (standing rule, 2026-09-27: never burst YouTube).

Usage: python3 tools/fetch_video.py <id-or-url> [<id-or-url> ...] [--gap 10] [--out transcripts]

For each video, in sequence: fetch_transcript.py (oEmbed + watch page + captions), strip [Music]-type tags,
fetch_description.py (watch page), with a pause of --gap seconds (default 10) between every YouTube request
and between videos. Never run this in parallel with itself or with the underlying tools.
Skips a video whose transcript file already exists (still appends the description if missing).
"""
import re, subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
args = sys.argv[1:]; gap = 10.0; out = "transcripts"
if "--gap" in args: i = args.index("--gap"); gap = float(args[i+1]); del args[i:i+2]
if "--out" in args: i = args.index("--out"); out = args[i+1]; del args[i:i+2]
ids = [ (re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", a) or re.search(r"^([A-Za-z0-9_-]{11})$", a)).group(1) for a in args ]
here = os.path.dirname(os.path.abspath(__file__))
def pause(): time.sleep(gap)
first = True
for vid in ids:
    path = f"{out}/{vid}.md"
    if not first: pause()
    first = False
    if not os.path.exists(path):
        r = subprocess.run([sys.executable, f"{here}/fetch_transcript.py", vid, out], capture_output=True, text=True)
        if not os.path.exists(path):
            err = (r.stderr.strip().splitlines() or ["no output"])[-1]
            print(f"{vid} FAILED transcript: {err[:200]}"); continue
        s = LN.read_text(path)
        s = re.sub(r"\[(Music|Applause|Laughter|music|applause|laughter|sighs|clears throat)\]", "", s)
        LN.write_text(path, s)
        words = len(s.split()); print(f"{vid} transcript OK ({words:,} words)")
        pause()
    else:
        print(f"{vid} transcript already present")
    if "## Video description" not in LN.read_text(path):
        r = subprocess.run([sys.executable, f"{here}/fetch_description.py", vid, out], capture_output=True, text=True)
        print(f"{vid} description {'OK' if r.returncode == 0 else 'FAILED: ' + r.stderr.strip()[-150:]}")
    else:
        print(f"{vid} description already present")
