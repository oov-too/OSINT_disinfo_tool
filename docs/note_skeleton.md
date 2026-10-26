# tools/note_skeleton.py: the house form as a skeleton (2026-10-15)

## Why

Every intake brief (wip/intake-1008/brief-document.md, wip/adverse-1014/brief-adverse.md, wip/<video-run>/brief-video.md) told the agent to read two or three exemplar notes in full to copy their form (the active pack's exemplars, {{pack.exemplars}}; at the time a 74k-word document-set note, a 42k-word note on a forum post's source map, a 41k-word adverse note on two sceptical essays and a 50k-word note on a second forum post). Profiling put that at about 200,000 tokens per agent, re-read from cache on every one of about 145 turns: the largest avoidable cost in the workflow. The form those notes carry is what the agent needs, not their content. This tool writes the form as a skeleton of about 2,300 to 2,800 words (the table below), and the agent reads an exemplar only by section, where the skeleton leaves a form unclear.

Nothing structural is typed into the tool. The schema's section headings, column headers and count lines are parsed from tools/schema.md (sections 1 to 11, and the placement rule "placed before `## Open questions`" for the timeline); every heading, table header, sub-heading, quote item and example row is parsed from the exemplar notes. The tool only selects which exemplar supplies which section (the `FORMS` table at its top; which notes are the exemplars is pack data, {{pack.exemplars}}); a selected heading that an exemplar no longer carries, or an exemplar table whose header differs from the schema, stops the tool with an error rather than writing a skeleton that drifts.

## Usage

```
python3 tools/note_skeleton.py --form document|adverse-web|adverse-forum|video|text --task wip/<task> \
        [--note books/<planned>.md] [--source <held file or folder> ...] [--stdout]
python3 tools/note_skeleton.py --check <note.md> [--form <form>]
python3 tools/note_skeleton.py --sizes
```

`--task` names the agent's wip folder (created if absent); the skeleton is written to `wip/<task>/skeleton.md` and the size printed. `--note` is the planned note path, used for the relative links (books/ or videos/). `--source` is the held copy: for `video` the transcript (`transcripts/<id>.md`); for the document forms one or more held files or a folder (every .txt, .md, .htm counts toward words; every .pdf toward pages). `--stdout` prints instead of writing. `--sizes` prints the size of every form's skeleton with no sources.

## The forms

