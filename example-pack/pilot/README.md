# packs/pilot: the phase 6b pilot pack (the Post Office Horizon IT Inquiry)

A second-domain pack (tools/platform-plan.md, phase 6b), written without touching core: a public inquiry with hearings and exhibits, its judgments as the canon, its own argot, the institution's own replies as adverse sources, and a lens from a published text. It is the shape a recipient's pack takes, and the plan makes the phase 6 pack the recipient's example, so nothing in it names or quotes the project's first pack. Prepared 2026-10-22 by the phase 6b prep session; every value was confirmed by the owner on 2026-10-22 (with Alan Bates added as a third ledgered speaker), drawn from the held sources under sources/pilot/ (the corpus case and the source list: wip/platform-phase6b/corpus.md).

| Folder or file | Holds |
|---|---|
| pack.toml | the manifest: the question, three PIRs, five subjects and the two audited, the audit clauses and 15 topic codes, the (empty) object register, the actor and polity vocabulary and referent, the two ledgered speakers, the lens instance, the canon, the codebook, the circles and the adverse-source rule, the catalysts and the threshold, the source kinds, six eras, the narrative seed and rival, the vocabulary files, the pack code, the briefs, the display settings |
| schema-extensions.md | the clauses this pack adds to tools/schema.md (hearing-day and exhibit metadata, topic codes, the decline grounds the transcripts show, citation forms, the divergence clause) |
| registers/ | the actor and polity vocabulary with the PIRs; the seed order of battle (29 actors, 7 polities, 17 dated rows, 8 posture rows, every row cited to a held line); the three ledgered speakers (Bates, Vennells, Jenkins) |
| lenses/sfo-cooperation.json | the lens instance from a text: the SFO's corporate guidance, 15 techniques with their held lines, mapped onto the core catalogue; no placements |
| canon/ | the three judgments, the unit scheme (the numbered paragraph), the scheme files and the paragraph marker plugin |
| codebook/ | the corpus's argot, code names and acronyms with the sources' own keys; one decode held as a lead |
| seeds/ | the circles with adverse sources per circle; the catalysts (20 dated events, threshold 2009-05-11); the narrative seed and its rival; theses.json |
| keywords/ | organisations, people, terms, the PIR keyword seed, catalyst keywords, stock phrases, the identifier forms |
| briefs/ | slots.toml (every slot of the phase 4 templates; all 26 templates render, every slot from the pack); runs/pilot-6b.toml and .md (the intake run, drafted) |

Licence route for the canon (owner, 2026-10-22): the judgment text does not ship. The pack carries the fetch manifest (packs/pilot/canon/fetch-manifest.toml: for each judgment the inquiry's evidence page, the exhibit, the expected bytes and SHA-256 of the PDF as held here, the scheme file and the commands), and the recipient re-holds each judgment from the inquiry's site under its terms. Example notes quote the judgments only in short passages, each with its attribution (the neutral citation and paragraph).

Pack code: canon/paragraphs.py (pack.toml [code]). Not in this pack: a reference object (a candidate is named in registers/README.md), a channelled class, compilers, a bulk archive.

The pilot runs best in its own project folder with its own ledger.toml naming this pack (wip/platform-phase6b/handoffs.md, item 2): the current ledger.toml names the first pack, and core tools read the pack through tools/packload.py, which every accessor of was exercised against this pack on 2026-10-22 without error.
