#!/usr/bin/env python3
"""Build research/figures/graph-data.json for the database map (notes, people, eras;
cross-check edges, shared-person edges, era profiles), with its companion files (graph-claims, graph-evidence, graph-relations,
graph-edges, graph-timeline), graph-display.json (the pack's display settings for the map: subject names and colours, the time
axis, page-kind names, the typed graph's kinds) and graph-typed.json (one graph, three typed edge kinds: people to people from the
relations register, actors to polities as order of battle from the pack's actor and polity register, people to actors through the
register rows' chain hops). Reads notes.db (the register's rows and their placements from the tables actors and polity_statements,
since 2026-10-22), the pack (packs/<pack>/pack.toml [display], [actors]) and the clusters page for the clusters' names."""
import glob
import sqlite3, re, json, collections, math, os, sys
sys.path.insert(0, "tools")
from ledger import notes as LN    # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP    # project paths and the sources/ alias table
DB = "notes.db"; OUT = "research/figures/graph-data.json"
import packload   # the pack's topic vocabulary, map era boundaries, subject order (phase 1) and the map's display settings (phase 5)
DM = packload.display("map"); DT = packload.display("typed_graph")
TOPICS = [t for t, _ in packload.topics()]
ERAS = packload.eras("map")
SUBJECT_ORDER_HINT = packload.graph_order()

short = {k: v for k, v in packload.short_labels().items() if v}   # pack.toml [display.index.short_labels] (was parsed out of build_index.py)

con = sqlite3.connect(DB)
vids = con.execute("select id, file, title, channel, guest, uploaded, recorded, words from videos").fetchall()
ids = {v[0] for v in vids}
subj = collections.defaultdict(list)
for v, s in con.execute("select video, subject from video_subjects"): subj[v].append(s)
tcount = collections.defaultdict(collections.Counter)
for v, t in con.execute("select video, topic from claims"): tcount[v][t] += 1
nclaims = {v: sum(c.values()) for v, c in tcount.items()}
# era profile
eprof = collections.defaultdict(collections.Counter)
for v, sk in con.execute("select video, sort_key from timeline"):
    if not sk or not sk[:10].isdigit(): continue
    y = int(sk[:10]) - 1000000000      # sort_key = 1e9 + year, zero-padded
    for name, lo, hi in ERAS:
        if lo <= y <= hi: eprof[v][name] += 1; break

subject_size = collections.Counter(s for v in subj for s in subj[v])
_OBJ_SUBJECT = os.path.splitext(os.path.basename(packload.pack().get("objects", {}).get("register", "")))[0] or None   # the object register's page stem
def primary_subject(v):
    """the note's first-listed subject, the object register's subject page excepted (a note filed under it sits with its other subject)"""
    ss = [s for s in subj.get(v, []) if s != _OBJ_SUBJECT]
    return ss[0] if ss else "unfiled"      # the note's first-listed subject

def vec(v):
    c = tcount.get(v, collections.Counter()); n = sum(c.values()) or 1
    return [c.get(t, 0) / n for t in TOPICS]
def cos(a, b):
    na = math.sqrt(sum(x*x for x in a)) or 1; nb = math.sqrt(sum(x*x for x in b)) or 1
    return sum(x*y for x, y in zip(a, b)) / (na*nb)

# search text per note: title, guest, channel, tags, people named, works, object-watch objects (lower-cased, deduplicated)
sblob = collections.defaultdict(set); tagsof = collections.defaultdict(list)
for v, t in con.execute("select video, tag from tags"):
    sblob[v].add((t or "").lower())
    if t and len(tagsof[v]) < 160: tagsof[v].append(t.strip())
for v, name in con.execute("select video, name from mentions"): sblob[v].add((name or "").lower())
for v, t, au in con.execute("select video, title, author from works"): sblob[v].add(((t or "") + " " + (au or "")).lower())
for v, o in con.execute(f"select video, object from {packload.name('table.object_watch')}"): sblob[v].add((o or "").lower()[:200])
def yt_id(url):
    m = re.search(r"(?:v=|youtu\.be/|/live/|/shorts/)([A-Za-z0-9_-]{11})", url or ""); return m.group(1) if m else ""
