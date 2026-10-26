# Investigation: the OSINT output mode and its agent protocol (v1, 2026-10-02)

An **Investigation** is a research page (research/investigation-<slug>-<date>.md, page kind `investigation` in notes.db) that takes one thread in the ledger, states the question as a choice between live explanations, lays out everything held on it with quotations and row citations, tests the strongest alternative, names the holes, and says what finite checks would settle it. It is the ledger's answer to the question "what do we actually know about X, how do we know it, and what would make it conclusive?" It is built by agents from the database, not from the open web; the web is used only to fetch what the ledger does not hold, and whatever is fetched is intaken first (a note in the house schema) so that every citation in an Investigation points at a held row.

The model is a public investigative post by an independent, pseudonymous author that set three accounts of one hidden episode side by side and tested the obvious alternative before any common cause. The original model, the held copy of it, and its mapping onto this protocol live in the active pack ({{pack.exemplars}}); this document shows the post's anatomy on an invented model built from tools/example-casebook.md: a post on three accounts converging on the deferred 2015 repair of the Harrowmere spillway (Petra Vanecek's evidence on the left wall and her later retellings of it; the Lisle memo of 2 June 2015 as Owen Thale published it; and Thale's anonymous source "Heron" on the repair that was scheduled and then dropped), set against Desmond Harlowe's denial that any warning was put in writing. The owner's instruction (2026-10-02): "Investigations need to be as thorough as the post; have a similar structure; use quotations; cite sources; talk about strengths and limitations of the evidence." Its anatomy (section 2 below) is what an Investigation reproduces; its limits (section 2.3) are what the ledger adds. The second pillar is an insider's description of how a machine would work the problem, read as a method: correlate records nobody reads together, see the gaps in the record that make no sense, detect where the record has been managed, infer that the official account of an event is not right and was cover for something else, then dig. In the invented example it is counsel to the inquiry, Ms Adair, in her closing submission (`[harrowmere-day-40 claims 12]` to 16 and 31 to 32): put "the site diary, the inspection logs and the board minutes side by side", look for "the gaps in the record that make no sense", "find where the record has been managed", infer that "the account of 2015 we were given is not right" and "was cover for a repair that was put off", then dig; the original pillar and its citation are pack data ({{pack.exemplars}}). Section 6 maps that onto the pipeline.

## 1. What an Investigation is, and is not

