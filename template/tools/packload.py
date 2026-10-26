#!/usr/bin/env python3
"""tools/packload.py: the one small loader through which core tools read the domain pack (phase 1 of tools/platform-plan.md,
2026-10-22). The core knows nothing of the subject; it asks this module. ledger.toml at the project root names the pack path
(default packs/default), the sources layout, the derived database path and the model policy; <pack>/pack.toml holds the data.

Usage as a module:
  import packload as P
  P.ledger()                      the project configuration (ledger.toml), with defaults when the file is absent
  P.pack()                        the pack manifest (pack.toml) as a dict
  P.pack_dir()                    the pack folder, absolute
  P.audited_subjects()            the subjects for which the candour audit is mandatory
  P.eras(kind)                    [(id, lo, hi), ...]; kind "pages" (era page ids), "synchrony" (synchrony page ids, narrative
                                  bounds) or "map" (map labels and bounds)
  P.catalysts_page(), P.threshold_date()
  P.source_kinds(), P.stem_patterns(), P.default_kind()
  P.topics()                      [(id, label), ...] in chart order; P.topic_labels() the dict; P.topic_ids() the set
  P.audit_captions()              {"channelled": ..., "human": ..., "footer": ...}
  P.lens_instance(id)             the lens instance file (dict) and its path
  P.graph_order()                 the subject display order for the map
  P.theses(), P.narrative_from()  the thesis seeds and the narrative pack's first year
  P.objects()                     the object register's criteria column, vocabulary line and words, findings watch name
  P.actors_findings_heading()     the staged intake's findings heading for actors
  P.threshold_label()             the first-utterance status of a telling held before the threshold catalyst
  P.skeleton_forms()              (forms, grid) for tools/note_skeleton.py
  P.id_patterns()                 [(label, regex)] document identifier forms for tools/context_pack.py
  P.display(section)              the presentation settings of one section (index, viewer, candour, openness, corroboration, map,
                                  typed_graph, status): DISPLAY_DEFAULTS laid under the pack's [display.<section>] (phase 5)
  P.short_labels(), P.subject_display(), P.era_segments(), P.actor_vocabulary(), P.pirs(), P.ledger_title()
  P.tool_data(tool)               a core tool's domain data (agencies, hosts, lexicons, page wording): TOOL_DEFAULTS with the pack's
                                  [tools.<tool>] keys laid over them, each key replaced whole (phase 7b)
  P.vocabulary_path(key)          the pack's [vocabulary] file for key (name_aliases, stock_phrases, ...), absolute, or None
  P.name(key)                     a core identifier as the pack names it: CORE_NAMES under the pack's [names] (the first pack keeps
                                  its earlier table, report-key and baseline names there; 7b2, 2026-10-23)
Command line: python3 tools/packload.py [--get <section>[.<key>]]   prints the whole manifest, or one value, as JSON.
Requires Python 3.11 or later (tomllib)."""
import os, sys, json, tomllib

TOOLS = os.path.dirname(os.path.abspath(__file__))
TOOLS_PROJECT = os.path.dirname(TOOLS)   # the project these tools sit in


def _project_root():
    """The project the tools serve (2026-10-22, so a second project, the pilot, a round-trip copy or a recipient's folder, uses the
    same tools): tools/ledger/paths.py's root(), which is $LEDGER_ROOT, else the nearest folder at or above the working directory
    holding ledger.toml, else the project these tools sit in; the same rule inline if the package cannot be imported."""
    try:
        if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
        from ledger import paths as _LP
        return _LP.root()
    except Exception:
        env = os.environ.get("LEDGER_ROOT")
        if env: return os.path.abspath(env)
        d = os.path.abspath(os.getcwd())
        while True:
            if os.path.isfile(os.path.join(d, "ledger.toml")): return d
            if os.path.dirname(d) == d: return TOOLS_PROJECT
            d = os.path.dirname(d)


ROOT = _project_root()
LEDGER_FILE = os.path.join(ROOT, "ledger.toml")
DEFAULT_LEDGER = {"ledger": {"name": "ledger"}, "pack": {"path": "packs/default"},
                  "sources": {"notes": ["videos", "books"], "transcripts": "transcripts", "held": "books/sources"},
                  "database": {"path": "notes.db"}, "models": {"agents": "opus", "effort": "high", "probes": "haiku"}}
_cache = {}

def _load(path):
    with open(path, "rb") as f: return tomllib.load(f)

def ledger():
    if "ledger" not in _cache:
        d = {k: dict(v) for k, v in DEFAULT_LEDGER.items()}
        if os.path.exists(LEDGER_FILE):
            for k, v in _load(LEDGER_FILE).items(): d.setdefault(k, {}).update(v) if isinstance(v, dict) else d.__setitem__(k, v)
        _cache["ledger"] = d
    return _cache["ledger"]

def pack_dir():
    """the pack folder: ledger.toml's [pack] path under the project, else under the project the tools sit in (packs kept with the tools)"""
    rel = ledger()["pack"]["path"]
    own = os.path.join(ROOT, rel)
    if os.path.isdir(own) or os.path.isabs(rel): return own
    shared = os.path.join(TOOLS_PROJECT, rel)
    return shared if os.path.isdir(shared) else own

