# Form brief: document intake (core template, platform phase 4, 2026-10-22)

Template, rendered by the skill with the pack's and the run's slot values into `wip/<run>/briefs/intake-document.md`. Merged from wip/intake-1008/brief-document.md and its .next copy (the .next copy's skeleton, units, generated-parts and timeline pre-pass paragraphs are the default path here; the exemplar reading of the live copy survives only as reading by section). Read with intake-standing.md (the standing rules, the pre-pass files, checkpoint, blocked output, the base report keys) and operations.md; with intake-adverse.md when the source is adverse.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.exemplars.document}}` | the pack's exemplar note for a document set, with what to copy from it | the skeleton alone |
| `{{pack.exemplars.text}}` | the pack's exemplar note for a single text (a post, an article) | the skeleton alone |
| `{{pack.free_sections.document}}` | free sections the pack's document notes carry beyond the schema | none |
| `{{pack.narratives}}` | the narrative pages a note is keyed to, and how to find their rows | the narrative register (research/narrative-register.md) |
| `{{pack.report_keys.document}}` | the report keys the pack adds to a document report | none |
| `{{run.label}}`, `{{run.date}}` | (run, from the run brief) the run's label and its intake date | |
| `{{run.purpose}}` | (run) why the run exists, in one or two sentences | none |
| `{{run.brief}}` | (run) the run brief's path, whose run-specific items bind with this one | none |

You write one note in the house schema for one held document or document set, in the **document form**: tools/schema.md v1.3 sections 1 to 11, as the exemplars apply them to a document rather than a recording. Run {{run.label}} ({{run.date}}). {{run.purpose}} Your note is what the next narrative run will read. The run brief {{run.brief}} binds with this one.

## Read first, in this order

intake-standing.md (all of it); operations.md; tools/schema.md (all of it) with the pack's schema extensions; tools/agent-wip.md (checkpointing, mandatory); tools/filter-blocks.md section 5; then `wip/<task>/TASK.md` and `wip/<task>/skeleton.md`, the note's form (made by `ledger prepare skeleton --form document --task wip/<task> --note <note> --source <held path>`; `--form text` for a single post or article; `--form adverse-web` or `--form adverse-forum` under intake-adverse.md). The skeleton's example rows come from the pack's exemplars: {{pack.exemplars.document}}; {{pack.exemplars.text}}. Read an exemplar only for a section whose form the skeleton leaves unclear, by section (the line range the skeleton's comment under each heading gives, with the Read tool). Copy their forms; do not invent new section shapes. Before you finish, `ledger prepare skeleton --check <note> --form <form>` must pass (tools/note_skeleton.md).

## Two paths

- **Staged intake (the default):** the orchestrator runs the pre-pass (intake-standing.md, "The pre-pass files") and launches `tools/workflows/staged-intake.js` with the phase briefs of this folder's `staged/` (read, write, finish). Each phase agent reads this brief for the form and does only its phase's part of it; the reader writes findings per unit, the writer builds the note from the findings and the pre-pass files and never reads the source whole (it pulls the source's words by the findings' pointers with `ledger quote`), the finisher runs the checks and the cross-checks.
- The shipped intake form is the unit writers (one writer per unit range with the unit in its context, then writer B and the finish; the staged read-and-writer-A form is kept as `form: "staged"` for comparison, and the check phase is optional). A single agent writing a whole note from a source in its context is not shipped: on the six-form measurement of 2026-10-24 it failed a third to a half of its quotations against the held text, and no gate made it correct them.

## What each note must do for the narratives

Beyond the schema, each note carries one section `## What this settles, and what it does not`, keyed to the narrative pages ({{pack.narratives}}): for each ledger row of a narrative page that cites this document or its subject (search the narrative pages for the document's name, number or the people in it, with the Grep tool or `ledger analyse rows`), say what the document's own text supports, which side of the contradiction it favours and on what words, and what it leaves open. Cite the narrative page and ledger row number. This is the section the next narrative run reads first.

The pack's own free sections for a document note: {{pack.free_sections.document}}

## Two rules for every document note (owner, 2026-10-23)

- **Cited-source scope** (the intake policy's rule 7). The ledger rows what this source says, including what it says a cited work says (class `read`, the chain naming the work). A source's own citations (the articles, documents, posts and books it cites, quotes or links, held beside it or not) are verified against and recorded: in Works, with what the source takes from each and whether the cited work bears it out where it is held, in the claim's chain, and as first-telling or lead candidates (`cited_sources_not_held` for those the project does not hold). They are never rowed as the cited work's own claims, timeline or audit. A cited work that matters comes in as its own intake under the intake policy (documents when cited), queued in `chain_leads`, unless TASK.md or the run brief ({{run.brief}}) names it as a source of the intake. (The round-trip measurement of 2026-10-23 rowed every cited source of a web article as its own claims: 818 claims rows against the original's 92; wip/platform-phase6a/REPORT.md section 9, finding 18.)
- **No transformation no brief states.** The findings and the quotations reach the note as the briefs say: no filter of the writer's own ("notable items only"), no quotation cut to a length inside its quotation marks (shortening is by `...`), no items merged or dropped to fit a size. A writer that generates rows by script keeps the script under `wip/<task>/` and names it, with what it does, in its reply. (The same measurement found a writer's script quoting only "notable" items and cutting quotations over 32 words; finding 11.)

## Metadata for documents

Keys and order as schema section 1, with the document conventions of the exemplar: Channel = the issuing body or publisher; Host = none (with the issuing office or author named in the parenthesis); Guest = none (the documents listed); Speakers = every office, author and quoted person who speaks in the document; URL = the original; Uploaded = the release or publication date; Recorded = the documents' own dates; Length = pages and words; Added to notes = {{run.date}}; Subjects; Description = the document's own opening or cover words, quoted; Tags; Transcript = the held copy's path (TASK.md names it, and the pdf beside it where one exists); a trailing Authors key as the exemplar. The derivable keys are generated (intake-standing.md, "Generated parts").

## Report (`wip/<task>/report.json`, built incrementally)

The base keys of intake-standing.md, and for a document: `{"file": "<note path>", "subject_rows": {"<subject page stem>": "| <uploaded> | [<title>](../<note path>) | <speakers> | <what it adds> |"}, "register_new": [...object register rows or []], "register_updates": [], "relations": [...], "chain_leads": [...], "answered_questions": [...], "timeline_rows": N, "claims_rows": N, "audit_counts": "...", "cited_sources_not_held": [...], "narrative_rows_addressed": [{"page": "...", "row": N, "favours": "...", "on": "..."}], "blocked_passages": [], "notes": "..."}` with the pack's keys added ({{pack.report_keys.document}}). `ledger extract report-check wip/<task>/report.json --form intake-document` must pass.
