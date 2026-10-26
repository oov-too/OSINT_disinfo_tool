#!/usr/bin/env python3
"""Divergence patterns: who tells the same story differently, and whether it is an agency or a person.

Owner's rule (2026-09-29): when different witnesses give diverging portions of the same story, the database notes
the divergence, especially when the diverging party is an agency rather than a person; and the divergences are
tallied to see whether one party is the source of changes generally, on specific topics, or once.

Reads notes.db only. Sources of divergences: timeline rows whose Agreement says contradicts or drifts; cross-checks
of kind contradicts; leads of kind divergence. The diverging party is the speaker of the note's own row (the row
that drifts from the database), the counter-party is the note the row is set against. Writes
research/divergence-patterns.md. Usage: python3 tools/divergences.py [--db notes.db]
"""
import re, sqlite3, sys, os, datetime
from collections import Counter, defaultdict
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
if "--help" in sys.argv or "-h" in sys.argv: sys.exit("usage: python3 tools/divergences.py [--db PATH]  (rewrites research/divergence-patterns.md from notes.db)")
DB = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else "notes.db"
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
import packload   # the pack's agencies, office-holders, canon rules, events and places ([tools.divergences]; phase 7b, 2026-10-22)
_D = packload.tool_data("divergences")
AGENCIES = list(_D["agencies"])     # bodies, offices and records: a party matching one is an agency or official
OFFICIALS = list(_D["officials"])   # office-holders by surname
SHORT = {}
try:
    s = LN.read_text(os.path.join(_T, "build_index.py"))
    for m in re.finditer(r'"([^"]+\.md)":\s*"([^"]+)"', s): SHORT[m.group(1)[:-3]] = m.group(2)
except Exception: pass
def short(slug): return SHORT.get(slug, slug)
def guest_of(slug):
    r = con.execute("select guest, speakers, host from videos where id=?", (slug,)).fetchone()
    if not r: return slug
    g = (r["guest"] or "").strip()
    if g and not g.lower().startswith(("none", "n/a")): return re.split(r"[;,(]", g)[0].strip()[:40]
    h = (r["host"] or "").strip()
    if h and not h.lower().startswith(("none", "n/a")): return re.split(r"[;,(]", h)[0].strip()[:40]
    return (r["speakers"] or slug).split(";")[0].split(",")[0].strip()[:40]
def party_of_basis(b):
    b = (b or "").strip()
    b = re.sub(r"\(.*?\)", "", b).split(",")[0].split(";")[0].split(" via ")[0].strip()
    return b[:50] or "unstated"
def is_agency(p):
    pl = " " + p.lower() + " "
    return any(re.search(r"(?<![a-z])" + re.escape(a.lower()) + r"(?![a-z])", pl) for a in AGENCIES)
def is_official(p): return any(re.search(r"(?<![a-z])" + re.escape(o.lower()) + r"(?![a-z])", p.lower()) for o in OFFICIALS)
def topic_for(video, text):
    ns = [int(x) for x in re.findall(r"claims? (\d+)", text or "")] or [int(x) for x in re.findall(r"rows? (\d+)", text or "")]
    for n in ns[:3]:
        r = con.execute("select topic from claims where video=? and n=?", (video, str(n))).fetchone()
        if r and r["topic"]: return r["topic"]
    return "unassigned"
def relink(text):
    """Links in agreement and cross-check cells are written relative to videos/; this page lives in research/."""
    def fix(m):
        name = m.group(1)
        if os.path.exists(f"videos/{name}.md"): return f"](../videos/{name}.md"
        if os.path.exists(f"books/{name}.md"): return f"](../books/{name}.md"
        return m.group(0)
    return re.sub(r"\]\((?!\.\./|https?://|#)([a-z0-9\-]+)\.md", fix, text or "")
def cut(text, n):
    """Truncate without leaving a half-written markdown link."""
    t = (text or "")
    if len(t) <= n: return t
    t = t[:n]
    k = t.rfind("[")
    if k >= 0 and t.find("](", k) < 0 or (k >= 0 and t.find(")", t.find("](", k) if t.find("](", k) >= 0 else k) < 0): t = t[:k]
    return t.rstrip() + "…"
