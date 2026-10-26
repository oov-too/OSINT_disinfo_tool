# Phase: candidates (build, step 1 of 4)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/candidates.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/candidates.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You read the builder digest in full, index lines included, in an otherwise empty context, and write the shortlist the drafter builds from. You do not write the page. Every row of the digest is read; the shortlist says what was kept and, per digest section, how many rows were set aside and why in one line.

Read: the fork's definition in the orchestrator's prompt; the parent's Forks entry and the parent's Nodes table (`ledger narrate narratives --section <parent> Forks`, `ledger narrate narratives --section <parent> Nodes`); the seed's digest (`ledger narrate digest`; the path the prompt names) in full (yours). Open index rows that may bear on the fork in batches (`--rows`).

Write `wip/<task>/candidates.md`: (1) node candidates in date order, each with the rows (`[note tl n]` / `[note claims n]`), carriers, the lane, and one line on why it belongs to the fork and not only the parent; (2) the rows the parent left as anomalies that the fork would place, grouped by independent root cluster; (3) the contradictions the digest lists that touch the fork's nodes; (4) the carriers and the circles they belong to; (5) per digest section: rows read, rows kept, rows set aside and the one-line reason. Then `wip/<task>/report-candidates.json`: {"rows_read": N, "candidates": N, "anomaly_clusters": N, "blocked_passages": []}. Reply with that JSON.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
