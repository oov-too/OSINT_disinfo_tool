#!/usr/bin/env python3
"""Complete truncated Reddit copies from the live RSS feed (standing fix, 2026-10-02).

Why: the Arctic Shift (and PullPush) archives capture a long post once, soon after posting. A poster's long pieces may be
posted in a first state cut at about 20,000 characters and completed by a later edit, so the archive copies end
mid-sentence at ~20 KB while Reddit's RSS feed (https://www.reddit.com/r/<sub>/comments/<id>/.rss) serves the full
edited body for as long as the post is up. This tool finds such copies, fetches the feed gently, verifies that the
archive text is a prefix of the feed text, and patches the held copy in place, keeping the archive capture as a sibling.

Usage (run from the project root):
  python3 tools/reddit_rss_patch.py scan  [--dir <held Reddit folder>]                list suspects (bodies ending mid-sentence)
  python3 tools/reddit_rss_patch.py fetch --out <dir> [--gap 6] [--ids id1,id2] [--all]  sequential RSS fetch of the suspects, or of every held copy with --all (saves <id>.xml, <id>.body.html, sweep.json; resumes from an existing sweep.json)
  python3 tools/reddit_rss_patch.py apply --bodies <dir> [--apply] [--ids ...]           dry run; --apply writes the patch, the sibling, INDEX.md and the log
A held file is patched only when the feed body is longer than the held body and contains it (at least 85% of the held text's
8-word shingles occur in the feed text); the header records whether the author also revised wording before the cut (a later
version, canonical under the version rule) or only completed the post. Anything else is reported and left alone.
"""
import argparse, glob, html, json, os, re, subprocess, sys, time, datetime, difflib
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
TERMINAL = re.compile(r'[.!?)"\]*_”’:]\s*$')

def split(path):
    s = LN.read_text(path); hdr, sep, body = s.partition("\n---\n")
    return hdr, body.strip()

def header_meta(hdr):
    m = re.search(r"id (\w+), (https://www\.reddit\.com/r/(\w+)/comments/\w+/[^ ]*)", hdr)
    return (m.group(1), m.group(3), m.group(2)) if m else (None, None, None)

def suspects(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "W*.md"))):
        if f.endswith(".first-posted-state.md"): continue
        hdr, body = split(f)
        if not body or body == "[body not held]" or TERMINAL.search(body): continue
        pid, sub, url = header_meta(hdr)
        out.append(dict(file=f, id=pid, sub=sub, url=url, held_chars=len(body), held_words=len(body.split()), tail=body[-60:]))
    return out

class MD(HTMLParser):
    """Reddit's rendered HTML back to markdown-like text: links, emphasis, headings, lists, quotes, code, tables kept."""
    def __init__(s): super().__init__(); s.out = []; s.inlink = False; s.href = None; s.lt = []; s.pre = False
    def handle_starttag(s, t, attrs):
        a = dict(attrs)
        if t == "a": s.inlink = True; s.href = a.get("href", ""); s.lt = []
        elif t in ("p", "div", "ul", "ol"): s.out.append("\n\n")
        elif t == "li": s.out.append("\n- ")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"): s.out.append("\n\n" + "#" * int(t[1]) + " ")
        elif t == "br": s.out.append("\n")
        elif t == "blockquote": s.out.append("\n\n> ")
        elif t in ("strong", "b"): s.out.append("**")
        elif t in ("em", "i"): s.out.append("*")
        elif t == "del": s.out.append("~~")
        elif t == "hr": s.out.append("\n\n---\n\n")
        elif t == "pre": s.pre = True; s.out.append("\n\n```\n")
        elif t == "code" and not s.pre: s.out.append("`")
        elif t == "table": s.out.append("\n\n")
        elif t == "tr": s.out.append("\n|")
        elif t in ("td", "th"): s.out.append(" ")
        elif t == "sup": s.out.append("^")
    def handle_endtag(s, t):
        if t == "a": s.inlink = False; txt = "".join(s.lt).strip(); s.out.append(f"[{txt}]({s.href})" if s.href else txt)
        elif t in ("strong", "b"): s.out.append("**")
        elif t in ("em", "i"): s.out.append("*")
        elif t == "del": s.out.append("~~")
        elif t == "pre": s.pre = False; s.out.append("\n```\n\n")
        elif t == "code" and not s.pre: s.out.append("`")
        elif t in ("td", "th"): s.out.append(" |")
    def handle_data(s, d): (s.lt if s.inlink else s.out).append(d if s.pre else re.sub(r"[ \t\r\n]+", " ", d))

