# Phase: check (revise, step 1 of 3)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1009/phases/check.md of 2026-10-09), rendered by the skill into `wip/<run>/briefs/narrate/check.md`; every file operation in the forms of operations.md.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.narratives}}` | the pack's narrative pages, register, rival sheets, history and digests | the narrative register and the pages it lists |
| `{{pack.model_policy}}` | the model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You check every objection in the page's latest Objections section against the objection's own rows and the leads on them, and write a decisions file. You do not edit the page.

Read: `ledger narrate narratives --section <page> "latest:Objections"` (your whole input, with the page's Nodes table via `--section <page> Nodes` and the ledger via `--section <page> "Contradiction ledger"` for the rows the objections name); tools/narratives.md section 6 (the revision rule) and section 10b. For a fork also `--section <parent> "latest:Objections"` and the parent's Score card. Collect every row reference the objections cite into `wip/<task>/refs.txt` and read them with one `ledger narrate narratives --rows wip/<task>/refs.txt`, saved to `wip/<task>/rows.txt` by the save operation of operations.md; read the leads named with the database query of operations.md (`select n, status, lead from leads where n in (...)` on notes.db).

Write `wip/<task>/decisions-objections.tsv` with columns: objection | verdict (adopt / adopt in part / decline) | rows read | leads checked | what the writer must change (exact: node numbers, ledger rows, edges, cells, wording) | why (one line, naming the rows that decide it). A decline names the rows that fail to say what the objection says. Every objection gets a row; an adopt with an empty rows-read cell is a failure. Then `wip/<task>/report-check.json`: {"objections": N, "adopt": N, "part": N, "decline": N, "blocked_passages": []}. Reply with that JSON.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` in your wip folder from the first minute with the step reached and the next step; every output file saved as you go; on any resume read your wip folder first and continue from the last completed step, never from scratch. Read sections and rows, never whole pages or digests, unless this brief names the file as yours to read in full. Batch your lookups: one `--rows` call with a file of references, never one call per row. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), the bisection result and the reason you infer; put a `[BLOCKED: wip/<task>/blocked/<n>.md]` pointer where the content would have gone; list every such pointer under `blocked_passages` in your report JSON (an empty list when none). Before every large write copy the unit in hand to `wip/<task>/current-unit.md` by the copy operation of operations.md.
