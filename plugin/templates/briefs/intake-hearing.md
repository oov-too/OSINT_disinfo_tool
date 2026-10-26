# Form brief: hearing-day intake (core template, platform phase 4, 2026-10-22)

Template, rendered by the skill with the pack's and the run's slot values into `wip/<run>/briefs/intake-hearing.md`. The hearing-day variant of intake-video.md, for the transcript of one day of a public hearing, an inquiry or a court: there is no channel, no upload date, no captions and no timestamps; the venue publishes a numbered transcript (page and line), a hearing page with the day, phase, date and reference number, and recordings that may or may not be held. Every standing rule of intake-standing.md and every slot of intake-video.md binds unchanged; only the recording's description, the metadata conventions, the unit cut and the citation form differ. Read with intake-standing.md and operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.exemplars.hearing}}` | the pack's exemplar hearing-day note, with what to copy from it | no exemplar: the skeleton's video form and this brief |
| `{{pack.exemplars.video}}` | the pack's exemplar recording note, for the sections a hearing note shares with it | the skeleton alone |
| `{{pack.free_sections.video}}` | free sections the pack's recording notes carry beyond the schema | none |
| `{{pack.free_sections.teller}}` | the free sections for a witness who already speaks in held notes, with the pack's exemplars of them | the three sections named below |
| `{{pack.report_keys.video}}` | the report keys the pack adds to a recording's report (a hearing day reports in the video form) | none |
| `{{pack.subjects}}` | the subject pages a note may name, with what each covers | the project's subject pages (subjects/) |
| `{{run.label}}`, `{{run.date}}` | (run) the run's label and its intake date | |
| `{{run.brief}}` | (run) the run brief: the hearing days, why the run exists, the run's own free sections and report keys | none |

You write one note in the house schema (tools/schema.md v1.3, sections 1 to 11, the video form with the hearing conventions below) for one hearing day, under run {{run.label}} ({{run.date}}). The run brief {{run.brief}} names the day or days, why the run exists, the held threads and passages that matter, and the run's own free sections; it binds with this brief.

## The owner's request

