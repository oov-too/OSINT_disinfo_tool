#!/usr/bin/env python3
"""The disinformation lens (tools/platform-plan.md: the technique catalogue, the weighting rules, the database tests with
counterexamples): a lens instance's frame, from a person or a text, run over notes.db. This is the frame's own sorting, not the
database's judgement: it shows what the frame's rules would weight or discount, and where the database already cuts against
them. The instance (its person or text, its note, its subject nouns, the patterns and wording of its database tests) is the
pack's: [[lenses.instance]] and [tools.greer_lens] (phase 7b, 2026-10-22).

Usage:
  python3 tools/greer_lens.py placements                      the frame's sorting of named people (the instance file)
  python3 tools/greer_lens.py criteria                        its rules, each with its claims row and time
  python3 tools/greer_lens.py claims [--side S] [--video slug] [--limit N]
                                                              claims rows whose Speaker, or whose chain, falls on side S
                                                              (S: disclosure, control, unwitting, mixed, undecided, unplaced)
  python3 tools/greer_lens.py compare <slug> [--all]          how many of a note's rows the lens weights, discounts or leaves
                                                              unplaced, with the discounted rows listed
  python3 tools/greer_lens.py test                            the criteria the database can test (T1 to T6), with counterexamples

Reads notes.db only (run tools/build_db.py first), the core technique catalogue tools/technique-catalogue.json (general criteria with public attributions,
subject nouns as parameters) and the pack's lens instance (placements, the instance's own criteria, parameter values, public-record
checks), found through tools/packload.py (phase 1 split, 2026-10-22). Names are canonicalised through the pack's alias table as
tools/relations.py does; a placement's match terms are then searched in the Speaker cell and in the hops of the first chain
segment (text before the first '; '), longest match first.
"""
import sqlite3, sys, os, json, re
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
DB = os.path.join(ROOT, "notes.db")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import packload
_D = packload.tool_data("greer_lens")   # the instance's frame: person, note, names, test patterns and wording ([tools.greer_lens]; phase 7b)
_F = _D["frame_name"]                   # the frame's name in the output ("<frame>'s placement")
_PK = _D["placement_key"]               # the instance's key for a placement's own words

def load_lens(instance_id=None):
    """The core technique catalogue (the pack's [lenses] catalogue, tools/technique-catalogue.json) merged with a pack's lens instance (pack.toml [[lenses.instance]]):
    criteria rendered from the catalogue's templates with the instance's parameter values and qualifications, plus the instance's
    subject-content criteria, in id order; placements, sides, weighting rules and public-record checks are the instance's."""
    # the shipped catalogue carries public attributions only; the instance names the criteria it draws on and holds this project's
    # references to where each statement is held (catalogue_refs: stated_in, rows, time), phase 7a turn 3
    core = json.load(open(os.path.join(ROOT, packload.pack()["lenses"].get("catalogue", "tools/technique-catalogue.json")), encoding="utf-8"))
    inst, _ = packload.lens_instance(instance_id or _D["instance"] or packload.pack()["lenses"]["instance"][0]["id"])
    use = set(inst.get("catalogue_criteria") or [c["id"] for c in core["criteria"]])
    refs = inst.get("catalogue_refs", {})
    crit = []
    for c in core["criteria"]:
        if c["id"] not in use: continue
        vals = inst.get("parameters", {}).get(c["id"], {})
        ref = refs.get(c["id"], c["source"])
        crit.append({"id": c["id"], "statement": c["statement"].format(**vals), "rows": ref.get("rows", []), "time": ref.get("time", ""),
                     "qualification": inst.get("qualifications", {}).get(c["id"], c.get("qualification", "")), "role": c["role"], "db_test": c["db_test"]})
    crit += inst["criteria"]
    crit.sort(key=lambda c: int(re.sub(r"\D", "", c["id"])))
    return {"source": inst["source"], "sides": inst["sides"], "criteria": crit, "placements": inst["placements"],
            "weighting_rules": inst["weighting_rules"], "public_record_checks": inst["public_record_checks"], "core": core, "instance": inst}
LENS = load_lens()
FRAME_NOTE = _D["frame_note"]   # the note the frame was catalogued from

_ALIAS = {}
_ap = packload.vocabulary_path("name_aliases")   # the pack's alias table ([vocabulary] name_aliases)
if _ap and os.path.exists(_ap):
    for _k, _vs in json.load(open(_ap, encoding="utf-8")).items():
        if _k == "_comment": continue
        _ALIAS[_k.lower()] = _k
        for _v in _vs: _ALIAS[_v.lower()] = _k
