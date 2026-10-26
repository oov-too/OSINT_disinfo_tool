#!/usr/bin/env python3
"""Route every document of a mirrored bulk archive into the pack's categories, by named actor (here the archive's viewers),
using only the typed layer (index title, folder, the archive's own OCR text). No page images read. The core mechanism is the
route-by-named-actor; the actors' ids, initials and identities, the categories and their words, and the page wording are the
pack's ([tools.stargate_viewer_filter]; phase 7b, 2026-10-22).

usage: stargate_viewer_filter.py --index            the whole release -> the pack's outdir
       stargate_viewer_filter.py 018 [--out page.md] one actor's page to stdout or a file

Actors are discovered from the typed layer: a role word ('VIEWER', 'SOURCE', 'MONITOR', 'INTERVIEWER') followed by a number,
transcript labels '#NN:' (the pack's interviewer labels left out), and the pack's known initials. Documents naming no actor go
to the bucket 'none'. Hand rulings in overrides.tsv are applied on every rebuild.
"""
import sqlite3, re, sys, os, collections, argparse, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import packload
_D = packload.tool_data("stargate_viewer_filter")

DB = _D["db"]
OUTDIR = _D["outdir"]
OVERRIDES = os.path.join(OUTDIR, "overrides.tsv")
MIN_DOCS = 5                      # an actor with fewer documents is filed under 'other'
INITIALS = dict(_D["initials"])   # known initials -> actor id
INTERVIEWER_LABELS = set(_D["interviewer_labels"])   # transcript labels of the interviewers, not actors
IDENT = dict(_D["ident"])         # actor id -> identity, as the pack's identities page has it
CATS = dict(_D["cats"])           # category -> its words (lower case; a word of five letters or more matches as a prefix)
DB_CATS = list(_D["db_cats"])     # the categories the database takes up (per-actor pages and the shortlists)
STOP = set(_D["stop_words"].split())   # capitalised words of the archive's forms, left out of a site's pooled nouns

ROLE = re.compile(r"(viewer|source|monitor|interviewer)(?:\s+identifier|\s+identification|\s+no\.?)?[ :#\-]{0,6}(\d{2,3}|[A-Z]{2})\b", re.I)   # no '.' or '/' between the word and the id: 'viewer. 5.' and 'Source //90' are noise
LABEL = re.compile(r"(?m)^\W{0,3}(#\d{2}(?:\.5)?)\s*:")
SITE = re.compile(r"SITE\s*#?:?\s*(\d{3,4})")


def load(con):
    return con.execute("select d.esdn,d.title,d.folder,d.date_iso,d.pages,d.ocr_quality,f.text "
                       "from docs d join fts f on f.esdn=d.esdn").fetchall()


def hit_count(k, low):
    tail = r"\w*" if len(k) >= 5 else r"s?\b"
    return len(re.findall(r"\b" + re.escape(k) + tail, low))


def classify(esdn, title, folder, date, pages, q, text):
    head = (title or "") + " " + (folder or "")
    low = (head + " " + (text or "")).lower()
    hits = {}
    for cat, kws in CATS.items():
        c = collections.Counter({k: n for k in kws if (n := hit_count(k, low))})
        if c:
            hits[cat] = c
    best, bestscore = None, 0
    for cat, c in hits.items():
        s = sum(c.values()) + 3 * sum(1 for k in c if re.search(r"\b" + re.escape(k), head.lower()))
        if s > bestscore:
            best, bestscore = cat, s
    site = SITE.search(title or "")
    return dict(esdn=esdn, title=title or "", date=date or "", pages=pages or 0,
                q=q if q is not None else 1.0, hits=hits, cat=best or "unclassified",
                score=bestscore, site=site.group(1) if site else "", ruling="", note="")


def viewers_of(title, text):
    """-> {viewer_id: role}; strict role words, transcript labels, known initials."""
    found = {}
    head = (title or "") + " " + (text or "")[:8000]
    for m in ROLE.finditer(head):
        role, v = m.group(1).lower(), m.group(2).upper()
        if v.isdigit():
            vid = v.zfill(3)
        elif v in INITIALS:
            vid, role = INITIALS[v], "initials"
        else:
            continue
        if vid == "000":
            continue
        found.setdefault(vid, role)
    for m in LABEL.finditer(text or ""):
        lab = m.group(1)
        if lab in INTERVIEWER_LABELS:
            continue
        vid = _D["label_ids"].get(lab, lab)
        found.setdefault(vid, "transcript")
    return found


def load_overrides():
    ov = {}
    if os.path.exists(OVERRIDES):
        for r in csv.DictReader(open(OVERRIDES), delimiter="\t"):
            ov[(r["esdn"], r["viewer"])] = r
    return ov


def apply_override(d, viewer, ov):
    r = ov.get((d["esdn"], viewer)) or ov.get((d["esdn"], "*"))
    if r:
        d = dict(d); d["cat"] = r["category"]; d["ruling"] = r["ruling"]; d["note"] = r["note"]
    return d