def secs(t):
    m = re.match(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", t or "")
    if not m: return None
    h, mi, se = m.groups(); return (int(h)*3600 + int(mi)*60 + int(se)) if se is not None else int(h)*60 + int(mi)
urls = {v[0]: v[7] for v in con.execute("select id, file, title, channel, guest, uploaded, recorded, url from videos")}
claims_out = collections.defaultdict(list)   # every note: [seconds or null, claim text, speaker, row number, time as written (page/section for books)]
for v, n, t, sp, topic, claim, note in con.execute("select video, n, time, speaker, topic, claim, note from claims"):
    sc = secs(t) if yt_id(urls.get(v, "")) else None
    corr = re.search(r"[Cc]orrected (\d{4}-\d{2}-\d{2})", note or "")      # a claim rewritten after a cross-check: the dispute that cited it is settled
    claims_out[v].append([sc, re.sub(r"\s+", " ", claim or "")[:420], (sp or "")[:24], str(n), re.sub(r"\s+", " ", t or "")[:40], corr.group(1) if corr else "", TOPICS.index(topic) if topic in TOPICS else -1])   # [6]: the claim's topic, an index into meta.topics (searchable on the map, owner 2026-10-03)
for v in claims_out: claims_out[v].sort(key=lambda r: (r[0] if r[0] is not None else 10**9, r[3]))
# graph-claims.json is written after the people section, which adds who speaks each claim and whom it names
# held source files per book note: links to books/sources/*.txt|pdf|png|jpg (text to display, pdf or image to show)
src_re = LN.SOURCE_LINK_RE   # form L6
# Standing rule (owner, 2026-10-02): third-party texts held for research (books/sources/reddit/, books/sources/web/) are never
# served by the published map; the map links to the original copy online instead. Each such source carries external=True and
# orig=<the original URL>, taken from the file's provenance header (or derived from a Reddit post id in the file name).
THIRD_PARTY_DIRS = tuple(DM["third_party_dirs"])   # pack.toml [display.map] third_party_dirs
_FORUM_DIRS = tuple(d for d in THIRD_PARTY_DIRS if "reddit" in d)   # the forum adapter's folders: post ids in the file names
def is_third_party(rel): return rel.startswith(THIRD_PARTY_DIRS)
def original_url(rel):
    name = os.path.basename(rel)
    try: head = LN.read_head(LP.resolve(rel), 3000, errors="replace")
    except OSError: head = ""
    if "posting-history" in name:
        m = re.search(r"u/([A-Za-z0-9_-]+)", head); user = m.group(1) if m else DM["posting_history_user"]
        return f"https://www.reddit.com/user/{user}/submitted/" if user else ""
    if _FORUM_DIRS and rel.startswith(_FORUM_DIRS):
        m = re.search(r"(?:^|-)([0-9a-z]{7})(?=[-.])", name)          # the post id in the file name (comments and RSS files included)
        if m:
            pid = m.group(1)
            for u in re.findall(r"https://www\.reddit\.com/r/[^\s)\]]+?/comments/" + pid + r"/[^\s)\]]*", head):
                if ".rss" not in u: return u.rstrip(".,")
            return f"https://www.reddit.com/comments/{pid}/"
    bad = ("arctic-shift", "archive.org", "/api/", ".rss", "substackcdn")
    for u in re.findall(r"https?://[^\s)\]\"'<>;]+", head):
        u = u.rstrip(".,")
        if not any(b in u for b in bad) and "/s/" not in u: return u
    return ""
# Cited excerpts (owner, 2026-10-02): for a third-party source the published map shows, beside the link to the original, the one
# to three sentences of the source that the note's own claims rows quote most (a citation, never a sample): quoted spans of five or
# more words in the note's claims are matched in the held text, the source sentences holding the most matches are kept, in source
# order, each cut to 60 words.
def _norm_q(t): return re.sub(r"\s+", " ", t.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")).strip().lower()
def cited_excerpt(note_id, rel, max_sent=3, max_words=60):
    try: txt = LN.read_text(LP.resolve(rel), errors="replace")
    except OSError: return []
    body = txt.split("\n---\n", 1)[1] if "\n---\n" in txt[:6000] else txt
    if "PAYWALL" in txt[:3000].upper(): max_sent = 1                                   # paywalled sources: one sentence at most
    body = re.sub(r"<[^>]+>", " ", body)                                                  # RSS and HTML captures
    raw = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip() and not re.match(r"\s*(#|URL:|Provenance|Status:|Standfirst|Work W|\| )", p) and "fetched 20" not in p and "Arctic Shift" not in p]
    paras = []
    for p in raw:                                                                         # rejoin hard-wrapped text: a paragraph that does not end a sentence continues
        if paras and re.search(r"[a-z]-$", paras[-1]): paras[-1] = paras[-1][:-1] + p      # a word hyphenated across the wrap
        elif paras and not re.search(r"[.!?:\"\u201d')\]]\s*$", paras[-1]): paras[-1] += " " + p
        else: paras.append(p)
    def split_sents(par):
        out, start = [], 0
        for m in re.finditer(r"[.!?][\"\u201d')\]]?\s+(?=[A-Z\"\u201c(\[])", par):
            prev = re.search(r"(\S+)$", par[start:m.start() + 1]); tok = prev.group(1) if prev else ""
            if re.fullmatch(r"(?:[A-Z]\.){1,3}|(?:Mr|Mrs|Ms|Dr|St|No|Vol|pp?|ed|cf|vs|U\.S|Jr|Sr|Gen|Col|Lt|Sgt|Capt|Maj|Rep|Sen)\.", tok): continue   # initials and abbreviations
            out.append(par[start:m.end()].strip()); start = m.end()
        out.append(par[start:].strip()); return out
    sents = [x for par in paras for x in split_sents(par.replace("\n", " ")) if len(x.split()) >= 5 and "\ufffd" not in x]   # a sentence with a replacement character is not a quotable excerpt
    nsents = [_norm_q(x) for x in sents]
    quotes = []
    for (claim,) in con.execute("select claim from claims where video=?", (note_id,)):
        for q in re.findall(r"[\"\u201c]([^\"\u201c\u201d]{20,400})[\"\u201d]", claim or ""):
            q = _norm_q(q.strip(" .,;:…"))
            if len(q.split()) >= 5: quotes.append(q)
    score = {}
    for q in quotes:
        for i, ns in enumerate(nsents):
            if q in ns or (len(q) > 60 and q[:60] in ns): score[i] = score.get(i, 0) + 1; break
    top = sorted(sorted(score, key=lambda i: -score[i])[:max_sent])
    out = []
    for i in top:
        w = re.sub(r"\*{1,3}|`|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", sents[i]).replace("\n", " ").split()   # markdown emphasis and links to plain text
        out.append(" ".join(w[:max_words]) + (" …" if len(w) > max_words else ""))
    return out
def sources_of(f):
    try: txt = LN.read_text(f)
    except OSError: return []
    seen, out = set(), []
    cands = [("books/" + m.group(1), m.group(2).lower()) for m in src_re.finditer(txt)]
    for m in re.finditer(r"`([A-Za-z0-9][^`\s]+?\.(txt|md|pdf|png|jpg))`", txt):          # backticked file names resolved under books/sources
        name, ext = m.group(1), m.group(2).lower()
        for base in DM["held_lookup_dirs"]:   # pack.toml [display.map] held_lookup_dirs
            if LP.exists(base + name): cands.append((base + name, ext)); break
    for rel, ext in cands:
        if rel in seen or not LP.exists(rel): continue   # a held path resolves through the sources/ alias table
        seen.add(rel); d = dict(path=rel, kind="pdf" if ext == "pdf" else "text" if ext in ("txt", "md") else "image", bytes=os.path.getsize(LP.resolve(rel)))
        if is_third_party(rel):
            d["external"] = True; d["orig"] = original_url(rel)
            ex = cited_excerpt(os.path.splitext(os.path.basename(f))[0], rel) if ext in ("txt", "md", "html", "htm") else []   # a PDF's bytes are not text: no excerpt (2026-10-09: one report's PDF put 1,164 replacement characters into the data file)
            if ex: d["excerpt"] = ex
        out.append(d)
    out.sort(key=lambda d: {"pdf": 0, "image": 1, "text": 2}[d["kind"]])
    return out
CHANNEL_SOURCE = [tuple(x) for x in DM["channel_sources"]]   # (channel substring, source name): pack.toml [display.map] channel_sources
BOOK_SOURCE = [tuple(x) for x in DM["book_sources"]]         # (note stem prefix, source name): [display.map] book_sources
# Display names for the map's Sources list (owner, 2026-10-02): a short name, a muted detail line (no parentheses in names), and the kind of source it is.
SOURCE_GROUPS = list(DM["source_groups"])
SOURCE_META = {k: tuple(v) for k, v in DM["source_meta"].items()}   # [display.map.source_meta]
def source_display(raw, kind):
    if raw in SOURCE_META: return SOURCE_META[raw]
    return (raw, "", DM["default_book_group"] if kind == "book" else DM["default_video_group"])
def source_of(vid, f, channel):
    if f.startswith("books/"):
        for pre, name in BOOK_SOURCE:
            if vid.startswith(pre): return name
        return DM["other_books"]
    c = (channel or "").lower()
    for key, name in CHANNEL_SOURCE:
        if key in c: return name
    return (channel or DM["unknown_channel"]).split("(")[0].strip()[:40]
nodes = []
for (vid, f, title, channel, guest, up, rec, words) in vids:
    kind = "book" if f.startswith("books/") else "video"
    nodes.append(dict(id=vid, file=f, yt=yt_id(urls.get(vid, "")), sources=sources_of(f) if kind == "book" else [], tags=tagsof.get(vid, []), source=source_display(source_of(vid, f, channel), kind)[0], source_detail=source_display(source_of(vid, f, channel), kind)[1], source_group=source_display(source_of(vid, f, channel), kind)[2], label=short.get(os.path.basename(f)) or (title[:40] if title else vid.replace("-"," ").title()[:40]), title=title or "", kind=kind,
                      subject=primary_subject(vid), subjects=subj.get(vid, []), uploaded=(up or "")[:10], claims=nclaims.get(vid, 0),
                      words=words or 0, topics=dict(tcount.get(vid, {})), eras=dict(eprof.get(vid, {})), vec=vec(vid),
                      search=" | ".join(sorted(x for x in sblob.get(vid, set()) if x)) + " | " + " ".join(x.lower() for x in [title or "", guest or "", channel or ""])))
# order groups by centroid similarity (greedy chain from the largest group), then nodes within a group by greedy nearest-neighbour seriation
groups = collections.defaultdict(list)
for n in nodes: groups[n["subject"]].append(n)
cent = {g: [sum(n["vec"][i] for n in ns)/len(ns) for i in range(len(TOPICS))] for g, ns in groups.items()}
order = [max(groups, key=lambda g: len(groups[g]))]
while len(order) < len(groups):
    last = order[-1]; nxt = max((g for g in groups if g not in order), key=lambda g: cos(cent[last], cent[g])); order.append(nxt)
def seriate(ns):
    if len(ns) <= 2: return ns
    rem = ns[:]; cur = max(rem, key=lambda n: n["claims"]); out = [cur]; rem.remove(cur)
    while rem:
        cur = max(rem, key=lambda n: cos(out[-1]["vec"], n["vec"])); out.append(cur); rem.remove(cur)
    return out
ordered = []
for g in order:
    for n in seriate(groups[g]): ordered.append(n)
for i, n in enumerate(ordered): n["order"] = i; n["dominant_topic"] = max(TOPICS, key=lambda t: n["topics"].get(t, 0)) if n["topics"] else "other"
# cross-check edges
link_re = LN.ANY_NOTE_LINK_RE   # form L11
edges = collections.defaultdict(lambda: collections.Counter()); erows = collections.defaultdict(list)
edir = collections.defaultdict(lambda: collections.Counter())   # (a, b, recorder) -> kinds: who recorded each link, for the map's from/to source filter (owner, 2026-10-02)
def clean(x): return re.sub(r"\s+", " ", (x or "")).strip()
for v, n, kind, this, elsewhere, verdict, note, settled in con.execute("select video, n, kind, this_note, elsewhere, verdict, note, settled from cross_checks"):
    if settled: continue      # settled rows (schema 10): the disagreement no longer stands, so they are not links (owner, 2026-10-01)
    for m3 in link_re.finditer(elsewhere or ""):
        t = m3.group(1)
        if t in ids and t != v:
            a, b = sorted([v, t]); edges[(a, b)][kind] += 1; edir[(a, b, v)][kind] += 1
            if len(erows[(a, b)]) < 400: erows[(a, b)].append(dict(f=v, n=n, k=kind, t=clean(this)[:420], e=clean(elsewhere)[:240], v=clean(verdict)[:40], o=clean(note)[:360]))
# note-to-note citations (2026-10-02): every relative link from one note's text to another note (videos/ or books/) is a "cites"
# edge kind, so a document that cites its sources (the Reddit post and its intaken sources) shows as a link in the notes circle;
# off by default in the page's legend because cross-check rows also carry links.
cite_re = LN.NOTE_CITE_LINK_RE   # form L12
for vid, f in [(v[0], v[1]) for v in vids]:
    try: txt = LN.read_text(f)
    except OSError: continue
    cnt = collections.Counter(t for t in cite_re.findall(txt) if t in ids and t != vid)
    for t, n in cnt.items():
        a, b = sorted([vid, t]); edges[(a, b)]["cites"] += n; edir[(a, b, vid)]["cites"] += n
        if len(erows[(a, b)]) < 12: erows[(a, b)].append(dict(f=vid, n="", k="cites", t=f"{short.get(f.split('/')[-1], vid)} links to {short.get(t + '.md', t)} {n} time{'s' if n != 1 else ''} (Works, Connections, cross-checks or prose)", e=t, v="", o=""))
# three further link kinds (owner, 2026-10-05), each from work the ledger already does:
#   divergence: tools/divergences.py items (contradicting cross-checks, timeline rows that contradict or drift, divergence leads), each with its class by its markers
#   echo: tools/echoes.py, the same wording or the same rare details in mouths with no acknowledged link (unacknowledged) or sharing a channel; from the earliest title to each later one
#   declined: research/declined-answered-elsewhere.md, what one speaker withheld and another title supplied; recorded from the supplying title
_fig = os.path.dirname(OUT)
def _xrow(a_, b_, rec, kind, row):
    a, b = sorted([a_, b_]); edges[(a, b)][kind] += 1; edir[(a, b, rec)][kind] += 1
    if len(erows[(a, b)]) < 400: erows[(a, b)].append(row)
_xn = collections.Counter()
try:
    for it in json.load(open(os.path.join(_fig, "divergences.json"), encoding="utf-8")):
        v = it["video"]
        if v not in ids: continue
        for t in dict.fromkeys(it["against"]):
            if t in ids and t != v:
                _xrow(v, t, v, "divergence", dict(f=v, n=f'{it["src"]} {it["n"]}', k="divergence", t=clean(it["text"])[:170], e=clean(it["detail"])[:200], v=it["cls"], o=f'party: {it["party"]}; {it["kind"]}' + ("; an agency or official" if it.get("agency") else ""))); _xn["divergence"] += 1
except (OSError, ValueError) as e: print("no divergences.json (run tools/divergences.py):", e)
try:
    for it in json.load(open(os.path.join(_fig, "echoes.json"), encoding="utf-8")):
        if it["kind"] == "acknowledged": continue
        vs = [v for v in it["vids"] if v in ids]; first = it["first"] if it["first"] in vs else (vs[0] if vs else None)
        for t in vs:
            if t != first:
                _xrow(first, t, t, "echo", dict(f=t, n="", k="echo", t=("the same wording: \"" + it["text"] + "\"" if it["what"] == "wording" else "the same details: " + it["text"])[:420], e=f'first held in [{short.get(first + ".md", first)}]({first}.md); in the mouths of ' + ", ".join(it["speakers"][:8]), v=it["kind"], o=clean(it["why"])[:300])); _xn["echo"] += 1
except (OSError, ValueError) as e: print("no echoes.json (run tools/echoes.py):", e)
try:
    _sec = ""
    for line in LN.iter_lines(os.path.join(_fig, "..", "declined-answered-elsewhere.md")):
        if line.startswith("## "): _sec = line[3:].strip(); continue
        if not line.startswith("|") or not _sec.lower().startswith("declined by") or _sec.lower().startswith("declined everywhere"): continue
        c = LN.split_row(line)
        if len(c) < 5 or not re.fullmatch(r"\d+[a-z]?", c[0]): continue
        dec = [t for t in link_re.findall(c[2]) if t in ids]; sup = [t for t in link_re.findall(c[3]) if t in ids]
        for d_ in dict.fromkeys(dec):
            for s_ in dict.fromkeys(sup):
                if d_ != s_:
                    _xrow(s_, d_, s_, "declined", dict(f=s_, n=f"sweep {c[0]}", k="declined", t=clean(c[3])[:420], e=("withheld: " + clean(c[1]) + ". Declined: " + clean(c[2]))[:420], v=clean(c[5] if "monologue" in _sec else c[4])[:40], o=(_sec + ". " + clean(c[-1]))[:360])); _xn["declined"] += 1
except OSError as e: print("no declined-answered-elsewhere.md:", e)
print("extra link kinds:", dict(_xn))
edge_list = [dict(source=a, target=b, kinds=dict(c), ks=dict(edir[(a, b, a)]), kt=dict(edir[(a, b, b)]), weight=sum(c.values()), rows=erows[(a, b)]) for (a, b), c in edges.items()]   # ks: recorded in the source note (source -> target); kt: recorded in the target note
# people (owner, 2026-10-03): everyone named in two or more titles or credited with claims; for each, the claims they speak and the
# cross-checks those claims take part in, split by the claim's attribution (firsthand / secondhand / own reasoning or host), and who talks about whom.
_al = {}
try:
    for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "name_aliases.json"), encoding="utf-8")).items():
        if k.startswith("_") or not isinstance(v, list): continue
        _al[k.lower()] = k
        for x in v: _al[str(x).lower()] = k
