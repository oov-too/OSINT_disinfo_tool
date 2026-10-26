#!/usr/bin/env python3
"""Narrative pack (tools/narratives.md, phase 0): the deterministic pre-pass the narrative agents read before they query notes.db.
Reads notes.db (read-only), research/figures/openness-dataset.json and the pack's alias table ([vocabulary] name_aliases). Writes only under --out.
Usage: python3 tools/narrative_pack.py [--out wip/narratives-<date>/pack] [--db notes.db] [--from 1933]
Files written:
  synchrony-index.md      year-by-lane counts 1933 on (quarters from 2017), dense windows ranked, lane rules
  synchrony/<era>.md      every dated timeline row of the era by window and lane, with chain root and agreement kind
  contradictions.md       every contradiction and drift node, ranked by provisional impact; insider and agency parties marked
  speakers.md             one sheet per carrier (>= --min-rows claims rows): span, class, topic and move mix, closures, affiliations, divergences
  signals.md              the hints layer: walls per carrier and what the carrier says near them; absence leads
  seeds.md                the six theses with their terms, and pointers to the crossings table and thread leads
Every section states its cap and what it dropped (no silent caps). Every carrier's rows count in window density alike: a compiler's developed posts stand on the same footing as a host's. Speaker grouping is by canonical name (the pack's alias table,
then full name, then a surname merged into a unique full name); the grouping is mechanical and may conflate or split; sheets say so.
"""
import sqlite3, sys, os, re, json, datetime, math
from collections import Counter, defaultdict
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT); sys.path.insert(0, "tools")
import packload   # the domain pack: era boundaries, the narrative pack's first year, the thesis seeds (phase 1, 2026-10-22)
def arg(n, d=None):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
TODAY = datetime.date.today().isoformat()
OUT = arg("--out", f"wip/narratives-{TODAY[5:7]}{TODAY[8:10]}/pack"); DB = arg("--db", "notes.db"); FROM = int(arg("--from", packload.narrative_from()))
MIN_ROWS = int(arg("--min-rows", 20))
os.makedirs(os.path.join(OUT, "synchrony"), exist_ok=True)
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory = sqlite3.Row
Q = lambda s, *a: con.execute(s, a).fetchall()

# ---------- speakers: canonical names ----------
_AP = packload.vocabulary_path("name_aliases")
aliases = json.load(open(_AP)) if _AP and os.path.exists(_AP) else {}; alias_map = {}   # the project's own alias table ([vocabulary] name_aliases), if it has one
_D = packload.tool_data("narrative_pack")   # the pack's lanes, lane wording, subject fallbacks, agencies and seed pointers ([tools.narrative_pack]; phase 7b)
for canon, vs in aliases.items():
    if canon.startswith("_"): continue
    for v in vs: alias_map[v.lower()] = canon
    alias_map[canon.lower()] = canon
TITLES = re.compile(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|col\.?|colonel|major|gen\.?|general|lt\.?|capt\.?|rep\.?|sen\.?|prof\.?)\s+", re.I)
def base_name(s):
    s = re.sub(r"\(.*?\)", "", s or "").strip()
    s = re.split(r",| with | and | relaying | reading | citing | quoting ", s)[0].strip()
    s = TITLES.sub("", s).strip(" .;:")
    return s
full_names = Counter()
for r in Q("select speaker from claims"):
    b = base_name(r["speaker"])
    if b.lower() in alias_map: full_names[alias_map[b.lower()]] += 1
    elif len(b.split()) >= 2 and not b.lower().startswith("the "): full_names[b] += 1
surname_to_full = defaultdict(set)
for f in full_names: surname_to_full[f.split()[-1].lower()].add(f)
_vid_people = {}
def video_people(v):
    if v not in _vid_people:
        row = videos.get(v, {}); names = []
        for fld in ("guest", "host", "speakers"):  # guest first: on a tie the guest wins (the guest over a co-host of the same surname)
            for part in re.split(r",| and |;", row.get(fld) or ""):
                b = base_name(part)
                if b and len(b.split()) >= 2 and not b.lower().startswith(("none", "the ", "unnamed")):
                    c = alias_map.get(b.lower(), b)
                    if c not in names: names.append(c)
        _vid_people[v] = names
    return _vid_people[v]