def site_targets(rows):
    sites = collections.defaultdict(lambda: dict(viewers=set(), docs=[], caps=collections.Counter(), fb=[]))
    for esdn, title, folder, date, pages, q, text in rows:
        if "SESSION DATA" not in (title or ""):
            continue
        m = SITE.search(title)
        if not m:
            continue
        s = m.group(1).zfill(4)
        x = re.sub(r"\s+", " ", text or "")
        d = sites[s]
        d["viewers"].update(re.findall(r"VIEWER:?\s*#?\s*(\w+)", title))
        d["docs"].append(esdn)
        for w in re.findall(r"\b[A-Z][a-z]{3,}\b", x):
            if w not in STOP:
                d["caps"][w] += 1
        fm = re.search(r"Site\s*:?\s*%s\s+([A-Z][^.]{5,100})" % s.lstrip("0"), x)
        if fm:
            d["fb"].append(fm.group(1).strip())
    return sites


def table(ds, cat, cap=200):
    lines = ["| ESDN | Date | Pages | OCR q | Role | Site | Title | Top words | Ruling |", "|---|---|---|---|---|---|---|---|---|"]
    for d in sorted(ds, key=lambda d: -d["score"])[:cap]:
        top = ", ".join("%s %d" % kv for kv in d["hits"].get(cat, collections.Counter()).most_common(5))
        rul = (d["ruling"] + (": " + d["note"] if d["note"] else "")).replace("|", "/")
        lines.append("| %s | %s | %d | %.2f | %s | %s | %s | %s | %s |" % (
            d["esdn"], d["date"], d["pages"], d["q"], d["role"], d["site"],
            d["title"].replace("|", "/")[:70], top, rul))
    if len(ds) > cap:
        lines.append("| ... | %d more in index.tsv | | | | | | | |" % (len(ds) - cap))
    return lines


def viewer_page(viewer, out, maxq):
    hw = [d for d in out if d["q"] <= maxq]
    bycat = collections.defaultdict(list)
    for d in out:
        bycat[d["cat"]].append(d)
    L = [_D["actor_page_title"] % viewer, "",
         _D["actor_page_intro"] % (IDENT.get(viewer, "unidentified"), maxq), "",
         "| Category | Docs | Pages | hw docs | hw pages |", "|---|---|---|---|---|"]
    for cat, ds in sorted(bycat.items(), key=lambda kv: -len(kv[1])):
        h = [d for d in ds if d["q"] <= maxq]
        L.append("| %s | %d | %d | %d | %d |" % (cat, len(ds), sum(d["pages"] for d in ds), len(h), sum(d["pages"] for d in h)))
    L.append("| **total** | %d | %d | %d | %d |" % (len(out), sum(d["pages"] for d in out), len(hw), sum(d["pages"] for d in hw)))
    rc = collections.Counter(d["role"] for d in out)
    L += ["", "Role of the viewer string: " + ", ".join("%s %d" % kv for kv in rc.most_common()), ""]
    for cat in DB_CATS:
        ds = bycat.get(cat, [])
        if ds:
            L += ["## %s (%d docs)" % (cat, len(ds)), ""] + table(ds, cat) + [""]
    return L


