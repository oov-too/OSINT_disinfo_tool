# Phase: finish (build, step 4 of 4)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/finish-build.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/finish-build.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You apply the sweep dispositions to the drafted fork page and finish it. Read: every `wip/<task>/sweep-dispositions-*.tsv` (yours); the page's sections by `--section` as needed. Do (with the Edit tool or Python): add every `new row` to the ledger, add covered citations to their rows; write the one count line under `### Rows read and left out`; recompute the Deltas and `### Anomalies absorbed` (by root cluster, `absorbed N clusters, M discriminating`); edge audit; the Score card's v0.4 line; `ledger narrate narratives --check <page>` and `ledger extract report-check wip/<task>/report.json --form fork` must pass.

Reply JSON, also at `wip/<task>/report.json`: the fork form of tools/report_check.py.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