def canon(term):
    t = re.sub(r"^(?:Dr\.?|Rep\.?|Col\.?|Colonel|Major|Gen\.?|Lt\.?|Adm\.?|Admiral|Prof\.?|Mr\.?|Mrs\.?|Ms\.?|Senator|Sen\.?)\s+", "", term.strip(), flags=re.I)
    return _ALIAS.get(t.lower(), t)

PL = LENS["placements"]
TERMS = []  # (term, placement index), longest first
for i, pl in enumerate(PL):
    for t in pl["match"]: TERMS.append((t, i))
    TERMS.append((pl["canonical"], i)) if not pl["canonical"].startswith("(") else None
TERMS.sort(key=lambda x: -len(x[0]))
_RX = {t: re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])") for t, _ in TERMS}

def _strip(s): return re.sub(r"\s*\([^)]*\)", "", s or "").strip()

def place_name(text, chain=False):
    """Return the placement index for a name or text fragment, longest match first; None if no placement matches."""
    if not text: return None
    c = canon(_strip(text))
    for i, pl in enumerate(PL):  # exact canonical or match-term equality first
        if c == pl["canonical"] or c in pl["match"] or canon(c) == canon(pl["canonical"]): return i
    for t, i in TERMS:
        pl = PL[i]
        if chain and not pl.get("chain_match", True): continue
        s = text
        for ex in pl.get("exclude", []): s = s.replace(ex, " ")
        if _RX[t].search(s): return i
    return None

def hops(chain):
    """Hops of the first chain segment after the speaker node: '2: A <- B <- C (type).' -> ['B', 'C']"""
    seg = (chain or "").split("; ")[0]
    seg = re.sub(r"^\s*\d+:\s*", "", seg)
    parts = [p.strip() for p in seg.split("<-")]
    return parts[1:]

def classify(speaker, cls, chain, attribution=""):
    """Returns (verdict, reason) with verdict in weight, discount, unplaced."""
    si = place_name(speaker)
    hs = [(h, None if re.search(r"friend of|close friend|closest friend", h) else place_name(h, chain=True)) for h in hops(chain)]
    ctrl_hops = [(h, i) for h, i in hs if i is not None and PL[i]["side"] == "control" and i != si]
    disc_hops = [(h, i) for h, i in hs if i is not None and PL[i]["side"] == "disclosure" and i != si]
    if si is not None and PL[si]["side"] == "control":
        return "discount", f"speaker {PL[si]['name']} placed control ({PL[si][_PK]})"
    if ctrl_hops:
        return "discount", f"chain rests on {PL[ctrl_hops[0][1]]['name']} (placed control)"
    if si is not None and PL[si]["side"] == "disclosure":
        return "weight", f"speaker {PL[si]['name']} placed disclosure"
    if si is not None and PL[si]["side"] == "unwitting":
        if cls == "firsthand": return "weight", f"speaker {PL[si]['name']} placed unwitting; firsthand (C11)"
        return "unplaced", f"speaker {PL[si]['name']} placed unwitting; not firsthand (C11, C17)"
    if disc_hops:
        return "weight", f"chain rests on {PL[disc_hops[0][1]]['name']} (placed disclosure)"
    if si is not None:
        return "unplaced", f"speaker {PL[si]['name']} placed {PL[si]['side']}"
    return "unplaced", f"speaker and chain not placed by {_F}"

def side_of(speaker, chain):
    si = place_name(speaker)
    sides = set()
    if si is not None: sides.add(PL[si]["side"])
    for h in hops(chain):
        i = place_name(h, chain=True)
        if i is not None: sides.add(PL[i]["side"])
    return sides or {"unplaced"}

def con(): return sqlite3.connect(DB)
def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default
def cut(s, n): s = (s or "").replace("\n", " "); return s if len(s) <= n else s[:n - 1] + "…"

def cmd_placements():
    print(f"| Name | {_F}'s placement | {_D['reason_header']} | Row (time) |")
    print("|---|---|---|---|")
    order = ["control", "mixed", "undecided", "unwitting", "disclosure"]
    for side in order:
        for pl in PL:
            if pl["side"] != side: continue
            rows = ", ".join(map(str, pl["rows"]))
            print(f"| {pl['name']} | {side}: {pl[_PK]} | {pl['reason']} | {rows} ({pl['time']}) |")
    print(f"\n{len(PL)} placements: " + ", ".join(f"{s} {sum(1 for p in PL if p['side'] == s)}" for s in order))

