# Phase: check (the checked form, optional, 2026-10-25)

Core template (platform, 2026-10-25; from wip/intake-staged/phases/check.md of 2026-10-25), rendered into `wip/<run>/briefs/staged/check.md`. Optional: `check: true` on a task runs it between the ledger stage and writer B; a budget in rows may be set in the prompt, and the order of attention makes a short budget worth having.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.blocked_precedent}}` | the precedent named for the pointer row | the pointer-row form of intake-standing.md's blocked-output paragraph |

The checked-staged form adds one agent to the staged intake between writer A and writer B: **you read every claims row of the ledger against the span its pointer pulls and correct what the gates cannot see.** The gates check words inside quotation marks, pointers and unit coverage; they cannot see a paraphrase that reverses or overstates the span, a wrong speaker, a wrong basis, or a merged grain that loses a proposition. The pilot's twenty-row samples measured those at 7.7 percent of rows (wip/pilot-run's reading, 2026-10-23); this phase is that reading done in full, with the correction made.

## What you read, and only this

`wip/<task>/TASK.md`; tools/agent-wip.md; tools/schema.md section 2 (the Claims ledger: columns, classes, moves, the attribution and chain rules (a) to (cr)) and section 3 (the audit's moves), by line range; write.md's paragraphs "The claims ledger's grain is the proposition", "Claim with quote" and "The paraphrase around a quotation says no more than the span". The note's ledger and audit as writer A left them (the Read tool on the section ranges of `<note>`). For each row, the span: `ledger quote --wip wip/<task> u NNN:L-M` for the row's pointer, with two lines either side, pulled in batches of ten to twenty rows per call; never the units whole, never the findings (the findings are the reader's digest; your judgement is against the source).

## The five judgements, every row

1. **Verbatim**: every quoted stretch in the Claim cell is in the span word for word (an ellipsis for a cut, a bracketed insertion or correction, the source's own spelling); a silent repair is corrected to the source's words with the mark.
2. **Support**: the row says what the span says and no more: nothing added from outside the source, nothing reversed, overstated or softened, the right speaker. A paraphrase that departs from the span is rewritten from the span; an outside citation, date, name or figure is removed from the row and listed in your reply's `outside_matter` for writer B's Open questions.
3. **Grain**: one proposition. A merged row is split when it loses a proposition, or when its parts differ in class, move or chain (a second speaker, a different basis, the speaker's own inference or stance beside a relayed or flat claim); the part with the other basis becomes the decimal row. A merged row that loses a proposition is split: the lost proposition becomes a new row with a decimal number after the row it came from (`48.1`), its own pointer, class, move and chain; a row that is a fragment of its neighbour is joined to it (the neighbour's pointer widened).
4. **Class and move** as schema section 2 and 3 give them; corrected with the rule named in the Note cell's change log (below). Every `firsthand` row is checked for a stated act of seeing, doing, measuring or receiving in the span; membership of an organisation, authorship of a report, or a flat statement about others is not one (schema rules ct and cr: a document's flat assertion is `host`, a hedged risk line `host` with move `n/a`). Where you doubt a findings class, read the span and decide; never write `as the findings read it` in a Note.
5. **Chain**: the prefix present on every non-firsthand row, n right, the hops as the span gives them, the terminal type and the set phrases right; corrected in place.

## The order of attention

The faults the gates cannot see cluster (the fault study, 2026-10-24): read the rows in this order, so a budget that stops early has met most of them. First, every row classed `firsthand` in a document note, and every `host` row whose span names a source. Second, every row whose span carries a hedge, bound or qualifier (appear, seem, suggested, alleged, earliest, only, unless, may, as far as, as practiced, could, might) that the row's quotation marks do not contain. Third, every row whose span holds a second named actor, a pronoun subject, or an embedded telling (told, said, set out, read out, a statement or URN, an email, a post about a post). Fourth, every row whose quotation ends mid-sentence before a clause beginning as, unless, but, if, which or provided. Then the rest. Your prompt may set a budget in rows; without one, every row.

## How you correct

Every correction is an exact string replacement of the one row in `<note>`, made by Python, never a rewrite of the section; the row keeps its number and its pointer (or gets a widened or decimal one as above). Every changed row is logged in `wip/<task>/check-log.md`: the row number, the judgement that failed, the words before and after, the rule. The audit rows that rest on a corrected claims row are read and corrected the same way. You never add a row the span does not support, never remove a row (a row the span does not support at all is marked in its Note cell `check: unsupported by the span; see check-log` and listed in your reply for the finisher), and never change a quotation to something other than the span's words.

## When you finish

`ledger extract gate --note <note> --wip wip/<task>` passes; `ledger prepare skeleton --check <note> --form <form>` passes. progress.md's last line is `check complete: rows 1 to N read, K corrected`. Reply with the structured fields: `rows_read`, `corrected` (count), `by_judgement` ({verbatim, support, grain, class_move, chain}), `split_rows` (the decimal rows added), `unsupported` (the list), `outside_matter` (the list), `log` (the path), `notes`.

## WIP, resume and blocked output (standing)

tools/agent-wip.md binds: progress.md from the first minute naming the last row read; the log appended as you go; on a resume continue from the last row logged, never from the first. The blocked-output paragraph of intake-standing.md's blocked-output paragraph binds; a `[BLOCKED: ...]` pointer row is never pulled and never changed.
