#!/usr/bin/env python3
"""Echo patterns: the same non-obvious wording in different mouths, and whether the tellings are acknowledged as linked.

Owner's question (2026-09-29): "Are we going to be able to track repetition across independent-looking mouths?"
This is the sanctioned-disinformation marker the divergence tool cannot see, because repetition is a convergence.

Reads notes.db only. Wording units: every quoted span of five or more words inside a claims row (speaker = the row's
speaker) and every row of the Quotes tables (speaker = the trailing parenthetical, else the note's guest). Units are
shingled into five-word windows; a shingle shared by two or more distinct speakers in two or more notes is an echo.
For each echo the relations register is asked whether one speaker is recorded as a source of the other (acknowledged),
whether the notes share a host or channel (same channel), or neither (unacknowledged echo). Writes
research/echo-patterns.md (a private --db writes beside that db, or under --out). Usage: python3 tools/echoes.py [--db notes.db] [--out <dir>] [--min-words 5]
"""
import re, sqlite3, sys, os, datetime
from collections import Counter, defaultdict
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
if "--help" in sys.argv or "-h" in sys.argv: sys.exit(__doc__ or "usage: python3 tools/echoes.py [--db notes.db] [--detail <mode>]")  # --help safe (2026-10-02): the tool used to regenerate the page on any invocation
DB = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else "notes.db"
# Output location (fixed 2026-10-07): a private --db writes its pages beside that db (or under --out), never over the shared research files.
import os as _os
_OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else (None if _os.path.abspath(DB) == _os.path.abspath("notes.db") else (_os.path.dirname(_os.path.abspath(DB))))
OUT_MD = _os.path.join(_OUT, "echo-patterns.md") if _OUT else "research/echo-patterns.md"
OUT_JSON = _os.path.join(_OUT, "echoes.json") if _OUT else "research/figures/echoes.json"
K = int(sys.argv[sys.argv.index("--min-words") + 1]) if "--min-words" in sys.argv else 5
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
STOP = set("the a an and or of to in on at for with by from that this these those it its is are was were be been being as if then than so but not no yes i you he she we they them his her our your their my me us him do does did have has had will would can could should may might just very really kind sort like there here what which who whom when where why how all any some such into out up down over under again about also".split())
import packload   # the pack's hosts, agencies, name forms and lexicons ([tools.echoes]; phase 7b, 2026-10-22)
_D = packload.tool_data("echoes")
HOSTS = set(_D["hosts"])   # interview hosts and channels: a host retelling a guest is expected
AGENCY = re.compile(_D["agency_rx"], re.I)   # a speaker that is a body or a record
STOCK = [l.strip().lower() for l in open("tools/stock_phrases.txt", encoding="utf-8") if l.strip() and not l.startswith("#")] if os.path.exists("tools/stock_phrases.txt") else []
def stock(sh):
    """A shingle that contains a stock phrase, a run of proper nouns, or nothing but numbers and decades is not wording evidence."""
    j = " " + " ".join(w for w, c in sh) + " "
    if any(" " + st + " " in j for st in STOCK): return True
    content = [(w, c) for w, c in sh if w not in STOP]
    caps = sum(1 for w, c in content if c)
    if content and caps >= 2 and caps * 3 >= len(content) * 2: return True  # a name, a title, a place
    if content and all(re.match(r"^\d|^(?:sixties|seventies|eighties|nineties|hundred|thousand|million|billion|dozen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)$", w) for w, c in content): return True
    return False
SHORT = {}
try:
    for m in re.finditer(r'"([^"]+\.md)":\s*"([^"]+)"', LN.read_text(os.path.join(_T, "build_index.py"))): SHORT[m.group(1)[:-3]] = m.group(2)
except Exception: pass
def short(slug): return SHORT.get(slug, slug)
vid = {r["id"]: r for r in con.execute("select id, guest, host, speakers, uploaded, channel from videos")}
def guest_of(slug):
    r = vid.get(slug)
    if not r: return slug
    g = (r["guest"] or "").strip()
    if g and not g.lower().startswith(("none", "n/a")): return re.split(r"[;,(]", g)[0].strip()[:40]
    h = (r["host"] or "").strip()
    return (re.split(r"[;,(]", h)[0].strip()[:40] if h else slug)