def feed_body_to_md(b):
    m = re.search(r'<div class="md">(.*)</div>\s*<!-- SC_ON -->', b, re.S)
    inner = m.group(1) if m else re.sub(r"&#32; submitted by.*$", "", b, flags=re.S)
    p = MD(); p.feed(inner); txt = "".join(p.out)
    txt = "\n".join(l.rstrip() for l in txt.split("\n")); txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt

def norm(t):
    t = re.sub(r"\\(.)", r"\1", t); t = re.sub(r"[*_#>`~|\[\]()]", "", t); t = re.sub(r"https?://\S+", "", t)
    t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", t).strip().lower()

def containment(held, full, n=8):
    """Share of the held text's n-word shingles that occur in the feed text (1.0 = every held sentence survives in the feed)."""
    def sh(t):
        w = norm(t).split(); return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
    a = sh(held[:max(0, len(held) - 60)]); b = sh(full)
    return len(a & b) / len(a) if a else 0.0

def prefix_match(held, full):
    a = norm(held); a = a[:max(0, len(a) - 60)]; b = norm(full)
    if not a or len(b) < len(a): return 0.0
    return difflib.SequenceMatcher(None, a, b[:len(a)], autojunk=False).ratio() if len(a) < 60000 else (1.0 if b.startswith(a) else 0.0)

def all_copies(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "W*.md"))):
        if f.endswith(".first-posted-state.md"): continue
        hdr, body = split(f)
        if not body or body == "[body not held]": continue
        pid, sub, url = header_meta(hdr)
        out.append(dict(file=f, id=pid, sub=sub, url=url, held_chars=len(body), held_words=len(body.split()), tail=body[-60:]))
    return out

