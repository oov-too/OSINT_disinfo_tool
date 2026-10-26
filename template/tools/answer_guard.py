"""Target check for answered-question writes (added 2026-10-01).

An agent's report names a note and a row; before an integrator writes the answer it calls
`check(report_item, row_question_text, where)`. The item may carry a "question" (or "lead")
field with the question it believes it is answering; the first six words of that field are
compared with the row's Question (or Lead) cell after normalisation. On mismatch, or when the
row is not an open-question or lead row at all, the write is refused and logged to
research/corrections/answer-refusals.md for a hand pass. An item with no question text passes
(the row number is all the agent gave), but the row still has to exist in the right table.
"""
import re, datetime, os

import sys as _sys; _T = os.path.dirname(os.path.abspath(__file__)); _sys.path.insert(0, _T) if _T not in _sys.path else None   # the ledger package beside this tool
from ledger.paths import root as _project_root; ROOT = _project_root()   # $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder, else this tools' project (2026-10-22)
LOG = os.path.join(ROOT, "research/corrections/answer-refusals.md")

def _norm(t):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(t or ""))
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return [w for w in t.split() if w not in ("the", "a", "an", "of", "in", "on", "to", "and", "is", "was", "that", "which", "whether")]

def matches(report_q, row_q, n=6):
    a = _norm(report_q)[:n]; b = _norm(row_q)
    if not a: return True
    if len(a) < 3: return " ".join(a) in " ".join(b)
    hits = sum(1 for w in a if w in b)
    return hits >= max(3, len(a) - 2)

def check(item, row_q, where, label=""):
    """Return True to write; on refusal, log and return False."""
    q = item.get("question") or item.get("lead") or item.get("question_text") or ""
    if row_q is None:
        _log(where, item, "row not found in the Open questions table or the Lead register", label); return False
    if q and not matches(q, row_q):
        _log(where, item, f"question mismatch: report says '{str(q)[:90]}' / row says '{str(row_q)[:90]}'", label); return False
    return True

def _log(where, item, reason, label):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8") as f:
        if new: f.write("# Answer refusals (target check, tools/answer_guard.py)\n\nEach line is an answered_questions item an integrator refused to write; apply by hand or correct the row number.\n\n")
        f.write(f"- {datetime.date.today().isoformat()} [{label}] {where}: {reason}. Answer: {str(item.get('answer',''))[:300].replace(chr(10),' ')}\n")
    print(f"  answered_questions REFUSED ({where}): {reason}")