def host_of(slug):
    r = vid.get(slug); h = (r["host"] or r["channel"] or "") if r else ""
    return re.split(r"[;,(]", h)[0].strip().lower()
def norm(t):
    t = t.lower().replace("’", "'"); t = re.sub(r"[^a-z0-9' ]+", " ", t); return re.sub(r"\s+", " ", t).strip()
def captoks(t):
    """(word, capitalised) pairs; a word is capitalised when its source token starts with a capital and is not the first token of the span."""
    out = []
    for i, tok in enumerate(t.replace("’", "'").split()):
        cap = bool(re.match(r"^[\"'(\[]*[A-Z]", tok)) and i > 0
        for w in norm(tok).split(): out.append((w, cap))
    return out
import json as _json
_ALIAS = {}
try:
    for _k, _vs in _json.load(open(packload.vocabulary_path("name_aliases"), encoding="utf-8")).items():   # the pack's alias table ([vocabulary] name_aliases)
        if _k == "_comment": continue
        _ALIAS[_k.lower()] = _k
        for _v in _vs: _ALIAS[_v.lower()] = _k
except Exception: pass
DOCUMENT = re.compile(r"(transcript|document|memo\b|letter|report\b|\btr\.|\bpp?\.\s*\d|statement|tweet|caption|title card|on-screen|slide|footage|record\b|newsreader|text\b|read aloud|archive|obituary|article|website|the \d{4} )", re.I)
HONORIFIC = re.compile(r"^(?:Dr\.?|Rep\.?|Sen\.?|Col\.?|Colonel|Major|Maj\.?|Gen\.?|General|Lt\.?|Lieutenant|Capt\.?|Captain|Adm\.?|Admiral|RADM|VADM|Rear Adm\.?|Rear Admiral|Prof\.?|Professor|Mr\.?|Mrs\.?|Ms\.?|Cdr\.?|Commander|Sgt\.?|Sergeant)\s+", re.I)
def base(p):
    """One mouth per label: strip clip, probability, role and page qualifiers, honorifics and nicknames; take the first
    name of 'X with Y' or 'X and Y'; return '' for documents, unidentified voices and page references."""
    if re.search(r"\((?:text|document|book|scripture|read aloud|title)\)", p or "", re.I) or re.search(r"\b(fragment|testament|key of solomon|zohar|lithica|the key\b|the text\b)", p or "", re.I): return ""
    p = (p or "").replace("\u00a0", " ")
    p = re.sub(r"\(.*?\)", "", p); p = re.sub(r'["“”][^"“”]*["“”]\s*', "", p); p = re.sub(r"‘[^’]*’\s*", "", p); p = p.replace("*", "")
    p = re.sub(r"^\s*(?:almost certainly|probably|likely|apparently|possibly|perhaps|presumably)\s+", "", p, flags=re.I)
    m = re.search(r"\s+(?:quoting|reading|reads|citing|relaying)\s+(.+)$", p, flags=re.I)
    if m: p = m.group(1)
    p = re.split(r"\s+(?:on|to|about|for|through|from|at|in)\s+", p)[0]
    p = re.sub(r"\s+episode(?:\s+voices?)?$", "", p, flags=re.I); p = re.sub(r"\s+", " ", p)
    p = re.sub(r"\b(probable|probably|unlabelled|unattributed|inserted|clip|narration|narrator|voice|recap|cold-open|via|relayed|as heard|assenting|reused)\b", "", p, flags=re.I)
    p = re.sub(r"[,;:]+.*$", "", p); p = re.split(r"\s+(?:with|and|&)\s+", p)[0].strip(" ,;:")
    p = HONORIFIC.sub("", p).strip()
    p = _D["first_name_aliases"].get(p, p)
    if not p or len(p) < 3 or not re.search(r"[A-Z]", p) or re.search(_D["role_words_rx"], p, re.I) or DOCUMENT.search(p) or re.search(_D["role_only_rx"], p, re.I) or p.lower().startswith(("unidentified", "unknown", "unnamed", "an interviewee", "a second")): return ""
    p = re.sub(r"\s+", " ", p).strip()
    return _ALIAS.get(p.lower(), p)
units = []  # (speaker, video, n, text, src)
for r in con.execute("select video, n, speaker, claim from claims"):
    for m in re.finditer(r'"([^"]{20,400})"', r["claim"] or ""):
        if len(m.group(1).split()) >= K: units.append((r["speaker"] or guest_of(r["video"]), r["video"], r["n"], m.group(1), "claims"))
