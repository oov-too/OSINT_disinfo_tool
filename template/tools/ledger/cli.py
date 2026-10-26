"""The `ledger` command (phase 2 of tools/platform-plan.md, 2026-10-22): one entry point over the tools in tools/, grouped by layer.

  ledger <layer> <tool> [the tool's own arguments]     run one tool exactly as `python3 tools/<tool>.py [arguments]` would
  ledger <layer>                                        list the layer's tools (present, integrate and check: their pipelines below;
                                                        ledger tools lists every layer's tools)
  ledger integrate <report.json> [--short LABEL] [--archive WIP] [--run LABEL] [--no-archive] [--report-check] [--dry]
                   [--no-present] [--with-graph]        the intake hand-back (wip/narratives-1009/RESUME.md) in order, stopping at the
                                                        first failing step with the step named, ending with ledger present
  ledger present [--only a,b] [--skip a,b] [--with-graph] [--log DIR] [--list]
                                                        every generated page after a hand-back, in order (tools/build_reports.py:
                                                        index, timeline, answers, candour charts and page, topic corroboration, first utterance,
                                                        divergences, viewer, status), each step's output path and exit reported
  ledger present status                                 the status page alone (tools/build_status.py -> research/status.md)
  ledger check [--out FILE] [--notes GLOB]              build_db, baseline --check, note_skeleton --check and note_fill --check over
                                                        every note; counts printed, the per-note results written to --out
  ledger tools                                          every tool with its layer (and the tools not mapped, if any)
  ledger file headings|section|lines|copy ...           the portable file operations of wip/platform-phase4/briefs/operations.md
  ledger run --out <file> -- <layer> <tool> [args]      run a tool and save what it prints to <file> (UTF-8, LF)
  ledger db sql "<select ...>" [--db <path>]            query the derived database read-only
  ledger quote --wip wip/<task> u NNN:L[-M] ... [--words "<first four> ... <last four>"] [--quotations NNN[-MMM]]
                                                        a staged intake's source words by pointer (the compact findings form)
  ledger quote --wip wip/<task> --find "<a few of the words>" [--find ...]
                                                        the same words located by word: the sentence or caption line that holds
                                                        them, with its pointer; every hit; the near miss when there is none
  ledger sample draw <note> --wip wip/<task> [--n 20] [--seed S] [--round N] [--out FILE] [--json]
                                                        the sample reading's twenty claims rows by seed, spread over the units,
                                                        each beside its span (tools/ledger/sample.py)
  ledger sample tally --wip wip/<task> [--round N] [--threshold T] [--on-threshold check|flag] [--reply JSON] [--json]
                                                        the reader's TSV counted into report.json's sample_reading key

Layers: acquire, prepare, extract, build, analyse, narrate, present, measure, integrate, check. A tool is named by its short name
in the layer (`ledger build db`) or by its file name (`ledger build build_db`). The tools are imported and run as their own entry
point (runpy, run_name "__main__": a tool with a main() has it called by its own `if __name__ == "__main__"` block), from the project
root, with sys.argv set as the shell would set it; nothing is re-implemented here. `python3 tools/<tool>.py` keeps working unchanged.
"""
import contextlib, datetime, glob, io, json, os, re, runpy, sys, time

TOOLS_DIR = None   # set by _setup()
ROOT = None
_CWD = None        # the folder the command was started in

# layer -> [(short name, tool file stem, one line)]
LAYERS = {
    "acquire": [
        ("video", "fetch_video", "fetch a recording's transcript and description, rate-limited"),
        ("transcript", "fetch_transcript", "fetch a transcript"),
        ("description", "fetch_description", "append the channel description to a held transcript"),
        ("playlist", "list_playlist", "list a playlist's video ids"),
        ("kjv", "fetch_kjv", "canon: the King James text"),
        ("tanakh", "fetch_tanakh", "canon: the Westminster Leningrad Codex"),
        ("samaritan", "fetch_samaritan", "canon: the Samaritan Pentateuch"),
        ("isaiah-scroll", "fetch_isaiah_scroll", "canon: the Great Isaiah Scroll"),
        ("stargate-mirror", "stargate_mirror", "bulk archive: mirror a released collection"),
        ("stargate-bulk", "stargate_bulk", "bulk archive: bulk text extraction"),
        ("stargate-index", "stargate_index", "bulk archive: the index database"),
        ("reddit-rss", "reddit_rss_patch", "patch held Reddit captures from RSS"),
        ("pastes", "extract_pastes", "extract pasted texts"),
        ("pasted-transcript", "parse_pasted_transcript", "a pasted transcript to the held form"),
    ],
    "prepare": [
        ("chunk", "chunk_source", "cut a source into units with a manifest"),
        ("context", "context_pack", "the context pack for an intake"),
        ("timeline-prepass", "timeline_prepass", "the date-keyed candidate list"),
        ("skeleton", "note_skeleton", "the house form of a note (and --check)"),
        ("scroll-control", "scroll_control", "canon witness comparison"),
        ("stargate-filter", "stargate_viewer_filter", "route the archive by named viewer"),
        ("verbatim-trim", "verbatim_trim", "trim long verbatim spans to pointers"),
    ],
    "extract": [
        ("fill", "note_fill", "generate the mechanical parts of a note (and --check)"),
        ("timeline-insert", "timeline_insert", "insert dated rows with permanent decimal IDs"),
        ("timeline-relocate", "timeline_relocate", "retire or relocate timeline rows, updating citations"),
        ("gate", "intake_gate", "the staged intake's script gates"),
        ("verbatim", "verbatim_check", "spans reproducing a held source"),
        ("report-check", "report_check", "an agent's report against its form"),
        ("agent-report", "extract_agent_report", "an agent's report from its transcript"),
        ("claimed-documents", "claimed_documents", "rows claiming an unnamed document"),
        ("people-dates", "people_dates", "birth and death dates for the people index"),
    ],
    "build": [
        ("db", "build_db", "derive notes.db from the notes"),
        ("timeline", "build_timeline", "the master timeline"),
        ("index", "build_index", "README.md from the notes"),
        ("graph", "build_graph_data", "the map's graph data"),
        ("forthrightness-page", "build_forthrightness_page", "the candour charts page"),
        ("baseline", "baseline", "the platform baseline (and --check)"),
    ],
    "analyse": [
        ("rows", "rows_search", "full-text search over the held rows"),
        ("onboard", "onboard_check", "a new note's cross-check candidates"),
        ("match-leads", "match_leads", "leads matching a note"),
        ("relations", "relations", "query the relations register"),
        ("divergences", "divergences", "the divergence patterns page"),
        ("echoes", "echoes", "same wording across independent-looking mouths"),
        ("lens", "greer_lens", "the disinformation lens"),
        ("evidence", "evidence_pack", "an investigation's evidence pack"),
        ("hebrew", "hebrew", "canon reading methods (pack plugin)"),
        ("balance", "source_balance", "source kinds and the intake quota"),
        ("first-utterance", "first_utterance", "the first-utterance register"),
        ("reopen", "reopen_check", "answered rows a contradiction reopens"),
        ("answers", "answers_rollup", "the answered-questions roll-up"),
        ("xc-unaudited", "xc_unaudited", "cross-checks citing corrected claims"),
    ],
    "narrate": [
        ("narratives", "narratives", "parse, score and compare narrative pages"),
        ("pack", "narrative_pack", "the narrative pack"),
        ("digest", "narrative_digest", "a seed's digest"),
        ("apply", "narrative_apply", "apply a narrative page's returned leads and relations"),
        ("snapshot", "narrative_snapshot", "snapshot narrative pages"),
        ("adoptions", "adoption_check", "the adoption check"),
        ("unused", "narrative_unused", "held rows bearing on a node that the page never cites (the unused-rows check)"),
        ("viewer", "build_narrative_viewer", "the narrative viewer"),
    ],
    "present": [
        ("openness-map", "draw_openness_map", "the openness map (on hold)"),
        ("forthrightness-chart", "draw_forthrightness_chart", "per-interview candour charts"),
        ("topic-corroboration", "draw_topic_corroboration", "the topic corroboration chart"),
        ("matrix-heatmap", "draw_matrix_heatmap", "matrix heatmap (pack)"),
        ("map", "map_server", "serve the map locally"),
        ("owner-store", "owner_store", "the owner's map notes and investigations"),
        ("status", "build_status", "the status page (research/status.md), after every hand-back"),
        ("reports", "build_reports", "every generated page in order (also: ledger present with no tool)"),
    ],
    "measure": [
        ("usage", "agent_usage", "agent token usage from transcripts"),
        ("health", "workflow_health", "a workflow run's health"),
    ],
    "integrate": [
        ("report", "integrate_report", "integrate an intake report"),
        ("book-report", "integrate_book_report", "integrate a book intake report"),
        ("post-intake", "post_intake", "post-intake steps"),
        ("leads", "add_leads", "append leads to the register"),
        ("merge-answers", "merge_answers", "append answers left unchanged"),
        ("answer-guard", "answer_guard", "the answer target check"),
        ("archive", "wip_archive", "keep a wip folder's artefacts"),
        ("blocked", "blocked_passages", "the blocked-passages queue"),
    ],
    "check": [
        ("packload", "packload", "load and show the pack"),
        ("bundle", "build_bundle", "the release bundle; --doc <core doc> --out <file> writes one document in its core form (the private project)"),
    ],
}
LIBRARIES = {"packload"}   # importable helpers that also answer on the command line