def pack():
    if "pack" not in _cache: _cache["pack"] = _load(os.path.join(pack_dir(), "pack.toml"))
    return _cache["pack"]

def path(rel):
    """An absolute path for a project-relative path from the manifest."""
    return os.path.join(ROOT, rel)

def audited_subjects(): return list(pack()["subjects"]["audited"])
def all_subjects(): return list(pack()["subjects"]["all"])
def graph_order(): return list(pack()["subjects"].get("graph_order", pack()["subjects"]["all"]))

def eras(kind="pages"):
    """The era boundaries as (id, lo, hi). kind: pages (era page ids, open bounds), synchrony (synchrony ids; the first era
    starts at the narrative pack's first year, the last ends at synchrony_to), map (map labels and the map's bounds)."""
    E = pack()["eras"]; out = []
    for i, e in enumerate(E["era"]):
        lo, hi = e["from"], e["to"]
        if kind == "pages": out.append((e["id"], lo, hi))
        elif kind == "synchrony":
            if i == 0: lo = e.get("synchrony_from", E.get("narrative_from", lo))
            if i == len(E["era"]) - 1: hi = e.get("synchrony_to", hi)
            out.append((e.get("synchrony_id", e["id"]), lo, hi))
        elif kind == "map":
            out.append((e.get("map_label", e["id"]), e.get("map_from", lo), e.get("map_to", hi)))
        else: raise ValueError(kind)
    return out

def catalysts_page(): return path(pack()["catalysts"]["page"])
def threshold_date(): return pack()["catalysts"]["threshold_date"]

def source_kinds(): return list(pack()["source_kinds"]["kinds"])
def default_kind(): return pack()["source_kinds"].get("default", "host")
def stem_patterns(): return {k: list(v) for k, v in pack()["source_kinds"]["stem_patterns"].items()}

def topics(): return [(t["id"], t["label"]) for t in pack()["audit"]["topics"]]
def topic_labels(): return dict(topics())
def topic_ids(): return {t for t, _ in topics()}

def audit_captions():
    a = pack()["audit"]
    return {"channelled": a["channelled_caption"], "human": a["human_caption"], "footer": a.get("openness_footer", ""),
            "channelled_kind": a.get("channelled_kind", "channelled")}

def lens_instance(lens_id):
    for inst in pack()["lenses"]["instance"]:
        if inst["id"] == lens_id:
            p = path(inst["file"])
            with open(p, encoding="utf-8") as f: return json.load(f), p
    raise KeyError(f"no lens instance {lens_id} in {pack_dir()}/pack.toml")

def pack_tools(): return list(pack()["code"]["pack_tools"])

def narrative_from(): return int(pack()["eras"].get("narrative_from", 1933))

def objects():
    """The object register's form values: criteria column header, vocabulary line label and words, findings watch name (core
    defaults when the pack names no reference object)."""
    o = pack().get("objects", {})
    return {"criteria_column": o.get("criteria_column", "<reference object> criteria met"), "vocabulary_line": o.get("vocabulary_line", "Object vocabulary"),
            "vocabulary": list(o.get("vocabulary", [])), "watch_name": o.get("watch_name", "object watch"), "watch_heading": o.get("watch_heading", "## Object watch")}

def actors_findings_heading(): return pack().get("actors", {}).get("findings_heading", "Actors and polities")

def threshold_label():
    """The first-utterance status of a cluster held before the threshold catalyst: the pack's held_label, else pre-<year> held."""
    c = pack().get("catalysts", {})
    return c.get("held_label") or f"pre-{c['threshold_date'][:4]} held"

def skeleton_forms():
    """(forms, grid): tools/note_skeleton.py's note forms from the pack's skeleton-forms.toml, sections in file order, an empty
    supplier as None; ({}, []) when the pack names none."""
    rel = pack().get("skeleton", {}).get("forms")
    if not rel: return {}, []
    d = _load(path(rel))
    forms = {n: {"primary": f["primary"], "sections": {h: (s or None) for h, s in f["sections"].items()}, "pool": list(f["pool"]), "about": f["about"]}
             for n, f in d.get("forms", {}).items()}
    return forms, list(d.get("grid", {}).get("sections", []))

def id_patterns():
    """[(label, order, regex)] of the pack's document identifier forms (a TSV: label TAB order TAB regex; # comments), [] when none."""
    rel = pack().get("vocabulary", {}).get("id_patterns")
    if not rel or not os.path.exists(path(rel)): return []
    out = []
    with open(path(rel), encoding="utf-8") as f:
        for line in f.read().split("\n"):
            if not line.strip() or line.startswith("#"): continue
            label, order, rx = line.split("\t", 2); out.append((label.strip(), float(order), rx.strip()))
    return out

def theses():
    """The pack's thesis seeds (pack.toml [narratives] theses): a list of dicts with key, title, thesis, terms."""
    p = path(pack()["narratives"]["theses"])
    with open(p, encoding="utf-8") as f: return json.load(f)["theses"]

