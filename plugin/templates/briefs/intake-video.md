# Form brief: recording intake (core template, platform phase 4, 2026-10-22)

Template, rendered by the skill with the pack's and the run's slot values into `wip/<run>/briefs/intake-video.md`. Merged from wip/intake-1008/COMMON.md (the common brief of standard video intakes) and wip/<video-run>/brief-video.md with its .next copy (the .next copy's skeleton paragraph and verbatim-check rule are the default here). The run-specific matter of those briefs (a series, an exercise, the people a run asks about) is the run brief's: the live video run's brief is now the pack's example run brief. Read with intake-standing.md and operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.exemplars.video}}` | the pack's exemplar recording note, with what to copy from it | the skeleton alone |
| `{{pack.free_sections.video}}` | free sections the pack's recording notes carry beyond the schema (grids, entities, effects) | none |
| `{{pack.free_sections.teller}}` | the free sections for a recording whose main speaker already speaks in held notes, with the pack's exemplars of them | the three sections named below |
| `{{pack.report_keys.video}}` | the report keys the pack adds to a recording's report | none |
| `{{pack.subjects}}` | the subject pages a note may name, with what each covers | the project's subject pages (subjects/) |
| `{{run.label}}`, `{{run.date}}` | (run) the run's label and its intake date | |
| `{{run.brief}}` | (run) the run brief: the recordings, why the run exists, the run's own free sections and report keys | none |

You write one recording note in the house schema (tools/schema.md v1.3, sections 1 to 11, the video form) for one recording, under run {{run.label}} ({{run.date}}). The run brief {{run.brief}} names the recording or series, why the run exists, the held threads and passages that matter, and the run's own free sections; it binds with this brief.

## The owner's request

The owner names a recording (a URL); the standard procedure applies: the transcript and description are fetched by the orchestrator (`ledger acquire video`, rate-limited; never fetch from a video platform yourself), one intake (staged by default, intake-document.md "Two paths" applies to recordings as well) writes the note in the house schema, the orchestrator integrates it. `wip/<task>/TASK.md` names the recording, the note file, the short label, the subjects, the held threads and the passages the owner cares about.

## Read first, in this order

intake-standing.md (all of it); operations.md; tools/schema.md (all) with the pack's schema extensions; tools/agent-wip.md (checkpointing, mandatory); tools/filter-blocks.md section 5; the run brief; `wip/<task>/TASK.md`; then `wip/<task>/skeleton.md` (made by `ledger prepare skeleton --form video --task wip/<task> --note <note> --source <transcript path>`): the metadata block in schema order with Channel, URL, Uploaded, Length, Transcript and the Description candidate filled from the transcript header, every section heading in the video form's order, every table's header row, and two example rows per table lifted verbatim from the exemplar ({{pack.exemplars.video}}), each marked `<!-- example row, delete -->`. Do not read the exemplar in full; read it only for a section whose form the skeleton leaves unclear, by section (the line range the skeleton's comment gives, with the Read tool). Before you finish, `ledger prepare skeleton --check <note> --form video` must pass (tools/note_skeleton.md).

## The recording

The transcript is the held transcript TASK.md names: the header carries title, channel, upload date and length, and the `## Video description` block at the end carries the channel's description (the Description metadata row quotes its first substantive paragraph, skipping sponsor, merch and link boilerplate, and says what was skipped). Where the transcript came from the owner's paste rather than captions, the header says so; timestamps are the paste's. Units are cut by timestamp (`ledger prepare chunk <transcript> --wip wip/<task>`).

## The forthrightness audit for a recording

Interview form: every party who asks and answers; mark reverse questions; stated declines, pseudo-declines; the Audit counts line (generated) and one explanatory line. A monologue or a narrated compilation takes the monologue mapping, stated under the counts line.

## The teller across the ledger (every recording whose main speaker already speaks in held notes)

TASK.md names the held notes where this recording's main speaker already speaks. Three free sections ({{pack.free_sections.teller}}): what no held telling of this speaker contains (claim | time | what the earlier sources had instead | class; checked by `ledger analyse rows` and by reading); the standard audit with the Audit counts line, with every divergence between this recording and an earlier or later held telling argued through the four classes (honest / honest mistake / disinformation / state sanctioned) before one is chosen, and what would change it, and the host's framing; and the corroboration inside the database (item | corroborating mouth and row | independent? | strength; chain and independence judged; echo check).

## Standard items in every recording note

Metadata with the Description row; the forthrightness audit; Claims ledger with attribution and chain on every non-firsthand row; People (every named person, caption variants); Works (every book, film, paper, article, page, institution); the object watch (intake-standing.md); the pack's free sections for recordings ({{pack.free_sections.video}}); Notable quotes; Dated timeline (every date the source states, permanent decimal IDs, Sortable, Agreement against the era pages and against the held notes, ruled from timeline-candidates.md); Open questions (Asked by `note`, with tests); `## Cross-checks` filled from the onboarding check (intake-standing.md); relations rows for every tie; the actor and polity rows; the echo watch; the speaker ledger note; the forthrightness chart data; the Audit counts line.

## Subjects

One subject row per page the recording bears on, from the pack's subject pages ({{pack.subjects}}) and the run brief's guide to them. Do not create a subject page.

## Reply

JSON only (also saved as report.json): the base keys of intake-standing.md and the video form's keys, `{"recorded_date" (with basis), "new_items", "forthrightness_comparison", "four_class_readings", "corroborations"}` (the last four when the teller section applies; the key names are the integrator's and stay as they are), the run brief's keys, and the pack's ({{pack.report_keys.video}}). `ledger extract report-check wip/<task>/report.json --form intake-video` must pass.
