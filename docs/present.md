# Presentation: the pack's display settings, the map's data files, the status page and `ledger present` (2026-10-22)

The presentation layer (phase 5 of tools/platform-plan.md) turns the notes and notes.db into pages: the index (README.md), the master timeline, the answered-questions roll-up, the forthrightness charts and their page, the topic corroboration chart, the first-utterance report, the divergence patterns page, the narrative viewer, the map and its data files, and the status page. Every one is generated; none is edited by hand. Nothing in the generating tools names a domain: every title, label, colour, group and word list comes from the active pack's `[display.<section>]` tables, laid over the core defaults. Every output is a local file; the map and the viewer open with no network.

Examples below use the invented cases of tools/example-casebook.md.

## 1. The `[display]` table and its core defaults

`tools/packload.py` holds the core defaults (`DISPLAY_DEFAULTS`) and `packload.display(<section>)` returns them with the pack's `[display.<section>]` laid on top: a key the pack leaves out keeps the core default, and a nested table is merged key by key (a pack that sets one subject's colour keeps the palette for the rest). The exact default values are in `DISPLAY_DEFAULTS`; `python3 tools/packload.py --get display` prints the pack's own values. A pack that has no `[display]` table at all renders every page with the core defaults.

| Section | Read by | Keys (core default in brief) |
|---|---|---|
| `index` | tools/build_index.py (README.md) | `title` (none: ledger.toml `[ledger] title`); `intro` (one neutral paragraph on what the ledger holds); `organised_heading`, `layout` (the folder tree); the headings, intros and columns of each list: `subjects_heading`, `notes_heading`, `notes_intro`, `notes_columns`, `books_heading`, `books_intro`, `books_columns`, `research_heading`, `research_intro`, `research_columns`, `tags_heading`, `tags_intro`, `single_tags_line`, `adding_heading`, `adding_text`, `tasks_heading`, `tasks_intro`, `tasks_columns`; `note_noun`, `book_noun` (recording, document); `short_chars` (30); `short_rules` (none: a short label built from a title by `title_contains`, `number_regex`, `format`); `short_labels` (none: note file name to short label, used by the tag index, the map, the timeline and the forthrightness charts page); `tag_aliases` (none) |
| `viewer` | tools/build_narrative_viewer.py and tools/narrative_viewer_template.html | `title` (none: "<ledger title> Narratives"); `about`; `views` (narratives, compare, contradictions, synchrony, register); `default_page` (none: the pack's first mainline); `lanes` (A to H, named "Lane A" and so on) |
| `candour` | tools/draw_forthrightness_chart.py, tools/build_forthrightness_page.py | `term`, `term_lower`, `file_prefix` (the audit's name as the chart titles and page wording use it, and the figure and page file names, `research/<file_prefix>-charts.md`; the core defaults are in DISPLAY_DEFAULTS, and this pack sets Forthrightness, forthrightness, forthrightness); `set_name`; `page_title`; `page_labels`; `page_scope`, `page_reading`, `page_ranking_note`, `page_closing`, `page_related`; `one_voice_labels`; `heading_note` |
| `openness` | tools/draw_openness_map.py | `label_strip` (none: text removed from a source's row label) |
| `corroboration` | tools/draw_topic_corroboration.py | `meta_tags` (the core's own method tags, left out of the chart); `meta_tags_extra`; `aliases`; `place_words`; `stop_words` (generic words and common names); `stop_words_extra`; `footer_note`. The pack's lists are added to the core's |
| `map` | tools/build_graph_data.py (graph-display.json) and research/figures/map/database-map.html | `source_groups` (eight neutral groups: interview shows and podcasts, video channels and talks, news, films, official and archival records, online writing, modern books, historical texts and translations); `default_video_group`, `default_book_group`, `other_books`, `unknown_channel`; `channel_sources`, `book_sources`, `source_meta` (none: the pack's assignment of channels and books to groups); `third_party_dirs` (`books/sources/web/`); `posting_history_user`; `held_lookup_dirs` (`books/sources/`); `page_title_prefixes`; `unfiled` (name and two colours); `subject_palette` (eight colour pairs, light and dark); `subjects` (none: every subject of the pack's graph order takes the palette); `page_kinds` (investigation, synthesis, map, ledger, scan, control, register, timeline, index, log, other, each with its group name); `era_segments` (none: one linear segment per era of the pack's `[eras]`, equal widths); `help_rows` (four neutral rows of the help panel's tracked-work table); `help_note` |
| `typed_graph` | tools/build_graph_data.py (graph-typed.json) | `node_kinds` (person, actor, polity, each with a label and colour); `edge_kinds` (relation, order-of-battle, chain-hop, each with a label and colour); `actor_aliases` (none); `polity_unplaced` (the cell values that place no polity: unknown, not stated, none, and the like); `clusters_page` (none: the pack's `[actors] entities_map`) |
| `status` | tools/build_status.py (research/status.md) | `title` (Status); `rulings_log` (`rulings.md`); `cost_log` (`research/cost-log.md`) |

A pack's override, in the casebook's terms:

```toml
[display.map.subjects.infrastructure-safety]
name = "Infrastructure safety"
color = "#3F86B8"
dark = "#7FB3D5"

[display.status]
title = "Harrowmere ledger: status"
```

The priority intelligence requirements the status page reads are their own pack table, not part of `[display]` (section 4).

## 2. The map and its data files

The map is research/figures/map/database-map.html, served locally by `ledger present map` (tools/map_server.py). It loads d3 from the vendored copy `../vendor/d3-7.9.0/d3.min.js` (research/figures/vendor/README.md records the version, licence, source and checksums) and reads its data from research/figures/, all written by `tools/build_graph_data.py` (`ledger build graph`, or `ledger present --with-graph`):

| File | What it holds |
|---|---|
| graph-data.json | notes, people, eras, shared-person edges, era profiles |
| graph-claims.json, graph-evidence.json, graph-timeline.json | the claims, evidence items and timeline rows the panels show |
| graph-edges.json | the cross-check edges (their own file since 2026-10-08, for size) |
| graph-relations.json | the relations register, who checks whom, and the forthrightness audits per person (the relations circle) |
| graph-display.json | the pack's display settings for the map (format below) |
| graph-typed.json | one graph with three typed edge kinds (format below) |

### graph-display.json

`{built, title, subjects, era_segments, page_kinds, help_rows, help_note, typed, actor_register_stem, topics}`:

| Key | Form | From |
|---|---|---|
| `built` | date | the build |
| `title` | text | ledger.toml `[ledger] title` |
| `subjects` | `[{id, name, color, dark}]`, the unfiled group last | `packload.subject_display()`: `[display.map] subjects`, else the palette in the pack's graph order |
| `era_segments` | `[{label, from, to, frac, scale, ticks?, era?}]`; `scale` is `linear`, `deep` (a compressed far past) or `open-end` | `packload.era_segments()`: `[display.map] era_segments`, else equal linear segments over `[eras]` |
| `page_kinds` | `{kind: name}` | `[display.map] page_kinds` |
| `help_rows`, `help_note` | `[[name, size, what]]`, text | `[display.map]` |
| `typed` | `{node_kinds: {kind: {label, color}}, edge_kinds: {kind: {label, color}}}` | `[display.typed_graph]` |
| `actor_register_stem` | text | the pack's `[actors] register` page stem |
| `topics` | the topic codes and labels | the pack's topic vocabulary |

### graph-typed.json

`{built, kinds, meta, nodes, edges}`: the map's one graph with typed edges (tools/platform-plan.md, the map row: people to people, actors to polities, people to actors).

- `kinds`: as `typed` in graph-display.json.
- `meta`: `{edges_by_kind, nodes_by_kind, register, clusters_page, clusters, vocabulary_to_cluster, register_rows, polity_statements, rows_without_an_actor, placements, hops}`: counts and the pages read. `rows_without_an_actor` counts register rows that name no cluster code and no word of the actor vocabulary; they are counted, never placed.
- `nodes`: `{id, kind, label, ...}` with `kind` one of `person`, `actor`, `polity` and the id prefixed by kind: `p:<name>` (a person; `pi` is the index into graph-data.json's people), `a:<cluster code>` (an actor; `code` and `rows`), `y:<normalised polity name>` (a polity; `body`, `named`, `refs`).
- `edges`, one form per kind:
  - `relation`: `{source, target, row}`: `p:` ids (`target` null for a party not on the people list); `row` is the relations row of graph-relations.json, verbatim.
  - `order-of-battle`: `{source (a:), target (y:), role, w, rows}`: `role` is member, outside, opposed, subordinate or placed; `w` the weight; `rows` `[[register id, role, teller, time, chain, quote or kind cell]]`.
  - `chain-hop`: `{source (p:), target (a:), hop, w, rows}`: `hop` the lowest hop at which the person stands in a chain that reaches the actor; `rows` `[[register id, hop]]`.

The relation edges come from notes.db through graph-relations.json; the order-of-battle and chain-hop edges are read from the actor and polity register page the pack names (`[actors] register`) until notes.db carries that register as tables (wip/platform-phase5/handoffs.md item 1). A casebook reading: a row of the register saying that Greenhollow Trading is "a front for the League", told in the Dorr cables, becomes an order-of-battle edge from the Greenhollow actor to the League polity with role `subordinate` and the row's teller, time and chain in `rows`.

## 3. The status page: research/status.md

Generated by `tools/build_status.py` (`ledger present status`), regenerated after every hand-back, plain markdown, LF, no external links. Its sections, and what each reads (nothing on the page is a judgement of its own):

| Section | Reads |
|---|---|
| Sources held and queued | the sources/ layout's alias table and the files held under sources/ by media kind (tools/ledger/paths.py); notes by source kind (tools/source_balance.py's kinds: research/source-kinds.md overrides, else the pack's stem patterns); queued records (every `sources/**/queue.tsv`, the database adapter's new and changed records); open blocked passages (research/corrections/blocked-passages.md) |
| Notes written | notes.db: notes by folder, research pages (`pages`), subject pages, narrative pages, words |
| Register sizes | notes.db tables (open questions, leads, relations, the object register and the object-watch rows, people and mentions, works, the ties tracker, narrative nodes and contradiction rows, the owner's map notes and investigations); the actor and polity register's rows, polity statements, placements and chain hops from graph-typed.json's `meta`, when it is built; the first-utterance clusters from the pack's `[catalysts] register` |
| What the narratives rest on that is not held | the first-utterance report (the pack's `[catalysts] report`, written by `tools/first_utterance.py --narratives`): the clusters the narrative pages rest on whose first telling is not held (`late`, `candidate not held`, `known earlier not held`) |
| Quota ledger | tools/source_balance.py's own lines (a read-only run; tools/intake-policy.md rule 6) |
| Open rulings | the rulings log, `[display.status] rulings_log` (default `rulings.md` at the project root): a table row with a cell reading `open`, `pending` or `proposed`, or a bullet line containing one of those words, counts as open (a lenient reading until phase 7 fixes the log's form); a placeholder line when no log exists |
| Priority intelligence requirements | the pack's `[[pirs.pir]]` tables (below), and for each the held rows that name its terms (the full-text index `rows_fts`, as `ledger analyse rows` searches it) |
| Cost log | the cost log, `[display.status] cost_log` (default `research/cost-log.md`), when `tools/agent_usage.py`'s per-agent table has been saved there; a line saying so when it has not |

The priority intelligence requirements, one `[[pirs.pir]]` table each in the pack's pack.toml, read by `packload.pirs()`, written by /setup stage 1:

```toml
[[pirs.pir]]
id = "PIR-1"
question = "Who set the 2011 hardwood levy's rate, and on whose advice?"
eeis = ["the date of the decision", "the office that set it", "the instrument that records it"]
terms = ["levy", "Timber Exporters' League", "Dorr cables"]   # the rows_fts search terms
declared = "2026-10-22"
by = "project manager"
```

A PIR seeds keywords and surfaces held rows; it never places anything the sources do not support. A pack that declares none gets a line saying so.

## 4. `ledger present`

`ledger present` (no tool named, or only options) runs `tools/build_reports.py`: every generated page in order, each step run as its tool would be from the project root. A step that fails is reported and the next still runs (the pages are independent); the command exits 1 when any step failed.

| Step | Tool | Writes |
|---|---|---|
| index | tools/build_index.py | README.md |
| timeline | tools/build_timeline.py | research/timeline-master.md |
| answers | tools/answers_rollup.py | research/answered-questions.md |
| candour-page | tools/build_forthrightness_page.py | `research/<file_prefix>-charts.md` (the audit charts' display section) |
| topic-corroboration | tools/draw_topic_corroboration.py | research/figures/topic-corroboration.png, .svg, .json |
| first-utterance | `tools/first_utterance.py --narratives` | the pack's `[catalysts] report` page |
| divergences | tools/divergences.py | research/divergence-patterns.md |
| viewer | tools/build_narrative_viewer.py | research/figures/narratives-viewer.html |
| graph (only with `--with-graph`, before the status page, which reads graph-typed.json) | tools/build_graph_data.py | research/figures/graph-*.json, graph-display.json, graph-typed.json |
| status | tools/build_status.py | research/status.md |

Options: `--only a,b` and `--skip a,b` (step names; naming `graph` in `--only` runs it), `--with-graph`, `--log DIR` (each step's printed output saved as `DIR/<step>.txt`, UTF-8, LF), `--list` (print the steps and their outputs, run nothing). `ledger present status` runs the status page alone; `ledger present <tool>` runs one presentation tool (`openness-map`, `forthrightness-chart`, `topic-corroboration`, `matrix-heatmap` (a pack tool), `map`, `owner-store`, `status`, `reports`); `ledger tools` lists them. The hand-back (`ledger integrate`) does not yet end with `ledger present` (wip/platform-phase5/handoffs.md item 3); until it does, the orchestrator runs it after integrating.
