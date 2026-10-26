# OSINT disinformation ledger

A local research ledger for a group whose sources are in their own database: every claim rowed with its chain of custody and its
exact quotation, a forthrightness audit of every speaker, registers of people, organisations and their relations, a dated timeline,
narratives that are built and then attacked under a disinformation lens, and reports against the group's own questions. It runs
inside Claude Code on the group's own model route; nothing in it sends the group's material anywhere else.

**Demo:** the narrative page of the worked example, a UK public inquiry, as the tool renders it: `docs/demo/narratives-viewer.html`
(one self-contained file; open it in a browser).

**Licence:** Apache License 2.0 (`LICENSE`).

**Case study:** [Parsing disinfo with OSINT and LLMs](CASE_STUDY.md), the methods, the product, the manual tools and the measurements behind the design.

## Start here

1. **On every account that will use it, in the Claude app:** Settings, then Privacy, and turn off *Location metadata* and *Help improve
   our AI models*. The sessions will hold your sources and notes about named people; these two settings govern what the provider may
   keep of them.
2. **Have Claude Code installed** and signed in to your Claude route, with Python 3.11 or later and Node available.
3. **Open Claude Code in an empty folder and paste the message in [`BOOTSTRAP.md`](BOOTSTRAP.md).** Claude installs the plugin from
   this repository, runs `/ledger:install` (the Python environment, the ledger package, the project template), tells you what the
   administrator must place by hand, and stops before setup.
4. **The administrator runs `/ledger:setup`** (stage 0), then the project manager continues it (stages 1 to 8: your question, the
   mapping of your database, the subjects and rules, the people and organisations found, the first intake).

By hand instead: [`ONLINE-INSTALL.md`](ONLINE-INSTALL.md). Read [`HANDOVER.md`](HANDOVER.md) for what the platform is and is not, the
administrator's checklist, the measured costs, the worked example, the standing rules and the known limits.

## What is here

| Folder | What it holds |
|---|---|
| `BOOTSTRAP.md`, `ONLINE-INSTALL.md` | the two ways in |
| `HANDOVER.md` | the handover document |
| `plugin/` | the Claude Code plugin: `/ledger:install`, `setup`, `settings`, `intake`, `narrate`, `attack`, `report`, `status`; its agents, hooks and brief templates |
| `template/` | the project template: the tools, the workflow scripts, the protocol documents, the viewer |
| `docs/` | the protocol documents, and `docs/demo/` the worked example's viewer |
| `example-pack/pilot/` | the worked example's domain pack, with the fetch manifest of its public sources |
| `sample/` | synthetic databases to run setup against before your own |
| `wheels/` | the ledger package and its dependency list (dependency wheels are fetched from the package index on install) |
| `install/`, `managed-settings/`, `platform/` | the install script, managed-settings templates per operating system, and what the administrator stages for OCR and transcription |