def cmd_criteria():
    for c in LENS["criteria"]:
        t = f" [database test {c['db_test']}]" if c["db_test"] else ""
        q = f" Qualification: {c['qualification']}" if c["qualification"] else ""
        print(f"{c['id']} ({c['role']}; rows {', '.join(map(str, c['rows']))}; {c['time']}){t}: {c['statement']}{q}")

def cmd_claims():
    side = arg("--side"); video = arg("--video"); limit = int(arg("--limit", "200"))
    q = "select video, n, time, speaker, source_class, claim, chain, attribution from claims"
    p = []
    if video: q += " where video = ?"; p.append(video)
    n = 0
    for v, rn, t, sp, cls, cl, ch, at in con().execute(q, p):
        sides = side_of(sp, ch)
        if side and side not in sides: continue
        verdict, why = classify(sp, cls, ch, at)
        n += 1
        if n <= limit: print(f"{v} #{rn} {t} [{sp}; {cls}] {verdict}: {why} | {cut(cl, 140)}")
    print(f"-- {n} rows" + (f" on side {side}" if side else "") + (f" in {video}" if video else "") + (f" (first {limit} shown)" if n > limit else ""))

def cmd_compare():
    slug = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
    if not slug: sys.exit("compare needs a note slug")
    rows = con().execute("select n, time, speaker, source_class, claim, chain, attribution from claims where video = ? order by rowid", [slug]).fetchall()
    if not rows: sys.exit(f"no claims rows for {slug}")
    tally = {"weight": 0, "discount": 0, "unplaced": 0}; reasons = {}; disc = []
    for rn, t, sp, cls, cl, ch, at in rows:
        v, why = classify(sp, cls, ch, at)
        tally[v] += 1; reasons.setdefault(v, {}); reasons[v][why] = reasons[v].get(why, 0) + 1
        if v == "discount": disc.append((rn, t, sp, cls, why, cl))
    tot = len(rows)
    print(f"{slug}: {tot} claims rows; weighted {tally['weight']} ({100*tally['weight']/tot:.0f}%), discounted {tally['discount']} ({100*tally['discount']/tot:.0f}%), unplaced {tally['unplaced']} ({100*tally['unplaced']/tot:.0f}%)")
    for v in ("weight", "discount", "unplaced"):
        for why, c in sorted(reasons.get(v, {}).items(), key=lambda x: -x[1])[:8]:
            print(f"  {v:8} {c:5}  {why}")
    lim = None if "--all" in sys.argv else 40
    print(f"discounted rows{'' if lim is None or len(disc) <= lim else f' (first {lim} of {len(disc)})'}:")
    for rn, t, sp, cls, why, cl in (disc if lim is None else disc[:lim]):
        print(f"  #{rn} {t} [{sp}; {cls}] {why} | {cut(cl, 110)}")

def _rows_in(cell):
    """claims row numbers named in a cross-check cell ('rows 583, 585', 'row 140', 'claims 13, 14', 'claims 67 to 69')."""
    out = []
    for m in re.finditer(r"\b(?:rows?|claims)\s+((?:M?\d+(?:\s*(?:,|and|to)\s*)?)+)", cell or ""):
        chunk = m.group(1)
        for a, b in re.findall(r"(M?\d+)\s*to\s*(M?\d+)", chunk):
            if a.isdigit() and b.isdigit() and int(b) - int(a) < 40: out += [str(x) for x in range(int(a), int(b) + 1)]
        out += re.findall(r"M?\d+", chunk)
    return list(dict.fromkeys(out))

