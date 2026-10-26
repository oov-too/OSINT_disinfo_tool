# chunk_source.py: pre-cut a held source into numbered reading units (2026-10-15)

Why: every intake agent used to split its source into reading units itself, record the boundaries in progress.md, and copy the unit in hand to `current-unit.md` before each large write (tools/agent-wip.md item 7; tools/filter-blocks.md sections 6 and 9). Profiling showed a dozen or more turns per agent spent on the splitting and bookkeeping, and an agent and its resume cut different boundaries, so a bisection after a death did not always probe what the dead agent had been reading. The orchestrator now cuts the units once, before launch; reading, resumption and bisection all work from the same numbered files.

## Usage

```
python3 tools/chunk_source.py <source file(s) | post directory | sets.json> --wip wip/<task> [--words 2500] [--by auto|page|post|heading|timestamp|words] [--set B] [--dry-run] [--force]
python3 tools/chunk_source.py --wip wip/<task> --verify
python3 tools/chunk_source.py --wip wip/<task> --status
python3 tools/chunk_source.py --wip wip/<task> --mark 007 "findings written" [--note "..."]
```

Writes `wip/<task>/units/NNN.txt` (numbered from 001 in reading order) and `wip/<task>/units/manifest.md`, then runs `--verify` itself. It refuses to run over an existing `units/manifest.md` (a running task must never be re-split; the statuses would be lost) unless `--force` is given. `--dry-run` prints the plan without writing.

## Boundaries, in order

Units break on natural boundaries, never mid-sentence. The source is split hierarchically; every unit closes at the strongest boundary available in its size window.

