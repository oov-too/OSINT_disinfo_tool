"""The sample reading (owner 2026-10-25: a phase of every intake, in both projects, after the finish phase and before integration;
the brief is phasesDir/sample.md, template plugin/templates/briefs/staged/sample.md). The gates see quotations, citations and
pointers; they cannot see a paraphrase that says what the span does not. Twenty claims rows of the finished note, drawn by seed, are
read by one Opus reader five ways; this module draws the rows and tallies the reading.

  ledger sample draw <note> --wip wip/<task> [--n 20] [--seed S] [--round N] [--out wip/<task>/sample.md] [--json]
      twenty claims rows by a seed (default: a hash of the note's stem, and of `<stem>:<N>` for round N > 1), spread over the
      note's units in proportion to their rows (at least one per unit while twenty allow; the unit is the row's last pointer),
      each written as the note has it with the span its pointers pull (two lines either side, as `ledger quote` prints them); a
      row with no pointer (the single-agent form) is drawn at random over the ledger and given with its Time cell and the first
      `--find` hit for its longest quoted stretch where one exists, else alone. The head names the note, the seed, the row count
      and the spread. Round N > 1 writes sample-N.md (the redraw after the check phase). The pilot's sampler of 2026-10-23
      (research/tasks/tool-feedback/pilot-1023/pilot-run/reading/sample.py) and the forms measurement's are its ancestors.
  ledger sample tally --wip wip/<task> [--round N] [--threshold T] [--on-threshold check|flag] [--reply JSON] [--report PATH] [--json]
      the reader's sample-reading.tsv (sample-reading-N.tsv for round N) counted into the report's `sample_reading` key:
      {rows, sound, formal, meaning, by_owner {reader, writer, form}, meaning_rows, files, seed, threshold, over_threshold,
      action}; round N > 1 goes under `sample_reading.redraw`, so the report keeps both tallies. `action` is what the workflow
      does at the threshold: `check` (the check phase runs, then the redraw), `flag` (no check phase in this form, or the check
      already ran: the note integrates flagged), `none` (under the threshold). With no TSV the reader's reply (--reply) is
      counted instead; where both exist and differ, `reply_differs` says so. The threshold: --threshold, else the pack's
      `[intake] sample_threshold` (packload), else 3.

Both print one JSON object on the last line with --json (ok, summary and the counts), as the workflow's script probes relay it."""
import hashlib, json, os, random, re, sys

from ledger import notes as LN, quote as Q

N_DEFAULT = 20
THRESHOLD_DEFAULT = 3
PTR = re.compile(r"\[u (\d{3}):(\d+)(?:-(\d+))?\]")
QUOTED = re.compile(r"\"([^\"]+)\"|“([^”]+)”")
TSV_COLS = ("row", "verbatim", "support", "grain", "class_move", "chain", "verdict", "kind", "owner")
OWNERS = ("reader", "writer", "form")


def default_seed(stem, rnd=1):
    """A seed from the note's stem (and the round, from the second): the same note draws the same rows on every machine."""
    key = stem if rnd <= 1 else f"{stem}:{rnd}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)


def suffix(rnd): return "" if rnd <= 1 else f"-{rnd}"


def claims_rows(note_path):
    """[(n, line number, cells, raw line)] of the note's `## Claims ledger` section."""
    out, sec = [], None
    for i, l in enumerate(LN.read_lines(note_path, errors="replace"), 1):
        if l.startswith("## "): sec = l[3:].strip(); continue
        if sec == "Claims ledger" and LN.CLAIMS_ROW_RE.match(l):
            c = LN.split_row(l)
            if len(c) >= 8: out.append((c[0], i, c, l))
    return out


def _rownum(n):
    try: return float(n)
    except ValueError: return 0.0


