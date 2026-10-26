# The ledger package (phase 2 of tools/platform-plan.md, 2026-10-22)

Three modules and a command. Every tool in tools/ that parses a note or a house-form page does it through `ledger.notes`;
every tool that resolves a held path or writes a new hold does it through `ledger.paths`. `python3 tools/<tool>.py` works as
before; `python3 ledger.py ...` at the project root is the one command over all of them.

## ledger.notes: the parser library

- Read and write: `read_text`, `read_lines`, `iter_lines`, `read_head`, `first_line` normalise line endings (CRLF and a lone CR
  become LF) and drop a byte-order mark; `write_text`, `write_lines`, `append_text`, `open_write`, `open_append` write UTF-8 with
  LF on every platform. Citations are line numbers and the verbatim gate matches text, so a page saved on Windows must parse as
  one saved here (tools/platform-plan.md, Portability).
- `Note(path)`: the page parsed once (text, lines, headings, sections, tables with their rows' line numbers, the metadata table,
  citations), every accessor cached.
- `parse_note(path, root)`: the schema parse tools/build_db.py loads (tools/schema.md sections 1 to 11), and `register_rows` for
  the registers (object register, leads, relations, ties tracker).
- The forms, each named in wip/platform-phase2/inventory.md with the tools that used it before the library: rows (`cells`,
  `split_row`, `split_spaced`, `is_sep`, `is_sep_cells`, `join_row`), sections (`section_start`, `section_bounds`, `section_span`,
  `section_text`, `section_match`, `section_text_until`, `sections_text`, `split_sections`, `line_sections`, `has_section`), tables
  (`find_table`, `tables`, `loose_table`, `first_table`, `hash_table_bounds`), metadata (`meta_rows`, `meta_text`, `meta_value`,
  titles), fixed lines and cells (`QUOTE_RE`, `COUNTS_RE`, `attribution_chain`, `xc_markers`, `sort_key`, `date_key`), citations and
  links (`CITE_RE` and the other `*_RE` constants, `citations`, `cite`, `row_numbers`, `row_match`, `tl_citation_re`), and the
  staged intake's unit pointers (`UNIT_PTR_RE` and its kin), and the actor and polity register (form A, 2026-10-22:
  `actor_register` gives the pack's [actors] register page as actor rows and polity statements with their line numbers and the
  heading above each table; `cluster_names` reads the clusters page; `ActorPlacer` is the order-of-battle reading, each row's
  clusters, by code or by the actor vocabulary, and the polity its cells place). tools/build_db.py loads them into the tables
  `actors` and `polity_statements`, which tools/build_graph_data.py reads for graph-typed.json.
- Where two tools read a section or a table differently (a prefix match against an exact one; the first table against every pipe
  line of a body), both readings are kept, each under its own name: a tool's output must not change because its parsing moved
  here. Folding them into one reading is a later decision, to be measured on the corpus first.

## ledger.paths: the project, the sources/ alias table, the names of new holds

- `root()`: `$LEDGER_ROOT`, else the nearest folder holding ledger.toml, else the project this package sits in.
- `sources/aliases.tsv` (written only by `python3 ledger.py extract gate --findings --wip wip/<task> [--units A-B] [--size] [--budget R]
                                                                   gate 1 of a staged intake (tools/intake_gate.py): --size prints per unit the
                                                                   words, the item allowance, the items per section and the state; over the
                                                                   allowance without a valid `size: over budget: <section>: <n> items over <cap>
                                                                   words: <reason>` line fails (2026-10-23); --budget R the older ratio, archived only
python3 ledger.py acquire layout --write`): the layout of
  wip/platform-phase1/sources-layout.md, by media kind (sources/video, text, web, archive, sets, catalogues), resolving to where
  each held file stands today. A row per transcript (YouTube ids gain `yt-`) and a row per folder; no file is moved or renamed,
  and no symlink is made. `resolve(path, base)` and `exists(path, base)` follow the table (a path with no alias is itself; a
  lower-cased name finds the file's actual spelling on any file system); `resolve_arg` leaves a tool's argument as given when no
  alias applies, so what the tool prints is unchanged; `layout_name` is the reverse; `check_aliases` tests the table.
- New holds: `new_hold(path, kind)` is the one function every acquire tool calls before writing a held file. An existing file is
  returned unchanged (the rules bind new holds only). For a new one the name is checked against the reserved-character rule
  (`< > : " / \ | ? *`, control characters, a trailing space or dot, a Windows device name, a leading `-` or `.`) and the caps
  (stem 80, basename 96, path 180); a breaking name is replaced by `hold_name()`'s compliant form (or refused with `fix=False`, and
  always for a YouTube id, which is checked as the layout writes it, `yt-<id>`). ASCII and lower case are reported by
  `name_warnings()` and not enforced in this phase. `slug(title)` makes a slug cut at a word boundary.