def counterparties(text):
    return sorted(set(m.group(1) for m in LN.NOTE_STEM_LINK_RE.finditer(text or "")))   # form L4
AGENCY_CANON = [tuple(x) for x in _D["agency_canon"]]   # (regex, office): a named head or an office's spellings folded to one office
EXTRA_CANON = [tuple(x) for x in _D["extra_canon"]]     # the same for elected bodies, the executive and unnamed official sides
def agency_party(note_text, default):
    """A cross-check whose Note begins 'agency divergence: <clause>' is tallied against the office the clause names, not the witness.
    The clause is free text ('the Authority's former chief executive and his spokesman are the diverging parties'), so it is matched against the office list."""
    t = (note_text or "").strip()
    # the audit markers of schema 10 (2026-10-01) may precede the prefix: 'point: date; settled 2026-09-28: ...; agency divergence: ...'
    t = re.sub(r"^(?:\s*(?:point\s*:\s*[a-z]+|settled\s+\d{4}-\d{2}-\d{2}\s*:[^;]*|revised\s+\d{4}-\d{2}-\d{2}\s*:[^;]*|was\s*:[^;]*)\s*;\s*)+", "", t, flags=re.I)
    if not re.match(r"agency divergence\s*:", t, re.I): return default
    clause = re.split(r"\.\s|;|\bcustody:", t.split(":", 1)[1], 1)[0][:200].lower()
    for rx, name in AGENCY_CANON + EXTRA_CANON:
        if re.search(rx, clause): return name
    return "Official record (unnamed office)"
TAG_RE = re.compile(r"\[div:\s*([^\]]+)\]")
def parse_tag(text):
    m = TAG_RE.search(text or "")
    if not m: return {}
    d = {}
    for part in m.group(1).split(";"):
        if "=" in part:
            k, v = part.split("=", 1); k = k.strip().lower(); d[k] = v.strip() if k == "party" else v.strip().lower()
    return d
items = []
for r in con.execute("select * from timeline where agreement like 'contradicts%' or agreement like 'drifts%'"):
    items.append(dict(src="timeline", video=r["video"], n=r["n"], party=agency_party(r["agreement"].split(":",1)[1] if ":" in r["agreement"] else "", party_of_basis(r["speaker_basis"])), kind=r["agreement"].split(":")[0].strip(), tag=parse_tag(r["agreement"]),
                      topic=topic_for(r["video"], r["link"]), against=counterparties(r["agreement"]), text=cut(relink(r["event"]),160), detail=cut(relink(r["agreement"]),260)))
for r in con.execute("select * from cross_checks where kind='contradicts' and (settled is null or settled='')"):   # a settled contradiction was the database's own misreading, since corrected: not a teller's divergence (2026-10-01)
    items.append(dict(src="cross-check", video=r["video"], n=r["n"], party=agency_party(r["note"], guest_of(r["video"])), kind="contradicts", tag=parse_tag(r["note"]),
                      topic=topic_for(r["video"], r["this_note"]), against=counterparties(r["elsewhere"]), text=cut(relink(r["this_note"]),160), detail=cut(relink(r["note"]),260)))
for r in con.execute("select * from leads where kind='divergence'"):
    notes = counterparties(r["sources"]); party = guest_of(notes[0]) if notes else "unstated"
    items.append(dict(src="lead", video=notes[0] if notes else "", n=r["n"], party=party, kind="divergence", tag=parse_tag(r["lead"]),
                      topic="lead", against=notes[1:], text=cut(relink(r["lead"]),160), detail=(r["status"] or "")))
for it in items:
    if it.get("tag", {}).get("party"): it["party"] = it["tag"]["party"]  # the tag names the diverging party when it is not the note's own speaker
    it["agency"] = is_agency(it["party"]) and it["party"] not in tuple(_D["non_parties"])
    it["official"] = is_official(it["party"])
# normalise party names: a bare surname merges into the fullest name that ends with it
names = Counter(it["party"] for it in items)
full = {}
for p in names:
    toks = p.split()
    if len(toks) >= 2:
        full.setdefault(toks[-1].lower(), []).append(p)
