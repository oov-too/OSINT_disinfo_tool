#!/usr/bin/env python3
"""Pull transcripts the user pasted into a Claude Code session (quoted blocks starting with 'Chapter 1:' followed by a
YouTube URL) out of the session's JSONL log, without re-typing them.
Usage: extract_pastes.py <session.jsonl> <out_dir>   -> writes paste_<videoId>.txt per transcript.
Then run parse_pasted_transcript.py on each file."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # new holds: ledger.paths.new_hold() checks the name (sources-layout.md section 4)
path, out_dir = sys.argv[1], sys.argv[2]
def texts_of(obj):
    msg = obj.get("message", obj); content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str): yield content
    elif isinstance(content, list):
        for c in content:
            if not isinstance(c, dict): continue
            if c.get("type") == "text": yield c.get("text", "")
            if c.get("type") == "tool_result":
                cc = c.get("content")
                if isinstance(cc, str): yield cc
                elif isinstance(cc, list):
                    for d in cc:
                        if isinstance(d, dict) and d.get("type") == "text": yield d.get("text", "")
seen = {}
for line in open(path):
    try: obj = json.loads(line)
    except Exception: continue
    for t in texts_of(obj):
        if "Chapter 1:" not in t or "seconds" not in t: continue
        for m in re.finditer(r'"(Chapter 1:.*?)"\s*\n+\s*(https?://www\.youtube\.com/watch\?v=([\w-]+)\S*)', t, re.S):
            vid, body = m.group(3), m.group(1)
            if vid not in seen or len(body) > len(seen[vid]): seen[vid] = body
        # the desktop app's form (2026-10-09): the URL in the message, the block inside <pasted_content ...> ... </pasted_content>
        for m in re.finditer(r'<pasted_content[^>]*>\s*(Chapter 1:.*?)</pasted_content', t, re.S):
            ids = re.findall(r'(?:v=|youtu\.be/)([\w-]{11})', t[:m.start()]) or re.findall(r'(?:v=|youtu\.be/)([\w-]{11})', t)
            if not ids: continue
            vid = ids[-1]; body = m.group(1).replace("Sync to video time", "").strip()
            if vid not in seen or len(body) > len(seen[vid]): seen[vid] = body
for vid, body in seen.items():
    LN.write_text(LP.new_hold(f"{out_dir}/paste_{vid}.txt"), body); print(vid, len(body.split()), "words")
