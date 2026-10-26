#!/usr/bin/env python3
"""Validate an agent's report.json before it replies (tools/narratives.md, token rule of 2026-10-09; the shape drift of 2026-10-08 cost
orchestrator tokens on every run). Usage: python3 tools/report_check.py <report.json> --form <form> [--pre-sample]
Forms: narrative (builder), fork, attack, revise, synchrony, register, intake-document, intake-video, and integrate (only the lists
`ledger integrate` reads, and `file`; the form its --report-check step uses). Checks required keys, basic types, the v0.3 score line
where one is reported (the trailing `thin nodes N of N` axis optional), the optional keys (thin_nodes, an int, under the narrative,
fork, attack and revise forms; 2026-10-25), and that blocked_passages is present (a list). Exit 1 and a list of problems on failure.
The agent fixes the report and reruns; it never replies with a failing report.

Every list `ledger integrate` reads is checked element by element, whatever the form, against exactly what the integrate step
consumes (2026-10-22: two report shapes passed this check and then stopped `ledger integrate`): register_new and register_updates
(tools/integrate_report.py, the object register), relations, chain_leads and leads, answered_questions (integrate_report.py),
first_telling_rows (tools/first_utterance.py --apply) and the actor rows (the pack's [actors] rows_key, actor_rows in the core;
the actors step of tools/ledger/cli.py, placed in the register's own columns). A problem names the list, the element's index and
the shape the step accepts. A key the step does not read is a warning (its value would be dropped), not a failure.

Under the intake forms (intake-document, intake-video, integrate) the note the report names in `file` is read too: an unfilled
`<!-- fill -->` marker left anywhere in it is a failure (2026-10-23, the round-trip REPORT.md finding 5: six of nine finished notes
kept markers and passed this check; tools/note_fill.py --check fails them by the same rule, the marker counted on every line).

Under the intake forms `sample_reading` is required (2026-10-25, the owner's ruling: the sample reading is a phase of every intake,
after the finish phase and before integration). The workflow writes it (`ledger sample tally`, tools/ledger/sample.py) after the
reader of the twenty sampled rows replies: {rows, sound, formal, meaning, by_owner {reader, writer, form}, meaning_rows, files}, with
`redraw` of the same shape after a check phase, or {"skipped": "<reason>"} when a task ran with `sample: false`. A check run before
that phase (the agent's own, at the end of its intake, and the plugin's SubagentStop hook) takes --pre-sample: the key's absence
is then a note, not a failure; its shape is still checked when present."""
import json, os, re, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)

SCORE = re.compile(r"^Narrative scores: clusters \d+, rows \d+, roots \d+, circle roots \d+, reading roots \d+, contradictions \d+, load [\d.]+, max downstream \d+,(?: closures predicted \d+ of \d+,)? unaffiliated roots \d+ of \d+, survive under rival \d+ of \d+, tests \d+(?:, thin nodes \d+ of \d+)?\.$")   # the thin-nodes axis optional (tools/narratives.md section 8e, 2026-10-25)
FORMS = {
 "narrative": {"page": str, "nodes": int, "roots": int, "contradictions": int, "load": (int, float), "max_downstream": int, "forks": list, "flares": int, "signals": int, "tests": int, "leads": int, "relations": int, "notes": str, "score_line": str},
 "fork": {"page": str, "parent": str, "fork_node": int, "nodes": int, "inherited": int, "rebuilt": int, "roots": int, "contradictions": int, "load": (int, float), "delta_load": (int, float), "delta_coverage": int, "anomalies_absorbed": int, "anomaly_clusters": int, "discriminating_clusters": int, "nodes_broken": int, "flare_assumed": str, "tests": int, "leads": int, "relations": int, "notes": str, "score_line": str},
 "attack": {"page": str, "citations_checked": int, "citation_misses": int, "broken_nodes": list, "roots_author": int, "roots_attacker": int, "missing_contradictions": int, "flares_disputed": int, "rowless_edges_struck": int, "objections": int, "leads": int, "score_line": str, "notes": str},
 "revise": {"page": str, "objections_answered": int, "objections_declined": int, "nodes_repaired": int, "nodes_dropped": int, "edges_removed": int, "ledger_rows_added": int, "flares_rewritten": int, "rows_revised_from_new_notes": int, "score_line_revised": str, "leads": int, "relations": int, "notes": str},
 "synchrony": {"page": str, "rows_considered": int, "windows": int, "co_movements": int, "contradictions": int, "flares": int, "signals": int, "leads": int, "relations": int, "lane_reassignments": int, "notes": str},
 "register": {"page": str, "narratives": int, "forks": int, "recurring_contradictions": int, "recurring_signals": int, "next_items": int, "leads": int, "relations": int, "notes": str},
 "intake-document": {"source_kind": str, "earliest_telling_search": str, "roots_added": list, "first_telling_rows": list, "file": str, "subject_rows": dict, "register_new": list, "register_updates": list, "relations": list, "chain_leads": list, "answered_questions": list, "actor_rows": list, "timeline_rows": int, "claims_rows": int, "audit_counts": str, "narrative_rows_addressed": list, "notes": str},
 "intake-video": {"source_kind": str, "earliest_telling_search": str, "roots_added": list, "first_telling_rows": list, "file": str, "words": int, "claims_rows": int, "audit_rows": int, "audit_counts": str, "subject_rows": dict, "relations": list, "chain_leads": list, "answered_questions": list, "timeline_rows": int, "actor_rows": list, "notes_on_intent": str},
 "integrate": {"file": str},
}