def draw_rows(rows, n, seed):
    """(picked rows in note order, {unit: (taken, of)}): the pilot sampler's spread, at least one row per unit while n allows,
    the rest by largest remainder in proportion to each unit's rows; rows without a pointer form the bucket `none`."""
    by_unit = {}
    for r in rows:
        ps = PTR.findall(r[2][7])
        by_unit.setdefault(ps[-1][0] if ps else "none", []).append(r)
    units = sorted(by_unit); total = len(rows)
    take = {u: (1 if len(units) <= n else 0) for u in units}
    while sum(take.values()) < min(n, total):
        u = max(units, key=lambda x: (len(by_unit[x]) / total * n - take[x]) if take[x] < len(by_unit[x]) else -9)
        take[u] += 1
    rng = random.Random(seed); picked = []
    for u in units: picked += rng.sample(by_unit[u], min(take[u], len(by_unit[u])))
    picked.sort(key=lambda r: (_rownum(r[0]), r[1]))
    return picked, {u: (take[u], len(by_unit[u])) for u in units}


def _span_block(wip, u, a, b):
    """The pointer's lines with two either side, clamped to the unit's body, as `ledger quote` prints them."""
    try:
        lines = Q.unit_lines(wip, u)
        lo, hi = max(2, a - 2), min(len(lines), b + 2)
        header, body = Q.span(wip, u, lo, hi)
        return f"[u {u}:{lo}-{hi}] {header}", body
    except Q.PointerError as e:
        return f"[u {u}:{a}-{b}] not pulled: {e}", []


def quoted_stretches(cells):
    """The quoted stretches of a row's Claim and Note cells, longest first (by words)."""
    found = []
    for c in (cells[4], cells[7] if len(cells) > 7 else ""):
        for m in QUOTED.finditer(c or ""):
            s = (m.group(1) or m.group(2) or "").strip()
            if len(Q.WORD_RE.findall(s)) >= 2: found.append(s)
    return sorted(dict.fromkeys(found), key=lambda s: -len(Q.WORD_RE.findall(s)))


def first_find(wip, cells):
    """(phrase, hit) for the longest quoted stretch that --find locates (the next longest when it does not), else (None, None)."""
    for s in quoted_stretches(cells):
        try: hits, _ = Q.find(wip, s)
        except Q.PointerError: continue
        if hits: return s, hits[0]
    return None, None


def _rel(p, root):
    try:
        r = os.path.relpath(os.path.realpath(p), os.path.realpath(root))
        return r if not r.startswith("..") else p
    except ValueError: return p


def draw(note, wip, n=N_DEFAULT, seed=None, rnd=1, out=None, root=None):
    """Write the sample file; return the summary dict the --json line carries."""
    root = root or os.getcwd()
    stem = os.path.splitext(os.path.basename(note))[0]
    seed = default_seed(stem, rnd) if seed is None else seed
    rows = claims_rows(note)
    picked, spread = draw_rows(rows, n, seed)
    out = out or os.path.join(wip, f"sample{suffix(rnd)}.md")
    rel_note, rel_wip = _rel(note, root), _rel(wip, root)
    pointered = sum(1 for r in rows if PTR.search(r[2][7]))
    spread_s = ", ".join(f"unit {u} {t} of {k}" if u != "none" else f"no pointer {t} of {k}" for u, (t, k) in spread.items())
    L = [f"# Sample of `{rel_note}`: {len(picked)} of {len(rows)} claims rows, seed {seed}" + (f", round {rnd}" if rnd > 1 else "") + f" (spread: {spread_s})", "",
         f"Note `{rel_note}` (a row and its neighbours: `grep -n \"^| <n> |\" {rel_note}`); task folder `{rel_wip}`; the source's words by "
         f"pointer `ledger quote --wip {rel_wip} u NNN:L-M`, by word `ledger quote --wip {rel_wip} --find \"<a few of the words>\"`. "
         + ("Each row is given as the note has it, then the span each pointer pulls with two lines either side." if pointered == len(rows) else
            "Rows without a unit pointer (the single-agent form) are given with their Time cell and the first `--find` hit for their longest "
            "quoted stretch where one exists; locate the rest by the Time cell in the units, and say `not found` where neither finds it."), ""]
    found = 0
    for num, line_no, c, raw in picked:
        L += [f"## Row {num} (note line {line_no})", "", "| # | Time | Speaker | Topic | Claim | Source class | Move | Note |", "|---|---|---|---|---|---|---|---|", raw, ""]
        ps = PTR.findall(c[7])
        if ps:
            for u, a, b in ps[-4:]:
                a, b = int(a), int(b or a)
                head, body = _span_block(wip, u, a, b)
                L += [f"Span of pointer [u {u}:{a}{'-' + str(b) if b != a else ''}]: {head}", "```", *body, "```", ""]
        else:
            L += [f"No unit pointer; Time cell: `{c[1]}`.", ""]
            phrase, hit = first_find(wip, c)
            if hit:
                found += 1
                (sa, _), (sb, _) = hit["sentence"]
                head, body = _span_block(wip, hit["unit"], sa, sb)
                L += [f"First `--find` hit for \"{phrase}\": [u {hit['unit']}:{sa}-{sb}]; {head}", "```", *body, "```", ""]
            else:
                L += ["No `--find` hit for a quoted stretch of this row" + ("" if quoted_stretches(c) else " (it quotes nothing)") + ": locate the passage by the Time cell.", ""]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    LN.write_text(out, "\n".join(L).rstrip("\n") + "\n")
    return {"ok": bool(picked), "summary": f"{len(picked)} of {len(rows)} claims rows drawn by seed {seed} ({spread_s}) -> {_rel(out, root)}" if picked else f"no claims rows in {rel_note}",
            "file": _rel(out, root), "rows": len(picked), "total": len(rows), "seed": seed, "round": rnd, "spread": {u: list(v) for u, v in spread.items()},
            "pointers": pointered == len(rows), "found_by_find": found, "threshold": threshold()}