except (OSError, ValueError): pass
def canon(n): n = re.sub(r"\s+", " ", n or "").strip(); return _al.get(n.lower(), n)
def _strip_paren(x):
    prev = None
    while prev != x: prev = x; x = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", "", x)
    return x
_TITLE = r"(?:Rear Adm\.?|Vice Adm\.?|Adm\.?|Lt\.? Col\.?|Lt\.? Gen\.?|Maj\.? Gen\.?|Brig\.? Gen\.?|Col\.?|Gen\.?|Maj\.?|Capt\.?|Lt\.?|Cmdr\.?|Sgt\.?|Dr\.?|Prof\.?|Rep\.?|Reps\.?|Sen\.?|Sir|Mr\.?|Mrs\.?|Ms\.?|Chairwoman|Chairman|Secretary|Senator|Representative|Congressman|Congresswoman|President|Director)"
def _clean_name(c):
    c = re.sub(r"\s+", " ", c).strip(" .;:*\"'“”")
    while True:
        c2 = re.sub(r"^" + _TITLE + r"\s+", "", c)
        if c2 == c: break
        c = c2
    return c
def _names_in(field):
    out = set()
    for part in re.split(r";|,| and | with |\bvs?\.?\b", _strip_paren(field or "")):
        c = _clean_name(part); toks = c.split()
        if not (1 <= len(toks) <= 4) or len(c) < 3 or re.search(r"\d", c) and not c.startswith("u/"): continue
        if c.lower() in ("none", "unknown", "us navy", "us army", "us air force"): continue
        if all(re.match(r"[A-Z]|u/", t) or t.lower() in ("de", "von", "van", "al", "la", "du", "bin", "st.") for t in toks): out.add(canon(c))
    return out
pnames = collections.defaultdict(set); pmeta = collections.defaultdict(set); phost = collections.defaultdict(set); pm = collections.defaultdict(set); roles = {}
_vars = collections.defaultdict(set)
for _k, _c in _al.items(): _vars[_c].add(_k)
for v, name, role in con.execute("select video, name, role from mentions"):
    if name and v in ids:
        c = canon(name); pnames[v].add(c); pm[c].add(v); roles.setdefault((c, v), re.sub(r"\s+", " ", role or "")[:90])
