#!/usr/bin/env python3
"""Look up birth and death years for the people on the map (owner, 2026-10-07): Wikidata search by name, the candidate
checked against what the ledger says the person is (their role descriptions in the notes and their section), so a name
shared by several people picks the one the ledger means. Writes research/people-dates.md (the register the map builder
reads) and checkpoints every answer to wip/people-dates/progress.jsonl so a stopped run resumes without repeating a query.

  python3 tools/people_dates.py            # look up everyone not yet in the checkpoint, then write the register
  python3 tools/people_dates.py --wiki     # the path to use: 50 names a request via Wikipedia titles, then Wikidata entities
  python3 tools/people_dates.py --sparql   # not recommended: the query service penalises batches (1000-second waits)
  python3 tools/people_dates.py --write    # only rewrite the register from the checkpoint
  python3 tools/people_dates.py --retry-low   # look up again the names that got no or a low-confidence answer

Confidence: high = one human candidate, or the best candidate's description matches the ledger's roles;
medium = several candidates and a weaker match; low = a single candidate with no role overlap (kept in the register,
not used by the map until someone checks it); none = nothing found or nothing human. Polite rate: 0.4 s between requests.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
DATA = os.path.join(ROOT, "research/figures/graph-data.json")
REG = os.path.join(ROOT, "research/people-dates.md")
WIP = os.path.join(ROOT, "wip/people-dates"); CK = os.path.join(WIP, "progress.jsonl")
UA = {"User-Agent": "ledger-people-dates/1.0 (research register; contact via the project owner)"}
GAP = 1.2   # Wikidata answered 429 at 0.4 s; 1.2 s with a backoff keeps the run polite
import packload; _D = packload.tool_data("people_dates")   # the pack's subject words and the register's founding note ([tools.people_dates]; phase 7b)
GROUP_NAME = dict(_D["group_words"])   # a map group (subject) -> words a Wikipedia description of its people tends to carry
SKIP = re.compile(r"\(unnamed\)|unnamed|anonymous|^u/|^Mr\.? [A-Z]\b|^Mrs?\b|^the |^a |^an |^his |^her |'s |^Dr\.? ?$|^[A-Z]\.?$|personnel|officials?$|^\w+ family$|caller|viewer \d|^Viewer|^source$", re.I)
STOP = set("the a an and of in at to for from by with on as is was were be his her their he she they who which that this these those or not but also american british german french russian former retired".split())

def get(url):
    for attempt in range(5):
        time.sleep(GAP)
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except urllib.error.HTTPError as ex:
            if ex.code != 429 or attempt == 4: raise
            wait = int(ex.headers.get("Retry-After", "0") or 0) or 20 * (attempt + 1)
            print(f"  429, waiting {wait}s", flush=True); time.sleep(wait)

def toks(s): return {t for t in re.findall(r"[a-z][a-z\-]{2,}", (s or "").lower()) if t not in STOP}

def year_of(claim):
    try:
        v = claim["mainsnak"]["datavalue"]["value"]; t = v["time"]; prec = v.get("precision", 9)
    except (KeyError, TypeError): return None
    m = re.match(r"([+-])(\d{1,16})-", t)
    if not m: return None
    y = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
    return {"y": y, "approx": prec < 9}

def lookup(name, roles, group):
    """-> dict(born, died, approx, qid, label, description, confidence, why) or None"""
    q = urllib.parse.quote(name)
    s = get(f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}&language=en&type=item&limit=7&format=json")
    cands = s.get("search", [])
    if not cands: return None
    ids = "|".join(c["id"] for c in cands)
    e = get(f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={ids}&props=claims|descriptions|labels|sitelinks&languages=en&format=json")
    want = toks(" ".join(roles.values())) | toks(GROUP_NAME.get(group, ""))
    scored = []
    for c in cands:
        ent = e.get("entities", {}).get(c["id"], {}); cl = ent.get("claims", {})
        human = any(x.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5" for x in cl.get("P31", []))
        if not human: continue
        desc = (ent.get("descriptions", {}).get("en", {}) or {}).get("value", "") or c.get("description", "")
        have = toks(desc) | toks(" ".join(a for a in c.get("aliases", [])))
        overlap = len(want & have)
        # a role word class shared with the description counts extra (physicist, musician, astronaut, general, senator...)
        born = next((year_of(x) for x in cl.get("P569", []) if year_of(x)), None)
        died = next((year_of(x) for x in cl.get("P570", []) if year_of(x)), None)
        links = len(ent.get("sitelinks", {}))
        exact = c.get("label", "").lower() == name.lower() or name.lower() in [a.lower() for a in c.get("aliases", [])]
        scored.append(dict(qid=c["id"], label=c.get("label", ""), description=desc, overlap=overlap, links=links, exact=exact, born=born, died=died))
    return pick(name, scored)

def pick(name, scored):
    """choose among human candidates [{qid,label,description,overlap,links,exact,born,died}] and grade the choice"""
    if not scored: return None
    scored.sort(key=lambda x: (x["overlap"], x["exact"], x["links"]), reverse=True)
    best = scored[0]
    if not best["born"] and not best["died"]: return dict(**best, confidence="none", why="no dates on the entity")
    others = [x for x in scored[1:] if x["born"]]
    if best["overlap"] >= 2 or (best["overlap"] >= 1 and (len(scored) == 1 or best["overlap"] > max([x["overlap"] for x in others] or [0]))): conf, why = "high", f"roles match ({best['overlap']} shared terms)"
    elif len(scored) == 1 and best["exact"] and len(name.split()) >= 2: conf, why = "high", "the one human of that name"
    elif best["overlap"] >= 1: conf, why = "medium", "weak role match among several candidates"
    elif len(scored) == 1 or (best["exact"] and best["links"] >= 15 and all(x["links"] < best["links"] / 4 for x in others)): conf, why = "low" if len(name.split()) == 1 else "medium", "single or dominant candidate, no role overlap"
    else: conf, why = "none", "several candidates and no role overlap"
    return dict(**best, confidence=conf, why=why)

SPARQL = "https://query.wikidata.org/sparql"
def sparql_batch(names):
    """one query for up to 40 names: humans whose label or alias is exactly the name, with dates, description and sitelink count"""
    esc = lambda n: n.replace("\\", "\\\\").replace('"', '\\"')
    vals = " ".join(f'"{esc(n)}"@en' for n in names)
    q = f"""SELECT ?name ?item ?desc ?born ?bp ?died ?dp ?links WHERE {{
  VALUES ?name {{ {vals} }}
  ?item rdfs:label|skos:altLabel ?name ; wdt:P31 wd:Q5 .
  OPTIONAL {{ ?item p:P569/psv:P569 [ wikibase:timeValue ?born ; wikibase:timePrecision ?bp ] }}
  OPTIONAL {{ ?item p:P570/psv:P570 [ wikibase:timeValue ?died ; wikibase:timePrecision ?dp ] }}
  OPTIONAL {{ ?item schema:description ?desc FILTER(lang(?desc) = "en") }}
  OPTIONAL {{ ?item wikibase:sitelinks ?links }}
}}"""
    for attempt in range(5):
        time.sleep(2)
        req = urllib.request.Request(SPARQL + "?format=json&query=" + urllib.parse.quote(q), headers={**UA, "Accept": "application/sparql-results+json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r: return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as ex:
            if ex.code not in (429, 500, 502, 503, 504) or attempt == 4: raise
            wait = int(ex.headers.get("Retry-After", "0") or 0) or 30 * (attempt + 1); print(f"  {ex.code}, waiting {wait}s", flush=True); time.sleep(wait)

def sparql_year(v, prec):
    if not v: return None
    m = re.match(r"(-?)(\d+)-", v)
    if not m: return None
    y = int(m.group(2)) * (-1 if m.group(1) else 1)
    if y <= 0: y -= 1   # the query service writes BC years astronomically (year 0 = 1 BC); the register writes 427 BC as -427
    return {"y": y, "approx": int(prec or 11) < 9}

def run_sparql(people, group, ck):
    todo = [(i, p) for i, p in enumerate(people) if p["label"] not in ck]
    print(f"SPARQL: {len(todo)} names to look up in batches of 40")
    with LN.open_append(CK) as f:
        for b in range(0, len(todo), 40):
            chunk = todo[b:b + 40]; ask = [p["label"] for i, p in chunk if not SKIP.search(p["label"]) and len(p["label"]) >= 3]
            try: rows = sparql_batch(ask) if ask else []
            except Exception as ex: print(f"  batch {b // 40} failed: {type(ex).__name__}; left for the next run", flush=True); continue
            by = collections.defaultdict(dict)
            for r in rows:
                nm = r["name"]["value"]; qid = r["item"]["value"].rsplit("/", 1)[-1]; c = by[nm].get(qid)
                if not c: c = by[nm][qid] = dict(qid=qid, label=nm, description=r.get("desc", {}).get("value", ""), links=int(r.get("links", {}).get("value", 0)), exact=True, born=None, died=None)
                if not c["born"]: c["born"] = sparql_year(r.get("born", {}).get("value"), r.get("bp", {}).get("value"))
                if not c["died"]: c["died"] = sparql_year(r.get("died", {}).get("value"), r.get("dp", {}).get("value"))
            for i, p in chunk:
                name = p["label"]
                if name not in ask: rec = dict(name=name, checked=time.strftime("%Y-%m-%d"), result=None, skipped="descriptor, not a findable name")
                else:
                    want = toks(" ".join(p.get("roles", {}).values())) | toks(GROUP_NAME.get(group[i] if group and i < len(group) else "other", ""))
                    cands = [dict(c, overlap=len(want & toks(c["description"]))) for c in by.get(name, {}).values()]
                    rec = dict(name=name, checked=time.strftime("%Y-%m-%d"), via="sparql", result=pick(name, cands))
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush(); ck[name] = rec
            print(f"  {min(b + 40, len(todo))} of {len(todo)}", flush=True)

WP = "https://en.wikipedia.org/w/api.php"; WD = "https://www.wikidata.org/w/api.php"
def plausible(res, p):
    """the candidate's life must cover the years the ledger reports the person involved in something (people row `ays`, from the dated timeline:
    events naming them where they are not the teller, births and deaths excluded). Events before birth are the strong sign of a namesake; events after
    death are tolerated up to a point (posthumous publications, declassifications). -> (ok, note)"""
    if not res: return True, ""
    ys = (p or {}).get("ays") or ([p["fy"]] if (p or {}).get("fy") is not None else [])
    if not ys: return True, "no involvement years to check against"
    b = (res.get("born") or {}).get("y"); d = (res.get("died") or {}).get("y")
    before = [y for y in ys if b is not None and y < b - 1]
    after = [y for y in ys if d is not None and y > d + 3]
    if before and (len(before) > 1 or len(ys) <= 2 or len(before) / len(ys) > 0.2): return False, f"{len(before)} of {len(ys)} involvement years fall before the candidate's birth ({b})"
    if after and d >= 1850 and len(after) / len(ys) > 0.5: return False, f"{len(after)} of {len(ys)} involvement years fall after the candidate's death ({d})"   # a historical figure (died before 1850) is only ever involved posthumously: editions, translations, citations; the rule catches modern namesakes
    return True, f"life {b or '?'} to {d or 'living'} covers the ledger's involvement years {min(ys)} to {max(ys)}"

def run_wiki(people, group, ck):
    """the light path (owner, 2026-10-07): English Wikipedia resolves 50 names a request (redirects followed, disambiguation pages flagged),
    then Wikidata's entity API returns dates and descriptions for 50 items a request. No query service, so no query-time budget."""
    todo = [(i, p) for i, p in enumerate(people) if p["label"] not in ck]
    print(f"Wikipedia/Wikidata: {len(todo)} names to look up in batches of 50", flush=True)
    with LN.open_append(CK) as f:
        for b in range(0, len(todo), 50):
            chunk = todo[b:b + 50]; ask = [p["label"] for i, p in chunk if not SKIP.search(p["label"]) and len(p["label"]) >= 3]
            title_of, qid_of, disamb = {}, {}, set()
            try:
                if ask:
                    r = get(WP + "?action=query&format=json&redirects=1&prop=pageprops&ppprop=wikibase_item|disambiguation&titles=" + urllib.parse.quote("|".join(ask)))
                    q = r.get("query", {}); m = {n: n for n in ask}
                    for x in q.get("normalized", []): m = {k: (x["to"] if v == x["from"] else v) for k, v in m.items()}
                    for x in q.get("redirects", []): m = {k: (x["to"] if v == x["from"] else v) for k, v in m.items()}
                    pages = {pg.get("title"): pg for pg in q.get("pages", {}).values()}
                    for n, t in m.items():
                        pg = pages.get(t) or {}; pp = pg.get("pageprops", {})
                        if "disambiguation" in pp: disamb.add(n)
                        elif pp.get("wikibase_item"): qid_of[n] = pp["wikibase_item"]; title_of[n] = t
                    ents = {}
                    ids = sorted(set(qid_of.values()))
                    for k in range(0, len(ids), 50):
                        e = get(WD + "?action=wbgetentities&format=json&props=claims|descriptions&languages=en&ids=" + "|".join(ids[k:k + 50]))
                        ents.update(e.get("entities", {}))
            except Exception as ex:
                print(f"  batch {b // 50} failed: {type(ex).__name__}: {ex}; left for the next run", flush=True); continue
            for i, p in chunk:
                name = p["label"]; now = time.strftime("%Y-%m-%d")
                if name not in ask: rec = dict(name=name, checked=now, result=None, skipped="descriptor, not a findable name")
                elif name in disamb: rec = dict(name=name, checked=now, via="wikipedia", result=dict(confidence="none", why="Wikipedia title is a disambiguation page; needs the per-name search (--retry-low)"))
                elif name not in qid_of: rec = dict(name=name, checked=now, via="wikipedia", result=dict(confidence="none", why="no English Wikipedia article of that title"))
                else:
                    ent = ents.get(qid_of[name], {}); cl = ent.get("claims", {})
                    human = any(x.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5" for x in cl.get("P31", []))
                    desc = (ent.get("descriptions", {}).get("en", {}) or {}).get("value", "")
                    want = toks(" ".join(p.get("roles", {}).values())) | toks(GROUP_NAME.get(group[i] if group and i < len(group) else "other", ""))
                    born = next((year_of(x) for x in cl.get("P569", []) if year_of(x)), None); died = next((year_of(x) for x in cl.get("P570", []) if year_of(x)), None)
                    res = dict(qid=qid_of[name], label=title_of[name], description=desc, overlap=len(want & toks(desc)), links=0, exact=title_of[name] == name, born=born, died=died)
                    if not human: res.update(confidence="none", why="the article is not about a person")
                    elif not born and not died: res.update(confidence="none", why="no dates on the item")
                    elif not plausible(res, p)[0]: res.update(confidence="none", why="a namesake: " + plausible(res, p)[1])
                    elif res["overlap"] >= 1: res.update(confidence="high", why=f"Wikipedia article of that name; description shares {res['overlap']} term(s) with the ledger's roles")
                    elif p.get("fy") is not None: res.update(confidence="medium", why="Wikipedia article of that name; dates cover the ledger's ties; no shared role terms")
                    else: res.update(confidence="low", why="Wikipedia article of that name; nothing in the ledger to check it against")
                    rec = dict(name=name, checked=now, via="wikipedia", result=res)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush(); ck[name] = rec
            print(f"  {min(b + 50, len(todo))} of {len(todo)}", flush=True)

GENERIC = STOP | set("born known best years united states world first one two has have been who whom its after before during later early late new old well many most more other some such than then there their them into over under about between being made became become said says also only own same both each".split())
def tok_match(a, b):
    """shared terms between two token sets, a term matching another when one is a prefix of the other (3+ letters) or both share their first 6 letters: ufo ~ ufologist, intelligence ~ intelligences"""
    n = 0
    for x in a:
        if any(x == y or (len(x) >= 3 and len(y) >= 3 and (y.startswith(x) or x.startswith(y))) or (len(x) >= 6 and x[:6] == y[:6]) for y in b): n += 1
    return n

def regrade(people, group, ck):
    """second check (owner, 2026-10-07): the opening paragraph of the matched person's English Wikipedia article must share terms with what the ledger says about them.
    A namesake (a biologist for the investigator of the same name) shares none and drops to low, which the map does not use."""
    P = {p["label"]: (i, p) for i, p in enumerate(people)}
    recs = [r for r in ck.values() if r.get("result") and r["result"].get("qid") and (r["result"].get("born") or r["result"].get("died")) and r["result"].get("confidence") != "owner"]   # every match with dates, whatever its earlier grade: the grade is recomputed here
    print(f"regrade: {len(recs)} matched names", flush=True)
    title = {}
    ids = sorted({r["result"]["qid"] for r in recs})
    for k in range(0, len(ids), 50):
        e = get(WD + "?action=wbgetentities&format=json&props=sitelinks&sitefilter=enwiki&ids=" + "|".join(ids[k:k + 50]))
        for q, ent in e.get("entities", {}).items():
            t = ent.get("sitelinks", {}).get("enwiki", {}).get("title")
            if t: title[q] = t
    ip = os.path.join(WIP, "intros.json"); intro = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    ts = sorted(t for t in set(title.values()) if t not in intro)
    for k in range(0, len(ts), 20):
        r = get(WP + "?action=query&format=json&prop=extracts&exintro=1&explaintext=1&exlimit=20&redirects=1&titles=" + urllib.parse.quote("|".join(ts[k:k + 20])))
        for pg in r.get("query", {}).get("pages", {}).values(): intro[pg.get("title")] = pg.get("extract", "") or ""
        print(f"  intros {min(k + 20, len(ts))} of {len(ts)}", flush=True)
    json.dump(intro, LN.open_write(ip), ensure_ascii=False)
    out = 0
    with LN.open_append(CK) as f:
        for r in recs:
            i, p = P.get(r["name"], (None, None))
            if p is None: continue
            x = dict(r["result"]); t = title.get(x["qid"]); text = intro.get(t, "") if t else ""
            want = (toks(" ".join(p.get("roles", {}).values())) | toks(GROUP_NAME.get(group[i] if group and i < len(group) else "other", ""))) - GENERIC
            have = (toks(text) | toks(x.get("description", ""))) - GENERIC
            n = tok_match(want, have)
            ok, note = plausible(x, p)
            # a strong article match outranks the involvement test (owner, 2026-10-08): Lincoln is only ever mentioned posthumously, and one 1947 row naming another Richardson is not a namesake
            if not ok and n >= 3: x.update(confidence="medium", why=f"the article's opening shares {n} terms with the ledger's description, which outranks the involvement test ({note})")
            elif not ok: x.update(confidence="none", why="a namesake: " + note)
            elif not text: x.update(confidence="medium" if n >= 2 else "low", why=f"no English Wikipedia article to check; description shares {n} term(s) with the ledger; {note}")
            elif n >= 3: x.update(confidence="high", why=f"the article's opening shares {n} terms with the ledger's description; {note}")
            elif n >= 1: x.update(confidence="medium", why=f"the article's opening shares {n} term(s) with the ledger's description; {note}")
            else: x.update(confidence="low", why=f"the article's opening shares nothing with the ledger's description: probably a namesake; {note}")
            x["article"] = t or ""
            f.write(json.dumps(dict(name=r["name"], checked=time.strftime("%Y-%m-%d"), via=(r.get("via") or "search") + "+intro", result=x), ensure_ascii=False) + "\n"); ck[r["name"]] = dict(name=r["name"], checked=time.strftime("%Y-%m-%d"), result=x); out += 1
    print(f"regraded {out}", flush=True)

def load_ck():
    out = {}
    if os.path.exists(CK):
        for l in LN.iter_lines(CK):
            try: r = json.loads(l); out[r["name"]] = r
            except Exception: pass
    return out

def write_register(ck, people):
    rows = [r for r in ck.values() if r.get("result")]
    rows.sort(key=lambda r: r["name"].split()[-1].lower())
    today = time.strftime("%Y-%m-%d")
    h = ["# People dates register: birth and death years for the people on the map", "",
         "| | |", "|---|---|",
         "| **What this is** | Birth and death years for the people the map shows, looked up on Wikidata by name and checked against the ledger's own description of the person (their role cells in the notes and their section), so a shared name picks the person the ledger means. The map's relationship network orders generations by these years; where a person has no row here, or only a low-confidence one, it falls back to a timeline row that says they were born, then to an estimate from their earliest dated tie. |",
         "| **Columns** | `Person`, `Born`, `Died` (a leading `~` marks a date Wikidata gives only to the century or decade; negative years are BC), `Wikidata` (the item), `Described as` (Wikidata's one-line description, the disambiguation evidence), `Confidence` (high, medium, low, none), `Why`, `Checked` (the lookup date). Rows with confidence low or none stay here for a human to check and are not used by the map. |",
         "| **Tool** | `python3 tools/people_dates.py` (tools/people_dates.py; checkpoint wip/people-dates/progress.jsonl). To correct a row, edit it here and set Confidence to `owner`; the script never overwrites an `owner` row. |",
         "| **Tags** | people, dates, generations, Wikidata, relationship network |", "",
         f"Founded {today} {_D['founded_why']}. {len(rows)} rows; {sum(1 for r in rows if r['result'].get('confidence') in ('high','owner'))} high, {sum(1 for r in rows if r['result'].get('confidence')=='medium')} medium, {sum(1 for r in rows if r['result'].get('confidence')=='low')} low, {sum(1 for r in rows if r['result'].get('confidence')=='none')} none.", "",
         "## Register", "", "| Person | Born | Died | Wikidata | Described as | Confidence | Why | Checked |", "|---|---|---|---|---|---|---|---|"]
    fmt = lambda d: "" if not d else ("~" if d.get("approx") else "") + str(d["y"])
    for r in rows:
        x = r["result"]; cell = lambda s: (s or "").replace("|", "/")
        h.append(f"| {cell(r['name'])} | {fmt(x.get('born'))} | {fmt(x.get('died'))} | {x.get('qid','')} | {cell(x.get('description',''))} | {x.get('confidence','none')} | {cell(x.get('why',''))} | {r.get('checked','')} |")
    LN.write_text(REG, "\n".join(h) + "\n")
    print(f"wrote {REG}: {len(rows)} rows")

def owner_rows():
    """rows the owner corrected by hand (Confidence = owner) survive every rewrite"""
    out = {}
    if not os.path.exists(REG): return out
    for l in LN.iter_lines(REG):
        c = LN.split_row(l)
        if len(c) == 8 and c[5] == "owner":
            yr = lambda s: None if not s else dict(y=int(s.lstrip("~")), approx=s.startswith("~"))
            out[c[0]] = dict(name=c[0], checked=c[7], result=dict(born=yr(c[1]), died=yr(c[2]), qid=c[3], description=c[4], confidence="owner", why=c[6]))
    return out

def main():
    os.makedirs(WIP, exist_ok=True)
    d = json.load(open(DATA, encoding="utf-8")); people = d["people"]
    ck = load_ck(); ck.update(owner_rows())
    if "--write" in sys.argv: write_register(ck, people); return
    if "--regrade" in sys.argv:   # the second check: the matched article's opening must share terms with the ledger's description
        try: group = json.load(open(os.path.join(ROOT, "research/figures/graph-relations.json"), encoding="utf-8"))["group"]
        except Exception: group = None
        regrade(people, group, ck); write_register(ck, people); return
    if "--wiki" in sys.argv:   # the light path, and the one to use: Wikipedia titles then Wikidata entities, 50 a request
        try: group = json.load(open(os.path.join(ROOT, "research/figures/graph-relations.json"), encoding="utf-8"))["group"]
        except Exception: group = None
        run_wiki(people, group, ck); write_register(ck, people); return
    if "--sparql" in sys.argv:   # kept but not recommended: the query service's time budget triggers 1000-second penalties   # the fast path: 40 names a query; exact label or alias only, so the per-name search (no flag, or --retry-low) can follow for the misses
        try: group = json.load(open(os.path.join(ROOT, "research/figures/graph-relations.json"), encoding="utf-8"))["group"]
        except Exception: group = None
        run_sparql(people, group, ck); write_register(ck, people); return
    retry = "--retry-low" in sys.argv
    todo = [p for p in people if p["label"] not in ck or (retry and ck[p["label"]].get("result", {}).get("confidence") in (None, "low", "none") and ck[p["label"]].get("result", {}).get("confidence") != "owner")]
    print(f"{len(people)} people; {len(ck)} already checked; {len(todo)} to look up")
    group = None
    try: group = json.load(open(os.path.join(ROOT, "research/figures/graph-relations.json"), encoding="utf-8"))["group"]
    except Exception: pass
    n = 0
    with LN.open_append(CK) as f:
        for i, p in enumerate(people):
            if p not in todo: continue
            name = p["label"]
            if SKIP.search(name) or len(name) < 3:
                rec = dict(name=name, checked=time.strftime("%Y-%m-%d"), result=None, skipped="descriptor, not a findable name")
            else:
                try: res = lookup(name, p.get("roles", {}), group[i] if group and i < len(group) else "other")
                except Exception as ex: res = dict(confidence="none", why=f"lookup failed: {type(ex).__name__}"); time.sleep(3)
                rec = dict(name=name, checked=time.strftime("%Y-%m-%d"), result=res)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush(); ck[name] = rec; n += 1
            if n % 50 == 0: print(f"  {n} looked up ({name}: {res and res.get('confidence')})", flush=True)
    write_register(ck, people)

if __name__ == "__main__": main()
