#!/usr/bin/env python3
"""List the videos in a YouTube playlist. Usage: python3 list_playlist.py <playlist-url-or-id>"""
import sys, re, subprocess
s = sys.argv[1]
m = re.search(r"list=([A-Za-z0-9_-]+)", s); pl = m.group(1) if m else s
subprocess.run(["/opt/anaconda3/bin/yt-dlp", "--flat-playlist",
                "--print", "%(id)s | %(duration_string)s | %(uploader)s | %(title)s",
                f"https://www.youtube.com/playlist?list={pl}"])
