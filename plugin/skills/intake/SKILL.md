---
name: intake
description: Take one or more held sources (records of the group's database, documents, recordings, web texts) into notes through the staged intake workflow (unit writers by default, the ledger written unit by unit with the unit in context, then gates, writer B and finish), with the pre-pass, the rendered briefs, the hand-back and the status page.
argument-hint: "<record identifier | held path | queue> [--staged] [--check]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(ledger *), Bash(python3 ledger.py *), Bash(python3 tools/*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /intake

You are the orchestrator of an intake in a ledger project. Agents are this plugin's `reader`, `writer` and `finisher` (Opus, high
effort, fixed) and the `probe` (Haiku, pass-through gates only). Every file operation goes through `ledger` (or `python3 ledger.py`
before installation), Python, or your own file tools; never a shell idiom (`<wip>/briefs/operations.md` once rendered).

## 1. Before anything is written

1. `python3 tools/ledger/members.py check --action launch`; refused means stop.
2. Choose the run label `intake-<slug>-<MMDD>` and the task folder `wip/<label>/`.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py acquire notes --run <label> --wip wip/<label>`; refused means another run is
   writing notes: say who, and stop.
4. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py start <label> --skill intake`.

## 2. Acquire and policy

- A record of their database: `python3 tools/ledger/acquire/database.py rescan setup/mapping.toml --records` lists new and changed
  records; `python3 tools/ledger/acquire/database.py run setup/mapping.toml` holds them (queue: `sources/db/<name>/queue.tsv`).
  The held text is the hold's `text.md` or `transcript.md` (its hold.json names it).
- Another source: the matching adapter (`ledger acquire ...`; documents, web texts, recordings, canon texts).
- `ledger analyse balance` (the deficit named in the launch note) and `ledger analyse first-utterance` (the earliest-telling search).
  If the source kind is adverse, the run renders `intake-adverse.md` too.

## 3. Pre-pass and briefs

1. `ledger prepare chunk <held text> --wip wip/<label>`; `ledger prepare skeleton --form <document|video> --task wip/<label> --note <note> --source <held text>`;
   `ledger prepare context <held text> --wip wip/<label>`; `ledger prepare timeline-prepass wip/<label>/units --wip wip/<label>`.
2. The run's TOML at `packs/<pack>/briefs/runs/<label>.toml` with the Write tool: `[run]` label, date, purpose, brief (a short run
   brief beside it).
3. Render: `python3 tools/ledger/briefs.py render --project . --templates "${CLAUDE_PLUGIN_ROOT}/templates/briefs" --run packs/<pack>/briefs/runs/<label>.toml --only operations.md intake- staged/ --out wip/<label>/briefs`.
   Exit 1 names a slot with no value: stop and send the person to /ledger:settings for the stage that fills it.
4. `wip/<label>/TASK.md` and `prompt.md` (tools/agent-wip.md item 0).
5. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py start <label> --skill intake --briefs wip/<label>/briefs` (a second start line
   carrying the rendered briefs' hashes, so the run can be reproduced).

## 4. The workflow

Call the Workflow tool with `scriptPath: tools/workflows/staged-intake.js` and args
`{tasks: [{key, wip, note, form, units, words, source, label}], phasesDir: "wip/<label>/briefs/staged", model: "opus", effort: "high", gateModel: "haiku"}`
(units and words from `wip/<label>/units/manifest.md`). The forms: `unit-writers`, the default (no `intakeForm` needed: one writer per
unit range with the unit in its context, the parts gate after each, the assembly, gate 2, writer B, finish); `staged`, the
read-and-writer-A form, kept for comparison (`--staged`: `intakeForm: "staged"`); `check`, optional in either (`--check`:
`check: true`, with `checkBudget` in rows if the launch note gives one). Request keep-awake before the launch (tools/agent-wip.md
item 9). Dead agents are resumed from their wip folder; a twice-dead agent's
`current-unit.md` goes to bisect-block. The plugin's hooks run the verbatim check after every part, the database build into
`wip/<label>/check.db` after every note write, and the report check when an agent stops; none of them fails a write.

## 5. Hand-back

1. `ledger integrate wip/<label>/report.json` (stops at the first failing step and names it).
2. `python3 tools/ledger/members.py stamp <note> --run <label>` (the launcher in the note's metadata).
3. `ledger integrate blocked register` if the report lists blocked passages.
4. `ledger measure health` and `ledger measure usage` for the run log; `runlog.py end <label> --units N --agents N --deaths N --resumes N --cost "<usage line>"`.
5. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py release notes --run <label>`.
6. `/ledger:status`.