# Display settings (phase 5 of tools/platform-plan.md, 2026-10-22): what the presentation tools (the index, the timeline, the
# charts, the generated pages, the narrative viewer, the map) show by name, label, order or colour. The pack's [display.<section>]
# tables are laid over these core defaults key by key (a nested table merges, a list or a value replaces), so a pack that omits
# a key, or the whole [display] table, still renders with neutral wording. Every default below is domain-free.
DISPLAY_DEFAULTS = {
    "index": {   # tools/build_index.py: README.md
        "title": None,   # None: ledger.toml [ledger] title
        "intro": "A plain-markdown ledger of testimony: notes carry claims with their speaker, time and chain of custody, candour audits, dated timelines and cross-checks against every other telling; subject pages synthesize; research pages follow threads across the ledger; registers hold objects, actors, relations and leads.",
        "organised_heading": "How it's organized",
        "layout": ["project/", "  README.md          <- this index (the map), regenerated by tools/build_index.py", "  subjects/          <- one page per subject",
                   "  videos/            <- one note per recording", "  books/             <- one note per document or book",
                   "  research/          <- research pages that follow a thread across the database", "  transcripts/       <- held transcripts", "  tools/             <- the ledger's tools"],
        "subjects_heading": "Subjects", "notes_heading": "All recordings", "notes_intro": "Sorted by upload date.",
        "notes_columns": ["Uploaded", "Title", "Channel", "Length", "Subjects"],
        "books_heading": "Documents", "books_intro": "Document and book notes.", "books_columns": ["Published", "Title", "Source", "Length", "Subjects"],
        "research_heading": "Research", "research_intro": "Research pages that follow a thread across the database.", "research_columns": ["Added", "Title", "Scope", "Length", "Subjects"],
        "tags_heading": "Tag index", "tags_intro": "Tags are finer-grained than subjects. A note can carry many tags; tags with a single note are grouped at the end.",
        "single_tags_line": "Single-note tags:",
        "adding_heading": "Adding a source", "adding_text": "Sources are taken in through the intake protocol (tools/intake-staged.md); after each hand-back this index is rebuilt with `tools/build_index.py`.",
        "tasks_heading": "Tasks", "tasks_intro": "Task write-ups in research/tasks/: a job sized, piloted and described, with its decision state.", "tasks_columns": ["File", "Title", "First line"],
        "note_noun": ["recording", "recordings"], "book_noun": ["document", "documents"], "short_chars": 30,
        "short_rules": [],    # [{title_contains, number_regex, format}]: a short label built from a title (format's {} takes the regex's group 1)
        "short_labels": {},   # note file name -> short label (the tag index, the map, the timeline, the candour charts page)
        "tag_aliases": {},    # lower-cased tag -> canonical tag
    },
    "viewer": {   # tools/build_narrative_viewer.py and tools/narrative_viewer_template.html
        "title": None,   # None: "<ledger title> Narratives"
        "about": "Derived pages of the ledger: every node and ledger row cites notes.db rows; nothing here is a claim of its own. Protocol: tools/narratives.md.",
        "views": [["narratives", "Narratives"], ["compare", "Compare"], ["recurring", "Contradictions"], ["synchrony", "Synchrony"], ["register", "Register"]],
        "default_page": None,   # None: the pack's first mainline ([narratives] mainlines), else the first page
        "lanes": {"A": "Lane A", "B": "Lane B", "C": "Lane C", "D": "Lane D", "E": "Lane E", "F": "Lane F", "G": "Lane G", "H": "Lane H"},
    },
    "candour": {   # tools/draw_forthrightness_chart.py and tools/build_forthrightness_page.py
        "term": "Candour", "term_lower": "candour", "file_prefix": "candour",   # chart titles, page wording and figure file names
        "set_name": "the audited set", "page_title": "Per-interview candour charts", "page_labels": {},
        "page_scope": "**Scope.** Every note under the first audited subject whose audit is of an interview or hearing; monologues, where most audit rows have no asker, are left out.",
        "page_reading": "**Reading rules.** A closed turn is a boundary the speaker marked, not a finding that the topic is secret. The counting scale differs between notes, so the index is a within-source shape, not a cross-source ratio; compare shapes and where the closures fall, not decimals. Stated declines are refusals with a basis; \"none stated\" does not count.",
        "page_ranking_note": "", "page_closing": "", "page_related": "",
        "one_voice_labels": [],   # group labels containing one of these words are one voice (no "(n recordings)" in the ranking)
        "heading_note": "each note's own `## Candour audit` section",
        "auto_charts": True,   # ledger present draws a chart per audited recording and the groups file from the ledgered speakers (7b2);
                               # false: the charts and research/figures/<prefix>-groups.json are kept by hand
    },
    "openness": {"label_strip": []},   # tools/draw_openness_map.py: text removed from a source's row label
    "corroboration": {   # tools/draw_topic_corroboration.py: the core's meta tags and stop words; the pack's are added to them
        "meta_tags": ["candour audit", "forthrightness audit", "dated timeline", "cross-checks", "relations register", "leads register", "openness map", "youtube", "podcast", "interview", "documentary", "monologue", "transcript", "channelled source audit"],
        "meta_tags_extra": [], "aliases": {}, "place_words": [], "stop_words": ["project", "group", "program", "office", "report", "house", "committee", "institute", "national", "research", "brown", "smith", "green", "white", "black", "wilson", "davis", "taylor", "jones", "miller", "hill", "hall", "king", "young", "stone", "fox", "rich", "gold", "ryan", "paul", "john", "james", "michael", "robert", "thomas", "william", "david"],
        "stop_words_extra": [], "footer_note": "",
    },
    "map": {   # tools/build_graph_data.py (graph-display.json) and research/figures/map/database-map.html
        "source_groups": ["Interview shows and podcasts", "Video channels and talks", "News", "Films", "Official and archival records", "Online writing", "Modern books", "Historical texts and translations"],
        "default_video_group": "Video channels and talks", "default_book_group": "Modern books", "other_books": "Other books", "unknown_channel": "Unknown channel",
        "channel_sources": [], "book_sources": [], "source_meta": {},
        "third_party_dirs": ["books/sources/web/"], "posting_history_user": "",
        "held_lookup_dirs": ["books/sources/"],   # where a backticked file name in a note is looked for (the held sources, a bulk archive's mirror)
        "page_title_prefixes": ["Synthesis", "Research page", "People index"],   # stripped from a research page's title for its map label
        "unfiled": {"name": "Unfiled", "color": "#9AA0A8", "dark": "#6C737D"},
        "subject_palette": [["#C9772E", "#E09B5A"], ["#3F86B8", "#7FB3D5"], ["#8A63C6", "#B08BD9"], ["#5E9E57", "#8FBF7F"], ["#C25C85", "#D97B9E"], ["#A89530", "#C9B458"], ["#6F7682", "#8A8F99"], ["#2E7D8C", "#6FB3BF"]],
        "subjects": {},   # subject id -> {name, color, dark}; a subject not named takes the palette in the pack's graph order
        "page_kinds": {"investigation": "Investigations", "synthesis": "Syntheses and threads", "map": "Maps", "ledger": "Ledgers", "scan": "Scans and verifications", "control": "Text controls", "register": "Registers", "timeline": "Consolidated timelines", "index": "Indexes", "log": "Tool logs and sweeps", "other": "Other"},
        "era_segments": [],   # [{label, from, to, frac, scale (linear | deep | open-end), ticks}]; empty: the pack's [eras] map labels, equal widths
        "help_rows": [["Quotes", "", "Verbatim quotes per title with timestamps."], ["Works cited", "", "Books, papers, films and documents each title names."],
                      ["Corrections and blocked passages", "queue files", "Claims corrected after cross-checks, and passages held back by output filters."],
                      ["Subject pages", "", "What each title adds to each subject."]],   # [[name, size, what it is]]: the help panel's tracked-work table
        "help_note": "",   # a sentence after the tracked-work intro (when the sizes were counted)
    },
    "typed_graph": {   # tools/build_graph_data.py graph-typed.json: one graph, three edge kinds (tools/platform-plan.md, the map row)
        "node_kinds": {"person": {"label": "people", "color": "#8A63C6"}, "actor": {"label": "actors", "color": "#B8432F"}, "polity": {"label": "polities", "color": "#2E7D8C"}},
        "edge_kinds": {"relation": {"label": "people to people: relations register", "color": "#6B7C93"},
                       "order-of-battle": {"label": "actors to polities: order of battle", "color": "#B8432F"},
                       "chain-hop": {"label": "people to actors: chain hops", "color": "#C58E1F"}},
        "actor_aliases": {},   # actor (a kind or name from the pack's actor vocabulary) -> further spellings matched as words
        "polity_unplaced": ["unknown", "not stated", "none", "none stated", "n/a", "", "not legible", "relayed"],
    },
    "status": {"title": "Status", "rulings_log": "rulings.md", "cost_log": "research/cost-log.md"},   # tools/build_status.py
}

