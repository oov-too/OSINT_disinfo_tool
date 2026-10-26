# Hold schema (v1.0, 2026-10-22; phase 3 of tools/platform-plan.md)

The hold is where every source the ledger reads is kept as it was obtained. Every acquire adapter (tools/ledger/acquire/: youtube, web, document, bulk, canon, database, transcribe) writes to it in the one form this document fixes, and the setup scan (setup stage 2) reads a stranger's database against the same fields. The machine form of the fields is tools/ledger/acquire/schema.py; the two agree field for field (tools/ledger/acquire/tests/test_base.py checks it). Notes are not part of the hold: they read it and cite it.

## 1. Rules

1. **Byte-for-byte.** A held file is the bytes as obtained: the response body, the export's file, the fetcher's output, the database rows as the query returned them. Nothing is re-encoded, re-wrapped or given a header. What the ledger makes from a held file (a text layer, an OCR, a transcript, a rendering of HTML to text, the units of a canon text) is a *derived* file: it names the held file it came from and the tool and settings that made it.
2. **The README records how.** Every hold has a README.md that says how each file was obtained (URL, query, path, route), when, by which adapter and underlying tool, with each file's size and SHA-256. The README is generated from hold.json by the adapter; it is never typed and never edited by hand (a re-capture regenerates it).
3. **Nothing held is overwritten.** A re-capture whose bytes are identical adds a capture row ("unchanged"). One whose bytes differ is held beside the first as `<stem>.<capture time>.<ext>` ("changed"); the first capture stays. Which capture is canonical is recorded, not decided by deletion (the version rule: a later, longer edited version is canonical; the first state is kept as a version, not read as the text).
4. **LF.** Every derived file, README.md and hold.json is UTF-8 with LF line endings on every platform; readers normalise CRLF and a byte-order mark (citations are line numbers; the verbatim gate matches text). Held files keep whatever line endings they arrived with.
5. **Portable names.** ASCII slugs, the caps and the reserved characters of section 7, so the hold copies to Windows, a share or a USB stick unchanged.
6. **Local.** The hold and any index beside it (index.db) live on the machine that reads them; SQLite files are never opened over a share.
7. **Fetching honestly** (the owner's policy, 2026-10-22). Every request names the ledger in its user agent (`LedgerAcquire/<version>`, the project and the operator's contact from ledger.toml `[acquire] contact`); there is no browser agent and no per-host override. robots.txt is read per host (RFC 9309: the longest matching rule decides, an Allow wins a tie) and honoured for the ledger's token and for Claude-User; a Crawl-delay raises the host's gap; a disallowed URL fails the hold, the failed row and `<state dir>/robots-refusals.jsonl` naming the deciding line; every hold made from the web records the verdict in its metadata (`robots`).
8. **The item's date, never the fetch date.** A date comes from the item itself (its markup, its catalogue entry, its first page) or from the caller with a basis; `date_basis` says which. When none is found the date stays empty, `date_basis` says what was searched, and the hold is named `undated-<slug>`.

## 2. Fields

One record per held item. `Required`: **yes**, the adapter refuses to hold without it; **set**, the adapter supplies it, never the source; **no**, recorded when the source states it. The synonyms are the column names (split into words: `recNo`, `rec_no` and `rec-no` all read as "rec no") the setup scan and the database adapter's mapping proposal match against; a match is scored 1.0 for an exact synonym, 0.85 for a synonym that ends the column's name, 0.7 for a synonym's words all inside it, 0.5 for a near spelling, and combined with a check of the values (date share, URL and path share, text length, uniqueness).

<!-- FIELD TABLE: generated from tools/ledger/acquire/schema.py -->

