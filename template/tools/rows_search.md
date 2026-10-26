# tools/rows_search.py: full-text search over the held rows

Added 2026-10-15. The narratives workflow measured (tools/narratives.md section 10b) that the main token cost of a page task is locating one held row: agents grep the markdown and read whole 35,000 to 55,000 word notes to find the row they need to cite. `tools/narratives.py --rows` resolves references already known; nothing resolved a question into references. This tool does: a query goes in, the matching rows come out in the citation form the agents use, with their cells.

Standing rule (the briefs, tools/narratives.md section 8c, tools/schema.md section 10): find held rows with `python3 tools/rows_search.py` before grep or reading a note. Reading the row in its own note afterwards is still the rule for anything entered into a Cross-checks row or a narrative ledger; the search finds the row, it does not replace reading it.

## What is indexed

`tools/build_db.py` builds an SQLite FTS5 virtual table, `rows_fts`, on every run, from the row tables of notes.db (no separate index file; notes.db grows by about 84 MB, 77 to 161 MB on 2026-10-15, because FTS5 stores a copy of the indexed text). One FTS row per held row:

| kind | source table | citation | date column | speaker column | text column | extra column (also searched) |
|---|---|---|---|---|---|---|
| `claims` | claims | `[<stem> claims N]` | Time | Speaker | Claim | topic, source class, move, Note (attribution and chain) |
| `tl` | timeline | `[<stem> tl N]` | Date as stated | Speaker / basis | Event | sortable date, chain, database link, agreement |
| `audit` | audit_rows | `[<stem> audit N]` | Time | Asked by | Question `=>` Answer | move, basis, note |
| `quote` | quotes | `[<stem> quote N]` | time | (none) | the quote | (none) |
| `people` | mentions | `[<stem> people <name>]` | times | name | role; detail | relation |

The first three are the citation forms `tools/narratives.py --rows` and the narrative pages use. `quote` and `people` are the two further row tables that carry text; they are searched by default and cited in the same shape (`--table` restricts the kinds).

Rows on 2026-10-15: claims 47,449; timeline 10,316; audit 14,930; quotes 9,448; people 13,105; `rows_fts` 95,248. Build time about five seconds. The tokenizer is unicode61 with diacritics removed, so a query without the accent finds the accented name or word (`cafe` finds café).

For `--from`/`--to`, each FTS row carries a sort key: a timeline row's own key (schema section 11, year plus 1,000,000,000), and for every other kind the note's Uploaded date in the same encoding. So a date range on timeline rows is by event date, and on claims, audit, quote and people rows by the date of the note that holds them.

## Command line

```
python3 tools/rows_search.py "<query>" [--note <stem glob>[,<glob>]] [--speaker <name>] [--table claims|timeline|audit|quote|people[,..]]
                             [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--limit N] [--full] [--json] [--db PATH]
```

- The query is FTS5 syntax passed through unchanged. Words are ANDed; `"a phrase"` matches in order; `OR`, `NOT`, `NEAR(a b, 5)` and `prefix*` work; column filters work on the FTS columns (`speaker:vanecek`, `text:"left wall"`, `date:2015`, `extra:hearsay`, `video:harrowmere`). Two FTS5 rules worth knowing: a hyphenated or punctuated term must be quoted (`"DC-0917"`, `"PROJECT LARKSPUR"` is safe either way), and a parenthesised group needs an explicit `AND` before it (`memo AND crack* AND (lisle OR heron)`); a syntax error is reported with that hint.
- `--note` is a glob on the note stem (`harrowmere-day-*`, `corvane-*`, `long-table-*`), several separated by commas. `--speaker` is a case-insensitive substring of the speaker, speaker/basis, asked-by or name cell. `--table` takes the names above (`timeline` and `tl`, `audit` and `audit_rows`, `quotes`, `mentions` are accepted).
- Results are ranked by bm25 with the text column weighted highest (text 10, extra 3, speaker 2, date 1). `--limit` defaults to 50. A summary line (total matches, shown, the filters) goes to stderr, so stdout is rows only.
- Default output, one row per line: `citation | date cell | speaker cell | text cell`, the text trimmed to about 300 characters (`--full` prints it whole; date and speaker cells are trimmed to 60). `--json` prints a list of objects, each with `cite`, `kind`, `note`, `n`, `table` and every cell of the row from its own table (for a timeline row: date_stated, sortable, sort_key, approx, event, speaker_basis, chain, link, agreement, agreement_kind).
- Reads notes.db read-only. If the table is missing, it says to run `python3 tools/build_db.py`.

## Examples (illustrative)

The notes, rows and result counts in this section are illustrative: they are invented on the cases of tools/example-casebook.md to show what each form of query does. The commands and the FTS5 syntax are exact.