def canon(p):
    toks = p.split()
    if len(toks) == 1 and toks[0].lower() in full:
        cands = full[toks[0].lower()]
        return max(cands, key=lambda c: names[c])
    return p
for it in items: it["party"] = canon(it["party"])
# agency party names come from free-text prefixes ("agency divergence: the Authority's director ..."), so fold them to one name per office
def agency_canon(p):
    low = p.lower()
    if not re.match(_D["agency_heads_rx"], low) and not (is_agency(p) or re.search(r"agency divergence|'s (director|leadership|deck|position|account|record|report|statement|reply|answer)|\(", low)):
        return p
    for rx, name in AGENCY_CANON:
        if re.search(rx, low): return name
    return p
for it in items:
    if it["src"] == "cross-check" and (it["detail"] or "").lower().startswith("agency divergence") or it["party"] in tuple(_D["agency_heads"]) or is_agency(it["party"]):
        it["party"] = agency_canon(it["party"])
PARTY_ALIASES = dict(_D["party_aliases"])   # a recorded party form -> the party's name (a host recorded by first name)
for it in items:
    if it["party"] in PARTY_ALIASES: it["party"] = PARTY_ALIASES[it["party"]]
EVENTS = dict(_D["events"])   # event -> the lower-cased words that place a divergence at it
PLACES = dict(_D["places"])   # place -> its words
def hits(lex, text):
    t = (text or "").lower(); return [k for k, ws in lex.items() if any(w in t for w in ws)]
for it in items:
    blob = f"{it['text']} {it['detail']}"
    it["events"] = hits(EVENTS, blob); it["places"] = hits(PLACES, blob)
    it["year"] = ""
    if it["src"] == "timeline":
        r = con.execute("select sortable from timeline where video=? and n=?", (it["video"], it["n"])).fetchone()
        m = re.search(r"(-?\d{3,4})", (r["sortable"] or "") if r else "")
        it["year"] = m.group(1) if m else "?"
byevent = defaultdict(list); byplace = defaultdict(list); byyear = Counter(); bystory = defaultdict(list)
for it in items:
    for e in it["events"]: byevent[e].append(it)
    for pl in it["places"]: byplace[pl].append(it)
    if it["year"]: byyear[(it["year"][:3] + "0s") if it["year"].lstrip("-").isdigit() and len(it["year"].lstrip("-")) == 4 else it["year"]] += 1
    bystory[it["video"]].append(it)
# divergence tags and the three-class scoring (owner, 2026-09-29)
CLASSES = ["honest memory error", "deliberate falsehood", "sanctioned disinformation"]
def votes(it):
    """Return (E, D, S) evidence weights for one item, from its tag where present, else from what the row text lets us infer."""
    E = D = S = 0.0
    full = f"{it['text']} {it['detail']}"
    t = it.get("tag") or parse_tag(full); tagged = bool(t)
    low = full.lower()
    dir_ = t.get("dir"); core = t.get("core"); stab = t.get("stab"); indep = t.get("indep"); timing = t.get("timing"); path = t.get("path")
    if not tagged:
        # inference from what the database already records
        if it["src"] == "timeline" and it["kind"] == "drifts": core = "periphery"
        if "not independent" in low or "same speaker" in low or "same host" in low or "one source" in low: indep = "no"
        if any(w in low for w in ("anonymous", "unnamed", "withheld", "won't say", "will not say", "cannot say", "can't say")): path = "anonymous"
        if "classif" in low: path = "classified"
        if any(w in low for w in ("public record", "document", "transcript", "official record", "verified")): path = path or "document"
    if dir_ == "self": D += 1.5; S += 0.5
    elif dir_ in ("other", "neutral"): E += 1.0
    if core == "core": D += 1.0; S += 0.5
    elif core == "periphery": E += 1.0
    if stab == "verbatim": D += 1.0; S += 1.0
    elif stab == "varied": E += 1.0
    if indep == "no": S += 1.0
    elif indep == "yes": E += 0.5
    if timing == "after-challenge": D += 1.0
    elif timing == "after-publication": S += 1.0
    elif timing == "gradual": E += 1.0
    if path in ("named", "document"): E += 0.5
    elif path == "withheld": D += 0.5; S += 0.5
    elif path in ("classified", "anonymous"): S += 1.0
    if it.get("agency"): S += 1.0; E -= 0.5
    return E, D, S, tagged
