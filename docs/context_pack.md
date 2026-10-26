# tools/context_pack.py: the context pack for an intake

Added 2026-10-15. Profiling of the intake agents (the session that commissioned this tool) found that each intake spends about forty greps and several whole-note reads (notes run 35,000 to 55,000 words) finding the held rows its source confirms or contests, the first-utterance clusters to tag, the narrative ledger rows to speak to and the leads to answer. `tools/rows_search.py` (same day) made each of those lookups one query. This tool runs every lookup a source needs before the agent starts and writes the results to one file, so the agent reads `<wip>/context.md` and opens a note only for a row the pack cites.

Standing rule for intake briefs: before reading held notes, run `python3 tools/context_pack.py <source files> --wip wip/<task>` and read `wip/<task>/context.md`; open a note only for rows the pack cites. A term match is never a finding (tools/schema.md section 10): read the cited row in its note before entering it in Cross-checks.

## Command line

```
python3 tools/context_pack.py <source .txt/.md files...> --wip wip/<task> [--max-rows-per-term 5] [--broad 60] [--min-count 3]
                              [--with-dates] [--row-chars 220 | --full] [--index-cap N] [--budget-words 30000]
                              [--sets-json books/sources/web/<set>/sets.json --set <key>] [--exclude-note <stem>[,<stem>]] [--names-only] [--db notes.db]
```

