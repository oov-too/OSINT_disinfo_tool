# Step brief: fork builders (phase 3 of tools/narratives.md)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1008/brief-fork.md of 2026-10-08), rendered by the skill into `wip/<run>/briefs/narrate/brief-fork.md`; every file operation in the forms of operations.md. The run's own material comes from the run's TOML (`{{run.*}}`); the domain's from the pack (`{{pack.*}}`).

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.synchrony_eras}}` | the era windows of the synchrony pages and the era page each reads | one window per era page of the pack |
| `{{pack.rivals}}` | the rival sheets and which rival each kind of page faces | the rival sheets research/narrative-rival-<slug>.md the register lists |
| `{{pack.blocked_precedent}}` | the precedent named for the pointer row | the pointer-row form of tools/filter-blocks.md section 5 |
| `{{pack.model_policy}}` | model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You build one fork narrative page `research/narrative-<parent>-fork-<n>.md` from one named contradiction in a parent mainline narrative. A fork takes the side the parent rejected as true and rebuilds the story forward from that node: which parent nodes change or fall, which rows the parent left as anomalies now fit, which rows that fitted now contradict. A fork is reported against its parent as deltas (load, coverage, anomalies absorbed, nodes broken), never as a verdict.

Read first: tools/narratives.md (sections 1, 5, 6, 8), tools/agent-wip.md, tools/investigation.md section 2.2, then the parent page in full, then `brief-builder.md` of this folder (the builders' rules apply to you unchanged, including the owner's reading, the blocked-output rule and the checkpointing).

## Inputs
- The parent page (named in your prompt) and its fork node (the ledger row number named in your prompt): the contradiction, the side the parent took, the other side, the parent's Downstream list.
- The synchrony pages `research/narrative-synchrony-*.md` ({{pack.synchrony_eras}}), the parent's evidence pack under `wip/<run>/packs/`, the pack sheets under `wip/<run>/pack/`, notes.db read-only.

## Tools first (token rule, 2026-10-09)
Start from the parent's page and its audit (`ledger narrate narratives --audit <parent> --out wip/<task>/parent-audit.md`), the digest for the parent's seed (`wip/<run>/digests/<seed>.md`) and the rival sheets ({{pack.rivals}}); seed Interests with `--interests`; run `--sweep` on your page before the ledger; forks are ranked by anomalies absorbed and the discriminating tests named, not by load; validate with `--check` and `ledger extract report-check --form fork`.

## Rules (in addition to the builders' rules)
- Carry the parent attacker's corrections first: read the parent's `## Objections`, repair or drop every broken node and remove every unsupported edge before you rebuild, and list what you carried under `### Carried from the parent's attacker` inside `## Deltas against the parent`.
- Deltas are measured against the parent's attacker score line and attacker-corrected graph; any graph correction of your own goes on its own line of the Deltas table. Re-measurement (proposal 31): when a parent is revised, every fork of it is re-measured against the parent's new attacker line in the next revise step; until then its Deltas table carries the line `dated: measured against parent line of <date>`. A revise task on a fork always re-measures first.
- Name one flare reading at the fork node (misdirection or error) and carry it through every node; a node that needs the other reading is a sub-fork candidate, not a switch.
- The fork node comes first in the Nodes table, marked Role `cause` with `fork node` in the Node cell; every later node says in Depends on whether it is inherited unchanged from the parent (`parent n`) or rebuilt (`rebuilt`).
- Flare reading is mandatory at the fork node: if the parent called the contradiction a possible flare, the fork must say what the story looks like if the flare is misdirection and what if it is error, and which the fork assumes.
- The fork is the loser's story told as well as it can be told, not a strawman: cite the best rows for the taken side, state its strongest objection at once.
- Carry every inherited caveat; collapse independence the same way; keep interests symmetrical.
- No word cap; write with the Write tool or Python; checkpoint from the first minute.

## The page
Metadata: **Kind** `narrative`; **Mode** `fork`; **Parent** `[<parent title>](narrative-<parent>.md), ledger row <n>`; **Thesis**; **Alternative** (the parent's side, in one sentence); **Span**; **Lanes**; **Built**; **Author**; **Status**; **Related**.
Sections exactly as the builders' brief (Thesis, Nodes, Contradiction ledger, Synchrony, Carriers, Interests, Objections (one line: written by the phase 4 agent), Score card, Forks, Tests, Leads returned, Relations returned), plus, between Thesis and Nodes, `## Deltas against the parent`: `| Measure | Parent | Fork | Delta |` with rows clusters, rows, roots, contradictions, load, max downstream, unaffiliated roots, tests (v0.4, no closures predicted); then `### Anomalies absorbed` grouped by root cluster (proposal 28): one entry per independent root cluster of rows the parent left as new, unexplained or closed-subtle that the fork places, each row-cited, each marked `discriminates` (the parent cannot place it) or `fits both`; the summary line reads `absorbed N clusters, M discriminating`, and the fork is ranked on M and its tests and `### Nodes broken` (parent nodes that fall, by number, with why).
Score line in the exact form: `Narrative scores: clusters N, rows N, roots N, circle roots N, reading roots N, contradictions N, load X.X, max downstream N, closures predicted N of N, unaffiliated roots N of N, survive under rival N of N, tests N.` (definitions as in the builders' brief).

## Reply
Final JSON, also at `wip/<task>/report.json`: `{"page": "...", "parent": "...", "fork_node": N, "nodes": N, "inherited": N, "rebuilt": N, "roots": N, "contradictions": N, "load": X.X, "delta_load": X.X, "delta_coverage": N, "anomalies_absorbed": N, "anomaly_clusters": N, "discriminating_clusters": N, "nodes_broken": N, "flare_assumed": "misdirection|error|n/a", "tests": N, "leads": N, "relations": N, "notes": "..."}`.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` from the first minute with the step reached and the next step; the deliverable saved after every step; `report.json` built incrementally; `current-unit.md` before every large write (by the copy operation of operations.md); on any resume read your wip folder first and continue from the last completed step, never from scratch. Tool outputs you are given (digest, sweep, interests seed, audit) are files: read them with the Read tool; never pass their text, or any source text, through your own reply. Before replying run `ledger extract report-check <your report.json> --form <form>` and fix every problem it lists; a failing report is never sent. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), where in the deliverable it belongs, and one neutral sentence on what it is about (not the text); enter a pointer row at that place in the deliverable with the marker `[BLOCKED: see <source location>; wip/<task>/blocked/<n>.md; awaiting human summary]` (speaker, time and topic filled; Move n/a; `attribution: n/a (pointer); chain: 1: <speaker> (n/a)`, Source class `host`, the Note cell "An API output filter blocked every attempt to catalogue this passage on <date>; the owner has the source" ({{pack.blocked_precedent}})); note it in progress.md; list it in the reply JSON under `blocked_passages`; and finish everything else. The owner will read the source, write a summary, and the orchestrator will splice it in under the owner's name; your work resumes from there. Prevention: never pass a fetched text through your own output (copy files by the copy operation of operations.md); before each large output copy the unit's source material to `wip/<task>/current-unit.md` by that operation and name it in progress.md; write note parts of about 1,500 words and run `ledger extract verbatim <part>` on each as its own call; record findings per source as you read.