for it in items:
    e, d, sc, tagged = votes(it); it["votes"] = (e, d, sc); it["tagged"] = tagged
import math
def classify3(lst):
    """Assign one of the three classes to a group of items with a confidence in [0, 1] and a label."""
    E = sum(max(0, i["votes"][0]) for i in lst); D = sum(i["votes"][1] for i in lst); S = sum(i["votes"][2] for i in lst)
    tot = E + D + S
    if tot <= 0: return ("unscored", 0.0, "none", (0, 0, 0), 0.0)
    shares = sorted([(E / tot, CLASSES[0]), (D / tot, CLASSES[1]), (S / tot, CLASSES[2])], reverse=True)
    top, second = shares[0], shares[1]
    margin = top[0] - second[0]
    coverage = sum(1 for i in lst if i["tagged"]) / len(lst)
    sample = 1 - 1 / math.sqrt(len(lst) + 1)
    conf = top[0] * (0.15 + 0.85 * coverage) * sample * (0.5 + margin)
    conf = max(0.0, min(1.0, conf))
    label = "high" if conf >= 0.6 and coverage >= 0.67 else "medium" if conf >= 0.35 and coverage >= 0.34 else "low"
    return (top[1], round(conf, 2), label, (round(E, 1), round(D, 1), round(S, 1)), round(coverage, 2))
# tallies
byparty = defaultdict(list)
for it in items: byparty[it["party"]].append(it)
def classify(lst):
    n = len(lst); topics = Counter(i["topic"] for i in lst if i["topic"] not in ("lead", "unassigned"))
    stories = len(set(i["video"] for i in lst))
    if n == 1: return "one instance"
    if topics and topics.most_common(1)[0][1] >= max(3, 0.6 * sum(topics.values())): return f"topic-specific: {topics.most_common(1)[0][0]}"
    if n >= 3 and len(topics) >= 3: return "general"
    return "few"
rows = []
for p, lst in byparty.items():
    rows.append((p, len(lst), len(set(i["video"] for i in lst)), classify(lst), is_agency(p) or is_official(p), Counter(i["topic"] for i in lst).most_common(3), Counter(i["src"] for i in lst), classify3(lst)))
rows.sort(key=lambda r: -r[1])
pairs = Counter()
for it in items:
    for a in it["against"]: pairs[(it["party"], short(a))] += 1
topics = Counter(it["topic"] for it in items)
today = datetime.date.today().isoformat()
out = [f"# Divergence patterns: who tells the same story differently\n",
       "| Field | Value |\n|---|---|",
       "| **Kind** | research (generated; regenerate with `python3 tools/divergences.py`) |",
       f"| **Built** | {today}, from notes.db: timeline rows whose Agreement contradicts or drifts, cross-checks of kind contradicts, and leads of kind divergence |",
       f"| **Counts** | {len(items)} divergence items ({sum(1 for i in items if i['src']=='timeline')} timeline, {sum(1 for i in items if i['src']=='cross-check')} cross-check, {sum(1 for i in items if i['src']=='lead')} leads); {len(byparty)} diverging parties, {sum(1 for r in rows if r[4])} of them agencies or officials |",
       "| **Rule** | Owner, 2026-09-29: diverging portions of the same story from different witnesses are always noted, especially when the diverging party is an agency rather than a person; the tallies below look for parties that are the source of changes generally, on specific topics, or once |",
       _D["related_row"],
       "How to read this page. The diverging party is the speaker of the note's own row, the one that drifts from what the database already holds; the counter-party is the note it is set against. 'Agency or official' marks parties that are bodies, offices, records or office-holders rather than private witnesses. The classification is mechanical: one instance; topic-specific when three or more divergences sit mostly in one topic; general when three or more spread across three or more topics. A high count is not a verdict: a long recording with many dated claims produces many drifts. Read the count beside the number of stories and the topics.\n",
       "## 1. Parties by number of divergences\n",
       "| Party | Divergences | Stories (notes) | Pattern | Agency or official | Topics | Sources |", "|---|---|---|---|---|---|---|"]