| Form | Heading order from | Form sections (beyond schema sections 2 to 11) and their suppliers | Example-row pool after the form's own exemplars |
|---|---|---|---|
| document | the document primary | One-paragraph summary; How the set is built (header from the second document exemplar, whose `Document` column is the generic one; the primary's says `Document (<archive number>)`); The documents, one by one (the first `### N. title (id)` sub-heading as an example); What this settles, and what it does not (from the second document exemplar; the primary lacks it); the grid trio | the second document exemplar, the second adverse-web exemplar, the adverse-web primary |
| adverse-web | the adverse-web primary | the document form's sections plus What this contests (header from the adverse-forum primary, whose `Adverse claim (this note)` column is generic; the adverse-web primary's column names its author, `<author>'s rows`); What it concedes; Who hosts, who relays, who answers; Echo watch; the grid trio from the document primary | the adverse-forum primary, the second adverse-web exemplar, the second document exemplar |
| adverse-forum | the adverse-forum primary | How the set is built; The documents, one by one; What this contests; What it concedes; Who hosts, who relays; Divergences, read four ways; What this settles, and what it does not; Echo watch; the grid trio from the document primary. Per-post row sets: the Time cell is the post id (`<forum initials> <post number>`), the Speaker the poster's handle, as the lifted claims row shows | the adverse-web primary, the second adverse-web exemplar, the second document exemplar |
| video | the video primary | One-paragraph summary; Key claims and ideas; the grid trio from the second video exemplar (the video form's grid is a matrix whose columns the recording itself supplies; the trio's other two sections carry the fixed headers the pack's video notes use) | the second video exemplar, then the document exemplars |
| text | the text primary | One-paragraph summary; How the post is built; Verification of every citation; The post's chronology as dated claims; What the ledger holds that the post does not use; Who hosts, who relays; Divergences, read four ways; Echo watch; the grid trio | the second text exemplar, then the document exemplars |

Core default forms (2026-10-22): a pack that names no `[skeleton] forms` has no exemplar notes yet (a new pack's first intake), and the tool then offers `video`, `document` and `text` built from tools/schema.md alone. They carry the metadata block with the schema's own descriptions as placeholders, every schema section in order with the schema lines that define it, each table's header, the count lines and the empty-table lines, and no example rows. The audit and object-watch headings are the pack's (`[audit] heading`, `[objects] watch_heading`), and `--check` accepts them. Free sections (schema section 12) are left to the brief. A pack's exemplar-based forms, where it names them, override these.

The exemplars are named here by role: each form's primary (the note its heading order comes from) and the second exemplar of a form, which supplies a header or pool rows; which notes fill the roles is the active pack's data ({{pack.exemplars}}). The grid trio is the three free sections the pack's briefs require ({{pack.free_sections}}); the tool lifts them like any form section.

The schema sections come in the primary exemplar's order (Claims ledger, Forthrightness audit, People, Works, Object watch, Notable quotes, Dated timeline, Open questions, Cross-checks; Tracker candidates where the primary has it, since schema section 8 is optional). A form section the primary lacks is inserted after the nearest preceding wanted heading of the exemplar that supplies it. Under each heading a comment gives the schema section number (or `form section`) and the exemplar's line range for that section, so an agent who needs the full form of one section reads it with the Read tool on that range (offset and limit) and nothing else. The forthrightness audit (schema section 3, emitted as `## Forthrightness audit`) carries the exemplar's `### (a)` to `(g)` sub-headings (free-form by schema section 3, but they must cover the listed points); where the primary has none (as the document primary had none when this was written), the first exemplar of the form that has them supplies them.

## What is filled

The metadata block has every key of schema section 1 in order, plus the trailing `Authors` key that every document-form exemplar carries. `Added to notes` is today. For `video` with `--source transcripts/<id>.md`: Channel, URL, Uploaded and Length (`Hh Mm Ss` from the header's `Length:` line) are read from the transcript header, Transcript is the relative link, and Description is the first paragraph of the `## Video description` block as a candidate (the agent checks it is the first substantive one and says what boilerplate was skipped); the header's `Source:` line (an owner's paste rather than captions) and the transcript title are echoed in comments. For the document forms with `--source`: Length is the page count over the PDFs (macOS `mdls`, else a count of page objects, marked approximate) and the whitespace word count over the text files, file by file; Transcript lists the held copies as links with the scans beside them. Everything else is a placeholder in angle brackets carrying the schema's or the brief's convention for that key (brief-document.md "Metadata for documents").

Each table carries two example rows lifted verbatim from an exemplar table with the same header, with ` <!-- example row, delete -->` appended inside the last cell (inside, so a row left behind still parses as one row and `--check` finds it). Rows are chosen by marker, in priority order, each priority contributing one row: the Claims ledger a `program-record` row with `attribution:` and `chain:` and then a `[first telling: FU-n]` row, a `document claimed, not named` row, a `(pseudonym)` hop, a `[div: ...]` tag or a `corroboration 2:` sub-chain; the forthrightness audit a redaction wall (`redacted: <exemption>` in Basis) and a pseudo-decline, then a closed-outright or stated-decline row; the Dated timeline a `contradicts:` row with its `[div: ...]` tag and a `[first telling:]` row, then a `matches` row; Cross-checks a `contradicts` row with `point:` and the tag, then `answers`, `extends` or a `custody:` line; Open questions a `checked` then an `open` row; Object watch a `candidate` then a `nil` row. The section's own exemplars are searched first, then the form's pool, then every exemplar, so at least one row is in the form's own style (its Time cells, its voices) and the marked rows the form's exemplars lack (a redaction wall in a video form) still appear; among matches the shortest row over 120 characters is taken, to keep the skeleton small. Notable quotes carries the exemplar's first two items marked `<!-- example item, delete -->`. The Audit counts and Object vocabulary lines are the schema's own forms, with N for each number.

## --check

`--check <note.md>` reports, against tools/schema.md: the metadata keys (present, in schema order, missing ones allowed only for Host, Guest, Recorded, Description; trailing keys after Transcript listed); the schema sections present (by exact heading, with a warning where only the parser's prefix match finds one, as `## People roster` would), missing, and out of order (the longest in-order run is kept and the rest reported, against the order Claims ledger > Forthrightness audit > People > Works > Object watch > Notable quotes > Tracker candidates > Dated timeline > Open questions > Cross-checks); each schema table's header against the schema's cells; the Audit counts and Object vocabulary lines; the empty-table lines for Open questions and Cross-checks; the form's own sections (form given with `--form`, else detected: videos/ is `video`, "How the post is built" is `text`, "What this contests" with a thread in Channel or Guest is `adverse-forum` and otherwise `adverse-web`, else `document`); and any `<!-- example` mark left from the skeleton. Schema gaps and leftovers fail (exit 1); absent form sections fail only when `--form` was given, and are otherwise reported. A `Status` metadata key is reported as a warning (a note in progress).

The exemplars and the two recent notes all pass (2026-10-15). The outputs are the real ones, with each note's path replaced by its role and shape in angle brackets and the pack's three free sections by `<grid trio>`:

```
books/<document primary: a document-set note on an archive's process documents, 74k words>.md: form document (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 9 of 10 present (Tracker candidates optional, absent); order ok
table headers: ok
count lines: ok
form sections (document): 5 of 6 present; absent: What this settles, and what it does not
RESULT: PASS

books/<text primary: a note on a forum post's source map, 42k words>.md: form text (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 9 of 10 present (Tracker candidates optional, absent); order ok
table headers: ok
count lines: ok
form sections (text): 10 of 10 present
RESULT: PASS

books/<adverse-web primary: a note on two sceptical essays, 41k words>.md: form adverse-web (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 10 of 10 present; order ok
table headers: ok
count lines: ok
form sections (adverse-web): 7 of 10 present; absent: <grid trio>
RESULT: PASS

books/<second text exemplar: a note on a second forum post, 50k words>.md: form text (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 9 of 10 present (Tracker candidates optional, absent); order ok
table headers: ok
count lines: ok
form sections (text): 10 of 10 present
RESULT: PASS

books/<second adverse-web exemplar: a note on two magazine articles, 33k words>.md: form adverse-web (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 9 of 10 present (Tracker candidates optional, absent); order ok
table headers: ok
count lines: ok
form sections (adverse-web): 6 of 10 present; absent: Who hosts, who relays, who answers, <grid trio>
RESULT: PASS

books/<second document exemplar: a document-set note on 37 released research papers, 39k words>.md: form document (detected); schema v1.3
metadata: 13 of 13 schema keys; trailing: Authors; order ok
schema sections: 9 of 10 present (Tracker candidates optional, absent); order ok
table headers: ok
count lines: ok
form sections (document): 3 of 6 present; absent: <grid trio>
RESULT: PASS
```

The skeleton itself fails `--check` by design (its example rows, and the N placeholders in the Audit counts line): the check is for the finished note.

## Sizes (measured 2026-10-15, `--sizes`, no sources)

| Form | Bytes | Words | Lines | Tokens (bytes/4) |
|---|---|---|---|---|
| adverse-forum | 17,354 | 2,733 | 193 | about 4,338 |
| adverse-web | 16,307 | 2,597 | 186 | about 4,074 |
| document | 14,287 | 2,311 | 163 | about 3,571 |
| text | 17,242 | 2,805 | 188 | about 4,303 |
| video | 15,597 | 2,453 | 155 | about 3,896 |

Against about 200,000 tokens of exemplar reading per agent, cached and re-read on every turn.

## Limits

- The video form's grid (the first section of the grid trio) is lifted from the second video exemplar, so its columns are that recording's; the agent replaces them with the recording's own. The trio's other two headers are the fixed ones.
- "The documents, one by one" lifts only its first sub-heading as an example, not the exemplar's per-document tables (they belong to those documents).
- `What this settles, and what it does not`, `What it concedes`, `Echo watch`, `Divergences, read four ways` and the `One-paragraph summary` are prose in the exemplars, so the skeleton gives the heading and the exemplar's line range only.
- The Description candidate for a video is the first paragraph as held, which may include channel boilerplate; the comment says to check it.
- The brief's run-specific free sections (a section on the recording's people and `## Series and dating` in one video run) are the brief's, not the form's, and are not in the skeleton.
- Page counts need the PDFs beside the text; OCR text files give words only.

## The brief change (prepared, not switched)

wip/intake-1008/brief-document.next.md and wip/<video-run>/brief-video.next.md are copies of the live briefs in which the one exemplar-reading sentence of the "Read first" paragraph is replaced by: run `python3 tools/note_skeleton.py --form <form> --task wip/<task> --note <note> --source <held path>`, work from `wip/<task>/skeleton.md`, read an exemplar only for a section whose form the skeleton leaves unclear, by section (`python3 tools/narratives.py --section` is for narrative pages; use `sed -n` on the exemplar's heading range the skeleton's comment gives), and run `--check` before finishing. Every other line is unchanged (`diff` shows one line each). The live briefs stay as they are until the five running intake agents finish; the orchestrator renames the `.next.md` files over them for the next run, and wip/adverse-1014/brief-adverse.md needs the same sentence pointed at `--form adverse-web` or `--form adverse-forum`.
