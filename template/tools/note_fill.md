# tools/note_fill.py: the mechanical parts of a note, generated (2026-10-15)

## Why

Four parts of every note in the house schema are mechanical and were typed by Opus agents and then re-read to verify: the metadata block's derivable keys (Length, Transcript, Added to notes, URL, Uploaded, Recorded), the document inventory table, the audit counts line under the forthrightness audit, and the cross-check table's mechanical cells (which row of this note, which row elsewhere, the custody of the row elsewhere). Each costs tokens twice and is wrong often enough to matter (one document-set note's hand table counts the issuer's pages, pypdf counts PDF pages, and the two differ by the cover sheet a document archive added to every file). The owner's rule: generate them, keep the judgement cells for the agent, and check before the report goes back.

Pairs with `tools/note_skeleton.py`, which writes the skeleton the agent works from: the skeleton fills the derivable metadata cells once from the held files; `note_fill.py` fills them when they are empty, compares them when they are filled, and generates the three blocks the skeleton cannot (inventory, counts, cross-check candidates). Run `note_fill.py` on the skeleton (`wip/<task>/skeleton.md`) or on the finished note (`books/<note>.md`); the relative links are written for the note's destination folder either way.

## Usage

```
python3 tools/note_fill.py --note <books/<note>.md or wip/<task>/skeleton.md> --sources <held dir or files ...> \
        [--readme README.md] [--onboard wip/<task>/onboard.md] [--accept wip/<task>/xc-accept.md] \
        [--dest-dir books] [--inventory-under "<heading>"] [--recursive] [--force] [--reset-xc] [--dry-run]

python3 tools/note_fill.py --check <note> [--sources ...] [--readme ...] [--report wip/<task>/report.json]
```

