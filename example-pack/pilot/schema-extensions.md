# Schema extensions of the pilot pack

The clauses this pack adds to tools/schema.md, section by section. Everything not named is core unchanged.

## 1. Metadata

- A hearing note's metadata takes the hearing day (`Day 117`), the transcript URN (`INQ00001126`), the phase (`Phases 5/6`) and both recording links, from the hold's README.
- An exhibit note's metadata takes the URN, the document date as the inquiry's evidence page gives it, the evidence type, and `text_layer_origin` from the hold (the publisher's OCR: quote with the page image beside it).

## 2. Claims topics

The pack's topic codes (pack.toml [[audit.topics]]): horizon-bugs, remote-access, knowledge-and-timing, prosecutions, disclosure, contract-and-liability, investigation-and-audit, mediation-and-redress, governance-and-government, legal-strategy, communications-and-press, own-role, how-they-know, human-impact, other.

## 3. Forthrightness audit

Mandatory for notes under the audited subjects (pack.toml [subjects] audited). Basis vocabulary for a stated decline at the inquiry, from the held transcripts: legal professional privilege (counsel cannot ask across it: Day 142, transcript.txt line 11113; the court on privilege, Common Issues at [40]); privilege against self-incrimination (the Chair's direction opening Day 142, transcript.txt lines 23 to 87); deferral to another body or witness ("It may be a question for them": Day 117, transcript.txt line 8269). "I don't remember" is not a stated decline. Further grounds (a restriction order, a pending police investigation) are added when a held transcript shows a witness relying on one. Counsel's questions supply the topic; the witness's answer is scored. A hearing day is a multi-voice recording: the inquiry's counsel, the Chair and the witness are separate speakers, and only the witness's turns are scored.

## 7. Citations

- Canon rows cite `<neutral citation> at [n]` and the hold line (packs/pilot/canon/texts.md).
- Transcript rows cite the inquiry's page and line (`Day 117, 159:24`) beside the hold's transcript.txt line: the inquiry's own page:line is the form other sources use.
- Exhibit rows cite the URN and page (`POL00028838, p. 2`) beside the hold's text.txt line.

## 9. Divergences

Tellings of the same fact by POL at different dates (2009, 2015, 2019, 2024) are a divergence of one party across time and are always recorded, with the documents the party held at each date (PIR-2).