| Field | Meaning | Type | Required | Synonyms the setup scan matches |
|---|---|---|---|---|
| `identifier` | The item's stable identifier in the place it came from: a YouTube id, a URL, a database key, an archive item number, a canon text's short name. Unique within its source; never reused for another item. | string | yes | id, identifier, key, uid, uuid, guid, pk, record id, rec no, record no, record number, item id, doc id, document id, document number, accession, accession number, catalogue number, catalog number, call number, reference, ref, esdn, serial, video id, file id, entry id, case number, case id, control number, number, no |
| `media_kind` | What the item is as a medium; decides the hold folder (sources/<folder>/) and which preparation applies (transcription for video and audio, text layer and OCR for document and image). | enum (archive-item, audio, canon, document, feed, image, post, record, text, thread, video, web-page) | yes | kind, type, media type, media kind, medium, format, mime, mime type, content type, record type, item type, doc type, document type, genre, category, source type, kind code |
| `date` | The date the item belongs to: published, uploaded, recorded, written or created, whichever the source states (the metadata block says which as date_basis). The source's own spelling is kept as date_raw; an inferred or swapped day and month is marked with a trailing `?`. | ISO 8601 date (YYYY-MM-DD, YYYY-MM or YYYY), with date_raw kept | no | date, published, publication date, pub date, uploaded, upload date, recorded, recording date, created, creation date, created at, date created, aired, air date, broadcast, dated, document date, event date, timestamp, time, issued, date of, posted, posted at, year |
| `title` | The item's title as the source gives it, in full (the slug is cut; the title never is). Where the source has none, a description in square brackets, e.g. [untitled letter of 3 May 1950]. | string | yes | title, name, headline, heading, subject, caption, label, document title, video title, episode title, display name, short title |
| `speaker_or_author` | Who speaks or wrote: authors, speakers, interviewer and interviewees, signatories, the poster of a post. Names as the source spells them; roles, where the source gives them, in the metadata block. | list of strings | no | author, authors, by, byline, writer, creator, speaker, speakers, host, guest, guests, presenter, interviewer, interviewee, participants, witness, witnesses, signatory, sender, from, poster, username, user, handle, contributor, respondent, narrator, person, people |
| `text` | The item's text: the transcript of a recording, the text layer or OCR of a document, the body of a page or post. A file inside the hold, derived from a held file by a named tool, or held as obtained when the source is text. Empty only with a status saying why (transcriber missing, renderer missing, pending). | file in the hold (UTF-8, LF), or empty with a status | no | text, body, content, transcript, transcription, full text, fulltext, ocr, ocr text, utterance, utterances, words, contents, message, post body, article, description, notes, summary, abstract, narrative, statement, testimony |
| `media_link` | Where the item's media are: the video or audio URL, a file path in the source's store, a scan's URL. Media found at a path are held byte-for-byte; a URL is recorded and fetched only where the network permits. | URL or path | no | url, link, href, uri, media, media url, media link, file, file path, path, location, filename, file name, attachment, audio, video, recording, scan, image, pdf, source url, download, blob |
| `venue` | Where the item appeared: channel, programme, outlet, publisher, forum and board, hearing and committee, archive and collection, journal. | string | no | venue, channel, outlet, publisher, publication, source, site, forum, board, subreddit, programme, program, show, podcast, series, network, station, journal, newspaper, collection, archive, repository, committee, hearing, event, conference, folder, box |
| `provenance` | How the item was obtained, exactly enough to obtain it again: the URL fetched, the SQL query with its parameters, the archive item URL, the export file and row, the local path a file was copied from. | string (URL, query, path) | set | provenance, source url, origin, obtained from, retrieved from, query, accession source, acquired from, fetched from, permalink, canonical url |
| `capture_time` | When the adapter read the item. Every later capture of the same item adds a capture row; earlier held bytes are never overwritten. | ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ) | set | captured, capture time, retrieved, retrieved at, accessed, access date, fetched, fetched at, harvested, ingested, imported, imported at, updated, modified, last modified, updated at |
| `capture_tool` | The adapter and version that held the item, and the underlying tool it wrapped with its version or settings (e.g. `ledger.acquire.youtube 1.0 via tools/fetch_transcript.py`). | string | set | tool, capture tool, harvester, scraper, importer, software, agent, user agent |
| `metadata` | Everything else the source states about the item that no field above takes: unmapped columns, the date's basis, roles, page counts, captions language, licence. Kept whole; promotable to a pack's keys later. | table of key -> value (strings, numbers, lists) | no | metadata, meta, extra, attributes, properties, tags, keywords, fields, info, misc |