for r in con.execute("select video, n, quote from quotes"):
    q = r["quote"] or ""; sp = None
    m = re.search(r"\(([^()]{2,60})\)\s*$", q)
    if m:
        sp = re.split(r"[,;]", m.group(1))[0].strip(); q = q[:m.start()].strip()
        if not base(sp): sp = None
    q = q.strip().strip('"').strip("“”")
    if len(q.split()) >= K: units.append((sp or guest_of(r["video"]), r["video"], r["n"], q, "quotes"))
# canonical speaker names: bare surname merges into the fullest name ending with it
names = Counter(base(u[0]) for u in units); full = defaultdict(list)
for p in names:
    toks = p.split()
    if len(toks) >= 2: full[toks[-1].lower()].append(p)
def canon(p):
    p = base(p); toks = p.split()
    if len(toks) == 1 and toks[0].lower() in full: return _ALIAS.get(max(full[toks[0].lower()], key=lambda c: names[c]).lower(), max(full[toks[0].lower()], key=lambda c: names[c]))
    return p
import math
df = Counter()
for sp, v, n, text, src in units:
    for w in set(norm(text).split()): df[w] += 1
NU = len(units)
def idf(w): return math.log((NU + 1) / (df.get(w, 0) + 1))
NAMEY = re.compile(_D["namey_rx"])   # full names of offices that read as rare wording
def distinctive(sh):
    """Keep a shingle only if it carries rare wording: at least two words rarer than 1 in 300 units, and a high total rarity."""
    rare = sum(1 for x in sh if x not in STOP and df.get(x, 0) <= NU / 300)
    return rare >= 2 and sum(idf(x) for x in sh if x not in STOP) >= 12 and not NAMEY.match(" ".join(sh))
shingles = defaultdict(set); where = defaultdict(list)
for sp, v, n, text, src in units:
    tw = captoks(text); w = [x for x, c in tw]
    for i in range(0, len(w) - K + 1):
        sh = w[i:i + K]
        if sum(1 for x in sh if x in STOP) >= K - 1: continue  # nearly all stopwords
        if not distinctive(sh) or stock(tw[i:i + K]): continue
        key = " ".join(sh); c = canon(sp)
        if not c: continue
        shingles[key].add((c, v)); where[key].append((c, v, n, text, src))
echoes = {k: s for k, s in shingles.items() if len(set(c for c, v in s)) >= 2 and len(set(v for c, v in s)) >= 2}
# merge overlapping shingles that share the same speaker set into phrases
groups = defaultdict(list)
for k, s in echoes.items(): groups[frozenset(c for c, v in s)].append(k)
def merge_phrases(keys):
    keys = sorted(set(keys)); out = []; used = set()
    for k in keys:
        if k in used: continue
        phrase = k.split(); used.add(k); grown = True
        while grown:
            grown = False
            for k2 in keys:
                if k2 in used: continue
                w2 = k2.split()
                if w2[:-1] == phrase[-(K - 1):]: phrase.append(w2[-1]); used.add(k2); grown = True
                elif w2[1:] == phrase[:K - 1]: phrase.insert(0, w2[0]); used.add(k2); grown = True
        out.append(" ".join(phrase))
    return out
rel = defaultdict(set)
for r in con.execute("select a, b, kind from relations"):
    a, b = canon(r["a"] or ""), canon(r["b"] or ""); rel[(a, b)].add(r["kind"]); rel[(b, a)].add("<-" + r["kind"])
def linkage(speakers, vids):
    acc = []
    for a in speakers:
        for b in speakers:
            if a < b:
                kinds = rel.get((a, b), set()) | rel.get((b, a), set())
                if any(k.endswith("source-of") for k in kinds): acc.append(f"{a} and {b}: one is recorded as the other's source")
                elif any(k.endswith("interviewer") for k in kinds): acc.append(f"{a} interviewed {b} (or the reverse)")
    hosts = Counter(host_of(v) for v in vids)
    same_host = [h for h, c in hosts.items() if c >= 2 and h]
    if acc: return "acknowledged", "; ".join(acc)
    if same_host: return "same channel", f"both through {', '.join(same_host)}"
    return "unacknowledged", ""
