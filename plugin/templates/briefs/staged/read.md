# Phase: read (staged intake, step 1 of 3)

Core template (platform phase 4, 2026-10-22; the compact findings form of 2026-10-23, wip/compact-findings/; from wip/intake-staged/phases/read.md of 2026-10-23), rendered into `wip/<run>/briefs/staged/read.md`.

| Slot | What it holds | Core default |
|---|---|---|
| `{{pack.topics}}` | the closed topic codes of a claims row | the topic codes of schema section 2 as the pack leaves them: `other` only |
| `{{pack.basis_vocabulary}}` | the grounds a stated decline may give | none |
| `{{pack.reference_objects.watch_name}}` | the object watch's name in the findings heading `## Objects (<name>)` (tools/intake_gate.py requires the heading) | object watch |
| `{{pack.reference_objects.features}}` | the features to record for an object, from the reference object's criteria | size, form, markings, condition, what it does |
| `{{pack.actor_register.findings_heading}}` | the findings heading for actors (tools/intake_gate.py requires it) | Actors and polities |
| `{{pack.actor_register.findings_line}}` | the fixed line form of an actor item | `- [u NNN:L] actor as named: <...> \| kind: <state actor \| non-state actor \| proxy \| front \| individual> \| teller: <...> \| firsthand or relayed: <chain> \| goals or role: <...> \| polity: <the polity it belongs to, or none stated> \| history: <...> \| posture toward the referent: <...>` |
| `{{pack.actor_register.findings_what}}` | what the reader collects for the actor register, in one phrase | every actor and polity the source describes |
| `{{pack.blocked_precedent}}` | the precedent named for the pointer row | the pointer-row form of tools/filter-blocks.md section 5 |

The compact findings form (2026-10-23; the form of 2026-10-22 ran at 2.63 times the source in the round-trip measurement, wip/platform-phase6a/REPORT.md section 7). The item allowance and the proposition rule (2026-10-23, after the re-measure: wip/compact-findings/REPORT.md sections 4 and 7).

You read every unit of your range in full and write one findings file per unit. You do not write the note. **Your findings file is a digest the writer navigates, not a second copy of the source.** The writer never reads the source whole: it reads your findings, and for every row, quotation and timeline entry it pulls the source's own words by your pointer with `ledger quote`. So an item you write reaches the note with the source's exact words behind it, and an item you do not write reaches nothing: a claim, dated event, name, document, object, kind, relation, question or decline that is not an item in your findings file is never rowed. Write for that reader: every item present, every pointer exact, the words left in the unit.

Standing briefs that bind you (read them first, in this order; TASK.md names the form and the run brief): `wip/<task>/TASK.md`; intake-standing.md (the standing rules: chain of custody, forthrightness audit, object watch, actors, relations, timeline, divergence, echoes, leads, intake policy; the units paragraph) and the form brief TASK.md names (intake-document.md or intake-video.md); intake-adverse.md when TASK.md says adverse; operations.md; tools/schema.md sections 2 (the claims ledger's classes, moves, attribution and chain rules), 3 (the audit's moves, stated limits, stated declines, pseudo-declines), 6 (the object watch) and 11 (the timeline columns), with the pack's clauses to them, each read by section (the headings with their lines, then the Read tool on the range); tools/agent-wip.md. Do not read context.md, timeline-candidates.md, skeleton.md or any held note: comparison with the database is the writer's work, and your context stays the unit in hand.

## What you do, unit by unit