- Sources are the held copies (`.txt` or `.md`); several files are one source. `--sets-json` with `--set` adds every file of that key of a `sets.json` (a blog batch's keys A and B).
- `--wip` is the task's wip folder; the tool writes `context.md` and `context-overflow.md` there and nothing else. The folder is created if missing.
- `--names-only` prints the extraction (names with their kind, members and query variants; dates; identifiers and titles; URLs) and stops, for review before a long run.
- `--max-rows-per-term N` (default 5) is the cap per term; see Caps. `--broad N` (default 60) is the row count above which a term is treated as broad. `--min-count N` (default 3) is the minimum number of mentions for a multi-word name; single words always need two. These defaults (2026-10-22) are the settings a blog batch of 2026-10-15 was given by hand after the earlier defaults (40, 200, 1) gave packs of 164,000 to 174,000 words.
- `--with-dates` builds section 2b (held rows by date); it is off by default, and skipped even when asked for when `<wip>/timeline-candidates.md` exists, since tools/timeline_prepass.py reads the source's dates against the held timeline with date windows and ranking (section 2b then holds a one-line pointer; the dates themselves are still listed in section 1).
- `--row-chars N` (default 220) cuts every row of sections 2, 4 and 5 to N characters after its citation, the index-form lines of sections 4 and 5 at a whole row (the full line goes to context-overflow.md); `--full` prints them whole. A note under each of those sections says so: the full row must be read in its note before use.
- `--index-cap N` (default 0, no cap) lists at most N rows on an index-form line of sections 3 to 5, the whole line in context-overflow.md.
- `--budget-words N` (default 30000): the header's Budget line gives the pack's words against N and names every section over its share (section 1 10%, 2 35%, 2b 10%, 2c 8%, 2d 3%, 2e 4%, 3 10%, 4 with 4b 10%, 5 7%, 6 3%), with the flags that narrow it. The budget is reported, never enforced: nothing is cut to meet it.
- `--exclude-note <stem>[,<stem>]` tests a source that is already held, as tools/timeline_prepass.py's option of that name does: the notes' own rows are left out of section 2, register rows whose every citation is to those notes (the rows their intake created) are left out of sections 3 and 5, and the notes are left out of section 6.
- Reads notes.db read-only (it needs the `rows_fts` table that `tools/build_db.py` builds), research/first-utterance-register.md, research/narrative-*.md, research/leads-and-inferences.md, research/source-kinds.md, tools/name_aliases.json and the held notes' markdown (section 6). It imports `tools/rows_search.py` and calls its `search()` function; it does not duplicate the index or the query syntax.
- Run time: about 20 seconds for a 3,500-word document, about 50 seconds for a 56,000-word set of 36 posts (2026-10-15, 95,000-row index). Section 6 reads every held note once.

## What context.md holds

**Header.** The command, the rule, and a count table: source files and words; names (people among them); dates (full, month-year, year); identifiers and titles; URLs; held rows cited (and across how many notes; terms with rows, without, broad); overflow rows; first-utterance clusters by name and by date; narrative ledger rows and nodes; leads; notes with any mention.

**1. Extracted from the source.** Every name with its mention count, kind and other forms seen; every date; every identifier and quoted title; every URL. Read this list first: it is what the rest of the pack searched for, and a name the extractor missed is a name the agent must search by hand.

**2. Held rows by name.** One group per name, ordered by mentions in the source: the heading gives the name, its mention count, the other forms merged into it (surname alone, acronym), the held-row total, the FTS query and the cap. Rows are `[citation] | date | speaker | text` in the citation forms the notes use (`[<stem> claims N]`, `[<stem> tl N]`, `[<stem> audit N]`), everything after the citation cut to `--row-chars` (220), ranked by bm25 with rows carrying a fuller form of the name (first and last name rather than the surname alone) first. A row is shown once, under the first term that matched it; later terms list it as a citation only ("also matched, shown under an earlier term"). Quotes and people rows are not searched (the brief asked for claims, timeline and audit).

**2b. Held rows by date** (only with `--with-dates`, and not when timeline-candidates.md exists). A full date: timeline rows whose event date is that day (`--from`/`--to` on the timeline's sort key), then claims and audit rows whose text carries the date in any of its spellings (`14 march 2017`, `march 14 2017`, `2017 03 14`). A month-year: timeline rows in that month that also name one of the source's specific names, then claims and audit rows carrying the month-year phrase. A bare year: timeline rows in that year that also name one of the source's specific names. The count of range rows left out for naming nothing is stated in the heading. Claims and audit rows are never searched by bare year (their date key is the note's upload date, not the claim's).

**2c. Held rows by document identifier and title.** Identifiers (the core's generic forms: agency report numbers of the `OFFICE/DIVISION-YY-NNN` form, memorandum or case numbers of the `X-YY-NNNN` form, contract numbers, archive accession numbers, record groups, FOIA case numbers; and the pack's own forms, read from the file its pack.toml names under `[vocabulary] id_patterns`, each with an order number that places it among the core's, since the first form to match an identifier gives its label) and quoted or italicised titles, each queried as the phrase of its tokens.

**2d. Held rows by URL.** Each URL as the phrase of its tokens; a YouTube URL whose video is a held note is also named as that note.

**2e. Terms with no held rows, and broad terms.** The names, dates, identifiers and URLs that matched nothing, in one line, and the broad terms with their row counts and the narrowed command to run.

**3. First-utterance register clusters.** Name matches: clusters whose Event or Claim text names one of the source's specific names, with ID, Event, Claim, Rows, earliest held telling, status and the names that matched; cite as `[fu FU-n]`. Date matches: clusters whose Event year range covers a source date, marked `specific` when a full date or month-year of the source falls in the range and `year` when only a bare year does, as compact lines (ID, range, claim, status).

**4. Narrative pages: contradiction-ledger rows.** Every `## Contradiction ledger` row of every narrative page (mainlines and forks; not the synchrony pages, the rival sheets or the register) whose Contradiction, Side taken, Other side, Why survivable or Flare cell names one of the source's specific names, with page, row number, node, the contradiction and side trimmed, and the names matched. 4b lists the `## Nodes` rows the same way (page, node number, date, node text, carriers).

**5. Leads register rows.** Every row of research/leads-and-inferences.md whose Lead, Sources, What would settle it or Answer cell names one of the specific names, with lead number, kind, status, the lead trimmed, what would settle it, the answer so far and the names matched.

**6. Held notes that mention the names most densely.** The fifteen notes with the most mentions of the specific names (the whole note file, transcript included), with the note's kind from research/source-kinds.md, the names counted most, and how many of its rows sections 2 to 2d cited; then every other note with any mention and its count, in one line.

**7. Commands used.** The count of rows_search.py queries and the forms used; the full list, one command per query, is at the end of context-overflow.md.

## Caps, and what is never dropped

- `--max-rows-per-term N` (default 5) caps every group in sections 2 to 2d. Rows beyond the cap are written to `context-overflow.md` under the same heading, in the same form (cut to `--row-chars`), and the group ends with "and N more rows, listed in context-overflow.md". Nothing is dropped silently.
- Reduced caps, each stated in the group heading: a single-word term that is not a person (a place, an adjective, an acronym) and a broad term the source names only once get a quarter of N; a month-year gets half; a bare year a quarter. Full dates, people, organisations and multi-word names get N.
- A broad term (more than `--broad` rows, default 60) shows its cap and then the rest as per-note counts ("and N more rows, by note: stem n, stem n, ..."), with no overflow: the agent narrows it with `rows_search.py ... --note '<stem glob>'`. The broad terms are listed again in 2e with the command. A broad term is usually a subject word (Harrowmere, the Authority, spillway) or a person the database holds in depth (Vanecek, Thale); the per-note counts say where the rows are.
- In sections 3 to 5 a name that matches more than 12 register rows is broad for that register; rows matched only by broad names are listed in index form under the name (ID or row number, status, a 50-character gist), so the agent can open them, and rows with at least one specific match are shown in full.
- Month-year and year ranges list only the timeline rows that also carry one of the source's specific names; the count of the rest is stated. A bare year on its own is not a match on the source.

## How the extraction works, and its limits

The examples in this section are the invented cases of tools/example-casebook.md.

- **Names** are capitalised word sequences (connectors such as of, the, for, and, de, von allowed inside), taken paragraph by paragraph after URLs, image markers, e-mail addresses, page markers and boilerplate lines (a line that recurs five or more times once digits are removed: the running footer of a scanned report) are removed and identifiers are cut out. A sequence breaks at sentence punctuation (not after an initial, a title such as Dr or Lt, or an abbreviation such as Inc or Jr), at brackets and quotes, at a slash, and across a line break next to a short line or a line that opens with an acronym (the headings and abbreviation lists of a scanned report). Leading stop words, titles, roman numerals and section words (Appendix, Attachment) are stripped; so is a leading common word when the next word is also common (Comments From the Vale Water Authority gives Vale Water Authority) but not when the next word is a name (a place name that opens with a common word such as New or North). A candidate is dropped when every word in it also occurs in lower case in the source, when it is a single word of fewer than three letters or one the source also uses in lower case, when it is an all-caps heading seen once, or when it is a single word seen once. Plurals join the singular (CACs into CAC). A candidate containing " and " is also split into its halves.
- **Kinds.** A candidate is a *person* when its normalised form, or its first and last word, is a held people name (notes.db `people`, with tools/name_aliases.json), when it opens with a title, or when its first word is a first name among the held people and neither word occurs in lower case in the source (so a place whose first word is a held first name, and Young Man, are not people). An acronym joins the phrase whose initials it is (CAC with Calloway Ashdown Civil) as one *organisation or programme*. People with the same first and last word merge (Petra Vanecek, Petra M Vanecek); a surname or first name the source uses alone joins the one person who carries it. Everything else is a *name* (places, bodies, documents, programmes without an acronym) or an *acronym*.
- **Query variants.** A person is queried as every form seen, the first-and-last form, the held forms with the same first and last word, the alias file's forms (two-word forms only; caption garbles of one word are left out), and the surname alone only when the source itself uses the surname alone and it is four letters or more and not a generic word. Everything is a quoted phrase of FTS tokens (punctuation dropped, so DC-0917 is "dc 0917"), OR-ed.
- **Dates** are ISO dates, day-month-year and month-day-year in words (14 March 2017, March 14, 2017, Mar. 14 2017), month-years, and bare years 1500 to 2049; a date spanning a line break is read. **Identifiers** are the patterns listed at the top of the script; **titles** are quoted strings of three to sixteen words containing a document word (Report, Memorandum, Letter, Act, Study ...) and italicised phrases in markdown. **URLs** are anything starting http(s)://, including the `[url]` form of one blog batch's captures.
- The extractor is heuristic. It over-generates (mailing boilerplate on a report's back page, "Best Regards", a fragment such as Standards Board cut by a line break) and those terms cost one line in 2e when they match nothing; it can under-generate a name written in lower case or split across a page break. Always read section 1 and search by hand for anything missing. `--names-only` shows the extraction in a few seconds.
- A term match is never a finding. A surname the source uses alone (Thale for Owen Thale) matches every held Thale; a place name matches every row that names the place. The agent reads the row in its note before using it, and the pack says in every heading what was searched.

## Tests, 2026-10-15

Two held sources, packs under wip/context-pack-test/ (REPORT.md there has the spot check):

| Source | Words | Names | Rows cited | Overflow rows | context.md | overflow.md | at --max-rows-per-term 20 |
|---|---|---|---|---|---|---|---|
| a government audit report held as text (one `.txt` file) | 3,468 | 117 | 1,384 | 1,226 | 84,077 words | 44,216 | 65,390 / 60,065 |
| a blog batch, sets.json key B (36 posts) | 55,889 | 207 | 2,347 | 2,846 | 147,185 words | 78,894 | 117,008 / 107,782 |

The packs are large because the database holds both sources' subjects in depth (section 2 is about half of each pack, the date section a sixth to a third); a source on a thinner subject gives a much smaller pack. Ten rows read against their notes: ten citations resolve to the right row with the right cells; nine bear on the source; one (a surname group) is a true term match on a surname the source uses alone that the database holds only for an unrelated person of the same surname. The sizes to compare against are the forty greps and the three to five whole-note reads (105,000 to 275,000 words) an intake made before.

## Tests, 2026-10-22 (the defaults above)

A blog batch held as two sets of posts (21 and 29 posts, about 50,000 words each), cut into units by post; the sets' own notes are now held, so they were also run with `--exclude-note` for both notes (the state of 2026-10-15, when the packs were first built by hand). Words of context.md:

| Run | set A | set B |
|---|---|---|
| defaults of 2026-10-15 (40, 200, 1, dates in, rows at 200 characters), today's database | 192,533 | 198,566 |
| the settings given by hand on 2026-10-15 (the archived packs) | 32,576 | 37,213 (and 16,000 to 19,000 in a separate by-date file) |
| these defaults, today's database | 43,366 | 47,928 |
| these defaults, both of the batch's notes excluded | 37,464 | 43,189 |
| `--max-rows-per-term 2 --min-count 5 --row-chars 160 --index-cap 4` | 34,461 | 38,992 |

The defaults reproduce the hand settings within about 15% (the registers have grown since). They do not reach the 10,000-word pack the intake measurement aimed at: section 2 alone is 14,000 to 18,000 words for a source that names some two hundred people and bodies the database holds in depth, and sections 3 to 5 list every register row that names one of them. The Budget line names those sections on every run. A pack of about 10,000 words needs a cut of a different kind (a total row budget across terms, or names ranked by their weight in the source), which is for the owner to rule on.

## Where it sits in the workflow

- Intake briefs (wip/context-pack-brief-line.md holds the line to add; the live briefs were not edited): run the pack first, read context.md, open a note only for a row the pack cites, then `tools/rows_search.py` for anything the extractor missed, then read each row in its note before the Cross-checks row.
- Investigation mode keeps `tools/evidence_pack.py` (a thread's whole record by terms given by hand); narratives keep `tools/narrative_digest.py` (a seed's digest). This tool is the intake-side counterpart: the terms come from the source itself.
- The pack is a wip file (tools/agent-wip.md): it is rebuilt by rerunning the command, never edited by hand, and it is not published.
