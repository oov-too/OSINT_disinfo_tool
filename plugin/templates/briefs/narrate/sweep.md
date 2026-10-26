# Phase: sweep (revise step 2 of 3; build step 3 of 4)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/sweep.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/sweep.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You disposition one chunk of the page's contradiction sweep: for every row in your chunk, say whether it belongs in the ledger (which existing row, or a new row with its text) or is left out, with a one-line reason. You do not edit the page. Every row in the chunk gets a line; none is skipped.

Read: your chunk `wip/<task>/sweep-chunk-<k>.md` in full (it is yours); the page's Nodes table (`ledger narrate narratives --section <page> Nodes`) and ledger (`--section <page> "Contradiction ledger"`), once. Where a chunk line is an index line (a short form), open the rows you need in one batch (`--rows`), never one at a time. Rules for a ledger row: the row contradicts or drifts against something a node states or rests on; weight = core (1.0) or periphery (0.3) x independent parties (1.0) or same line (0.4) x (1 + downstream / nodes), where downstream is the dependent closure over row-backed edges; a possible flare where an insider or agency party contradicts with high downstream, with the outsider-runnable test that separates error from misdirection.

Write `wip/<task>/sweep-dispositions-<k>.tsv` with the Write tool or Python: ref | disposition (covered: row n / new row / left out) | new row text (contradiction; side taken; why survivable; weight; flare) or reason left out | nodes touched. Then `wip/<task>/report-sweep-<k>.json`: {"chunk": k, "rows": N, "covered": N, "new": N, "left_out": N, "blocked_passages": []}. Reply with that JSON.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
