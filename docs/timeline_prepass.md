# tools/timeline_prepass.py: the date-keyed pre-pass for the Dated timeline

Added 2026-10-15. An intake agent rules every Dated timeline row's Agreement cell (schema section 11: `matches`, `drifts`, `contradicts`, `new`) against the rows the database already holds for that date. Until now it found those rows by searching per date, dozens of turns per note. This tool does the search once, for every date the source carries, and writes one list the agent rules from: `wip/<task>/timeline-candidates.md`.

It is the date-keyed complement of `tools/context_pack.py`, which is name-keyed (people, documents, identifiers, register clusters, narrative rows, leads). context_pack lists the rows that mention a source's dates as terms; this tool resolves every date expression to a precision and a span, matches held rows by date arithmetic, ranks them against the sentence, and adds what the agent needs to write the row (the era page, the decimal ID). Shared code is imported, not copied: `rows_search.search()` for the FTS5 ranking, `timeline_insert.sort_key()`, `between()` and `fmt()` for the IDs, `source_balance.guess()` for a stem research/source-kinds.md does not list yet.

Standing rule (wip/intake-1008/brief-document.next.md, tools/schema.md section 11): rule the Dated timeline's Agreement column from `wip/<task>/timeline-candidates.md`; search beyond it only for a date it marks as having no held row. Reading each cited row in its own note before entering it stays the rule; the list locates rows, it does not read them for you.

## Command line

```
python3 tools/timeline_prepass.py <source file(s) or units dir> --wip wip/<task> [--window 1] [--year-window 0] [--cap 4]
                                  [--coarse-inline] [--budget-words 30000]
                                  [--note <stem>] [--exclude-note <stem>] [--source-date YYYY-MM-DD] [--db notes.db] [--summary]
```

- Sources: transcripts (`transcripts/<id>.md`; the header before the first `---` is metadata, its `Uploaded:` the source date), held texts (`books/sources/...`; a `--- page N ---` marker gives the page), or a `units/` directory written by `tools/chunk_source.py` (the manifest is skipped, each unit's header line is metadata, locations are the unit's own line numbers). Several sources may be given.
- `--window` days either side of a full date (default 1); `--year-window` years either side of a year-only date (default 0); `--cap` candidates printed per date (default 4; the rest go to the overflow file). These defaults (2026-10-22) are the settings a blog batch of 2026-10-15 was given by hand after the earlier defaults (3, 1, 25) gave files of about 209,000 words.
- Dates at year, decade, century, range or approximate precision go to `timeline-candidates-coarse.md` (same form, same section numbers), with a one-line pointer in the main file; `--coarse-inline` keeps them in the main file. A coarse date rarely decides an Agreement cell on its own; the full dates and month-years are read first.
- `--budget-words N` (default 30000): the Budget line under the Summary gives the main file's words against N and names the date sections over an equal share of it, with the flags that narrow it. It is reported, never enforced.
- `--note <stem>`: the held note the rows will go into (a revision in place, a retrofit). The ID line then gives the decimal ID `tools/timeline_insert.py` would assign, computed from the note's rows in notes.db by the same rules (verified against `timeline_insert.py --dry` on five dates of a held video note with 95 timeline rows, the note of the third test run below: 13.1, 48.1, 1.1, 95, 2.1). Without it the note is new and the ID line gives the row's position among the dates found, in date order.
- `--exclude-note <stem>`: leave one note's rows out of the candidates (testing the tool on a source whose note is already held).
- `--source-date`: the date of the source itself, the anchor for "N years ago" and bare two-digit years; default the header's `Recorded:`/`Published:`/`Uploaded:` line, else the first full date in the first 60 lines, else today. The header of the output says which.
- `--summary`: print the Summary line only, write nothing.
- Reads notes.db read-only (the `timeline` and `videos` tables, the `rows_fts` index). Writes only `<wip>/timeline-candidates.md`, `<wip>/timeline-candidates-coarse.md` (removed when there is no coarse date or with `--coarse-inline`) and `<wip>/timeline-candidates-overflow.md` (removed if nothing overflows).

## What is extracted

