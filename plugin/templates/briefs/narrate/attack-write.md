# Phase: write (attack, step 2 of 2)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/attack-write.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/attack-write.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You assemble the two findings files into the page's Objections section and the attacker's score card, write the leads file and the rival sheet Additions, and nothing else. Follow brief-attack.md's section "What you write" exactly.

Read: `wip/<task>/parts/tests-A.md` and `wip/<task>/parts/tests-B.md` in full (yours; if absent, look under `wip/<task>/parts/`, and failing that recover the tests agents' replies from the workflow journal named in your task brief's folder); `ledger narrate narratives --section <page> "Score card"`; the page's current Objections heading form (the page's headings with their lines, operations.md). Resolve duplicates and order by severity. Write the section with the heading the orchestrator's prompt names, placed where it says, by exact string replacement with the Edit tool or Python; append the attacker card under `## Score card` with the recomputed axes and one v0.4 line prefixed as the prompt says; prefix an unprefixed author line in place, never leave a second copy. Leads: `wip/<task>/leads.json` as a list of {"lead","kind","sources","settles"}. Rival sheet: add the rows tests-B lists under the sheet's `## Additions`, dated. Then `ledger narrate narratives --check <page>` (the page must still pass) and `ledger extract report-check wip/<task>/report.json --form attack` must pass.

Reply JSON, also at `wip/<task>/report.json`: the attack form of tools/report_check.py (for a fork, notes states `absorbed N clusters, M discriminating`).

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
