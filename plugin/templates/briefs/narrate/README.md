# Phase briefs of a narrative page task (core template, platform phase 4, 2026-10-22; from wip/narratives-1009/phases/README.md, owner 2026-10-09, token points 1 to 4 and 6)

Templates, rendered by the skill into `wip/<run>/briefs/narrate/` and named in the prompts `tools/workflows/staged-page.js` receives. Slots across the folder: `{{pack.narratives}}` (the pages, the register, the rival sheets, the history and digests), `{{pack.model_policy}}`, and the slots the step briefs of this folder list in their own tables. Every file operation in the forms of operations.md.

A page task is split into short-lived agents with small contexts: each reads the same material once and hands the next phase a file. Tools do the mechanical halves before any agent runs. The standing rules of the step briefs of this folder (brief-revise.md, brief-attack.md, brief-fork.md, brief-builder.md; brief-synchrony.md and brief-register.md for the synchrony and register steps) still bind every phase; a phase brief says only which part of the work is that agent's, what it reads, and what it writes. The method is tools/narratives.md (v0.4).

Revise (mainline or fork): check (objections against their rows) -> sweep (dispositions, chunks in parallel) -> write (apply, edge audit, score line, check).
Attack: tests-a (tests 1 to 4, 5a, 5b on the audit and the diff) and tests-b (tests 5 to 8, the rival, test 9 on the adoption check) in parallel -> write (the Objections section, the score card, leads, rival Additions).
Build (new fork): candidates (reads the digest in full, writes the shortlist) -> draft (the page) -> sweep (chunks) -> finish (dispositions applied, edge audit, score line, check).

Receipts (owner 2026-10-09): every sweep row still gets a reason, but the reasons live in wip/<task>/sweep-dispositions-*.tsv (archived by the orchestrator), not on the page; the page carries one count line. Earlier Objections and Revision passes are moved to the narrative history pages (research/narrative-history/<stem>.md) by the orchestrator after each attack; the page keeps the latest of each.