def threshold(given=None):
    """The count of faults of meaning in the twenty that sends a note to the check phase: given, else the pack's
    [intake] sample_threshold, else 3."""
    if given is not None: return int(given)
    try:
        import packload
        return int(packload.sample_threshold())
    except Exception:
        return THRESHOLD_DEFAULT


def read_tsv(path):
    """[{col: value}] of a sample-reading TSV (a header line, when present, is skipped)."""
    out = []
    for l in LN.read_lines(path, errors="replace"):
        if not l.strip() or l.startswith("#"): continue
        c = [x.strip() for x in l.split("\t")]
        if c[0].lower() in ("row", "#"): continue
        out.append(dict(zip(TSV_COLS, c + [""] * (len(TSV_COLS) - len(c)))))
    return out


def count(lines):
    """The tally of a reading's lines: rows, sound, formal, meaning, by_owner, meaning_rows."""
    sound = sum(1 for x in lines if x["verdict"].lower().startswith("sound"))
    faulty = [x for x in lines if not x["verdict"].lower().startswith("sound")]
    meaning = [x for x in faulty if x["kind"].lower().startswith("meaning")]
    formal = [x for x in faulty if x["kind"].lower().startswith("formal")]
    by_owner = {o: sum(1 for x in faulty if x["owner"].lower().startswith(o)) for o in OWNERS}
    return {"rows": len(lines), "sound": sound, "formal": len(formal), "meaning": len(meaning), "by_owner": by_owner,
            "meaning_rows": [x["row"] for x in meaning]}