# ---------------------------------------------------------------- the lists `ledger integrate` reads
EXAMPLE = {
    "register_new": '{"video": "", "timestamp": "0:41:10", "who": "<witness>", "object": "<the object as described>", "match": "<criteria met>", "strength": "weak"}'
                    ' (or {"text": "| new | <video> | <time> | <who> | <object> | <match> | <strength> |"})',
    "register_updates": '{"entry": 12, "text": "| 12 | <video> | <time> | <who> | <object> | <match> | <strength> |"} (the whole revised row, numbered as the entry)',
    "relations": '{"a": "<person or body>", "b": "<person or body>", "relation": "<kind>", "hierarchy": "", "when": "", "what": "", "source": "", "chain": "", "confidence": "medium"}',
    "chain_leads": '{"lead": "<the inference or thread>", "kind": "inference", "sources": "<rows>", "settles": "<the test that would settle it>"}',
    "leads": '{"lead": "<the lead>", "kind": "lead", "sources": "<rows>", "settles": "<the test that would settle it>"}',
    "first_telling_rows": '{"cluster": "FU-12" (or "new: <the claim>"), "row": "<note row>", "date": "YYYY-MM-DD", "venue": "<where it was told>", "event": "<short label, for a new cluster>"}',
    "answered_questions": '{"note": "videos/<note>.md", "row": 3, "status": "checked" (or "closed"), "answer": "<the answer>", "answered_by": "note: [<label>](<link>)", "question": "<the row\'s question, for the target check>"}',
    "actor_rows": '"| new | <kind as the teller names it> | <body> | <teller and note row> | <chain> | ... |" (one cell per register column after #), or a dict keyed by the register\'s column names',
}
READS = {
    "register_new": {"video", "timestamp", "who", "object", "match", "strength", "text"},
    "register_updates": {"entry", "text"},
    "relations": {"a", "b", "relation", "kind", "hierarchy", "when", "what", "source", "source (time)", "chain", "confidence"},
    "chain_leads": {"lead", "kind", "sources", "settles"},
    "leads": {"lead", "kind", "sources", "settles"},
    "first_telling_rows": {"cluster", "row", "date", "venue", "event"},
    "answered_questions": {"note", "row", "status", "answer", "answered_by", "settles", "question", "lead", "question_text"},
}
# Optional keys per form, checked for type when present (2026-10-25: the basis audit's thin-node count, tools/narratives.md section 8e)
OPTIONAL = {"narrative": {"thin_nodes": int}, "fork": {"thin_nodes": int}, "attack": {"thin_nodes": int}, "revise": {"thin_nodes": int}}
ISO = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
ROWNUM = re.compile(r"^\d+(\.\d+)?$")


