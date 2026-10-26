# Vendored libraries (phase 5 of tools/platform-plan.md, 2026-10-22)

The map (research/figures/map/database-map.html) and the narrative viewer open with no network: every script they load is in this folder. The viewer loads none (its data and code are inlined); the map loads d3.

| Library | Version | Files | Licence | Fetched | SHA-256 |
|---|---|---|---|---|---|
| d3 | 7.9.0 | d3-7.9.0/d3.min.js | ISC (d3-7.9.0/LICENSE, Copyright 2010-2023 Mike Bostock) | 2026-10-22, from the npm package d3@7.9.0 (its dist/d3.min.js and LICENSE), with the owner's approval | d3.min.js f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539; LICENSE 3e6849627f74ff73c257a3ae1efb574015d94fc1035c05ec3c15805165efcbc4 |

The map references it as `../vendor/d3-7.9.0/d3.min.js` (relative to research/figures/map/). Fonts are not vendored: the pages name their preferred faces and fall back to the system's (serif, sans-serif, monospace stacks). To update a library, place the new version in its own folder with its licence, change the one script tag, and record it here.