def tally(wip, rnd=1, thr=None, on_threshold="check", reply=None, report=None, root=None):
    """Count the reading, write it into report.json's sample_reading (round 1) or sample_reading.redraw (round N > 1), and return
    the summary dict."""
    root = root or os.getcwd()
    sfx = suffix(rnd)
    tsv = os.path.join(wip, f"sample-reading{sfx}.tsv")
    md = os.path.join(wip, f"sample-reading{sfx}.md")
    sample_md = os.path.join(wip, f"sample{sfx}.md")
    thr = threshold(thr)
    if os.path.isfile(tsv):
        t = count(read_tsv(tsv)); src = "tsv"
    elif isinstance(reply, dict) and isinstance(reply.get("rows"), int):
        bo = reply.get("by_owner") if isinstance(reply.get("by_owner"), dict) else {}
        t = {"rows": reply["rows"], "sound": int(reply.get("sound") or 0), "formal": int(reply.get("formal") or 0), "meaning": int(reply.get("meaning") or 0),
             "by_owner": {o: int(bo.get(o) or 0) for o in OWNERS}, "meaning_rows": [str(x) for x in (reply.get("meaning_rows") or [])]}
        src = "reply"
    else:
        return {"ok": False, "summary": f"no reading to count: {_rel(tsv, root)} does not exist and the reply carries no counts", "round": rnd}
    head = LN.read_lines(sample_md, errors="replace")[0] if os.path.isfile(sample_md) else ""
    m = re.search(r"seed (\d+)", head)
    t.update({"files": [_rel(p, root) for p in (sample_md, md, tsv) if os.path.isfile(p)], "seed": int(m.group(1)) if m else None, "source": src})
    if src == "tsv" and isinstance(reply, dict):
        diff = [k for k in ("rows", "sound", "formal", "meaning") if isinstance(reply.get(k), int) and reply[k] != t[k]]
        if diff: t["reply_differs"] = ", ".join(f"{k} {reply[k]} in the reply, {t[k]} in the TSV" for k in diff)
    over = t["meaning"] >= thr
    t.update({"threshold": thr, "over_threshold": over, "action": (on_threshold if over else "none")})
    report = report or os.path.join(wip, "report.json")
    rep = {}
    if os.path.isfile(report):
        try: rep = json.loads(LN.read_text(report))
        except ValueError as e: return {"ok": False, "summary": f"{_rel(report, root)} is not valid JSON ({e}); the tally is not written", "round": rnd, **t}
    if rnd <= 1:
        old = rep.get("sample_reading") if isinstance(rep.get("sample_reading"), dict) else {}
        rep["sample_reading"] = {**t, **({"redraw": old["redraw"]} if "redraw" in old else {})}
    else:
        if not isinstance(rep.get("sample_reading"), dict): return {"ok": False, "summary": "a redraw without the first reading in the report", "round": rnd, **t}
        rep["sample_reading"]["redraw"] = {**t, "round": rnd}
    LN.write_text(report, json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    line = tally_line(t)
    return {"ok": True, "summary": f"{line}; threshold {thr}: {'reached, action ' + t['action'] if over else 'not reached'} -> {_rel(report, root)} sample_reading" + (".redraw" if rnd > 1 else ""),
            "round": rnd, "report": _rel(report, root), **t}


def tally_line(t):
    """`meaning M of R (sound S, formal F; reader X, writer Y, form Z)`: the form the cost log and the status page carry."""
    bo = t.get("by_owner") or {}
    return (f"meaning {t.get('meaning', 0)} of {t.get('rows', 0)} (sound {t.get('sound', 0)}, formal {t.get('formal', 0)}; "
            f"reader {bo.get('reader', 0)}, writer {bo.get('writer', 0)}, form {bo.get('form', 0)})")


def summary_line(sr):
    """The report's sample_reading as one cell: the first tally and, after a check, the redraw's; `none` when absent."""
    if not isinstance(sr, dict) or "rows" not in sr: return "none" if not (isinstance(sr, dict) and sr.get("skipped")) else f"skipped ({sr['skipped']})"
    s = "sample: " + tally_line(sr)
    if sr.get("over_threshold"): s += f"; threshold {sr.get('threshold')} reached ({sr.get('action')})"
    if isinstance(sr.get("redraw"), dict): s += "; after the check: " + tally_line(sr["redraw"])
    return s


COST_HEADER = ["| Run | Date | Agent | Phase | Model | Turns | Calls | Cache-create | Cache-read | Cache-read (records) | Output (est) | Context at end | Wall | Result |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]   # tools/agent_usage.py's cost log columns
COST_AGENT = "**sample reading, {task}**"
COST_ROW_RE = re.compile(r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*\*\*sample reading, ([^*|]+)\*\*\s*\|.*\|\s*(sample: [^|]*|none|skipped[^|]*?)\s*\|\s*$")


def cost_row(task, run, note, sr, day):
    """The cost log's line for a task's sample reading: the Agent cell names the task, the Phase cell `Sample`, the Result cell the
    tally and the note (`ledger integrate` writes it; tools/build_status.py reads it back for the per-note column)."""
    res = summary_line(sr) + (f"; note {note}" if note else "")
    return f"| {run or task} | {day} | {COST_AGENT.format(task=task)} | Sample | | | | | | | | | | {res.replace('|', '/')} |"


def record_cost_log(report_path, run=None, path=None, day=None):
    """Write (or replace) the task's sample line in the cost log; returns the message `ledger integrate` prints."""
    import datetime
    from ledger import paths
    rep = json.loads(LN.read_text(report_path))
    sr = rep.get("sample_reading")
    task = os.path.basename(os.path.dirname(os.path.abspath(report_path)))
    if path is None:
        import packload
        path = os.path.join(paths.root(), packload.display("status")["cost_log"])
    if sr is None: return f"sample reading: the report carries no sample_reading; nothing written to {os.path.basename(path)} (the status page shows `none`)"
    line = cost_row(task, run, rep.get("file") or "", sr, day or datetime.date.today().isoformat())
    old = LN.read_lines(path) if os.path.exists(path) else []
    if old and old[-1] == "": old = old[:-1]
    agent = COST_AGENT.format(task=task)
    hit = [i for i, l in enumerate(old) if l.startswith("|") and f"| {agent} |" in l]
    if hit:
        old[hit[-1]] = line; verb = "replaced"
    elif old:
        old.append(line); verb = "appended"
    else:
        old = ["# Cost log", "", "Per-agent usage of each Workflow run, appended by `python3 tools/agent_usage.py <run> --append-cost-log`; the sample "
               "reading's line per task by `ledger integrate`.", ""] + COST_HEADER + [line]; verb = "written"
    LN.write_text(path, "\n".join(old) + "\n")
    return f"sample reading: {summary_line(sr)}; line {verb} in {os.path.relpath(path, paths.root())}"


def cost_log_readings(path):
    """{note path: (task, run, date, result cell)} from the cost log's sample lines, the last line per note winning."""
    out = {}
    if not os.path.exists(path): return out
    for l in LN.read_lines(path, errors="replace"):
        m = COST_ROW_RE.match(l)
        if not m: continue
        run, day, task, res = m.groups()
        nm = re.search(r"; note (\S+\.md)\s*$", res)
        out[nm.group(1) if nm else task] = (task.strip(), run, day, re.sub(r"; note \S+\.md\s*$", "", res))
    return out


def _resolve(p, root):
    """A path as given when it exists from the working folder, else under the project root (as `ledger quote --wip` resolves)."""
    if p is None or os.path.isabs(p): return p
    if os.path.exists(p): return os.path.abspath(p)
    return os.path.join(root, p)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help") or a[0] not in ("draw", "tally"): print(__doc__); return 0 if a and a[0] in ("-h", "--help") else 2
    cmd, a = a[0], a[1:]
    def take(flag, default=None):
        if flag not in a: return default
        i = a.index(flag)
        if i + 1 >= len(a): raise SystemExit(f"ledger sample: {flag} needs a value")
        v = a[i + 1]; del a[i:i + 2]; return v
    as_json = "--json" in a
    if as_json: a.remove("--json")
    from ledger import paths
    root = paths.root()
    wip = _resolve(take("--wip"), root); rnd = int(take("--round", "1"))
    if not wip or not os.path.isdir(wip): print(f"ledger sample {cmd}: --wip wip/<task> is required and must exist", file=sys.stderr); return 2
    if cmd == "draw":
        n = int(take("--n", str(N_DEFAULT))); seed = take("--seed"); out = take("--out")
        if len(a) != 1: print("ledger sample draw: one note expected", file=sys.stderr); return 2
        note = _resolve(a[0], root)
        if not os.path.isfile(note): print(f"ledger sample draw: {a[0]} not found", file=sys.stderr); return 2
        r = draw(note, wip, n, int(seed) if seed is not None else None, rnd, _resolve(out, root) if out else None, root=root)
    else:
        thr = take("--threshold"); on = take("--on-threshold", "check"); rep = take("--report"); reply = take("--reply")
        if on not in ("check", "flag"): print("ledger sample tally: --on-threshold check or flag", file=sys.stderr); return 2
        try: reply = json.loads(reply) if reply else None
        except ValueError: reply = None
        r = tally(wip, rnd, thr, on, reply, _resolve(rep, root), root=root)
    print(json.dumps(r, ensure_ascii=False) if as_json else r["summary"])
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