def _setup():
    global TOOLS_DIR, ROOT
    if ROOT: return
    from ledger import paths
    ROOT = paths.root()
    # the project's own tools/ when it has one, else the tools this package sits in (a second project served by these tools: the
    # pilot, a round-trip copy, a recipient's folder; 2026-10-22)
    own, beside = os.path.join(ROOT, "tools"), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TOOLS_DIR = own if os.path.isdir(own) else beside
    if not os.path.isfile(os.path.join(TOOLS_DIR, "build_db.py")): sys.exit(f"ledger: no tools/ folder under the project root {ROOT} or beside the package (set LEDGER_ROOT)")
    if sys.path[0] != TOOLS_DIR: sys.path.insert(0, TOOLS_DIR)
    os.chdir(ROOT)


def find_tool(layer, name):
    for short, stem, _ in LAYERS.get(layer, []):
        if name in (short, stem, stem + ".py"): return stem
    return None


def run_tool(stem, args, capture=False):
    """Run tools/<stem>.py as its own entry point with sys.argv = [tools/<stem>.py, *args]; returns (exit code, captured output or
    None). A SystemExit's code is the exit code (None and 0 are success; a string is printed and counts as 1); an exception is
    printed with its traceback and counts as 1. The working directory and sys.path are restored afterwards."""
    _setup()
    path = os.path.join(TOOLS_DIR, stem + ".py")
    if not os.path.isfile(path): return 127, f"ledger: no tool tools/{stem}.py\n"
    old_argv, old_cwd, old_path = sys.argv, os.getcwd(), list(sys.path)
    sys.argv = [os.path.join("tools", stem + ".py")] + list(args)
    buf = io.StringIO() if capture else None
    code = 0
    try:
        with (contextlib.redirect_stdout(buf) if capture else contextlib.nullcontext()), (contextlib.redirect_stderr(buf) if capture else contextlib.nullcontext()):
            try:
                runpy.run_path(path, run_name="__main__")
            except SystemExit as e:
                if e.code is None: code = 0
                elif isinstance(e.code, int): code = e.code
                else: print(e.code, file=sys.stderr); code = 1
            except Exception:
                import traceback; traceback.print_exc(); code = 1
    finally:
        sys.stdout.flush(); sys.stderr.flush()
        sys.argv = old_argv; os.chdir(old_cwd); sys.path[:] = old_path
    return code, (buf.getvalue() if capture else None)


# ============================================================================================================ integrate
# The actor table's second column, by the forms in use: the first pack's register, the core register setup stage 4 generates, and
# the row shape a pack's actor_register slot gives the writers (the pilot pack; 2026-10-23, 7a turn 5's owed item)
ACTOR_COLUMNS = ("actor or kind", "actor as named")   # and the pack's own ([names] "actors.header_column"; the first pack keeps its earlier one)
CORE_ACTOR_HEADER = ["#", "Actor or kind (teller's name)", "Kind", "Teller and note row", "Firsthand / relayed (chain)", "Goals or role",
                     "Polity (member / outside / opposed / unknown; by whose telling)", "When", "Confidence"]


def _actor_columns():
    try:
        import packload
        extra = packload.name("actors.header_column")
    except Exception:
        extra = ""
    return ACTOR_COLUMNS + ((extra.lower(),) if extra else ())


def _is_actor_header(h):
    return len(h) > 1 and h[1].lower().startswith(_actor_columns())


def _actor_header(lines):
    from ledger import notes
    for t in reversed(notes.tables(lines, 0, len(lines))):
        if _is_actor_header(t.header): return t.header
    return None