CLASS_SECTION = ["\n## 1b. Classification by party: honest memory error, deliberate falsehood, or sanctioned disinformation\n", "Each party's divergences are scored on the six markers of the divergence tag (tools/schema.md section 10). Where a row carries no tag yet, the tool infers what it can (a date drift is periphery; 'not independent' sets indep=no; an anonymous, withheld or classified terminal hop sets the path; an agency party lacks the means to err) and leaves the rest unscored, so confidence stays low until the backfill tags the rows. Confidence combines the winning class's share of the evidence, the margin over the runner-up, the fraction of rows tagged, and the sample size; it is a confidence in the pattern, never a verdict on a person. E, D, S are the raw evidence weights.\n", "| Party | Divergences | Class | Confidence | Label | E / D / S | Rows tagged |", "|---|---|---|---|---|---|---|"]
for p, n, st, cls, ag, tp, src, c3 in sorted(rows, key=lambda r: (-r[7][1], -r[1]))[:80]:
    CLASS_SECTION.append(f"| {p} | {n} | {c3[0]} | {c3[1]} | {c3[2]} | {c3[3][0]} / {c3[3][1]} / {c3[3][2]} | {int(c3[4]*100)}% |")
for p, n, st, cls, ag, tp, src, c3 in rows[:80]:
    out.append(f"| {p} | {n} | {st} | {cls} | {'yes' if ag else ''} | {', '.join(f'{t} {c}' for t, c in tp)} | {', '.join(f'{k} {v}' for k, v in src.items())} |")
out += CLASS_SECTION
fam = defaultdict(list)
for it in items:
    if is_agency(it["party"]) or it["party"].startswith(tuple(_D["pooled_prefixes"])): fam[it["party"].split(" / ")[0]].append(it)
out += ["\n## 2. Agencies and officials only\n", "Offices first (every row credited to the office or to one of its named heads is pooled), then each party as recorded. Agency rows are those whose Note opens 'agency divergence:' or whose tag names the office with party=.\n",
        "| Office (pooled) | Divergences | Stories | Class (confidence) | E / D / S |", "|---|---|---|---|---|"]
for f, lst in sorted(fam.items(), key=lambda kv: -len(kv[1])):
    c3 = classify3(lst); st = len(set(story_key(i) for i in lst)) if "story_key" in globals() else len(set(i["video"] for i in lst))
    out.append(f"| {f} | {len(lst)} | {st} | {c3[0]} ({c3[1]}, {c3[2]}) | {c3[3][0]:.1f} / {c3[3][1]:.1f} / {c3[3][2]:.1f} |")
out += ["\n| Party | Divergences | Stories | Pattern | Topics | Class (confidence) |", "|---|---|---|---|---|---|"]
for p, n, st, cls, ag, tp, src, c3 in rows:
    if ag: out.append(f"| {p} | {n} | {st} | {cls} | {', '.join(f'{t} {c}' for t, c in tp)} | {c3[0]} ({c3[1]}, {c3[2]}) |")
out += ["\n## 3. Pairs that diverge most\n", "| Diverging party | Against | Count |", "|---|---|---|"]
for (a, b), c in pairs.most_common(40): out.append(f"| {a} | {b} | {c} |")
out += ["\n## 4. Topics where divergence concentrates\n", "| Topic | Divergences |", "|---|---|"]
for t, c in topics.most_common(): out.append(f"| {t} | {c} |")
out += ["\n## 5. Events that attract divergence\n", "Keyword match on the diverging telling and its counter-telling; one item can count under several events.\n", "| Event | Divergences | Parties (top 3) | Agencies or officials among them | Class (confidence) |", "|---|---|---|---|---|"]
for e, lst in sorted(byevent.items(), key=lambda kv: -len(kv[1])):
    pc = Counter(i["party"] for i in lst); ag = sorted(set(i["party"] for i in lst if is_agency(i["party"]) or is_official(i["party"]))); c3 = classify3(lst)
    out.append(f"| {e} | {len(lst)} | {', '.join(f'{p} {c}' for p, c in pc.most_common(3))} | {', '.join(ag)[:120]} | {c3[0]} ({c3[1]}, {c3[2]}) |")
