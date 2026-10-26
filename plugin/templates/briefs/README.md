# Brief templates

The intake and narrative briefs as core templates with named slots; the plugin's skills load them. Nothing here names a corpus: every domain value is a slot, filled from the active pack's `briefs/slots.toml` (packs/<pack>/briefs/slots.toml, written by /setup stage by stage), with the core default of slots-default.toml where a pack gives none. Run values (`{{run.*}}`) come from a run's TOML beside its run brief; project values (`{{ledger.*}}`) from ledger.toml and the project folder.

| Template | What it is | Read with |
|---|---|---|
| operations.md | the shell idioms every brief uses, in the ledger's command form | every template |
| intake-standing.md | the standing rules of every intake | the form brief |
| intake-document.md | the intake of a document, a document set or a web text | intake-standing.md |
| intake-video.md | the intake of a recording; the run's own matter is in the pack's run brief | intake-standing.md |
| intake-hearing.md | the hearing-day variant of intake-video.md for transcripts of hearings, inquiries and court days (no channel, upload date, captions or timestamps; units by page; page:line citations; speakers by role) | intake-standing.md |
| intake-adverse.md | the intake of an adverse source (a text that disputes a circle's reading) | intake-standing.md, intake-document.md |
| staged/README.md, read.md, write.md, finish.md | the staged intake: read, gate, write, gate, finish | intake-standing.md and the form brief |
| narrate/README.md and eight phase briefs | the narrative workflow's phases | the step briefs of narrate/ |
| narrate/brief-builder.md, brief-synchrony.md, brief-revise.md, brief-attack.md, brief-fork.md, brief-register.md | the narrative workflow's step briefs; the run's own matter is in the pack's run brief | the phase briefs of narrate/ |

## The default path and the named alternative

The pre-pass (units by chunk_source, skeleton.md by note_skeleton, context.md by context_pack, timeline-candidates.md by timeline_prepass) and the generated parts (note_fill) are the default for every intake (intake-standing.md, "The pre-pass files and the generated parts"). The staged intake (staged/) is the default path; the single-agent intake (one agent from the first unit to the report, under guarded-intake.js, with the same pre-pass files and generated parts) is kept as the named alternative (intake-document.md, "Two paths"). The plan makes staged intake the default "once measured": it has not run live yet (tools/intake-staged.md), so the switch is the owner's.

## Rendering

`python3 tools/ledger/briefs.py render --pack packs/<pack> --run packs/<pack>/briefs/runs/<run>.toml [--only <prefixes>] [--out <dir>]` writes the run's rendered briefs (the slot tables stay as written; every other `{{...}}` is filled; it exits 1 naming any slot without a value). `--defaults-only` renders with the core defaults alone, as a recipient's empty pack would. The orchestrator passes the rendered `staged/` folder to tools/workflows/staged-intake.js as `phasesDir`, and names the rendered narrate briefs in the prompts tools/workflows/staged-page.js receives; no workflow script changes. `ledger brief render` will be this script inside the command.

## Pack slots (every slot of every template)

| Slot | What it holds | Used in |
|---|---|---|
| `{{pack.actor_register}}` | the actor and polity register: row shape, report keys, polity key | intake-standing.md |
| `{{pack.actor_register.findings_heading}}` | the actors' findings heading (gate-parsed) | staged/read.md |
| `{{pack.actor_register.findings_line}}` | the actors' findings line form | staged/read.md |
| `{{pack.actor_register.findings_what}}` | what the reader collects for the register | staged/read.md |
| `{{pack.archives}}` | bulk archives, reading rooms, routing rules | the skills (plugin/skills) |
| `{{pack.audited_subjects}}` | subjects whose notes must carry the forthrightness audit | intake-standing.md |
| `{{pack.base_reading}}` | the owner's base reading of the material, with its compilers | narrate/brief-builder.md |
| `{{pack.basis_vocabulary}}` | grounds a stated decline may give | staged/read.md |
| `{{pack.blocked_precedent}}` | the precedent named for the blocked-output pointer row | intake-standing.md, narrate/brief-attack.md, narrate/brief-builder.md, narrate/brief-fork.md, narrate/brief-register.md, narrate/brief-revise.md, narrate/brief-synchrony.md, staged/read.md, staged/write.md |
| `{{pack.forthrightness_charts}}` | the forthrightness chart data an intake returns | intake-standing.md |
| `{{pack.canon}}` | canon texts and unit schemes | intake-standing.md |
| `{{pack.catalysts}}` | catalysts page and threshold catalyst | intake-standing.md |
| `{{pack.channelled_clause}}` | the class of relayed voices and its audit and metadata clauses | intake-standing.md |
| `{{pack.circles}}` | circles and the adverse sources named per circle | intake-adverse.md |
| `{{pack.codebook}}` | codebook instance(s) | intake-standing.md |
| `{{pack.compilers}}` | compiler channels, stem patterns, quota baseline | the skills (plugin/skills) |
| `{{pack.eras}}` | era ids, boundaries and pages | intake-standing.md, narrate/brief-builder.md, narrate/brief-synchrony.md |
| `{{pack.exemplars.adverse_scan}}` | exemplar notes, scanned magazine or paper | intake-adverse.md |
| `{{pack.exemplars.adverse_web}}` | exemplar note, adverse web text | intake-adverse.md |
| `{{pack.exemplars.hearing}}` | exemplar note, hearing day | intake-hearing.md |
| `{{pack.exemplars.document}}` | exemplar note, document set | intake-document.md |
| `{{pack.exemplars.text}}` | exemplar note, single text | intake-document.md |
| `{{pack.exemplars.video}}` | exemplar note, recording | intake-hearing.md, intake-video.md |
| `{{pack.free_sections.document}}` | pack free sections of document notes | intake-document.md, staged/write.md |
| `{{pack.free_sections.teller}}` | the three teller-across-the-ledger sections | intake-video.md |
| `{{pack.free_sections.video}}` | pack free sections of recording notes | intake-video.md, staged/write.md |
| `{{pack.lanes}}` | the lane letters and what each holds | narrate/brief-builder.md, narrate/brief-synchrony.md |
| `{{pack.lenses}}` | the disinformation lens instance(s) | the skills (plugin/skills) |
| `{{pack.model_policy}}` | model, effort and probe rule for every delegated agent | intake-standing.md, narrate/README.md, narrate/attack-tests.md, narrate/attack-write.md, narrate/brief-attack.md, narrate/brief-builder.md, narrate/brief-fork.md, narrate/brief-register.md, narrate/brief-revise.md, narrate/brief-synchrony.md, narrate/candidates.md, narrate/check.md, narrate/draft.md, narrate/finish-build.md, narrate/sweep.md, narrate/write-revise.md, staged/README.md |
| `{{pack.name}}` | the pack's name | the skills (plugin/skills) |
| `{{pack.narrative_reading_list}}` | the pack's own reference pages for builders and synchrony agents | narrate/brief-builder.md, narrate/brief-synchrony.md |
| `{{pack.narrative_seeds}}` | the thesis seeds, one line each | narrate/brief-builder.md, narrate/brief-register.md, narrate/brief-synchrony.md |
| `{{pack.narratives}}` | narrative pages, register, rival sheets, step briefs, digests | intake-document.md, narrate/README.md, narrate/attack-tests.md, narrate/attack-write.md, narrate/candidates.md, narrate/check.md, narrate/draft.md, narrate/finish-build.md, narrate/sweep.md, narrate/write-revise.md |
| `{{pack.ordinary_grounds}}` | the ordinary grounds a wall set excludes | narrate/brief-attack.md, narrate/brief-builder.md, narrate/brief-revise.md |
| `{{pack.reference_objects}}` | the object register, entries to read, reference object and criteria, vocabulary line | intake-standing.md |
| `{{pack.reference_objects.features}}` | the features recorded for an object | staged/read.md |
| `{{pack.reference_objects.watch_name}}` | the watch's name in the findings heading (gate-parsed) | staged/read.md |
| `{{pack.report_keys.document}}` | report keys added to a document report | intake-document.md, intake-standing.md, staged/finish.md |
| `{{pack.report_keys.video}}` | report keys added to a recording report | intake-standing.md, intake-video.md, staged/finish.md |
| `{{pack.rivals}}` | the rival sheets and which rival each kind of page faces | narrate/brief-attack.md, narrate/brief-builder.md, narrate/brief-fork.md, narrate/brief-register.md, narrate/brief-revise.md |
| `{{pack.schema_extensions}}` | the pack's schema-extensions.md | intake-standing.md |
| `{{pack.speaker_ledgers}}` | ledgered speakers, when to read the ledger, report keys | intake-standing.md |
| `{{pack.stock_phrases}}` | the domain stop-list of the echo tool | intake-standing.md |
| `{{pack.subjects}}` | subject pages | intake-video.md |
| `{{pack.synchrony_eras}}` | the synchrony windows and the era page each reads; scope start and quarter start | narrate/brief-builder.md, narrate/brief-fork.md, narrate/brief-synchrony.md |
| `{{pack.topics}}` | closed topic codes of claims rows | staged/read.md |

## Run and project slots

| Slot | Used in |
|---|---|
| `{{ledger.root}}` | intake-standing.md |
| `{{ledger.title}}` | intake-standing.md |
| `{{run.brief}}` | intake-document.md, intake-video.md |
| `{{run.date}}` | intake-document.md, intake-video.md, narrate/brief-builder.md, narrate/brief-revise.md, narrate/brief-synchrony.md |
| `{{run.flare_documents}}` | narrate/brief-revise.md |
| `{{run.label}}` | intake-document.md, intake-video.md |
| `{{run.new_events}}` | narrate/brief-revise.md |
| `{{run.new_material}}` | narrate/brief-builder.md, narrate/brief-revise.md |
| `{{run.purpose}}` | intake-document.md |

## Commands the templates assume that do not exist yet

`ledger file headings`, `ledger file section`, `ledger file copy`, `ledger file lines` (with `--count` and `--out`), `ledger run --out`, `ledger db sql`, `ledger narrate narratives --chunks`, `ledger brief render`. operations.md gives the interim Python form of each, so the templates run today.