for v, host, guest, speakers, channel in con.execute("select id, host, guest, speakers, channel from videos"):
    if v in ids: phost[v] = _names_in(host) | _names_in((guest or "").split(",")[0]) | {x for x in _names_in(guest) if x in pnames[v]}; pmeta[v] = phost[v] | _names_in(speakers) | _names_in(channel)   # phost: the host and guests, the pool for unsure attributions
def _surname(n):
    t = [x for x in _strip_paren(n).replace(",", " ").split() if not re.fullmatch(r"(Jr\.?|Sr\.?|II|III|PhD|Dr\.?|Col\.?|Gen\.?|Rep\.?|Sen\.?)", x)]
    return t[-1] if t else n
_rc = {}
def resolve(v, s):
    key = (v, s)
    if key in _rc: return _rc[key]
    s0 = _clean_name(_strip_paren(s or "")); out = None
    if s0:
        low = s0.lower(); c0 = canon(s0)
        for pool in (pmeta[v], pnames[v]):                      # the title's host, guest and speakers first, then everyone it names
            forms = {n: {n.lower()} | _vars.get(n, set()) for n in pool}
            hit = [n for n in pool if n == c0 or low in forms[n]] or [n for n in pool if any(_surname(f).lower() == low for f in forms[n])] or [n for n in pool if any(low in [t.strip(".,") for t in f.split()] for f in forms[n])]
            hit = sorted(set(hit), key=lambda h: (len(h), h))   # ties of length by name, so the pick never follows hash order
            if len(hit) > 1 and all(set(hit[0].lower().split()) <= set(h.lower().split()) for h in hit): hit = hit[:1]   # "A. Name" and "Rear Adm. A. Name": one person
            if len(hit) == 1: out = hit[0]; break
    _rc[key] = out; return out
_UNKNOWN = re.compile(r"unidentif|unknown|unattrib|unnamed|unclear|uncertain|not identified|^(speaker|voice|man|woman)\b|^\??$", re.I)
BUCKET = {"firsthand": 0, "hearsay": 1, "read": 1, "program-record": 1, "clip": 1, "channelled": 1}   # everything else (inference, host, blank) is 2: the speaker's own reasoning or questions
p_claims = collections.defaultdict(lambda: [0, 0, 0]); p_cr = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
who = {}; talk = collections.defaultdict(lambda: [0, 0, 0]); talk_refs = collections.defaultdict(list); _pat = {}
pu_claims = collections.defaultdict(lambda: [0, 0, 0]); pu_cr = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0])); who_u = {}; talk_u = collections.defaultdict(lambda: [0, 0, 0]); unsure_claims = 0
def _patterns(v):
    if v not in _pat:
        pool = pnames[v] | pmeta[v]; sur = collections.Counter(_surname(n) for n in pool); pats = []
        for n in sorted(pool):   # sorted: the order of the people a claim names follows the patterns
            alts = [re.escape(n)]; sn = _surname(n)
            if len(sn) >= 4 and sur[sn] == 1 and sn != n: alts.append(re.escape(sn))
            pats.append((n, re.compile(r"(?<![A-Za-z])(?:" + "|".join(alts) + r")(?![A-Za-z])")))
        _pat[v] = pats
    return _pat[v]
resolved = total = 0
cl_subj = collections.defaultdict(list); spk_t = collections.defaultdict(lambda: [0] * 6); talk_t = collections.defaultdict(lambda: [0] * 6)   # per title: [firsthand, secondhand, own, unsure firsthand, unsure secondhand, unsure own]
for v, n, speaker, claim, sc in con.execute("select video, n, speaker, claim, source_class from claims"):
    if v not in ids: continue
    total += 1; sp = resolve(v, speaker)
    if not sp:
        cands = sorted(phost[v]) if _UNKNOWN.search(_strip_paren(speaker or "").strip()) else []
        if cands:
            b = BUCKET.get((sc or "").strip(), 2); who_u[(v, str(n))] = (cands, b); unsure_claims += 1
            for c in cands:
                pu_claims[c][b] += 1; pm[c].add(v); spk_t[(c, v)][3 + b] += 1
                for q, rx in _patterns(v):
                    if q != c and q not in cands and rx.search(claim or ""):
                        talk_u[(c, q)][b] += 1; talk_t[(c, q, v)][3 + b] += 1
                        if q not in cl_subj[(v, str(n))]: cl_subj[(v, str(n))].append(q)
                        if len(talk_refs[(c, q)]) < 4: talk_refs[(c, q)].append([v, str(n), 1])
        continue
    resolved += 1; b = BUCKET.get((sc or "").strip(), 2); p_claims[sp][b] += 1; who[(v, str(n))] = (sp, b); pm[sp].add(v); spk_t[(sp, v)][b] += 1
    for q, rx in _patterns(v):
        if q != sp and rx.search(claim or ""):
            talk[(sp, q)][b] += 1; talk_t[(sp, q, v)][b] += 1; cl_subj[(v, str(n))].append(q)
            if len(talk_refs[(sp, q)]) < 4: talk_refs[(sp, q)].append([v, str(n)])
def _nums(text, word):
    out = []
    for m in re.finditer(word + r"\s+(\d+(?:\s*(?:,|and|to)\s*\d+)*)", text or "", re.I):
        seg = m.group(1); to = re.fullmatch(r"(\d+)\s*to\s*(\d+)", seg)
        if to: out += [str(k) for k in range(int(to.group(1)), min(int(to.group(2)), int(to.group(1)) + 40) + 1)]
        else: out += [x for x in re.split(r"\s*(?:,|and)\s*", seg) if x.isdigit()]
    return out
pp_x = collections.defaultdict(lambda: collections.Counter()); pp_refs = collections.defaultdict(list)   # who contradicts, corroborates, extends... whom: the speaker of this note's rows -> the speaker of the claim checked
for v, xn, kind, this, elsewhere, settled in con.execute("select video, n, kind, this_note, elsewhere, settled from cross_checks"):
    if settled or v not in ids: continue
    cred = {who[(v, k)] for k in _nums(this, r"rows?") if (v, k) in who}
    _mine = {x[0] for x in cred}
    ms = list(link_re.finditer(elsewhere or ""))
    for a, m in enumerate(ms):
        t = m.group(1); tail = (elsewhere or "")[m.end(): ms[a + 1].start() if a + 1 < len(ms) else None]
        _theirs = {who[(t, k)][0] for k in _nums(tail, r"claims?") if (t, k) in who}
        for _a in sorted(_mine):   # sorted (c): the order of the pairs in px follows these loops
            for _b in sorted(_theirs):
                if _a != _b:
                    pp_x[(_a, _b)][kind] += 1
                    if len(pp_refs[(_a, _b)]) < 400: pp_refs[(_a, _b)].append((v, t, str(xn), kind))   # every row, so the map can show each check in full (owner, 2026-10-05); was 8
        cred |= {who[(t, k)] for k in _nums(tail, r"claims?") if (t, k) in who}
    for person, b in cred: p_cr[person][kind][b] += 1
    ucred = set()
    for k in _nums(this, r"rows?"):
        if (v, k) in who_u: ucred |= {(c, who_u[(v, k)][1]) for c in who_u[(v, k)][0]}
    for a, m in enumerate(ms):
        t = m.group(1); tail = (elsewhere or "")[m.end(): ms[a + 1].start() if a + 1 < len(ms) else None]
        for k in _nums(tail, r"claims?"):
            if (t, k) in who_u: ucred |= {(c, who_u[(t, k)][1]) for c in who_u[(t, k)][0]}
    for person, b in ucred - cred: pu_cr[person][kind][b] += 1
