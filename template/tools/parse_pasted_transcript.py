#!/usr/bin/env python3
"""Convert a transcript pasted from YouTube's transcript panel (with doubled timestamps like
'1:101 minute, 10 secondsText...' and 'Chapter N: Title' lines) into the standard transcript format.
Usage: parse_pasted_transcript.py <raw.txt> <video_id> "<title>" "<channel>" <uploaded YYYY-MM-DD> <duration> <out_dir>"""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
raw, vid, title, channel, uploaded, duration, out_dir = sys.argv[1:8]
ts_re = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)((?:\d+ (?:hours?|minutes?|seconds?)(?:, )?)+)?(.*)$")
def ts(s):
    p = [int(x) for x in s.split(":")]
    if len(p) == 2: p = [0] + p
    return f"{p[0]:02d}:{p[1]:02d}:{p[2]:02d}"
paras, buf, start, words = [], [], None, 0
def flush():
    global buf, start, words
    if buf: paras.append(f"**[{start}]** " + " ".join(buf)); buf, start, words = [], None, 0
for line in LN.iter_lines(raw):
    line = line.rstrip("\n").strip()
    if not line or line == "Sync to video time": continue
    if re.match(r"^Chapter \d+:", line):
        flush(); paras.append(f"### {line}"); continue
    m = ts_re.match(line)
    if m:
        t, text = ts(m.group(1)), m.group(3).strip()
        if start is None: start = t
        text = re.sub(r"\[music\]|\[laughter\]|\[snorts\]|\[applause\]", "", text, flags=re.I).strip()
        text = re.sub(r"\s+", " ", text)
        if text: buf.append(text); words += len(text.split())
        if words >= 120: flush()
    else:
        buf.append(line); words += len(line.split())
flush()
total = sum(len(p.split()) for p in paras if not p.startswith("###"))
body = (f"# Transcript: {title}\n\n- Channel: {channel}\n- URL: https://www.youtube.com/watch?v={vid}\n- Uploaded: {uploaded}\n"
        f"- Captions: en (auto-generated, pasted from YouTube transcript panel; chapter headings preserved)\n- Length: ~{duration}, ~{total:,} words\n\n---\n\n" + "\n\n".join(paras) + "\n")
LN.write_text(LP.new_hold(f"{out_dir}/{vid}.md", kind="youtube" if LP.YT_ID_RE.match(vid) else "file"), body); print(vid, total, "words", sum(1 for p in paras if p.startswith('###')), "chapters")
