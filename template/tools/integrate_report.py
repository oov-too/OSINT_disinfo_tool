#!/usr/bin/env python3
"""Integrate a note-writing agent's JSON report into the subject pages, tracker, object register, the audit's openness dataset and the index.

Usage: python3 tools/integrate_report.py <report.json> [--short "Label"]
Report keys used: file, subject_rows {page: row}, audit_blurb (+ optional audit_pages [..], default the audited subject
pages the pack marks ([tools.integrate_report] audit_marks) if a subject row exists for them), tracker_rows [{from,to,degree,kind,when,what,source}], register_new [{video,timestamp,
who,object,match,strength}], register_updates (printed for manual handling), openness_cells/openness_counts (+ label),
answered_questions [{note, row, status, answer, answered_by?, settles?}]: sets Status (checked or closed), Answer,
Answered by (default `note: [<short>](<link to this report's file>)`) and Answered on (today) in that note's
`## Open questions` row, or in the Lead register when note is research/leads-and-inferences.md; settles, if given,
replaces What would settle it (the remaining test, which a checked row needs). A row already carrying a different
answer is left alone and reported. Idempotent: every insert is keyed on its first 90 characters, and an answer
already in place is skipped.
"""
import datetime, json, os, re, subprocess, sys
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
from ledger import paths as LP   # project paths and the sources/ alias table (tools/ledger/paths.py)
import packload   # the pack's object register, topic codes and the audit paragraphs of its subject pages ([tools.integrate_report]; phase 7b)
_D = packload.tool_data("integrate_report")
OBJECT_REGISTER = packload.pack().get("objects", {}).get("register") or "research/object-register.md"   # the pack's object register ([objects] register)
rep = json.load(open(sys.argv[1]))
def _norm(r):
    m = dict({"video": "video", "timestamp": "timestamp", "who": "who", "object": "object", "match": "match", "strength": "strength"}, **{k: "match" for k in _D["register_match_keys"]})
    return {m.get(k.lower(), k.lower()): v for k, v in r.items()} if isinstance(r, dict) else r
rep["register_new"] = [_norm(r) for r in (rep.get("register_new") or [])]
short = sys.argv[sys.argv.index("--short") + 1] if "--short" in sys.argv else None
fname = os.path.basename(rep["file"]); stem = fname[:-3]
NOTE_DIR = (rep.get('file','') or '').split('/')[0] if (rep.get('file','') or '').split('/')[0] in ('videos','books') else 'videos'  # book notes live in books/ (2026-09-28)
# the subject pages' audit paragraphs are matched by their text (the pack's: subject page -> the paragraph's opening words)
AUDIT_MARK = dict(_D["audit_marks"])

def has(s, text): return text.strip()[:90] in s
# A new project has no registers and no subject pages until its first intake (the pilot project, 2026-10-23): each is started in its
# core form when a report first has rows for it, and the first row of an empty table goes after the table's header.
CORE_PAGES = {
    OBJECT_REGISTER: ("# Object register\n\nStarted by tools/integrate_report.py at the project's first object row, in the core form (setup stage 4 "
                      "writes the same table in a new project).\n\n## Register\n\n", ["#", "Video", "Timestamp", "Who", "Object", "Match to the reference object", "Strength"]),
    "research/leads-and-inferences.md": ("# Questions, leads and inferences\n\nStarted by tools/integrate_report.py at the project's first lead, in the core form.\n\n"
                                         "## Lead register\n\n", ["#", "Lead", "Kind", "Asked by", "Sources", "What would settle it", "Status", "Answer", "Answered by", "Answered on", "Added"]),
    "research/relations-register.md": ("# Relations register\n\nStarted by tools/integrate_report.py at the project's first relation, in the core form.\n\n"
                                       "## Relation register\n\n", ["#", "A", "B", "Kind", "Hierarchy", "When", "What", "Source", "Chain", "Confidence", "Added"]),
}
def _ensure(p):
    """Start a missing register or subject page in its core form (CORE_PAGES; a subject page from the pack's subject name)."""
    if os.path.exists(p): return True
    if p.startswith("subjects/"):
        slug = p[len("subjects/"):-3]
        if slug not in packload.all_subjects(): return False
        name = ((packload.pack().get("display", {}).get("map", {}).get("subjects", {}) or {}).get(slug) or {}).get("name") or slug.replace("-", " ").capitalize()
        head, cols = f"# {name}\n\nStarted by tools/integrate_report.py at the subject's first note, in the core form.\n\n## Videos in this subject\n\n", ["Uploaded", "Video", "Speakers", "What it adds"]
    elif p in CORE_PAGES: head, cols = CORE_PAGES[p]
    else: return False
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    LN.write_text(p, head + "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"); print("  started", p)
    return True