rows = []
for spk, keys in groups.items():
    for phrase in merge_phrases(keys):
        ks = [k for k in keys if k in phrase]
        occ = {}
        for k in ks:
            for c, v, n, text, src in where[k]: occ[(c, v, n)] = (text, src)
        vids = sorted(set(v for (c, v, n) in occ)); speakers = sorted(spk)
        kind, why = linkage(speakers, vids)
        first = min(vids, key=lambda v: (vid[v]["uploaded"] if v in vid and vid[v]["uploaded"] else "9999"))
        firstsp = sorted(set(c for (c, v, n) in occ if v == first))
        rows.append(dict(phrase=phrase, speakers=speakers, n_speakers=len(speakers), vids=vids, kind=kind, why=why, first=first, first_speakers=firstsp,
                         hosts=sum(1 for s in speakers if s in HOSTS), agency=bool(AGENCY.search(" ".join(speakers))), occ=occ))
rows.sort(key=lambda r: (-r["n_speakers"], r["kind"] != "unacknowledged", -len(r["vids"]), r["phrase"]))
by_speaker_repeats = Counter(); by_speaker_source = Counter()
for r in rows:
    if r["kind"] == "acknowledged": continue
    for s in r["speakers"]:
        if s in r["first_speakers"]: by_speaker_source[s] += 1
        else: by_speaker_repeats[s] += 1

# ---------------------------------------------------------------------------------------------------------------------
# Detail echoes: the same non-obvious fact in different words. Details are named people and places, dates, sums and
# counted things drawn from every claims row; a detail echo is a PAIR of rare details that co-occur in one claim and
# recur together in claims by two or more speakers in two or more notes. Corroborates cross-checks and the era pages'
# 'not independent' marks are read to say whether the repetition is already recorded.
ORG = re.compile(_D["org_rx"], re.I)   # names that are not details: offices, places, media, scripture, peoples, eras
_DICT_LOWER = set()
try:
    for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore"):
        w = w.strip()
        if w and w[0].islower(): _DICT_LOWER.add(w.lower())
except Exception: pass
def common_word(name):
    """A single capitalised token that is an ordinary English word (black, key, frost, defense) is not a detail."""
    toks_ = name.split()
    return len(toks_) == 1 and toks_[0].lower() in _DICT_LOWER
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
CAPSTOP = set("I The A An In On At But And Or So If When Then Yes No Not It He She We They You This That There What Who How Why Where Which Because While After Before Also Well Now Just Like Even Still Only Very Here Its His Her Their Our My Your One Two Three Four Five Six Seven Eight Nine Ten First Second Third Mr Mrs Ms Dr Rep Sen Gen Col Lt Capt Adm Prof".split()) | set(MONTHS.split("|")) | set("Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split())
UNIT = _D["unit_rx"]   # the counted things of a number detail
def details(text):
    out = set(); t = text or ""
    for m in re.finditer(r"\b(1[6-9]\d\d|20[0-2]\d)(s?)\b", t): out.add("y:" + m.group(1) + m.group(2))
    for m in re.finditer(r"\b(\d{1,2})\s+(" + MONTHS + r")\s+(\d{4})\b", t): out.add("d:" + m.group(1) + " " + m.group(2) + " " + m.group(3))
    for m in re.finditer(r"\b(" + MONTHS + r")\s+(\d{4})\b", t): out.add("d:" + m.group(1) + " " + m.group(2))
    for m in re.finditer(r"\$\s?(\d[\d,.]*)\s*(million|billion|thousand|trillion|bn|m|k)?\b", t): out.add("$:" + m.group(1).rstrip(".") + (" " + m.group(2).lower() if m.group(2) else ""))
    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?)[- ]" + UNIT + r"\b", t, flags=re.I): out.add("n:" + m.group(0).lower().replace("-", " "))
    # proper-noun runs of one to four capitalised tokens (a single token at sentence start is skipped)
    for m in re.finditer(r"(?:(?<=^)|(?<=[\s(\[\"'“‘]))((?:[A-Z][\w'’\-]+|[A-Z]{2,})(?:(?:\s+(?:of|de|von|van|der|the|and|&))?\s+(?:[A-Z][\w'’\-]+|[A-Z]{2,})){0,4})", t):
        run = m.group(1); words = [w for w in re.split(r"\s+", run) if w]
        words = [w for w in words if w not in CAPSTOP and not re.search(r"['’](?:re|ve|ll|d|m|s)$", w)]
        if not words: continue
        start = m.start(); prev = t[max(0, start - 3):start]
        if len(words) == 1 and (start == 0 or re.search(r"[.!?:]\s*[\"'“‘]?\s*$", prev)) : continue
        name = re.sub(r"[’']s$", "", " ".join(words)); name = HONORIFIC.sub("", name)
        if len(name) < 3 or ORG.match(name) or common_word(name) or all(ORG.match(w) or common_word(w) for w in name.split()): continue
        out.add("p:" + _ALIAS.get(name.lower(), name))
    return out