def canon(s, video=None):
    b = base_name(s)
    if not b: return "unnamed"
    if b.lower() in alias_map: return alias_map[b.lower()]
    toks = b.split()
    if len(toks) >= 2 and not b.lower().startswith("the "): return b
    k = b.lower()
    if video:  # a bare surname resolves first through the note's own Host, Guest and Speakers fields (fix 2026-10-08: a bare surname was merging into a namesake's full name)
        hits = [n for n in video_people(video) if n.split()[-1].lower() == k]
        if hits: return hits[0]
    if k in surname_to_full and len(surname_to_full[k]) == 1: return next(iter(surname_to_full[k]))
    if k in surname_to_full and len(surname_to_full[k]) > 1:  # ambiguous surname: pick the most frequent full name, say so
        return max(surname_to_full[k], key=lambda f: full_names[f])
    return b

# ---------- lanes ----------
videos = {r["id"]: dict(r) for r in Q("select * from videos")}
subj = defaultdict(set)
for r in Q("select video, subject from video_subjects"): subj[r["video"]].add(r["subject"])
claim_topic = {}
for r in Q("select video, n, topic, speaker, source_class, move from claims"): claim_topic[(r["video"], str(r["n"]))] = r
_LF = _D["lane_fallback"]   # the note-subject fallback of lane_of: a primary and a secondary subject, their lanes and labels, the antecedent year
PRIMARY = lambda v: _LF["primary_subject"] in subj.get(v, ())
SECONDARY = lambda v: _LF["secondary_subject"] in subj.get(v, ())
LANES = ["A", "B", "C", "D", "E", "F", "G", "H"]
try: _PACK = packload.pack()
except FileNotFoundError: _PACK = {}   # no pack yet: the core defaults alone (as packload.tool_data)
_OWN = _PACK.get("tools", {}).get("narrative_pack", {})   # the keys the pack itself gives in [tools.narrative_pack]
_VIEWER_LANES = _PACK.get("display", {}).get("viewer", {}).get("lanes", {})   # the pack's declared lanes ([display.viewer.lanes])
_CORE = packload.TOOL_DEFAULTS["narrative_pack"]
# Lane names (7b2 item 14, 2026-10-23): the pack's [tools.narrative_pack] lane_names when it gives them; else the lanes the pack declares
# for its viewer ([display.viewer.lanes]); else the core's neutral names. A lane the viewer table leaves out keeps the core's name.
LANES_FROM_VIEWER = "lane_names" not in _OWN and bool(_VIEWER_LANES)
LANE_NAME = {L: _VIEWER_LANES.get(L, _D["lane_names"][L]) for L in LANES} if LANES_FROM_VIEWER else dict(_D["lane_names"])
_LRX = dict(_D["lane_rx"])
if LANES_FROM_VIEWER and "lane_rx" not in _OWN:
    # the core's wording describes the core's lanes (B public record, E money, H organisations); it places rows only in a pack lane of the same
    # name, never in a lane the pack has given another meaning (the pilot's B is "Prosecutions and recovery": public-record wording stays out)
    _LRX = {L: p for L, p in _LRX.items() if LANE_NAME[L].strip().lower() == _CORE["lane_names"].get(L, "").strip().lower()}
RX = {L: re.compile(p, re.I) for L, p in _LRX.items()}   # a lane with no wording in the pack is placed by topic and subject only
def lane_rule_notes():
    """What the index page says of a pack that gives the lanes only in part: where the names come from, which lanes have wording, the fallback."""
    out = []
    if LANES_FROM_VIEWER: out.append("Lane names are the pack's own ([display.viewer.lanes]); the pack gives no [tools.narrative_pack] lane_names.")
    if "lane_rx" not in _OWN:
        out.append("The pack gives no lane wording ([tools.narrative_pack] lane_rx): the core's wording places rows only in " + (", ".join(f"{L} {LANE_NAME[L]}" for L in LANES if L in RX) or "no lane") + "; every other lane is reached only by claims topic (topic_lane) or note subject (lane_fallback).")
    if "topic_lane" not in _OWN: out.append("The pack maps no claims topic to a lane (topic_lane).")
    if "lane_fallback" not in _OWN:
        out.append(f"The pack gives no subject fallback (lane_fallback): a row no wording or topic places falls to lane {_LF['fallback_lane']} ({LANE_NAME.get(_LF['fallback_lane'], '?')}), marked lane-rule=fallback; that lane is a default, not a reading of the row.")
    if not any(k in _OWN for k in ("lane_rx", "topic_lane", "lane_fallback")):
        _reach = sorted(set(RX) | {"G", _LF["fallback_lane"]})
        out.append("So for this pack only lanes " + ", ".join(_reach) + " receive rows (G by date before %d); builders place the rest by reading." % FROM)
    return (" " + " ".join(out)) if out else ""