def _anchor(s, n):
    """The row a new row goes after: the register's last numbered row, or an empty table's separator line (n 0)."""
    if n: return LN.row_match(s, n).group(0)
    return re.search(r"^\| # \|[^\n]*\n\|(?:-+\|)+\n", s, re.M).group(0)
def insert_row(page, row):
    p = f"subjects/{page}.md"; s = LN.read_text(p); row = row.strip()
    if has(s, row): print("  skip row", page); return
    date = row.split("|")[1].strip()
    rows = [(m.start(), m.group(1)) for m in re.finditer(r"^\| (\d{4}-\d{2}-\d{2}) \|[^\n]*\n", s, re.M)]
    if not rows:   # an empty subject table (a page started at the subject's first note): the row goes after its header
        m = re.search(r"^## Videos in this subject\n\n\|[^\n]*\n\|(?:-+\|)+\n", s, re.M)
        if not m: print("  no table", page); return
        s = s[:m.end()] + row + "\n" + s[m.end():]; LN.write_text(p, s); print("  row added", page); return
    later = [pos for pos, d in rows if d > date]
    if later: pos = later[0]; s = s[:pos] + row + "\n" + s[pos:]
    else:
        last = max(rows)[0]; end = s.index("\n", last) + 1; s = s[:end] + row + "\n" + s[end:]
    LN.write_text(p, s); print("  row added", page)
def add_bullet(page, blurb):
    p = f"subjects/{page}.md"; s = LN.read_text(p); b = "- " + blurb.strip()
    if has(s, b): print("  skip bullet", page); return
    if page in _D["audit_mark_before"]:   # the bullet goes before the paragraph on these pages, after its list elsewhere
        i = s.index(AUDIT_MARK[page]); s = s[:i] + "\n" + b + s[i:]
    else:
        i = s.index(AUDIT_MARK[page]); j = s.index("\n- ", i); k = s.index("\n\n", j); s = s[:k] + "\n" + b + s[k:]
    LN.write_text(p, s); print("  bullet added", page)
def add_tracker(rows):
    """Since 2026-09-26 the ties tracker is superseded: tracker_rows are converted to relations-register rows (one tie per seat) and appended there."""
    rels = []
    for r in rows:
        a = str(r.get("from", "")).strip(); to = str(r.get("to", "")).strip(); kind = str(r.get("kind", "")); deg = str(r.get("degree", ""))
        what = str(r.get("what", "")); when = str(r.get("when", "")); src = str(r.get("source", ""))
        kl = kind.lower()
        rk = "funder" if "fund" in kl else "family" if "marri" in kl or "family" in kl else "agreement" if "contract" in kl or "sale" in kl or "custody" in kl or "creditor" in kl else "employer" if "office" in kl or "revolving" in kl or "employ" in kl or "command" in kl or "seat" in kl else "founder" if "found" in kl else "member-of"
        conf = "high" if "verified" in what.lower() and "unverified" not in what.lower() else "low" if ("unverified" in (what + src).lower() or "assertion" in (what + src).lower() or "inference" in (what + src).lower()) else "medium"
        seats = [t.strip() for t in re.split(r";\s*", to) if t.strip()] or [to]
        for seat in seats:
            rels.append({"a": a, "b": seat, "relation": rk, "when": when, "what": (f"tracker kind: {kind}; degree {deg}; " if kind or deg else "") + what, "source": src, "chain": r.get("chain", ""), "confidence": conf})
    add_relations(rels)
def add_register(rows):
    if not rows: print("  register rows added: 0"); return
    p = OBJECT_REGISTER; _ensure(p); s = LN.read_text(p); n = 0
    for r in rows:
        if "object" not in r and r.get("text", "").lstrip().startswith("|"):
            cells = [c.strip() for c in LN.split_spaced(r["text"].strip().strip("|"))]
            if len(cells) >= 7: r = {"video": cells[1], "timestamp": cells[2], "who": cells[3], "object": cells[4], "match": cells[5], "strength": cells[6]}
            else: print("  register row malformed:", r["text"][:80]); continue
        key = "| " + r["object"][:60]
        if key[:90] in s: continue
        last = max(LN.row_numbers(s) or [0])
        anchor = _anchor(s, last)
        vid = r.get("video") or f"[{short or stem}](../{NOTE_DIR}/{fname})"
        s = s.replace(anchor, anchor + "| %d | %s | %s | %s | %s | %s | %s |\n" % (last + 1, vid, r.get("timestamp", ""), r.get("who", ""), r["object"], r.get("match", ""), r.get("strength", "")), 1); n += 1
    LN.write_text(p, s); print("  register rows added:", n)