class Context:
    """What the checks need from the project: the object register's match-key aliases, the actor rows' report key and the actor
    register's header, the first-utterance cluster ids, and whether a note exists. Each is None when it cannot be read (the check then
    falls back to the element's shape alone)."""
    def __init__(self, root=None, match_keys=(), rows_key="actor_rows", header=None, fu_ids=None, note_exists=None):
        self.root = root; self.match_keys = {k.lower() for k in match_keys}; self.rows_key = rows_key
        self.header = header; self.fu_ids = fu_ids; self.note_exists = note_exists

    @classmethod
    def of_project(cls):
        from ledger import paths as LP, notes as LN
        root = LP.root(); ctx = cls(root=root)
        try:
            import packload
            p = packload.pack()
            ctx.match_keys = {k.lower() for k in (packload.tool_data("integrate_report").get("register_match_keys") or [])}
            ctx.rows_key = p.get("actors", {}).get("rows_key") or "actor_rows"
            reg = p.get("actors", {}).get("register")
            if reg and os.path.exists(os.path.join(root, reg)):
                from ledger import cli
                ctx.header = cli._actor_header(LN.read_lines(os.path.join(root, reg)))
        except Exception:
            pass
        fu = os.path.join(root, "research", "first-utterance-register.md")   # tools/first_utterance.py's REG
        if os.path.exists(fu):
            ctx.fu_ids = {m.group(1) for m in re.finditer(r"^\|\s*(FU-\d+)\s*\|", LN.read_text(fu), re.M)}
        ctx.note_exists = lambda rel: os.path.exists(os.path.join(root, rel))
        return ctx


def _s(v): return isinstance(v, str) and v.strip() != ""


INTAKE_FORMS = ("intake-document", "intake-video", "integrate")