Beside the fields, a record carries `date_raw` (the source's own spelling of the date, kept whenever it differs from the ISO form) and the system entries of hold.json (section 3).

Media kinds and where they land:

<!-- KIND TABLE: generated from tools/ledger/acquire/schema.py -->

| Media kind | Hold folder | Preparation |
|---|---|---|
| video | sources/video/ | transcript (captions, or local transcription) |
| audio | sources/audio/ | local transcription |
| text | sources/text/ | none (the text is held) |
| document | sources/document/ | text layer, OCR of pages that need it |
| image | sources/image/ | OCR |
| web-page | sources/web/ | HTML rendered to text; feed entries; thread pages |
| post | sources/web/ | HTML rendered to text; feed entries; thread pages |
| thread | sources/web/ | HTML rendered to text; feed entries; thread pages |
| feed | sources/web/ | HTML rendered to text; feed entries; thread pages |
| archive-item | sources/archive/ | index (FTS5) over the items |
| canon | sources/canon/ | units by the text's scheme |
| record | sources/db/ | record.json, mapped fields, media held and transcribed |

The fields line up with a note's metadata table (tools/schema.md section 1): identifier and media link with URL, date with Uploaded or the document date, title with the note's heading, speaker_or_author with Host, Guest, Speakers or Authors, venue with Channel, text with Transcript. A note is written from a hold; the hold never from a note.

## 3. The hold layout (an item hold)

```
sources/<kind folder>/<name>/
    README.md          generated provenance form (below)
    hold.json          the machine record: schema version, adapter, the record's fields, the files, the captures
    <held files>       byte-for-byte: page.html, feed.xml, the PDF, the media file, record.json, the fetcher's output, ...
    <derived files>    UTF-8, LF: text.md, text-layer.txt, ocr.txt, text.txt, pages.tsv, transcript.md, units.jsonl, annotations.json, ...
```

`<kind folder>` is the media kind's folder (section 2); a set adds one level (`sources/web/<set>/`, `sources/document/<set>/`). `<name>` comes from `hold_path(kind, ident, title)` (tools/ledger/hold.py): a YouTube id is `yt-<id>` with its case kept; otherwise the slug of the identifier (adapters put the date first where they know it, as the web sets name their files: `2026-10-14-<slug>`), then the slug of the title while there is room under the stem cap. Two items whose names collide keep their own folders: the second gains `-<8 hex of the SHA-1 of its identifier>`. A captured file named README.md or hold.json is held as `held-README.md` or `held-hold.json`.

hold.json:

| Key | Content |
|---|---|
| schema | this document's version |
| adapter | `ledger.acquire.<adapter> <version>` |
| hold_module | which module named the folder (ledger.hold) |
| record | the fields of section 2 and date_raw |
| files | one entry per file: name, role (held, derived or linked), bytes, sha256, how, captured; a derived file adds derived_from and tool; a linked file (a large original held by link: its URL, size and SHA-256 recorded, the bytes left at the source) adds link |
| captures | one entry per capture: time, tool, status (new, unchanged, changed), provenance, note |
| status_note | what the adapter could not do (renderer missing, transcriber missing, media not found), so a hold that is incomplete says so |
| texts | when the item's text is several held files (a database record's text attachments with `all = true`): every one, in order; `record.text` is the first. The pre-pass cuts them all |
| size | bytes stored in the hold (held and derived files), size_class (small under 10 MB, medium under 100 MB, large), linked_bytes |

README.md, the provenance form (as the READMEs under books/sources/web/ have it, generated):