## ledger.quote: spans by pointer (the compact findings form, 2026-10-23)

`span(wip, n, a, b)`, `words(wip, n, a, b, anchors)`, `locate(lines, a, b, anchors)`, `quotation_items(findings)`: the reader's
findings carry pointers and anchors, not text (tools/intake-staged.md section 3); the writer and the finisher pull the words with
`ledger quote`, and gate 1 (tools/intake_gate.py) locates the anchors with the same functions. Words match as tokens (case, curly
quotes, dashes and the punctuation between words do not count; an inline URL token and a bracketed insertion of three or more
characters are not words); a pointer's anchors are searched on its lines with two lines' slack either side, as gate 1 has always
allowed a quotation's pointer. A pointer outside its unit, a missing unit or anchors not found raise PointerError (exit 1).

## ledger.hold: where a new hold goes

`safe_slug(text, max_len=80)` (an ASCII slug cut at a word boundary) and `hold_path(kind, ident, title)` (the root-relative folder
`sources/<kind>/<name>` of a new hold, a YouTube id as `yt-<id>`, leaving room for a 32-character file name under the 180-character
path cap), on ledger.paths' caps and rules. The acquire layer (tools/ledger/acquire/, phase 3) imports these two names.

## ledger.cli: the command

```
python3 ledger.py tools                                   every tool with its layer
python3 ledger.py <layer>                                 the layer's tools
python3 ledger.py <layer> <tool> [the tool's arguments]   e.g. ledger.py build db --report; ledger.py analyse rows "spillway"
python3 ledger.py integrate <report.json> [--short L] [--archive WIP] [--run LABEL] [--no-archive] [--report-check] [--dry] [--no-present] [--with-graph]
python3 ledger.py check [--out FILE] [--notes GLOB] [--no-build]
python3 ledger.py present [--only a,b] [--skip a,b] [--with-graph] [--log DIR] [--list]   every generated page (tools/build_reports.py)
python3 ledger.py present status                                   the status page alone
python3 ledger.py file headings <path> [--all]                     the headings with their line numbers (levels 2 and 3)
python3 ledger.py file section <path> "<heading>" [--numbered]     one section (a heading prefix; "latest:<heading>" for the last)
python3 ledger.py file lines <path> <a>-<b> [--out <dst>]          a line range, printed or copied to a file
python3 ledger.py file lines <path> --count                        the line count
python3 ledger.py file copy <src> <dst>                            a byte copy (a unit to current-unit.md)
python3 ledger.py run --out <file> -- <layer> <tool> [args]        a tool's printed output saved to a file
python3 ledger.py db sql "<select ...>" [--db <path>] [--header]   the derived database, read-only
python3 ledger.py narrate unused <page> [--out FILE] [--node N] [--cap K]
                                                                   held rows bearing on each node that the page never cites, ranked
                                                                   (earlier date, document, other side, the rest; tools/narrative_unused.py)
python3 ledger.py quote --wip wip/<task> u NNN:L[-M] [u NNN:L[-M] ...] [--numbered]
                                                                   a staged intake's unit lines by pointer, verbatim, with the unit's header
python3 ledger.py quote --wip wip/<task> u NNN:L[-M] --words "<first four> ... <last four>"
                                                                   only the words between the anchors (tools/ledger/quote.py)
python3 ledger.py quote --wip wip/<task> --quotations NNN[-MMM]    a findings file's compact Quotations items, resolved to their words
python3 ledger.py sample draw|tally ...                            the sample reading (every intake, 2026-10-25): twenty claims rows by seed
                                                                   beside their spans; the reader's TSV into report.json sample_reading
                                                                   (tools/ledger/sample.py; the threshold from pack.toml [intake])
python3 ledger.py acquire layout [--write | --check | --resolve PATH ...]
python3 ledger.py acquire name PATH ... [--youtube]
python3 ledger.py acquire youtube|web|document|bulk|canon|database|transcribe ...   an adapter of tools/ledger/acquire/, its own arguments
python3 ledger.py acquire batch <list.toml> [fetch|hold|all] [--cache DIR] [--only id,id] [--list]
                                                                   a list of sources held in two stages (tools/ledger/batch.py)
```