| strength | boundary | detected as |
|---|---|---|
| 0 | page | `--- page N ---` (pypdf and OCR extracts), `[page NN]` (one web archive's sets), `=== page N ===` and the Apple Vision OCR form `=== page-001.png` (optional hyphen, extension and trailing `===`; read as page 1), `<!-- page N -->`; the marker line opens the page |
| 0 | transcript page | the court and inquiry transcript form, read when a file has no page markers: numbered lines 1 to 25 per page and the page number alone on a line, far indented, after the page (a footer, the next page opening with a form feed, as the inquiry's transcripts print it) or before it (a header); accepted only when the page numbers run in order and four pages in five carry a run of numbered lines 1, 2, 3 ... of at least ten. Spans read `transcript pages 12-22 (12:1 to 22:25)`, the transcript's own page:line (2026-10-22) |
| 0 | post | one file per post: a directory of `.txt` posts in name order, or the files a `sets.json` key lists (`--set A`, `--set B`; a blog batch's shape `[date, title, url, file, words]`) |
| 1 | markdown heading | `# ` to `###### ` lines |
| 2 | transcript timestamp | `**[h:mm:ss]**`, `[h:mm:ss]` or a bare `h:mm:ss` at the start of a line (the transcripts/ form); a block runs to the next stamp |
| 2 | capitalised section line | an all-capitals line after a blank line (`FOREWORD`, `SEARCH STRATEGY AND METHODOLOGY`), used only where a stretch has no page markers and no timestamps, as in the OCR of an agency report with its attachments; speaker tags like `PV:` are excluded |
| 3 | paragraph | blank-line separated blocks (the blank lines stay with the block before) |
| 4 | sentence | only inside a paragraph longer than the ceiling: cut after `.`, `!`, `?` and a closing quote or bracket |
| 5 | word | last resort, only for a single sentence longer than the ceiling; the span says `forced mid-sentence cut` |

`--words` is the target unit size (default 2,500); the hard ceiling is 1.5x (`--ceiling` overrides it). Packing: leaves (paragraphs, timestamp blocks, or sentences where a paragraph is over the ceiling) are taken in order; once the unit holds 0.6x the target, the script looks ahead to every close point up to the ceiling and closes at the strongest boundary, nearest the target on ties. A remainder of 1.25x the target or less becomes the last unit whole. Pages, posts and timestamp blocks are therefore kept whole wherever they fit; a 3,000-word page is one unit on its own; a 5,000-word post is cut at paragraph ends and its parts are marked `beginning`, `middle`, `end`.

`--by` forces the top level: `page`, `post`, `heading`, `timestamp` or `words` (paragraphs and sentences only). Where a forced level has no markers in a file the manifest says so and the finer boundaries apply. `auto` (default) tries page markers, then headings, timestamps, capitalised section lines, paragraphs.

In `--by post` mode (or whenever a `sets.json` key is given) a unit may hold two or more short posts in sequence; each post inside the unit opens with its own header line (`[unit NNN/MMM continues] source: ...`). In every other mode a unit never spans two source files.

## The unit file

Line 1 is the header; everything after it is the exact source text of the unit, byte for byte, so `--verify` can rebuild the source and a probe can print lines of it (`python3 -c "import sys; L = open(sys.argv[1], encoding='utf-8').read().split('\n'); print('\n'.join(L[int(sys.argv[2]) - 1:int(sys.argv[3])]))" <unit> <a> <b>`; interim form; `ledger file lines` to build). An illustrative header, on a source of the example casebook (tools/example-casebook.md):

```
[unit 003/032] source: books/sources/web/harrowmere-2018/report-on-the-harrowmere-event.txt | span: pages 7-9, lines 180-312 | words: 2431
```

Span forms: `pages 7-9` (with `starts mid-page` / `ends mid-page` where a long page was cut), `post "Title" (2020-03-18)` (with `beginning` / `middle` / `end` for a cut post), `00:15:44-00:30:17` (the first and last stamps in the unit; `header, then ...` for the transcript's metadata block; `..., then "Video description (...)"` where the description section closes the unit), `from "HEADING A" to "HEADING B"` or `under "HEADING"` for the heading context, and always `lines a-b` in the source file. A citation can be written from the unit alone: source file, page or stamp or post, line.

Line numbers for bisection: probe line L of a unit file is source line `a + L - 2` (line 1 is the header; the span's `lines a-b` gives `a`).

## The manifest

`units/manifest.md` opens with totals (sources, words, lines, split basis per file, unit count, target, ceiling, largest, smallest, mean; a line when a file has no page markers and no headings and the fallback was used) and the standing instruction to read in order and copy the unit in hand to `current-unit.md` (the tool still prints that instruction as a `cp` command until phase 2 changes it to the portable copy form; wip/platform-phase4/handoffs.md), then one table:

| unit | source | span | words | status | notes |
|---|---|---|---|---|---|

The reading agent fills `status`: blank = unread; `read`; `findings written` (the unit's findings are in `parts/findings.md`); `rowed` (its rows are in the note). `notes` is free text (a block, a cross-reference, "skipped: duplicate of unit 004"). `--mark NNN <status> [--note "..."]` writes a cell by command, which is less error-prone than editing the table; `--status` lists the units whose status is not `findings written` or `rowed` and names the first one as the resume point, with its file path.

## Verify

`--verify` reads every unit file under `wip/<task>/units/`, strips the header lines, concatenates the parts per source file and compares them to the source byte for byte; it also checks each header's word count against its body. It prints a line per source (up to six) and the count: `verify: 31 units, 1 source file(s): OK, units concatenate back to the source exactly`. It exits 2 on any mismatch, naming the first differing character and source line. The build runs it automatically.

## How the units are used (tools/agent-wip.md item 7, tools/filter-blocks.md sections 6, 7 and 9)

1. The orchestrator runs `chunk_source.py` for each task before launch, so `wip/<task>/units/manifest.md` exists when the agent starts; the brief says: "Units are pre-cut: read `wip/<task>/units/` in manifest order, mark each unit's status in manifest.md as you go, and copy the unit in hand to `current-unit.md` by the copy operation (plugin/templates/briefs/operations.md); never re-split." (the brief templates' wording; the live briefs of 2026-10-15 said "by `cp`")
2. The agent reads `units/001.txt`, `002.txt`, ... in order, writes findings per unit to `parts/findings.md` under the unit number, marks the status, and before each large output runs `python3 -c "import shutil; shutil.copyfile('wip/<task>/units/NNN.txt', 'wip/<task>/current-unit.md')"` (interim form; `ledger file copy` to build) with one line in progress.md naming the unit number and where its output goes.
3. A resumed agent runs `--status` and continues from the first unit without findings; the boundaries are the same ones the dead agent read.
4. After a death past the last resume, `tools/workflows/guarded-intake.js` probes `wip/<task>/current-unit.md` with `bisect-block`, which is now one of the numbered units; the capture's source location is read from the unit header (file, span, start line) and the probe's line range translated by `a + L - 2`. If the agent did not copy a unit, the manifest's first unit without findings is the one to probe.

## Tests (2026-10-15, wip/chunk-test/)

| source | basis found | units | words | largest | smallest | mean | verify |
|---|---|---|---|---|---|---|---|
| a government audit report held as text (one `.txt` file) | 26 page markers | 2 | 3,468 | 2,353 | 1,115 | 1,734 | exact |
| the OCR text of an agency report of 1995 with its attachments 1 to 31 (part A of a two-part release; one `.txt` file) | no page markers and no markdown headings in that OCR; 628 capitalised section lines used as weak boundaries, paragraphs otherwise | 31 | 77,652 | 3,491 | 1,524 | 2,505 | exact |
| a blog batch's post directory, `--by post --set B` | 36 posts from sets.json key B; 2 posts over the ceiling (an interview transcript posted 2019-12-12, 5,205 words; a post of 2020-10-30 on an investigators' case database, 4,308 words) cut at paragraph ends; 10 units hold two posts | 23 | 55,889 | 3,200 | 1,584 | 2,430 | exact (36 files) |
| a 4h55m two-person interview transcript (`transcripts/<id>.md`) | 417 timestamp lines, 2 headings | 21 | 52,136 | 2,506 | 2,461 | 2,483 | exact |

Also checked: `[page NN]` markers (one web archive's set, 41 pages, 4 units, exact); `--by page` on a file without markers (says so, falls back); `--by words --words 600` on the audit-report text (6 units; a one-paragraph page over the ceiling cut at sentence ends, span flagged `ends mid-line`); `--mark`, `--status`, the refusal to re-split without `--force`.

## Limits

- Word counts are whitespace-token counts (`len(text.split())`), the same measure the transcripts' headers use approximately.
- Capitalised section lines are a weak signal in OCR (letterheads and form fields match too); they only decide where a unit may close, never what it contains.
- A post set is read from `sets.json` by key; a directory without one takes every `.txt` in name order. Post titles and dates come from the set entry, else from the file's `# Title` and `Published:` lines.
- A unit never crosses a source file whose text does not end in a newline (exactness over packing).
- Statuses other than the four standard values are kept and listed by `--status` as non-standard.
