# Step brief: synchrony pages (phase 1 of tools/narratives.md)

Core template (platform phase 4, 2026-10-22; from wip/narratives-1008/brief-synchrony.md of 2026-10-08), rendered by the skill into `wip/<run>/briefs/narrate/brief-synchrony.md`; every file operation in the forms of operations.md. The run's own material comes from the run's TOML (`{{run.*}}`); the domain's from the pack (`{{pack.*}}`).

| Slot | What it holds | Core default |
|---|---|---|
| `{{run.date}}` | (run) the run's date, used for Built, Added and the revision marks | (the run TOML gives it) |
| `{{pack.synchrony_eras}}` | the era windows of the synchrony pages and the era page each reads | one window per era page of the pack |
| `{{pack.lanes}}` | the lane letters and what each holds (tools/narratives.md section 3) | the generic lanes of tools/narratives.md section 3 |
| `{{pack.narrative_seeds}}` | the thesis seeds, with one line each | the seeds in the narrative register |
| `{{pack.eras}}` | era ids, boundaries and pages; the scope start year | the master timeline only |
| `{{pack.narrative_reading_list}}` | the pack's own reference pages a builder consults | none |
| `{{pack.blocked_precedent}}` | the precedent named for the pointer row | the pointer-row form of tools/filter-blocks.md section 5 |
| `{{pack.model_policy}}` | model, effort and probe rule | every reading or writing agent on the most capable model at high effort |

You are one of the run's synchrony agents, one per era window ({{pack.synchrony_eras}}), each writing one era's synchrony page: `research/narrative-synchrony-<era>.md`. The page says what each lane does in the era ({{pack.lanes}}), which lanes move together and when, the era's contradictions with their impact and flare flags, the era's signals (walls and what is said near them), the organisations' lifecycle, and what the era offers each narrative thesis seed ({{pack.narrative_seeds}}). The narrative builders (phase 2) will read your page before anything else, so it must be complete for its era and cite rows for everything.

Read first, in this order: tools/narratives.md (the protocol; sections 1, 3, 5a, 6 and 8 matter most), tools/agent-wip.md (checkpointing, mandatory), tools/investigation.md section 2.2 (the moves), tools/schema.md section 2 (source classes, the chain-of-custody column).

## Inputs