TOPIC_LANE = dict(_D["topic_lane"])
def year_of(sortable):
    m = re.match(r"~?(-?\d{1,4})", sortable or "")
    return int(m.group(1)) if m else None
def lane_of(row):
    y = year_of(row["sortable"])
    if y is not None and y < FROM: return "G", "date before %d" % FROM
    ev = row["event"] or ""; v = row["video"]
    topic = None
    for m in re.finditer(r"claims (\d+)", (row["speaker_basis"] or "") + " " + (row["link"] or "")):
        c = claim_topic.get((v, m.group(1)))
        if c: topic = c["topic"]; break
    for L in ["H", "F", "B"]:
        if L in RX and RX[L].search(ev):
            if L == "H" and not re.search(r"\b(?:[A-Z][A-Za-z&.-]+ ){0,3}(?:[A-Z]{2,}|Institute|Foundation|Office|Agency|Corporation|Corp\.?|Inc\.?|Company|Project|Program|Programme|Task Force|Society|Committee|Council|Bureau|Laboratory|Lab|Division|Command|Department|Ministry|Church|University)\b", ev): continue
            return L, "wording"
    if topic in TOPIC_LANE and TOPIC_LANE[topic] in ("E", "C", "D", "G"): return TOPIC_LANE[topic], "topic " + topic
    for L in ["E", "C", "D", "A"]:
        if L in RX and RX[L].search(ev): return L, "wording"
    if topic in TOPIC_LANE: return TOPIC_LANE[topic], "topic " + topic
    if SECONDARY(v) and not PRIMARY(v): return _LF["secondary_lane"], _LF["secondary_label"]
    if PRIMARY(v): return _LF["primary_lane"], _LF["primary_label"]
    if y is not None and _LF.get("antecedent_year") is not None and y < _LF["antecedent_year"]: return _LF["antecedent_lane"], _LF["antecedent_label"]
    return _LF["primary_lane"] if PRIMARY(v) else _LF["fallback_lane"], "fallback"
def root_of(chain):
    c = re.sub(r"^\s*\d+:\s*", "", chain or "").strip()
    if not c: return "?"
    parts = [p.strip() for p in c.split("<-")]
    return re.sub(r"\s*\(.*?\)\s*$", "", parts[-1])[:60]
ERAS = packload.eras("synchrony")   # the pack's era boundaries (pack.toml [eras]; moved 2026-10-22)
def window_of(sortable):
    y = year_of(sortable)
    if y is None: return None
    if y >= 2017:
        m = re.match(r"~?\d{4}-(\d{2})", sortable or "")
        q = (int(m.group(1)) - 1) // 3 + 1 if m and m.group(1) != "00" else 0
        return f"{y}" + (f"-Q{q}" if q else "")
    return str(y)
def note_link(v):
    f = videos.get(v, {}).get("file", f"videos/{v}.md"); t = videos.get(v, {}).get("title", v)
    return f"[{t}](../../{f})"

# ---------- synchrony ----------
tl = Q("select * from timeline where sortable is not null and sortable != ''")
rows_by_era = defaultdict(list); grid = defaultdict(Counter); undated = 0
for r in tl:
    y = year_of(r["sortable"])
    if y is None: undated += 1; continue
    if y < FROM: continue
    L, why = lane_of(r); w = window_of(r["sortable"])
    grid[w][L] += 1
    for name, a, b in ERAS:
        if a <= y <= b: rows_by_era[name].append((w, L, r, why)); break
def wkey(w):
    m = re.match(r"(\d{4})(?:-Q(\d))?", w); return (int(m.group(1)), int(m.group(2) or 0))