- It is a derived page: it cites notes and rows; it holds no claims of its own and loads into notes.db only as a page (`pages`, `page_links`), never into the claims, audit or timeline tables. Its findings that outlive it go where findings live: leads (research/leads-and-inferences.md, Asked by `page: <link>`), cross-checks written back into the notes, relations rows, corrections, and answers to open questions with Answered by `page: <link>`.
- It differs from a synthesis page (research/synthesis-*.md: the ledger's own theory, dated and row-cited) in that it does not propose a theory; it adjudicates between explanations already on the table and says what would decide. It differs from a subject page (a map of a field) in being about one question. It differs from a speaker ledger or the consolidated timelines (registers and consolidations) in having a verdict section.
- Its standard is the post's: every assertion quoted or row-cited; the strongest alternative tested rather than assumed; deflationary readings taken seriously; every candidate identification led by its strongest counter-fact; chains of custody drawn; a finite list of tests; a conclusion that keeps the live explanations live. The ledger adds what the post lacked: independence of tellings (who hosts, who relays), declines and audits on the point, every teller's own changes across tellings with the divergence tag, the official explanations tested as cover stories, and a holes section written by a critic who looked for what was not done.

## 2. The model: the post's anatomy

### 2.1 The structure (section by section, with its function)
1. **Opening: the convergence.** Three accounts, one window of time; each account summarised in a sentence with its own hedge ("Vanecek says the left wall was to be repaired... Vanecek later said she only heard it secondhand"; "Heron, as Thale reports him, does not date the cancellation... the natural reading puts it after the memo").
2. **The alternative, stated at once.** "None of this shows that anyone decided to put the repair off. The strongest alternative is that these accounts travelled through a small press and engineering circle after the 2017 story. The point is to test that reading... not to take it for granted."
3. **The question as a disjunction.** "Are [they] separate views of one decision made in 2015, or versions of one story passed around a circle in which everyone knows everyone?"
4. **Source note.** The inherited caveat declared once and carried by every dependent claim ("I have not checked Thale's quotations from the memo against the inquiry's own copy").
5. **The chronology that makes the comparison interesting.** Dated elements in order, each with its source and its limit ("Heron never gives a date... Vanecek gives only a latest possible date... the comparison may rest on a false premise").
6. **Per-source analysis: what the claim does and does not match.** For each strand: the quotation, then the narrowing ("that loosens the tightest form of the match"), then what a real match would require ("agreement on the wall, the crack, the people, the dates, the procedure or where the source got it").
7. **The reconstruction, entry by entry, with dates as headings.** The granular evidence laid out so a reader can check it (in the invented model, the site diary HI-114 day by day); methodological remarks on what the procedure implies (a fixed daily form, blank days kept rather than filled in later).
8. **Deflationary readings taken seriously.** "If what Lisle saw was surface crazing, the 'line down the left wall' could have been a curing mark, not a structural crack."
9. **The teller's own limit quoted.** "I wasn't at that meeting. I only know what I was told." Marked as "the edge of what the whole reconstruction can carry."
10. **What the inspection might have been testing, and what is missing from the record** (photographs, dated measurements, a repeat visit, an independent engineer): the gap between an inspection record and a retrospective narrative.
11. **The third strand with its contemporaneous anchor** (the Lisle memo of 2 June 2015), its later extraordinary version (Heron's 2017 account that the repair was cancelled on the chief executive's word), an independent documentary route (a repair line in the Authority's published 2015 capital plan), and a witness who reacted as if he already knew (Lisle, asked on the stand about the cancellation).
12. **The same evidence read as a deception warning.** The denials, the board secretary who knew nothing, the possibility of a false premise: "this is not a side objection for sceptics; it belongs to the case itself."
13. **Identifications, strongest counter-fact first.** Harlowe: "the fact that cuts against him goes first: ... asked on Day 31 whether he had seen the memo before 2017, Harlowe answered, 'No.'" An Authority engineering manager (a role): "a fit on post and dates, not an identification," built from three records (a staff list, a letter in the inquiry bundle, a professional register entry).
14. **The finite archival problem.** "Reconstruct who sat in the Authority's capital-programme meetings of autumn 2015 from the minutes, the diaries and the expense claims... Either answer is worth more than guessing at who was in the room."
15. **What the evidence currently allows.** Both explanations restated with what each predicts.
16. **What can actually be tested.** Three checks with the place to check; the prospective test (a promised publication, *The Long Table*'s announced release of the papers behind its series: "whether it holds the 2015 papers or only one more retelling; if it never appears, that tells us something too"); the rule that "a question only the people accused of burying the warning could answer is no test anyone can run."
17. **The evidentiary chain** drawn as a diagram (the 2015 inspection → Lisle → the memo → Heron → Thale → the *Ostley Gazette* → public).
18. **Conclusion.** The convergence restated; the warning restated; "both readings are still standing"; what distinguishes them ("matches on particulars from sources with separate roots, not a family likeness").

### 2.2 The moves (the method in the structure)
- Compare only where there is a reason to compare (overlapping chronology, a shared specific), and say what the reason is.
- Separate what a source says from what the author infers from it; hedge the inference in the author's own words.
- Treat generic resemblance ("somebody was warned at some point") as no evidence; demand non-generic correspondences.
- Carry inherited caveats on every dependent claim.
- Keep the internal tensions (who are "the people upstairs"?) as things to watch, not things to resolve.
- Let the evidence cut both ways and say so.
- Turn vague mysteries into finite tasks with a place to look, and refuse tests that no outsider can run.
- Draw the chain of custody; prefer any step that shortens it.

### 2.3 The limits (what the ledger's version must add)
- Reliance on a transcription the author did not check against the exhibit; citations without links (two *Ostley Gazette* pieces, *The Long Table* episodes 2 and 4, a radio clip of Harlowe, a trade-journal article, a council minute, the inquiry's Day 12 transcript).
- No independence analysis of hosts and relays (*The Long Table* carries two of the three Vanecek tellings in its own voice; Castellan plays Lisle's evidence to Vanecek; Heron relays a board member).
- No use of tellings the ledger holds (Lisle's own evidence on the 2015 inspection, with Harlowe and the Pernell Geotechnics engineers; Vanecek's "it was never a secret" and "the core went to the lab like any other"; Harlowe's 2017 press clip, "no warning was ever put in writing").
- No audit of declines on the point (what each teller refused, and on what ground).
- No reading of the tellers' own changes across tellings (the divergence tags and the four-class reading).
- The author's own provenance unexamined (pseudonymous; a burst of posts in a few weeks; readers doubting a person wrote it; a revision between versions; the copy later removed by the host site).
- The official explanations (the Authority's 2018 review: "no warning of cracking was received before 2017"; Harlowe's denial; an official's "I have no idea what memo you mean") used as warnings but not tested as cover stories against independent records.

## 3. Required structure of an Investigation page

Metadata table first, then these sections in this order with these headings (a parser-stable shape; free prose inside each):

| Key | Content |
|---|---|
| Kind | investigation |
| Question | the disjunction, one sentence |
| Thread | the strands, named |
| Parties | every teller and relay, with the number of independent tellings per strand |
| Sources held | the notes read, as links; sources cited by any party and not held, listed as such |
| Built | date; the agents and models used (section 5); the evidence pack file |
| Status | open / closed; the verdict class (section 3.13) |
| Related | leads rows produced, pages, registers touched |

1. `## The question` — the convergence that makes the comparison worth making, each strand in a sentence with its own hedge; the strongest alternative stated at once; the question as a disjunction of two or more live explanations.
2. `## Source note` — what each strand rests on (held notes, with the class of custody at the root: firsthand, document, relay), the inherited caveats, what is cited but not held.
3. `## Chronology` — every dated element as a table: Sortable | Date as stated | Event | Teller and basis | Note and row (claims N, tl N) | Agreement (matches / drifts / contradicts, with the tag) | Era page block. The table is built from the timeline rows in the evidence pack and the notes; nothing is dated from memory.
4. `## Strand by strand` — one subsection per strand: (a) what the teller says, quoted with note, row and time; (b) what it does and does not match in the other strands; (c) custody and independence: the chain, the hosts and relays, how many independent tellings there are; (d) the teller's own limits and declines on the point (audit rows: closed-outright, closed-subtle, pseudo-declines, with grounds); (e) the teller's changes across tellings (the divergence rows and tags; the four-class reading: honest, honest mistake, disinformation, state sanctioned); (f) the deflationary readings; (g) the strand's strengths and limits as evidence, in two short lists.
5. `## The strongest alternative, tested` — the shared-information-environment or common-source explanation (or whatever the alternative is), with the relations register's two-hop neighbourhood among the parties, the precedents the ledger holds (earlier lore, earlier tellings, stock phrases from tools/echoes.py), and what the alternative predicts that the common-program reading does not; the test applied.
6. `## Internal tensions` — things that do not fit within a single telling or a single party, kept as things to watch, each with what would resolve it.
7. `## Identifications and candidates` — only where a strand turns on an unnamed person, place, document or program: each candidate led by its strongest counter-fact; the personnel-fingerprint method (records held in the ledger: bulk document collections ({{pack.archives}}), archives, registers); "a plausible match, not an identification" unless a record places the candidate.
8. `## Official explanations and the cover-story test` — one row per official explanation of any event in the thread: the event as officially told | issuer and date (note, row) | the witness counter-claim (note, row) | what the explanation must predict in an independent record | the check (held record, or the record to obtain) | verdict (holds / fails / untested). The house rules apply: an office's contradiction of a witness is a lead, not a correction (the agency rule, tools/schema.md section 10); the row is a `contradicts` cross-check with `party=<office>`.
9. `## What the evidence currently allows` — each live explanation restated with what it predicts and what it cannot explain.
10. `## Holes` — written from the completeness critic's report (section 5, stage 5): sources cited and not held; strands not run; declines never filled; records named but unread; questions no interviewer asked; tellings whose independence is unknown; the parties never heard from. Each hole with the task that would fill it and the model tier that task needs.
11. `## What would be conclusive` — finite tests only: the record to read (shelf, folder, document number, page), the person to ask and the question, the publication to await and what it must contain; who can run each; what result settles which explanation; the non-tests named and refused ("a question only the people accused of burying the warning could answer").
12. `## The evidentiary chain` — a diagram per strand (plain text arrows, as the post drew it), and the step in each chain that a finite test would shorten.
13. `## Conclusion` — the verdict class (`converges` / `diverges` / `undecidable on held evidence` / `settled: <explanation>`), the confidence and its basis, the live explanations, and the one sentence that says what distinguishes them.
14. `## Register entries produced` — the leads added (numbers), cross-checks written back (note and row), relations added, open questions answered, corrections proposed, candidate intakes queued.
15. `## Method` — the pipeline run (stages, agents, models, effort), the evidence pack's terms and caps, what was read in full and what only through the pack, the judge's score against the model and the fixes applied.

Every quotation carries note, row and time (`[Vanecek / Ambrose](../videos/harbour-talks-vanecek-2020.md) claims 69, 0:58:00`); every date carries a Sortable; every corroboration carries the chain of both sides and the independence judgement; a paraphrase is marked as one; no claim is taken from memory or from the open web without the fetch date and the label `own: Claude, web, <confidence>`. The schema's standing rules apply throughout: chain of custody (section 2), the divergence rule and tag (section 10), decimal timeline IDs (section 11), no keyword drops (a shortlist item leaves only on a recorded ruling), the editor-gloss rule, the agency rule (tools/schema.md section 10): no office ever at face value.

## 4. The standard an Investigation is judged by (the judge's rubric, stage 6)

Score 0 to 3 on each; a page ships at 2 or better on every line, with the judge's fixes applied.

1. Thoroughness: every held telling of each strand read and cited (not only the pack's excerpts); every party's declines on the point listed.
2. Quotation: the tellers' words, not paraphrase, at every load-bearing point, with note, row and time.
3. Sourcing: every assertion row-cited; external material intaken before citation; the not-held list complete.
4. Independence: hosts, relays and common sources named for every corroboration; counts of independent tellings stated and correct.
5. Alternatives: the strongest alternative stated first and tested with evidence, not dismissed.
6. Strengths and limits: per strand, explicit, both sides.
7. Chronology: a dated table with Agreement; no undated assertion where a date is held.
8. Cover-story test: every official explanation in the thread tested or marked untested with the record that would test it.
9. Holes and tests: finite, placed, runnable; non-tests refused.
10. Conclusion: the verdict class with its basis; live explanations kept live; nothing settled by resemblance.
11. House rules: tags on every divergence; the agency rule (tools/schema.md section 10); leads with tests; register entries produced; links resolve; the page loads as kind `investigation`.

## 5. The pipeline (agents, stages, models)

| Stage | What | Who | Model tier | Why that tier |
|---|---|---|---|---|
| 0 Scope | The question, the strands, the parties, the terms (accented and unaccented), the candidate notes; written to wip/<run>/SCOPE.md | the orchestrator with the owner | Fable (session) | judgement about what the thread is |
| 1 Evidence pack | `python3 tools/evidence_pack.py --out ... --terms ... --people ... --pages` (deterministic; caps stated); one pack per strand with that strand's terms, plus one whole-thread pack | the orchestrator | tool, no model | reproducible; no silent caps |
| 1b Intake of what is cited but not held | fetch (tools/fetch_video.py, rate-limited; web pages to books/sources/web/ with provenance headers), then a house-schema note per source, with `## Use by <the citing source>` and `cited_by` in the reply | one agent per source | Opus, high | an intake is claims, chains, audits, timeline: the tiers below Opus misclass custody (the active pack's model study holds the transcription case, {{pack.model_policy}}) |
| 2 Strand investigation | one agent per strand: reads its pack, then every cited note's relevant sections in full; returns findings as JSON: {finding, quotes[{note,row,time,words}], chain, independent_tellings, declines[], divergences[{tag, reading}], deflationary_readings[], strengths[], limits[], holes[], tests[]} | one agent per strand | Opus, high | reading tellings and judging independence |
| 3 Verification | per finding, three verifiers with distinct lenses, each told to refute: custody and independence; dates and quotation accuracy (open the transcript at the time); the alternative explanation. A finding survives two of three; refuted findings are kept in a "did not survive" list with the reason | three agents per finding (batched per strand) | Opus, high (Sonnet acceptable for the quotation-accuracy lens, which is a string check against the transcript) | plausible-but-wrong findings are the failure mode; refutation by default catches them |
| 4 Synthesis | writes the page in the section 3 structure from the surviving findings, the chronology table, the cover-story rows and the relations neighbourhood; every quotation re-checked against the note | one agent | Fable (recommended; Opus under the standing rule unless the owner says otherwise) | the page is the judgement; holding every strand and deciding what would be conclusive is the hardest step |
| 5 Completeness critic | reads the page and the packs and asks what is missing: a source cited and not held, a strand not run, a teller's decline not listed, a record named but unread, a question nobody asked; returns the Holes section and next-round tasks with tiers | one agent | Fable or Opus | adversarial to the synthesis; must not share its blind spots |
| 6 Judge | scores the page on the section 4 rubric against the model post; lists required fixes; the synthesis agent applies them; one loop | one agent | Opus | rubric-driven |
| 7 Integration | page under research/, kind `investigation` (tools/build_db.py PAGE_KINDS); SHORT label in tools/build_index.py; leads via tools/add_leads.py --label "page: <link>"; cross-checks written back with the split rule and tags; relations appended; answers applied with tools/answer_guard.py's target check; build_db --report, build_index, build_timeline, divergences.py; archive wip to research/corrections/intake-logs/ | the orchestrator | Fable (session) with tools | bookkeeping with judgement |

Lower tiers, where they are safe: Haiku for fetching, link resolution, metadata, formatting and link checks, deduplication of candidate rows, and rate-limited polling; Sonnet for string-level checks (a quotation against a transcript at a time; a date against a row), for first-pass candidate screening when the rubric is explicit (term match → read both sides → keep or drop with the reason), and for summarising a pack into a strand digest that an Opus agent then reads. Never below Opus for anything that assigns a source class, writes a chain, scores an audit row, judges independence, or chooses a verdict. The owner's standing rule (2026-09-25) is that delegated work runs on Opus at high effort; the Fable recommendations above are proposals for the owner to accept or decline per run.

## 6. The second pillar: the method read from the other end

The rows below read the invented pillar of the introduction (Ms Adair's closing submission, `[harrowmere-day-40 claims 12]` to 16 and 31 to 32); the active pack maps its own pillar the same way ({{pack.exemplars}}).

| The insider's description (the second pillar) | Where it lives in this protocol |
|---|---|
| put "the site diary, the inspection logs and the board minutes side by side" (the contractor's records, the owner's records, "the record as a whole") | stage 1: the evidence pack across every note, register and timeline; and the ledger's weakest column, instrument records held as data (in the invented example, the Authority's reservoir-level and rainfall logs would be one; laboratory test records, contractors' site diaries and inspection photographs are the public-domain candidates under the archive rule; the active pack names its own, {{pack.archives}}) |
| "the gaps in the record that make no sense" | the chronology table's Agreement column; the Holes section; the consolidated timelines' open contradictions |
| "find where the record has been managed" | the divergence tags (dir, core, stab, indep, timing, path) and tools/divergences.py's three classes; tools/echoes.py for same wording across linked mouths |
| "the account of 2015 we were given is not right... cover for a repair that was put off" | the cover-story test (section 3.8) and the cover-story register (below) |
| then dig | leads with tests; finite archival tasks; intakes queued |

**The cover-story register** (research/cover-story-register.md, to be seeded; parsed as a register page): one row per official explanation of an event the ledger's witnesses tell differently. Columns: `| # | Event (as officially told) | Issuer, date (note, row) | Witness counter-claim (note, row) | What the explanation must predict in an independent record | The record (held / to obtain) | Check | Verdict (holds / fails / untested) | Lead |`. Candidates already in prose across the notes (in the invented casebook): the Authority's 2018 review, "no warning of cracking was received before 2017", against the Lisle memo; Harlowe's 2017 "no warning was ever put in writing"; the loss of core sample C-14 told as a filing error (lead n); CAC's account of the 2009 pour as to specification against the site diary HI-114; Corvane's account of the Larkspur transfers as ordinary treasury management against Mara Quillon's 2014 complaint (lead n); Velmora's account of the levy's rate as its own ministry's figure against the Dorr cables. The active pack's own candidates are pack data ({{pack.exemplars}}). Every Investigation seeds the rows for its own thread; a backfill pass seeds the rest.

## 7. Brief template (give the agent this text, filled in; keep the rules verbatim)

```
# Investigation strand <letter>: <strand name> (run <label>, <date>)
Project <project root>. Markdown is canonical; notes.db is derived; never init git; do not run build_db.py on the shared notes.db; edit nothing (this stage writes only wip/<run>/<strand>/ files); everything goes in the reply JSON. Read tools/investigation.md sections 1 to 4 first, then tools/schema.md section 2 (custody), 10 (cross-checks, the divergence tag) and 11 (timeline IDs).
The question: <the disjunction>. This strand: <what it covers>. The parties: <names>, with <who hosts, who relays>.
Evidence pack: wip/<run>/<strand>/pack.md (every row is a term match, never a finding; read the cited note and row in full before using it). Notes to read in full for this strand: <list>. Registers: research/relations-register.md (python3 tools/relations.py "<name>"), research/leads-and-inferences.md (grep before proposing), research/timeline-consolidated-<era>.md (the era blocks for the strand's dates), <the speaker ledger page of each ledgered speaker in the strand ({{pack.speaker_ledgers}})>.
Return findings, not a narrative. For each finding: the finding in one sentence; every quotation that carries it (note, row, time, the words); the chain of custody of each telling; the number of independent tellings and why; the declines on the point (audit rows, move, ground); the divergences across tellings (rows, the tag, the four-class reading argued before chosen); the deflationary readings; strengths and limits as evidence; the holes (what is not held, not asked, not read); the tests (finite, placed, runnable; who can run them; what result settles what). Also: chronology rows for the strand (Sortable, date as stated, event, teller, note and row, Agreement with tag); cover-story rows (section 3.8 columns) for every official explanation touching the strand; relations the strand asserts that the register lacks; candidate leads with tests; sources cited by any party and not held.
Standing rules: chain of custody on every telling; a same-speaker repeat or a relay of its own source is never independent; an office's contradiction of a witness is a lead, never a correction; no keyword drops; label anything from memory or the web `own: Claude, <basis>, <confidence>`; quote at most a sentence or two of any copyrighted page.
Checkpoint (tools/agent-wip.md): wip/<run>/<strand>/progress.md from your first minute; findings.json built incrementally; save the final JSON there and reply with it only.
Blocked output (tools/filter-blocks.md): on a second refusal, bisect to the smallest failing unit, capture the source and deliverable locations in wip/<run>/<strand>/blocked/<n>.md, leave the marker `[BLOCKED: ...; awaiting human summary]` at the place, list it under blocked_passages, and finish everything else.
Reply JSON: {"strand","findings":[...],"chronology":[...],"cover_story_rows":[...],"relations":[...],"leads":[...],"not_held":[...],"notes_read":[...],"blocked_passages":[...],"notes_on_method"}
```

The verification brief: "Finding: <text and its quotes>. Your lens: <custody and independence | dates and quotation accuracy | the alternative explanation>. Try to refute it: open the cited notes and rows (and the transcript at the time for quotation accuracy); default to refuted=true if the citation does not carry the finding, the independence count is wrong, the date is not held, or the alternative explains it as well. Reply JSON: {"finding_id","lens","refuted":true|false,"reason","corrections":[...]}."

The synthesis brief: "Write research/investigation-<slug>-<date>.md in the structure of tools/investigation.md section 3, from wip/<run>/findings-verified.json (surviving findings only; the refuted ones go in Method as 'did not survive'), the chronology rows, the cover-story rows and the relations neighbourhood. Re-open every cited note and row as you quote it. Draw the chain diagrams. Write Holes from the critic's report when it arrives (leave the heading with 'pending critic' until then). Reply JSON: {"file","words","sections_present","quotes","rows_cited","leads_proposed","cross_checks_proposed","verdict_class"}."

The critic brief: "Read the page and every pack. List what is missing: a source any party cites that the ledger does not hold; a strand the page treats in a sentence that the ledger holds at length (grep); a teller whose declines on the point are not listed; a record named but unread; a question no interviewer asked that the page could pose; a teller counted as independent who is a relay; a chronology row with no Agreement; an official explanation not tested. For each: the task that would fill it, the files, and the model tier (section 5). Reply JSON: {"holes":[{hole, task, files, tier}], "verdict_on_completeness"}."

The judge brief: "Score the page on tools/investigation.md section 4 (0 to 3 per line) against the model post <the active pack's held model ({{pack.exemplars}})>; for each line under 3, the specific fix (section, what to add or change, from which note and row). Reply JSON: {"scores":{...},"fixes":[...],"ships":true|false}."

## 8. Workflow script (the shape; pass strands, run label and file paths in args)

```js
export const meta = { name: 'investigation', description: 'Strands → verify → synthesis → critic → judge', phases: [{title:'Strands'},{title:'Verify'},{title:'Synthesis'},{title:'Critic and judge'}] }
const OPUS = { model: 'opus', effort: 'high' }
phase('Strands')
const strands = await parallel(args.strands.map(s => () => agent(s.prompt, { label: `strand:${s.key}`, phase: 'Strands', ...OPUS })))
// findings are also on disk at wip/<run>/<strand>/findings.json; the orchestrator parses them between workflows if the reply is too large
phase('Verify')
const findings = parseFindings(strands)             // [{id, strand, text, quotes}]
const votes = await parallel(findings.map(f => () => parallel(['custody','dates','alternative'].map(lens => () =>
  agent(verifyPrompt(f, lens), { label: `verify:${f.id}:${lens}`, phase: 'Verify', ...OPUS })))
  .then(vs => ({ id: f.id, survives: vs.filter(Boolean).filter(v => !v.refuted).length >= 2, votes: vs }))))
phase('Synthesis')
const page = await agent(synthesisPrompt(votes), { label: 'synthesis', phase: 'Synthesis', ...OPUS })   // Fable if the owner allows
phase('Critic and judge')
const [critic, judge] = await parallel([() => agent(criticPrompt, { label: 'critic', ...OPUS }), () => agent(judgePrompt, { label: 'judge', ...OPUS })])
const fixed = await agent(fixPrompt(critic, judge), { label: 'synthesis:fixes', ...OPUS })
const blocked = [...strands, ...votes.flatMap(v => v.votes), page, critic, judge, fixed].filter(Boolean).flatMap(r => (parseJSON(r).blocked_passages || []))
return { strands: strands.length, findings: findings.length, survived: votes.filter(v => v.survives).length, critic, judge, fixed, blocked }   // blocked → tools/blocked_passages.py register, then the owner's summaries
```

Every agent checkpoints to wip/<run>/ (tools/agent-wip.md); the orchestrator writes prompt.md per agent before launch; a killed run resumes from progress.md, never from scratch.

## 9. Naming, loading, indexing

- File: research/investigation-<slug>-<YYYY-MM-DD>.md. tools/build_db.py's PAGE_KINDS maps the prefix `investigation-` to kind `investigation` (added 2026-10-02). tools/build_index.py lists it under Research; give it a SHORT label.
- The map (research/figures/map/database-map.html, the project's map artifact; its data files and display settings: tools/present.md) lists Investigations line by line on the right, newest first by the date in the filename, with lines into the notes circle for the page's citations (grey) and the notes' cross-checks against it (verdict colours); the other research pages sit inside the notes circle as kind groups. Rebuild the data with tools/build_graph_data.py and republish after integration.
- Evidence packs and agent folders: wip/<run>/; archived to research/corrections/intake-logs/<run>/ after integration; the packs are kept there because the page's Method section cites them.
- A re-run of an Investigation (new sources held) is a new dated file with a `Supersedes` row in Metadata; the old page gets a `Superseded by` banner and stays.

## 11. Blocked output (tools/filter-blocks.md)

Every stage's brief carries the blocked-output paragraph and every reply JSON has a `blocked_passages` list. An agent that hits a filter bisects to the smallest failing unit, captures the source location and the deliverable location in `wip/<run>/<stage>/blocked/<n>.md`, enters the marker `[BLOCKED: see <source location>; <capture file>; awaiting human summary]` at the place in its deliverable, and finishes everything else. The workflow script returns every `blocked_passages` entry with the run result; the orchestrator registers them (`python3 tools/blocked_passages.py register`), tells the owner how many summaries are awaited, splices each summary in with `apply` under the owner's name (the precedent of the first blocked intake: an owner's paraphrase entered 2026-09-27 as a claims row of the blocked note, with a standing guidance row), and relaunches the dependent stage with "RESUME: the block at BP-<n> is now filled". An Investigation page with an unfilled marker in a load-bearing place carries `Status: open, blocked at BP-<n>` until the summary lands; the judge scores it as it stands and notes the block. A summary is the owner's reading: it carries rows at the owner's name and is never turned back into a quotation.

## 10. First run (held)

No Investigation has been run. A first run on the post's own thread was prepared (wip/osint-1002/investigation/: scope, six strand briefs, verification, synthesis, critic and judge prompts, packs) and the owner held it on 2026-10-02 pending a decision on the design of the control: an expansion run (agents read the post and improve on it) and a blind run (the post and its derived rows excluded; the judge compares the result with the post) were both described and neither was accepted as the test. The briefs stay on file; the run starts only on the owner's instruction, with the design they choose.

## 12. Fan-outs run guarded (added 2026-10-02)

Every agent fan-out of the pipeline (intakes, strands, verification, probes) runs through the named workflow `guarded-intake` (tools/workflows/guarded-intake.js) so a dead agent is resumed from its checkpoint and, after the last resume, its unit is bisected by `bisect-block` (tools/filter-blocks.md sections 6 to 9). The orchestrator runs `python3 tools/workflow_health.py --runlog` on every hand-back.