```
# <title>

Held <date> by <capture tool> from <provenance>. <n> files held byte-for-byte as obtained and <m> derived from them by the tools
named in the files table. The SHA-256 of every file is in the table; a later capture never overwrites a held file (...). <status note>

This file is generated from hold.json by ledger.acquire; it is not typed and not edited by hand.

| Field | Value |                     identifier, media kind, date (with the source's spelling when it differs), title,
|---|---|                             speaker or author, text, media link, venue, provenance, capture time, capture tool

## Metadata                            the free block, one row per key, sorted
| Key | Value |

## Files                               one row per file: name, role, bytes, SHA-256, how obtained (a derived file: from what, by what)
| File | Role | Bytes | SHA-256 | How obtained |

## Captures                            one row per capture: time, tool, status, note
| Captured | Tool | Status | Note |
```

Every table is a house table (header row, separator, rows), so the parser library reads a README as it reads a note (ledger.notes.tables).

### Metadata keys the adapters write

| Key | Meaning |
|---|---|
| date_basis | where the date came from (a meta tag, JSON-LD, a visible dateline, a catalogue column, the caller), or `none found` and what was searched |
| robots | the robots.txt verdict for the ledger's token and Claude-User, with each agent's deciding line |
| text_extent | which part of a web page text.md holds (the itemprop=articleBody element, the largest <article>, <main>, the whole page); page-full.md holds the whole page when they differ |
| canonical_url, page_title | the page's <link rel=canonical> when it differs from the URL asked for; its <title> when it differs from og:title |
| text_layer_origin, pdf_producer, pdf_creator, pages_with_image | a PDF's scan profile: born-digital, OCR text layer under page images (someone else's OCR), scan without a text layer, mixed |
| page_verdicts, page_sources | the per-page verdicts (good, index, low-words, garbled, empty) and where each page's reading text came from |
| witness | the second OCR of pages whose text layer is someone else's OCR: pages, mean agreement, the layer's words the witness does not match, substitutions (witness.json has them per page) |
| machine | the renderer and OCR backend available on the machine that held the item (what ran is in the capture tool) |
| media_links, media_status, transcription | a recording's links (every one, labelled), whether they were downloaded, and the transcription queued for them |
| class, circle | the item's source class and circle as the caller gives them (the pilot's intake fields); any caller metadata is kept as given |

Configuration (ledger.toml `[acquire]`): `hold_root` (default `sources`: the folder every hold goes under, so a pilot can hold under sources/pilot/ with the same names and caps), `state_dir` (default `.ledger/acquire`, shared by every session on the machine so their gates wait for each other), `agent_token` and `contact` (the user agent), `ocr_vision_bin`, `whisper_weights`.

## 4. Set holds, and the holds that predate this schema

A set hold is one folder for many items whose README is a table with one row per item, the form of books/sources/web/<set>/README.md:

- **Archive sets** (tools/ledger/acquire/bulk.py): `sources/archive/<set>/` with README.md, items.jsonl (the machine record, one line per item: identifier, file, bytes, sha256, url, captured, tool and the index row), `items/<id>.<ext>` byte-for-byte, FAILED.tsv for the last run, index.db (FTS5). A folder per item would be 12,000 folders for one release; the item's record lives in items.jsonl instead of a hold.json.
- **Databases** (tools/ledger/acquire/database.py): `sources/db/<database>/` with README.md (one row per record held), mapping.toml (the confirmed mapping, section 6), state.json (each record's row digest, the SHA-256 of its rows as read, for the scheduled re-read; a schema change such as a renamed column changes every record's digest, and the re-scan says so) and queue.tsv (new and changed records for intake); each record is an item hold below it, `sources/db/<database>/<table>-<key>-<title>/`, holding record.json.
- **Canon texts** (tools/ledger/acquire/canon.py): an item hold `sources/canon/<text id>/` with the text, units.jsonl and scheme.json.

