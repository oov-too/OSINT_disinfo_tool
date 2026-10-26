# The ledger project template

`install/install.py --apply --project <folder>` lays this folder into a new project folder (a file already there is never
overwritten). It holds what a project needs beside its notes: the 74 core tools under tools/ (run as `python3 tools/<tool>.py` or
through `python3 ledger.py <layer> <tool>`), the workflow scripts (tools/workflows/), the package source the tools import
(tools/ledger/, the same as the bundle's wheel), the protocol documents the tools and the briefs read (tools/*.md, the schema
first), the core technique catalogue, the stock phrases of the echo tool, the viewer template and its vendored library
(research/figures/vendor/), the Vision OCR source, and the root launcher ledger.py. The project's own folders (videos/, books/,
subjects/, research/, sources/, packs/<pack>/, setup/) are written by /ledger:setup and by intake.

Left out: build_bundle.py (the maintainer's bundle builder: the bundle is its output; a project never builds one); handover.md (shipped at the bundle's top level as HANDOVER.md); build_bundle.md (not a shipped protocol document).