def _start_actor_register(register, rep):
    """A new project's actor register, started at its first actor row: the report's own `actor_rows_header` when it is an actor table
    header (the row shape the pack's actor_register slot gave the writer), else the core header setup stage 4 writes."""
    from ledger import notes
    h = rep.get("actor_rows_header")
    cols = notes.split_row(h) if isinstance(h, str) and h.strip().startswith("|") else None
    if not (cols and _is_actor_header(cols)): cols = CORE_ACTOR_HEADER
    os.makedirs(os.path.dirname(register) or ".", exist_ok=True)
    notes.write_text(register, "# Actor and polity register\n\nStarted by `ledger integrate` at the project's first actor row, in the row shape "
                     "the intake reports carry.\n\n## Actors and polities\n\n| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
    print(f"actors: started {register} ({len(cols)} columns)")


_ACTOR_SYNONYMS = {"teller": "tellerandnoterow", "tellerrow": "tellerandnoterow",
                     "cluster": "matchescluster", "bcode": "matchescluster", "firsthand": "firsthandrelayed", "relayed": "firsthandrelayed"}


def _norm(s):
    import re
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def actor_cells(item, header):
    """One actor_rows item (the pack's [actors] rows_key) as the register's cells after `#`, in the register's column order. The item shapes the intake reports
    return: a table-row string (`| new | ... |`), a dict holding such a string under `row`, or a dict keyed by the register's column
    names (long or short: `Polity (federation member ...)`, `polity`; `firsthand_relayed`; `cluster`). ValueError names a key that
    fits no column or a row of the wrong width."""
    from ledger import notes
    cols = header[1:]
    if isinstance(item, dict) and isinstance(item.get("row"), str) and item["row"].strip().startswith("|"): item = item["row"]
    if isinstance(item, str):
        if not item.strip().startswith("|"): raise ValueError(f"not a table row: {item[:80]!r}")
        cs = notes.split_row(item)
        if cs and not (cs[0].isdigit() or cs[0].strip("()").lower() in ("new", "next", "")): raise ValueError(f"row with {len(cs)} cells does not start with `new` or a number: {item[:80]!r}")
        cs = cs[1:]
        if len(cs) != len(cols): raise ValueError(f"row has {len(cs)} cells after the number; the register has {len(cols)} columns: {item[:80]!r}")
        return cs
    if not isinstance(item, dict): raise ValueError(f"neither a row nor a dict: {item!r:.80}")
    ncols = [_norm(c) for c in cols]; out = [""] * len(cols)
    for k, v in item.items():
        nk = _norm(k)
        if nk == "": continue                      # the `#` key
        syn = {**_ACTOR_SYNONYMS, **_pack_synonyms()}.get(nk)
        if syn and any(c.startswith(syn) or syn.startswith(c) for c in ncols): nk = syn   # a synonym only where its column is in this register
        hit = [i for i, c in enumerate(ncols) if c.startswith(nk) or nk.startswith(c)]
        if len(hit) != 1: raise ValueError(f"key {k!r} fits {'no' if not hit else 'more than one'} column of the register")
        out[hit[0]] = "" if v is None else str(v)
    return out


def _pack_synonyms():
    try:
        import packload
        return {_norm(k): _norm(v) for k, v in packload.name_synonyms().items()}
    except Exception:
        return {}


def actor_register():
    """(register path, report key) of the pack's actor register: pack.toml [actors] register and rows_key (core defaults
    research/actor-register.md, actor_rows)."""
    _setup()
    try:
        import packload
        a = packload.pack().get("actors", {})
    except Exception:
        a = {}
    return a.get("register") or "research/actor-register.md", a.get("rows_key") or "actor_rows"


def actor_append(report_path, register=None, dry=False):
    """Append a report's actor rows (the pack's [actors] rows_key) to the pack's actor register ([actors] register; its section 8,
    rule 7) under a heading of their own, numbering on from the register's highest section-3 row; a row whose cells (after the
    number) already stand in the register is skipped, so a re-run adds nothing. Every item is placed before anything is written: an
    item that fits no column stops the step with the item named and nothing appended. Returns (added, skipped)."""
    from ledger import notes
    reg, key = actor_register()
    register = register or reg
    rep = json.load(open(report_path, encoding="utf-8"))
    items = rep.get(key) or []
    if not items: return 0, 0
    if not os.path.exists(register) and not dry: _start_actor_register(register, rep)
    text = notes.read_text(register); lines = text.split("\n")
    hdr = _actor_header(lines)
    if not hdr: raise SystemExit(f"actors: no table headed " + " or ".join(f"`| # | {c} ...`" for c in _actor_columns()) + f" (case aside) in {register}")
    nums = []
    for t in notes.tables(lines, 0, len(lines)):
        if _is_actor_header(t.header):
            nums += [int(c[0]) for c in t.row_cells if c and c[0].isdigit()]
    n = max(nums) if nums else 0
    placed = []
    for k, it in enumerate(items, 1):
        try: placed.append(actor_cells(it, hdr))
        except ValueError as e: raise SystemExit(f"actors: item {k} of {len(items)} cannot be placed in the register's columns ({e}); nothing appended, add the rows by hand")
    new, skipped = [], 0
    for cs in placed:
        cs = [c.replace("|", "/").replace("\n", " ").strip() for c in cs]
        body = " | ".join(cs)
        if body[:90] in text: skipped += 1; continue
        n += 1; new.append(f"| {n} | {body} |")
    if not new or dry: return len(new), skipped
    stem = _report_stem(rep, report_path)
    # the polity line: a pack naming one polity (pack.toml [actors] polity_name, polity_key) keeps its statements by hand; a pack naming
    # none has them appended by polity_append (2026-10-23; the wording was the first pack's, fixed, before then)
    a = _actors_section(); pname, pkey = a.get("polity_name") or "", a.get("polity_key") or "polity_statements"
    fed = rep.get(pkey)
    if pname:
        label = pname.split()[-1]
        fed_line = f"{label} statements returned by this intake: none." if (not fed or fed == "none") else f"{label} statements returned by this intake: see the report's {pkey} (section 4 rows are added by hand, rule 7)."
    else:
        fed_line = f"Polity statements returned by this intake: {len(fed) if isinstance(fed, list) else 'none'} (appended by `ledger integrate` to the register's polity statement tables)."
    today = datetime.date.today().isoformat()
    block = ["", f"### Rows from the intake of {stem}, appended {today}", "",
             f"Appended by `ledger integrate` from the intake's {actor_register()[1]} (rule 7 of section 8). Numbering continues the register's.", "",
             notes.join_row(hdr), "|" + "---|" * len(hdr)] + new + ["", fed_line, ""]
    notes.write_text(register, text.rstrip("\n") + "\n" + "\n".join(block))
    return len(new), skipped


def _actors_section():
    _setup()
    try:
        import packload
        return packload.pack().get("actors", {}) or {}
    except Exception:
        return {}


def _report_stem(rep, report_path):
    return os.path.basename(rep.get("file", "") or report_path)[:-3] if (rep.get("file", "") or "").endswith(".md") else os.path.basename(os.path.dirname(report_path))


STATEMENT_HEADER = ["#", "Teller (note, row, time)", "Body (alliance, bloc, coalition, network, faction)", "Inside / members", "Outside", "Opposed",
                    "The referent's standing", "Time (when said; period it refers to)", "Quote (short)", "Chain"]
# a report item's keys, by the forms the intake writers return (the slot gives no fixed shape): column -> the keys that fill it
_STATEMENT_KEYS = [("teller", ("teller", "by", "who", "speaker")), ("body", ("body", "polity")), ("inside", ("inside", "members")),
                   ("outside", ("outside",)), ("opposed", ("opposed",)), ("standing", ("standing", "statement", "posture", "text", "position")),
                   ("time", ("time", "when", "date", "period")), ("quote", ("quote",)), ("chain", ("chain",))]


def statement_cells(item, stem):
    """One polity statement as the register's cells after `#` (STATEMENT_HEADER). A table row of that width is taken as it is; a dict is
    mapped by _STATEMENT_KEYS (a sentence as `<polity>: <statement>`), its note row (note_row, row, rows) joined to the teller with the note's stem, and any key that fits no
    column kept in the standing cell as `key: value`, so nothing the writer returned is dropped. ValueError for anything else."""
    from ledger import notes
    if isinstance(item, str) and item.strip().startswith("|"):
        cs = notes.split_row(item)
        if len(cs) - 1 != len(STATEMENT_HEADER) - 1: raise ValueError(f"not a statement row of {len(STATEMENT_HEADER) - 1} cells: {item[:80]!r}")
        return cs[1:]
    if isinstance(item, str):   # a sentence: `<polity>: <statement>` when it opens with a polity id (P2 ...), else the statement alone
        m = re.match(r"^\s*(P\d+\b[^:]{0,80}):\s*(.+)$", item, re.S)
        item = {"body": m.group(1), "standing": m.group(2)} if m else {"standing": item}
    if not isinstance(item, dict): raise ValueError(f"neither a row nor a dict: {item!r:.80}")
    out = {c: [] for c, _ in _STATEMENT_KEYS}; extra = []; row = None
    for k, v in item.items():
        nk = re.sub(r"[^a-z]", "", str(k).lower())
        if nk in ("noterow", "row", "rows", "noterows"): row = v; continue
        col = next((c for c, keys in _STATEMENT_KEYS if any(nk == re.sub(r"[^a-z]", "", x) for x in keys)), None)
        (out[col] if col else extra).append(str(v) if col else f"{k}: {v}")
    teller = "; ".join(out["teller"]) or "not stated"
    out["teller"] = [f"{teller} ({stem}" + (f", row {row})" if row not in (None, "") else ")")]
    if extra: out["standing"].append("[" + "; ".join(extra) + "]")
    return ["; ".join(out[c]).replace("|", "/").replace("\n", " ").strip() for c, _ in _STATEMENT_KEYS]


def polity_append(report_path, register=None):
    """Append a report's polity statements (the pack's [actors] polity_key) to the actor register under a heading of their own, in
    STATEMENT_HEADER's columns, numbering on from the register's statement tables (a header with Inside); a statement already held is
    skipped. Packs that name one polity (polity_name) keep theirs by hand and are not touched. Returns (added, skipped)."""
    from ledger import notes
    a = _actors_section()
    if a.get("polity_name"): return 0, 0
    reg, _ = actor_register(); register = register or reg
    rep = json.load(open(report_path, encoding="utf-8"))
    items = rep.get(a.get("polity_key") or "polity_statements") or []
    if not isinstance(items, list) or not items or not os.path.exists(register): return 0, 0
    stem = _report_stem(rep, report_path)
    text = notes.read_text(register); lines = text.split("\n")
    nums = [int(c[0]) for t in notes.tables(lines, 0, len(lines)) if any(h.lower().startswith("inside") for h in t.header)
            for c in t.row_cells if c and c[0].isdigit()]
    n = max(nums) if nums else 0; new, skipped = [], 0
    placed = []
    for k, it in enumerate(items, 1):
        try: placed.append(statement_cells(it, stem))
        except ValueError as e: raise SystemExit(f"polity statements: item {k} of {len(items)} cannot be placed ({e}); nothing appended, add it by hand")
    for cs in placed:
        body = " | ".join(cs)
        if body[:90] in text: skipped += 1; continue
        n += 1; new.append(f"| {n} | {body} |")
    if not new: return 0, skipped
    block = ["", f"### Polity statements from the intake of {stem}, appended {datetime.date.today().isoformat()}", "",
             "Appended by `ledger integrate` from the intake's polity statements, by whose telling; keys the table has no column for are kept in the standing cell in brackets.", "",
             notes.join_row(STATEMENT_HEADER), "|" + "---|" * len(STATEMENT_HEADER)] + new + [""]
    notes.write_text(register, text.rstrip("\n") + "\n" + "\n".join(block))
    return len(new), skipped


def speaker_ledgers(report_path):
    """The report's values for the pack's ledgered speakers ([[speakers.ledgered]] report_keys) appended to each speaker's ledger page
    (tools/ledger/speakers.py; pilot defect 7). Returns [(page, key, what was done)]."""
    _setup()
    import packload
    from ledger import speakers
    rep = json.load(open(report_path, encoding="utf-8"))
    pi = packload.tool_data("post_intake")
    anchors = {pi["ledger_page"]: pi["ledger_anchor"]} if pi.get("ledger_page") else {}
    return speakers.append(rep, _report_stem(rep, report_path), packload.pack().get("speakers", {}).get("ledgered", []), ROOT, anchors)


def integrate(argv):
    """ledger integrate <report.json> [--short LABEL] [--archive WIP] [--run LABEL] [--no-archive] [--report-check] [--dry] [--no-present] [--with-graph]"""
    _setup()
    a = list(argv)
    if not a or a[0] in ("-h", "--help"): print(integrate.__doc__); print(INTEGRATE_DOC); return 0 if a else 2
    def opt(flag, default=None):
        if flag in a:
            i = a.index(flag); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    def flag(f):
        if f in a: a.remove(f); return True
        return False
    short = opt("--short"); archive = opt("--archive"); run_label = opt("--run")
    no_archive = flag("--no-archive"); report_check = flag("--report-check"); dry = flag("--dry")
    no_present = flag("--no-present"); with_graph = flag("--with-graph")
    if len(a) != 1: print("ledger integrate: one report.json expected; got " + " ".join(a), file=sys.stderr); return 2
    report = a[0]
    if not os.path.isfile(report): print(f"ledger integrate: {report} not found", file=sys.stderr); return 2
    rep = json.load(open(report, encoding="utf-8"))
    if archive is None and not no_archive:
        d = os.path.dirname(os.path.abspath(report))
        if os.path.relpath(d, ROOT).replace(os.sep, "/").startswith("wip/"): archive = os.path.relpath(d, ROOT)
    steps = []
    if report_check: steps.append(("report_check", "report_check", [report, "--form", "integrate"]))   # the lists this command reads (without --form the check took the narrative form)
    steps += [("integrate_report", "integrate_report", [report] + (["--short", short] if short else [])),
              ("build_db", "build_db", ["--report"]),
              ("build_timeline", "build_timeline", []),
              ("first_utterance --apply", "first_utterance", ["--apply", report]),
              ("first_utterance --narratives", "first_utterance", ["--narratives"]),
              ("source_balance --write-kinds", "source_balance", ["--write-kinds"]),
              ("divergences", "divergences", []),
              ("actors", None, None),
              ("speaker ledgers", None, None),
              ("objects", None, None),
              ("sample reading", None, None)]
    if archive and not no_archive: steps.append(("wip_archive", "wip_archive", [archive] + (["--run", run_label] if run_label else [])))
    # last, ledger present (2026-10-22, phase 5 handoff 3): every generated page, the status page included, regenerated after the
    # hand-back; the three pages steps above have just written (timeline, first utterance --narratives, divergences) are skipped
    if not no_present: steps.append(("present", "build_reports", ["--skip", PRESENT_DONE] + (["--with-graph"] if with_graph else [])))
    print(f"ledger integrate {report}: {len(steps)} steps" + (" (dry run: the steps are listed, nothing runs)" if dry else ""))
    for k, (label, stem, args) in enumerate(steps, 1):
        print(f"== step {k}/{len(steps)}: {label}" + (f": python3 tools/{stem}.py {' '.join(args)}" if stem else ""), flush=True)
        if dry: continue
        t0 = time.time()
        if label == "actors":
            try:
                added, skipped = actor_append(report)
                reg, key = actor_register()
                print(f"actors: {added} row(s) appended to {reg}, {skipped} already held" if (added or skipped) else f"actors: the report carries no {key}")
                padded, pskipped = polity_append(report)
                if padded or pskipped: print(f"polity statements: {padded} appended to {reg}, {pskipped} already held")
                code = 0
            except SystemExit as e: print(e); code = 1
            except Exception:
                import traceback; traceback.print_exc(); code = 1
        elif label == "speaker ledgers":
            try:
                done = speaker_ledgers(report)
                print("speaker ledgers: " + ("; ".join(f"{pg} {k}: {w}" for pg, k, w in done) if done else "the pack names no ledgered speaker the report carries"))
                code = 0
            except Exception:
                import traceback; traceback.print_exc(); code = 1
        elif label == "objects":
            nn = len(rep.get("register_new") or []); nu = len(rep.get("register_updates") or [])
            print(f"objects: register_new {nn}, register_updates {nu}: applied by integrate_report in step 1 (rows keyed on their text; updates it could not match were printed there as MANUAL)" if (nn or nu) else "objects: the report carries no object register rows")
            code = 0
        elif label == "sample reading":
            try:
                from ledger import sample as SM
                print(SM.record_cost_log(report, run=run_label)); code = 0
            except Exception:
                import traceback; traceback.print_exc(); code = 1
        else:
            code, _ = run_tool(stem, args)
        if code != 0:
            print(f"ledger integrate: STOPPED at step {k} ({label}): exit {code}; the steps after it did not run", file=sys.stderr)
            return code if isinstance(code, int) and code else 1
        print(f"   step {k} ok ({time.time() - t0:.1f}s)", flush=True)
    if archive and not no_archive and not dry: print(f"ledger integrate: done; {archive} is archived and left in place (delete it by hand once checked)")
    elif not dry: print("ledger integrate: done" + ("" if archive else "; no wip folder archived (the report is not under wip/; give --archive)"))
    return 0


PRESENT_DONE = "timeline,first-utterance,divergences"   # build_reports steps the integrate steps build_timeline, first_utterance --narratives and divergences cover

INTEGRATE_DOC = """Steps, in the order of the hand-back (wip/narratives-1009/RESUME.md, INTAKE hand-back):
  [report_check (with --report-check)], integrate_report <report> [--short], build_db --report, build_timeline, first_utterance --apply <report>,
  first_utterance --narratives, source_balance --write-kinds, divergences, actors (the report's actor rows, the pack's [actors]
  rows_key, appended to the pack's actor register), speaker ledgers (the report's keys for the pack's
  [[speakers.ledgered]], appended to each speaker's page: tools/ledger/speakers.py), objects (integrate_report's register_new and register_updates for the object
  register, reported), sample reading (the report's sample_reading tally written as the task's line in the cost log, pack
  [display.status] cost_log: Agent `**sample reading, <task>**`, Phase `Sample`, the tally in Result; tools/ledger/sample.py),
  wip_archive <wip folder> [--run],
  present (ledger present: tools/build_reports.py --skip timeline,first-utterance,divergences, those three pages having been
  written by the steps above; the status page is regenerated last; --with-graph also rebuilds the map's data files).
The wip folder defaults to the report's folder when it is under wip/; --no-archive skips the archive step; --no-present skips the
present step. Nothing is deleted."""


# ============================================================================================================ check
def check(argv):
    """ledger check [--out FILE] [--notes GLOB] [--no-build]: build_db, baseline --check, note_skeleton --check and note_fill --check
    over every note (videos/*.md and books/*.md); prints counts and writes the per-note results to --out (default
    wip/ledger-check/check-<date>.md)."""
    _setup()
    a = list(argv)
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join("wip", "ledger-check", f"check-{datetime.date.today().isoformat()}.md")
    pat = a[a.index("--notes") + 1] if "--notes" in a else None
    notes_list = sorted(glob.glob("videos/*.md") + glob.glob("books/*.md"))
    if pat:
        import fnmatch; notes_list = [n for n in notes_list if fnmatch.fnmatch(n, pat)]
    L = [f"# ledger check, {datetime.date.today().isoformat()}", ""]
    summary = []
    if "--no-build" not in a:
        code, txt = run_tool("build_db", [], capture=True)
        print(txt.rstrip()); summary.append(f"build_db: exit {code}: {txt.strip().splitlines()[0] if txt.strip() else ''}")
        L += ["## build_db", "", "```", txt.rstrip(), "```", ""]
        if code != 0: print("ledger check: build_db failed; the checks below read the previous notes.db", file=sys.stderr)
    code, txt = run_tool("baseline", ["--check"], capture=True)
    last = txt.strip().splitlines()[-1] if txt.strip() else ""
    print(f"baseline --check: exit {code}: {last}"); summary.append(f"baseline --check: exit {code}: {last}")
    L += ["## baseline --check", "", "```", txt.rstrip(), "```", ""]
    res = {}
    for tool, mk in (("note_skeleton", lambda n: ["--check", n]), ("note_fill", lambda n: ["--check", n])):
        ok = fail = 0; rows = []
        for n in notes_list:
            c, t = run_tool(tool, mk(n), capture=True)
            if c == 0: ok += 1
            else:
                fail += 1
                why = [x for x in t.splitlines() if x.startswith(("FAIL", "DIFF"))]
                rows.append(f"- {n}: exit {c}: " + (" / ".join(w[:200] for w in why[:4]) + (f" (+{len(why) - 4} more)" if len(why) > 4 else "") if why else t.strip().splitlines()[-1][:200] if t.strip() else ""))
        res[tool] = (ok, fail)
        line = f"{tool} --check: {len(notes_list)} notes: {ok} pass, {fail} fail"
        print(line); summary.append(line)
        L += [f"## {tool} --check ({ok} pass, {fail} fail)", ""] + (rows or ["none failed"]) + [""]
    L[2:2] = ["## Counts", ""] + [f"- {s}" for s in summary] + [""]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    from ledger import notes
    notes.write_text(out, "\n".join(L) + "\n")
    print(f"per-note results: {out}")
    return 0


# ============================================================================================================ acquire built-ins
def layout(argv):
    """ledger acquire layout [--write | --check | --resolve PATH ...]: the sources/ alias table (wip/platform-phase1/sources-layout.md).
    No option: show the table's rows that would be written and how many exist. --write: write sources/aliases.tsv (the table's only
    writer; nothing is moved). --check: every target exists, no target shared, no case-only collision. --resolve: the file each path
    names."""
    _setup()
    from ledger import paths
    if "--write" in argv:
        p, n = paths.write_alias_table(); print(f"wrote {os.path.relpath(p, ROOT)}: {n} rows (nothing moved or renamed)"); return 0
    if "--check" in argv:
        probs = paths.check_aliases(); al = paths.aliases()
        print(f"{len(al)} aliases ({sum(1 for a in al if a.endswith('/'))} folders, {sum(1 for a in al if not a.endswith('/'))} files); {len(probs)} problem(s)")
        for x in probs[:200]: print("  " + x)
        return 1 if probs else 0
    if "--resolve" in argv:
        for q in argv[argv.index("--resolve") + 1:]:
            r = paths.resolve(q, os.getcwd()); print(f"{q} -> {os.path.relpath(r, ROOT)}" + ("" if os.path.exists(r) else "  (does not exist)"))
        return 0
    rows = paths.build_alias_rows()
    for r in rows[:5] + ([("...", f"({len(rows) - 10} more)", "", "")] if len(rows) > 10 else []) + rows[-5:]: print("\t".join(r))
    print(f"{len(rows)} rows would be written to {paths.ALIAS_FILE}; it holds {len(paths.aliases())} now (ledger acquire layout --write)")
    return 0


def name_check(argv):
    """ledger acquire name PATH [...] [--youtube]: the portability rules a new hold's name must meet (sources-layout.md section 4):
    the problems new_hold() would refuse or fix, the warnings it only reports, and the compliant name it would write."""
    _setup()
    from ledger import paths
    kind = "youtube" if "--youtube" in argv else "file"; bad = 0
    for q in [a for a in argv if not a.startswith("--")]:
        r = paths.rel(q, os.getcwd()); probs = paths.name_problems(r, kind); warns = [] if kind == "youtube" else paths.name_warnings(r)
        fixed = "" if not probs or kind == "youtube" else f"; new_hold() would write {paths.hold_name(os.path.basename(r))}"
        print(f"{r}: " + ("ok" if not probs else "PROBLEMS: " + "; ".join(probs)) + (f" (warnings: {'; '.join(warns)})" if warns else "") + fixed + (" (exists: never renamed)" if os.path.exists(os.path.join(ROOT, r)) else ""))
        bad += bool(probs)
    return 1 if bad else 0


BUILTINS = {("acquire", "layout"): layout, ("acquire", "name"): name_check}

# The acquire adapters (phase 3; routed 2026-10-22, the phase 3 hand-over's open item 2): `ledger acquire <adapter> [its own
# arguments]` calls tools/ledger/acquire/<adapter>.py's main() from the project root, exactly as running the file would.
ADAPTERS = ("youtube", "web", "document", "bulk", "canon", "database", "transcribe")


def _adapter_cmd(name):
    def run(argv):
        import importlib
        _setup()
        m = importlib.import_module(f"ledger.acquire.{name}")
        try:
            r = m.main(list(argv)); return r if isinstance(r, int) else 0
        except SystemExit as e:
            if e.code is None or isinstance(e.code, int): return e.code or 0
            print(e.code, file=sys.stderr); return 1
    run.__doc__ = f"ledger acquire {name} ...: the {name} adapter (tools/ledger/acquire/{name}.py; --help lists its arguments)"
    return run


def batch_cmd(argv):
    """ledger acquire batch <list.toml> [fetch|hold|all] [--cache DIR] [--only id,id] [--list]: hold a list of sources (fetch to a cache through the rate gate, hold from the cache, verify, manifest; tools/ledger/batch.py)"""
    _setup()
    a = list(argv)
    if a and not a[0].startswith("-") and not os.path.isabs(a[0]):   # the list is named from the caller's folder, as a shell would
        cand = os.path.join(_CWD or ROOT, a[0])
        if os.path.isfile(cand): a[0] = cand
    from ledger import batch
    return batch.main(a)


for _n in ADAPTERS: BUILTINS[("acquire", _n)] = _adapter_cmd(_n)
BUILTINS[("acquire", "dedupe-holds")] = _adapter_cmd("dedupe_holds")   # the one-off dedupe of existing holds (pilot defect 19, 7b2)
BUILTINS[("acquire", "batch")] = batch_cmd


# ============================================================================================================ file, run, db
# The portable operations the brief templates use in place of shell idioms (wip/platform-phase4/briefs/operations.md; phase 4
# handoff 7). Every write is UTF-8 with LF; paths are relative to the working directory, as a shell's would be.
def _rel(p): return os.path.relpath(p) if not os.path.isabs(p) else p


def file_cmd(argv):
    """ledger file headings <path> [--all] | section <path> "<heading>" [--numbered] | lines <path> <a>-<b> [--out <dst>] |
    lines <path> --count | copy <src> <dst>"""
    from ledger import notes
    if not argv or argv[0] in ("-h", "--help"): print(file_cmd.__doc__); return 0 if argv else 2
    op, rest = argv[0], argv[1:]
    def need(n, usage):
        if len([a for a in rest if not a.startswith("--")]) < n: print(f"ledger file {op}: usage: {usage}", file=sys.stderr); return False
        return True
    if op == "headings":
        if not need(1, "ledger file headings <path> [--all]"): return 2
        lines = notes.read_lines(rest[0])
        for lv, t, i in notes.headings(lines):
            if "--all" in rest or lv in (2, 3): print(f"{i + 1}:{lines[i]}")
        return 0
    if op == "section":
        if not need(2, 'ledger file section <path> "<heading>" [--numbered]  (a heading prefix; "latest:<heading>" for the last match)'): return 2
        path, heading = [a for a in rest if not a.startswith("--")][:2]
        lines = notes.read_lines(path); hs = notes.headings(lines)
        latest = heading.startswith("latest:"); h = heading[7:] if latest else heading
        hits = [k for k, (lv, t, i) in enumerate(hs) if t.startswith(h.lstrip("# ").strip())]
        if not hits: print(f"ledger file section: no heading starting {h!r} in {path}", file=sys.stderr); return 1
        k = hits[-1] if latest else hits[0]; lv, t, i = hs[k]
        end = next((i2 for lv2, t2, i2 in hs[k + 1:] if lv2 <= lv), len(lines))
        for j in range(i, end): print(f"{j + 1}\t{lines[j]}" if "--numbered" in rest else lines[j])
        return 0
    if op == "lines":
        pos = [a for a in rest if not a.startswith("--")]
        if not pos: print("ledger file lines: usage: ledger file lines <path> <a>-<b> [--out <dst>] | <path> --count", file=sys.stderr); return 2
        lines = notes.read_lines(pos[0])
        if "--count" in rest: print(len(lines)); return 0
        out = rest[rest.index("--out") + 1] if "--out" in rest else None
        rng = [a for a in pos[1:] if a != out]
        if not rng or "-" not in rng[0]: print("ledger file lines: give a range a-b", file=sys.stderr); return 2
        a, b = (int(x) for x in rng[0].split("-", 1))
        sel = lines[a - 1:b]
        if out:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); notes.write_text(out, "\n".join(sel) + "\n")
            print(f"wrote {_rel(out)}: lines {a}-{min(b, len(lines))} of {pos[0]} ({len(sel)} lines)")
        else: print("\n".join(sel))
        return 0
    if op == "copy":
        if not need(2, "ledger file copy <src> <dst>"): return 2
        import shutil
        src, dst = [a for a in rest if not a.startswith("--")][:2]
        if os.path.isdir(dst): dst = os.path.join(dst, os.path.basename(src))
        other = _project_of(os.path.dirname(os.path.abspath(dst)))
        if other:
            src, dst = os.path.abspath(src), os.path.abspath(dst)   # before _setup moves to the project root
            _setup()
            if os.path.normcase(other) != os.path.normcase(os.path.abspath(ROOT)): return _copy_out(src, dst, other)
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True); shutil.copyfile(src, dst)
        print(f"copied {_rel(src)} -> {_rel(dst)} ({os.path.getsize(dst):,} bytes)")
        return 0
    print(f"ledger file: unknown operation {op!r} (headings, section, lines, copy)", file=sys.stderr); return 2