TOPICS = [t for t, _ in packload.topics()]   # the pack's claims topic codes, in its order ([audit] topics)
def _topic(t):
    t = t.lower().strip()
    if t in TOPICS: return t
    key = re.sub(r"[^a-z]", "", t)
    for code in TOPICS:
        if re.sub(r"[^a-z]", "", code) == key: return code
    return _D["topic_aliases"].get(key, t)   # a reported label's letters -> a topic code
def add_openness(rep):
    counts = rep.get("openness_counts") or {}; cells = rep.get("openness_cells") or []
    # a report without them: read from the note itself, its audit counts line and its audit rows (tools/ledger/openness.py; pilot defect
    # 10, 7b2 2026-10-23), for an audited note of a pack that does not keep its dataset by hand ([tools.integrate_report] openness_from_note)
    if not (counts and cells) and _D.get("openness_from_note", True) and os.path.exists(rep.get("file", "")):
        aud = set(packload.audited_subjects()); subj = set(LN.parse_note(rep["file"], ROOT).get("subjects") or [])
        if not aud or (subj & aud):
            from ledger import openness as _OP
            c2, cells2 = _OP.from_note(rep["file"], ROOT)
            if c2 and cells2: counts, cells = counts or c2, cells or cells2; print(f"  openness: read from the note ({len(cells2)} audit rows)")
    if isinstance(counts, str):  # tolerate the Audit-counts string form (fix 2026-10-08, arlington-1008): one source only; two named speakers = multi-source
        txt = counts
        if len(re.findall(r"\b([A-Z][a-z]+) (?:open|partial)", txt)) >= 2: print("  openness: MULTI-SOURCE counts (string); add by hand (one source per speaker)"); return
        m = {k: int(v) for k, v in re.findall(r"(open|partial|closed[- ]outright|closed[- ]subtle|stated declines|pseudo[- ]declines)\s+(\d+)", txt, re.I) and [(a.lower().replace(" ", "_").replace("-", "_"), b) for a, b in re.findall(r"(open|partial|closed[- ]outright|closed[- ]subtle|stated declines|pseudo[- ]declines)\s+(\d+)", txt, re.I)]}
        counts = m if m else {}
    if not isinstance(counts, dict): counts = {}
    if not counts or not cells: print("  openness: none"); return
    if any(isinstance(v, dict) for v in counts.values()): print("  openness: MULTI-SOURCE counts; add by hand (one source per speaker)"); return
    dp = "research/figures/openness-dataset.json"; sid = stem
    d = json.load(open(dp)) if os.path.exists(dp) else {"sources": [], "cells": [], "topic_summary": [{"topic": t} for t, _ in packload.topics()], "notes": "the forthrightness audits' openness dataset: tools/integrate_report.py adds one source per audited intake; tools/draw_openness_map.py refreshes the counts"}   # the first audited intake of a new project starts the dataset (phase 7b)
    if any(x["id"] == sid for x in d["sources"]): print("  openness: exists"); return
    d["sources"].append({"id": sid, "label": rep.get("openness_label") or short or stem, "kind": "human", "note": NOTE_DIR + "/" + fname,
                         "counts": {k: int(counts.get(k, 0)) for k in ("open", "partial", "closed_outright", "closed_subtle", "stated_declines", "pseudo_declines")}})
    for c in cells:
        if c["class"] not in ("open", "partial", "contested", "closed-subtle", "closed-outright"): continue
        d["cells"].append({"source": sid, "topic": _topic(c["topic"]), "class": c["class"], "evidence": c.get("evidence", ""), "basis": c.get("basis", "n/a")})
    LN.write_text(dp, json.dumps(d, indent=1, ensure_ascii=False)); print("  openness: added", len(cells), "cells")
    if os.path.exists("research/figures/OPENNESS_HOLD"): print("  openness: HOLD file present, map not redrawn (owner, 2026-09-27)"); return
    subprocess.run([sys.executable, os.path.join(_T, "draw_openness_map.py")], check=False)
def add_short():
    if not short: return
    p = os.path.join(_T, "build_index.py"); s = LN.read_text(p)
    if f'"{fname}"' in s: print("  short exists"); return
    s = s.replace('SHORT = {  # short labels for the tag index\n', 'SHORT = {  # short labels for the tag index\n    "%s": "%s",\n' % (fname, short), 1)
    LN.write_text(p, s); print("  short added")