keep = sorted([p for p in pm if len(pm[p]) >= 2 or p in p_claims or p in pu_claims], key=lambda p: (-len(pm[p]), p)); pidx = {p: i for i, p in enumerate(keep)}; nidx = {n["id"]: i for i, n in enumerate(ordered)}
people = [dict(id="p:" + p, label=p, notes=sorted(pm[p]), n=len(pm[p]), roles={v: roles[(p, v)] for v in sorted(pm[p]) if roles.get((p, v))}, cl=p_claims.get(p, [0, 0, 0]), cr={k: c for k, c in p_cr.get(p, {}).items()}, **({'clu': pu_claims[p], 'cru': {k: c for k, c in pu_cr.get(p, {}).items()}} if p in pu_claims else {})) for p in keep]   # clu / cru: unsure attributions (speaker not identified; credited to every host and guest)
# generation (owner, 2026-10-07, for the relationship network): by = a recorded birth year (a timeline row that says the person was born, year from its sort key);
# fy = the earliest dated year the ledger ties the person to (a relations-register When cell, or a timeline event that names them), recording-era rows (2023 on) excluded so a 2026 interview does not date a life
_tl_all = [(int(sk[:10]) - 1000000000, ev, sb or "", v, n) for sk, ev, sb, v, n in con.execute("select sort_key, event, speaker_basis, video, n from timeline") if sk and sk[:10].isdigit() and int(sk[:10]) - 1000000000 < 3000]
_born_re = re.compile(r"\b(?:is |was )?born\b|\bbirth of\b", re.I)
_yr_re = re.compile(r"(?<!\d)(-?\d{3,4})(?!\d)")
_cand = collections.defaultdict(list); _by = {}; _aev = collections.defaultdict(list)   # aev: the dated events the person is reported involved in, [title index, row, year]
_last = lambda p: p.split()[-1] if p.split() else p
_sur = collections.Counter(_last(p) for p in keep)   # a birth row that says only "Bosley is born" credits the one person of that surname
_surre = {p: re.compile(r"\b" + re.escape(_last(p)) + r"\b") for p in keep if len(p.split()) >= 2 and len(_last(p)) >= 5 and _sur[_last(p)] == 1 and _last(p)[:1].isupper()}
for y, ev, sb, _v, _n in _tl_all:
    if _born_re.search(ev):
        for p in keep:
            if p not in _by and ((p in ev and re.search(re.escape(p) + r"(?:,| \([^)]*\))? (?:is |was )?born\b", ev)) or (len(_last(p)) >= 5 and _sur[_last(p)] == 1 and re.search(r"\b" + re.escape(_last(p)) + r" (?:is |was )?born\b", ev))): _by[p] = y   # the name must be the one said to be born, right before the verb: "Bosley born 1963", not "Bosley's father born 1936"
    _life = bool(_born_re.search(ev)) or bool(re.search(r"\b(dies|died|death of|is killed|was killed)\b", ev, re.I))   # a birth or death row is not an involvement
    if _life or y > 2026: continue
    for p in keep:
        # named by full name, or by a surname no one else on the map carries (most rows give the surname alone) (owner, 2026-10-07)
        if p in ev or (_surre.get(p) and _surre[p].search(ev)):
            # the person must be a party to the event, not its teller: a 2023 witness telling of 1933 does not get 1933 as an action; events up to 2026 count (a hearing, an interview given)
            if p not in sb and _last(p) not in sb: _cand[p].append(y); _aev[p].append((_v, _n, y))
for a, b, when in con.execute("select a_canon, b_canon, when_ from relations"):
    ys = [int(x) for x in _yr_re.findall(when or "") if -1000 <= int(x) < 2023]
    if not ys: continue
    for p in (a, b):
        if p in pidx: _cand[p].append(min(ys))
_fy = {}; _ays = {}
for p, ys in _cand.items():
    hi = max(ys); win = sorted({y for y in ys if y >= hi - 110})   # one life: ties more than 110 years before the latest are someone else's event that names them
    _fy[p] = min(win); _ays[p] = win[:80]   # ays: the years the ledger reports the person involved in something (owner, 2026-10-07), for the dates register's check and the panel's range
# the people dates register (research/people-dates.md, tools/people_dates.py: Wikidata, checked against the ledger's roles) comes first; a timeline "born" row second
_reg = {}
_regp = os.path.join(os.path.dirname(DB) or ".", "research/people-dates.md")
if os.path.exists(_regp):
    for l in LN.iter_lines(_regp):
        c = LN.split_row(l)
        if len(c) == 8 and c[5] in ("high", "medium", "owner") and (c[1] or c[2]):
            yr = lambda s: None if not s else (int(s.lstrip("~")), s.startswith("~"))
            _reg[canon(c[0])] = dict(born=yr(c[1]), died=yr(c[2]), src="owner" if c[5] == "owner" else "wikidata")
for p, d in zip(keep, people):
    r = _reg.get(p)
    if r and r["born"]: d["by"], d["bs"] = r["born"][0], r["src"]; d["bya"] = r["born"][1]
    elif p in _by: d["by"], d["bs"] = _by[p], "timeline"
    if r and r["died"]: d["bd"] = r["died"][0]
    if p in _fy: d["fy"] = _fy[p]; d["ays"] = _ays[p]; lo = max(_cand[p]) - 110; d["aev"] = sorted([[nidx[v], n, y] for v, n, y in _aev[p] if v in nidx and y >= lo], key=lambda r: r[2])[:120]
print(f"people dates register: {len(_reg)} usable rows; {sum(1 for d in people if d.get('bs')=='wikidata' or d.get('bs')=='owner')} people dated from it")
print(f"generation: {len(_by)} recorded birth years, {len(_fy)} people with an earliest dated tie")
# who talks about whom: [speaker index, subject index, firsthand, secondhand, own reasoning, [[title index, claim row, 1 if unsure], ...], unsure firsthand, unsure secondhand, unsure own]
_pairs = sorted(set(talk) | set(talk_u))   # sorted (a): people_talk in a fixed order
_ub = collections.defaultdict(list)
for (v, r), (cands, b) in who_u.items(): _ub[v].append(r)
# unsure attributions: [title index, [person indices credited], [claim rows whose speaker the transcript does not identify]]
people_unsure = [[nidx[v], [pidx[c] for c in sorted(phost[v]) if c in pidx], sorted(rs, key=lambda x: int(x) if x.isdigit() else 0)] for v, rs in _ub.items() if v in nidx]
_tt = collections.defaultdict(list)
for (a, b, v), c in talk_t.items():
    if v in nidx: _tt[(a, b)].append([nidx[v], *c])
# index 9: every title the pair occurs in, [title index, firsthand, secondhand, own, unsure firsthand, unsure secondhand, unsure own], so the map can filter titles by who talks about whom
people_talk = [[pidx[a], pidx[b], *talk.get((a, b), [0, 0, 0]), [[nidx[x[0]], *x[1:]] for x in talk_refs[(a, b)] if x[0] in nidx], *talk_u.get((a, b), [0, 0, 0]), _tt.get((a, b), [])] for (a, b) in _pairs if a in pidx and b in pidx]
# who speaks in which title: [person index, title index, firsthand, secondhand, own, unsure firsthand, unsure secondhand, unsure own]
people_speak = [[pidx[a], nidx[v], *c] for (a, v), c in spk_t.items() if a in pidx and v in nidx]
top_people = keep[:80]; shared = collections.Counter()
for p in top_people:
    vs = sorted(pm[p])
    for i in range(len(vs)):
        for j in range(i+1, len(vs)): shared[(vs[i], vs[j])] += 1
people_edges = [dict(source=a, target=b, weight=w) for (a, b), w in shared.items() if w >= 3]
print(f"people: {len(people)} (speakers credited: {len(p_claims)}); claims with a named speaker: {resolved} of {total}; unsure (credited to hosts and guests): {unsure_claims}; talks-about pairs: {len(people_talk)}")
eras = [dict(id="e:"+name, label=name) for name, _, _ in ERAS]
# research pages: derived objects that cite notes (pages table, 2026-10-01); never sources
pages = []
for pid, f, title, kind, gen, words, lo in con.execute("select id, file, title, kind, generated, words, links_out from pages"):
    t = re.sub(r"^(" + "|".join(map(re.escape, DM["page_title_prefixes"])) + r"):\s*", "", title or pid)
    pages.append(dict(id="r:"+pid, stem=pid, file=f, label=t[:48], title=title or pid, kind=kind, generated=bool(gen), words=words or 0, links_out=lo or 0))
