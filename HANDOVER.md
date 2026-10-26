# Handover: the ledger platform

For the recipient's administrator and project manager. Version of 2026-10-24, written with the release bundle it ships in. Every
figure below was measured on the build machine; where something was not verified, the document says so.

## 1. What the platform is, and what it is not

The ledger is a working method and a set of tools for keeping a record of what sources say. A source (a hearing transcript, a
document, an article, a forum thread, a recording) is held byte for byte with its provenance, cut into numbered units, and read by
agents into a note. The note is a markdown file in a fixed form, and it is the only source of truth: the database, the registers'
indexes, the charts and the status page are derived from the notes and can be rebuilt at any time.

What a note holds, row by row:

- **The claims ledger**: every claim the source makes, with its speaker, its class (firsthand, hearsay, read from a document, inference,
  the author's own statement) and a chain of custody. A claim that the speaker did not witness names where it came from, hop by hop,
  ending in the kind of origin (a document, the public record, a person whose basis is never stated, nothing at all).
- **The forthrightness audit**: for every question put to a witness or that a document leaves open, whether it was answered openly, in
  part, closed outright or closed subtly, and on what stated basis. The counts line and the per-interview charts are generated from it.
- **The dated timeline**, with permanent row numbers that never change, and an agreement column comparing each date with every other
  held telling.
- **People, works cited, objects of interest, notable quotes, open questions and cross-checks** against other notes.

Across the notes the platform keeps registers: actors and polities (the order of battle: who is part of, run by, contracted by
whom, in the vocabulary of national security studies), relations between people, leads and inferences (each with the test that would
settle it), the first-utterance register (the earliest held telling of each claim), divergences between tellings, and one speaker
ledger per person the group chooses to follow across appearances.

On top of the registers it builds **narratives under a disinformation lens**: a narrative page assembles the held rows into a dated
account of who knew what when, names the strongest rival reading, and is then attacked, objection by objection, first from the
sources adverse to it. A technique catalogue (a lens) taken from a person or a text, each technique attributed to its source, is used
to ask whether a pattern of closures looks like management of the record; it never places a finding the sources do not support.

What it is not:

- **Not a search engine.** It answers questions only from what has been held and read. A source not held does not exist for it.
- **Not a summariser.** A note is longer than its source (the pilot's notes run two to twelve times their sources' length) because
  every row carries its speaker, its class, its chain and a pointer to the unit and line it rests on.
- **Not a referee.** An agency, a company or a court is a party whose tellings are recorded and compared, never the authority that
  settles what a witness said. Contradictions are recorded and tested, not resolved by rank.
- **Not online.** The only outbound connection is the model route the network permits. Publishing pages to claude.ai as artifacts is
  an end-user setting, **off by default**; with it off, every viewer, map and report is a local file in the project folder.

## 2. What is on the media, and how to install it

The bundle is one folder for every operating system; the install script detects the system and selects what differs.

| Folder | What it holds |
|---|---|
| `HANDOVER.md` | this document |
| `plugin/` | the Claude Code plugin: the skills `/ledger:setup`, `settings`, `intake`, `narrate`, `attack`, `report`, `status`; agent definitions (reader, writer, finisher, builder, attacker, reviser on Opus at high effort; a probe on Haiku); hooks written in Python; the brief templates with their pack slots |
| `wheels/` | the `ledger` Python package and its dependency wheels for offline install; `wheels/TO-STAGE.md` lists the wheels the administrator must stage from the institution's mirror |
| `template/` | the project template: the core tools, the workflow scripts, the package source, the protocol documents in their core form, the viewer library |
| `docs/` | the protocol documents (house schema, intake policy, staged intake, narratives, setup, presentation, hold schema, an invented example casebook) |
| `example-pack/pilot/` | the pilot's domain pack (section 6) with the fetch manifest of its sources; no held text: each source is re-held from its own site under its own terms |
| `sample/` | synthetic databases of the invented casebook, to run setup against before the group's own database |
| `platform/<os>/` | per system, the OCR and transcription pieces the administrator stages (Tesseract and its language data on Linux and Windows; the Apple Vision OCR source, compiled at install, on macOS; the transcription engine and weights everywhere), each with a checksum column |
| `managed-settings/` | a managed-settings template per system and how to fill it |
| `install/` | `install.py`, with `install.sh` and `install.ps1` as the entry points |

**Install, on each machine:**

1. Stage what `platform/<os>/MANIFEST.md` and `wheels/TO-STAGE.md` list, then run `python3 install/install.py --write-checksums`.
2. Fill `managed-settings/<os>.json` (its README names each key) and place it at the system's managed path.
3. Run `python3 install/install.py` to check, then `python3 install/install.py --apply --project <project folder>`. It verifies the
   bundle's checksums, detects the system and the OCR backend, checks for Claude Code, Python 3.11 or later and Node, lays the template
   into the project (never overwriting a file already there), makes a virtual environment at `<project>/.ledger/venv`, installs the
   wheels into it with no network, compiles the Vision OCR on macOS, renders a test page, and writes `<project>/.ledger/install-report.json`.
4. Register the plugin: `claude plugin marketplace add <bundle folder>` (or, for the repository, an SSH address your git can authenticate, since a private repository's plain GitHub name is refused) and `claude plugin install ledger@ledger-local`, or seed it
   from a shared directory as the managed-settings README describes.
5. The simpler path from here: in the project folder run `/ledger:install`, which creates the environment, installs the package and lays the template, says what the administrator must place by hand, and hands over to setup (steps 3 and 4 above are then unnecessary; the repository's `BOOTSTRAP.md` is a message to paste into Claude Code that runs the whole sequence). Then the administrator runs `/ledger:setup` (stage 0, section 3); the project manager takes the later stages.

**What was verified here, and what was not.** The bundle was built and installed on **macOS only** (Apple silicon, Python 3.12): the
offline install into the venv, the Vision OCR build and its test render, the shipped tests (section 9 gives the count), setup stages
0 to 8 against the sample database, and the full pilot run of section 6. **Not verified**: the Linux and Windows branches of the
install script (Tesseract selection, the PowerShell entry point, Windows paths and the `python` naming), the transcription engine on
any system (no recording was transcribed in the pilot; the hearings came with published transcripts), and the plugin, its skills and
its hooks in a live Claude Code session on any machine other than the build machine. These are the administrator's to check at
stage 0; the round-trip test (section 5) should be run once per system before the group relies on it.

## 3. The administrator's stage 0 checklist

Stage 0 is read-only to everyone but the administrator. `/ledger:setup` stage 0 checks each item and refuses to continue while one is
missing; it asks only about what it cannot detect.

0. **Privacy settings on every account, first.** Before setup runs, every member opens the Claude app's settings, Privacy (or Preferences), and turns off 'Location metadata' and 'Help improve our AI models'. The second allows chats and coding sessions to be used to train the provider's models; the agents' sessions will hold the group's sources and notes about named people. The settings are per account, not per project, and setup cannot see or change them, so stage 0 asks the administrator to confirm and records the answer as a ruling; it refuses to continue until the answer is yes.
1. **The group's Claude instance and its model route.** No part of the model runs on premises. The route must be reachable through a
   plain HTTPS proxy (a CA bundle and client certificates are supported; SOCKS, NTLM and Kerberos proxies are not). Choose by the
   institution's existing trust: Amazon Bedrock, Google Cloud, Microsoft Foundry, Claude Platform on AWS, or Claude for Enterprise
   directly (the only route with zero data retention). Stage 0 reads which route is configured from the environment variable names,
   never their values. Provider and gateway routes have no artifacts, connectors or web search, which suits a closed network.
2. **Managed settings** on every machine, from `managed-settings/<os>.json`: the allowed providers, the available models (Opus for
   every reading and writing agent, Haiku for the gate probes, nothing else is needed), the maximum effort level (high), managed
   permission rules and hooks only, the sandbox's allowed domains (the model route alone), a strict list of known plugin marketplaces,
   and non-essential traffic disabled. Server-managed settings do not reach provider routes, so these files are the policy.
3. **The venv.** The install's `<project>/.ledger/venv` holds every Python dependency; the hooks, the gates and the probes use it when
   it exists. Nothing is installed into the system's Python.
4. **The database connection.** Setup reads the group's database record by record and holds each record byte for byte with its
   identifier, table, timestamp and query as provenance. Give it a read-only connection or an export. The derived database
   (`notes.db`) is always local to each machine and never on a share (SQLite's locking is not safe over a network); the project
   folder itself may sit on the group's secure share.
5. **Nothing leaves the network.** The bundle fetches nothing; the install fetches nothing; the web adapter, where the network allows
   it at all, honours robots.txt and Crawl-delay with an honest user agent and never overrides a refusal. Artifact publishing stays
   off unless the project manager turns it on and the route supports it.
6. **Members.** Stage 0 writes the administrator into `members.toml`; the project manager adds the members and their roles at stage 7.

## 4. Setup, stages 1 to 8, as the group will meet them

Setup is one skill, resumable at the first stage not yet done, and every answer is written down: each stage writes `setup/stage-N.toml`
and appends its answers to `rulings.md` as dated rulings attributed to the member who gave them. The project's `CLAUDE.md`, which
every agent reads, is regenerated from the rulings.

1. **The question.** The pack's name, the project's title, the question the group is asking, who or what the inquiry is protecting
   (every actor is later described by its stance toward this), and the questions the group most needs answered, each with the facts
   that would answer it. Those questions are an overlay: they make sure every dated statement of knowledge they name is captured; they
   never tell the readers what a source says.
2. **The schema mapping.** Setup introspects the group's tables, columns, types, keys and samples and proposes, for every field of the
   hold schema, a column or an expression, with its confidence and alternatives, and the record unit. The project manager confirms or
   edits the mapping table; unmapped columns are kept as metadata and may be promoted. Annotation tables (coded claims, speakers,
   tags, relations, events) are offered for import into the registers, with the group's database named as the teller and marked as
   the group's own reading. **A dry run on five records** shows, for each, the text it found and the file it came from, before
   anything is saved. A re-scan later reports what changed.
3. **Subjects and balance.** Subjects, the subjects under which the forthrightness audit is mandatory, topic codes, eras. Then **the
   adverse-source rule**, explained before it is asked: if on, the group names its circles (the connected groups of tellers), says for
   each how an adverse source is identified (declared at intake, named in advance, or detected by position and confirmed), and sets a
   quota. Setup states plainly that the rule never makes an adverse source more reliable, never scores who is right, and never lets a
   sceptic correct a witness; it only makes sure the record is not built from one side. The group may turn it off.
4. **The people and organisations found.** The scan lists who speaks, which people, organisations and groups the sources talk about,
   and how they relate. The group reviews the list by marking names: a marked name is brought forward in every report and watched
   for; marking never changes what the sources say about anyone, and a name the scan did not find cannot be added by hand, because
   the picture is built from the sources and not from the group's prior view. The group also names the people who get a record of
   their own, one column per appearance, so their statements can be compared across time.
5. **Canon and codebook.** Foundational texts held in addressable units (the pilot's are three court judgments by numbered paragraph),
   and known codes and argot. A decode is always a lead naming its code, never a finding.
6. **Lenses.** A lens is a known playbook of disinformation or misleading techniques, from a person who described one or from a text (a manual, a
   doctrine, a playbook, a regulator's guidance: the pilot's is a prosecutor's published guidance on corporate cooperation), each
   technique attributed to its source and matched to the core catalogue of techniques. Nothing is read through a lens at setup; that
   happens when sources are read, and a match is always attributed.
7. **Members and policy.** Members and roles, the model route, the budget, the no-omission rule (no work is left out to save cost;
   a limit delivers what remains as an index), the turning points after which a telling may have been shaped by what became public,
   the private-individuals rule, and whether to publish artifacts (off by default).
8. **The first intake and the pack check.** One record is taken through the whole intake; the pack check confirms every brief renders
   with every slot filled.

**Later changes go through `/ledger:settings`**, which the project manager uses to re-enter any stage from 1 to 8 (stage 0 is the
administrator's). It shows the current values, rewrites the stage's file, appends a dated, attributed ruling, and writes to
`owed.md` what the change owes: a re-scan, retroactive audit rows for a newly audited subject, the source balance, a detection re-run,
the lens and canon tests. It never rewrites an existing note; it hashes every note before and after and fails loudly if one changed.
A launcher may propose a change; only a project manager or the administrator adopts it.

## 5. How an intake runs, and what it costs

An intake is a workflow of short-lived agents, each reading only what its phase needs (`tools/workflows/staged-intake.js`). The shipped
form is **unit writers**, the workflow's default:

1. **Unit writers.** One writer per range of units writes the claims ledger and the audit rows of its units with the unit itself in its
   context, in sequence; a source of more than about 20,000 words gets two or more writers, each with about 10,000 to 20,000 words.
   Every quotation is pasted from `ledger quote` (the lines by pointer, or `--find "<a few of the words>"`, which prints the sentence
   or caption line that holds the words and the pointer to cite), never typed from the unit; every row ends with its unit pointer.
2. **The parts gate**, a script, after each writer: every quotation in its parts is in its unit word for word, every pointer holds its
   row's words, the rows run on without gaps, every unit is cited or listed as having nothing to row. A quotation from an unpunctuated
   caption may add punctuation and capitals but never change, add or drop a word (the caption rule): the gate reports such a quotation
   as `punctuation only`, apart, and never fails it; a changed word fails, with the source's words beside it. The writer clears every
   failure before it replies, and the workflow resumes it with the report if one is left.
3. **The assembly**, a script, builds the note from the skeleton and the parts; **gate 2** checks the whole note the same way.
4. **The check**, optional (`check: true`): one agent reads the claims rows against the spans their pointers pull, in an order of
   attention (first the rows classed firsthand in a document and the host rows whose span names a source; then the rows whose span
   carries a hedge or qualifier the quotation leaves out; then the rows with a second actor, a pronoun subject or an embedded telling;
   then the quotations that stop before a limiting clause; then the rest), and corrects each failing row in place; `checkBudget`
   caps it in rows; gate 2 after it. Measured at about 5 percent of a task's cost (3.7M and 11.7M records on the two sources below), it
   corrected 6 of 118 and 19 of 419 rows, every sampled change right, but did not lower the sample's count of faults of meaning.
5. **Writer B** writes the other sections from the units and the finished ledger; gate 2 again.
6. **The finisher** generates the mechanical parts (the counts line, the inventory, the cross-check candidates), runs the checks and
   writes the report; gate 2 a third time.
7. **The sample reading**, on every intake (`sample: false` skips it; never by default). `ledger sample draw` draws twenty claims rows
   of the finished note by a fixed seed (a hash of the note's name), spread over the units in proportion to their rows, each beside the
   span its pointer pulls; one Opus reader judges each row five ways (verbatim, support, grain, class and move, chain) under
   `plugin/templates/briefs/staged/sample.md` and writes its reading; `ledger sample tally` writes the tally into the report's
   `sample_reading`. When the faults of meaning reach the pack's threshold (`[intake] sample_threshold` in pack.toml, default 3), the
   check of step 4 runs over the whole ledger, gate 2 after it, and a second sample with a new seed is read; the report keeps both
   tallies. `ledger integrate` then carries the report into the registers, writes the tally to the cost log and regenerates every
   page; the status page shows each note's tally (`sample: meaning M of 20`) and the total per run. The report check fails an intake
   report that has no `sample_reading`.

The other form, **staged** (`intakeForm: "staged"`), puts a reader before the ledger: one reader per range of units (over about 35,000
words, two or more) writes a compact findings file per unit, each claim, date, quotation, name, document, actor, relation and question an
item with its unit and line pointer; gate 1, a script, checks them (the fixed form, every quotation verbatim, every pointer inside its
unit, the item allowance of 200 words plus a fixed allowance per item); and writer A writes the metadata, the claims ledger and the audit
from the findings, pulling the source's words by pointer. Steps 3 to 6 follow as above. The pilot (section 6) ran this form.

**Why unit writers: the six-form measurement** (2026-10-24, two sources of the first project: a 4,913-word recording transcript of two
speakers and a 21,305-word OCR text of two magazine articles; each form's note read at twenty claims rows against the source):

| Form | Faults of meaning (40 rows) | 95% interval | Formal faults (40) | Claims-ledger quotations not word for word | Cost, both sources (records) |
|---|---|---|---|---|---|
| The first project's original notes (one agent, the whole source in context, no gates) | 0 | 0 to 8.8% | 14 | 33.5% and 50.4% | not measured |
| Staged | 5 | 5.5 to 26.1% | 4 | 0 and 2.3% | 224.4M |
| One agent, the gates' report after it | 2 | 1.4 to 16.5% | 15 | 51.4% and 57.2% | 165.4M |
| **Unit writers (shipped)** | **1** | 0.4 to 12.9% | 5 | **0 of 1,078** | 169.3M |
| Staged with the check | 3 | 2.6 to 19.9% | 4 | 0 and 0 | 260.6M |
| Unit writers, the briefs of 2026-10-25 (the confirming run) | 2 | 1.4 to 16.5% | 11 | 0 of 989 (8 punctuation only) | 163.9M |
| One agent, obliged to paste every quotation from the tool, the quotation gate after it (the confirming run) | 6 | 7.1 to 29.1% | 11 | 0 of 684 (5 punctuation only) | 183.4M |

On forty rows a form the intervals overlap, so no ranking of the gated forms by meaning is established. What is established: the
forms whose writer pastes the words from the tool quote exactly, and the one-agent form does not, whether or not the gate's report is
put before it; unit writers is the cheapest of the exact-quoting forms (75 percent of the staged form's cost; its ledger stage a third
to a half of the staged reader's and writer A's), and it has no reader-to-writer hand-off for faults to enter at (the staged form's 5
were all its reader's). The one-agent form is not shipped.

**The confirming run** (2026-10-25, the same two sources, the last two rows of the table) repeated unit writers under the final briefs
and gave the one-agent form the obligation to paste every quotation from the tool, with the quotation gate after its reply. Unit
writers are confirmed: 0 changed words in 989 claims-ledger quotations, 2 faults of meaning in 40, 163.9M records. The one-agent form's
quotations are fixed by the obligation (0 changed words in 684), but its meaning is not shown intact: 6 faults of meaning in 40 (7.1
to 29.1 percent), at 183.4M records. It stays unshipped; the sample reading (step 7) runs on it too.

**Measured cost** (the cache-read tokens of every agent call, counted once per streamed record, which is how the estimates are made):

| Pilot task | Source words | Readers | Claims rows | Audit rows | Note words | Cost (records) | Estimate | Ratio |
|---|---|---|---|---|---|---|---|---|
| terms of reference | 998 | 1 | 33 | 5 | 12,684 | 35.2M | 63.5M | 0.55 |
| press article | 1,894 | 1 | 44 | 9 | 16,214 | 49.4M | 66.6M | 0.74 |
| internal meeting notes | 2,665 | 1 | 84 | 12 | 19,774 | 44.9M | 69.3M | 0.65 |
| regulator's guidance | 2,697 | 1 | 80 | 11 | 15,122 | 39.9M | 69.4M | 0.57 |
| counsel's advice | 4,243 | 1 | 126 | 24 | 31,733 | 66.4M | 74.9M | 0.89 |
| press investigation | 4,453 | 1 | 132 | 20 | 27,246 | 56.0M | 75.6M | 0.74 |
| interim report | 9,892 | 1 | 240 | 32 | 40,179 | 58.6M | 94.6M | 0.62 |
| adverse reply | 24,253 | 1 | 412 | 35 | 61,545 | 130.8M | 144.9M | 0.90 |
| forum thread | 31,373 | 1 | 521 | 70 | 68,633 | 133.6M | 169.8M | 0.79 |
| hearing day (claimant) | 42,034 | 1 | 614 | 163 | 83,099 | 184.4M | 207.1M | 0.89 |
| hearing day (executive) | 46,937 | 1 | 662 | 316 | 94,488 | 207.1M | 224.3M | 0.92 |
| **eleven intakes** | 171,439 | | 2,948 | 697 | 470,717 | **1,006.3M** | 1,260.0M | 0.80 |

The estimate is 60M plus 3.5M per 1,000 source words, fitted to two earlier runs; every pilot task came in under it. In plain terms:
**a short document costs 35 to 65 million cache-read tokens whatever its length** (a fixed cost of the phases), and a long one about
**4 to 4.5 million per 1,000 words**. Writing (writers A and B) is 41 to 67 percent of each task; the finisher is 15 to 51 percent and is
the larger share on short sources. The narrative step for one page (six synchrony agents, a builder, an attack and a revision) cost a
further 219.9M; the whole pilot, 1,226.2M. Measured on an earlier private corpus in the round-trip test (nine sources of 4,000 to
73,000 words held under a deliberately different database schema): 1,170.4M for nine intakes under the first form of the workflow,
2.1 times its estimate; the compact findings and the split write since then cut the cost per claims row from about 0.41M to 0.28 to
0.30M. Record each run with `python3 tools/agent_usage.py <run> --by-phase --append-cost-log`, which writes `research/cost-log.md`.

**The form's limits.** About **40,000 words of transcript per note**: under the staged form the largest pilot writer reached a context of
641,000 tokens on a 46,937-word day; under unit writers every agent of the 21,305-word source stayed under 370,000. Unit writers split
a source over 20,000 words between two or more writers by default (the staged form splits its reading over 35,000); a source much larger
than 50,000 words should be cut into session notes. The per-task cap (`maxRecords`) stops one task without stopping the others. Before
any run that will outlast the session's turn, keep the computer awake (`docs/agent-wip.md` item 9: a sleeping computer kills the agent
in flight).

**What the gates check, and what they cannot.** The gates check words and places: that quotations are verbatim (219 of 219 sampled
were), that pointers land, that every unit is accounted for, that the findings are not padded. **They cannot see a fault of meaning**:
a paraphrase outside the quotation marks that reverses what the span says, a wrong speaker, a footnote's assertion taken as the
issuer's own act, a merged row that buries a proposition. The only control on these is **the sample reading**: one Opus reader per note
reads twenty claims rows against the spans their pointers pull. In the pilot it found **17 faults of meaning in 220 rows, 7.7 percent
(95 percent interval 4.9 to 12.0)**, 10 owed to the reader and 7 to writer A; under the final briefs, 1 in 40 (2.5 percent). Each
reader cost about 140,000 to 180,000 tokens, under 0.2 percent of an intake. The sample reading is built into the workflow as a phase
of every intake (step 7 above, from 2026-10-25): its tally is in every report and on the status page, and a note at the pack's
threshold goes to the check before it integrates (the pilot's 17 were corrected by hand; section 6).

## 6. The pilot, as a worked example

The pilot is a complete project built from public material on the Post Office Horizon IT Inquiry, chosen because it has hearings,
exhibits, court judgments, press and public comment, an adverse party, and a well-documented question: when each actor first recorded,
in writing, that bugs affected branch accounts and that branch data could be altered without the subpostmaster's knowledge.

| What | Where in the installed project |
|---|---|
| the pack: question, referent, three requirements, seven polities, eight lanes, the guidance lens, the judgments as canon, an argot codebook, catalysts, three ledgered speakers | `packs/pilot/` |
| the eleven held sources (the bundle carries the fetch manifest; re-hold them from their sites) | `sources/pilot/` |
| the eleven notes: two hearing days, four inquiry exhibits (internal meeting notes, an interim report, counsel's advice, the adverse reply), two press pieces, a forum thread, the terms of reference, the regulator's guidance | `videos/` (hearings), `books/` (the rest) |
| the registers: actors and polities, relations, leads, first utterance, divergences, echoes, the timeline | `research/actor-polity-register.md`, `relations-register.md`, `leads-and-inferences.md`, `first-utterance-register.md`, `divergence-patterns.md`, `echo-patterns.md`, `timeline-master.md` |
| three speaker ledgers | `research/*-perspective-ledger.md` |
| the narrative page, its rival sheet and six synchrony pages | `research/narrative-managed-knowledge.md`, `narrative-rival-good-faith-reliance.md`, `narrative-synchrony-*.md` |
| the forthrightness charts | `research/forthrightness-charts.md`, `research/figures/` |
| the status page and the cost log | `research/status.md`, `research/cost-log.md` |
| every task's working folder, archived | `research/tasks/tool-feedback/pilot-1023/` |

The narrative page was built from the six synchrony pages (33 nodes over eight lanes), then attacked with 27 objections drawn first
from the adverse source (the reply of 2015 by the party whose conduct the question concerns), and ruled on: 13 objections adopted, 14
adopted in part, none declined outright, every declined part naming its rows. The page records what the ruling moved.

**The retrofit after the run.** The demonstration was brought under the rulings made during the run, so the group meets it in its
final form: a hedged risk or option statement in a document is now the author's own statement with no audit move (7 rows changed in
the meeting notes); the 17 rows with faults of meaning were corrected against their spans (3 propositions given rows of their own, with
decimal IDs); 39 duplicate first-utterance clusters created by a re-run were superseded by their originals, with every citation
updated; and claims rows now carry the number of the audit row that rests on them, which the charts use to give each audit row its
topic. The counts before and after are in section 9.

**The visualisations are produced for the group automatically** (owner ruling, 2026-10-26). Every `ledger integrate` ends with the presentation step, which writes local files under `research/figures/` that open from the folder with no network: the narrative viewer (`narratives-viewer.html`: every narrative page, its nodes, ledger and objections, the synchrony grid when a narrative pack exists), the forthrightness charts per audited recording and the pooled overview, and the map's data files (the relations, chain-hop and order-of-battle graph, viewed locally with `python3 tools/map_server.py`). Publishing any of them to claude.ai as a shared artifact is the separate choice of stage 7 (`publish_artifacts`, off by default, since a group on a secure network may not reach it); the local files are written either way, and the pilot ships with its viewer and charts built.

## 7. The standing rules the group inherits

Each is written into the project's `CLAUDE.md` and `rulings.md` at setup and may be changed through `/ledger:settings` (a dated,
attributed ruling; what it owes goes to `owed.md`).

- **Opus at high effort** for every agent that reads or writes; Haiku only for the probes that run a script and relay its line.
- **No token omission.** Work is never left out to save tokens; a cap delivers the remainder in index form rather than dropping it.
- **The archive rule.** Every agent checkpoints to `wip/<task>/` from its first minute; a finished task's folder is archived with
  `python3 tools/wip_archive.py wip/<task> --run <run> --trash` (deliverables kept under `research/tasks/tool-feedback/`, caches never).
- **The hand-back rule.** A report enters the project only through `ledger integrate <report.json>`, which stops at the first failing
  step and names it; the report is checked against what integrate consumes before the agent replies.
- **The cited-source rule.** An intake rows what its source says, including what the source says a cited work says; the cited work's
  own claims are never rowed until that work is itself held.
- **The divergence rule.** Diverging tellings of one event are always recorded, with the parties named; an agency or a company is a
  party under scrutiny like any other.
- **The adverse-source rule** (if the group turned it on): adverse sources per circle and era, and the quota.
- **Markdown is the source of truth**; the database is derived; permanent row IDs are never renumbered.

## 8. Known defects and limits at handover

1. **Faults of meaning are invisible to the gates** (section 5). Measured 7.7 percent in the pilot's sample, 2.5 percent under the final
   briefs on a sample of 40 (the staged form); under unit writers, 1 in 40 on the six-form measurement (section 5), whose intervals
   overlap. The sample reading is the control, and it runs on every intake under either form: the workflow's sample phase (section 5,
   step 7) reads twenty rows of every note, records the tally in the report and on the status page, and sends a note at the pack's
   threshold to the check before it integrates. (tools/intake_gate.py; tools/ledger/sample.py; the briefs `plugin/templates/briefs/staged/`)
2. **The audit's grain.** On the round-trip test a long recording's audit came out at 59 rows against the original note's
   31, with 14 pseudo-declines against none; whether an audit row should follow a ledger row or a question-and-answer exchange has not
   been read and ruled. (`plugin/templates/briefs/staged/write.md`, writer A; `docs/schema.md` section 3)
3. **The scorer's quotation pairing** in the round-trip test pairs quotations by text, so a quotation cut differently from its original
   counts as lost; quotation coverage figures are a lower bound. (`tools/roundtrip/score.py`, not shipped)
4. **The terms-of-reference note's pointers are one line late** throughout (its reader numbered from the held file, not the unit file);
   the words and meaning are intact. Gate 2's one-line slack passed them. A warning when many of a unit's pointers resolve only by the
   slack is proposed, not built. (the pilot note; `tools/intake_gate.py`)
5. **Lanes of the pilot pack.** The pack names its eight lanes but gives no lane wording or topic map, so the narrative pre-pass places
   most rows in one fallback lane; the narrative agents reassigned them by hand. The pack should carry `lane_rx` and `topic_lane`
   ([tools.narrative_pack] in `packs/pilot/pack.toml`).
6. **Relations keyed without their date** at intake: `ledger integrate` de-duplicates relations on the two parties and the kind, so a
   dated variant of a held relation is dropped (the narrative step's own dedupe now keeps it). (`tools/integrate_report.py`)
7. **Hearing audits cite no claims rows**, so a hearing's charts give each audit row its topic by matching timestamps; about a fifth of
   a hearing's turns still fall to "other". (the write brief; `tools/draw_forthrightness_chart.py`)
8. **The bulk-archive tools' file names are historical**: the mirror, index, extraction and route-by-named-actor tools of the
   acquire and prepare layers (`ledger acquire` and `ledger prepare` list them) are named after the first archive they served. They
   work on any released collection.
9. **Untested here**: the Linux and Windows install branches, transcription, the plugin in a live session beyond the build machine, a
   gateway or provider model route, the group's database engine and volume, media held outside the database (section 2).
10. **The narrative viewer is not built for the pilot**: `ledger present` skips it with a notice because the pilot pack's
    `[narratives]` table names no `folder` (the narrative pre-pass folder, archived under `research/tasks/tool-feedback/pilot-1023/`).
    Setting `folder` to a current pre-pass folder builds `research/figures/narratives-viewer.html`. (`packs/pilot/pack.toml`;
    `tools/build_narrative_viewer.py`)
11. **Follow-ups found by the retrofit and left as they are**: a few rows beside the corrected 17 carry the same kind of fault (listed
    in the retrofit record); they are queued, not corrected.

## 9. The state at handover, with counts

**The bundle** (rebuilt 2026-10-25 with the unit writers as the shipped form): about 420 MB in 423 files (the dependency wheels for
macOS, Linux and Windows are most of it), every file listed with its SHA-256 in `CHECKSUMS.sha256`. Every file was checked before shipping for anything that belongs to another project; the dependency wheels and the
viewer's vendored chart library are third-party code, carried as downloaded. **The shipped tests**: 27 Python test files of the template (307 tests)
pass in an installed project, run with the project's venv, and the two workflow dry-run files pass (staged-intake 22 cases,
guarded-intake 7), with no network.

**The pilot project, before and after the retrofit of section 6:**

| Count | Before | After |
|---|---|---|
| notes | 11 | 11 |
| claims rows | 2,948 | 2,951 (3 propositions given rows of their own, decimal IDs) |
| claims rows with a fault of meaning found by the sample | 17 | 0 (corrected against their spans) |
| hedged risk or option lines classed host with an audit move (rule cr) | 7 | 0 (now host, no move) |
| claims rows carrying the number of the audit row that rests on them | 8 | 259 (32 citations too ambiguous to link, listed) |
| first-utterance register rows (active clusters) | 56 (56, of which 39 were duplicates) | 56 (17 active, 39 superseded by their originals) |
| audit rows; quotes; timeline rows; open questions; cross-checks | 697; 639; 631; 240; 225 | unchanged |
| actors (placed); polity statements; relations; leads | 358 (325); 106; 382; 326 | unchanged |
| held text files duplicated within a hold | 6 (1.13 MB) | 0 (each removal recorded in its hold) |
| narrative page: adoptions; mechanical fails; warnings | 27; 0; 13 | 27; 0; 13 |
| `ledger check` | exit 0 | exit 0, baseline 0 differences |

## 10. How to report a defect back

Use the tool-feedback archive form the project already keeps: a folder under `research/tasks/tool-feedback/<run>/<task>/` holding the
task's `progress.md`, its `report.json`, and a short `REPORT.md` with, for each defect, a row of `| # | Finding | File(s) | Proposed
fix or brief wording |`, as the pilot's report does. Name the file the defect belongs to, the command that shows it, and the
before-and-after counts where a fix touches a parser. Brief and template wording changes are proposed in the report, not made in place,
so that every agent reads one version of each brief at a time. Send the folder by the same removable route the bundle came by; nothing
is sent to a public server.

## 11. What this handover did not verify

Stated once more, plainly: the install on Linux and Windows; the transcription of any recording; the plugin's skills and hooks in a
live Claude Code session on the group's machines; any model route other than the build machine's; the group's own database (its
engine, size, encodings and media); the round-trip test on any system but macOS. The handover session with the administrator and the
project manager, walking setup against the group's real database to stage 8, is where each of these is first checked.