out += ["\n## 6. Places that attract divergence\n", "| Place | Divergences | Parties (top 3) |", "|---|---|---|"]
for pl, lst in sorted(byplace.items(), key=lambda kv: -len(kv[1])):
    pc = Counter(i["party"] for i in lst); out.append(f"| {pl} | {len(lst)} | {', '.join(f'{p} {c}' for p, c in pc.most_common(3))} |")
out += ["\n## 7. Decades (timeline items only, by the diverging row's Sortable)\n", "| Decade | Divergences |", "|---|---|"]
for y, c in sorted(byyear.items(), key=lambda kv: (kv[0] == '?', kv[0])): out.append(f"| {y} | {c} |")
out += ["\n## 8. Stories (notes) by divergence count\n", "A note with many divergences is a long, date-heavy recording or a contested one; read with the party column.\n", "| Note | Divergences | Diverging parties |", "|---|---|---|"]
for v, lst in sorted(bystory.items(), key=lambda kv: -len(kv[1]))[:40]:
    pc = Counter(i["party"] for i in lst); out.append(f"| {short(v)} | {len(lst)} | {', '.join(f'{p} {c}' for p, c in pc.most_common(3))} |")
out += ["\n## 9. The items\n", "Every divergence, by party. Each line: source, note and row, kind, topic, the diverging telling, and what it is set against.\n"]
for p, n, st, cls, ag, tp, src, c3 in rows:
    out.append(f"\n### {p} ({n}; {cls}{'; agency or official' if ag else ''}; {c3[0]}, confidence {c3[1]} {c3[2]})\n")
    for it in sorted(byparty[p], key=lambda i: (i["video"], str(i["n"]))):
        link = f"[{short(it['video'])}](../videos/{it['video']}.md)" if os.path.exists(f"videos/{it['video']}.md") else (f"[{short(it['video'])}](../books/{it['video']}.md)" if os.path.exists(f"books/{it['video']}.md") else it["video"])
        out.append(f"- {'tagged ' if it['tagged'] else ''}{it['src']} {link} {('tl ' if it['src']=='timeline' else ('cross-check ' if it['src']=='cross-check' else 'lead '))}{it['n']} ({it['kind']}; {it['topic']}): {it['text'].replace('|','/')} — against {', '.join(short(a) for a in it['against']) or 'the database'}: {it['detail'].replace('|','/')}")
LN.write_text("research/divergence-patterns.md", "\n".join(out) + "\n")
print(f"wrote research/divergence-patterns.md: {len(items)} items, {len(byparty)} parties, {sum(1 for r in rows if r[4])} agencies/officials, {sum(1 for i in items if i['tagged'])} tagged")
for p, n, st, cls, ag, tp, src, c3 in rows[:14]: print(f"  {n:3d} {st:3d} {p[:28]:28} {cls[:32]:32} {c3[0][:26]:26} {c3[1]:.2f} {c3[2]:6} {'AGENCY' if ag else ''}")

# machine-readable copy for the map (tools/build_graph_data.py reads it): one object per item, with the item's own class by its markers
import json as _json
def _cls(it):
    e, d, sc = it["votes"]; m = max(e, d, sc)
    return "unscored" if m <= 0 or not it["tagged"] else CLASSES[[e, d, sc].index(m)]
_json.dump([dict(src=it["src"], video=it["video"], n=str(it["n"]), party=it["party"], kind=it["kind"], against=list(it["against"]), text=it["text"], detail=it["detail"], cls=_cls(it), agency=bool(it.get("agency"))) for it in items],
           LN.open_write("research/figures/divergences.json"), ensure_ascii=False)
