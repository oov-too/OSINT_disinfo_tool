---
name: attack
description: Attack one narrative page under the method's tests A and B (two attackers in parallel), then write the Objections, the attacker card, leads and the rival sheet's Additions.
argument-hint: "<narrative page>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(ledger *), Bash(python3 ledger.py *), Bash(python3 tools/*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /attack

You orchestrate an attack on one narrative page. Agents: two `attacker`s for tests A and B in parallel, then one `attacker` for the
write step; Opus at high effort (fixed). File operations through `ledger`, Python or your own file tools only.

1. `python3 tools/ledger/members.py check --action launch`; `lock.py acquire page-<slug> --run <label>`; `runlog.py start <label> --skill attack`.
2. Render: `python3 tools/ledger/briefs.py render --project . --templates "${CLAUDE_PLUGIN_ROOT}/templates/briefs" --run packs/<pack>/briefs/runs/<label>.toml --only operations.md narrate/ --out wip/<label>/briefs`.
3. Before the agents: `ledger narrate narratives --audit <page> --out wip/<label>/audit.md`; `--diff` against
   `ledger narrate snapshot --latest <page>`; `ledger narrate adoptions <page> --out wip/<label>/adoptions.md`.
4. Agents A and B with `wip/<label>/briefs/narrate/attack-tests.md` and `brief-attack.md`, writing `findings-A.md`, `findings-B.md`
   and `report-tests-A.json`, `-B.json`; then the write agent with `attack-write.md`: the page's Objections section and the attacker
   card under the Score card, `wip/<label>/leads.json`, the rival sheet's `## Additions`, `report.json` (form attack). The plugin's
   report check holds each agent until its report passes.
5. After: `ledger integrate leads` with the run's leads.json; the history move of the Objections; release the lock;
   `runlog.py end <label> ...`; `/ledger:status`.

An agency's or a critic's contradiction of a witness is a party's statement, recorded as a divergence and a lead, never a
correction; ordinary grounds are excluded before a wall is read as concealment.