def _project_of(d):
    """The project folder (the nearest folder at or above d holding ledger.toml), or None."""
    d = os.path.abspath(d)
    while True:
        if os.path.isfile(os.path.join(d, "ledger.toml")): return d
        if os.path.dirname(d) == d: return None
        d = os.path.dirname(d)


def _copy_out(src, dst, other):
    """A copy into another project (7b2, 2026-10-23; the incident of 2026-10-23 put the first pack's wording into the pilot's schema by
    a byte copy): a document the bundle rewrites to its core form (tools/build_bundle.py DOC_REWRITES) is refused, with the one-document
    rewrite named; anything else is copied to a temporary file beside the destination and
    moved into place only when the check finds nothing. Exit 1 on a refusal or a hit (the destination untouched)."""
    import shutil, tempfile
    rel = os.path.relpath(os.path.abspath(src), ROOT).replace(os.sep, "/")
    bb = os.path.join(TOOLS_DIR, "build_bundle.py")
    if os.path.isfile(bb):
        if TOOLS_DIR not in sys.path: sys.path.insert(0, TOOLS_DIR)
        import build_bundle
        if rel in build_bundle.DOC_REWRITES:
            print(f"ledger file copy: {rel} is rewritten to its core form for any other project; use\n  python3 tools/build_bundle.py --doc {rel} --out {dst}", file=sys.stderr)
            return 1
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ledger-copy-", dir=os.path.dirname(os.path.abspath(dst))); os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst); tmp = None
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)
    print(f"copied {rel} -> {dst} ({os.path.getsize(dst):,} bytes; into the project {other})")
    return 0


