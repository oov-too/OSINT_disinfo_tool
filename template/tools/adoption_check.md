# tools/adoption_check.py: the adoption check (the mechanical half of test 9)

Added 2026-10-15. Run 2's register found that 10 of 11 attacked revisions had adopted at least one objection in a form its rows do not carry. The revision rule (tools/narratives.md section 6, 2026-10-09, proposal 25) makes the reviser verify an objection's own rows before adopting it and record them in the Revision table's `Rows read` and `Leads checked` cells; the attacker's test 9 (wip/narratives-1009/phases/attack-tests.md, agent B) then checks each adopted objection: were the rows read, and do they say what the objection says. Until now agent B re-derived the list from `--section <page> "latest:Revision"` and fetched the rows itself. This tool does the mechanical half before the attack, so the attacker reads a short list and rules on it.

## What it does

For the page's latest `## Revision` section (every Revision section on the page and in research/narrative-history/<stem>.md with `--all`), the Revision table is parsed into one row per objection with its disposition, its `Rows read` cell, its `Leads checked` cell and the text of what changed. For every adopted or partly adopted objection (and, with the same checks, every applied row that is not a numbered objection: brief items, `P` rows carried from a parent, `(own)` rows):

1. **Empty Rows read.** FAIL `empty-rows-read`: the revision rule's own test. (A cell with text but no database row, such as `relations 2090; the page's Carriers row`, is WARN `no-row-citations`; the attacker decides whether the objection needed rows.)
2. **Every citation in Rows read resolved against notes.db.** FAIL `missing-note` (no such note), FAIL `missing-row` (the note exists, the row does not). Each resolved row is placed: in the page's Nodes or ledger, elsewhere on the page, newly added by this revision (cited in the version after the revision and not before), or OUTSIDE the page (WARN `outside-note`: the reviser read a row from a note the page cites nowhere). Shorthand is resolved to the note last named in the cell (`[same claims 10]`, `; tl 5, 7, 10 of the same note`, `claims 44, 161` after a bracketed citation) and marked `shorthand`; a shorthand row that does not exist in that note is WARN `unresolved-shorthand`, not a fail, because the shorthand may mean another note; a bare `claims N` before any note is counted as WARN `bare-references`.
3. **The page rows the adoption changed.** The nodes and ledger rows the Objection and What changed cells name (`node 21`, `nodes 21, 22`, `row 13`, `ledger rows 73 to 76`, `Ledger 2`) are diffed between the snapshot taken before the revision and the first snapshot after it (research/tasks/tool-feedback/snapshots/<stem>.<label>.md, written by tools/narrative_snapshot.py; the page itself when no later snapshot exists). For each: the changed columns with old and new text, the citations on the new text against the Rows read set (how many are the rows the objection cited, how many are new), the rows added that are not in Rows read (WARN `new-rows-on-change`: the adoption's support on the page is not the support the reviser says was read). WARN `no-change-located` when none of the named rows differs between the two versions (the change was in prose, or was not made). A node named by several Revision rows shows all its changes under each, with the other rows named.
4. **Leads checked.** Every lead number in the cell (relations numbers, citations, dates and parenthesised notes are not leads) is resolved against research/leads-and-inferences.md: FAIL `missing-lead` when the number is not in the register; the register's status is printed beside the status the page states (`(page says open)` when they differ); open leads are listed in a note (`open leads: ...`), since an adoption that rests on an open lead rests on something unresolved. The count is in the summary line; it is not a fail.
5. **The rows' text.** Every Rows read row is printed in full, trimmed to `--chars` (400) characters, in the form `--rows` uses (date or time, speaker, move, the text, the chain), so the attacker reads the list and rules whether the rows say what the objection says.

The objection's own text (from the Objections section the Revision answers, the last one before it in page order, on the page or in the history file) and the What changed cell are printed above the rows; a `4(b)`-style label prints that sub-item. Declined objections are listed in one table (rows cited, missing, named nodes and rows, whether those rows changed anyway); rows not applied (`not applicable`, `Answered through the rows above`) in another.

The 2026-10-08 tables (v0.3: one `Rows` column mixing page rows and citations, no Leads checked) are parsed and their citations resolved; the empty-cell and no-row checks are notes there, since the rule postdates them.

## Dispositions

Read from the What changed cell's opening (`Adopted.`, `adopt in part.`, `declined:`, `Carried.`, `Done.`) or, when the word is not at the opening, from its first 80 characters and any parenthesis in the Objection cell (`(adopted: a, b, c)`, `(adopted; one part declined with 3b)`), then from the whole cell. A cell that says both (`Row 40's reweighting declined: ... Row 13's side adopted`) is `partly`. A cell with no disposition word that describes a change is `applied` and checked like an adoption (the summary counts it apart). `not applicable`, `Answered through the rows above` and `no change` are `other` and not checked.

## Command line

```
python3 tools/adoption_check.py <page> [--all] [--out <file.md>] [--snapshots <dir>] [--chars N]
python3 tools/narratives.py --adoptions <page> [--all] [--out <file.md>]
```

`--all` checks every Revision section (page and history), latest only otherwise. `--out` writes the markdown (the attacker's wip folder: `wip/<task>/adoptions.md`); stdout otherwise. `--snapshots` names another snapshot directory. `--chars` is the row text trim (400).

Exit code 1 when any mechanical fail exists (`empty-rows-read`, `missing-note`, `missing-row`, `missing-lead`), so the staged workflow can gate on it; 0 otherwise. Reads the pages, the snapshots, the leads register and notes.db; writes only `--out`; never writes a page.

## Output

One markdown file: a summary line (`adoptions N (adopted, partly, applied); declined N; other N; mechanical fails N (by kind); warnings N (by kind); adoptions resting on open leads N; revisions checked N of N`), then per Revision section the blocks, severity first (FAIL, WARN, OK), each block: the severity lines, the objection, what changed, the rows read with placement and text, the leads with status, the page rows changed with the citation comparison, and a line for the attacker's ruling. Non-objection applied rows follow, tagged `not an objection`.

## Where it runs

After every revise step and before the attack (tools/narratives.md section 6, the sentence after the revision rule; section 8c): the orchestrator runs it beside `--audit` and `--diff` when it prepares an attack step (wip/narratives-1009/make_args2.py, `audit_and_diff`), into `wip/<task>/adoptions.md`; agent B's test 9 reads that file instead of re-deriving the list, and writes its rulings in findings-B.md citing the blocks. A FAIL in the summary is a finding on its own (the revision rule was broken) whether or not the attacker agrees with the adoption.

## First run (2026-10-15, every page with a Revision section, `--all`)

The page labels stand for a pack's narrative pages ({{pack.narratives}}): mainline N is the pack's Nth mainline in seed order; fork Na, Nb and so on are the forks of mainline N.

| Page | Revisions checked | Adoptions (adopted, partly, applied) | Declined | Fails | Warnings | Open leads under adoptions |
|---|---|---|---|---|---|---|
| mainline 5 | 1 | 19 (14, 5, 0) | 0 | 0 | 10 (new-rows-on-change 10) | 73 |
| mainline 4 | 1 | 21 (16, 5, 0) | 0 | 0 | 4 (new-rows-on-change 4) | 49 |
| fork 2a | 1 | 42 (31, 11, 0) | 1 | 0 | 35 (new-rows-on-change 30, no-row-citations 5) | 57 |
| mainline 2 | 2 | 42 (38, 4, 0) | 0 | 0 | 6 (new-rows-on-change 6) | 32 |
| fork 3a | 1 | 18 (5, 13, 0) | 0 | 0 | 15 (new-rows-on-change 13, no-row-citations 2) | 30 |
| mainline 3 | 2 | 47 (25, 4, 18) | 2 | 0 | 4 (new-rows-on-change 4) | 48 |
| fork 1a | 1 | 16 (12, 4, 0) | 0 | 0 | 12 (new-rows-on-change 10, no-change-located 2) | 32 |
| fork 1b | 1 | 19 (13, 6, 0) | 0 | 0 | 22 (new-rows-on-change 16, no-row-citations 6) | 30 |
| fork 1d | 1 | 29 (21, 8, 0) | 0 | 0 | 28 (new-rows-on-change 23, no-row-citations 5) | 20 |
| fork 1c | 1 | 23 (17, 6, 0) | 0 | 0 | 23 (new-rows-on-change 19, no-row-citations 4) | 24 |
| mainline 1 | 2 | 33 (14, 4, 15) | 1 | 0 | 12 (new-rows-on-change 9, no-row-citations 3) | 32 |
| mainline 6 | 1 | 22 (16, 5, 1) | 0 | 0 | 1 (unresolved-shorthand 1) | 43 |

Outputs: wip/adoption-check-1015/<stem>.md (100 to 280 KB each with `--all`, because every Rows read row is printed; the latest-only run of mainline 1 is about 110 KB). The 2026-10-08 revisions of mainlines 1, 2 and 3 have no snapshot before them (they predate the snapshots), so their change diff is unavailable; mainline 6 has no snapshot before its 2026-10-09 revision either. Four pages (forks 2b, 3b, 4a and 6a) have no Revision section yet: nothing to check until their first revise step.

No page changed. Mechanical fails were 0 on every page once shorthand citations (`[same claims 10]`, `tl 5, 7 of the same note`) were resolved to the preceding note; the warnings are mostly `new-rows-on-change` (the revised node or ledger row cites rows the Rows read cell does not name), which is the attacker's test 9 input, not an error by itself.