def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items(): out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out

def display(section):
    """The display settings of one presentation section: the core default laid under the pack's [display.<section>]."""
    return _merge(DISPLAY_DEFAULTS.get(section, {}), pack().get("display", {}).get(section, {}))

# Core tools' domain data (phase 7b of tools/platform-plan.md, 2026-10-22): the literals a core tool needs that are a pack's, such as
# the agencies and office-holders tools/divergences.py tallies, the interview hosts tools/echoes.py groups, the lanes
# tools/narrative_pack.py sorts rows into, and the page wording that names the pack's own pages. The pack's [tools.<tool>] table
# is laid over these domain-free defaults key by key, and a key the pack gives replaces the default whole (a lexicon is the pack's,
# never a union with the core's). A pack that names none of them still runs every tool with neutral values.
TOOL_DEFAULTS = {
    "divergences": {   # tools/divergences.py: who diverges, and whether the party is an agency or an office-holder
        "agencies": ["Authority", "Agency", "Board", "Commission", "Committee", "Council", "Department", "Ministry", "Office", "Inquiry",
                     "Regulator", "the government", "the military", "the press", "task force", "official transcript", "the record",
                     "public record", "captions"],
        "officials": [],
        "agency_canon": [],    # [regex, office]: the spellings and named heads of one office folded to its name
        "extra_canon": [[r"minister|secretary of state|member of parliament|senator|representative|office-holder", "Office-holders"],
                        [r"military|officials'|official side|official account|official record|agencies|government office", "Official record (unnamed office)"]],
        "agency_heads_rx": r"(?!)",   # named heads tallied with their office (a pattern on the lower-cased party; this one never matches)
        "agency_heads": [], "party_aliases": {}, "non_parties": ["unstated", "narrator"],
        "events": {}, "places": {},   # name -> lower-cased words that place a divergence at the event or place
        "related_row": "| **Related** | [leads register](leads-and-inferences.md) (kind divergence) |\n",
        "pooled_prefixes": [],        # party-name prefixes pooled into one office in section 2
    },
    "echoes": {   # tools/echoes.py: same wording and same rare details across independent-looking mouths
        "hosts": [],                  # interview hosts and channels (a host retelling a guest is expected)
        "agency_rx": r"(?<![a-z])(ministry|department|agency|authority|board|commission|committee|parliament|government|task force|official transcript|the record)(?![a-z])",
        "first_name_aliases": {},     # a speaker recorded by first name or surname -> the full name
        "role_words_rx": r"\b(reply|description|channel|voices?|occupant|pilot|aviator|narrator|questioner|witness|caller|congress(?:wo)?man|senator)\b",
        "role_only_rx": r"^(an? |the )?(interviewee|past guest|guest|host|guest voice|unidentified|unknown|voice|-over|over|voices|episode|episode voices|narration|questioner|analyst|pilot|witness|wife|second voice)$",
        "namey_rx": r"(?!)",          # full office names that would otherwise read as rare wording
        "org_rx": r"^(dod|department of defense|department of|office of|defense|the pentagon|pentagon|nasa|navy|air force|army|marines?|congress|senate|house|committee|subcommittee|intelligence|security|under secretary|secretary|director|deputy|general|president|government|federal|national|united states|us|usa|america|american|washington|dc|cia|fbi|nsa|dia|nro|doe|faa|noaa|dhs|gao|ig|inspector general|task force|white house|earth|moon|mars|sun|god|lord|jesus|christ|bible|genesis|exodus|torah|quran|heaven|hell|internet|youtube|google|twitter|facebook|x|new york|california|nevada|texas|florida|virginia|ohio|arizona|new mexico|washington post|new york times|wall street journal|nyt|wsj|cnn|fox|bbc|ted|podcast|episode|part|chapter|volume|vol|section|page|q|a|program|programs|programme|foia|oath|reagan|clinton|obama|trump|biden|bush|kennedy|jfk|eisenhower|truman|roosevelt|nixon|carter|ford|soviet|russia|russian|russians|china|chinese|japan|japanese|german|germans|germany|british|britain|england|uk|europe|european|israel|israeli|iran|iranian|iraq|africa|india|indian|egypt|egyptian|greek|greece|roman|rome|jewish|jews|christian|christians|muslim|arab|arabs|earthlings|humans|human|humanity|men|women|black|white|world war ii|world war two|wwii|cold war|nazis?|ss|world)$",
        "unit_rx": r"(?:foot|feet|ft|meters?|metres?|miles?|people|men|witnesses|hours|minutes|days|weeks|months|years|programs?|programmes?|pages|percent|knots|mph|tons?|pounds|inches|kilometers?|kilometres?|sessions|objects|vehicles|planes|aircraft|helicopters|soldiers|scientists|engineers|contractors|companies|countries|acres|square feet|stories|floors|levels)",
        "how_to_read": "How to read this page. 'Acknowledged' means the relations register already records one speaker as the other's source or interviewer, so the repetition has a stated route. 'Same channel' means the notes share a host or channel, the commonest route for a repeated line, and it is the host's own retelling that should be checked. 'Unacknowledged' means the same wording appears in mouths with no recorded link: the candidates for a common unnamed source. 'First' is the earliest-uploaded telling held, which is not necessarily the origin.\n",
    },
    "integrate_report": {   # tools/integrate_report.py: the intake hand-back into subject pages, the object register and the openness dataset
        "register_match_keys": ["match to the reference object"],   # report keys read as an object register row's Match
        "audit_marks": {},          # audited subject page -> the opening words of its audit paragraph (the bullet's anchor)
        "audit_mark_before": [],    # pages whose bullet goes before the paragraph (elsewhere: after the paragraph's list)
        "topic_aliases": {},        # a reported topic label's letters -> a topic code
        "openness_from_note": True,   # a report without openness_counts/cells: read them from the note's audit (7b2); false: by hand
    },
    "build_db": {   # tools/build_db.py: research page kinds and the ties tracker
        "ties_tracker": "research/ties-tracker.md",
        "page_kinds": [   # [prefix or exact stem, kind, generated]: the first that fits wins
            ["narrative-synchrony-", "narrative-synchrony", 0], ["narrative-rival-", "narrative-rival", 0], ["narrative-register", "register", 0],
            ["narrative-", "narrative", 0], ["investigation-", "investigation", 0], ["synthesis-", "synthesis", 0], ["object-register", "register", 0],
            ["actor-register", "register", 0], ["timeline-consolidated", "timeline", 0], ["timeline-contradictions", "timeline", 0],
            ["timeline-master", "timeline", 1], ["answered-questions", "index", 1], ["people-index", "index", 1], ["relations-register", "register", 1],
            ["leads-and-inferences", "register", 1], ["first-utterance-register", "register", 1], ["echo-patterns", "log", 1],
            ["divergence-patterns", "log", 1], ["topic-corroboration", "log", 1], ["forthrightness-charts", "log", 1], ["openness-map", "log", 1],
            ["declined-answered", "log", 1], ["cited-videos-not-held", "log", 1], ["audio-checks", "log", 1], ["reference-redacted", "log", 1],
            ["cost-log", "log", 1], ["status", "log", 1]],
    },
    "evidence_pack": {   # tools/evidence_pack.py: an investigation's evidence pack
        "register_title": "Object register entries", "watch_title": "Object-watch rows",
        "extra_page_files": [],     # further pages --pages greps (a bulk archive's index page)
    },
    "post_intake": {   # tools/post_intake.py: a speaker ledger's section from the report
        "ledger_key": "speaker_ledger_section", "ledger_note_key": "speaker_ledger_note",
        "ledger_page": "",          # the ledgered speaker's page; empty: no section is appended
        "ledger_anchor": "\n## Delta",
    },
    "people_dates": {   # tools/people_dates.py: birth and death years for the map's people
        "group_words": {"other": ""},   # subject -> words a matched person's description should share
        "founded_why": "to order the map's generations by birth year",
    },
    "narratives": {"stop_names": ["The", "A", "An", "Node", "Nodes", "Root", "Roots", "Relay", "Via", "Unnamed", "Document", "Documents"],   # tools/narratives.py: chain words that are no teller
                   "press_markers": ["article", "news", "newspaper", "magazine", "press report", "forum", "thread", "blog", "broadcast"]},   # a document note whose Guest or Host names one of these is a press note (the basis audit, 2026-10-25)
    "blocked_passages": {"queue_precedent": ""},   # tools/blocked_passages.py: the first block handled by hand, named on the queue page
    "reddit_rss_patch": {"default_dir": "sources/web/reddit"},   # tools/reddit_rss_patch.py: the held Reddit folder scanned by default
    "stargate_viewer_filter": {   # tools/stargate_viewer_filter.py: route a mirrored archive's documents by named actor
        "db": "sources/archive/index.db", "outdir": "sources/archive/by-actor",
        "initials": {}, "interviewer_labels": [], "ident": {}, "label_ids": {},   # known initials -> id; labels that are no actor; id -> identity
        "cats": {}, "db_cats": [], "short_labels": {"unclassified": "uncl"}, "stop_words": "",
        "actor_page_title": "# Actor %s: documents routed by typed layer",
        "actor_page_intro": "Identity: %s. Generated by tools/stargate_viewer_filter.py --index from the archive's OCR text, index title and folder; no page images read. `hw` = ocr_quality <= %.2f (handwriting-heavy). Role = how the actor string appears (viewer, source, monitor, interviewer, initials, transcript label). Rulings come from overrides.tsv.",
        "sites_title": "# Session sites pooled from the typed layer",
        "sites_intro": "For every 'SESSION DATA. SITE # n' document: the actors filed on the site, the document count, the most frequent capitalised words across those documents' OCR (form boilerplate removed) and, where one survives, a feedback sentence beginning with the site number. The nouns are a guess at the target, not a reading.",
        "index_title": "# Archive documents by actor and topic",
        "index_intro": "The routing of the whole release (%d documents mirrored) by actor and by category, built from the typed layer only. Actors with under %d documents are pooled in other.md. Hand rulings in overrides.tsv are applied on every rebuild and shown in the Ruling column. Rebuild with `python3 tools/stargate_viewer_filter.py --index`.",
    },
    "stargate_index": {   # tools/stargate_index.py: a mirrored archive's full-text index (quality() is core)
        "all": "sources/archive/all", "db": "sources/archive/index.db", "index": "sources/archive/index.xlsx",
        "columns": {"id": "id", "date": "date", "title": "title", "folder": "folder", "pages": "pages", "box": "box"}, "id_prefix": "",
    },
    "stargate_mirror": {   # tools/stargate_mirror.py: mirror a collection item by item (fetch() is core)
        "user_agent": "ledger-archive-mirror/1.0 (a research ledger's archive mirror)",
        "header": "# Document {esdn}, mirrored from its archive item.\n# Title: {title}\n# Folder: {folder}\n# Pages: {pages}\n\n",
        "out": "sources/archive/all", "id_column": "id", "id_prefix": "", "url": "",
        "title_column": "title", "folder_column": "folder", "pages_column": "pages",
    },
    "stargate_bulk": {   # tools/stargate_bulk.py: a collection from one bulk item's zips
        "out": "sources/archive/all", "scratch": "wip/archive-bulk", "scratch_env": "LEDGER_BULK_SCRATCH",
        "user_agent": "ledger-archive-bulk/1.0 (a research ledger's archive mirror)", "zips": [], "url": "", "index": "sources/archive/index.xlsx",
        "header": "# Document {esdn}, from {zipname} ({member}).\n# Title: {title}\n# Folder: {folder}\n# Pages: {pages}\n\n",
        "id_column": "id", "id_prefix": "", "title_column": "title", "folder_column": "folder", "pages_column": "pages",
    },
    "greer_lens": {   # tools/greer_lens.py: the disinformation lens over a pack's instance
        "instance": None,             # the [[lenses.instance]] id; None: the pack's first
        "frame_name": "the frame", "placement_key": "placement", "reason_header": "Stated reason",
        "frame_note": "", "frame_person": "", "frame_person_forms": [], "frame_speaker_prefix": "",
        "test_text": {
            "T1b": "   that is not itself placed on the control side. The frame's rule drops a known co-mingler outright, so each is a counterexample to the sorting.",
            "T2a": "\nT2. Rows in which a speaker, or the origin the row relays, denies what the frame says the denier's side holds.",
            "T2b": "   The frame: such a speaker is uninformed or disinforming. A disclosure-side denier is a counterexample.",
            "T3a": "\nT3. Rows presenting the frame's protected party as hostile, harmful or a threat. The frame: such a speaker is wrong.",
            "T4a": "\nT4 (applied to the frame's own source). Control-side people in the frame's own sourcing: relations in which such a person is its source,",
            "T5a": "\nT5. Firsthand reports of threats or reprisals against placed speakers. The frame: nobody bothers people who spread disinformation.",
            "T6a": "\nT6. People the frame places on the disclosure or unwitting side who are recorded approaching its camp as adversaries or red-teamers."},
        "t2_denial_rx": r"(?!)", "t2_denial_rx2": r"(?!)",   # the instance's denial wording (never matches by default)
        "t3_hostile_rx": r"(?:hostile|malevolent|evil|a threat|threatening|harmful|killed|hurt)", "t3_beings_rx": r"(?!)",
        "t3_negation_rx": r"\bnot (?:this |a |an |that )?(?:hostile|a threat|evil|malevolent)\b|\bno (?:indication|evidence)[^.]{0,30}hostile|\bhoax|\bI (?:personally )?have not\b|\bhave never\b|\bhaven't\b",
        "t4_exempt": [], "t5_topic": "(no topic)",
    },
    "narrative_pack": {   # tools/narrative_pack.py: the narrative agents' pre-pass (lanes, insiders, agencies, seeds)
        "lane_names": {"A": "Lane A", "B": "Public record", "C": "Lane C", "D": "Lane D", "E": "Money and contracts", "F": "Lane F", "G": "Antecedents", "H": "Organisations"},
        "lane_rx": {   # a lane's wording (compiled with re.I); a lane left out is placed by topic and subject only
            "H": r"\b(found(s|ed|ing)|establish(es|ed)|stood up|stands up|set(s)? up|creat(es|ed)|incorporat(es|ed)|form(s|ed)|renam(es|ed)|rebrand|dissolv|disband|shut(s)? down|closes|closed down|wound up|merg(es|ed)|spun off|launch(es|ed) (the|a|an|its) (office|program|programme|project|institute|foundation|company|task force|unit|group|board|society|firm|division)|appoint(s|ed)|named (director|head|chief|administrator)|takes over as|becomes (director|head|chief|president|chairman|CEO)|hired as|joins (the )?[A-Z]|leaves (the )?[A-Z]|resign|retires from|fired|contract (ends|expires|terminated)|(program|programme|project|office|unit) (ends|ended|closed|terminated|cancelled|canceled|transferred|moved))\b",
            "B": r"\b(hearing|testif|testimony|Congress|Senate|House (Oversight|Intelligence|Armed)|press|article|published|publishes|publication|documentary|episode|interview|podcast|aired|broadcast|releases|released|declassif|FOIA|op-ed|New York Times|NYT|Washington Post|60 Minutes|Fox|CNN|statement|letter to|briefed Congress|disclosure|whistleblower|Inspector General|executive order|memo released|book (is )?published|goes public|went public|announces|announced|tweet|posted)\b",
            "E": r"\$|\b(fund(s|ed|ing)|contract(s|ed)?|grant(s|ed)?|budget|million|billion|IRAD|sole[- ]source|appropriat|misappropriat|paid|payment|donat|invest(s|ed|or|ment)|sponsor|line item|earmark|cost)\b"},
        "topic_lane": {},             # claims topic code -> lane
        "lane_fallback": {"primary_subject": "", "secondary_subject": "", "primary_lane": "A", "primary_label": "subject (primary)",
                          "secondary_lane": "D", "secondary_label": "subject (secondary)", "antecedent_year": None, "antecedent_lane": "G",
                          "antecedent_label": "before the antecedent year", "fallback_lane": "D"},
        "agencies": ["Authority", "Agency", "Board", "Commission", "Committee", "Council", "Department", "Ministry", "Inspector General", "Regulator", "Parliament"],
        "insider_topics": [],         # claims topics on which five firsthand rows make a speaker an insider
        "seeds_intro": "The pack's thesis seeds (pack.toml [narratives] theses).",
        "other_seed_sources": "## Other seed sources\n\n- Thread leads: `sqlite3 notes.db \"select n, lead from leads where kind='thread'\"`.\n- Dense windows: synchrony-index.md.\n",
    },
}

