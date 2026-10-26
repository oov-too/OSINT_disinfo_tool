#!/usr/bin/env python3
"""Integrate a book-intake agent report of the 2026-09-30 shape into the registers (tolerant of the agents' key variants).
Handles: register_updates [{entry,text}], register_new (dict rows with video/timestamp/who/object/match/strength, or
pipe-format strings starting '| new |'), subject_rows {page: row}, relations (a/A, b/B, kind/relation/Kind, ...),
chain_leads (settles | test | what_would_settle_it), answered_questions ({note,row|question} or {target}) with
'status'/'status_proposed'/'proposed_status' and 'answer'/'answer_append'. Usage: python3 tools/integrate_book_report.py <report.json> "<label>" """
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import answer_guard
import json, re, sys, os, datetime, subprocess, tempfile
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import packload; OBJECT_REGISTER = packload.pack().get("objects", {}).get("register") or "research/object-register.md"   # the pack's object register ([objects] register)
rep = json.load(open(sys.argv[1], encoding="utf-8")); label = sys.argv[2] if len(sys.argv) > 2 else "agent report"; today = datetime.date.today().isoformat()
reports = rep if isinstance(rep, list) else [rep]
def object_update(n, text):
    p = OBJECT_REGISTER; s = LN.read_text(p)
    i = s.find(f"\n| {n} |")
    if i < 0: print("  no register entry", n); return
    i += 1; j = s.index("\n", i); c = LN.split_spaced(s[i:j]); c[5] = c[5] + " " + text.replace("|", "/").replace("\n", " "); LN.write_text(p, s[:i] + " | ".join(c) + s[j:])
def object_new(rows):
    p = OBJECT_REGISTER; s = LN.read_text(p); nums = LN.row_numbers(s); n = max(nums)
    last = LN.row_match(s, n); new = ""; added = []
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("row"), str): r = r["row"]
        if isinstance(r, str):
            if not r.strip().startswith("|"): continue
            n += 1; new += re.sub(r"^\|\s*(new|next|\(next\)|\(new\))\s*\|", f"| {n} |", r.strip()) + "\n"; added.append(n)
        elif isinstance(r, dict) and "object" in r and "video" in r:
            n += 1; new += "| " + " | ".join([str(n), r.get("video", ""), r.get("timestamp", ""), r.get("who", ""), r.get("object", ""), r.get("match", ""), r.get("strength", "")]).replace("\n", " ") + " |\n"; added.append(n)
    if new: s = s[:last.end()] + new + s[last.end():]; LN.write_text(p, s)
    return added
def subject_row(page, row):
    if not os.path.exists(page): print("  no page", page); return
    s = LN.read_text(page); row = row.strip()
    if row[:50] in s: return
    if page.endswith(os.path.basename(OBJECT_REGISTER)): object_new([row]); return
    m = list(re.finditer(r"^\| \d{4}-\d{2}-\d{2} \|[^\n]*\n", s, re.M))
    if m: last = m[-1]; s = s[:last.end()] + row + "\n" + s[last.end():]; LN.write_text(page, s); print("  subject row added to", page)
def relations(items):
    if not isinstance(items, list): print("  relations not a list; skipped"); return 0
    p = "research/relations-register.md"; s = LN.read_text(p); nums = LN.row_numbers(s); n0 = n = max(nums)
    last = LN.row_match(s, n); new = ""
    # the Source cell always names the note (fixed 2026-10-07): "this note" is expanded, and a source with no link or path gains the note's link
    _link = f"[{label}](../{rep.get('file','')})" if rep.get("file") else ""
    def _src(src):
        src = str(src or "")
        if _link and "this note" in src: src = src.replace("this note", _link)
        elif _link and not re.search(r"\]\(|videos/|books/|research/", src): src = (src.strip() + "; " if src.strip() else "") + _link
        return src
    for r in items:
        g = lambda *ks: next((str(r[k]) for k in ks if k in r and r[k] is not None), "")
        a = g("a", "A", "from"); b = g("b", "B", "to")
        if not a or not b: continue
        n += 1; new += "| " + " | ".join([str(n), a, b, g("kind", "relation", "Kind"), g("hierarchy", "Hierarchy"), g("when", "When"), g("what", "What").replace("|", "/"), _src(g("source", "Source")).replace("|", "/"), g("chain", "Chain").replace("|", "/"), g("confidence", "Confidence"), today]).replace("\n", " ") + " |\n"
    if new: s = s[:last.end()] + new + s[last.end():]; LN.write_text(p, s)
    return n - n0
def leads(items, kind):
    items = [{"lead": l.get("lead", ""), "kind": l.get("kind", kind), "sources": l.get("sources", ""), "settles": l.get("settles") or l.get("test") or l.get("what_would_settle_it") or "unknown"} for l in items if isinstance(l, dict) and l.get("lead")]
    tmp = os.path.join(tempfile.gettempdir(), "_leads_%d.json" % os.getpid()); json.dump(items, LN.open_write(tmp), ensure_ascii=False)
    out = subprocess.run([sys.executable, os.path.join(_T, "add_leads.py"), tmp, "--kind", kind, "--label", label], capture_output=True, text=True).stdout.strip(); os.remove(tmp); print(" ", out)
