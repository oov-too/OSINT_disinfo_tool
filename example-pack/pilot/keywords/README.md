# packs/pilot/keywords

Term lists of the pilot pack, every term taken from the held sources (sources/pilot/). They serve three uses: the detection seeds of setup stage 4 (organisations, people, actor and polity terms), the scrub that checks nothing of one pack leaks into core or into another pack (the phase 6b separation check read another pack's lists against this one; the reverse check reads these lists against that pack's corpus), and tools/context_pack.py's identifier forms (id-patterns.tsv). Matching rule: case-insensitive whole word for terms of four characters or more; case-sensitive whole word for shorter ones; literal for terms with spaces or punctuation.

| File | Contents |
|---|---|
| organisations.txt | institutions, firms, bodies and internal projects named in the held sources |
| people.txt | people named in the held sources with a role in the order of battle or the circles |
| terms.txt | the corpus's system, bug and process vocabulary (the codebook's terms, flat) |
| actor-polity.txt | the PIR keyword seed (packs/pilot/registers/actor-polity-vocabulary.md) |
| catalyst-keywords.txt | keywords of the dated events (packs/pilot/seeds/catalysts.md) |
| stock-phrases-domain.txt | the corpus's set expressions, for the echo tool's stop-list |
| id-patterns.tsv | the inquiry's URN forms for tools/context_pack.py |
