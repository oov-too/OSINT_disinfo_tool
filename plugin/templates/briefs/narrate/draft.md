# Phase: draft (build, step 2 of 4)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/draft.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/draft.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You write the fork page from the candidates file, under brief-fork.md and brief-builder.md of this folder (every rule binds; the sweep and its dispositions come in the next phases). Read: `wip/<task>/candidates.md` in full (yours); the parent's Thesis, Forks entry, Nodes table, latest Objections and Score card by `--section`; the rival sheet your Alternative cites. Carry the parent's newest attacker corrections first.

Write the page in full with every section the briefs require (Thesis, Deltas against the parent with Carried from the parent's attacker, Anomalies absorbed by root cluster and Nodes broken, Nodes with the joining row for every Depends-on edge, Contradiction ledger, Synchrony, Carriers, Interests, Objections placeholder line, Score card with a provisional v0.4 line, Forks, Tests with Tests already run, Leads returned, Relations returned), with the Write tool or Python. Then run `ledger narrate narratives --sweep <page> --out wip/<task>/sweep.md` and split its rows into three chunk files `wip/<task>/sweep-chunk-1.md`, `-2.md`, `-3.md` of equal length by the split operation of operations.md (section headings repeated in each). Then `wip/<task>/report-draft.json`: {"nodes": N, "ledger_rows": N, "sweep_rows": N, "blocked_passages": []}. Reply with that JSON.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