crows = []  # (speaker, video, n, detailset)
ddf = Counter()
for r in con.execute("select video, n, speaker, claim from claims"):
    c = canon(r["speaker"] or "") or canon(guest_of(r["video"]))
    if not c: continue
    ds = details(r["claim"]); crows.append((c, r["video"], r["n"], ds))
    for d in ds: ddf[d] += 1
NC = len(crows)
def didf(d): return math.log((NC + 1) / (ddf.get(d, 0) + 1))
MAXDF = 200
pairs = defaultdict(list)
for c, v, n, ds in crows:
    keep = sorted(d for d in ds if 2 <= ddf[d] <= MAXDF)
    for i in range(len(keep)):
        for j in range(i + 1, len(keep)):
            a, b = keep[i], keep[j]
            if a[0] == "y" and b[0] == "y": continue  # two bare years say little
            if a[0] != "p" and b[0] != "p" and not (a[0] == "d" or b[0] == "d"): continue  # a pair needs a name or a full date
            if a[2:].lower() in b[2:].lower() or b[2:].lower() in a[2:].lower(): continue  # 'Lisle' inside 'Gareth Lisle'
            pairs[(a, b)].append((c, v, n))
# recorded corroborations (cross-check rows) and the era pages' 'not independent' marks, as video pairs
def slugs_in(text): return set(LN.NOTE_SLUG_RE.findall(text or ""))   # form L5
corro = defaultdict(list)
for r in con.execute("select video, n, this_note, elsewhere from cross_checks where kind='corroborates'"):
    for sl in slugs_in(r["elsewhere"]):
        if sl != r["video"]: corro[frozenset((r["video"], sl))].append((r["video"], r["n"]))
era_dep = set()
import glob
for fp in glob.glob("research/timeline-consolidated-*.md"):
    for line in LN.iter_lines(fp):
        if "not independent" in line:
            sl = sorted(slugs_in(line))
            for i in range(len(sl)):
                for j in range(i + 1, len(sl)): era_dep.add(frozenset((sl[i], sl[j])))
def recorded(vids):
    vids = sorted(vids); cc = []; era = False
    for i in range(len(vids)):
        for j in range(i + 1, len(vids)):
            k = frozenset((vids[i], vids[j]))
            if k in corro: cc += corro[k]
            if k in era_dep: era = True
    return cc, era
dech = {}
for (a, b), occ in pairs.items():
    sp = set(c for c, v, n in occ); vs = set(v for c, v, n in occ)
    if len(sp) < 2 or len(vs) < 2 or len(occ) > 40: continue
    dech[(a, b)] = occ
# cluster pairs that share the same speaker set and video set
clusters = defaultdict(lambda: {"details": set(), "occ": set(), "score": 0.0})
for (a, b), occ in dech.items():
    key = (frozenset(c for c, v, n in occ), frozenset(v for c, v, n in occ))
    cl = clusters[key]; cl["details"] |= {a, b}; cl["occ"] |= set(occ); cl["score"] = max(cl["score"], didf(a) + didf(b))
def label(d):
    k, val = d[0], d[2:]
    return {"y": val, "d": val, "$": "$" + val, "n": val, "p": val}[k]
drows = []
for (sps, vs), cl in clusters.items():
    kind, why = linkage(sorted(sps), sorted(vs))
    cc, era = recorded(vs)
    first = min(vs, key=lambda v: (vid[v]["uploaded"] or "9999") if vid.get(v) else "9999")
    firstsp = sorted(set(c for c, v, n in cl["occ"] if v == first))
    drows.append(dict(details=sorted(label(d) for d in cl["details"]), speakers=sorted(sps), vids=sorted(vs), kind=kind, why=why, score=cl["score"],
                      cc=cc, era=era, first=first, first_speakers=firstsp, n=len(cl["occ"]), hosts=sum(1 for s in sps if s in HOSTS)))