windows = sorted(grid, key=wkey)
dense = sorted(windows, key=lambda w: (-sum(1 for L in LANES if grid[w][L] > 0), -sum(grid[w].values())))
with open(os.path.join(OUT, "synchrony-index.md"), "w") as f:
    f.write(f"# Synchrony index (narrative pack, built {TODAY} from {DB})\n\n")
    f.write(f"Rows: {len(tl)} timeline rows with a sortable date; {sum(sum(c.values()) for c in grid.values())} from {FROM} on placed below; {undated} unparseable dates skipped; rows before {FROM} are not on this grid (lane G antecedents enter only when a later carrier invokes them).\n\n")
    f.write("Lanes: " + "; ".join(f"{L} {LANE_NAME[L]}" for L in LANES) + ". Assignment is mechanical (tools/narrative_pack.py `lane_of`: date before %d -> G; then H, F, B by wording; then topic for E, C, D, G; then E, C, D, A by wording; then topic; then note subject). Agents reassign a node when the rule is wrong and say so.%s\n\n" % (FROM, lane_rule_notes()))
    f.write("## Counts by window and lane\n\n| Window | " + " | ".join(LANES) + " | Total | Lanes active |\n|---|" + "---|" * (len(LANES) + 2) + "\n")
    for w in windows:
        c = grid[w]; f.write(f"| {w} | " + " | ".join(str(c[L] or "") for L in LANES) + f" | {sum(c.values())} | {sum(1 for L in LANES if c[L])} |\n")
    f.write("\n## Dense windows (ranked by lanes active, then rows)\n\nA dense window is where three or more lanes move at once; every narrative must say what the other lanes were doing in each dense window it crosses.\n\n| Rank | Window | Lanes active | Rows | Lanes |\n|---|---|---|---|---|\n")
    for i, w in enumerate(d for d in dense if sum(1 for L in LANES if grid[d][L]) >= 3):  # no cap (change 37, 2026-10-08)
        c = grid[w]; f.write(f"| {i+1} | {w} | {sum(1 for L in LANES if c[L])} | {sum(c.values())} | " + ", ".join(f"{L} {c[L]}" for L in LANES if c[L]) + " |\n")
for name, a, b in ERAS:
    rows = rows_by_era[name]
    with open(os.path.join(OUT, "synchrony", f"{name}.md"), "w") as f:
        f.write(f"# Synchrony rows, {name} (narrative pack, built {TODAY})\n\n{len(rows)} dated timeline rows. Each line: `[note timeline-n] date as stated: event (speaker basis) root=<chain root> agree=<agreement kind> lane-rule=<why>`. Rows are grouped by window, then lane. No cap: every row of the era is here.\n")
        byw = defaultdict(lambda: defaultdict(list))
        for w, L, r, why in rows: byw[w][L].append((r, why))
        for w in sorted(byw, key=wkey):
            f.write(f"\n## {w}\n")
            for L in LANES:
                if not byw[w][L]: continue
                f.write(f"\n### {L} {LANE_NAME[L]} ({len(byw[w][L])})\n")
                for r, why in sorted(byw[w][L], key=lambda x: (x[0]["sort_key"] or "", x[0]["video"])):
                    ev = (r["event"] or "").replace("|", "/")[:300]; sb = (r["speaker_basis"] or "")[:120]
                    f.write(f"- [{r['video']} tl {r['n']}] {r['date_stated'] or r['sortable']}: {ev} ({sb}) root={root_of(r['chain'])} agree={r['agreement_kind'] or 'new'} lane-rule={why}\n")

# ---------- contradictions ----------
AGENCIES = list(_D["agencies"])   # bodies and offices: an agency party is marked on a contradiction node
def is_agency(s): return any(re.search(r"\b" + re.escape(a) + r"\b", s or "") for a in AGENCIES)
# The agency mark from the rows' own agency tags (7b2 item 14, 2026-10-23; tools/schema.md section 10): a cross-check Note or a timeline
# Agreement that opens `agency divergence:` (after the audit markers of rulings (h) to (q)), or a [div: ...] tag whose party= names an agency.
# The parsing is tools/divergences.py's (agency_party's marker strip and prefix, parse_tag's party, is_agency over the pack's
# [tools.divergences] agencies, the non-parties), repeated here because that tool writes its page when imported.
_DV = packload.tool_data("divergences")
DIV_AGENCIES = list(_DV["agencies"]); NON_PARTIES = tuple(_DV["non_parties"])
_MARKERS = re.compile(r"^(?:\s*(?:point\s*:\s*[a-z]+|settled\s+\d{4}-\d{2}-\d{2}\s*:[^;]*|revised\s+\d{4}-\d{2}-\d{2}\s*:[^;]*|was\s*:[^;]*)\s*;\s*)+", re.I)
def is_div_agency(p):
    pl = " " + (p or "").lower() + " "
    return any(re.search(r"(?<![a-z])" + re.escape(a.lower()) + r"(?![a-z])", pl) for a in DIV_AGENCIES)