def build(rows, maxq):
    ov = load_overrides()
    docs = {}
    per_viewer = collections.defaultdict(list)
    for r in rows:
        d = classify(*r)
        docs[d["esdn"]] = d
        vs = viewers_of(r[1], r[6])
        if not vs:
            vs = {"none": "none"}
        for v, role in vs.items():
            dd = apply_override(d, v, ov); dd = dict(dd); dd["role"] = role; dd["viewer"] = v
            per_viewer[v].append(dd)
    return docs, per_viewer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("viewer", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--maxq", type=float, default=0.55)
    a = ap.parse_args()
    con = sqlite3.connect(DB); rows = load(con); con.close()
    docs, pv = build(rows, a.maxq)
    if not a.index:
        txt = "\n".join(viewer_page(a.viewer, pv.get(a.viewer, []), a.maxq))
        if a.out:
            open(a.out, "w").write(txt + "\n"); print("wrote", a.out)
        else:
            print(txt)
        return
    os.makedirs(OUTDIR, exist_ok=True)
    big = sorted([v for v in pv if v != "none" and len(pv[v]) >= MIN_DOCS], key=lambda v: -len(pv[v]))
    small = sorted([v for v in pv if v != "none" and len(pv[v]) < MIN_DOCS])
    for v in big + ["none"]:
        fn = v.replace("#", "gf-") + ".md"
        open(os.path.join(OUTDIR, fn), "w").write("\n".join(viewer_page(v, pv[v], a.maxq)) + "\n")
    other = [d for v in small for d in pv[v]]
    open(os.path.join(OUTDIR, "other.md"), "w").write("\n".join(viewer_page("other (%d ids with under %d docs each: %s)" % (len(small), MIN_DOCS, ", ".join(small)), other, a.maxq)) + "\n")
    with open(os.path.join(OUTDIR, "index.tsv"), "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["viewer", "esdn", "role", "category", "score", "pages", "ocr_q", "date", "site", "title", "top_words", "ruling", "note"])
        for v in big + small + ["none"]:
            for d in sorted(pv[v], key=lambda d: (d["cat"], -d["score"])):
                top = "; ".join("%s %d" % kv for kv in d["hits"].get(d["cat"], collections.Counter()).most_common(5))
                w.writerow([v, d["esdn"], d["role"], d["cat"], d["score"], d["pages"], "%.2f" % d["q"], d["date"], d["site"], d["title"], top, d["ruling"], d["note"]])
    st = site_targets(rows)
    S = [_D["sites_title"], "",
         _D["sites_intro"], "",
         "| Site | Viewers | Docs | Pooled nouns | Feedback line |", "|---|---|---|---|---|"]
    for s in sorted(st):
        d = st[s]
        S.append("| %s | %s | %d | %s | %s |" % (s, ", ".join(sorted(d["viewers"])), len(d["docs"]),
                 ", ".join(w for w, _ in d["caps"].most_common(8)), (d["fb"][0][:110] if d["fb"] else "").replace("|", "/")))
    open(os.path.join(OUTDIR, "site-targets.md"), "w").write("\n".join(S) + "\n")
    cats = list(CATS) + ["unclassified"]
    allcat = collections.Counter(d["cat"] for d in docs.values())
    I = [_D["index_title"], "",
         _D["index_intro"] % (len(docs), MIN_DOCS), "",
         "## The whole release by category (each document once)", "",
         "| Category | Docs | Pages | hw docs | hw pages |", "|---|---|---|---|---|"]
    for cat in cats:
        ds = [d for d in docs.values() if d["cat"] == cat]
        h = [d for d in ds if d["q"] <= a.maxq]
        I.append("| %s | %d | %d | %d | %d |" % (cat, len(ds), sum(d["pages"] for d in ds), len(h), sum(d["pages"] for d in h)))
    I.append("| **total** | %d | %d | %d | %d |" % (len(docs), sum(d["pages"] for d in docs.values()),
             sum(1 for d in docs.values() if d["q"] <= a.maxq), sum(d["pages"] for d in docs.values() if d["q"] <= a.maxq)))
    short = dict(_D["short_labels"])   # category -> its column label
    I += ["", "## Documents per viewer and category", "",
          "| Viewer | Identity | Docs | Pages | hw pages | " + " | ".join(short.get(c, c) for c in cats) + " |",
          "|---|---|---|---|---|" + "---|" * len(cats)]
    for v in big + ["none"]:
        ds = pv[v]; cc = collections.Counter(d["cat"] for d in ds)
        I.append("| [%s](%s.md) | %s | %d | %d | %d | " % (v, v.replace("#", "gf-"), IDENT.get(v, ""), len(ds), sum(d["pages"] for d in ds),
                 sum(d["pages"] for d in ds if d["q"] <= a.maxq)) + " | ".join(str(cc.get(c, 0)) for c in cats) + " |")
    cc = collections.Counter(d["cat"] for d in other)
    I.append("| [other](other.md) | %d ids under %d docs | %d | %d | %d | " % (len(small), MIN_DOCS, len(other), sum(d["pages"] for d in other),
             sum(d["pages"] for d in other if d["q"] <= a.maxq)) + " | ".join(str(cc.get(c, 0)) for c in cats) + " |")
    I += ["", "## Release-wide shortlists (each document once; best-scoring viewer shown)", ""]
    for cat in DB_CATS:
        best = {}
        for v in big + small + ["none"]:
            for d in pv[v]:
                if d["cat"] == cat and (d["esdn"] not in best or d["score"] > best[d["esdn"]]["score"]):
                    best[d["esdn"]] = d
        uniq = sorted(best.values(), key=lambda d: -d["score"])
        I += ["### %s (%d docs)" % (cat, len(uniq)), "",
              "| Viewer | ESDN | Date | Pages | OCR q | Site | Title | Top words | Ruling |", "|---|---|---|---|---|---|---|---|---|"]
        for d in uniq[:80]:
            top = ", ".join("%s %d" % kv for kv in d["hits"].get(cat, collections.Counter()).most_common(4))
            I.append("| %s | %s | %s | %d | %.2f | %s | %s | %s | %s |" % (d["viewer"], d["esdn"], d["date"], d["pages"], d["q"], d["site"], d["title"].replace("|", "/")[:60], top, d["ruling"]))
        if len(uniq) > 80:
            I.append("| ... | %d more in index.tsv | | | | | | | |" % (len(uniq) - 80))
        I.append("")
    open(os.path.join(OUTDIR, "index.md"), "w").write("\n".join(I) + "\n")
    print("wrote", OUTDIR, "docs", len(docs), "viewers", len(big), "small", len(small), "none", len(pv["none"]))


if __name__ == "__main__":
    main()