INTAKE_DEFAULTS = {"sample_threshold": 3}   # pack.toml [intake]: the sample reading's threshold (2026-10-25, tools/ledger/sample.py)

def intake():
    """The pack's [intake] table laid over INTAKE_DEFAULTS (sample_threshold: the count of faults of meaning in the twenty sampled
    rows that sends a note to the check phase before it integrates; the slot pack.sample_threshold of the briefs)."""
    return _merge(INTAKE_DEFAULTS, pack().get("intake", {}))

def sample_threshold(): return int(intake()["sample_threshold"])


def tool_data(tool):
    """A core tool's domain data: TOOL_DEFAULTS[tool] with the pack's [tools.<tool>] keys replacing the defaults key by key."""
    d = dict(TOOL_DEFAULTS.get(tool, {}))
    try:
        over = pack().get("tools", {}).get(tool, {})
    except FileNotFoundError:   # no pack yet (the install check, setup before stage 1 writes one): the core defaults alone
        over = {}
    d.update(over)
    return d

def vocabulary_path(key):
    """The pack's [vocabulary] file for `key` (name_aliases, stock_phrases, stock_phrases_domain, ...), absolute, or None when the pack
    names none; the caller decides what an absent file means (a project with no alias table has no aliases)."""
    try:
        rel = pack().get("vocabulary", {}).get(key)
    except FileNotFoundError:   # no pack yet
        return None
    return path(rel) if rel else None