FIND_BLOCKS = 10   # --find: hits printed with their whole sentence; every later hit is one line, its pointer and phrase


def quote_cmd(argv):
    """ledger quote --wip wip/<task> u NNN:L[-M] [u NNN:L[-M] ...] [--numbered] | --wip wip/<task> u NNN:L[-M] --words "<first four> ...
    <last four>" | --wip wip/<task> --quotations NNN[-MMM] | --wip wip/<task> --find "<a few of the words>" [--find "..." ...]: the
    source's words by pointer (the compact findings form, 2026-10-23) or by word (--find, 2026-10-25).
    A pointer prints `[u NNN:L-M] <the unit's header line>` and lines L to M of wip/<task>/units/NNN.txt verbatim (--numbered: with
    their `cat -n` numbers); several pointers print one block each. --words prints only the words from the first anchor to the last
    on those lines (two lines' slack either side). --quotations prints every `## Quotations` item of findings/NNN.md with the words
    its anchors locate. Exit 1 on a pointer outside its unit, a missing unit or anchors not found (every good pointer still prints).
    --find locates a phrase in every unit of the task by word keys (tools/ledger/quote.py: case, curly quotes, dashes and the
    punctuation between words do not count, so a phrase typed with punctuation finds an unpunctuated caption; `...` in the phrase
    cuts it into parts found in order): for each hit it prints `[u NNN:L-M] <the unit's header line>`, the whole sentence that
    holds the phrase verbatim (the whole caption line when the line has no sentence punctuation) on lines L to M, and a last line
    `phrase [u NNN:L-M]: <the phrase's exact words in the unit>`; several hits print `hit k of n` blocks. The writer pastes from
    those lines and cites the pointer. Nothing found: exit 1 with a message on stderr and, when one exists, the near miss (the
    window that holds most of the words, with the word that is changed, added or dropped). Several --find flags run in turn; the
    exit is 1 when any finds nothing."""
    from ledger import quote as Q
    a = list(argv)
    if not a or a[0] in ("-h", "--help"): print(quote_cmd.__doc__); return 0 if a else 2
    def take(flag):
        if flag not in a: return None
        i = a.index(flag)
        if i + 1 >= len(a): raise SystemExit(f"ledger quote: {flag} needs a value")
        v = a[i + 1]; del a[i:i + 2]; return v
    wip, anchors, qrange = take("--wip"), take("--words"), take("--quotations")
    finds = []
    while "--find" in a: finds.append(take("--find"))
    numbered = "--numbered" in a
    if numbered: a.remove("--numbered")
    if not wip: print("ledger quote: --wip wip/<task> is required", file=sys.stderr); return 2
    if not os.path.isabs(wip) and not os.path.isdir(wip):
        from ledger import paths
        if os.path.isdir(os.path.join(paths.root(), wip)): wip = os.path.join(paths.root(), wip)
    if not os.path.isdir(os.path.join(wip, "units")): print(f"ledger quote: no units/ under {wip}", file=sys.stderr); return 1
    bad = 0
    def ptr(n, x, y): return f"[u {n}:{x}{'-' + str(y) if y != x else ''}]"
    if finds:
        if a or anchors is not None or qrange: print("ledger quote: --find takes no pointer, --words or --quotations", file=sys.stderr); return 2
        for k, phrase in enumerate(finds):
            if k: print()
            try: hits, nm = Q.find(wip, phrase)
            except Q.PointerError as e: print(f"ledger quote: {e}", file=sys.stderr); bad += 1; continue
            if not hits:
                bad += 1
                print(f'ledger quote: --find "{phrase}": no unit under {wip}/units holds these words in this order (case, curly quotes, dashes and punctuation between words ignored)', file=sys.stderr)
                if nm:
                    (la, _), (lb, _) = nm["start"], nm["end"]
                    print(f"  nearest: {ptr(nm['unit'], la, lb)} {nm['header']}\n  {nm['text']}\n  difference: {Q.describe_ops(nm['ops']) or 'none'}", file=sys.stderr)
                else:
                    print("  no near miss: no window of the units holds most of these words; check the phrase against the unit with a pointer", file=sys.stderr)
                continue
            if len(hits) > 1: print(f'--find "{phrase}": {len(hits)} hits' + (f" (the first {FIND_BLOCKS} with their sentences, the rest by pointer and phrase; more words narrow it)" if len(hits) > FIND_BLOCKS else ""))
            for j, h in enumerate(hits, 1):
                (sa, _), (sb, _) = h["sentence"]; (pa, _), (pb, _) = h["start"], h["end"]
                if j > FIND_BLOCKS:
                    if j == FIND_BLOCKS + 1: print()
                    print(f"hit {j} of {len(hits)}: {ptr(h['unit'], sa, sb)} phrase {ptr(h['unit'], pa, pb)}: {h['phrase_text']}"); continue
                if len(hits) > 1: print(f"{'' if j == 1 else chr(10)}hit {j} of {len(hits)}")
                print(f"{ptr(h['unit'], sa, sb)} {h['header']}")
                print(h["sentence_text"])
                print(f"phrase {ptr(h['unit'], pa, pb)}: {h['phrase_text']}")
        return 1 if bad else 0
    if qrange:
        m = re.match(r"^(\d{1,3})(?:-(\d{1,3}))?$", qrange)
        if not m: print("ledger quote: --quotations NNN or NNN-MMM", file=sys.stderr); return 2
        for k in range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1):
            fp = os.path.join(wip, "findings", f"{k:03d}.md")
            if not os.path.isfile(fp): print(f"ledger quote: no findings file {fp}", file=sys.stderr); bad += 1; continue
            for line_no, p, anc, use, raw in Q.quotation_items(fp):
                if not p: print(f"findings/{k:03d}.md line {line_no}: a Quotations item without a pointer", file=sys.stderr); bad += 1; continue
                head = f"{ptr(*p)} findings/{k:03d}.md line {line_no}" + (f" | use: {use}" if use else "")
                if anc is None: print(head + " | (the older form: the words are in the item)\n" + raw + "\n"); continue
                try: _, text = Q.words(wip, *p, anc)
                except Q.PointerError as e: print(f"ledger quote: {e}", file=sys.stderr); bad += 1; continue
                print(head + "\n" + text + "\n")
        return 1 if bad else 0
    try: ptrs = Q.parse_pointers(a)
    except Q.PointerError as e: print(f"ledger quote: {e}", file=sys.stderr); return 1
    if not ptrs: print("ledger quote: give a pointer, u NNN:L or u NNN:L-M (or --quotations NNN)", file=sys.stderr); return 2
    if anchors is not None and len(ptrs) != 1: print("ledger quote: --words takes one pointer", file=sys.stderr); return 2
    for n, x, y in ptrs:
        try:
            if anchors is not None:
                header, text = Q.words(wip, n, x, y, anchors); print(f"{ptr(n, x, y)} {header}\n{text}")
            else:
                header, lines = Q.span(wip, n, x, y)
                print(f"{ptr(n, x, y)} {header}")
                for j, l in enumerate(lines, x): print(f"{j:6d}\t{l}" if numbered else l)
            if len(ptrs) > 1: print()
        except Q.PointerError as e:
            print(f"ledger quote: {e}", file=sys.stderr); bad += 1
    return 1 if bad else 0