The holds made before this schema keep their places and forms: transcripts/<YouTube id>.md, books/sources/ (text layers beside their PDFs, the first bulk archive's mirror, whose files carry a four-line header above the OCR, the web sets with hand-written README tables, Reddit captures). Phase 2's alias table (sources/aliases.tsv, tools/ledger/paths.py) resolves the layout's paths (sources/video/yt-<id>.md, sources/text/, sources/web/, sources/archive/<set>/, sources/sets/, sources/catalogues/) to where those files stand, without moving them. A new hold of an item already held there is not made unless asked (the YouTube adapter checks transcripts/<id>.md and its alias first).

## 5. The manifest row

Every hold() returns one row; a run writes them to a TSV with `base.write_manifest` (LF, tabs and newlines in cells made spaces):

| Column | Content |
|---|---|
| identifier, media_kind, title, date | from the record |
| hold | the hold folder, relative to the project root |
| status | new, unchanged, changed, failed |
| files, bytes | in the hold after this capture |
| captured, adapter | the capture time and the adapter |
| note | what changed, what failed and why |

## 6. Mapping a stranger's database (mapping.toml)

Setup stage 2 maps the group's tables onto these fields. `python3 tools/ledger/acquire/database.py propose <source>` writes a proposal; the group confirms or corrects it, sets `confirmed` and `confirmed_by`, sees five records held by `dry-run`, then runs it. Sections:

| Section | Content |
|---|---|
| `[mapping]` | version, database (the hold folder's slug), source (passwords redacted), engine, proposed, proposer, confirmed, confirmed_by |
| `[record]` | the record unit: table, key, order, where (an SQL condition), confidence, alternatives, why |
| `[fields.<field>]` | one per hold field: `column`; or `columns` with `split` (list fields); or `template` ("{first} {last}"); or `sql` (with `:key`); or `join` = {table, column, sep}; or `segments` = {table, key, order, start, duration, text, speaker, heading, description} (rendered in tools/fetch_transcript.py's form; `heading` a chapter-label column, written as `### <label>` lines; `description` a record-table column closing the transcript as the channel description block); or `value` (a constant); `value_map` and `default` for coded columns (`kind_code`: VID to video); `format`, `formats` (tried in order) and `ambiguous` for dates; `prefix` for the identifier; `fallback = "media_text"` (the text attachments: the first, or with `all = true` every one, named in hold.json as `texts`; a README, INDEX or MANIFEST file only when no other text is attached; else the local transcription of an audio or video attachment); a `template` with an empty placeholder yields nothing (`partial = true` to fill it with blanks). **Several sources:** `alternatives` as a list of tables (`[[fields.text.alternatives]]`, `[[fields.date.alternatives]]`) is the order the adapter tries per record, the first that yields a value winning (for the date: the first that parses, which sets the precision); a list of names under `alternatives` or `candidates` is the proposer's other candidates, shown and never read. Confidence, why |
| `[[media]]` | each media field: table, key, `path` (with `base_dir`, "." the database file's folder, else relative to the project) or `url` (recorded, fetched only where the network permits) or `blob`; `mime`; `transcribe` |
| `[[dates]]` | each date column with its format; target `date` (the field) or `metadata` (kept with its ISO form beside the raw value) |
| `[metadata]` | keep_unmapped (default true) and the columns kept: every record-table column no field takes, kept whole, promotable to pack keys |
| `[[annotations]]` | each table of the group's coding (claims, tags, speakers, relations, events): table, key, the register it is offered to (claims, people, relations, timeline, subjects), the columns for text, author, kind, date, attributed_to; teller "their database (<name>), table <t>"; reading "the group's reading". Offered for import at setup, never placed by the adapter |
| `[[ignored]]` | tables not read, with the reason |
| `[schema]` | the fingerprint (SHA-256 over tables, columns and declared types), the time of introspection, and per table its rows and columns: what `rescan` compares the live database with |

Text in several places (phase 6a, handoff H1): a catalogue that keeps a video's text in transcript rows, a web page's in a body column and a document's in attachments is mapped whole by one text field with three sources, segments, the body column, the attachments, tried in that order; the record's metadata says which was taken (`text_basis`).

Dates: a date split by precision across columns (a full date where known, else month and year, else the year: handoff H3) is one date field with sources in order, e.g. `{column = "published_on", format = "%m/%d/%Y"}`, `{template = "{pub_month} {pub_year}", format = "%b %Y"}`, `{column = "pub_year", format = "%Y"}`; `date_basis` in the metadata names the source and format taken, or, when none gave a date, what was empty and what did not parse. The source's spelling is kept as date_raw; the ISO form is YYYY-MM-DD, YYYY-MM or YYYY by the format's precision; when no value of a day-month-year column tells day-first from month-first, the column is marked `ambiguous` and every date whose day and month differ ends in `?` (the first archive index's swapped dates were the precedent).

## 7. Names, caps and line endings (wip/platform-phase1/sources-layout.md section 4)

| Rule | Value |
|---|---|
| Slug | ASCII, lower case, `[a-z0-9]+(-[a-z0-9]+)*`, cut at a word boundary; the full title stays in the record |
| Stem cap | 80 characters (a hold folder's name; a file's stem) |
| Basename cap | 96 characters with the extension |
| File name inside a hold | 64 characters (a longer original name is replaced by a role name, e.g. source.pdf, media-1-1.mp3, and kept in the file's `how`) |
| Path cap | 180 characters relative to the project root (80 characters of room under the Windows limit of 260); hold_path keeps 32 characters free for the file name |
| Reserved | `< > : " / \ | ? *` and control characters; no name ending in a space or a dot; no Windows device name (CON, PRN, AUX, NUL, COM1 to COM9, LPT1 to LPT9) as a stem; no name starting with `-` or `.` (a YouTube id is written `yt-<id>`) |
| Check | every new file's root-relative path goes through ledger.paths.name_problems before it is written; a breaking name fails the hold with the reason |
| Line endings | derived files, READMEs, hold.json, manifests: LF; held files: as obtained |

## 8. The shared text forms

- **Per-page text** (document.py, web.py threads): `--- page N ---`, a newline, the page's text; pages joined by a blank line (the later release files of the first project's document set; its earlier-release files use a single newline, and both are reproduced exactly by pypdf with the matching join). text-layer.txt is pypdf's text, ocr.txt the OCR of the pages that needed it (Apple Vision on macOS through tools/ocr_vision.swift, Tesseract elsewhere, the same form), text.txt the reading copy, pages.tsv which page came from where. Page verdicts: `empty`; `index` (a transcript's word index, page/line references: kept, never OCRed); `garbled` (junk characters or a failed decoding; on a page image also a low share of plain words); `low-words` (a born-digital page with few plain words and no junk: kept); `good`. A page whose text layer is someone else's OCR under a page image is read again by our OCR as a second witness: ocr.txt holds the witness, the reading text stays the layer, witness.json compares them word by word.
- **Transcript** (youtube.py, transcribe.py, database.py segments): tools/fetch_transcript.py's form: `# Transcript: <title>`, the lines `- Channel:`, `- URL:`, `- Uploaded:`, `- Captions:`, `- Length: ~HH:MM:SS, ~N words`, `---`, then paragraphs of about 120 words each opening with `**[HH:MM:SS]**`; a chapter heading, where the source has chapters, as a `### <label>` line before the paragraph that opens the chapter (the paragraph in progress closed first; heading words not counted), as the held transcripts with chapters have it; the channel description block (tools/fetch_description.py's: a rule, `## Video description (as posted by the channel)`, the description quoted line by line) closes it when the source has one. A database's segment rows render to this form byte for byte: the ten video records of phase 6a's stranger database reproduce the bodies of the held transcripts they were built from, chapters and description included.
- **Canon units** (canon.py): units.jsonl, one unit per line with its address, levels, first and last line in the held text, and text.

## 9. Where the adapters are

tools/ledger/acquire/README.md: the adapter list, what each wraps, its commands and tests.
