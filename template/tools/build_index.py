#!/usr/bin/env python3
"""Rebuild README.md from the metadata tables in videos/*.md and books/*.md and the H1 + first paragraph of subjects/*.md.
Run from the project folder: python3 tools/build_index.py
The page's title, prose, section names, the nouns of its counts, the short labels and the tag aliases are the pack's display
settings (pack.toml [display.index], with the core defaults of tools/packload.py DISPLAY_DEFAULTS); nothing here names the domain."""
import re, glob, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)

import packload   # the display settings: titles, prose, section names, short labels and tag aliases (pack.toml [display.index]; moved 2026-10-22, phase 5)
D = packload.display("index")
TAG_MAP = D["tag_aliases"]     # normalize near-duplicate tags (lowercase key -> canonical)
SHORT = D["short_labels"]      # short labels for the tag index (note file name -> label)
SHORT_RULES = [(r["title_contains"], re.compile(r["number_regex"]), r["format"]) for r in D["short_rules"]]   # a channel's titles labelled by episode number

def short_of(m):
    if m["file"] in SHORT: return SHORT[m["file"]]
    for contains, rx, fmt in SHORT_RULES:
        if contains in m["title"]: return fmt.format(rx.search(m["title"]).group(1))
    return m["title"][:D["short_chars"]]

def meta(path):
    s = LN.read_text(path)
    m = {"file": os.path.basename(path), "dir": os.path.dirname(path), "title": LN.title_re(s)}   # form M3c
    for k in ("Channel", "Uploaded", "Length", "Subjects", "Tags"):
        m[k.lower()] = LN.meta_value(s, k)   # form M2b
    m["short"] = short_of(m)
    m["taglist"] = [TAG_MAP.get(t.strip().lower(), t.strip()) for t in m["tags"].split(",") if t.strip()]
    return m

vids = sorted((meta(p) for p in glob.glob("videos/*.md")), key=lambda v: v["uploaded"])
books = sorted((meta(p) for p in glob.glob("books/*.md")), key=lambda v: v["uploaded"])
research = sorted((meta(p) for p in glob.glob("research/*.md")), key=lambda v: v["uploaded"])
allnotes = vids + books + research
subs = []
for p in sorted(glob.glob("subjects/*.md")):
    s = LN.read_text(p); h1 = re.search(r"^# (.+)$", s, re.M).group(1)
    desc = re.search(r"^# .+\n\n(.+?)\n", s, re.M).group(1)
    desc = re.sub(r"\]\((?!https?://|subjects/)([^)]+\.md)\)", r"](subjects/\1)", desc)  # fix relative links copied from subject pages
    n = sum(1 for v in vids if os.path.basename(p) in v["subjects"])
    nb = sum(1 for v in books if os.path.basename(p) in v["subjects"])
    subs.append((h1, p, desc, n, nb))

tags = defaultdict(list)
for v in allnotes:
    for t in dict.fromkeys(v["taglist"]): tags[t].append(v)

def noun(n, pair): return pair[0] if n == 1 else pair[1]
def cols(c): return ["| " + " | ".join(c) + " |", "|" + "---|" * len(c)]
out = ["# " + (D["title"] or packload.ledger_title()), "", D["intro"], "",
"## " + D["organised_heading"], "", "```", *D["layout"], "```", "",
"## " + D["subjects_heading"], ""]
for h1, p, desc, n, nb in subs:
    cnt = f"{n} {noun(n, D['note_noun'])}" + (f", {nb} {noun(nb, D['book_noun'])}" if nb else "")
    out.append(f"- [{h1}]({p}) — {desc.rstrip('.')} ({cnt})")
out += ["", "## " + D["notes_heading"], "", D["notes_intro"], "", *cols(D["notes_columns"])]
for v in vids:
    subj = v["subjects"].replace("](../", "](")
    out.append(f"| {v['uploaded']} | [{v['title']}](videos/{v['file']}) | {v['channel']} | {v['length']} | {subj} |")
if books:
    out += ["", "## " + D["books_heading"], "", D["books_intro"], "", *cols(D["books_columns"])]
    for v in books:
        subj = v["subjects"].replace("](../", "](")
        out.append(f"| {v['uploaded'][:4]} | [{v['title']}](books/{v['file']}) | {v['channel']} | {v['length']} | {subj} |")
if research:
    out += ["", "## " + D["research_heading"], "", D["research_intro"], "", *cols(D["research_columns"])]
    for v in research:
        subj = v["subjects"].replace("](../", "](")
        out.append(f"| {v['uploaded']} | [{v['title']}](research/{v['file']}) | {v['channel']} | {v['length']} | {subj} |")
out += ["", "## " + D["tags_heading"], "", D["tags_intro"], ""]
multi = sorted((t for t in tags if len(tags[t]) > 1), key=str.lower)
single = sorted((t for t in tags if len(tags[t]) == 1), key=str.lower)
for t in multi:
    out.append(f"- **{t}** — " + ", ".join(f"[{v['short']}]({v['dir']}/{v['file']})" for v in tags[t]))
out += ["", D["single_tags_line"], ""]
for t in single:
    v = tags[t][0]; out.append(f"- {t} — [{v['short']}]({v['dir']}/{v['file']})")
out += ["", "## " + D["adding_heading"], "", D["adding_text"], ""]
tasks = sorted(glob.glob("research/tasks/*.md"))
if tasks:
    out += ["", "## " + D["tasks_heading"], "", D["tasks_intro"], "", *cols(D["tasks_columns"])]
    for t in tasks:
        _l = [x for x in LN.read_lines(t) if x.strip()]
        _title = _l[0].lstrip("# ").strip() if _l else t; _first = next((x for x in _l[1:] if not x.startswith("#")), "")[:160].replace("|", "/")
        out.append(f"| [{t.split('/')[-1]}]({t}) | {_title} | {_first} |")
LN.write_text("README.md", "\n".join(out))
print(f"{len(vids)} {D['note_noun'][1]}, {len(books)} {D['book_noun'][1]}, {len(research)} research pages, {len(subs)} subjects, {len(tags)} tags")