def check_lists(rep, ctx, form="integrate"):
    """(problems, warnings) for every list `ledger integrate` reads that the report carries. Under the narrative forms `leads` and
    `relations` are counts, not lists, and are checked only where they are lists."""
    probs, warns = [], []
    def bad(key, i, what, ex_key=None): probs.append(f"{key}[{i}]: {what}; accepted: {EXAMPLE[ex_key or key]}")
    def unread(key, i, it, reads):
        extra = sorted(k for k in it if k.lower() not in reads and k not in reads)
        if extra: warns.append(f"{key}[{i}]: key(s) {', '.join(extra)} are not read by the integrate step; their values would be dropped")
    def items(key):
        v = rep.get(key)
        if v is None: return []
        if not isinstance(v, list) and form not in INTAKE_FORMS: return []
        if not isinstance(v, list): probs.append(f"{key}: {type(v).__name__}, expected a list (of elements like {EXAMPLE[key if key in EXAMPLE else 'actor_rows']})"); return []
        return list(enumerate(v))

    for i, it in items("register_new"):
        if not isinstance(it, dict): bad("register_new", i, f"a {type(it).__name__}, not an object (integrate_report reads each element as a dict)"); continue
        low = {k.lower(): v for k, v in it.items()}
        if "object" in low or any(k in ctx.match_keys for k in low):
            if not _s(low.get("object")): bad("register_new", i, "no `object` (the register's Object cell)")
            unread("register_new", i, {k: v for k, v in it.items() if k.lower() not in ctx.match_keys}, READS["register_new"])
        elif "text" in low:
            t = low["text"]
            if not (isinstance(t, str) and t.lstrip().startswith("|")): bad("register_new", i, "`text` is not a table row")
            elif len([c for c in t.strip().strip("|").split(" | ")]) < 7: bad("register_new", i, "`text` row has fewer than seven cells (#, video, timestamp, who, object, match, strength)")
        else: bad("register_new", i, f"neither `object` nor `text` (keys: {', '.join(sorted(it)) or 'none'})")
    for i, it in items("register_updates"):
        if not isinstance(it, dict): bad("register_updates", i, f"a {type(it).__name__}, not an object"); continue
        e, t = it.get("entry"), it.get("text")
        if e is None or not ROWNUM.match(str(e)): bad("register_updates", i, "no `entry` number"); continue
        if not (isinstance(t, str) and t.strip().startswith(f"| {e} |")): bad("register_updates", i, f"`text` must be the whole revised row starting `| {e} |` (an update in any other form is not applied)")
        unread("register_updates", i, it, READS["register_updates"])
    for i, it in items("relations"):
        if not isinstance(it, dict): bad("relations", i, f"a {type(it).__name__}, not an object"); continue
        if not (_s(it.get("a")) and _s(it.get("b"))):
            alt = [k for k in ("A", "B", "from", "to") if k in it]
            bad("relations", i, "no `a` and `b` (lower case)" + (f"; {', '.join(alt)} are not read, so the row would be skipped" if alt else ""))
            continue
        if not (_s(it.get("relation")) or _s(it.get("kind"))): bad("relations", i, "no `relation` (or `kind`)")
        unread("relations", i, it, READS["relations"])
    for key in ("chain_leads", "leads"):
        for i, it in items(key):
            if not isinstance(it, dict): bad(key, i, f"a {type(it).__name__}, not an object"); continue
            if not _s(it.get("lead")): bad(key, i, "no `lead`"); continue
            if not _s(it.get("settles")):
                alt = [k for k in ("test", "what_would_settle_it") if _s(it.get(k))]
                bad(key, i, "no `settles` (every lead carries its test)" + (f"; `{alt[0]}` is not read, the register would say `unknown`" if alt else ""))
            unread(key, i, it, READS[key])
    for i, it in items("first_telling_rows"):
        if not isinstance(it, dict): bad("first_telling_rows", i, f"a {type(it).__name__}, not an object"); continue
        c = str(it.get("cluster", "")).strip()
        if c.lower().startswith("new:"):
            if not c[4:].strip(): bad("first_telling_rows", i, "`new:` without the claim")
        elif not re.match(r"^FU-\d+$", c): bad("first_telling_rows", i, f"cluster {c!r} is neither a register id `FU-n` nor `new: <claim>`")
        elif ctx.fu_ids is not None and c not in ctx.fu_ids: bad("first_telling_rows", i, f"cluster {c} is not in the first-utterance register (the item would be skipped)")
        if not _s(it.get("row")): bad("first_telling_rows", i, "no `row`")
        d = str(it.get("date", "") or "").strip()
        if d and not ISO.match(d): bad("first_telling_rows", i, f"date {d!r} is not YYYY, YYYY-MM or YYYY-MM-DD (dates are compared as text)")
        unread("first_telling_rows", i, it, READS["first_telling_rows"])
    for i, it in items("answered_questions"):
        if not isinstance(it, dict): bad("answered_questions", i, f"a {type(it).__name__}, not an object"); continue
        note = str(it.get("note", "")).strip()
        if not note: bad("answered_questions", i, "no `note`"); continue
        rel = note if "/" in note else "videos/" + note; rel = rel if rel.endswith(".md") else rel + ".md"
        if ctx.note_exists and not ctx.note_exists(rel): bad("answered_questions", i, f"note {rel} does not exist")
        if it.get("row") is None or not ROWNUM.match(str(it.get("row")).strip()): bad("answered_questions", i, "no `row` number (the target row's # cell)")
        if str(it.get("status", "")).strip().lower() not in ("checked", "closed"): bad("answered_questions", i, f"status {it.get('status')!r} is not `checked` or `closed`")
        if not _s(it.get("answer")): bad("answered_questions", i, "no `answer`")
        unread("answered_questions", i, it, READS["answered_questions"])
    keys = [ctx.rows_key] + (["actor_rows"] if ctx.rows_key != "actor_rows" and "actor_rows" in rep else [])
    for key in keys:
        v = rep.get(key)
        if v is None: continue
        if not isinstance(v, list): probs.append(f"{key}: {type(v).__name__}, expected a list (of elements like {EXAMPLE['actor_rows']})"); continue
        for i, it in enumerate(v):
            if ctx.header:
                from ledger import cli
                try: cli.actor_cells(it, ctx.header)
                except ValueError as e: probs.append(f"{key}[{i}]: {e}; accepted: {EXAMPLE['actor_rows']}")
            else:
                s = it.get("row") if isinstance(it, dict) and isinstance(it.get("row"), str) else it
                if isinstance(s, str):
                    c0 = s.strip().strip("|").split("|")[0].strip().strip("()").lower() if s.strip().startswith("|") else None
                    if c0 is None: probs.append(f"{key}[{i}]: not a table row; accepted: {EXAMPLE['actor_rows']}")
                    elif not (c0.isdigit() or c0 in ("new", "next", "")): probs.append(f"{key}[{i}]: the first cell is {c0!r}, not `new` or a number; accepted: {EXAMPLE['actor_rows']}")
                elif not isinstance(it, dict): probs.append(f"{key}[{i}]: a {type(it).__name__}, neither a row nor an object; accepted: {EXAMPLE['actor_rows']}")
    return probs, warns