Fill mode writes the note in place and prints one line per decision: `WROTE` (generated and written), `KEPT` (set by hand, left as is, generated value shown), `OK` (agrees), `DIFF` (disagrees, or empty and not derivable), `HINT` (what the sources and README gave, for the agent's explanatory lines). Check mode writes nothing, prints the same lines, and exits 1 when any `DIFF` remains, so it can gate `tools/report_check.py`.

`--sources` takes held folders and files in any mix (a batch folder `books/sources/web/<batch>`; the three files of one essay pair; a forum thread's files plus `<forum>/cited`, `<archive>`, `<archive>/cited`). A folder is read one level deep unless `--recursive`. `README.md`, `INDEX.md` and hidden files are skipped. The README used for dates and URLs is `--readme`, else `README.md` in each source folder, its parent and its grandparent (the batch README `books/sources/web/<batch>/README.md` covers its subfolders), stopping at `books/sources`.

`--dest-dir` is the folder the note will live in, for relative links; it defaults to the note's own folder when the note is under `books/` or `videos/`, else `books/` (a skeleton in `wip/`).

## What it generates

### (a) Metadata, derivable keys

| Key | Generated from | Form |
|---|---|---|
| Length | pypdf page counts over the PDFs; whitespace word counts over the `.txt` and `.md` text layers | `63 PDF pages in 2 held files, 58,220 words in the text layers (<title>: 4 pages, 1,458 words; ...)`; `N words in K held texts (...); no PDF held` for web texts |
| Transcript | the held files | `Source files: [<title or stem>](<rel .txt>) (and [the pdf](<rel .pdf>)); ...; provenance in [<batch> README](<rel>)`; over eight documents it links the folders and three examples and points to the inventory |
| Added to notes | today | `YYYY-MM-DD`, only when empty |
| URL | the README table's URL column for the matched rows | up to three URLs joined by `; `, then `(and N more, in the inventory)` |
| Uploaded | the README table's Published or Release column | the earliest, `YYYY-MM-DD` |
| Recorded | the README table's Date or Document date column, every date in the cells | `YYYY-MM-DD to YYYY-MM-DD [the documents' own dates, from the README beside the files]` |

A derivable key that is empty (or holds `<!-- fill -->`) is written; one already filled is kept and compared (`KEPT`, with the generated value shown, or `OK` when they agree); `--force` overwrites. Length is compared on its figures: the cell agrees when its first `N pages` / `N words` figure, its largest, or the sum of all of them matches the files (words within 5 percent). Transcript is checked for every held document being linked by file name or folder, and for every relative link resolving from the destination folder (this is how an adverse-forum note's dead link to a held HTML analysis surfaced: the file is one folder deeper, in the archive's subfolder). The judgement keys (Channel, Host, Guest, Speakers, Subjects, Description, Tags, Authors) are never touched when filled and are marked `<!-- fill -->` when empty.

README tables are read by their header words, so the batch READMEs' differing shapes all work: `File | Document | Date | Pages | Bytes` (a batch of released papers), `ID | Title | Document date | Pages | Size | URL` (an official release batch), `Published | Title | Words | File | URL` (a blog batch), `File | What | Pages / words | Size | Source URL | Original issuer` (a batch of reports and attachments). A row matches a document when a cell equals one of its file names, an `ID` cell is a prefix of the file stem (`HI-114`), or a cell equals the stem. Where the README has no table (one adverse batch's), a prose or bullet line naming the file or stem supplies a URL and an ISO date (the README's `## Dates` bullets), and failing that the `## <folder>/` section's URL is used in the inventory only, marked `(the folder's URL in the README; not per file)`, never in the metadata URL key.

### (b) Document inventory

Between `<!-- inventory:start -->` and `<!-- inventory:end -->`, directly under `## How the set is built` (else `## The documents, one by one`, else `--inventory-under`): one row per held document, a document being the `.pdf` and the `.txt`, `.md` or `.html` of the same stem in the same folder.

`| # | Document | Held files | Pages | Words | Bytes | Document date | URL |` and a total row. Document is the README's title or the stem; Pages is pypdf's count (`n/a` when no PDF; `? (pypdf could not read it)` on failure; `(README says N)` appended when the README's Pages column disagrees); Words counts `.txt` and `.md` only (an `.html` raw copy is listed with its bytes); the date comes from the README, else from a date in the file name marked `(from the file name)`, else `<!-- fill -->`; the URL from the README, else `<!-- fill -->`. Re-running replaces only the block. The hand-written table of the section ("How the set is built", with its What it gives and Claims columns) is judgement and stays; check mode compares its rows to the files (a row is matched by a file name, the stem, or an ID such as `HI-114` or `Day 12` against the stem) and reports Pages cells that differ, rows it cannot match, and held documents the table does not name.

`tools/build_db.py` never reads these sections, so the generated table cannot shadow a schema table.

### (c) Audit counts

Between `<!-- audit-counts:start -->` and `<!-- audit-counts:end -->`, directly after the audit table: the schema section 3 line in its exact form, computed from the table.

- The four move counts come from the Move cell; a compound move (`open on content, closed-outright on identities`) counts its first class, as the parser does; `n/a` rows are not counted and their number is printed.
- Stated declines (rule of 2026-10-22) are the rows whose Basis names something (not `n/a`, not `none stated` even with a parenthesis after it, not `not known ...`, not blank, not a wall) and that are a refusal: the Move is closed-outright (the schema's mapping: a refusal with a ground given), or the Note says the row is a decline (`stated decline`, `X's decline`, `declines on ...`; not `pseudo-decline`, not `not counted as a decline`), or the Basis names a ground of the basis vocabulary (the pack's [audit] basis_vocabulary; inflections and up to two words inside a phrase match, `classified`, `pending IG reprisal investigation`), on any move (a decline delivered inside another answer). A Basis that is only sourcing (a monologue's `His own reasoning`, a book title, `public record`) on an open, partial or closed-subtle row is never a ground: the earlier rule counted any named Basis, which put 204 stated declines on a monologue whose hand line says 4 (2026-10-22: 85 notes disagreed with their hand lines before the change, 55 after, none by more than 5; wip/platform-phase2/followup3/audit/). A row carrying two refusals counts once here; the schema counts refusals, so where a note's author counted a row twice the line will differ by that much, and the explanatory line should say which rows carry more than one.
- Walls are the rows whose Basis begins `redacted:` or names a sanitisation at release; they are reported with their row numbers and never counted as stated declines. (This reproduces all six finished document notes' hand lines exactly, the primary document exemplar included, where three `classification (sanitisation at release)` rows are walls and five grounded refusals are the stated declines.)
- Pseudo-declines are the rows whose Note cell says `pseudo-decline`, not preceded by `not a` or `no`.

The `HINT audit:` line prints the row count, the n/a rows, the walls and the full Basis histogram, which is what the explanatory line under the counts line is written from. A hand line that disagrees is reported (`DIFF`) and kept unless `--force`; a skeleton placeholder (`open N, partial N ...`) is replaced. `tools/retired/audit_counts.py (retired 2026-10-22; the counts line is generated by tools/note_fill.py)`'s `Source counts (class audit):` line, written after the counts line, lands inside the block and is preserved.

### (d) Cross-check candidates

`--onboard wip/<task>/onboard.md` parses `tools/onboard_check.py`'s report (parts A, B and C) into candidates with stable ids: `A3` (a standing question or lead), `B12.2` (the second row of the twelfth B entry: one candidate per pair), `C1` (a decline). Each becomes a row in the schema section 10 shape:

- This note: the time, row number and clipped claim of the best-matching ledger row (`(also rows ...)` for the others);
- Elsewhere: a link to the other note or the leads register with the short title as link text, then `claims N`, `open question N`, `lead N` or `audit N`;
- Note: the custody of the row elsewhere as the report gives it (`custody: <class>; <attribution; chain>`), the other row's time, speaker and claim for B, what would settle it for A, the decline's basis, answer and sweep status for C, then `candidate <id> (<shared terms>); likely <kind>` and `<!-- fill -->`;
- Kind and Verdict: `<!-- fill -->`.

The block `<!-- cross-checks:start onboard=<hash> ... -->` ... `<!-- cross-checks:end -->` holds the section's single table, because `tools/build_db.py` reads the first schema-shaped table under the heading: a hand table already in the section is moved into the block unchanged, its rows keep their numbers, and generated rows take the next integers. Rows inside the block are never edited or deleted by a re-run; a re-run appends only candidates whose Elsewhere target is not yet in the table, and does nothing when the onboard report is unchanged (its hash is in the start marker). `--reset-xc` drops the generated rows still wholly unfilled and regenerates. The lead-in paragraph above the table ("From the onboarding check ...") is prose and is left alone.

**The --accept file is the intended path.** Without it every candidate is written (223 for a note on a 2008 contract's statement of objectives and order, 227 for a note on two magazine articles), which is a worksheet, not a table. The agent reads the onboard report and both sides of each candidate it keeps, as schema section 10 requires, then writes `wip/<task>/xc-accept.md`, one line per kept candidate:

```
# id  kind  verdict  | note text (point marker, direction, applied/proposed, div tag)
A3    answers   partial | point: substance; proposed: checked
B12.2 contradicts direct | point: date; 2008 against 2011 [div: dir=self; core=periphery; stab=?; indep=yes; timing=first; path=document]
C1    fills     direct  |
```

and runs the fill with `--accept`: only those rows are written, Kind and Verdict filled, the note text placed first in the Note cell, the generated custody and candidate id after it. Candidates already present (by Elsewhere target) are skipped and named. `tools/build_db.py` reports rows whose Kind or Verdict is still `<!-- fill -->` (`Kind or Verdict not in schema section 10`), and `--check` counts every `<!-- fill -->` left in the note.

## Check mode and report.json

`--check <note>` recomputes (a) to (c) with the same `--sources` and `--readme` and reports every difference: Length against the files, Transcript links against the files and the disk, the hand inventory table and the generated block against the files, the audit counts line against the audit table, `<!-- fill -->` markers anywhere. `--report wip/<task>/report.json` adds: `claims_rows` against the Claims ledger's row count, `timeline_rows` against the Dated timeline's, `audit_rows` against the audit table's where present, `audit_counts` against the computed line (with or without the `Audit counts:` prefix and the final period), `words` against the note's whitespace word count, and `file` against the note's name. Exit 1 on any `DIFF`; run it before `python3 tools/report_check.py`.

## Run on the five finished notes (2026-10-15, nothing changed in them)

| Note | Length | Inventory (hand table vs files) | Audit counts | report.json |
|---|---|---|---|---|
| a document-set note on 37 released research papers and their release letter (2009 to 2011) | 1,497 PDF pages stated for the papers plus the letter's 5 against 1,502 PDF pages held: agrees once the letter is added; the cell's own figures (1,497; 1,473 issuer's count; 11 missing; 5) are not summable | all 37 rows differ by exactly one page: the table counts the issuer's pages, pypdf counts PDF pages, and the archive's cover sheet is PDF page 2 of every file (the note says so in its Length cell); the release letter (cited by its FOIA case number) is not in the table | agrees (6, 1, 41, 11, 4, 0); 37 walls on rows 1 to 37, declines on rows 41, 42, 43, 49 | claims 109, timeline 52, counts: all agree |
| a note on a 2008 contract's statement of objectives and order (two released documents) | 63 pages agree; the cell gives words for the first document only (1,460) and tokens for the second, so no word total to compare with the files' 58,220 | rows 1 and 2 (4 and 59 pages) agree; rows 3 to 6 are read-beside documents held outside the folder | agrees (7, 0, 8, 10, 0, 0); 10 walls, no stated decline | claims 142, timeline 24, counts: all agree |
| an adverse-web note on two magazine articles (1952 and 1956) | 20 pages, 21,305 words: agree | no hand table with a # column (the section is prose) | agrees (5, 4, 8, 14, 9, 0); the 9 declines are rows 4, 5, 7, 9, 11, 15, 18, 20, 30 | claims 177, timeline 51, counts: all agree |
| an adverse-web note on two sceptical essays on one blog (2025) | 23,045 + 11,507 words agree with the files' 34,725 within the tolerance (a notice on the blog adds about 170) | the hand table is a section map, not a document table | agrees (15, 9, 2, 14, 2, 0); declines on rows 4 and 16 | claims 212, timeline 109, counts: all agree |
| an adverse-forum note on a forum thread and an archive's analysis of a leaked document (2020 to 2024) | the cell counts post text and the posters' own words (11,400; 6,500); the files' text layers total 48,695 words including the batch copy and the cited texts: not comparable, reported | the batch copy of the thread (`<thread>-<number>.md`) and the page's HTML are not in the hand table | agrees (11, 0, 3, 23, 3, 0); declines on rows 17, 23, 28 | claims 140, timeline 33, counts: all agree |

One defect found: the adverse-forum note's Transcript cell links `sources/web/<batch>/<analysis>.html`, and the file is at `sources/web/<batch>/<archive>/<analysis>.html`. Not corrected here (the five notes were not to be changed); a one-line fix for the owner or the next pass over that note.

None of the five has the generated blocks yet; fill mode would insert the inventory under `## How the set is built`, wrap the (agreeing) counts line in markers, and move each note's cross-check table into the block without changing a row. The archived wip folders under `research/tasks/tool-feedback/` hold their onboard.md and report.json, so the `--report` comparison above used the real reports.

## Tested

On scratch copies: fill on the statement-of-objectives note with `--onboard` (the archived report, 223 candidates) and a four-line `--accept` file: the 42 hand rows moved into the block unchanged, four candidate rows appended as 43 to 46, a second run changed nothing (`UNCHANGED`), and `tools/build_db.py`'s parser read the result as 15 metadata keys, counts `[7, 0, 8, 10, 0, 0]`, 46 cross-check rows, 142 claims, 25 audit rows, 24 timeline rows, with no report lines. On a bare skeleton with empty cells: every judgement key marked `<!-- fill -->`, Length and Transcript and Added to notes written, the inventory inserted, the counts line written after the table (the explanatory line left in place), 227 candidates of the magazine-articles note written without `--accept`. On `tools/note_skeleton.py`'s own document skeleton for the magazine-articles note's sources: the skeleton's Length and Transcript agreed and were kept, the inventory was inserted, the placeholder counts line was replaced and wrapped.

## Known limits

- Stated declines are counted as rows, not refusals (schema section 3 counts refusals); where a row carries two, the hand line is right and the tool reports a difference of one, which the explanatory line should already explain.
- A README with no table and no line naming the file gives no date or URL; the inventory cell takes `<!-- fill -->` and the metadata URL, Uploaded and Recorded stay for the agent, with the folder-level URL and PDF CreationDate values printed as hints.
- Words are whitespace tokens of the whole text layer (OCR noise and gutter fragments included, as the magazine-articles note's cell says); a cell that counts something narrower (the posters' own words) will always differ and is reported, not overwritten.
- Pages are PDF pages. A note whose convention is the issuer's own pagination (the 37 released papers above, the issuer's pages without the cover sheet) will differ by the cover sheets; the check reports it and the note's Length cell should state the convention, as that note does.
- The cross-check candidate parser depends on `tools/onboard_check.py`'s current heading forms (`### A1. <where> #<n> [status]...`, `### B1. This note #<n> (...)`, `### C1. <file> audit <n> (...)`); a change there needs a change in `parse_onboard`.