page_ids = {p["stem"] for p in pages}
page_note = [dict(source="r:"+pg, target=t, weight=c) for pg, t, tk, c in con.execute("select page, target, target_kind, count from page_links") if tk in ("videos", "books") and t in ids]
page_page = [dict(source="r:"+pg, target="r:"+t, weight=c) for pg, t, tk, c in con.execute("select page, target, target_kind, count from page_links") if tk == "research" and t in page_ids and t != pg]
xc_page = collections.defaultdict(collections.Counter); xrows = collections.defaultdict(list)
rlink = LN.RESEARCH_LINK_RE   # form L13
for v, n, kind, this, elsewhere, verdict, note, settled in con.execute("select video, n, kind, this_note, elsewhere, verdict, note, settled from cross_checks"):
    if settled: continue
    for m4 in rlink.finditer(elsewhere or ""):
        if m4.group(1) in page_ids:
            key = (v, "r:"+m4.group(1)); xc_page[key][kind] += 1
            if len(xrows[key]) < 400: xrows[key].append(dict(f=v, n=n, k=kind, t=clean(this)[:420], e=clean(elsewhere)[:240], v=clean(verdict)[:40], o=clean(note)[:360]))
note_page_xc = [dict(source=a, target=b, kinds=dict(c), weight=sum(c.values()), rows=xrows[(a, b)]) for (a, b), c in xc_page.items()]
# dated timeline rows (schema section 11): one event per telling, year from sort_key (1e9 + year)
tl_rows = []
for v, n, sk, sortable, stated, event, sb, agreement, akind, dblink in con.execute("select video, n, sort_key, sortable, date_stated, event, speaker_basis, agreement, agreement_kind, link from timeline"):
    if v not in ids or not sk or not sk[:10].isdigit(): continue
    # r: the other notes this row's Database link and Agreement cells name as holding the same event (for the map's "event told before" flag, owner 2026-10-03)
    refs = sorted({t for t in link_re.findall((dblink or "") + " " + (agreement or "")) if t in ids and t != v})
    row = dict(note=v, n=n, y=int(sk[:10]) - 1000000000, s=(sortable or "")[:24], d=(stated or "")[:80], e=(event or "")[:220], w=(sb or "")[:90], a=(akind or agreement or "")[:16])
    if refs: row["r"] = refs
    tl_rows.append(row)
meta = dict(source_groups=SOURCE_GROUPS, notes=len(nodes), cross_check_edges=len(edge_list), people=len(people), people_edges=len(people_edges), timeline_rows=len(tl_rows),
            pages=len(pages), page_note_links=len(page_note), page_page_links=len(page_page), note_page_xc=len(note_page_xc),
            topics=TOPICS, groups=order, built=__import__("datetime").date.today().isoformat(),
            kinds=sorted({k for e in edge_list for k in e["kinds"]}))
# every address a title is known by (the video or article URL from the videos table, and the originals of held third-party sources), so the map's search can find a title from a pasted URL or a video id
for n in ordered:
    n["urls"] = sorted(set(re.findall(r"https?://[^\s)\];,]+", urls.get(n["id"], "") or "")) | {x["orig"] for x in n.get("sources", []) if x.get("orig")})
# claim rows gain: [7] the speaker as a people index (-1 when not a listed person), [8] the people the claim names, [9] attribution (0 firsthand, 1 secondhand, 2 own reasoning or host), [10] for an unidentified speaker, the hosts and guests it is credited to (unsure)
for v, rows in claims_out.items():
    for r in rows:
        k = (v, r[3]); w = who.get(k); u = who_u.get(k)
        r += [pidx.get(w[0], -1) if w else -1, [pidx[q] for q in cl_subj.get(k, []) if q in pidx], (w[1] if w else u[1] if u else 2)]
        if u: r.append([pidx[c] for c in u[0] if c in pidx])
# the claims file is sharded (2026-10-24): graph-claims.json is an index {built, shards, files}, and graph-claims-<k>.json holds the notes whose
# position in the sorted note list is k mod 8; the page loads the index, then every shard in parallel, and merges them. One file reached 14.4 MB of the 16 MB cap.
_CS = 8; _cnotes = sorted(claims_out)
for _k in range(_CS):
    LN.write_text(OUT.replace("graph-data.json", f"graph-claims-{_k}.json"), json.dumps({v: claims_out[v] for v in _cnotes[_k::_CS]}, ensure_ascii=False))
LN.write_text(OUT.replace("graph-data.json", "graph-claims.json"), json.dumps(dict(built=meta["built"], shards=_CS, files=[f"graph-claims-{_k}.json" for _k in range(_CS)], notes=len(_cnotes)), ensure_ascii=False))
# graph-evidence.json: the evidence the ledger is looking for. Every open-questions row of every note and every row of the leads register, with what would settle it.
# item: [0 question | 1 lead, key, kind, text, what would settle it, status, asked by, [title indices], bears on, answer so far, row number]
_fidx = {n["file"]: i for i, n in enumerate(ordered)}; _iidx = {n["id"]: i for i, n in enumerate(ordered)}
_cl = lambda t, k: re.sub(r"\s+", " ", re.sub(r"\]\([^)]*\)", "]", t or "")).strip()[:k]
ev_items = []
for v, n, kind, by, q, bears, settles, status, answer in con.execute("select video, n, kind, asked_by, question, bears_on, settles, status, answer from open_questions"):
    if v in _iidx: ev_items.append([0, f"{v}#{n}", kind or "question", _cl(q, 700), _cl(settles, 500), (status or "open").split()[0], _cl(by, 80), [_iidx[v]], _cl(bears, 160), _cl(answer, 500), str(n)])
for n, lead, kind, by, sources, settles, status, answer in con.execute("select n, lead, kind, asked_by, sources, settles, status, answer from leads"):
    ts = sorted({_fidx[f] for f in LN.NOTE_FILE_LINK_RE.findall(sources or "") if f in _fidx})
    ev_items.append([1, f"lead#{n}", kind or "lead", _cl(lead, 700), _cl(settles, 500), (status or "open").split()[0], _cl(by, 80), ts, _cl(sources, 160), _cl(answer, 500), str(n)])
# research pages keep their own open questions and leads in the schema's open-questions columns (a register's own L1 to L16, a synthesis page's questions); cross-check rows answer them by reference ("lead L1", "open question 1"), so they are carried too. item[11] is the page id.
_pg_ids = {pg["id"] for pg in pages} if isinstance(pages, list) else set()
_cells = LN.split_row   # form F2
for _f in sorted(glob.glob(os.path.join(os.path.dirname(OUT), "..", "*.md"))):
    _stem = os.path.basename(_f)[:-3]; _pid = "r:" + _stem
    if _pid not in _pg_ids or _stem in ("leads-and-inferences", "answered-questions", "declined-answered-elsewhere"): continue
    _hdr = None
    for line in LN.iter_lines(_f):
        if not line.lstrip().startswith("|"): _hdr = None; continue
        c = _cells(re.sub(r"\\\|", "/", line)); low = [x.lower() for x in c]
        if _hdr is None:
            col = {k: next((i for i, x in enumerate(low) if x.startswith(w)), None) for k, w in (("q", "question"), ("l", "lead"), ("s", "what would settle"), ("st", "status"), ("k", "kind"), ("by", "asked by"), ("b", "bears on"), ("a", "answer"))}
            _hdr = col if (col["q"] is not None or col["l"] is not None) and col["s"] is not None and col["st"] is not None else False
            continue
        if not _hdr or set(c[0]) <= set("-: "): continue
        g = lambda k: c[_hdr[k]] if _hdr[k] is not None and _hdr[k] < len(c) else ""
        rid = c[0].strip("* ")
        if not re.fullmatch(r"[A-Za-z]?\d+(?:\.\d+)?", rid): continue
        ev_items.append([0, f"{_pid}#{rid}", g("k") or "question", _cl(g("q") or g("l"), 700), _cl(g("s"), 500), (g("st") or "open").split()[0].lower(), _cl(g("by"), 80), [], _cl(g("b"), 160), _cl(g("a"), 500), rid, _pid])
LN.write_text(OUT.replace("graph-data.json", "graph-evidence.json"), json.dumps(dict(built=meta["built"], items=ev_items), ensure_ascii=False))
print(f"evidence sought: {len(ev_items)} rows ({sum(1 for e in ev_items if e[5] in ('open', 'standing', 'checked'))} not closed)")
# graph-relations.json (owner, 2026-10-05): the relations register, who checks whom, and the candour audits per person, for the map's relations circle.
_pgroup = []
for _p in keep:
    _c = collections.Counter(primary_subject(v) for v in sorted(pm[_p]) if v in ids); _pgroup.append(min(_c.items(), key=lambda kv: (-kv[1], kv[0]))[0] if _c else "")   # (d) the most common group, a tie broken by name