SAMPLE_PHASE = ("the sample phase writes it after the finish phase and before integration: `ledger sample draw`, the reader of the twenty "
                "rows (phasesDir/sample.md), then `ledger sample tally` (tools/ledger/sample.py); a check run before that phase takes --pre-sample")
SAMPLE_INTS = ("rows", "sound", "formal", "meaning")


def check_sample(rep, form, pre_sample=False):
    """(problems, notes) for the report's sample_reading under the intake forms; [] elsewhere."""
    if form not in INTAKE_FORMS: return [], []
    if "sample_reading" not in rep:
        return ([], [f"sample_reading not yet in the report ({SAMPLE_PHASE.split('; ')[0]})"]) if pre_sample else ([f"missing key: sample_reading ({SAMPLE_PHASE})"], [])
    def shape(v, where):
        if not isinstance(v, dict): return [f"{where}: {type(v).__name__}, expected an object {{rows, sound, formal, meaning, by_owner, meaning_rows, files}}"]
        if where == "sample_reading" and "skipped" in v and "rows" not in v:
            return [] if isinstance(v["skipped"], str) and v["skipped"].strip() else [f"{where}.skipped: give the reason as text"]
        out = []
        for k in SAMPLE_INTS:
            if not isinstance(v.get(k), int) or isinstance(v.get(k), bool) or v.get(k) < 0: out.append(f"{where}.{k}: {'missing' if k not in v else repr(v[k])}, expected a count")
        bo = v.get("by_owner")
        if not isinstance(bo, dict) or any(not isinstance(bo.get(o), int) or isinstance(bo.get(o), bool) for o in ("reader", "writer", "form")):
            out.append(f"{where}.by_owner: expected {{reader, writer, form}} counts")
        if not isinstance(v.get("meaning_rows"), list): out.append(f"{where}.meaning_rows: expected a list of row numbers")
        if not isinstance(v.get("files"), list) or not all(isinstance(f, str) for f in v.get("files") or []): out.append(f"{where}.files: expected a list of paths")
        if not out:
            if v["sound"] + v["formal"] + v["meaning"] > v["rows"]: out.append(f"{where}: sound {v['sound']} + formal {v['formal']} + meaning {v['meaning']} is more than rows {v['rows']}")
            if len(v["meaning_rows"]) != v["meaning"]: out.append(f"{where}.meaning_rows: {len(v['meaning_rows'])} row(s) listed for meaning {v['meaning']}")
            if sum(bo.values()) > v["rows"] - v["sound"]: out.append(f"{where}.by_owner: {sum(bo.values())} owners for {v['rows'] - v['sound']} faulty row(s)")
        if where == "sample_reading" and "redraw" in v: out += shape(v["redraw"], "sample_reading.redraw")
        return out
    return shape(rep["sample_reading"], "sample_reading"), []


FILL = "<!-- fill -->"   # tools/note_fill.py's marker