def _short(path):
    if short and os.path.basename(path) == fname: return short
    m = re.search(r'"%s": "([^"]+)"' % re.escape(os.path.basename(path)), LN.read_text(os.path.join(_T, "build_index.py")))
    if m: return m.group(1)
    first = LN.first_line(path).lstrip("# ").strip() if os.path.exists(path) else path
    return first[:40]
import importlib.util as _ilu, os as _os
_ag_spec=_ilu.spec_from_file_location('answer_guard', _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'answer_guard.py')); answer_guard=_ilu.module_from_spec(_ag_spec); _ag_spec.loader.exec_module(answer_guard)
def apply_answers(items):
    """Write answered_questions into the target notes' Open questions tables (or the Lead register)."""
    today = datetime.date.today().isoformat()
    for it in items:
        note = it.get("note", ""); note = note if "/" in note else "videos/" + note
        note = note if note.endswith(".md") else note + ".md"
        if not os.path.exists(note): print("  answered_questions: no such note", note); continue
        status = str(it.get("status", "")).strip().lower()
        if status not in ("checked", "closed"): print("  answered_questions: status must be checked or closed:", note, it.get("row")); continue
        src = it.get("answered_by") or ""
        if not re.match(r"(note|page|document|own):", src):
            tgt = src or rep["file"]; tgt = tgt if "/" in tgt else "videos/" + tgt
            link = os.path.relpath(tgt, os.path.dirname(note))
            src = f"note: [{_short(tgt)}]({link})"
        lines = LN.read_lines(note); head = "## Lead register" if note.endswith("leads-and-inferences.md") else "## Open questions"
        start = LN.section_start(lines, head)   # form S1
        if start is None: print("  answered_questions: no", head, "in", note); continue
        hdr = None; done = False
        for i in range(start + 1, len(lines)):
            if lines[i].startswith("## "): break
            c = LN.split_row(lines[i]) if lines[i].lstrip().startswith("|") else None
            if not c: continue
            if hdr is None:
                if c[0] == "#": hdr = [h.lower() for h in c]
                continue
            if c[0] != str(it.get("row")): continue
            col = {k: next(j for j, h in enumerate(hdr) if h.startswith(k)) for k in ("status", "answer", "answered by", "answered on", "what would settle")}
            _qi = next((j for j, h in enumerate(hdr) if h.startswith("question") or h == "lead"), None)
            if not answer_guard.check(it, c[_qi] if _qi is not None and _qi < len(c) else "", f"{note} row {c[0]}", short or stem): done = True; break
            c += [""] * (len(hdr) - len(c)); ans = str(it.get("answer", "")).replace("|", "/").replace("\n", " ").strip()
            if c[col["answer"]] and c[col["answer"]] != ans:
                print(f"  answered_questions: {note} row {c[0]} already answered differently; left unchanged, merge by hand"); done = True; break
            if c[col["status"]] == status and c[col["answer"]] == ans and c[col["answered by"]] == src:
                print(f"  answered_questions: {note} row {c[0]} unchanged"); done = True; break
            old = c[col["status"]]; c[col["status"]], c[col["answer"]], c[col["answered by"]], c[col["answered on"]] = status, ans, src, today
            if it.get("settles"): c[col["what would settle"]] = str(it["settles"]).replace("|", "/").strip()
            lines[i] = LN.join_row(c); LN.write_lines(note, lines)
            print(f"  answered_questions: {note} row {c[0]}: {old} -> {status}"); done = True; break
        if not done: answer_guard.check(it, None, f"{note} row {it.get('row')}", short or stem)

print("integrating", fname)
def _norm_subjects(d):
    out = {}
    for k, v in (d or {}).items():
        k = re.sub(r"^(\.\./)?subjects/", "", k.strip()); k = k[:-3] if k.endswith(".md") else k
        if isinstance(v, str) and v.strip():
            v = v.strip(); v = v if v.startswith("|") else "| " + v; v = v if v.endswith("|") else v + " |"
        out[k] = v
    return out
rep["subject_rows"] = _norm_subjects(rep.get("subject_rows"))
for page, row in (rep.get("subject_rows") or {}).items():
    if row and _ensure(f"subjects/{page}.md"): insert_row(page, row)
    elif row: print("  no such page", page)
if rep.get("audit_blurb"):
    for page in rep.get("audit_pages") or [p for p in AUDIT_MARK if (rep.get("subject_rows") or {}).get(p)]: add_bullet(page, rep["audit_blurb"])
