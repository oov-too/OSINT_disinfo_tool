# Step brief: the narrative register (phase 5 of tools/narratives.md)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1008/brief-register.md of 2026-10-08), rendered by the skill into `wip/<run>/briefs/narrate/brief-register.md`; every file operation in the forms of operations.md. The run's own material comes from the run's TOML (`{{run.*}}`); the domain's from the pack (`{{pack.*}}`).

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.rivals}}` | the rival sheets and which rival each kind of page faces | the rival sheets research/narrative-rival-<slug>.md the register lists |
| `{{pack.narrative_seeds}}` | the thesis seeds, with one line each | the seeds in the narrative register |
| `{{pack.blocked_precedent}}` | the precedent named for the pointer row | the pointer-row form of tools/filter-blocks.md section 5 |
| `{{pack.model_policy}}` | model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You write `research/narrative-register.md`: the page that puts every narrative page side by side, draws the family tree (mainlines and their forks), tallies the contradictions that recur across narratives, reads the attackers' objections against the authors' pages, and says what the run found and what to run next. It is the page the owner reads first.

Read first: tools/narratives.md in full, tools/agent-wip.md, then every `research/narrative-*.md` page (synchrony pages, mainlines, forks) in full, then `ledger narrate narratives --all --recurring --tree` (and `--json wip/<task>/narratives.json`).

## The page
Metadata: **Kind** `narrative-register`; **Built**; **Author**; **Pages** (count by kind); **Related** (tools/narratives.md, the synchrony pages, the contradictions page, the leads register).

1. `## Narratives side by side`: `| Page | Mode | Parent | Thesis | Alternative | Span | Lanes | Nodes | Roots | Contradictions | Load (author / attacker) | Load per cluster | Max downstream | Unaffiliated roots | Tests | Broken nodes (attacker) |` from the pages' score lines and the attackers' cards; no composite rank (tools/narratives.md section 6).
2. `## Family tree`: each mainline with its forks and the forks' deltas (load, coverage, anomalies absorbed, nodes broken), one paragraph on what each fork bought and what it broke.
3. `## Contradictions that recur`: the ledger rows that two or more narratives had to take a side on, with the side each took, the flare calls, and whether the narratives agree; these are the next investigations (tools/investigation.md). `| Contradiction | Pages and sides | Flare calls | Agreed? | Downstream (max) | Existing lead |`.
4. `## Signals that recur`: nodes with Role signal that two or more narratives used, with each page's reading; where the readings differ, say so. `| Signal (rows) | Pages and readings | Carrier | Window |`.
5. `## What the attackers found`: per page, the objections by severity (broken nodes, independence overcounts, missing contradictions, strawmanned sides, non-runnable tests) and whether the author's and attacker's score lines differ materially.
6. `## Where the lanes move together`: from the synchrony pages, the co-movements that more than one narrative used, and the dense windows no narrative touched.
7. `## What the pilot says`: one paragraph per thesis on how it fared ({{pack.narrative_seeds}}), one on the base reading, one on the flares, one on the signals layer, one on the lane and pack rules that misfired (the synchrony pages' notes), all row-cited through the pages.
8. `## Next`: the full run (the remaining seeds, the forks not yet built, the attackers), the investigations the recurring contradictions call for, the protocol changes to propose (tools/narratives.md section 8), each as one line with the page that motivates it.
9. `## Leads returned` and `## Relations returned` as in the other briefs (only what no page already returned).

Also (2026-10-09): refine the rival sheets ({{pack.rivals}}) from the pages' Additions (keep their compiled sections, add a `## Refined` section); rank forks by anomalies absorbed and tests, never by load; report load per cluster (`ledger narrate narratives --all` prints it); closures predicted is retired from the score line (owner 2026-10-09, proposal 24): report, per page, only the attacker's count of walls the reading predicts and its rival does not, from the Carriers closures table; rank forks by discriminating anomaly clusters (proposal 28) and tests; mark every fork whose Deltas are dated against a superseded parent line (proposal 31); validate with `ledger extract report-check wip/<task>/report.json --form register`.

Rules: derived page, every statement cites a page section or a row; no claims of its own; no composite ranking; write with the Write tool or Python; checkpoint from the first minute (tools/agent-wip.md); blocked-output rule (tools/filter-blocks.md section 5).

Reply: `{"page": "...", "narratives": N, "forks": N, "recurring_contradictions": N, "recurring_signals": N, "next_items": N, "leads": N, "relations": N, "notes": "..."}`.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` from the first minute with the step reached and the next step; the deliverable saved after every step; `report.json` built incrementally; `current-unit.md` before every large write (by the copy operation of operations.md); on any resume read your wip folder first and continue from the last completed step, never from scratch. Tool outputs you are given (digest, sweep, interests seed, audit) are files: read them with the Read tool; never pass their text, or any source text, through your own reply. Before replying run `ledger extract report-check <your report.json> --form <form>` and fix every problem it lists; a failing report is never sent. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), where in the deliverable it belongs, and one neutral sentence on what it is about (not the text); enter a pointer row at that place in the deliverable with the marker `[BLOCKED: see <source location>; wip/<task>/blocked/<n>.md; awaiting human summary]` (speaker, time and topic filled; Move n/a; `attribution: n/a (pointer); chain: 1: <speaker> (n/a)`, Source class `host`, the Note cell "An API output filter blocked every attempt to catalogue this passage on <date>; the owner has the source" ({{pack.blocked_precedent}})); note it in progress.md; list it in the reply JSON under `blocked_passages`; and finish everything else. The owner will read the source, write a summary, and the orchestrator will splice it in under the owner's name; your work resumes from there. Prevention: never pass a fetched text through your own output (copy files by the copy operation of operations.md); before each large output copy the unit's source material to `wip/<task>/current-unit.md` by that operation and name it in progress.md; write note parts of about 1,500 words and run `ledger extract verbatim <part>` on each as its own call; record findings per source as you read.