**The Lisle memo of June 2015.** `python3 tools/rows_search.py 'lisle memo "june 2015"'` returns 27 rows. The top of the ranking holds the memo itself and its relays: `[lisle-memo-2015 claims 33]` (the memo of 2 June 2015 from Lisle, signed, as disclosed to the inquiry), `[harrowmere-day-12 claims 114]` (counsel to the inquiry putting it to the witness), `[thale-ostley-gazette-2017 claims 184]` (Thale's account of what it warned of), `[lisle-memo-2015 quote 1]` (its opening sentence) and `[thale-ostley-gazette-2017 audit 37]` (what the published story withheld of it). Narrowed to the event: `python3 tools/rows_search.py 'lisle memo' --table timeline --from 2015-06-01 --to 2015-06-30` returns exactly the two dated rows, `[harrowmere-day-12 tl 16]` and `[thale-ostley-gazette-2017 tl 7]`. Narrowed to one note: `'lisle memo 2015' --table claims --note 'lisle-memo*'` returns 14 rows, claims 22, 33, 117, 99, 2, 90, 21 and 50 at the top. Checked against books/lisle-memo-2015.md line 181 (claims 33).

**The Larkspur spreadsheet's routing question.** The spreadsheet's sheet 7 lists the routes the transfers took. `python3 tools/rows_search.py 'spreadsheet AND transfer* AND (treasury OR auditor OR board)'` returns 6 rows, the three spreadsheet rows among them: `[corvane-files-larkspur-spreadsheet-2019 claims 99]` (the first block of transfers, routed through the treasury account), `claims 100` (the second block, booked as an intra-group loan) and `claims 101` (the third block, approved at board level), with `[brightwell-fenn-audit-letter-2014 claims 20]`, the auditor's reading of the same schedule. `'"sheet 7"' --note 'corvane-files*'` returns 1 row, `[corvane-files-larkspur-spreadsheet-2019 quote 7]`, the routing line quoted as sheet 7; `'"board approval"'` returns 5 rows, led by `[corvane-board-minutes-2014-04-03 claims 37]`, the minutes' approval item. The broad `'larkspur transfer*'` returns 42 rows and ranks Quillon's and the press's rows above the spreadsheet's, because those rows say "Larkspur" where the spreadsheet rows name the arrangement only in their note stem; narrow by `--note` when the holding note is known. Checked against books/corvane-files-larkspur-spreadsheet-2019.md lines 361 to 363 (claims 99 to 101) and line 666 (quote 7).

**Core sample C-14.** `python3 tools/rows_search.py '"C-14" core'` returns 6 rows: `[margin-notes-strand-harrowmere-2021 claims 79]`, `tl 4` (the 2011 coring of the left wall, the test record against Vanecek's recollection), `claims 65`, `claims 73`, `claims 70`, and `[long-table-episode-4-2022 tl 10]`. `'"C-14"' --table timeline` returns 3 rows (the *Margin Notes* note's tl 4 and tl 48, and *The Long Table*'s tl 10). `--json` on the timeline row gives its chain (`3: Ivo Strand <- Petra Vanecek (2019, 2020) <- the core test record, 2011, and Pernell Geotechnics' foundation report (2010) (document)`) and its agreement cell. Checked against books/margin-notes-strand-harrowmere-2021.md, Dated timeline row 4.

**Other forms.** `'speaker:castellan "lisle memo"'` (34 rows: what Castellan says about the Lisle memo across her episodes); `'NEAR(harlowe lisle, 6)' --table claims` (17 rows: Harlowe and Lisle within six tokens); `'memo' --speaker harlowe` (15 rows: rows whose speaker cell contains Harlowe); `'"HI-114"'` (40 rows: every row that cites the site diary by exhibit number).

## Where it sits in the workflow

- Intake (wip/intake-1008/brief-document.md and the video intake brief of a 2026-10-08 batch, standing rules): find the held row for a fact with this tool before grep or reading a note; then `tools/narratives.py --rows` for a batch of known references; then read the row in its note before entering it in Cross-checks.
- Narratives (tools/narratives.md section 8c): lookups batched (`--rows`), reads of sections (`--section`), and rows not yet known by reference found with this tool.
- Schema (tools/schema.md section 10): the pointer in the Cross-checks rule.
- The query cost is one call of under a second against a 95,000-row index; the saving is the note read it replaces.

## Limits

- A term match is never a finding (schema section 10): the search locates rows; the agent reads them.
- The row's note date, not the claim's date, bounds `--from`/`--to` for claims, audit, quote and people rows; for the date a claim speaks of, search the timeline (`--table timeline`), whose rows carry the event date.
- The FTS copy is rebuilt from the markdown on every `build_db.py` run and never written to; agents validating a note on their own `--db wip/<task>/check.db` get a private index there, and can point `--db` at it.
- Cross-checks (`[<stem> xc N]`), open questions, leads and relations are not indexed here; `tools/narratives.py --row` prints a known xc row, and tools/relations.py and the leads register's own queries cover the rest.