add_register(rep.get("register_new") or []); add_openness(rep); add_short()
# chain findings and other proposed leads go to the register as open rows with a test
def add_leads(items, default_kind):
    if not any(str(it.get("lead", "")).strip() for it in items): print(f"  leads added ({default_kind}): 0"); return
    p = "research/leads-and-inferences.md"; _ensure(p); s = LN.read_text(p); n0 = max(LN.row_numbers(s) or [0]); n = n0
    anchor = _anchor(s, n0); new = ""
    for it in items:
        lead = str(it.get("lead", "")).strip()
        if not lead or lead[:60] in s: continue
        n += 1; src = str(it.get("sources", "")); src = src + ("; " if src else "") + f"via [{short or stem}](../{NOTE_DIR}/{fname})"
        new += "| " + " | ".join([str(n), lead.replace("|", "/"), it.get("kind", default_kind), "note: [" + (short or stem) + "](../" + NOTE_DIR + "/" + fname + ")", src.replace("|", "/"), str(it.get("settles", "unknown")).replace("|", "/"), "open", "", "", "", __import__("datetime").date.today().isoformat()]) + " |\n"
    if new: s = s.replace(anchor, anchor + new, 1); LN.write_text(p, s)
    print(f"  leads added ({default_kind}):", n - n0)
add_leads(rep.get("chain_leads") or [], "inference"); add_leads(rep.get("leads") or [], "lead")
def add_relations(items):
    if not items: print("  relations added: 0"); return
    p = "research/relations-register.md"; _ensure(p); s = LN.read_text(p)
    nums = LN.row_numbers(s); n = max(nums) if nums else 0; n0 = n
    hdr = re.search(r"^\|---\|---\|---\|---\|---\|---\|---\|---\|---\|---\|---\|\n", s, re.M)
    anchor = LN.row_match(s, n).group(0) if n else hdr.group(0)
    new = ""
    for it in items:
        a = str(it.get("a", "")).strip(); b = str(it.get("b", "")).strip()
        if not a or not b: continue
        key = "| " + a + " | " + b + " | " + str(it.get("relation", it.get("kind", "")))
        if key[:90] in s: continue
        n += 1; src = str(it.get("source", it.get("source (time)", ""))); src = src + ("; " if src else "") + (f"[{short or stem}]({fname})" if rep.get("file", "").startswith("research/") else f"[{short or stem}](../{NOTE_DIR}/{fname})")
        new += "| " + " | ".join([str(n), a, b, str(it.get("relation", it.get("kind", ""))).replace("|", "/").replace("handler", "directs"), str(it.get("hierarchy", "")).replace("|", "/"), str(it.get("when", "")).replace("|", "/"), str(it.get("what", "")).replace("|", "/"), src.replace("|", "/"), str(it.get("chain", "")).replace("|", "/"), str(it.get("confidence", "medium")), __import__("datetime").date.today().isoformat()]) + " |\n"
    if new: s = s.replace(anchor, anchor + new, 1); LN.write_text(p, s)
    print("  relations added:", n - n0)
add_tracker(rep.get("tracker_rows") or []); add_relations(rep.get("relations") or [])
apply_answers(rep.get("answered_questions") or [])
for u in rep.get("register_updates") or []:
    if isinstance(u, dict) and u.get("entry") and str(u.get("text", "")).lstrip().startswith("| " + str(u["entry"]) + " |"):
        rp = OBJECT_REGISTER; rs = LN.read_text(rp)
        m = LN.row_match(rs, u["entry"], tail=r"[^\n]*$")
        if m and m.group(0) != u["text"].strip(): rs = rs.replace(m.group(0), u["text"].strip()); LN.write_text(rp, rs); print("  register entry", u["entry"], "replaced")
        else: print("  register entry", u["entry"], "unchanged")
    else: print("  MANUAL register update:", str(u)[:200])
subprocess.run([sys.executable, os.path.join(_T, "build_db.py"), "--report"], capture_output=True)
print(subprocess.run([sys.executable, os.path.join(_T, "build_index.py")], capture_output=True, text=True).stdout.strip().splitlines()[-1])
bad = 0
import glob
for f in (x for x in glob.glob("**/*.md", recursive=True) if not x.startswith(("wip/", "transcripts/", "research/tasks/tool-feedback/")) and "-logs/" not in x):  # archived working copies keep their page-relative links (2026-10-14)  # archived change logs quote links verbatim
    dd = os.path.dirname(f)
    for m in LN.LOCAL_LINK_RE.finditer(LN.read_text(f, errors="replace")):   # form L2; links resolve through the sources/ alias table
        if not LP.exists(m.group(1), base=dd or "."): bad += 1; print("  BROKEN", f, m.group(1))
print("broken links:", bad)