def cmd_test():
    db = con()
    ctrl = {i for i, p in enumerate(PL) if p["side"] == "control"}
    disc = {i for i, p in enumerate(PL) if p["side"] == "disclosure"}
    counter = {}
    spk = {}
    def speaker_of(video, n):
        k = (video, str(n))
        if k not in spk:
            r = db.execute("select speaker from claims where video=? and n=?", k).fetchone()
            spk[k] = r[0] if r else None
        return spk[k]
    def origin(sp, ch):
        """placement of the row's origin: the last placed hop of the first chain segment, else the speaker"""
        i = place_name(sp)
        for h in hops(ch):
            j = place_name(h, chain=True)
            if j is not None: i = j
        return i
    def is_frame(x):
        x = _strip(x or "")
        return canon(x) == _D["frame_person"] or x in tuple(_D["frame_person_forms"])
    # T1 (C6, C9)
    print("T1 (C6 and C9). Control-side people whose own claims the cross-check tables record as corroborated by an independent route")
    print(_D["test_text"]['T1b'])
    t1 = {}
    for video, xn, kind, this, elsew, verdict, note in db.execute("select video, n, kind, this_note, elsewhere, verdict, note from cross_checks where kind='corroborates' and verdict in ('direct','partial')"):
        indep = bool(re.search(r"\bIndependent\b|\bindependent of\b|\bindependently\b", note or "")) and not re.search(r"[Nn]ot independent|same speaker|same teller|retelling|same host|Same speaker|Same teller", note or "")
        if not indep: continue
        a_side = [(video, rn) for rn in _rows_in(this)]
        b_side = []
        for link, rest in re.findall(r"\]\(([^)]+\.md)\)([^\[]*)", elsew or ""):
            b_side += [(os.path.basename(link)[:-3], rn) for rn in _rows_in(rest)]
        def placed(side):
            return [(v, rn, place_name(speaker_of(v, rn))) for v, rn in side if speaker_of(v, rn)]
        A, B = placed(a_side), placed(b_side)
        for mine, other in ((A, B), (B, A)):
            if not [x for x in other if x[2] not in ctrl]: continue
            for v, rn, i in mine:
                if i in ctrl: t1.setdefault((PL[i]["name"], v, rn), []).append(f"{video} cross-check {xn} ({verdict})")
    per = {}
    for (name, v, rn), refs in sorted(t1.items()):
        per.setdefault(name, []).append(f"{v} claims {rn} [" + "; ".join(dict.fromkeys(refs)) + "]")
    for name, items in sorted(per.items(), key=lambda x: -len(x[1])):
        print(f"   COUNTEREXAMPLE {name} ({len(items)} rows): " + " | ".join(items[:6]) + (" | ..." if len(items) > 6 else ""))
    counter["T1"] = len(t1)
    if not t1: print("   none found")
    # T2 (C12, C20)
    print(_D["test_text"]['T2a'])
    print(_D["test_text"]['T2b'])
    rx = re.compile(_D["t2_denial_rx"], re.I)   # a denial that the frame's own side holds the technology
    rx2 = re.compile(_D["t2_denial_rx2"], re.I)
    by = {}
    for v, rn, sp, cl, ch, at in db.execute("select video, n, speaker, claim, chain, attribution from claims"):
        if (at or "").startswith("n/a"): continue
        if not (rx.search(cl or "") or rx2.search(cl or "")): continue
        if v == FRAME_NOTE and _D["frame_speaker_prefix"] and (sp or "").startswith(_D["frame_speaker_prefix"]): continue  # the frame's own speaker reporting others' denials
        i = origin(sp, ch)
        if i is not None and PL[i]["name"] == _D["frame_person"]: continue
        key = PL[i]["name"] if i is not None else _strip(sp)
        by.setdefault(key, []).append((v, rn, cut(cl, 120), PL[i]["side"] if i is not None else "unplaced"))
    c2 = 0
    for name, lst in sorted(by.items(), key=lambda x: -len(x[1])):
        side = lst[0][3]; flag = "COUNTEREXAMPLE " if side == "disclosure" else ""
        c2 += bool(flag)
        print(f"   {flag}{name} ({side}; {len(lst)} rows): " + "; ".join(f"{v} #{rn} \"{c}\"" for v, rn, c, _ in lst[:3]))
    print("   (control-side deniers are consistent with C12; unplaced ones are rows the lens would count as uninformed or disinforming; review each, the pattern is textual)")
    counter["T2"] = c2
    # T3 (C4, C5, C13)
    print(_D["test_text"]['T3a'])
    H = _D["t3_hostile_rx"]
    VS = _D["t3_beings_rx"]   # the frame's subject nouns
    rxh = re.compile(H + r"[^.;]{0,50}\b" + VS + r"\b|\b" + VS + r"\b[^.;]{0,50}" + H, re.I)
    rxneg = re.compile(_D["t3_negation_rx"], re.I)
    byh = {}
    for v, rn, sp, cl, ch, at in db.execute("select video, n, speaker, claim, chain, attribution from claims"):
        if (at or "").startswith("n/a") or v == FRAME_NOTE: continue
        if rxh.search(cl or "") and not rxneg.search(cl or ""):
            i = origin(sp, ch)
            if i is not None and PL[i]["name"] == _D["frame_person"]: continue
            key = PL[i]["name"] if i is not None else _strip(sp)
            byh.setdefault(key, []).append((v, rn, cut(cl, 110), PL[i]["side"] if i is not None else "unplaced"))
    c3 = 0
    for name, lst in sorted(byh.items(), key=lambda x: -len(x[1])):
        side = lst[0][3]
        if side == "unplaced" and len(lst) < 2: continue
        flag = "COUNTEREXAMPLE " if side == "disclosure" else ""
        c3 += bool(flag)
        print(f"   {flag}{name} ({side}; {len(lst)} rows): " + "; ".join(f"{v} #{rn} \"{c}\"" for v, rn, c, _ in lst[:2]))
    print(f"   ({len(byh)} speakers or origins in all; unplaced ones with a single row not shown; the pattern is textual, so review each)")
    counter["T3"] = c3
    # T4 (C9 applied to the frame's own sourcing)
    print(_D["test_text"]['T4a'])
    print("   his interviewee, colleague or client, and rows of his note that rely on such a person's words or document (not rows that criticise them).")
    t4 = 0
    for n, a, b, kind, what in db.execute("select n, a, b, kind, what from relations"):
        if not (is_frame(a) or is_frame(b)): continue
        other = b if is_frame(a) else a
        k = (kind or "").split(" ")[0]
        i = place_name(other)
        if i not in ctrl: continue
        if (k == "source-of" and is_frame(b)) or (k == "interviewer" and is_frame(a)) or k in ("colleague", "employer"):
            t4 += 1; print(f"   COUNTEREXAMPLE relation {n}: {a} | {b} | {kind} | {cut(what, 110)}")
    for rn, sp, ch, cl in (db.execute("select n, speaker, chain, claim from claims where video=? and speaker like ?", [FRAME_NOTE, _D["frame_speaker_prefix"] + "%"]) if _D["frame_speaker_prefix"] else []):
        for h in hops(ch):
            if re.search(r"friend of|close friend|closest friend|public record|public position|public statements", h): continue
            i = place_name(h, chain=True)
            if i in ctrl and PL[i]["name"] not in _D["t4_exempt"]:
                t4 += 1; print(f"   COUNTEREXAMPLE {_F} note claims {rn}: relies on {PL[i]['name']} ({cut(h, 60)}) | {cut(cl, 100)}"); break
    counter["T4"] = t4
    if not t4: print("   none found")
    # T5 (C15)
    print(_D["test_text"]['T5a'])
    t5c = t5d = 0
    for v, rn, sp, cl in db.execute("select video, n, speaker, claim from claims where topic like ? and source_class='firsthand'", ["%" + _D["t5_topic"] + "%"]):
        i = place_name(sp)
        if i is None: continue
        if i in ctrl:
            if not re.search(r"threat|security|harass|intimidat|surveil|Havana|attack|followed|reprisal|killed|smear|stalk", cl or "", re.I): continue
            if re.search(r"\b(?:they|people|patients|some of them|witnesses|one person)\b", (cl or "")[:40], re.I): continue
            t5c += 1; print(f"   COUNTEREXAMPLE {PL[i]['name']} (control): {v} #{rn} {cut(cl, 120)}")
        elif i in disc: t5d += 1
    counter["T5"] = t5c
    print(f"   consistent with C15: {t5d} firsthand threat or risk rows by disclosure-side speakers; counterexamples: {t5c}")
    # T6 (C14, C16)
    print(_D["test_text"]['T6a'])
    t6 = 0; seen6 = set()
    for n, a, b, kind, what in db.execute("select n, a, b, kind, what from relations where kind like 'adversary%' or what like '%red team%' or what like '%red-team%' or what like '%bona fide%' or what like '%made a bump%' or what like '%vet his whistleblowers%'"):
        if not is_frame(b): continue
        i = place_name(a)
        if i is None or PL[i]["side"] not in ("disclosure", "unwitting"): continue
        t6 += 1
        print(f"   COUNTEREXAMPLE relation {n}: {a} | {b} | {kind} | {cut(what, 110)} ({_F} places {PL[i]['name']}: {PL[i]['side']}, {PL[i][_PK]})")
    counter["T6"] = t6
    if not t6: print("   none found")
    tot = sum(counter.values())
    print("\nCriteria tested: C4, C5, C6, C9, C12, C13, C14, C15, C16, C20 (tests T1 to T6). Counterexamples flagged: " + str(tot) + " (" + ", ".join(f"{k} {v}" for k, v in counter.items()) + ").")
    print("A flag is a lead, not a verdict: each should be read on both sides before it is cited.")

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"placements": cmd_placements, "criteria": cmd_criteria, "claims": cmd_claims, "compare": cmd_compare, "test": cmd_test}.get(c, lambda: sys.exit(__doc__))()