def set_oq(path, qnum, status, answer, by, question=None):
    if not os.path.exists(path): print("  no note", path); return
    s = LN.read_text(path)
    if "## Open questions" not in s: print("  no OQ section", path); return
    OQ = s.index("## Open questions"); nxt = re.search(r"^## ", s[OQ + 5:], re.M); end = OQ + 5 + nxt.start() if nxt else len(s); blk = s[OQ:end]
    hdr = [l for l in blk.split("\n") if l.startswith("| #")]; cols = hdr[0].split(" | ") if hdr else []
    m = LN.row_match(blk, qnum)   # form R2
    if not m: answer_guard.check({"question": question, "answer": answer}, None, f"{path} row {qnum}", "book integrator"); return
    c = LN.split_spaced(m.group(0).rstrip("\n")); c[-1] = c[-1].rstrip(" |")
    _qi = next((i for i, x in enumerate(cols) if x.strip("| ").lower() == "question"), None)
    if not answer_guard.check({"question": question, "answer": answer}, c[_qi] if _qi is not None and _qi < len(c) else "", f"{path} row {qnum}", "book integrator"): return
    si = next((i for i, x in enumerate(cols) if x.strip("| ").lower() == "status"), None); ai = next((i for i, x in enumerate(cols) if x.strip("| ").lower() == "answer"), None)
    bi = next((i for i, x in enumerate(cols) if x.strip("| ").lower() == "answered by"), None); oi = next((i for i, x in enumerate(cols) if x.strip("| ").lower() == "answered on"), None)
    while len(c) < len(cols): c.append("")
    if status and si is not None: c[si] = status
    if ai is not None: c[ai] = (c[ai] + " " if c[ai].strip() else "") + answer
    if bi is not None and by: c[bi] = (c[bi] + "; " if c[bi].strip() else "") + by
    if oi is not None: c[oi] = today
    blk = blk.replace(m.group(0), " | ".join(c) + " |\n", 1); LN.write_text(path, s[:OQ] + blk + s[end:]); print("  OQ", qnum, "updated in", path)
def lead_note(num, status, text, question=None):
    p = "research/leads-and-inferences.md"; s = LN.read_text(p); m = LN.row_match(s, num)
    if not m: answer_guard.check({"question": question, "answer": text}, None, f"lead {num}", "book integrator"); return
    c = LN.split_spaced(m.group(0).rstrip("\n")); c[-1] = c[-1].rstrip(" |")
    if not answer_guard.check({"question": question, "answer": text}, c[1] if len(c) > 1 else "", f"lead {num}", "book integrator"): return
    if status and status in ("checked", "closed"): c[6] = status
    c[7] = (c[7] + " " if c[7].strip() else "") + text; c[9] = today; s = s.replace(m.group(0), " | ".join(c) + " |\n", 1); LN.write_text(p, s); print("  lead", num, "noted")
for d in reports:
    if not isinstance(d, dict): continue
    print("report:", d.get("file") or d.get("research_page"))
    for u in d.get("register_updates") or []:
        if isinstance(u, dict) and "entry" in u: object_update(u["entry"], u.get("text", ""))
    print("  register updates:", len(d.get("register_updates") or []))
    rn = d.get("register_new") or []
    if isinstance(rn, list): print("  register new:", object_new(rn))
    sr = d.get("subject_rows") or {}
    if isinstance(sr, dict):
        for page, row in sr.items():
            if isinstance(row, str) and row.strip().startswith("|"): subject_row(page, row)
    print("  relations added:", relations(d.get("relations") or []))
    if d.get("chain_leads"): leads(d["chain_leads"], "inference")
    if d.get("leads"): leads(d["leads"], "lead")
    for a in d.get("answered_questions") or []:
        if not isinstance(a, dict): continue
        target = a.get("target") or a.get("note") or ""; q = str(a.get("row") or a.get("question") or target)
        status = a.get("status") or a.get("status_proposed") or a.get("proposed_status") or ""; status = status if status in ("checked", "closed") else None
        ans = a.get("answer_append") or a.get("answer") or ""; by = a.get("answered_by", ""); text = f"Checked {today}: {ans}" if status else f"Note {today}: {ans}"
        mnum = re.search(r"(\d+)", q)
        _q = a.get("question") if isinstance(a.get("question"), str) and not re.fullmatch(r"\s*\d+\s*", str(a.get("question"))) else None
        if "leads-and-inferences" in target and mnum: lead_note(int(mnum.group(1)), status, text + (f" ({by})" if by else ""), _q)
        elif ("open question" in q.lower() or a.get("row")) and mnum:
            note = target.split(" open question")[0].split(" lead")[0].strip(); set_oq(note, int(mnum.group(1)), status, text, by, _q)
        else: print("  deferred:", target, q[:60])
