# Setup, settings and members (platform phase 7a, 2026-10-22)

The guided setup that turns a research group's own database into a ledger project, the re-entry of its stages, and the members file
that decides whose rulings bind. The plugin's `/ledger:setup` and `/ledger:settings` skills are the interactive form; these modules are
the engine, and every question goes through one function that reads a JSON answers file, so every stage runs without a person.

| Module | What it does |
|---|---|
| `tools/ledger/setup_stages.py` | stages 0 to 8; resumable from the first stage whose file is missing; seeded from the scan of their database |
| `tools/ledger/settings.py` | re-enter a stage, show its values, rewrite its file, append a ruling, queue what the change owes; never rewrites a note |
| `tools/ledger/members.py` | the members file (name, OS user, roles), the check before a ruling or a launch, the launcher row in a note's metadata |
| `tools/ledger/briefs.py` | the brief renderer the skills call at run time (the module form of `ledger brief render`) |
| `tools/ledger/sampledb.py` | the shipped sample database, written from the invented cases of tools/example-casebook.md |

The engine is named `setup_stages.py`, not `setup.py`: a `setup.py` beside `tools/ledger/pyproject.toml` is run by setuptools as the
package's build script, which breaks the wheel build.

## The stages

Each stage writes `setup/stage-N.toml` (its answers, where each came from, and its result) and the pack files it fills before the next
stage starts; each completed stage appends its answers to `rulings.md` as dated, attributed rulings and regenerates `CLAUDE.md`.