The owner names a hearing day (the venue's hearing page, or its transcript); the orchestrator holds the venue's transcript, the hearing page and the links to the recordings (the document adapter `ledger.acquire.document` for the transcript and the page, run as `ledger acquire document` once the command routes it, wip/platform-phase6b/handoffs.md item 13; a recording is linked, not fetched, unless the run says to transcribe it locally). One intake (staged by default, intake-document.md "Two paths") writes the note; the orchestrator integrates it. `wip/<task>/TASK.md` names the day, the note file, the short label, the subjects, the held threads and the passages the owner cares about.

## Read first, in this order

intake-standing.md (all of it); operations.md; tools/schema.md (all) with the pack's schema extensions; tools/agent-wip.md (checkpointing, mandatory); tools/filter-blocks.md section 5; the run brief; `wip/<task>/TASK.md`; the hold's README (the generated description of the hold: identifier, venue, date, title, provenance, the media links, the text basis); then `wip/<task>/skeleton.md` (made by `ledger prepare skeleton --form video --task wip/<task> --note <note> --source <transcript path>`): the video form's headings and table headers, with the metadata cells the skeleton cannot derive from a hearing transcript left as placeholders for you to fill from the hold (section "Metadata for a hearing day"). The exemplars are {{pack.exemplars.hearing}} and, for the sections a hearing note shares with a recording note, {{pack.exemplars.video}}; read either only for a section whose form the skeleton leaves unclear, by section, with the Read tool. Before you finish, `ledger prepare skeleton --check <note> --form video` must pass (tools/note_skeleton.md).

## The hearing day

The transcript is the held transcript TASK.md names (the venue's own text where it publishes one, the PDF's text layer kept beside it as a second witness; the hold's README says which is the text basis). It opens with the day's date and the sitting time, then numbered lines, 1 to 25 a page in the usual court form, with the page number on a line of its own; speakers are marked by role and name as the transcript gives them (the chair, counsel to the inquiry or to a party, the witness), and the sitting times it records (`(10.00 am)`, `(Adjourned)`) are the only clock it has. The day's header facts come from the venue's hearing page and the hold: the day's number, the phase, the date, the transcript's reference number, the recordings. A word index at the end of a transcript (pages of words with page:line references) is not testimony: leave it unread and say so in the Description cell.

Units are cut by page (`ledger prepare chunk <transcript> --wip wip/<task> --by page`), so that a unit is a run of whole transcript pages and its header names them. Where the chunker does not recognise the form (it reports no markers and cuts by paragraph), the units still hold the exact text; the unit header then gives file lines only, and you read the transcript's own page and line numbers inside the unit for every citation.

The citation form is the transcript's own: page and line, `159:24`, a range `159:24 to 160:3`. It takes the place of the h:mm:ss timestamp everywhere the schema puts a time (the Time cell of claims, audit, object-watch and timeline rows, the quote items `N. (159:24) "quote"`, the `blanket declaration at` and `venue named at` forms of schema section 2), and it is never written as a clock time. Each row still carries its unit pointer `[u NNN:L]` at the end of its Note cell, as on every staged intake.

## Metadata for a hearing day

Keys and order as schema section 1, with the hearing conventions of its parser rules ("A hearing: Host is the chair, Guest lists the witnesses, Speakers lists every member"):

| Key | A hearing day |
|---|---|
| Channel | the venue: the inquiry, tribunal or court, as it names itself |
| Host | the chair (the judge, the chair of the inquiry or the panel) |
| Guest | the witness or witnesses who give evidence that day |
| Speakers | every voice the transcript marks, by name with the role it gives (the chair, counsel to the inquiry, counsel for a party, the witness, a panel member, an assessor), comma separated |
| URL | the venue's hearing page for the day |
| Uploaded | the date the venue published the transcript, where its page gives one; else the hearing date, with `(hearing date; no publication date given)` |
| Recorded | the hearing date, with its basis (the transcript's first line, the hearing page) |
| Length | the transcript's pages and words (`79 pages, 42,034 words`), and the sitting times it records; never a clock length invented from them |
| Added to notes | {{run.date}} |
| Subjects | links to subject pages ({{pack.subjects}}) |
| Description | the hearing page's own description of the day, quoted; say what was left out (the word index, procedural boilerplate) |
| Tags | comma-separated |
| Transcript | the held transcript's path, and the PDF beside it where one is held |
| Hearing | the one trailing key schema section 1 allows: `Day <n>; <phase>; <reference number>; recordings: <links, and whether each is held>; citations are page:line of the transcript` |

In a casebook example, a note on Day 12 of the Harrowmere Inquiry has Channel `the Harrowmere Inquiry`, Host `Judge Imelda Corrin`, Guest `Petra Vanecek`, Speakers `Judge Imelda Corrin (chair), Ms Adair (counsel to the inquiry), Petra Vanecek (witness)`, Recorded `2019-11-05 (the transcript's first line)`, and Hearing `Day 12; the construction phase; HI-T012; recordings: two sessions, linked, not held; citations are page:line of the transcript`; a claim she makes on page 59, line 12 has Time `59:12`.

## The forthrightness audit for a hearing day

Interview form, with the hearing's turn-taking: Asked by names the questioner by role and name (counsel to the inquiry, counsel for a party, the chair); every question put and answered or declined is a row; a witness's question back to counsel is a reverse question; stated declines, pseudo-declines; an objection by counsel or a ruling by the chair that stops a question is recorded in the row's Note with who stopped it and on what ground (a wall placed by the venue or a party, not a decline by the witness); the Audit counts line (generated) and one explanatory line. A day of submissions with no witness takes the monologue mapping, stated under the counts line.

## The teller across the ledger (every witness who already speaks in held notes)

TASK.md names the held notes where the day's witness already speaks (an earlier statement, an interview, an earlier day). Three free sections ({{pack.free_sections.teller}}): what no held telling of this witness contains (claim | page:line | what the earlier sources had instead | class; checked by `ledger analyse rows` and by reading); the standard audit with the Audit counts line, with every divergence between this day and an earlier or later held telling argued through the four classes (honest / honest mistake / disinformation / state sanctioned) before one is chosen, and what would change it, and the questioner's framing; and the corroboration inside the database (item | corroborating mouth and row | independent? | strength; chain and independence judged; echo check).

## Standard items in every hearing-day note

Metadata as above; the forthrightness audit; Claims ledger with attribution and chain on every non-firsthand row (a document put to the witness on screen and read from is `read`, chained to the document by its reference number; the witness's own recollection of it is a separate row); People (every named person, with the spellings the transcript uses); Works (every document the day names, with its reference number, and every exhibit put to the witness); the object watch (intake-standing.md); the pack's free sections for recordings ({{pack.free_sections.video}}); Notable quotes; Dated timeline (every date the day states, permanent decimal IDs, Sortable, Agreement against the era pages and against the held notes, ruled from timeline-candidates.md); Open questions (Asked by `note`, with tests; a question counsel puts and the day leaves open is `video: <speaker, page:line>`); `## Cross-checks` filled from the onboarding check (intake-standing.md); relations rows for every tie; the actor and polity rows; the echo watch; the speaker ledger note; the forthrightness chart data; the Audit counts line.

## Subjects

One subject row per page the day bears on, from the pack's subject pages ({{pack.subjects}}) and the run brief's guide to them. Do not create a subject page.

## Reply

JSON only (also saved as report.json): the base keys of intake-standing.md and the video form's keys, `{"recorded_date" (with basis), "new_items", "forthrightness_comparison", "four_class_readings", "corroborations"}` (the last four when the teller section applies; the key names are the integrator's and stay as they are), the run brief's keys, and the pack's ({{pack.report_keys.video}}). `ledger extract report-check wip/<task>/report.json --form intake-video` must pass.