Every date expression, with the location (transcript stamp `[h:mm:ss]`, `page P, line L`, or `line L`), the surrounding sentence trimmed to about 200 characters around the match, and a precision. Specific forms are matched first and a later pattern never matches inside an earlier match, so "March 14, 2017" is one day-precision hit, not also a month and a year.

| precision | forms matched | Sortable written | matched against held rows |
|---|---|---|---|
| day | `2017-03-14`; `14 March 2017`, `14th of March, 2017`, `14 Mar 2017`; `March 14, 2017`, `Sept. 29 2017`; `3/14/17`, `3/14/2017`, `3-14-2017` (US month/day/year assumed, said in the Reading line); `9/11` | `2017-03-14` | rows whose span intersects ±`--window` days |
| month | `2017-03`; `March 2017`, `March of 2017`, `Mar. 2017` | `2017-03` | rows in the same month |
| year | `2017`; `'93`, `'94-ish`; `in 93` (1900s assumed, said); `FY09`, `fiscal year 2025` (October to September, said); `eighteen eighty-eight`, `two thousand and five` | `2017` | rows within ±`--year-window` years |
| decade | `the 1950s`, `1950's`, `the '50s`, `the fifties` (1900s assumed), with `early` (0 to 3), `mid` (4 to 6), `late` (7 to 9) | `1950..1959`, `~1950..1953` | rows whose span intersects the decade |
| century | `18th century`, `1st century BC` | `1701..1800` | rows whose span intersects |
| range | `2019 to 2021`, `2019-21`, `1992–1994`, `between 1992 and 1994`, `from 1992 through 1995`, `1 October 2019 - 30 September 2020` | `2019..2021` | rows whose span intersects |
| approx | `3,000 BC`; `5,000 years ago`, `two thousand years ago`, `two hundred thousand years ago` (from the source date; spelled counts read with their hundreds and thousands since 2026-10-22, when "two thousand years ago" had been read as two years) | `~-3000` | rows within a tenth of the distance (`3,000 BC`: ±300 years) |
| relative | `the next day`, `the following day/week/month/year`, `the day after`, `the day before`, `six years later`, `two weeks after`, `a year earlier`, `that same year`, `later that day`, `that night` | the anchor's date shifted | at the resolved precision |
| day without a year | `March 15`, `the 14th of March` | the year of the nearest earlier dated hit | as a day |

Relative forms and days without a year take their anchor from the nearest earlier dated expression in the same unit (800 characters back for a relative phrase, 1,500 for a day-month); the Reading line and the occurrence say which anchor and the shift (`relative (The following day) to "March 14, 2017", +1 day`). A shift the anchor cannot carry ("30 days after" an anchor of "June 2015") keeps the anchor's precision and says so. A relative phrase with no anchor, or a day-month with no year in reach, is listed at the end under "Unresolved date expressions (no anchor)" with its sentence; nothing is dropped. "The day after Harrowmere" (a proper noun after "the day after") is an event reference and is not treated as a date.

Not treated as years: four-digit numbers followed by a unit (feet, pounds, hours, people, pages), preceded by `$`, `#`, a page marker, `Room`, `Suite`, `Box`, `No.`, `Form`, `Section`, or standing inside a URL, a transcript stamp or an identifier (`DC-0917`). A bare "about 1000" in a transcript still comes through as a year and is for the agent to judge from its sentence.

## Matching, ranking, the echo signal

The held rows are the `timeline` table of notes.db (10,316 rows on 2026-10-15; 388 with Sortable `?` cannot be matched by date and are counted in the header). Each row's Sortable is read as a span (`2017-03` is 2017-03-00 to 2017-03-31; `1992..2004` is the whole range; `~` is approximate), and a row is a candidate when its span intersects the source date's query span. Candidates are tiered: 0 the row speaks at the source's precision or closer (a day row for a day date; any row in the year for a year date), 1 one step coarser or a neighbouring year, 2 coarser still (a year-only row for a day date), 3 a held span far wider than the date (a century, "the 40s onward") which merely contains it.