drows.sort(key=lambda r: (r["kind"] != "unacknowledged", -len(r["speakers"]), -r["score"]))
# corroborates cross-check rows whose mouths have no recorded link
unlinked_corro = []
for r in con.execute("select video, n, this_note, elsewhere from cross_checks where kind='corroborates'"):
    others = [sl for sl in slugs_in(r["elsewhere"]) if sl != r["video"]]
    if not others: continue
    sps = sorted(set([canon(guest_of(r["video"]))] + [canon(guest_of(sl)) for sl in others]) - {""})
    if len(sps) < 2: continue
    kind, why = linkage(sps, [r["video"]] + others)
    if kind == "unacknowledged": unlinked_corro.append((r["video"], r["n"], sps, others, r["this_note"] or ""))

today = datetime.date.today().isoformat()
out = ["# Echo patterns: the same wording in different mouths\n", "| Field | Value |", "|---|---|",
       "| **Kind** | research (generated; regenerate with `python3 tools/echoes.py`) |",
       f"| **Built** | {today}, from notes.db: quoted spans of {K} or more words in claims rows, and the Quotes tables, shingled into {K}-word windows; an echo is a window shared by two or more speakers in two or more notes |",
       f"| **Counts** | {len(rows)} echoed phrases (stock phrases, names and titles excluded by tools/stock_phrases.txt and the proper-noun rule); {sum(1 for r in rows if r['kind']=='unacknowledged')} unacknowledged, {sum(1 for r in rows if r['kind']=='same channel')} through a shared channel, {sum(1 for r in rows if r['kind']=='acknowledged')} acknowledged (one speaker recorded as the other's source); {sum(1 for r in rows if r['n_speakers']>=3)} phrases in three or more mouths |",
       f"| **Detail mode** | {len(drows)} detail clusters (section 6): the same rare details in claims by two or more speakers in two or more notes; {sum(1 for r in drows if r['kind']=='unacknowledged')} unacknowledged, {sum(1 for r in drows if not r['cc'] and not r['era'])} not yet recorded by a corroborates cross-check or an era 'not independent' mark; {len(unlinked_corro)} recorded corroborations between mouths with no recorded link (section 7) |",
       "| **Rule** | The sanctioned-disinformation marker the divergence page cannot see: 'the same non-obvious wording or detail appears in several tellers who cite each other or a common unnamed source' (owner, 2026-09-29). An echo is evidence of a shared source, not of coordination; stock phrases, scripture, famous lines and sponsor reads echo innocently, and a host retelling a guest is expected. Read the linkage column first. |",
       "| **Related** | [divergence patterns](divergence-patterns.md); [relations register](relations-register.md); [leads register](leads-and-inferences.md) |\n",
       _D["how_to_read"],
       "## 1. Phrases in three or more mouths\n", "| Phrase | Speakers | Linkage | Why | First held telling |", "|---|---|---|---|---|"]
for r in rows:
    if r["n_speakers"] >= 3:
        out.append(f"| {r['phrase'][:140]} | {', '.join(r['speakers'])} | {r['kind']} | {r['why'][:160]} | {short(r['first'])}: {', '.join(r['first_speakers'])} |")
out += ["\n## 2. Unacknowledged echoes between two speakers\n", "Pairs with no recorded source, interview or channel link. The list is long; agencies and officials are marked.\n", "| Phrase | Speakers | Notes | First held telling |", "|---|---|---|---|"]
for r in rows:
    if r["n_speakers"] == 2 and r["kind"] == "unacknowledged":
        out.append(f"| {r['phrase'][:140]} | {', '.join(r['speakers'])}{' (agency or official)' if r['agency'] else ''} | {', '.join(short(v) for v in r['vids'])} | {short(r['first'])}: {', '.join(r['first_speakers'])} |")
out += ["\n## 3. Who repeats, and who is repeated (unacknowledged and same-channel echoes only)\n", "| Speaker | Echoes where this speaker is the first held telling | Echoes where this speaker repeats an earlier telling |", "|---|---|---|"]
for s, _ in sorted(Counter({k: by_speaker_source[k] + by_speaker_repeats[k] for k in set(by_speaker_source) | set(by_speaker_repeats)}).most_common(60)):
    out.append(f"| {s}{' (host)' if s in HOSTS else ''} | {by_speaker_source[s]} | {by_speaker_repeats[s]} |")
