# Actor and polity vocabulary of the pilot pack

The core register is the actor and polity register in the vocabulary of national security studies (tools/platform-plan.md, core-versus-pack table): actors (state actors, non-state actors, proxies, fronts, individuals) with teller, chain, goals and confidence by provenance; polities (states, alliances and blocs, coalitions, transnational criminal organisations and cartels, movements and factions, networks), nesting, with upstream and carriers; order of battle as dated sourced rows; a referent object and each polity's assessed posture toward it (intent, capability) by whose telling; a PIR overlay that seeds keywords but places nothing. This pack fills it for the Post Office Horizon IT Inquiry. The seed rows are in [order-of-battle-seed.md](order-of-battle-seed.md), every one cited to a held line.

| Field | This pack's value |
|---|---|
| Register page (to be created by the first intake) | research/actor-polity-register.md in the pilot project |
| Referent object | the subpostmasters (their liberty, livelihoods and good names) and the integrity of the branch accounts and prosecutions built on Horizon data. Source: Hamilton at [1] ("We have to decide whether their prosecutions were an abuse of the process of the court and whether their convictions are unsafe"), the terms of reference, paragraph B |
| Report keys every intake returns | `actor_rows` (the row shape below) and `polity_statements` (posture toward the referent, by whose telling), or `none` |
| Row shape | `\| # \| Actor as named (teller's spelling) \| Kind \| Polity \| Order of battle (part of, run by, funded by, contracted by, instructed by, a front for) with date \| Teller and note row \| Firsthand / relayed (chain) \| Goals or role as told \| Posture toward the referent (intent, capability) as told \| Confidence \|` |
| Kinds | state actor (a department, the shareholder, a court, a prosecutor, a commission, a committee, the inquiry; a company owned by the state is a state actor and says so); non-state actor (a corporation, a law firm, an auditor, an investigating firm, an alliance, a federation, an outlet); proxy (acting for another under its instruction: a lawyer for a client, an expert for a party); front (an entity standing in for another; none is recorded in the held sources); individual |
| Polities in the seed (P1 to P7) | the state; the Post Office coalition (POL with its executives, projects, working groups and contracted lawyers); Fujitsu (from ICL Pathway); the subpostmasters' movement (JFSA, claimants, appellants); the NFSP (a faction); the press and campaigners (a network); the investigators (Second Sight) |
| Confidence scale | high (a court's finding, a dated document, or the speaker on his or her own role), medium (a named witness on another's role, a press report of a named speaker), low (anonymous, a forum post, three or more hops, or labelled inference), nil (a word only) |
| Order-of-battle verbs (the detection pass of setup stage 4) | part of, a division of, taken over by, appointed by, instructed by, advised, employed by, contracted to, reports to, chaired by, a member of, owned by, became |
| The court's place | the judgments are the canon of record: a court's finding is entered as the court's telling, cited by paragraph, beside the parties' tellings; never as a referee's correction of a witness (the core rule that agencies under scrutiny are parties) |

## Priority intelligence requirements (the overlay; packs/pilot/pack.toml [pirs])

Written by the phase 6b prep session from the terms of reference (paragraph B) and the held sources, and confirmed by the owner on 2026-10-22 (setup stage 1). They seed keywords and surface entries; they place nothing.

| PIR | Question | Essential elements of information |
|---|---|---|
| PIR-1 | When did each actor first record, in writing, (a) bugs affecting branch accounts and (b) the ability to alter branch data without the subpostmaster's knowledge? | per actor (POL executives and board, POL's lawyers, Fujitsu's SSC and management, the shareholder): the earliest dated document, its author and recipients, and whether it reached a defendant or a court |
| PIR-2 | How did POL's public, parliamentary and court statements on Horizon's reliability and on remote access change, and when? | each dated statement with its speaker and audience (the 2009 spokesman, the 2015 statements, the 2019 admissions), and the documents the speaker held at that date |
| PIR-3 | Who directed POL's response to its critics (Second Sight, the JFSA, the mediation scheme, the group litigation), through which bodies, and with what stated aims? | membership and dates of Project Sparrow and the X Working Group; decisions on the mediation scheme; instructions to lawyers; what each member says now |

## Keywords the PIRs seed (keywords/actor-polity.txt)

remote access, Balancing Transaction, APPSUP, SSC, ARQ, PEAK, KEL, Sparrow, X Working Group, Working Group, Mediation Scheme, Second Sight, Clarke advice, expert witness, disclosure, robust, bugs errors and defects, Receipts and Payments Mismatch, Callendar Square, Dalmellington, Group Litigation, settlement, shareholder, ShEx, UKGI, BEIS.