def agency_prefixed(text): return bool(re.match(r"agency divergence\s*:", _MARKERS.sub("", (text or "").strip()), re.I))
def agency_tagged(text, body=None):
    """True when the row's own tags name an agency: the `agency divergence:` prefix on `body` (the cell less its kind word), or party=."""
    if agency_prefixed(text if body is None else body): return True
    p = parse_div(text).get("party", "")
    return bool(p) and p not in NON_PARTIES and (is_agency(p) or is_div_agency(p))
# insiders: speakers with firsthand rows on own role or program details
ins = Counter()
_IT = list(_D["insider_topics"])   # the topics on which firsthand rows make an insider (own role, the programme's details)
for r in Q("select video, speaker, count(*) c from claims where source_class in ('firsthand','program-record') and topic in (%s) group by video, speaker" % ",".join("?" * len(_IT)), *_IT):
    ins[canon(r["speaker"], r["video"])] += r["c"]
HOSTS = Counter(canon(v.get("host") or "", vid) for vid, v in videos.items() if v.get("host") and v.get("host") != "none")
# insider = five or more firsthand or program-record rows on own role or program details, and not primarily a host (fix 2026-10-08: the mark caught three interview hosts)
INSIDERS = {k for k, v in ins.items() if v >= 5 and HOSTS.get(k, 0) < 3}
def parse_div(s):
    m = re.search(r"\[div:([^\]]*)\]", s or ""); d = {}
    if m:
        for kv in m.group(1).split(";"):
            if "=" in kv: k, v = kv.split("=", 1); d[k.strip()] = v.strip()
    return d
cluster_size = Counter()
for r in tl: cluster_size[(r["sortable"] or "", (r["event"] or "")[:40].lower())] += 1
nodes = []
for r in tl:
    if r["agreement_kind"] not in ("contradicts", "drifts"): continue
    y = year_of(r["sortable"])
    if y is not None and y < FROM: continue
    d = parse_div(r["agreement"]); party = canon(r["speaker_basis"] or "", r["video"])
    core = 1.0 if d.get("core") == "core" else 0.3 if d.get("core") == "periphery" else 0.5
    indep = 1.0 if d.get("indep") == "yes" else 0.4 if d.get("indep") == "no" else 0.6
    more = 0.1 * max(0, cluster_size[(r["sortable"] or "", (r["event"] or "")[:40].lower())] - 1)
    _ag = r["agreement"] or ""
    agency = 0.5 if (is_agency(r["speaker_basis"]) or is_agency(r["agreement"]) or agency_tagged(_ag, _ag.split(":", 1)[1] if ":" in _ag else "")) else 0
    kindw = 1.0 if r["agreement_kind"] == "contradicts" else 0.5
    score = kindw * (core * indep + more + agency)
    nodes.append(dict(src="timeline", video=r["video"], n=r["n"], date=r["date_stated"] or r["sortable"], event=(r["event"] or "")[:200], party=party,
                      kind=r["agreement_kind"], agreement=(r["agreement"] or "")[:400], div=d, score=round(score, 2), agency=bool(agency), insider=party in INSIDERS))
for r in Q("select * from cross_checks where lower(kind) like '%contradict%' or lower(verdict) like '%contradict%'"):
    _xa = is_agency(r["this_note"]) or is_agency(r["elsewhere"]) or agency_tagged(r["note"])
    nodes.append(dict(src="cross_check", video=r["video"], n=r["n"], date="", event=(r["this_note"] or "")[:200], party=canon(videos.get(r["video"], {}).get("guest") or "", r["video"]),
                      kind="cross-check " + (r["verdict"] or r["kind"] or ""), agreement=(r["elsewhere"] or "")[:300] + " | " + (r["note"] or "")[:150], div={},
                      score=0.6 + (0.5 if _xa else 0), agency=_xa, insider=False))   # the agency bonus the page's formula states for cross-checks (7b2 item 14)
for r in Q("select * from leads where kind='divergence'"):
    nodes.append(dict(src="lead", video="", n=r["n"], date="", event=(r["lead"] or "")[:260], party="", kind="lead divergence; status " + (r["status"] or ""),
                      agreement=(r["settles"] or "")[:200], div={}, score=0.5 + (0.5 if is_agency(r["lead"]) else 0), agency=is_agency(r["lead"]), insider=False))
