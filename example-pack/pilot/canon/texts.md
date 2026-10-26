# Canon texts of the pilot pack

The canon layer is core (the canon adapter, witness comparison, canon citation in rows, the echo tool over the canon). Which texts are the canon and the unit scheme per text are this pack's. The canon is the three judgments the inquiry's terms of reference name as its foundation ("The Inquiry will draw on the findings made by Mr Justice Fraser ... (in particular Judgment (No3) 'Common Issues' and Judgment (No 6) 'Horizon issues'), the judgments of the Court of Appeal (Criminal Division) in R v Hamilton and others": sources/pilot/web/2021-06-01-terms-of-reference-post-office-horizon-it-inquiry/text.md).

| Text id | Citation | Court and date | Held from | Hold | Units | Paragraphs missing from the chain |
|---|---|---|---|---|---|---|
| bates-no6-horizon-issues | [2019] EWHC 3408 (QB), Judgment (No 6) "Horizon Issues" (Rev 1) | High Court, QBD, Fraser J, 16 December 2019 | inquiry exhibit RLIT0000005 | sources/pilot/canon/bates-no6-horizon-issues/ | 1,027 (paragraphs 1 to 1030) | 11, 793, 1003 |
| bates-no3-common-issues | [2019] EWHC 606 (QB), Judgment (No 3) "Common Issues" | High Court, QBD, Fraser J, 15 March 2019 | inquiry exhibit POL00022936 | sources/pilot/canon/bates-no3-common-issues/ | 1,110 (paragraphs 1 to 1122) | 3, 5, 8, 215, 416, 518, 918, 1027, 1028, 1040, 1053, 1062 |
| hamilton-v-post-office | [2021] EWCA Crim 577, Hamilton and others v Post Office Ltd | Court of Appeal (Criminal Division), 23 April 2021 | inquiry exhibit POL00113278 | sources/pilot/canon/hamilton-v-post-office/ | 444 (paragraphs 1 to 447) | 3, 7, 8 |

## Licence route (owner, 2026-10-22)

The judgment text does not ship with the pack. The pack carries the fetch manifest, [fetch-manifest.toml](fetch-manifest.toml): for each judgment the inquiry's evidence page and exhibit number, the PDF's bytes and SHA-256 as held here on 2026-10-22, the scheme file, the expected unit count and the steps. A recipient re-holds each judgment from the inquiry's site under its terms (Crown copyright; the site's Open Government Licence notice), checks the bytes against the manifest, and cuts the units with the same scheme, so that a citation `at [n]` resolves to the same paragraph on every machine. Example notes quote the judgments only in short passages, each attributed with the neutral citation and paragraph. The holds under sources/pilot/canon/ are this project's local copies and are excluded from any bundle.

## The unit scheme: the numbered paragraph

- Unit: the judgment's numbered paragraph; address the number; cited in rows as `<citation> at [n]` with the hold's line (`[2019] EWHC 3408 (QB) at [315], paragraphs.txt:4288`). `python3 tools/ledger/acquire/canon.py cite sources/pilot/canon/<id> "315"` returns the unit.
- How the units are cut: the held PDF's text layer (the publisher's OCR of page images; see each hold's `text_layer_origin`) goes through the pack plugin [paragraphs.py](paragraphs.py), which inserts a marker line `¶ n` before each paragraph start of the in-order chain (a numbered line is a paragraph start only if its number is the next expected or at most three beyond it; the first must be 1; OCR letters O, l, I read as digits); the core canon adapter's `headings` scheme ([schemes/](schemes/), one level, pattern `^¶ (\d+)$`) then cuts one unit per marker. No line of the text layer is changed, so a quotation from the text layer still matches.
- Missing numbers: a paragraph whose number the OCR damaged stays inside the previous paragraph's unit (the table above lists them; each hold's paragraphs-report.json has the rejected candidates). A citation of a missing paragraph resolves to the unit that holds it, and the row says so.
- Tail matter: text after the last paragraph (the Horizon Issues glossary, signatures) belongs to the last unit; cite it by line.
- Page furniture: each page's exhibit stamp (`RLIT0000005`, `POL00022936`, `POL001 13278`) and running heads are inside the units; the verbatim gate should ignore them.

## Witnesses

Each judgment is held once (one witness). A second witness for comparison, should the owner want one (the canon layer's witness comparison), is the court's own published text on Find Case Law or judiciary.uk; neither was fetched (corpus.md: Find Case Law's robots.txt disallows Claude agents; judiciary.uk refused the request). The technical appendix to the Horizon Issues judgment is a separate exhibit (RLIT0000006) and is not held.

## Reading-method plugins

paragraphs.py is the only plugin: a unit-marking aid, not a reading method. No cipher or numerical reading applies to this corpus.