The project served (2026-10-22): `$LEDGER_ROOT`, else the nearest folder at or above the working folder holding ledger.toml, else
the project these tools sit in. The launcher ledger.py, packload and every tool take the root this way, and a tool's own files
(the schema, a sibling tool, a template) are read beside the tool. A second project with its own ledger.toml, the pilot, a
round-trip copy or a recipient's folder, is therefore served by the same tools without a tools/ folder of its own, and nothing is
written into this one. Run `python3 <this project>/ledger.py ...` from the other project's folder, or set LEDGER_ROOT.

Layers: acquire, prepare, extract, build, analyse, narrate, present, measure, integrate, check. A tool runs as its own entry point
(runpy with run_name `__main__`, so a tool's `if __name__ == "__main__"` block calls its main), from the project root, with
sys.argv as the shell would set it; nothing is re-implemented in the command.

`integrate` runs the intake hand-back of wip/narratives-1009/RESUME.md in order and stops at the first failing step, naming it:
integrate_report, build_db --report, build_timeline, first_utterance --apply, first_utterance --narratives, source_balance
--write-kinds, divergences, the actor rows (the pack's [actors] rows_key, appended to the pack's actor register under a heading of their own, numbering
on, a row already held skipped), the speaker ledgers (the report's keys for the pack's [[speakers.ledgered]], appended to each
speaker's page: tools/ledger/speakers.py), the object register rows (applied by integrate_report; reported), wip_archive (the report's wip folder by
default), and last `ledger present` (tools/build_reports.py without the timeline, first-utterance and divergences steps, which
the hand-back has just run; the status page is regenerated last; `--with-graph` adds the map's data files, `--no-present` skips
the step). It deletes nothing. `check` runs build_db, baseline --check, note_skeleton --check and note_fill --check over every note
and writes the per-note results to wip/ledger-check/.

## Building a wheel (later)

`tools/ledger/pyproject.toml` builds the package (`python3 -m pip wheel tools/ledger --no-deps -w <dir>`); the installed `ledger`
command finds the project by `$LEDGER_ROOT` or ledger.toml and runs the project's own tools/. The tools move into the package in a
later phase.

## Tests

`python3 tools/ledger/tests/test_library.py`: the three held notes parse identically under CRLF, lone CR and a byte-order mark;
writers emit LF; the forms on a synthetic note; the actor register form on a synthetic register; the alias table; the name rules; new_hold. The corpus-wide equivalence tests of
phase 2 (the database rebuilt table by table, every rewired tool's output before and after) are in wip/platform-phase2/.
`python3 tools/ledger/tests/test_quote.py`: `ledger quote` on synthetic units (spans verbatim with the header, the pointer forms, bad
pointers, --words across a line break, --quotations). `test_intake_gate.py` covers gate 1's compact items, the item allowance and the exception line's checkable form, and gate 2's
nothing-to-row line, its parts mode and `--quotes-only` (2026-10-24); `test_assemble_parts.py` the unit-writers form's assembly step
(tools/assemble_parts.py); `test_agent_usage.py` the per-task records figure (`agent_usage.py --task --records`); `test_staged_intake_workflow.py`
runs the workflow script's dry runs (tools/workflows/tests/, node); and
`test_report_check.py` the fill-marker check, beside the cases they had. `test_basis_audit.py` (2026-10-25) covers the Basis
column and the thin-nodes axis (tools/narratives.py's parser, --check and --audit, tools/report_check.py, tools/build_db.py's
narrative_nodes) and the unused-rows check (tools/narrative_unused.py) on a fixture project.
