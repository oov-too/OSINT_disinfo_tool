"""By-hand parts of an intake report that tools/integrate_report.py does not cover.
Usage: python3 post_intake.py <report.json> "<short label>"
 - adds the SHORT label to tools/build_index.py
 - appends the report's speaker-ledger section (the pack's [tools.post_intake] ledger_key) to that speaker's ledger page, before its anchor heading
 - appends a Held status to the cited-recordings row named in cited_row (and new_cited rows to the residuals for review)
 - moves answered_questions items marked 'annotation only' out of the report (into residuals) so the integrator does not stamp an OQ row
 - logs disagreements_with_existing_notes and unlocated_clips_placed as correction items in corr/residuals-round3.md
 - records recorded_date and notes_on_intent in the intake log
Run BEFORE integrate_report.py (it rewrites the report file)."""
import json, sys, re, os, datetime
rep_path, short = sys.argv[1], sys.argv[2]
rep = json.load(open(rep_path)); today = datetime.date.today().isoformat()
NOTE_DIR = (rep.get('file','') or '').split('/')[0] if (rep.get('file','') or '').split('/')[0] in ('videos','books') else 'videos'  # book notes live in books/ (2026-09-28)
fname = os.path.basename(rep["file"]); link = f"[{short}](../{NOTE_DIR}/{fname})"; rlink = f"[{short}](../{NOTE_DIR}/{fname})"
import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22); os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
import packload; _D = packload.tool_data("post_intake")   # the pack's speaker ledger: report keys, page and anchor ([tools.post_intake]; phase 7b)
res = LN.open_append("research/corrections/pending-round3-raw.md")  # correction items queue (path fixed 2026-09-28)
# 1 SHORT label
p = os.path.join(_T, "build_index.py"); s = LN.read_text(p)
if f'"{fname}"' not in s:
    s = s.replace("SHORT = {  # short labels for the tag index\n", f'SHORT = {{  # short labels for the tag index\n    "{fname}": "{short}",\n', 1); LN.write_text(p, s); print("SHORT added")
# 2 ledger: every ledgered speaker of the pack ([[speakers.ledgered]] report_keys; 7b2, 2026-10-23, was the single [tools.post_intake]
# ledger_key), the values in section form only (a string headed `#`; "n/a" and other values are skipped, as since 2026-09-28), each
# inserted before the anchor of [tools.post_intake] for its page (tools/ledger/speakers.py, the same step `ledger integrate` runs)
from ledger import speakers as _SP
_led = [dict(sp) for sp in packload.pack().get("speakers", {}).get("ledgered", [])]
if _D["ledger_page"] and _D["ledger_key"] and not any(sp.get("page") == _D["ledger_page"] and _D["ledger_key"] in (sp.get("report_keys") or []) for sp in _led):
    _led.append({"name": "", "page": _D["ledger_page"], "report_keys": [_D["ledger_key"]]})
_other = {k for sp in _led if sp.get("page") == _D["ledger_page"] for k in (sp.get("report_keys") or []) if k != _D["ledger_key"]}   # that page takes ledger_key alone, as before
_secs = {k: v.strip() for k, v in rep.items() if isinstance(v, str) and v.strip().startswith("#") and k not in _other}
for page, key, what in _SP.append(_secs, os.path.basename(rep_path), _led, ROOT, {_D["ledger_page"]: _D["ledger_anchor"]} if _D["ledger_page"] else {}):
    if what == "section": print("ledger section appended:", page, key)
# 3 cited row
cr = rep.get("cited_row") or {}
row = cr.get("row")
if row:
    p = "research/cited-videos-not-held-2026-09-26.md"; lines = LN.read_lines(p)
    for i, l in enumerate(lines):
        if l.startswith(f"| {row} | "):
            cells = LN.split_spaced(l)
            _st = cr.get("settles") or []
            settles = ("; ".join(_st) if isinstance(_st, list) else str(_st)) or "none of the listed tests"
            dns = "; ".join(cr.get("does_not_settle") or [])
            add = f" **Held {today}:** {rlink}. Settles: {settles}." + (f" Does not settle: {dns}." if dns else "")
            cells[-2] = cells[-2] + add.replace("|", "/"); lines[i] = " | ".join(cells); print("cited row", row, "annotated"); break
    else: print("cited row", row, "not found")
    LN.write_lines(p, lines)
for nc in cr.get("new_cited") or []:
    res.write(f"- NEW CITED RECORDING (from {short} intake, {today}): {json.dumps(nc, ensure_ascii=False)} -> add a row to research/cited-videos-not-held-2026-09-26.md\n")
# 4 annotation-only answered items
keep = []
for it in rep.get("answered_questions") or []:
    if str(it.get("settles", "")).lower().startswith("none; annotation") or "not an open-question row" in it.get("answer", ""):
        res.write(f"- ANNOTATION (from {short} intake, {today}): {it['note']} row {it['row']}: {it['answer']}\n")
    else: keep.append(it)
rep["answered_questions"] = keep
# 5 corrections
for d in rep.get("disagreements_with_existing_notes") or []:
    res.write(f"- From the {short} intake ({today}): {d}\n")
for c in rep.get("unlocated_clips_placed") or cr.get("unlocated_clips_placed") or []:
    res.write(f"- CLIP PLACED (from {short} intake, {today}): {c.get('note')} {c.get('row_or_time')} -> {short} {c.get('this_recording_time')} (verbatim: {c.get('verbatim')}); update the clip row's Note/chain to name the source recording\n")
res.close()
with LN.open_append("research/corrections/intake-log.md") as f:
    f.write(f"\n## {short} ({fname}), {today}\n- recorded_date: {rep.get('recorded_date','')}\n- {_D['ledger_note_key']}: {rep.get(_D['ledger_note_key'],'')}\n- consent_axis: {rep.get('consent_axis','')}\n- notes_on_intent: {rep.get('notes_on_intent','')}\n- openness_counts: {json.dumps(rep.get('openness_counts'))} (map on hold)\n")
json.dump(rep, LN.open_write(rep_path), indent=1, ensure_ascii=False); print("report rewritten; answered kept:", len(keep))