def run_cmd(argv):
    """ledger run --out <file> -- <layer> <tool> <arguments>: run a tool and save what it prints (stdout) to <file>, UTF-8 with LF;
    its stderr still reaches the terminal; the exit code is the tool's."""
    a = list(argv)
    if "--out" not in a or "--" not in a: print(run_cmd.__doc__, file=sys.stderr); return 2
    out = a[a.index("--out") + 1]; cmd = a[a.index("--") + 1:]
    if len(cmd) < 2 or cmd[0] not in LAYERS: print("ledger run: give <layer> <tool> after --", file=sys.stderr); return 2
    stem = find_tool(cmd[0], cmd[1])
    if not stem: print(f"ledger run: no tool {cmd[1]!r} in {cmd[0]}", file=sys.stderr); return 2
    _setup()
    from ledger import notes
    buf = io.StringIO(); code = 0
    with contextlib.redirect_stdout(buf): code, _ = run_tool(stem, cmd[2:])
    out_abs = out if os.path.isabs(out) else os.path.join(_CWD or os.getcwd(), out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True); notes.write_text(out_abs, buf.getvalue())
    print(f"ledger run: {cmd[0]} {cmd[1]} exit {code}; {len(buf.getvalue().splitlines())} lines to {out}", file=sys.stderr)
    return code