1. Read `wip/<task>/units/NNN.txt` with the Read tool (the whole unit; its line numbering is the unit's own, line 1 is its header, which carries the source file, the span and the line range; a unit in `--by post` mode may hold several posts, each opening with its own `[unit NNN/MMM continues]` header line). Copy it to `wip/<task>/current-unit.md` by the copy operation and add one line to progress.md. A pointer's line is the unit file's own line, where the header is line 1; never the held file's line (a unit numbered from the source file puts every pointer one line late, and the gate's slack hides it).
2. Write `wip/<task>/findings/NNN.md` in the form below, with the Write tool or Python. You copy no passage of the unit into it: items carry pointers, key words and anchors.
3. Check the size: `ledger extract gate --findings --wip wip/<task> --units NNN-NNN --size`. The budget is an item allowance, not a share of the unit: the file's words are at most 200 (head and summary) plus 35 per claim item, 30 per question item, 20 per quotation item and 25 per every other item. The gate computes it from the items it counts, so the number of items never puts you over; only words per item do. Over it, cut fields to the form (key words, no sentences, no restated context, no field repeated from the item above), never by dropping an item. The one exception: a section whose items cannot be cut to their cap and stay exact (report numbers and URLs in Documents and works cited; a question whose wording is the point; a long actor description), kept whole and declared on the head line in the form the gate checks, `size: over budget: <section>: <n> items over <cap> words: <reason>` (for example `size: over budget: Documents and works cited: 14 items over 25 words: report numbers and URLs`); the gate confirms the named section is the one over and fails an exception that names none or names the wrong one. "Dense" is never a reason: density raises the item count, and the allowance already grows with it. Without a valid exception line an over-budget unit fails gate 1.
4. `ledger prepare chunk --wip wip/<task> --mark NNN "findings written"`.
5. Next unit. In a fan-out (your prompt names a range) touch only your range; do not re-split; do not read other readers' files.

Coverage (unchanged by the compact form; it applies to items, not to words): every claim, with its speaker, class and move, as schema section 2 would have it in a claims row; every dated event; every span the writer must quote (every passage of 15 or more words that carries a claim, a description or a document's wording in the speaker's own words, and shorter ones where the words matter: a document's phrase, a denial, a stated limit, an echo candidate) as a Quotations item; every name with role and relation; every document, book, article, film, page, institution cited; every object for the object watch (and the nearest physical objects where nothing qualifies, so the writer can log them at strength nil); {{pack.actor_register.findings_what}}; every who-knows-whom, employer, funder, member-of, directs, source-of edge; every question put and answered or declined, every wall, every stated limit. Nothing is omitted because it looks minor: an item you leave out is a row nobody writes. The pack's requirements ({{pack.pirs}}) are an overlay, not a filter: make sure every dated statement of knowledge they name is an item with its date, author and recipients; they never tell you what the source says. Cited sources (the intake policy's rule 7, owner 2026-10-23): the ledger rows what this source says, including what it says a cited work says (class `read`, the chain naming the work); the source's citations are verified against and recorded in Works, the chain and as first-telling or lead candidates, never rowed as the cited work's own claims; a cited work that matters is queued in `chain_leads` for its own intake unless TASK.md names it as a source. Your part of it: a cited work's content appears in your findings only as what this source says of it (one claim item, class `read`, with the work under Documents and works cited), never as items of its own.

## The findings file (fixed form; tools/intake_gate.py checks it)

```
# Findings: unit NNN of MMM
unit: <line 1 of the unit file, copied exactly>
status: complete
reader: <your label>, <date>
size: over budget: <section>: <n> items over <cap> words: <reason>     (only when step 3 needs it)

## Summary
<two or three sentences, at most about 60 words: what the unit is, who speaks; for a post set, each post's code, title and date>

## Dated events
- [u NNN:L] <the date as the source states it, a few words> | <sortable: YYYY, YYYY-MM, YYYY-MM-DD, ~, .., ?> | <the event: a few words with the actors> | <speaker; basis> | chain: <0, or n: origin (type)>
(one item per event: a line that dates two events is two items with the same pointer; a span that gives one event two dates is one item with both)

## Claims
- [u NNN:L-M] <speaker> | <one of the pack's topic codes: {{pack.topics}}> | <class> | <move> | claim: <the claim in at most about 20 of the source's own key words, the date in it where there is one> | chain: <0, or n: origin (type); a personal author with no work named takes rule (ce)'s `author named, work not named` and `(document, unnamed)`> | loc: <the Time cell: h:mm:ss, page, P04 para. 5> | attr: <the declared origin, a few words> | note: <a few words: the basis of a closure, the record word, the blanket declaration>

## Quotations
- [u NNN:L-M] <speaker> | words: <the span's first four words> ... <its last four words> | use: <notable quote | audit row | document's phrase | denial | stated limit | echo candidate | timeline>

## Questions, declines, walls and stated limits
- [u NNN:L-M] <asked by, and how: (FOIA), (email), (in person), (reverse)> | q: <a few words> | a: <a few words> | <move> | basis: <a ground from {{pack.basis_vocabulary}}, none stated, n/a, redacted: <exemption>> | <stated limit | stated decline | pseudo-decline | wall: <office> | none>

## Names
- [u NNN:L] <canonical spelling, or the description as given for an unnamed person or group> | <role as given> | <relation to speaker> | <the facts this unit gives, a few words> | variants: <caption or spelling variants, or none>
(every named person, and every unnamed person or group the source describes as acting or speaking (`the F-18 pilots`, `a radar operator`, `a friend of Mr. Newton's`), by the description as given: writer B builds People from these items alone)

## Documents and works cited
- [u NNN:L] <title as cited> | <author or issuer> | <book | paper | film | document | report | program | website | episode | institution | artwork | concept | site | artifact | other> | <date> | for: <what the speaker takes from it, a few words> | id: <a report number, a FOIA case number, a URL, or none>

## Objects ({{pack.reference_objects.watch_name}})
- [u NNN:L-M] <object> | witness: <...> | custody: <contractor | government | private | none | unknown> | described: <{{pack.reference_objects.features}}: key words; the description's own words by a Quotations item> | note: <a few words>
(or the one line: none; nearest physical objects: <list>, for the writer's nil rows)

## {{pack.actor_register.findings_heading}}
{{pack.actor_register.findings_line}}
(or: none)

## Relations
- [u NNN:L] <a> | <b> | <knows | employer | funder | member-of | directs | source-of | ...> | hierarchy: <...> | when: <...> | what: <a few words> | chain: <...> | confidence: <...>
(or: none)

## Tensions inside the source
(optional) - [u NNN:L] <what this unit says> against <the earlier unit and line, or the same speaker elsewhere> | <a few words>

## Open threads the unit raises
(optional) - [u NNN:L] <the question the source leaves open, or poses> | <what would settle it>

## Nothing to row
(only when the unit yields no claim: the reason, one line; the sections above still stand, with `none`)
```

Rules of the form.

- **Pointers.** `[u NNN:L]` is the unit number and the line of the unit file where the item rests (the Read tool's numbering, line 1 the header), `[u NNN:L-M]` for a span; every item carries one, and it is the writer's only way back to the words, so it covers the whole passage the item rests on and no more. Items are one line each, fields separated by ` | `, in the order given; the labelled fields `attr:` and `note:` of a claim, and a field with nothing, are left out (no `none` fields inside an item; a section with no items takes the one line `- none`). The actor line keeps the pack's fields, each a few words.
- **Fields are key words, not sentences.** A field is a few words; a claim is at most about 20 of the source's own key words (the gate checks that the pointer's lines hold three content words of the claim).
- **Every proposition on the span is named.** The writer rows from your key words and does not re-read the span for what you left out, so an item's claim field names every proposition its pointer's span holds, each by its key words, separated by `;` (`claim: the agency came to the lab 1972; wanted a test of the subject; funded three months`). A span that holds more than three propositions is split into items with narrower pointers. A date, a figure, a name or a second assertion inside the span that the key words do not name is a row nobody writes. Never merge two speakers, two classes or two moves into one item.
- **Quotations are located, never copied.** A Quotations item gives the span's pointer and its first four and last four words exactly as the unit has them (`words: <first four> ... <last four>`); a span of eight words or fewer is given whole, without `...`. The anchors must sit on the pointer's lines in that order (the gate allows two lines either side; case, curly quotes, dashes and the punctuation between words do not count; a changed or dropped word does). The anchors are never put in quotation marks. Check an item with `ledger quote --wip wip/<task> u NNN:L-M --words "<first four> ... <last four>"`, which prints the exact span the writer will receive. A quotation that runs across a unit boundary is two items, one per unit.
- **`firsthand` is an act.** The class field is `firsthand` only where the speaker or the document's author says, in the span, that they saw, did, measured, interviewed or received it themselves (`we examined`, `I attended`, `we were told`); a document's flat statement of fact about any other party, time, practice or event, with no source named, is `host` with `chain: 1: <issuer> (unsourced)` and, in a document, move `closed-subtle`; with a source named, `read`. The author of a report or reply is not a witness of what it reports, and a member's flat statement about their organisation's holdings is `host` (schema rule ct). Before you mark a unit done, every `firsthand` item in a document names, in its key words, the act the author performed. A figure or a valuation in a claim field keeps its qualifier in the key words (whose figure, for whose benefit, `claimed`, `valued at`), and a hedge or bound in the span (appear, seem, suggested, earliest, only, unless, may) is in the key words too, so the writer quotes it.
- **The unit's characters as they are.** Anchors and any quoted words are the unit's exact characters, OCR errors, line-break hyphens and misspellings included; the writer marks them with `[sic]` or a bracketed correction when it quotes. Never correct the unit in an anchor.
- **Quotation marks elsewhere.** Shorthand is never put in quotation marks. A few words in quotation marks inside a field (a date as stated, a term the source coins) are checked by the gate against the unit and must be the unit's exact words; keep them to the words that are the point.
- **Chain and documents.** Where a speaker's claim rests on a document the unit names, the Documents section carries the document and the claim's chain names it. A document's footnote, editor's note or edit note is firsthand only as to the edit or the citation it makes; what it states about the world is classed as any other statement of that document's issuer, and a footnote's assertion is never rowed as the issuer's own act.
- **Location.** `loc:` carries what the writer puts in the Time cell: the h:mm:ss of a transcript line, the page of a document, the post code and paragraph of a post set (`P04 para. 5`); for a post set the Summary gives each post's code, title and date.

## When you finish your range

`ledger extract gate --findings --wip wip/<task> --units <first>-<last>` must pass (every unit of your range has a findings file; every Quotations item's anchors are on its lines in order; every quoted span is verbatim in its unit; every pointer is on its line), and `--size` over the range shows every unit within its item allowance or carrying a valid exception line (gate 1 fails an over-budget unit without one). Fix what they name, with the Edit tool or Python, against the unit text. Then progress.md's last line is `read phase complete: units <first> to <last>`, and your reply carries the structured fields: `units_done` (count), `units` ("NNN-MMM"), `blocked_passages` (the list, `[]` when none), `notes` (one or two sentences: anything the writer must know that no findings file carries, such as a unit that duplicates another, and the units with a size exception).

## WIP, resume and blocked output (standing)

tools/agent-wip.md binds: progress.md from the first minute; findings saved per unit before the next unit is opened; on a resume, `ledger extract gate --findings --wip wip/<task> --status` names the first unit without a passing findings file and you continue from it, never from scratch. The blocked-output paragraph of intake-standing.md binds: a passage refused twice is bisected, captured in `wip/<task>/blocked/<n>.md`, and entered in the findings file as an item `- [u NNN:L-M] [BLOCKED: see <unit and lines>; wip/<task>/blocked/<n>.md; awaiting human summary]` under `## Claims`, listed in your reply under `blocked_passages`; the writer carries the pointer row into the note ({{pack.blocked_precedent}}). Never pass a fetched text through your own output; copy files by the copy operation.