def fetch(out, gap, ids, d, everything=False, skip=None):
    os.makedirs(out, exist_ok=True); rows = []
    if os.path.exists(os.path.join(out, "sweep.json")): rows = json.load(open(os.path.join(out, "sweep.json")))
    done = {r["id"] for r in rows} | (skip or set())
    pool = all_copies(d) if everything == "all" else ([c for c in all_copies(d) if '"is_edited": true' in split(c["file"])[0] or not TERMINAL.search(split(c["file"])[1])] if everything == "edited" else suspects(d))
    for s in pool:
        if ids and s["id"] not in ids: continue
        if s["id"] in done: continue
        rec = dict(s); xml = os.path.join(out, f"{s['id']}.xml")
        for attempt in range(4):
            code = subprocess.run(["curl", "-s", "-m", "40", "-A", UA, "-o", xml, "-w", "%{http_code}", f"https://www.reddit.com/r/{s['sub']}/comments/{s['id']}/.rss"], capture_output=True, text=True).stdout.strip()
            rec["http"] = code
            if code == "200": break
            time.sleep(20 * (attempt + 1))
        rec["fetched"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if rec.get("http") == "200":
            x = LN.read_text(xml, errors="replace"); e = re.search(r"<entry>.*?</entry>", x, re.S)
            c = re.search(r'<content type="html">(.*?)</content>', e.group(0) if e else x, re.S)
            if c:
                b = html.unescape(c.group(1)); LN.write_text(os.path.join(out, f"{s['id']}.body.html"), b)
                t = re.sub(r"<[^>]+>", " ", b); t = re.sub(r"\s+", " ", t).strip()
                rec.update(rss_html_chars=len(b), rss_words=len(t.split()), removed=("[removed]" in t[:200] or "[deleted]" in t[:200]))
            else: rec["error"] = "no content element"
        rows.append(rec); print(json.dumps(rec, ensure_ascii=False)); sys.stdout.flush(); time.sleep(gap)
    json.dump(rows, LN.open_write(os.path.join(out, "sweep.json")), indent=1, ensure_ascii=False)

def apply(bodies, do_apply, ids, d, today, force=None):
    sweep = {r["id"]: r for r in json.load(open(os.path.join(bodies, "sweep.json")))}
    index = os.path.join(d, "INDEX.md"); idx = LN.read_text(index) if os.path.exists(index) else ""
    patched = []; skipped = []
    for s in suspects(d):
        if ids and s["id"] not in ids: continue
        r = sweep.get(s["id"]); bf = os.path.join(bodies, f"{s['id']}.body.html")
        if not r or r.get("http") != "200" or not os.path.exists(bf): skipped.append((s["file"], f"feed not fetched (http {r.get('http') if r else 'none'})")); continue
        if r.get("removed"): skipped.append((s["file"], "post removed on Reddit; feed body empty")); continue
        full = feed_body_to_md(LN.read_text(bf)); hdr, held = split(s["file"])
        if len(full) <= len(held) * 1.02: skipped.append((s["file"], f"feed body not longer ({len(full)} vs {len(held)} chars): not a truncation")); continue
        ratio = prefix_match(held, full); cont = containment(held, full)
        forced = bool(force and s["id"] in force)
        if cont < 0.85 and not forced: skipped.append((s["file"], f"the feed text does not contain the held text (containment {cont:.3f}, prefix similarity {ratio:.3f}); a different text, left for a reading")); continue
        revised = cont < 0.98 or ratio < 0.97
        how = (f"The feed text is a later edited version: the author revised wording before the cut as well as completing the post (held 8-word shingles found in the feed {cont:.3f}; prefix similarity {ratio:.3f}); under the version rule the later, longer version is canonical and the first-posted state is kept as a version, not read as the text."
               if revised else f"The feed text completes the held text without revising it (held 8-word shingles found in the feed {cont:.3f}; prefix similarity {ratio:.3f}).")
        if forced: how = f"The feed text was verified by the orchestrator by reading: same post (title, author, opening) but a rewritten or placeholder first-posted state (held 8-word shingles found in the feed {cont:.3f}; prefix similarity {ratio:.3f}); under the version rule the later, longer version is canonical and the first-posted state is kept as a version."; revised = True
        sib = s["file"][:-3] + ".first-posted-state.md"; base = os.path.basename(s["file"]); sibb = os.path.basename(sib)
        m = re.search(r"Text verbatim from the Arctic Shift archive \(fetched (\d{4}-\d{2}-\d{2})\); (\d+) words; body held\.", hdr)
        afetch = m.group(1) if m else "2026-10-02"
        newtext = (f"Text: the full edited body as served by Reddit's RSS feed (https://www.reddit.com/r/{s['sub']}/comments/{s['id']}/.rss, fetched {r['fetched']}, HTTP 200), "
                   f"{len(full.split())} words, rendered from the feed's HTML (links kept; the author's raw markdown escapes are not reproduced). "
                   f"The Arctic Shift capture (fetched {afetch}) held only the first {len(held)} characters ({len(held.split())} words) of the first-posted state, before the author's completing edit, "
                   f"ending mid-sentence; it is kept as {sibb} for exact-wording checks against the author's raw markdown. {how} Patched {today} by the orchestrator (tools/reddit_rss_patch.py; INDEX.md, 'Patched copies').")
        newhdr = hdr.replace(m.group(0), newtext) if m else hdr.rstrip("\n") + "\n" + newtext
        patched.append(dict(file=base, id=s["id"], sub=s["sub"], held_words=len(held.split()), held_chars=len(held), full_words=len(full.split()), ratio=round(ratio, 3), cont=round(cont, 3), revised=revised, sib=sibb))
        if not do_apply: continue
        if not os.path.exists(sib):
            LN.write_text(sib, hdr.rstrip("\n") + f"\nArchive capture: the Arctic Shift text as held before the patch of {today}: the first {len(held)} characters of the first-posted state (the author completed the post by a later edit; the full text is in {base}).\n\n---\n\n" + held + "\n")
        LN.write_text(s["file"], newhdr.rstrip("\n") + "\n\n---\n\n" + full + "\n")
        if idx:
            lines = idx.split("\n")
            for i, l in enumerate(lines):
                if l.startswith("| ") and base in l:
                    cells = l.split("|"); cells[-2] = f" {len(full.split())} (full, RSS; archive prefix {len(held.split())}) "; lines[i] = "|".join(cells)
            idx = "\n".join(lines)
    if do_apply and idx and patched:
        if "## Patched copies" not in idx: idx = idx.rstrip("\n") + "\n\n## Patched copies\n\nArchive captures that ended mid-sentence at about 20,000 characters (the first-posted state, before the author's completing edit) were replaced by the full edited body from Reddit's RSS feed (tools/reddit_rss_patch.py); each archive capture is kept beside its file as `.first-posted-state.md`.\n\n| Date | File | Archive words | Full words | Held text found in feed | Prefix similarity | Revised before the cut | Archive capture kept as |\n|---|---|---|---|---|---|---|---|\n"
        for p in patched: idx = idx.rstrip("\n") + f"\n| {today} | {p['file']} | {p['held_words']} | {p['full_words']} | {p['cont']} | {p['ratio']} | {'yes' if p['revised'] else 'no'} | {p['sib']} |"
        LN.write_text(index, idx + "\n")
    print(("APPLIED" if do_apply else "DRY RUN") + f": {len(patched)} to patch, {len(skipped)} left alone")
    for p in patched: print(f"  patch  {p['file']}: {p['held_words']} -> {p['full_words']} words (held text found in feed {p['cont']}, prefix similarity {p['ratio']}{', revised before the cut' if p['revised'] else ''})")
    for f, why in skipped: print(f"  skip   {os.path.basename(f)}: {why}")
    return patched, skipped

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["scan", "fetch", "apply"]); ap.add_argument("--dir", default=__import__("packload").tool_data("reddit_rss_patch")["default_dir"])
    ap.add_argument("--out"); ap.add_argument("--bodies"); ap.add_argument("--gap", type=float, default=6); ap.add_argument("--ids"); ap.add_argument("--apply", action="store_true"); ap.add_argument("--all", action="store_true", help="fetch every held copy, not only the suspects"); ap.add_argument("--edited", action="store_true", help="fetch the suspects plus every copy the archive marks is_edited"); ap.add_argument("--skip-ids"); ap.add_argument("--force-ids", help="patch these ids although the feed text does not contain the held text (only after reading both)")
    a = ap.parse_args(); ids = set(a.ids.split(",")) if a.ids else None
    if a.cmd == "scan":
        for s in suspects(a.dir): print(f"{os.path.basename(s['file'])}\t{s['held_chars']} chars\t{s['held_words']} words\t...{s['tail'][-40:]!r}")
    elif a.cmd == "fetch": fetch(a.out or "wip/reddit-rss-patch", a.gap, ids, a.dir, "all" if a.all else ("edited" if a.edited else ""), set(a.skip_ids.split(",")) if a.skip_ids else None)
    else: apply(a.bodies, a.apply, ids, a.dir, datetime.date.today().isoformat(), set(a.force_ids.split(",")) if a.force_ids else None)