out += ["\n## 4. Echoes through a shared channel\n", "| Phrase | Speakers | Channel | Notes |", "|---|---|---|---|"]
for r in rows:
    if r["kind"] == "same channel": out.append(f"| {r['phrase'][:120]} | {', '.join(r['speakers'])} | {r['why'][:80]} | {', '.join(short(v) for v in r['vids'])} |")
out += ["\n## 5. Acknowledged repetitions\n", "| Phrase | Speakers | Route |", "|---|---|---|"]
for r in rows:
    if r["kind"] == "acknowledged": out.append(f"| {r['phrase'][:120]} | {', '.join(r['speakers'])} | {r['why'][:160]} |")
out += ["\n## 6. Repeated details in different mouths (the same fact in different words)\n",
        "A detail is a named person or place, a date, a sum or a counted thing, read from every claims row. A row here is a set of rare details that occur together in one claim and recur together in claims by two or more speakers in two or more notes. 'Recorded' says whether a corroborates cross-check already links the notes (cc) or an era page marks the tellings not independent (era); 'no' means the repetition is not yet recorded anywhere. Unacknowledged rows come first.\n",
        "| Details | Speakers | Linkage | Recorded | Notes | First held telling |", "|---|---|---|---|---|---|"]
for r in drows[:250]:
    rec = ("cc " + ", ".join(f"{short(v)} {n}" for v, n in r["cc"][:3])) if r["cc"] else ""
    if r["era"]: rec = (rec + "; " if rec else "") + "era: not independent"
    out.append(f"| {'; '.join(r['details'])[:160]} | {', '.join(r['speakers'])}{' (host in the set)' if r['hosts'] else ''} | {r['kind']}{(': ' + r['why'][:100]) if r['why'] else ''} | {rec or 'no'} | {', '.join(short(v) for v in r['vids'])[:160]} | {short(r['first'])}: {', '.join(r['first_speakers'])} |")
out += ["\n## 7. Recorded corroborations between mouths with no recorded link\n",
        "Corroborates cross-check rows whose two notes' speakers have no source, interview or channel link in the relations register. Each is either an independent confirmation (the strongest kind of evidence the database holds) or an unrecorded common source; the relations register should say which.\n",
        "| Note | Row | Speakers | Corroborated by | This note's telling |", "|---|---|---|---|---|"]
for v, n, sps, others, tn in unlinked_corro[:300]:
    out.append(f"| {short(v)} | {n} | {', '.join(sps)} | {', '.join(short(o) for o in others)[:120]} | {tn[:180].replace('|', '/')} |")
LN.write_text(OUT_MD, "\n".join(out) + "\n")
print(f"detail echoes: {len(drows)} clusters ({sum(1 for r in drows if r['kind']=='unacknowledged')} unacknowledged, {sum(1 for r in drows if not r['cc'] and not r['era'])} unrecorded); corroborations between unlinked mouths: {len(unlinked_corro)} of {sum(len(v) for v in corro.values())} rows")
for r in drows[:12]: print(f"  {r['kind']:14} {'; '.join(r['details'])[:60]:60} | {', '.join(r['speakers'])[:50]}")
print(f"wrote {OUT_MD}: {len(units)} wording units, {len(rows)} echoed phrases, {sum(1 for r in rows if r['kind']=='unacknowledged')} unacknowledged, {sum(1 for r in rows if r['n_speakers']>=3)} in 3+ mouths")
for r in rows[:15]: print(f"  {r['n_speakers']} {r['kind']:14} {r['phrase'][:70]:70} | {', '.join(r['speakers'])[:60]}")

# machine-readable copy for the map (tools/build_graph_data.py reads it): the echoed phrases and the repeated-detail clusters
import json as _json2
def _row(r, what): return dict(what=what, text=(r.get("phrase") or "; ".join(r.get("details", []))), speakers=list(r.get("speakers", [])), vids=list(r.get("vids", [])), kind=r.get("kind", ""), why=r.get("why", ""), first=r.get("first", ""))
_json2.dump([_row(r, "wording") for r in rows] + [_row(r, "detail") for r in drows], LN.open_write(OUT_JSON), ensure_ascii=False)