def fill_markers(rep, root):
    """[problem] for unfilled markers in the note the report's `file` names (resolved under root when relative); [] when the key is
    absent or the note does not exist (a missing note is the integrate step's own failure)"""
    f = rep.get("file")
    if not isinstance(f, str) or not f.endswith(".md"): return []
    path = f if os.path.isabs(f) else os.path.join(root, f)
    if not os.path.isfile(path): return []
    from ledger import notes as LN
    lines = LN.read_lines(path, errors="replace")
    hits = [i for i, l in enumerate(lines, 1) if FILL in l]
    if not hits: return []
    n = sum(lines[i - 1].count(FILL) for i in hits)
    return [f"{f}: {n} unfilled `{FILL}` marker(s) in the note (lines {', '.join(map(str, hits[:12]))}{', ...' if len(hits) > 12 else ''}); fill them (tools/note_fill.py, then --check) before the report"]


def check_form(rep, form, rows_key="actor_rows"):
    """Required keys and types; the actor rows' key is the pack's [actors] rows_key (core actor_rows)."""
    probs = []
    spec = {(rows_key if k == "actor_rows" else k): t for k, t in FORMS[form].items()}
    for k, t in spec.items():
        if k not in rep: probs.append(f"missing key: {k}"); continue
        if not isinstance(rep[k], t): probs.append(f"wrong type: {k} is {type(rep[k]).__name__}, expected {t if isinstance(t, tuple) else t.__name__}")
    for k, t in OPTIONAL.get(form, {}).items():
        if k in rep and (not isinstance(rep[k], t) or isinstance(rep[k], bool)): probs.append(f"wrong type: {k} is {type(rep[k]).__name__}, expected {t.__name__} (optional key)")
    if form != "integrate" and ("blocked_passages" not in rep or not isinstance(rep["blocked_passages"], list)): probs.append("missing or non-list key: blocked_passages (the blocked-output rule; [] when none)")
    for k in ("score_line", "score_line_revised"):
        if k in rep and isinstance(rep[k], str) and rep[k].strip():
            line = rep[k].strip()
            line = re.sub(r"^(author|attacker)( \(v\d\)| \(revised\))?:\s*", "", line)
            if not SCORE.match(line): probs.append(f"{k} is not the v0.3 form: {line[:120]}")
    if "subject_rows" in rep and isinstance(rep["subject_rows"], dict):
        for key in rep["subject_rows"]:
            if not key.startswith("subjects/") or not key.endswith(".md"): probs.append(f"subject_rows key must be a page path like subjects/<page>.md: {key}")
    if form != "integrate" and "openness_counts" in rep and isinstance(rep["openness_counts"], str): probs.append("openness_counts is a string; use a dict per speaker {speaker: {open, partial, closed_outright, closed_subtle, stated_declines, pseudo_declines}} or a single dict")
    return probs


def main(argv):
    path = argv[0]; form = argv[argv.index("--form") + 1] if "--form" in argv else "narrative"
    pre_sample = "--pre-sample" in argv
    try: rep = json.load(open(path, encoding="utf-8"))
    except Exception as e: print(f"FAIL: {path} is not valid JSON: {e}"); return 1
    if form not in FORMS: print(f"FAIL: unknown form {form}; forms: {', '.join(FORMS)}"); return 1
    if not isinstance(rep, dict): print(f"FAIL: {path} is a JSON {type(rep).__name__}, not an object"); return 1
    ctx = Context.of_project()
    probs = check_form(rep, form, ctx.rows_key)
    lp, warns = check_lists(rep, ctx, form)
    probs += lp
    if form in INTAKE_FORMS:
        from ledger import paths as LP
        probs += fill_markers(rep, LP.root())
    sp, sn = check_sample(rep, form, pre_sample)
    probs += sp
    for w in warns: print("WARN", w)
    for x in sn: print("NOTE", x)
    if probs:
        print("FAIL", path, f"({form}):"); [print(" -", x) for x in probs]; return 1
    print("OK", path, f"({form})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"): sys.exit(print(__doc__) or (0 if len(sys.argv) > 1 else 2))
    sys.exit(main(sys.argv[1:]))