def ledger_title(): return ledger().get("ledger", {}).get("title") or ledger().get("ledger", {}).get("name") or "Ledger"

def short_labels(): return dict(display("index")["short_labels"])

def subject_display():
    """[(subject id, name, light colour, dark colour)]: the subjects the pack names in [display.map] subjects, in its graph order (when
    it names none, every subject of the graph order, coloured from the palette), then the unfiled group: the map's group colours and names."""
    m = display("map"); pal = m["subject_palette"]; out = []; seen = set()
    named = m["subjects"]   # a pack that names its subjects' display gets those only (in graph order); otherwise every subject takes the palette
    for i, s in enumerate([g for g in graph_order() if not named or g in named] + [k for k in named if k not in graph_order()]):
        if s in seen: continue
        seen.add(s); d = m["subjects"].get(s, {}); c = pal[i % len(pal)] if pal else ["#888888", "#aaaaaa"]
        out.append((s, d.get("name", s.replace("-", " ").capitalize()), d.get("color", c[0]), d.get("dark", c[1])))
    u = m["unfiled"]; out.append(("unfiled", u["name"], u["color"], u["dark"]))
    return out

def era_segments():
    """The map's time-axis segments: the pack's [display.map] era_segments, else one linear segment per [eras] map era, equal widths."""
    segs = display("map")["era_segments"]
    if segs: return [dict(s) for s in segs]
    E = eras("map"); n = len(E) or 1
    return [{"label": lab, "from": lo, "to": hi, "frac": round(1 / n, 4), "scale": "linear"} for lab, lo, hi in E]

