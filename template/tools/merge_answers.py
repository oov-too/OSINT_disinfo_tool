"""Append answers the integrator left unchanged ('already answered differently'): for every answered_questions item in a report,
if the target row's Answer cell does not already contain the answer's first 60 chars, append 'Added <date> (<short>): <answer>'.
Upgrades checked -> closed when the item asks for closed. Usage: merge_answers.py <report.json> "<short>" """
import json, re, sys, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import answer_guard
from ledger import notes as LN   # the parser library (tools/ledger/notes.py, phase 2)
rep=json.load(open(sys.argv[1])); short=sys.argv[2]; today=datetime.date.today().isoformat()
fname=os.path.basename(rep["file"])
NOTE_DIR = (rep.get('file','') or '').split('/')[0] if (rep.get('file','') or '').split('/')[0] in ('videos','books') else 'videos'  # book notes live in books/ (2026-09-28)
for it in rep.get("answered_questions") or []:
    note=it["note"]; note=note if "/" in note else "videos/"+note
    if not os.path.exists(note): print("missing", note); continue
    s=LN.read_text(note)
    if note.startswith("research/leads"):
        head="| # | Lead |"; link=f"[{short}](../{NOTE_DIR}/{fname})"
    else:
        head="## Open questions"; link=f"[{short}]({fname})"
    i=s.find(head)
    if i<0: print("no section", note); continue
    seg=s[i:]; m=LN.row_match(seg, it["row"], tail=r" .*$")   # form R2
    if not m: answer_guard.check(it, None, f"{note} row {it['row']}", short); continue
    row=m.group(0); cells=LN.split_spaced(row)
    cols=LN.split_row(row)
    if len(cols) < 10:   # short rows (no Answer / Answered-by / Answered-on cells) padded to the table's ten columns (2026-10-03)
        cols += [""] * (10 - len(cols)); row2 = LN.join_row(cols); seg = seg.replace(row, row2, 1); row = row2; cells = LN.split_spaced(row)
    qi = 1 if note.startswith("research/leads") else 3   # the question cell: Lead in the register, Question (after Kind, Asked by) in a note (fixed 2026-10-03)
    if not answer_guard.check(it, cells[qi] if len(cells)>qi else "", f"{note} row {it['row']}", short): continue
    ans=str(it.get("answer","")).replace("|","/")
    if ans[:60] in row or ans.split(': ',1)[-1][:60] in row: continue  # already applied
    # column indexes: leads: 7 status, 8 answer, 9 answered by, 10 answered on; OQ: 6 status, 7 answer, 8 answered by, 9 answered on
    si = 6  # split on " | " puts the row number in cells[0]; Status is cells[6] in both tables
    ai = si+1
    cells[ai]=(cells[ai].strip()+" " if cells[ai].strip() else "")+f"Added {today} ({link}): {ans}"
    if it.get("status")=="closed" and cells[si].strip() in ("open","checked"): cells[si]="closed"
    elif it.get("status")=="checked" and cells[si].strip()=="open": cells[si]="checked"
    if cells[ai+1].strip()=="" : cells[ai+1]=f"note: {link}"
    if ai+2 >= len(cells): continue
    if cells[ai+2].strip() in ("", "|"): cells[ai+2]=f"{today} |" if cells[ai+2].strip()=="|" or ai+2==len(cells)-1 else today
    new=" | ".join(cells)
    s=s[:i]+seg.replace(row,new,1); LN.write_text(note, s); print("merged", note, it["row"], "->", cells[si].strip())