_rel = []
_rcanon = lambda x: canon(_clean_name(_strip_paren(x or "")))
for n, a, b, kind, hier, when, what, source, chain, conf, ac, bc in con.execute("select n, a, b, kind, hierarchy, when_, what, source, chain, confidence, a_canon, b_canon from relations"):
    ai = pidx.get(ac, pidx.get(_rcanon(ac), pidx.get(_rcanon(a), -1))); bi = pidx.get(bc, pidx.get(_rcanon(bc), pidx.get(_rcanon(b), -1)))
    if ai < 0 and bi < 0: continue
    ts = sorted({_fidx[f] for f in re.findall(r"((?:videos|books)/[^)#\s]+\.md)", source or "") if f in _fidx})
    _rel.append([ai, bi, (ac or a or "")[:70], (bc or b or "")[:70], re.sub(r"\s*\(.*", "", kind or "")[:30], _cl(when, 50), _cl((hier + ": " if hier and hier != "none" else "") + (what or ""), 170), ts, (conf or "")[:10], n])
_px = [[pidx[a], pidx[b], dict(c), [[nidx[v], nidx[t], xn, k] for v, t, xn, k in pp_refs[(a, b)] if v in nidx and t in nidx]] for (a, b), c in pp_x.items() if a in pidx and b in pidx]
# audits: who answered each audited turn. The audit table names the asker, not the answerer, so the answerer is read from the claims rows the turn rests on: a claim that cites the audit row, the claims at the same timestamp, or the rows the turn names; the asker is never the answerer. Where that fails and the title has exactly one guest, the guest; otherwise the turn is left unattributed (-1).
_W = {"open": 0, "partial": 1, "contested": 2, "closed-subtle": 3, "closed-outright": 4}
def _move(m):
    m = (m or "").strip().lower().split(" then ")[0].split(";")[0].strip()
    m = {"closed outright": "closed-outright", "closed subtle": "closed-subtle", "yes": "open", "no": "closed-outright"}.get(m, m)
    return _W.get(m)
_c_by_v = collections.defaultdict(list)
for v, n, t, topic, note in con.execute("select video, n, time, topic, note from claims"):
    if v in ids: _c_by_v[v].append((str(n), t or "", topic, note or ""))
_audit = []; _att = 0
for v in sorted(ids):   # sorted (b): the audit list in a fixed order
    cl = _c_by_v.get(v, []); a_sp = collections.defaultdict(collections.Counter); a_tp = collections.defaultdict(collections.Counter); t_sp = collections.defaultdict(collections.Counter); t_tp = collections.defaultdict(collections.Counter); n_sp = {}; n_tp = {}
    for n, t, topic, note in cl:
        w = who.get((v, n)); n_tp[n] = topic
        if w: n_sp[n] = w[0]
        for a in re.findall(r"[Aa]udit\s+(\d+)", note):
            a_tp[a][topic] += 1
            if w: a_sp[a][w[0]] += 1
        m = re.match(r"\s*(\d+:\d\d:\d\d|\d+:\d\d|L\d+)", t)
        if m:
            if topic != "other": t_tp[m.group(1)][topic] += 1
            if w: t_sp[m.group(1)][w[0]] += 1
    guests = [g for g in sorted(phost[v]) if g in pidx]
    for n, t, asker, q, ans, mv, basis in con.execute("select n, time, asked_by, question, answer, move, basis from audit_rows where video=?", (v,)):
        mi = _move(mv)
        if mi is None: continue
        ask = resolve(v, re.split(r"[,(]", asker or "")[0]) if asker and not re.match(r"\s*(none|n/a|the film)", asker, re.I) else None
        m = re.match(r"\s*(\d+:\d\d:\d\d|\d+:\d\d|L\d+)", t or ""); key = m.group(1) if m else None; text = (ans or "") + " " + (q or "")
        rows_named = set()
        for a, b in re.findall(r"rows?\s+(\d+)(?:\s*(?:to|-|–)\s*(\d+))?", text):
            a = int(a); b = int(b) if b else a
            if b - a <= 12: rows_named.update(str(x) for x in range(a, b + 1))
        def _pick(counter):
            c = collections.Counter({k: x for k, x in counter.items() if k != ask}); return c.most_common(1)[0][0] if c else None
        sp = _pick(a_sp.get(str(n), {})) or (key and _pick(t_sp.get(key, {}))) or _pick(collections.Counter(n_sp[r] for r in rows_named if r in n_sp))
        if not sp:
            others = [g for g in guests if g != ask]
            if len(others) == 1: sp = others[0]
        tp = (a_tp[str(n)].most_common(1)[0][0] if a_tp.get(str(n)) else t_tp[key].most_common(1)[0][0] if key and t_tp.get(key) else (collections.Counter(n_tp[r] for r in rows_named if r in n_tp).most_common(1) or [("other", 0)])[0][0])
        if sp and sp in pidx: _att += 1
        _audit.append([pidx.get(sp, -1) if sp else -1, nidx[v], secs(t) if yt_id(urls.get(v, "")) else None, _cl(t, 30), mi, TOPICS.index(tp) if tp in TOPICS else -1, _cl(q, 170), _cl(ans, 200), str(n), (basis or "").strip()[:40]])
LN.write_text(OUT.replace("graph-data.json", "graph-relations.json"), json.dumps(dict(built=meta["built"], group=_pgroup, rel=_rel, px=_px, audit=_audit), ensure_ascii=False))
print(f"relations file: {len(_rel)} relations touching a listed person ({sum(1 for r in _rel if r[0] >= 0 and r[1] >= 0)} person to person); {len(_px)} person-to-person verdict pairs; {len(_audit)} scored audit turns, {_att} attributed to a person")
# the cross-check edges live in their own file (graph-edges.json) since 2026-10-08: graph-data.json reached 15.17 MB of the artifact's 16 MB page-file cap at 242 notes
LN.write_text(OUT.replace("graph-data.json", "graph-edges.json"), json.dumps(dict(built=meta["built"], edges=edge_list), ensure_ascii=False))
LN.write_text(OUT, json.dumps(dict(meta=meta, nodes=ordered, people=people, people_talk=people_talk, people_unsure=people_unsure, people_speak=people_speak, eras=eras,   # people_edges is no longer written: the map stopped reading it, and the file is near the artifact's 16 MB limit
               pages=pages, page_note=page_note, page_page=page_page, note_page_xc=note_page_xc), ensure_ascii=False))
# the timeline rows live in their own file (graph-timeline.json) since 2026-10-07: graph-data.json reached 15.65 MB of the artifact's 16 MB page-file cap
LN.write_text(OUT.replace("graph-data.json", "graph-timeline.json"), json.dumps(dict(built=meta["built"], rows=tl_rows), ensure_ascii=False))
print("wrote", OUT, meta)

# ---- graph-display.json (phase 5, 2026-10-22): the map's display settings, from the pack (pack.toml [display.map] and
# [display.typed_graph]) over the core defaults (tools/packload.py), so the page names no subject, era or kind of its own.
_AV = packload.actor_vocabulary(); _reg_path = _AV["register"]
display_out = dict(built=meta["built"], title=packload.ledger_title(),
    subjects=[dict(id=s_, name=n_, color=c_, dark=d_) for s_, n_, c_, d_ in packload.subject_display()],
    era_segments=packload.era_segments(), page_kinds=DM["page_kinds"], help_rows=DM["help_rows"], help_note=DM["help_note"],
    typed=dict(node_kinds=DT["node_kinds"], edge_kinds=DT["edge_kinds"]),
    actor_register_stem=os.path.splitext(os.path.basename(_reg_path))[0] if _reg_path else "", topics=TOPICS)
LN.write_text(OUT.replace("graph-data.json", "graph-display.json"), json.dumps(display_out, ensure_ascii=False))

