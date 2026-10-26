---
name: narrate
description: Build or revise narrative pages (mainlines, forks, synchrony pages, the register) under the narrative method, from rows already held; pages in parallel, phases as guarded agents.
argument-hint: "<build|fork|revise|synchrony|register> <page or seed>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(ledger *), Bash(python3 ledger.py *), Bash(python3 tools/*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /narrate

You orchestrate a narrative run. Agents: `builder` (candidates, draft, finish-build; synchrony), `reviser` (check, sweep,
write-revise), on Opus at high effort (fixed). File operations through `ledger`, Python or your own file tools only.

1. `python3 tools/ledger/members.py check --action launch`; then `lock.py acquire page-<slug> --run <label>` for each page the run
   writes (or `pages` for the register); `runlog.py start <label> --skill narrate`.
2. The run's TOML `packs/<pack>/briefs/runs/<label>.toml` (`[run]` date, new_material, flare_documents, new_events) with the Write tool.
3. Render: `python3 tools/ledger/briefs.py render --project . --templates "${CLAUDE_PLUGIN_ROOT}/templates/briefs" --run packs/<pack>/briefs/runs/<label>.toml --only operations.md narrate/ --out wip/<label>/briefs`.
   A missing slot stops the run (exit 1 names it).
4. Before the agents: `ledger narrate pack` and `ledger narrate digest` (the seed digests); for a revision, `ledger narrate snapshot`
   of the page and `ledger narrate narratives --diff` against the last snapshot.
5. The workflow `tools/workflows/staged-page.js` (pages in parallel, phases as guarded agents), naming the rendered phase and step
   briefs in each phase's prompt. Every node cites held rows; the score line comes from `ledger narrate narratives --check`.
6. After: `ledger narrate apply` (returned leads and relations), `ledger analyse first-utterance --narratives`, `ledger narrate viewer`;
   for a revision the orchestrator moves the Objections and the Revision pass to the page's history file.
7. Release the locks; `runlog.py end <label> ...`; `/ledger:status`.

## Publishing (the end user's choice; off by default)

The local file is always written first. Then `python3 tools/ledger/settings.py publish-check viewer`: exit 0 means the project publishes this target, the model route has artifacts and claude.ai is reachable, so publish the page with the Artifact tool and then run `python3 tools/ledger/settings.py published viewer`; exit 1 prints the reason (publishing off, the target not chosen, a provider or gateway route, claude.ai unreachable): publish nothing, and tell the person that the local file is the result and why.
