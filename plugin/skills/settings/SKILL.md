---
name: settings
description: Re-enter a setup stage (1 to 8; stage 0 only for the administrator), show its current values, change them, and record the change as a dated, attributed ruling with what it owes queued in owed.md. Never rewrites an existing note.
argument-hint: "<stage number> [what to change]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash(python3 tools/ledger/settings.py *), Bash(python3 tools/ledger/members.py *), Bash(python3 tools/ledger/briefs.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /settings

You change a setup stage for the group. The engine is `tools/ledger/settings.py` (it re-runs the stage through
`tools/ledger/setup_stages.py`). File operations through Python or your own file tools only; no shell idioms.

1. **Who may.** `python3 tools/ledger/members.py check --action rule --stage <N>`. A project manager may change stages 1 to 8; stage 0
   only the administrator. A member who may not rule (a launcher) may still propose: write the changes file as in step 4 and run
   `python3 tools/ledger/settings.py propose <N> --answers <file>`, which appends a ruling with status `proposed` (not binding; the
   status page lists it as open) and changes nothing else; a project manager adopts it later with `set <N> --answers <the saved proposal>`.
2. **Lock.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py acquire pack --run settings-<N>`; refused means another run holds the pack.
3. **Show.** `python3 tools/ledger/settings.py show <N>` prints the stage's answers, its result and the pack and ledger values it
   set. Present them as a table, then ask what to change. For stage 2 also show `setup/mapping.md`; for stage 4 `setup/scan.md` and
   `packs/<pack>/registers/detected-candidates.md`.
4. **Write the changes** as `setup/changes-<date>-stage-<N>.json` with the Write tool: `{"answers": {"<qid>": <value>}}`, using the
   question ids the stage file lists under `[answers]` (for example `3.audited_subjects`, `4.flags`, `7.catalysts`). Only the changed
   answers are needed; the stage's earlier answers fill the rest.
5. **Apply.** `python3 tools/ledger/settings.py set <N> --answers setup/changes-<date>-stage-<N>.json`.
   - exit 0: the stage file is rewritten, a ruling (status `adopted`) naming each change, what it supersedes and what it owes is
     appended to `rulings.md`, `CLAUDE.md` is regenerated, and what the change owes is queued in `owed.md`. Show the diff and the owed rows.
   - exit 3: a question needs an answer (the same JSON as /setup); ask, add it to the changes file, run again. If it carries
     `explain` (the adverse-source rule), show that first.
   - exit 4: refused; show the reason.
6. **Owed work** is listed, never run silently: re-scans (stage 2), retroactive forthrightness audits for notes under a newly audited
   subject, one row per note (stage 3), the source balance (stage 3), the detection re-run (stages 1 and 4), the canon controls and
   codebook test (stage 5), the lens tests (stage 6), the first-utterance tests (stage 7), and the brief render check. Offer to run
   the ones the person chooses, each through its own skill or command.
7. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py release pack --run settings-<N>`; `/ledger:status`.

**Publishing artifacts** is stage 7's `7.publish_artifacts`: a list among `viewer`, `map`, `docs`, `[]` (off) by default, the end
user's choice. It is kept in `packs/<pack>/pack.toml` `[display.publish]` (enabled, targets, last_published). Say, when it is turned on,
that a skill still publishes only when `python3 tools/ledger/settings.py publish-check <target>` allows it (a model route with
artifacts, claude.ai reachable) and otherwise writes the local file and says so.

/settings never edits a note. If the person asks for a note to change, that is an intake or a revision, not a setting.