| Stage | Asks | Writes |
|---|---|---|
| 0 environment (administrator) | the model route from the environment (`CLAUDE_CODE_USE_BEDROCK`, `_VERTEX`, `_FOUNDRY`, `_ANTHROPIC_AWS`, a gateway's `ANTHROPIC_BASE_URL`, an API key; names only, never values; Claude for Enterprise declared by the administrator); the managed settings file for this OS; the plugin path; whether the project folder is on a share; the OS and Python; the OCR backend and a test render of a one-page PDF; the transcription engine; Claude Code. It refuses to continue without a route or a managed settings file, and asks only if something is missing. | `setup/platform.json`, `ledger.toml` (`[models]` opus, high, haiku; `[database]` local, per machine when the folder is on a share; `[acquire]`), `members.toml` (the administrator), `wip/runs/setup.log` |
| 1 the question | the pack's name, the title, the question, the referent object, the priority intelligence requirements with their essential elements of information and terms. A name whose `packs/<name>/` already exists and was not written by this project's stage 1 is refused (setup never overwrites a pack); the name is fixed once stage 1 has run, and a re-entry updates the stage 1 values in place | the pack skeleton in the default pack's shape (loads through tools/packload.py from here on), `[[pirs.pir]]` with id, question, eeis, terms, declared and by (a requirement unchanged on re-entry keeps its first declaration), `keywords/pir-terms.txt`, slots `name`, `referent`, `pirs` |
| 2 schema mapping (refused before stage 1) | their database's connection, or a folder of holds already in the hold schema (`holds:<folder>`, or a folder with hold.json files under it: phase 7b; the hold schema is the mapping, five holds verified byte for byte are the dry run, the holds are copied to `sources/<set>/` and verified again, and the scan runs over them; holds already under the project's `sources/` stay in place); the record unit (proposed with confidence and alternatives); field edits; a column for every required field without one; the text's sources in the order they are tried per record (transcript rows, a body column, text attachments: `2.text_order`, `confirm` or the numbers in the order wanted, one left out to drop it); unmapped columns to promote; each annotation table offered for import (their database as teller, the group's reading), its register, and its columns per role (`2.annotations.<table>.columns`); the dry run of five records (with the file each record's text came from) accepted or not; whether to hold now | `setup/introspection.json`, `mapping-proposal.toml`, `mapping.md` (the table with confidence, evidence and alternatives), `dry-run.md`, `mapping.toml` (confirmed, by whom), `rescan.json` when a mapping was saved before; the hold under `sources/db/<name>/`; `setup/scan.json` and `scan.md`; `[archives]`, `[metadata]`, `[registers] import`, slot `archives` |
| 3 subjects and balance | subjects, audited subjects, topic codes, the basis vocabulary, a relayed-voice class, eras, compilers; then the adverse-source rule, explained before it is asked; if on: circles, each circle's identification (declared, named, detected by position and confirmed), the quota and ratio | `[subjects]`, `[audit]`, `[eras]`, `[circles]`, `[source_kinds] compilers`, `seeds/circles.md`, `schema-extensions.md`, eight slots |
| 4 detected entities | flags on detected actors and polities; ledgered speakers (a policy: a speaker the scan has not met yet is accepted and recorded as not yet detected); detected names that are not entities; reference objects; stock phrases. A flag or a dropped name the scan did not detect is refused: nothing is placed by hand | `registers/detected-candidates.md`, `registers/actor-polity-vocabulary.md`, `[actors]`, `[speakers]`, `[objects]`, slots |
| 5 canon and codebook | foundational texts with their unit schemes and witnesses; known codes and argot | `canon/texts.md`, `codebook/codebook.md`, `[canon]`, `[codebook]`, slots |
| 6 lenses | lenses from a person or a text, each technique attributed to its source; the proposed mapping of each technique to the core technique catalogue, confirmed or edited | `lenses/<id>.json` (techniques, subject criteria, no placements), `[lenses]`, slot |
| 7 members and policy | members and roles, the model route, the budget, the no-omission rule, catalysts and the threshold catalyst, the private-individuals rule, and whether to publish artifacts (`7.publish_artifacts`: viewer, map, docs; `[]`, off, by default: the end user's choice) | `members.toml`, `ledger.toml` `[models]` and `[policy]`, `seeds/catalysts.md`, `[catalysts]`, `[display.publish]` (enabled, targets, last_published), slots `model_policy`, `catalysts`, `CLAUDE.md` |
| 8 first intake and the pack check | the record to take first and why | `packs/<pack>/briefs/runs/<run>.toml` and `.md`, `setup/pack-check.json` (every packload accessor against the new pack; the intake briefs rendered with no missing slot), the rendered briefs under `wip/<run>/briefs/`, `setup/stage-8-launch.json` (the Workflow call, the pre-pass and the hand-back commands), `setup/stage-8.toml` after the launcher returns |

The scan (end of stage 2) runs over the hold, not the live database: the context-pack extractors (tools/context_pack.py, imported, with
a person lexicon built from the records' speakers and the names the text gives a role) for names, organisations, dates and
identifiers; then the organisation and grouping pass: possessive and multi-word names, acronym expansion (`Long Name (ACR)`), alias
merge (`the Authority`), polity words and state contexts (`minister of`, `envoy of`), order-of-battle verbs (`a front for`, `part of`,
`run by`, `funded by`, `a subcontractor of`, `member of`, `controlled by` and the rest); speakers from the records and from the
annotations' attributions (kept apart as the group's reading); adverse position markers per record; PIR terms surfaced, never placed;
proposals for subjects, topics, venues, circles and eras. Every candidate carries its count and the records that name it.

## Driving it

```
python3 tools/ledger/setup_stages.py status --project .
python3 tools/ledger/setup_stages.py run --project . --answers setup/answers.json [--until N]
python3 tools/ledger/setup_stages.py stage N --project . --answers setup/answers.json
python3 tools/ledger/setup_stages.py launched --project . --note <note> --run <label>
python3 tools/ledger/setup_stages.py pack-check --project .     the stage 8 pack check on its own: setup/pack-check.json; exit 1 on a problem
```

Exit codes: 0 done; 3 a question needs an answer (printed as JSON: `qid`, `prompt`, `kind`, `choices`, `default`, `context`,
`explain`, `error`); 4 refused; 5 the stage 8 launch is built and pending. The answers file is `{"answers": {"<qid>": value}}`; a
default is offered but never taken unless the answer is given (or `--use-defaults`, for tests). `plugin/templates/answers-casebook.json`
answers every question for the sample database.

## Slots and pack keys

Every brief slot and every register name has an answer key and a core default, asked in the stage that owns it, so a corpus that already
has its own vocabulary (register files, findings headings, watch names, exemplars, report keys) keeps it without hand editing. After its
own questions each of stages 1 to 7 asks two grouped questions, both shown with every key's current value (the stage's result, else the
core default):

- `N.slots`: a JSON object of brief slots this stage owns (`tools/ledger/setup_stages.py` `SLOT_STAGE`; a slot named by its dotted key,
  such as `actor_register.findings_heading`). The free-text slots are offered as keep the default (`{}`) or write your own.
- `N.pack`: a JSON object of pack.toml keys in this stage's sections (`PACK_SECTIONS`), dotted (`objects.register`) or nested; a dict
  value is merged into the section, not put in its place. `pack.name` and `pack.root` are fixed; stage 7 also owns any section no stage
  names (a pack's own settings, such as a bulk archive's).

A single key, `N.slot.<name>` or `N.pack.<dotted key>`, answers one value alone and wins over the grouped answer. A key outside the
stage is refused with the stage that owns it. Ownership: stage 1 the name, referent and requirements; stage 2 archives and the layout;
stage 3 subjects, audited subjects, the audit's headings and captions, eras, circles, compilers, source kinds and the narrative slots;
stage 4 the actor and object registers (files, findings heading, line and what, watch heading and name, criteria column, vocabulary),
speakers and stock phrases; stage 5 canon and codebook; stage 6 lenses; stage 7 catalysts, skeleton forms, report keys, exemplars, free
sections, the model policy, display and tools. The question itself (exit 3) carries the current values in its `context`. Every slot of
a stage is written to slots.toml, the core default shown where neither the stage nor an answer gave one, so a finished setup renders
its briefs with no slot from the core defaults (the pack check's `slots_from_defaults` is 0).

## Pack files: generated or imported

Every file a pack key can name comes from one of two places.

- Generated (the main path: a recipient has no pack to import from), by the stage that owns its content, from the answers and the
  scan: stage 1 the `[question]` section and the seeds (narratives.md with the question and the referent, theses.json, placeholders
  for catalysts.md and circles.md); stages 1, 2, 4, 5 and 7 the keyword lists of `vocabulary.keywords_dir` (pir-terms.txt and terms.txt
  from the requirements' terms and the codebook's codes, people.txt, organisations.txt and actor-polity.txt from the scan and the
  flags, catalyst-keywords.txt from the catalysts, stock-phrases-domain.txt, name-aliases.json from the scan's aliases, id-patterns.tsv
  from the identifier forms the scan proposes, a README); stage 3 circles.md; stage 4 detected-candidates.md, the actor and polity
  vocabulary, the order-of-battle seed (the proposed placements, unplaced), the reference-objects page, the object register page in
  the core form, and the actor register page with its actor table in the row shape of the pack's actor_register slot (its first
  backticked table row that is not the statement shape; else the core header) and its polity statement table in `ledger integrate`'s
  shape (the candidates listed as unplaced rows that no parser counts); stage 5 canon/texts.md, one unit
  scheme per text (canon/schemes/<id>.json: the answer's own scheme, else a headings scheme on its unit pattern, else the canon
  adapter's scheme for the unit named) and codebook/codebook.md; stage 6 the lens instances; stage 7 catalysts.md, skeleton-forms.toml
  (`7.skeleton_forms` and `7.skeleton_grid`; with none, the core forms of tools/note_skeleton.py, shown in its comments) and
  briefs/README.md (every slot, its stage, its value, and whether it is the core default).
- Imported, when an answer names a file or folder under another pack (a folder with a pack.toml that is not this pack's), by a
  relative path or an absolute one: the file is copied into this pack at the same place under the pack's folder, the key and the slot
  texts that name it are repointed, and the provenance (the key, the source, its bytes and SHA-256, the stage, who and when) goes to
  `setup/imports.json` and the stage file's `[[imported]]`. pack.toml, briefs/slots.toml and schema-extensions.md are written from the
  answers and never copied (a value naming the other pack's file of that name points at this pack's own). Once an answer names a file
  under another pack (the source pack), each stage also brings the source pack's files that no answered key names: every
  pack-relative path a slot of the stage names in the source's briefs/slots.toml (or in the stage's slot texts), and every
  pack-relative path a value of the stage's sections holds in the source's pack.toml (when this pack's key is unset or names the same
  place); provenance as above, with `named_in`. Stage 1 imports the source's narrative and thesis seeds instead of generating them
  empty. These imports keep the guards of a generated file: never outside the pack or the project, never over a pack file edited
  since setup wrote or imported it (kept, and listed in the stage file's `[[import_kept]]`).

A generated file never replaces an imported one; a file outside the pack (a register page, a tool's data file) is written only when it
is absent; nothing is written where the real path leaves the project folder (a linked folder); a pack file edited since setup wrote it
is kept (`setup/generated.json` holds what setup wrote); a key given empty names no file. Each stage file lists what it generated
(`[generated]`). Stage 7 freezes `research/platform-baseline.json` (tools/build_db.py, then tools/baseline.py) when the project has
none, so `ledger check` passes in a new project; a project that has a baseline keeps it.

## Settings

```
python3 tools/ledger/settings.py show N
python3 tools/ledger/settings.py set N --answers changes.json
python3 tools/ledger/settings.py owed
python3 tools/ledger/settings.py propose N --answers changes.json
python3 tools/ledger/settings.py publish-check viewer|map|docs
python3 tools/ledger/settings.py published viewer|map|docs
```

The rulings log, `rulings.md`, is one markdown table, `| # | Date | Author | Stage | Ruling | Effect | Status |`, the Status cell one of
open, pending, proposed, adopted, withdrawn (tools/build_status.py counts open, pending and proposed as open). Setup's answers are
appended as adopted rulings; a launcher's `propose` appends a proposed ruling and saves the changes under `setup/proposals/` without
applying anything; a project manager adopts it with `set N --answers <the saved proposal>`.

A project manager re-enters stages 1 to 8, the administrator stage 0. The stage re-runs with its earlier answers under the changed
ones; the stage file is rewritten; an adopted ruling names each change, the stage file it supersedes and what it owes; what the change owes goes to
`owed.md` (re-scan and record queue for stage 2; one retroactive forthrightness audit row per note under a newly audited subject, the source
balance and the era pages for stage 3; the detection re-run for stages 1 and 4; canon controls and the codebook test for stage 5; lens
tests for stage 6; the first-utterance tests for a new threshold catalyst; the brief render check always). No note is rewritten: the
engine hashes every note before and after and fails loudly if one changed.

Publishing artifacts is the end user's choice and off by default. `publish-check <target>` allows a publish only when the setting
names the target, the model route is one with artifacts (Claude for Enterprise or the Anthropic API; provider and gateway routes
have none) and claude.ai is reachable; otherwise it prints why, and the skill writes the local file only and says so. `published
<target>` records the date and target in `[display.publish] last_published`.

The audit's core name is "forthrightness" (owner ruling, 2026-10-22): the skeleton pack's `[audit] heading` is `## Forthrightness audit`,
and every text these modules write names the audit from that key.

## Members

`members.toml` lists `[[member]]` entries with `name`, `os_user` (one or more logins) and `roles` (`administrator`,
`project-manager`, `launcher`). The acting member is the OS user (`$LEDGER_USER` where a shared account runs Claude Code). A ruling
needs a project manager or the administrator (stage 0: the administrator); a launch needs any role. `members.py stamp <note> --run
<label>` writes `| **Launched by** | <name>, run <label>, <date> |` after the note's last metadata row, once.

## Tests

`python3 -m unittest tools/ledger/tests/test_setup.py`: stages 0 to 7 against the sample database with the casebook answers and every
pack file asserted; stage 8 to the launch call; resume from a deleted stage file; refusals (no managed settings, no route) and
questions (an unanswered one, the adverse rule explained first, a name placed by hand); settings re-entry with the owed queue and an
untouched note; member checks and the launcher stamp; the hooks, the lock and the manifest; the renderer byte-identical to the
prototype; the plugin and these modules checked before shipping.