# ---- graph-typed.json (phase 5, 2026-10-22): the map as one typed graph (tools/platform-plan.md, the Map row). Three edge kinds:
#   relation        people to people: every relations-register row of graph-relations.json, verbatim (row = the same array), so the
#                   relations circle drawn from this file alone is the circle drawn from graph-relations.json;
#   order-of-battle actors to polities: dated, sourced placements from the pack's actor and polity register page: the actor rows'
#                   polity cells (member, outside, opposed, or a body named) and the polity statements' inside, outside and opposed
#                   cells; an actor is placed only where a cell names it.
# An actor is a cluster of the register's own classification: the codes in an actor row's cluster column that the clusters page
# ([actors] entities_map) defines, labelled with that page's name for the code. A row with no code is placed by the pack's actor
# vocabulary ([actors] kinds_of_being with [display.typed_graph] actor_aliases) matched in its kind cell, each word taken to the
# cluster the coded rows that carry it are most often filed under; the polity statements, which carry no codes, are placed the same
# way. A row that names no cluster and no word of the vocabulary is left unplaced and counted.
#   chain-hop       people to actors: the actor rows' teller and chain cells, each person of the map's people list found in them at
#                   the hop the chain gives (1 = the teller; k = the k-th mouth along "A <- B <- C").
# The register's rows and their placements come from notes.db (tables actors and polity_statements, written by tools/build_db.py through
# tools/ledger/notes.py form A, 2026-10-22; the parse and the placement rules were this file's, moved there unchanged). The clusters
# page ([actors] entities_map) is still read here, for the clusters' names and their count.
_ACTORS, _POLNAME = _AV["actors"], _AV["polity_name"]
_CL = LN.cluster_names(_AV["clusters"] and packload.path(_AV["clusters"]))
_pnorm = LN.polity_norm
_polities = {}   # id -> node
def _polity(name, body, ref):
    pid = "y:" + _pnorm(name)
    n = _polities.get(pid)
    if n is None: n = _polities[pid] = dict(id=pid, kind="polity", label=re.sub(r"\s+", " ", name).strip()[:90], body=body, named=bool(_POLNAME) and _POLNAME.lower() in name.lower(), refs=[])
    if ref not in n["refs"]: n["refs"].append(ref)
    return pid
_cl2 = lambda t, k: re.sub(r"\s+", " ", re.sub(r"\]\([^)]*\)", "]", t or "")).strip()[:k]
try:
    _act_db = con.execute("select cells, placed, oob_role, oob_polity, teller, chain from actors order by rowid").fetchall()
    _stm_db = con.execute("select cells, body_kind, polity, inside_placed, outside_placed, opposed_placed, teller, time, chain, quote from polity_statements order by rowid").fetchall()
except sqlite3.OperationalError as e:
    sys.exit(f"build_graph_data: {DB} has no actor register tables ({e}); run python3 tools/build_db.py first")
_act_rows = [json.loads(r_[0]) for r_ in _act_db]; _stm_rows = [json.loads(r_[0]) for r_ in _stm_db]
_oob = collections.defaultdict(list); _hop = collections.defaultdict(list); _actor_rows = collections.Counter(); _unplaced_rows = 0
# people of the map's list, by full name (as written), by a multi-word alias (any case) and by a surname no one else on the list carries
_full = {p: p for p in keep}
_alias_forms = {a: _al[a] for a in _al if " " in a and _al[a] in pidx}
_sur_tg = collections.Counter(_surname(p) for p in keep)
_sur_forms = {_surname(p): p for p in keep if len(p.split()) >= 2 and len(_surname(p)) >= 5 and _sur_tg[_surname(p)] == 1 and _surname(p)[:1].isupper()}
_rx_cs = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(map(re.escape, set(_full) | set(_sur_forms)), key=lambda x: (-len(x), x))) + r")(?![A-Za-z])") if keep else None
_rx_ci = re.compile(r"(?<![a-z])(" + "|".join(sorted(map(re.escape, _alias_forms), key=lambda x: (-len(x), x))) + r")(?![a-z])") if _alias_forms else None
def _people_in(text):
    out = []
    if _rx_cs:
        for m_ in _rx_cs.finditer(text or ""): out.append(_full.get(m_.group(1)) or _sur_forms.get(m_.group(1)))
    if _rx_ci:
        for m_ in _rx_ci.finditer((text or "").lower()): out.append(_alias_forms[m_.group(1)])
    return [p for p in dict.fromkeys(out) if p]
def _hops(teller, chain):
    """{person: the lowest hop at which the row's teller or chain names them}"""
    h = {}
    def put(p, k): h[p] = min(h.get(p, k), k)
    for p in _people_in(teller): put(p, 1)
    for part in re.split(r";", chain or ""):
        segs = re.split(r"\s*<-\s*", re.sub(r"^\s*(?:[a-z ,/()]*?:\s*)?(?:\d+:\s*)?", "", part, flags=re.I))
        for k, seg in enumerate(segs, 1):
            for p in _people_in(seg): put(p, k if len(segs) > 1 else 1)
    return h
_WORD2CL = LN.ActorPlacer(_CL, _ACTORS, DT["actor_aliases"], DT["polity_unplaced"], _act_rows).word_cluster   # for the meta (the placements are the database's)
_split = lambda cell: [x for x in cell.split("; ") if x] if cell else []
for r_, (_, placed, role, pname, teller, chain) in zip(_act_rows, _act_db):
    rid = r_.get("#", ""); kind_cell = LN.reg_kind_cell(r_)
    acts = _split(placed)
    if not acts: _unplaced_rows += 1; continue
    for a in acts: _actor_rows[a] += 1
    if pname:
        pid = _polity(pname, "register row", rid)
        for a in acts: _oob[("a:" + a, pid, role)].append([rid, role, _cl2(teller, 120), "", _cl2(chain, 120), _cl2(kind_cell, 170)])
    for p, k in _hops(teller, chain).items():
        for a in acts: _hop[("p:" + p, "a:" + a)].append([rid, k])
for r_, (_, bkind, pname, ins, outs, opp, teller, when, chain, quote) in zip(_stm_rows, _stm_db):
    if not pname: continue
    sid = r_.get("#", ""); pid = None
    for role, cell in (("member", ins), ("outside", outs), ("opposed", opp)):
        for a in _split(cell):
            pid = pid or _polity(pname, bkind, sid)
            _oob[("a:" + a, pid, role)].append([sid, role, _cl2(teller, 120), _cl2(when, 60), _cl2(chain, 120), _cl2(quote, 170)])
tg_edges = [dict(kind="relation", source=("p:" + keep[r_[0]]) if r_[0] >= 0 else None, target=("p:" + keep[r_[1]]) if r_[1] >= 0 else None, row=r_) for r_ in _rel]
tg_edges += [dict(kind="order-of-battle", source=a, target=y, role=role, w=len(rows), rows=rows) for (a, y, role), rows in sorted(_oob.items())]
tg_edges += [dict(kind="chain-hop", source=p, target=a, hop=min(x[1] for x in rows), w=len(rows), rows=rows) for (p, a), rows in sorted(_hop.items())]
_pi_used = sorted({i for r_ in _rel for i in (r_[0], r_[1]) if i >= 0} | {pidx[p[2:]] for p, _ in _hop})
_act_used = sorted({a for a, _, _ in _oob} | {a for _, a in _hop})
tg_nodes = [dict(id="p:" + keep[i], kind="person", label=keep[i], pi=i) for i in _pi_used]
tg_nodes += [dict(id=a, kind="actor", label=f"{a[2:]} {_CL.get(a[2:], '')}".strip(), code=a[2:], rows=_actor_rows[a[2:]]) for a in _act_used]
_pol_used = sorted({y for _, y, _ in _oob})
tg_nodes += [_polities[y] for y in _pol_used]
_kc = collections.Counter(e["kind"] for e in tg_edges)
tg_meta = dict(edges_by_kind={k: _kc.get(k, 0) for k in DT["edge_kinds"]}, nodes_by_kind=dict(collections.Counter(n["kind"] for n in tg_nodes)),
               register=_reg_path, clusters_page=_AV["clusters"], clusters=len(_CL), vocabulary_to_cluster=_WORD2CL, register_rows=len(_act_rows), polity_statements=len(_stm_rows), rows_without_an_actor=_unplaced_rows,
               placements=sum(e["w"] for e in tg_edges if e["kind"] == "order-of-battle"), hops=sum(e["w"] for e in tg_edges if e["kind"] == "chain-hop"))
LN.write_text(OUT.replace("graph-data.json", "graph-typed.json"), json.dumps(dict(built=meta["built"], kinds=display_out["typed"], meta=tg_meta, nodes=tg_nodes, edges=tg_edges), ensure_ascii=False))
print("typed graph:", tg_meta)
