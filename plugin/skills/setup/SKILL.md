---
name: setup
description: Set up a ledger project from the group's own database, stage by stage (0 environment, 1 the question, 2 schema mapping, 3 subjects and the adverse-source rule, 4 detected entities, 5 canon and codebook, 6 lenses, 7 members and policy, 8 first intake and the pack check). Resumable; every answer becomes a dated, attributed ruling.
argument-hint: "[status | from-stage N]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash(python3 tools/ledger/setup_stages.py *), Bash(python3 tools/ledger/members.py *), Bash(python3 tools/ledger/briefs.py *), Bash(python3 tools/ledger/acquire/database.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *), Bash(ledger *)
---

# /setup

You are running the ledger's setup for a research group, from the project folder (`${CLAUDE_PROJECT_DIR}`). The engine is
`tools/ledger/setup_stages.py`; you are its interactive form. You never answer a question for the group: you show each question, its
explanation and its evidence, take the person's answer, and write it to the answers file. Every answer becomes a dated, attributed
ruling in `rulings.md`, binding only from members named in `members.toml`.

Every file operation goes through Python, `ledger` or your own file tools (Read, Write, Edit); never a shell idiom (no heredoc, `cat`,
`cp`, `sed`, redirect or `&&` chain): the same steps must run under PowerShell.

## Before the first stage

0. Say this first, before any command: every member must turn off two settings in the Claude app's privacy preferences, 'Location metadata' and 'Help improve our AI models', on their own account, because the agents' sessions will hold the group's sources and notes about named people, and those settings govern what the provider may keep of them; stage 0 asks the administrator to confirm it and records the answer as a ruling, and refuses to go on until it is yes.
1. `python3 tools/ledger/setup_stages.py status --project .` shows which stages are done; setup resumes at the first stage whose file
   (`setup/stage-N.toml`) is missing. Say which stage is next.
2. The answers file is `setup/answers.json`. If it does not exist, create it with the Write tool as `{"answers": {}}`.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py acquire pack --run setup` (one writer on the pack); if it is refused, stop and say
   who holds it.
4. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py start setup --skill setup`.
5. Stage 0 is the administrator's: if `setup/stage-0.toml` is missing, say that the administrator must run it on this machine.

## The loop

Run `python3 tools/ledger/setup_stages.py run --project . --answers setup/answers.json`. Its exit code says what happened:

- **0**: the stages ran to the end (or to `--until`). Report what was written (the `setup/stage-N.toml` files, the pack under
  `packs/<name>/`, `rulings.md`, `CLAUDE.md`).
- **3**: a question needs an answer. The output is JSON: `qid`, `prompt`, `kind` (text, bool, int, list, json), `choices`,
  `default`, `context`, `explain`, `error`. Then:
  1. If `explain` is present, show it to the person in full **before** the question (stage 3's adverse-source rule must be explained
     before it is chosen: what it does, and that it never makes adverse sources more reliable, scores who is right, or lets a
     sceptic correct a witness).
  2. Show the evidence: read the files the context names (`setup/mapping.md` for the mapping table with confidence, evidence and
     alternatives; `setup/dry-run.md` for the five records; `setup/scan.md` for detected names, speakers, actors, polities,
     placements and adverse position markers) and present the part that bears on the question.
  3. If `error` is present, the previous answer was refused: say why.
  4. Ask the person. Offer the default if there is one; never pick it for them.
  5. Write the answer into `setup/answers.json` under `answers.<qid>` with the Edit tool (JSON: a list for `list`, an object or list
     for `json`, `true`/`false` for `bool`).
  6. Run the loop command again.
- **4**: setup refused (stage 0 without a model route or a managed settings file; a stage 8 pack check that failed; a member check).
  Show the reason and stop; do not work around it.
- **5**: stage 8 built the first intake's launch (`launch_pending` in the output; the same in `setup/stage-8-launch.json`). Then:
  1. Run each command of `prepass` in order (they are `ledger` commands; use `python3 ledger.py ...` if `ledger` is not installed).
  2. Read `<wip>/units/manifest.md` and set each task's `units` and `words` from it.
  3. Call the Workflow tool with `scriptPath` and `args` from the launch (the staged intake: reader, writer and finisher agents of this
     plugin on Opus at high effort; gates by the probe on Haiku).
  4. When it returns, run each command of `after` in order (`ledger integrate`, the launcher stamp in the note's metadata, then
     `python3 tools/ledger/setup_stages.py launched ...`, which records stage 8 and offers the note as the form's exemplar).

## Stage notes the person should hear

- **Stage 1**: the pack's name, the question, who or what the inquiry is protecting (every actor is later described by its stance
  toward this), and the questions the group most needs answered, each with the facts that would answer it. Say in plain words that
  these questions are an overlay with a date on it: they seed the search terms and bring matching entries forward, and they never put
  anything into the record that the sources do not support. Setup refuses a pack name whose
  `packs/<name>/` already exists in the folder (it never overwrites a pack), and the name is fixed once stage 1 has run.
- **Stage 2**: the engine introspects their database (tables, columns, types, keys, samples) and proposes a column or an expression
  per hold field with its confidence, evidence and alternatives, and the record unit. Required fields with no column are asked.
  Unmapped columns are kept whole as metadata and can be promoted to pack keys. Tables of their own coding (claims, tags, speakers,
  relations, events) are offered for import into the registers with their database as the teller, marked as the group's reading.
  Where a record's text can live in several places (transcript rows, a body column, text attachments), the sources are shown in the
  order they are tried per record and the group confirms, reorders or drops them (`2.text_order`); the annotation tables' columns
  for text, author, kind, date and attribution can be changed (`2.annotations.<table>.columns`). Five records are held as a dry run
  before the mapping is saved (the dry run shows which source gave each record its text); then the hold and the scan run. If a
  mapping was saved before, a re-scan reports the differences.
- **Stage 4**: the scan has found the people, organisations and groups the sources talk about, who speaks, and how they relate
  (setup/scan.md). Explain before asking: the group reviews this list by marking names, and marking does two things only, it brings a
  name forward in every report and it tells the search what to watch for; it never changes what the sources say about anyone, and a
  name the scan did not find cannot be added by hand, because the picture is built from the sources and not from the group's prior
  view. Show the scan's list in plain terms (name, what kind of thing it is, which others it belongs to) before the question.
- **Stage 6**: a lens is a known playbook of disinformation or misleading techniques, taken from a person who described one or from a text (a manual,
  doctrine, playbook or treatise). Each technique stays attributed to its source and is matched to the core catalogue of techniques
  (the file the pack's `[lenses] catalogue` names). Say that nothing is read through the lens yet: that happens when sources are read.
- **Stage 7**: the members and their roles (administrator, project manager, launcher), the model route, the budget, the
  no-omission rule (no work left out to save cost), the turning points after which people may have changed their story, the
  private-individuals rule, and whether to publish artifacts (viewer, map, docs; off by default, the end user's
  choice; even when on, a skill publishes only if the model route reaches claude.ai, else it writes the local file and says so).

## After

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py release pack --run setup`, then
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py end setup`, then `/ledger:status`.

Briefs are rendered at run time from the plugin's templates with this project's pack slots:
`python3 tools/ledger/briefs.py render --project . --templates "${CLAUDE_PLUGIN_ROOT}/templates/briefs" --run <run.toml> --only operations.md intake- staged/ --out <wip>/briefs`
(exit 1 names any slot without a value). Stage 8 does this itself.