def db_cmd(argv):
    """ledger db sql "<select ...>" [--db <path>] [--header]: query the derived database read-only (a write is refused); rows
    printed with ` | ` between the cells."""
    import sqlite3
    a = list(argv)
    if len(a) < 2 or a[0] != "sql": print(db_cmd.__doc__, file=sys.stderr); return 2
    _setup()
    db = a[a.index("--db") + 1] if "--db" in a else os.path.join(ROOT, "notes.db")
    q = a[1]
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try: cur = con.execute(q)
    except sqlite3.Error as e: print(f"ledger db sql: {e}", file=sys.stderr); return 1
    if "--header" in a and cur.description: print(" | ".join(d[0] for d in cur.description))
    n = 0
    for r in cur: print(" | ".join("" if x is None else str(x) for x in r)); n += 1
    print(f"{n} rows", file=sys.stderr)
    return 0


# ============================================================================================================ main
def list_tools():
    _setup()
    mapped = {stem for v in LAYERS.values() for _, stem, _ in v}
    for layer, items in LAYERS.items():
        print(f"{layer}:" + (" (and the pipeline: ledger integrate <report.json>)" if layer == "integrate" else " (and the pipeline: ledger check)" if layer == "check" else " (and the pipeline: ledger present)" if layer == "present" else ""))
        for short, stem, what in items:
            if _have(stem): print(f"  {short:22s} tools/{stem}.py  {what}")
    present = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(TOOLS_DIR, "*.py"))}
    left = sorted(present - mapped); gone = sorted(mapped - present)
    # a tool the project does not carry (a pack's tool, left out of an installed project's template) is not listed (7b2, 2026-10-23)
    print(f"{len(mapped & present)} tools mapped" + (f"; not mapped: {', '.join(left)}" if left else "") + (f"; {len(gone)} mapped tools not in this project, not listed" if gone else ""))
    return 0 if not left else 1