def actor_vocabulary():
    """The pack's actor and polity register for the presentation tools: {actors (the actor vocabulary matched in the register's cells),
    polity_name, register (page path), clusters (the page whose table defines the register's cluster codes, or "")}; empty values when
    the pack has none."""
    a = pack().get("actors", {})
    return {"actors": list(a.get("kinds_of_being", a.get("actors", []))), "polity_name": a.get("polity_name", ""), "register": a.get("register", ""),
            "clusters": display("typed_graph").get("clusters_page") or a.get("entities_map", "")}

# core identifiers a pack may rename ([names] in pack.toml; 7b2, 2026-10-23: the core's names are the neutral ones, and a pack whose
# corpus was built under earlier names keeps them by mapping, so its database, reports and baseline are unchanged)
CORE_NAMES = {
    "table.object_watch": "object_watch",      # notes.db: the object watch rows of every note
    "report.object_rows": "object_rows",       # an intake report's count of object watch rows
    "label.object_rows": "object rows",        # build_db's printed count
    "section.object_watch": "object watch",    # build_report's section label
    "baseline.object": "object",               # the baseline's per-note key
    "baseline.object_entries": "object_entries",   # the baseline's object register size
    "baseline.actor_rows": "actor_rows",       # the baseline's actor register size
    "actors.header_column": "",                # a further actor-table second-column prefix the pack's register uses
}

def name(key):
    """A core identifier (CORE_NAMES) as the active pack names it in [names], else the core name. KeyError for an unknown key."""
    core = CORE_NAMES[key]
    v = pack().get("names", {}).get(key)
    return v if isinstance(v, type(core)) and v != "" else core

def name_synonyms():
    """The pack's actor-row key synonyms ([names] \"actors.key_synonyms\", normalised key -> normalised column), {} when none."""
    return dict(pack().get("names", {}).get("actors.key_synonyms", {}) or {})

def pirs():
    """The pack's declared priority intelligence requirements ([[pirs.pir]]: id, question, eeis, terms, declared, by), [] when none."""
    return [dict(p) for p in pack().get("pirs", {}).get("pir", [])]

if __name__ == "__main__":
    if "--get" in sys.argv:
        keys = sys.argv[sys.argv.index("--get") + 1].split("."); d = pack()
        for k in keys: d = d[k]
        print(json.dumps(d, indent=1, ensure_ascii=False))
    else:
        print(json.dumps({"ledger": ledger(), "pack_dir": pack_dir(), "pack": pack()}, indent=1, ensure_ascii=False))
