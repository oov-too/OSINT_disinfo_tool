---
name: report
description: Write an investigation, a synthesis page or a report against a priority intelligence requirement from rows already held, with strands, three verifiers per finding, a synthesis, a completeness critic and a judge, and a citable export of every row cited.
argument-hint: "<PIR id | investigation question | synthesis topic>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(ledger *), Bash(python3 ledger.py *), Bash(python3 tools/*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /report

You orchestrate a report. Agents: `builder` for strands and the synthesis, `attacker` for the verifiers and the completeness critic,
`reviser` for the judge; Opus at high effort (fixed). The protocol is tools/investigation.md (sections 2, 7 and 8); the divergence
and agency rules are tools/schema.md section 10. File operations through `ledger`, Python or your own file tools only.

1. `python3 tools/ledger/members.py check --action launch`; `lock.py acquire page-<slug> --run <label>`; `runlog.py start <label> --skill report`.
2. For a PIR report, read the requirement and its essential elements of information from the pack (`python3 tools/packload.py --get pirs`)
   and the referent object (`--get actors.referent`); each essential element is a strand.
3. Per strand: `ledger analyse evidence` (the evidence pack), `ledger analyse rows`, `ledger analyse relations`, `ledger analyse divergences`,
   `ledger analyse echoes`, `ledger analyse lens` (the pack's lens instances, for the deception reading), `ledger analyse match-leads`.
4. The workflow of tools/investigation.md section 8: strands, three verifiers per finding, synthesis, completeness critic, judge.
   Every finding cites rows; a finding resting on a PIR term alone is struck (requirements surface entries, they place nothing).
5. Write `research/investigation-<slug>-<date>.md` (page kind investigation) or the synthesis page, with dated, row-cited entries;
   the leads with their tests through `ledger integrate leads`; a citable export of every row cited (note, source, unit, line).
7. Release the lock; `runlog.py end <label> ...`; `/ledger:status`.

## Publishing (the end user's choice; off by default)

The local file is always written first. Then `python3 tools/ledger/settings.py publish-check docs`: exit 0 means the project publishes this target, the model route has artifacts and claude.ai is reachable, so publish the page with the Artifact tool and then run `python3 tools/ledger/settings.py published docs`; exit 1 prints the reason (publishing off, the target not chosen, a provider or gateway route, claude.ai unreachable): publish nothing, and tell the person that the local file is the result and why.