def _have(stem):
    if TOOLS_DIR is None: _setup()
    return os.path.isfile(os.path.join(TOOLS_DIR, stem + ".py"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"): print(__doc__); return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    global _CWD
    _CWD = os.getcwd()   # the caller's folder: `file` and `run --out` paths are relative to it, as a shell's would be
    if cmd == "tools": return list_tools()
    if cmd == "file": return file_cmd(rest)
    if cmd == "run": return run_cmd(rest)
    if cmd == "db": return db_cmd(rest)
    if cmd == "quote": return quote_cmd(rest)
    if cmd == "sample": _setup(); from ledger import sample; return sample.main(rest)
    if cmd == "integrate" and (not rest or rest[0].endswith(".json") or rest[0].startswith("-")): return integrate(rest)
    if cmd == "check" and (not rest or rest[0].startswith("-")): return check(rest)
    if cmd == "present" and (not rest or rest[0].startswith("-")): return run_tool("build_reports", rest)[0]   # phase 5: the report command
    if cmd in LAYERS:
        if not rest:
            print(f"ledger {cmd}:")
            for short, stem, what in LAYERS[cmd]:
                if _have(stem): print(f"  {short:22s} tools/{stem}.py  {what}")
            for (lay, nm), fn in BUILTINS.items():
                if lay == cmd: print(f"  {nm:22s} (built in)  {fn.__doc__.splitlines()[0]}")
            return 0
        if (cmd, rest[0]) in BUILTINS: return BUILTINS[(cmd, rest[0])](rest[1:])
        stem = find_tool(cmd, rest[0])
        if not stem:
            other = [l for l in LAYERS if find_tool(l, rest[0])]
            print(f"ledger {cmd}: no tool {rest[0]!r}" + (f" (it is in: {', '.join(other)})" if other else ""), file=sys.stderr); return 2
        code, _ = run_tool(stem, rest[1:])
        return code
    print(f"ledger: unknown command {cmd!r}; layers: {', '.join(LAYERS)}; also: tools", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