- `wip/<run>/pack/synchrony/<era>.md` (the run's narrative pack, `ledger narrate pack`): every dated timeline row of your era, grouped by window (year; quarter from the pack's quarter-start year) and lane, each with its chain root, agreement kind and the mechanical lane rule applied. Read it in full; it is your primary input. It is large: read it in slices by window (the Read tool with offset and limit), and record findings per window in `wip/<task>/parts/findings.md` before moving on (agent-wip rule 8).
- `wip/<run>/pack/synchrony-index.md`: counts by window and lane, the dense windows, the lane rules.
- `wip/<run>/pack/contradictions.md`: every contradiction and drift node ranked by provisional impact, with insider and agency marks. Take the nodes whose note row or date falls in your era (search the era's years and the notes you meet with the Grep tool).
- `wip/<run>/pack/speakers.md` and `signals.md`: one sheet per carrier (span, classes, topics, closures, affiliations, opponents; the walls and what is said near them). Consult the sheets of the carriers active in your era.
- The consolidated era page (`research/timeline-consolidated-<era>.md`; the pack's mapping of windows to era pages and its scope start: {{pack.synchrony_eras}}): the era's event clusters already made. Cite its cluster IDs (K-numbers, block names) beside your row citations when a cluster exists.
- The consolidated timelines' contradictions page (#n and Dn clusters), `research/divergence-patterns.md`, `research/echo-patterns.md`, `research/relations-register.md` (query with `ledger analyse relations`), `research/leads-and-inferences.md`, and the pack's reference pages ({{pack.narrative_reading_list}}).
- notes.db, read-only (the database query of operations.md: `python3 -c "import sqlite3; [print(*r, sep=' | ') for r in sqlite3.connect('notes.db').execute('<select ...>')]"` (interim form; `ledger db sql` to build)), for anything the pack cut; the notes for the original rows and their prose.

## Rules

- A derived page: no claims of its own. Every statement cites rows as `[note tl n]` or `[note claims n]` (note = the note's file stem), with class and chain root where independence matters. Your tables are cited by the narrative pages in one form only (proposal 30, owner 2026-10-09): `[synchrony <era> <table> <row>]`, so every table keeps its `#` column stable and never renumbers. Where the era page has a cluster, cite it too.
- Independence is counted in chain roots, not mouths: a retelling by the same speaker is one root; a host relaying a guest is the guest's root; an unnamed teller is a root of its own but is marked unnamed; echoes (research/echo-patterns.md) collapse to one root. Say how many roots after collapse.
- An agency's or official's contradiction of a witness is a lead, never a correction (the agency rule, tools/schema.md section 10).
- Openness is not truth. A wall (stated decline, closed-outright, closed-subtle) is a boundary, never a denial and never evidence for the content behind it. A hint (an omission, speaking around a thing, an offhand remark) is recorded as a signal with the rows and your reading; it is never promoted to a claim or an event.
- Flare rule: a high-impact contradiction whose party is an insider (speakers.md marks them) or an agency may be misdirection; write `possible flare: <why>` or `no`, and say what would separate error from misdirection.
- Lanes: {{pack.lanes}}. The pack's lane is mechanical; reassign a row when it is wrong and say `lane A (pack said B)`.
- Material before the pack's scope start year ({{pack.eras}}) enters only as an antecedent a later carrier invokes.
- The seeds (`seeds.md` of the run's pack): {{pack.narrative_seeds}}.
- No word cap. Every co-movement, every contradiction node of score 1.0 or more in the era, and every signal you find gets a row. Lane prose accounts for the era's rows in aggregate (counts and representative rows), not row by row.
- Write with the Write tool or Python, never by passing long source text through your own output; copy the unit in hand to `wip/<task>/current-unit.md` before each large output (agent-wip rules 7 and 8).

## The page (headings exact; tools/narratives.md section 5a)

Metadata table (two columns, bold keys): **Kind** `narrative-synchrony`; **Era**; **Built** {{run.date}}; **Author** (your task label); **Sources** (the pack, built {{run.date}} from notes.db; the era page; notes consulted); **Rows considered** (how many pack rows, how many clusters); **Status** (`in progress` until done, then `complete`); **Related** (links to the era page, the contradictions page, tools/narratives.md).

1. `## Lanes in this era`: one paragraph per lane: what the lane does across the era, who the roots are, what is absent; no row lists (trimmed 2026-10-09).
2. `## Windows`: dense windows only (three or more lanes active): `| Window | Lanes active | What moves | Carriers (roots) | Rows | Reading |` (trimmed 2026-10-09). Reading: causal, coincident, or the same story told twice.
3. `## Co-movements`: `| # | Window(s) | Lanes | What moves together | Independent roots | Rows | Reading | Bears on seeds |`, ranked by independent roots. These are the era's cross-lane patterns: the thing the builders need most.
4. `## Contradictions`: `| # | Pack rank | Window | Node | Side A (rows) | Side B (rows) | Parties | Insider or agency | Provisional impact | Flare | Bears on seeds |`.
5. `## Signals`: `| # | Carrier | Window | Wall (rows, ground) | Near the wall (rows) | Reading |`. The window is the era of the thing withheld or hinted at, even when the wall is spoken later.
6. `## Organisations`: `| Body | Event | Window | Rows | Roots |` (lane H lifecycle: founded, renamed, staffed, moved, dissolved).
7. `## For the builders`: one `### <seed>` subsection per seed, in the order of `seeds.md`: what the era offers for and against each thesis, the nodes a builder should take (by row), the contradictions it must take a side on.
8. `## Leads returned`: `| # | Lead | Kind | Asked by | Sources | What would settle it | Status | Answer | Answered by | Answered on | Added |` with # blank, Asked by `page narrative-synchrony-<era>`, kinds thread, inference, divergence or absence, Status open, Added {{run.date}}.
9. `## Relations returned`: `| a | b | kind | hierarchy | when | what | source | chain | confidence |` for edges the era's rows show that the register lacks (check with `ledger analyse relations` first).

## Checkpointing (tools/agent-wip.md, mandatory)

Your wip folder is named in your prompt. From the first minute: `progress.md` (what is done, next, files touched; overwrite each time), `parts/findings.md` (per-window findings as you read), `report.json` (built up incrementally), `current-unit.md` (the unit in hand before each large write). Write the destination page section by section with Status `in progress`; set `complete` only at the end. Never delete your wip folder.

## Reply

Final JSON, also saved to `wip/<task>/report.json`: `{"page": "...", "rows_considered": N, "windows": N, "co_movements": N, "contradictions": N, "flares": N, "signals": N, "leads": N, "relations": N, "lane_reassignments": N, "notes": "anything the orchestrator should know, including caps you hit and notes you could not read"}`.

## WIP, resume and output errors (standing)
Follow tools/agent-wip.md: `progress.md` from the first minute with the step reached and the next step; the deliverable saved after every step; `report.json` built incrementally; `current-unit.md` before every large write (by the copy operation of operations.md); on any resume read your wip folder first and continue from the last completed step, never from scratch. Tool outputs you are given (digest, sweep, interests seed, audit) are files: read them with the Read tool; never pass their text, or any source text, through your own reply. Before replying run `ledger extract report-check <your report.json> --form <form>` and fix every problem it lists; a failing report is never sent. {{pack.model_policy}}

> **Blocked output (standing rule, tools/filter-blocks.md).** If an output is refused or an extraction fails on a passage twice, do not retry a third time and do not paraphrase around the filter. Bisect the unit until the smallest failing piece is found, recording each attempt in `wip/<task>/bisect-<unit>.md`; write `wip/<task>/blocked/<n>.md` with the source location (file, lines or h:mm:ss, page), where in the deliverable it belongs, and one neutral sentence on what it is about (not the text); enter a pointer row at that place in the deliverable with the marker `[BLOCKED: see <source location>; wip/<task>/blocked/<n>.md; awaiting human summary]` (speaker, time and topic filled; Move n/a; `attribution: n/a (pointer); chain: 1: <speaker> (n/a)`, Source class `host`, the Note cell "An API output filter blocked every attempt to catalogue this passage on <date>; the owner has the source" ({{pack.blocked_precedent}})); note it in progress.md; list it in the reply JSON under `blocked_passages`; and finish everything else. The owner will read the source, write a summary, and the orchestrator will splice it in under the owner's name; your work resumes from there. Prevention: never pass a fetched text through your own output (copy files by the copy operation of operations.md); before each large output copy the unit's source material to `wip/<task>/current-unit.md` by that operation and name it in progress.md; write note parts of about 1,500 words and run `ledger extract verbatim <part>` on each as its own call; record findings per source as you read.