nodes.sort(key=lambda n: -n["score"])
CAP = 400
with open(os.path.join(OUT, "contradictions.md"), "w") as f:
    f.write(f"# Contradiction nodes (narrative pack, built {TODAY})\n\n{len(nodes)} nodes: {sum(1 for n in nodes if n['src']=='timeline')} timeline rows (contradicts or drifts, from {FROM} on), {sum(1 for n in nodes if n['src']=='cross_check')} cross-checks, {sum(1 for n in nodes if n['src']=='lead')} divergence leads. Listed: top {min(CAP, len(nodes))} by provisional impact; {max(0, len(nodes)-CAP)} lower-scored nodes not listed (query notes.db for them).\n\n")
    f.write("Provisional impact (tools/narratives.md section 4): kind (contradicts 1.0, drift 0.5) × [core 1.0 / periphery 0.3 / untagged 0.5] × [independent 1.0 / same line 0.4 / untagged 0.6] + 0.1 per further row in the same event cluster + 0.5 if a party is an agency or official (an agency word in the party or the row, an `agency divergence:` prefix, or a div tag's party= naming an agency). Cross-checks 0.6 and leads 0.5 flat (plus the agency bonus). The real impact is the narrative's own downstream closure.\n\n")
    f.write(f"Flare rule (owner, 2026-10-08): `insider=yes` marks a party with five or more firsthand or program-record rows on own role, program details or program existence ({len(INSIDERS)} such carriers: " + ", ".join(sorted(INSIDERS)[:40]) + "). A high-impact contradiction from an insider or an agency is a candidate flare (misdirection), to be tested, not assumed.\n\n")
    f.write("| Rank | Score | Source | Note / row | Date | Party | insider | agency | Kind | Event or lead | Against (agreement, elsewhere, or what settles it) | div tags |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    for i, n in enumerate(nodes[:CAP]):
        f.write(f"| {i+1} | {n['score']} | {n['src']} | {n['video']} {n['n']} | {n['date']} | {n['party']} | {'yes' if n['insider'] else ''} | {'yes' if n['agency'] else ''} | {n['kind']} | {n['event'].replace('|','/')} | {n['agreement'].replace('|','/')} | {'; '.join(f'{k}={v}' for k,v in n['div'].items())} |\n")
    by_party = Counter(n["party"] for n in nodes if n["party"])
    f.write("\n## Parties by node count (all nodes)\n\n| Party | Nodes | insider | High-impact (score >= 1.0) |\n|---|---|---|---|\n")
    for p, c in by_party.most_common(40):
        f.write(f"| {p} | {c} | {'yes' if p in INSIDERS else ''} | {sum(1 for n in nodes if n['party']==p and n['score']>=1.0)} |\n")

# ---------- speakers and signals ----------
sp_rows = defaultdict(list)
for r in Q("select * from claims"): sp_rows[canon(r["speaker"], r["video"])].append(r)
rel = Q("select * from relations")
AFFIL = {"employer", "member-of", "funder", "founder", "directs", "owner", "operator", "student-of", "patient-of"}
OPP = {"adversary", "critic"}
def rel_rows(name):
    k = name.lower(); out = []
    for r in rel:
        a = (r["a_canon"] or r["a"] or ""); b = (r["b_canon"] or r["b"] or "")
        if canon(a).lower() == k or canon(b).lower() == k: out.append(r)
    return out
od = json.load(open("research/figures/openness-dataset.json"))
cells_by_src = defaultdict(list)
for c in od["cells"]: cells_by_src[c["source"]].append(c)
def src_for(name):
    sur = name.split()[-1].lower()
    return [s for s in od["sources"] if isinstance(s.get("label"), str) and sur in s["label"].lower()]
div_by_party = Counter(n["party"] for n in nodes if n["party"])
audit_notes = defaultdict(list)
for r in Q("select * from audit_rows"): audit_notes[r["video"]].append(r)
absence = Q("select n, lead, status, sources from leads where kind='absence'")
speakers = sorted([s for s in sp_rows if len(sp_rows[s]) >= MIN_ROWS], key=lambda s: -len(sp_rows[s]))
with open(os.path.join(OUT, "speakers.md"), "w") as f, open(os.path.join(OUT, "signals.md"), "w") as g:
    f.write(f"# Speaker sheets (narrative pack, built {TODAY})\n\n{len(speakers)} carriers with {MIN_ROWS} or more claims rows ({len(sp_rows)} canonical speaker names in all; the rest are below the cap). Grouping is mechanical: parentheticals stripped, tools/name_aliases.json applied, a bare surname merged into the unique full name that carries it (an ambiguous surname goes to the most frequent full name and is flagged). Openness per topic is from research/figures/openness-dataset.json where the carrier is one of its 42 sources, else from the audit rows of the notes where the carrier is the guest. Affiliations are relations rows of kind employer, member-of, funder, founder, directs, owner, operator, student-of, patient-of; opponents are adversary and critic rows. Caps per sheet are stated inline.\n\n")
    g.write(f"# Signals: walls and what is said near them (narrative pack, built {TODAY})\n\nOwner's reading (2026-10-08): people who cannot speak about something may hint at it by what they omit, how they speak around it, or what they say offhand. For each carrier below (same {len(speakers)} as speakers.md): (1) the walls: stated declines, closed-outright and closed-subtle audit rows with the ground given, and claims rows the carrier closes; (2) near the wall: rows the carrier volunteers (move n/a) or answers partially on the same topics they close elsewhere; (3) the carrier's pseudo-declines count. A wall is a boundary, not a denial, and nothing here is evidence for the content behind it (tools/narratives.md section 6). Builders record a hint as a node with Role `signal`, never as a claim. Caps stated inline.\n\n")
    for s in speakers:
        rows = sp_rows[s]; vids = sorted({r["video"] for r in rows})
        dates = sorted({d for d in ((re.match(r"\[?(?:about |c\. )?(\d{4}(?:-\d{2}(?:-\d{2})?)?)", (videos[v].get("recorded") or "")) or re.match(r"(\d{4}(?:-\d{2}(?:-\d{2})?)?)", videos[v].get("uploaded") or "")) for v in vids if v in videos) if d for d in [d.group(1)]})
        cls = Counter(r["source_class"] for r in rows); top = Counter(r["topic"] for r in rows); mv = Counter(r["move"] for r in rows)
        amb = s.split()[-1].lower() in surname_to_full and len(surname_to_full[s.split()[-1].lower()]) > 1
        f.write(f"## {s}\n\n- Rows: {len(rows)} claims in {len(vids)} notes; recordings {dates[0] if dates else '?'} to {dates[-1] if dates else '?'}" + (" (surname ambiguous: " + ", ".join(sorted(surname_to_full[s.split()[-1].lower()])) + "; bare-surname rows were merged here)" if amb else "") + f"; insider={'yes' if s in INSIDERS else 'no'}; divergence nodes as party: {div_by_party.get(s, 0)}\n")
        f.write("- Source classes: " + ", ".join(f"{k} {v}" for k, v in cls.most_common()) + "\n- Topics: " + ", ".join(f"{k} {v}" for k, v in top.most_common(8)) + "\n- Moves (claims): " + ", ".join(f"{k} {v}" for k, v in mv.most_common()) + "\n")
        f.write("- Notes: " + "; ".join(f"{v} ({(videos.get(v, {}).get('recorded') or videos.get(v, {}).get('uploaded') or '?')[:10]})" for v in vids[:25]) + (f"; and {len(vids)-25} more" if len(vids) > 25 else "") + "\n")
        srcs = src_for(s)
        if srcs:
            f.write("- Openness map rows: " + "; ".join(f"{x['label']}: " + ", ".join(f"{k} {v}" for k, v in x["counts"].items() if v) for x in srcs) + "\n")
            closed = [c for x in srcs for c in cells_by_src[x["id"]] if c["class"] in ("closed-outright", "closed-subtle", "contested")]
            if closed: f.write("- Closed or contested topics on the map: " + "; ".join(f"{c['topic']} ({c['class']}, basis {c['basis']})" for c in closed[:20]) + (f"; {len(closed)-20} more" if len(closed) > 20 else "") + "\n")
        guest_notes = [v for v in vids if v in videos and s.split()[-1].lower() in (videos[v].get("guest") or "").lower()]
        ac = Counter()
        for v in guest_notes:
            for a in audit_notes[v]: ac[a["move"]] += 1
        if ac: f.write(f"- Audit rows in {len(guest_notes)} notes where the carrier is the guest: " + ", ".join(f"{k} {v}" for k, v in ac.most_common()) + "\n")
        rr = rel_rows(s); aff = [r for r in rr if (r["kind"] or "").split(" ")[0] in AFFIL]; opp = [r for r in rr if (r["kind"] or "").split(" ")[0] in OPP]
        if aff: f.write(f"- Affiliations ({len(aff)}; cap 25): " + "; ".join(f"{r['a']} -{r['kind']}-> {r['b']}" + (f" [{r['when_']}]" if r["when_"] else "") + f" (rel {r['n']}, {r['confidence'] or '?'})" for r in aff[:25]) + "\n")
        if opp: f.write(f"- Opponents ({len(opp)}; cap 15): " + "; ".join(f"{r['a']} -{r['kind']}-> {r['b']} (rel {r['n']})" for r in opp[:15]) + "\n")
        srcof = [r for r in rr if (r["kind"] or "").startswith("source-of")]
        if srcof: f.write(f"- Source-of edges ({len(srcof)}; cap 15): " + "; ".join(f"{r['a']} -> {r['b']}" for r in srcof[:15]) + "\n")
        f.write("\n")
        # signals
        closed_claims = [r for r in rows if r["move"] in ("closed-subtle", "closed-outright")]
        NOGROUND = re.compile(r"^(none|n/?a|not known|not stated|unknown|no ground|\s*$)", re.I)
        walls_a = [a for v in guest_notes for a in audit_notes[v] if a["move"] in ("closed-subtle", "closed-outright") or (a["move"] == "partial" and not NOGROUND.match((a["basis"] or "").strip()))]
        walls_a.sort(key=lambda a: (0 if a["move"] == "closed-outright" else 1 if a["move"] == "closed-subtle" else 2, 0 if not NOGROUND.match((a["basis"] or "").strip()) else 1))
        pseudo = sum(1 for v in guest_notes for a in audit_notes[v] if "pseudo-decline" in (a["note"] or "").lower())
        wall_topics = Counter(r["topic"] for r in closed_claims)
        if not closed_claims and not walls_a: continue
        g.write(f"## {s}\n\n- Walls: {len(closed_claims)} closed claims rows (topics: " + ", ".join(f"{k} {v}" for k, v in wall_topics.most_common(6)) + f"); {len(walls_a)} audit rows closed or with a ground; pseudo-declines noted {pseudo}\n")
        for a in walls_a[:12]:
            g.write(f"  - [{a['video']} audit {a['n']} {a['time']}] {a['move']}; basis {a['basis'] or 'none'}: Q {(a['question'] or '')[:140]} / A {(a['answer'] or '')[:160]}\n")
        if len(walls_a) > 12: g.write(f"  - ({len(walls_a)-12} more audit walls not listed)\n")
        for r in closed_claims[:10]:
            g.write(f"  - [{r['video']} claims {r['n']} {r['time']}] {r['move']} {r['topic']}: {(r['claim'] or '')[:180]}\n")
        if len(closed_claims) > 10: g.write(f"  - ({len(closed_claims)-10} more closed claims rows not listed)\n")
        near = [r for r in rows if r["topic"] in wall_topics and r["move"] in ("n/a", "partial")]
        if near:
            g.write(f"- Near the wall ({len(near)} volunteered or partial rows on the topics the carrier closes; cap 15):\n")
            for r in near[:15]:
                g.write(f"  - [{r['video']} claims {r['n']} {r['time']}] {r['move']} {r['topic']} ({r['source_class']}): {(r['claim'] or '')[:200]}\n")
        g.write("\n")
    g.write("## Absence leads (kind absence)\n\n")
    for a in absence: g.write(f"- lead {a['n']} ({a['status']}): {(a['lead'] or '')[:300]} [sources: {(a['sources'] or '')[:80]}]\n")

# ---------- seeds ----------
SEEDS = [(t["key"], t["title"], t["thesis"], t["terms"]) for t in packload.theses()]   # the pack's thesis seeds (the pack's seeds/theses.json; moved 2026-10-22)
with open(os.path.join(OUT, "seeds.md"), "w") as f:
    f.write(f"# Thesis seeds (narrative pack, built {TODAY})\n\n{_D['seeds_intro']} For each: the thesis, the terms for tools/evidence_pack.py, and a count of claims rows matching any term (substring, case-insensitive; a size signal, not a relevance measure).\n\n")
    for key, title, thesis, terms in SEEDS:
        like = " or ".join("claim like ?" for _ in terms); n = con.execute(f"select count(*) from claims where {like}", [f"%{t}%" for t in terms]).fetchone()[0]
        f.write(f"## {key}: {title}\n\n{thesis}\n\n- Terms: " + ", ".join(terms) + f"\n- Claims rows matching any term: {n}\n- Evidence pack: `python3 tools/evidence_pack.py --out wip/narratives-<date>/packs/{key}.md --title \"{title}\" --terms " + " ".join(f'"{t}"' for t in terms) + " --pages`\n\n")
    f.write(_D["other_seed_sources"])
print("pack written to", OUT); print("eras:", {k: len(v) for k, v in rows_by_era.items()}); print("contradiction nodes:", len(nodes), "insiders:", len(INSIDERS), "speakers:", len(speakers))