Within a date the candidates are ranked by keyword overlap with the source sentence: each distinct keyword the event (or speaker cell) shares with the sentence scores 1, a rare word or a figure scores 3, plus a closeness bonus of 6 for tier 0, 3 for tier 1, 0 for tier 2 and -3 for tier 3; ties are broken by `rows_search.search()`'s bm25 rank for the sentence's keywords over the same span, then by date. Keywords are the sentence's tokens minus stop words and the date's own tokens, taken per occurrence, so a date the source states thirty times does not match everything. A rare word is one that occurs in the event text of at most three held notes; a figure is any token with digits (`0917`, `$10`) that is not part of the date. Rows that share one are marked `echo: 0917, pernell`: the echo signal (tools/echoes.py; the same rare detail across unlinked mouths is corroboration, the same wording across linked mouths is an echo), to be judged for independence before it counts. Rows with ordinary shared keywords show `shared: wall, water`.

## The output

`wip/<task>/timeline-candidates.md`:

1. The Summary line: date expressions by precision (and how many relative forms and day-month forms were anchored, how many are unanchored), distinct dates, candidate rows (and how many at the source's precision), dates with no held row, dates held only at a coarser precision or a neighbouring year, candidates beyond the cap.
2. A header: the command, notes.db's build time and row counts, the source date and its basis, the windows used; then how to read the sections.
3. One section per distinct date, in source order of first occurrence: `## 4. 2017-03-14 (day) — first stated as "March 14, 2017"`, then
   - `Stated forms:` every wording with its count; `Reading:` the notes the extraction made (assumed order, inferred year, the relative anchor);
   - `Era page:` the consolidated era page the date falls in (the era ids, boundaries and pages are the active pack's: {{pack.eras}}, the active pack's pack.toml `[eras]`; a range spanning two eras lists both);
   - `Master neighbours outside the window:` the nearest held rows before and after the query span, so the row's place in the master timeline is visible;
   - `ID:` with `--note`, the decimal ID timeline_insert.py would give and the gap it falls in (`tl 13.1 (between tl 13 and tl 14)`; a second row in the same gap takes the next free decimal); without it, `row N of M in date order` (the rule is stated once in the header);
   - `Occurrences (N in U units; one line per unit):` per unit, the first `unit location: "sentence"` that states the date, with the anchor note for relative forms, then where else in the unit it recurs (`and 3 more in this unit: line 40, line 77, line 102`);
   - `Candidates (shown of total; tier counts):` one line per row: `[<stem> tl N] | date as stated (Sortable) | speaker, basis | event (180 characters) | kind: <source kind> | <agreement kind> | div: [div: ...] | echo: ...`. The kind is the note's row on research/source-kinds.md, or `source_balance.guess()`'s with `(guessed)`. `div:` carries the held row's own divergence tags, so an already-ruled contradiction is visible before the agent rules again.
4. `## Dates with no held row`: the `new` candidates, listed again with their sentences (still check the claims ledgers with tools/rows_search.py before ruling `new`: a claims row may hold the event without a timeline row).
5. `## Dates held only at a coarser precision or a neighbouring year`: the event may be held under a looser date.
6. `## Unresolved date expressions (no anchor)`.

`wip/<task>/timeline-candidates-coarse.md`: the coarse dates' sections, in the same form and numbering. The main file's `## Coarse dates` line points to it; the lists of dates with no held row and of dates held only at a coarser precision cover both files and mark the coarse ones `(coarse file)`.

`wip/<task>/timeline-candidates-overflow.md`, when a date has more than `--cap` candidates: candidates `cap + 1` to `5 × cap` in the same form, the rest in index form (citation, Sortable, the event's first 80 characters, kind, agreement kind, tier, echo). Nothing is dropped; a year-only date in a heavily covered year, or a range like "2009 to 2021", legitimately has hundreds or thousands of held rows, and they are all there.

## Test runs, 2026-10-15 (outputs under wip/timeline-prepass-test/)

| source | expressions | distinct dates | candidates (at precision) | no held row | overflow |
|---|---|---|---|---|---|
| a government audit report held as text (3,468 words, 26 page markers) | 86 (day 14, month 45, year 13, range 12, decade 2; 2 relative anchored, 2 day-month given a year) | 35 | 13,206 (7,543) | 0 (2 coarser only) | 12,331 |
| a researcher's blog post setting out a programme's timeline, held as text (755 words) | 61 (day 30, month 21, year 10) | 45 | 10,740 (1,107) | 0 (8 coarser only) | 9,615 |
| a video transcript of a narrated timeline (about 2h44m and 24,105 words, 262 year mentions; its note already held, 95 timeline rows) | 244 (year 146, range 43, month 27, decade 15, day 7, century 4, approx 1; 4 relative anchored, 1 unanchored) | 108 | 51,649 (32,618) | 0 | 48,962 |
| the same transcript with `--exclude-note <its note's stem>` | 244 | 108 | 50,800 (32,058) | 0 (5 coarser only) | 48,113 |
| the audit report as two chunk_source units (a `units/` directory) | 86 | 35 | 13,206 | 0 | 12,331 (identical to the file run; locations are unit and line) |

Spot-checks by eye against the notes' markdown (the row quoted in the candidates list is the row in the note). They were real checks on this project's notes and are described here by shape:

1. The audit report's first stated day, in the month-day-year form (section 4), lists timeline row 8 of a held note on a batch of web posts, which states the same day in the same words: a press release of that day naming an officer, at that note's line 638, with `echo:` on a figure the two share (a unit's number).
2. The audit report's own release date (section 3) lists tl 74 of the held video note of the third test run, which gives the same day in another wording (an ordinal day before the month), the release of the report itself: that note's line 917.
3. The audit report's "The following day" (section 5), resolved to the next day from the anchor of check 1, lists tl 17 of a held book note, "Back on" that day, an official identification announced that day: that note's line 534.
4. The blog post's day date (section 16) lists tl 16 of a held contract-status document's note (line 528) and tl 9 of the held letter's own note (line 442), both the same letter of that day, and tl 7 of a held agency document release's note: tl 16 and tl 7 are the two timeline rows a `--table timeline` query for that letter over that month returns with tools/rows_search.py (the form of tools/rows_search.md's first example).
5. The transcript's day date in the form "24th <Month> <year>" (section 16) lists tl 2 of a held congressional document release's note, an officer's letter dated one day earlier in the document's own form (month abbreviated in capitals, day, year), one day inside the window: that note's line 495; and, in the run without `--exclude-note`, the transcript note's own `tl 13` (the speaker's dating of a document to that day), which the excluded run removes.

Noise seen and left for the agent: a short filler sentence ending "about 1000." in the transcript comes through as the year 1000 (its sentence shows it); "Room 1100" and "the day after" followed by a place name are now excluded by rule.

## Tests, 2026-10-22 (the defaults above)

A blog batch held as two sets of posts (21 and 29 posts, about 50,000 words each), cut into units by post with tools/chunk_source.py. Words of timeline-candidates.md (the coarse file beside it in brackets):

| Run | set A | set B |
|---|---|---|
| defaults of 2026-10-15 (3, 1, 25, coarse dates inline) | 205,213 | 221,712 |
| the settings given by hand on 2026-10-15 (the archived files) | 30,947 (28,723) | 35,323 (29,192) |
| these defaults | 28,151 (25,815) | 35,243 (23,584) |
| `--cap 2` | 20,149 | 25,803 |
| `--cap 1` | 16,339 | 21,386 |

Most of the main file is the candidates themselves (four rows of about 45 words for each of about 90 full dates and month-years in set A). The defaults reproduce the hand settings; a file of about 10,000 words for a source this dense in dates needs `--cap 1` and a shorter candidate line, or the main file restricted to full dates (month-years to the coarse file), which is for the owner to rule on.

## Limits

- A candidate is a row on the date, not a finding: read it in its note before citing it in Agreement, Cross-checks or a ledger.
- The IDs with `--note` come from notes.db, that is the note as last built; a note edited since may have moved. The agent still inserts with `tools/timeline_insert.py`, which computes the ID again at write time; the pre-pass's ID is for writing the row text without a lookup.
- Spelled-out dates beyond years ("the fourteenth of March" without digits), seasons ("the summer of 2016": the year is caught, the season is not read as a month), and "N years" without "ago" are not resolved. Captions that split a date across two timestamp blocks are read as two expressions.
- Undated held rows (Sortable `?`) are not matched; the consolidated era pages place some of them by hand, so the era page is still worth a look for an event with no dated candidate.
- Claims rows are not searched: a date held only in a claims ledger shows as "no held row" here. tools/rows_search.py with `--table claims` covers that before a `new` ruling.
