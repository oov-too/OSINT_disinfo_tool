# The ledger plugin

A Claude Code plugin (manifest `.claude-plugin/plugin.json`, name `ledger`) that drives a ledger project: a folder of markdown notes
over a research group's own sources, with the `ledger` Python package and the project's `tools/`. Built in phase 7a of the platform
plan against the plugin format checked on 2026-10-22 (the build notes record the documentation pages read).

| Path | What it is |
|---|---|
| `.claude-plugin/plugin.json` | the manifest |
| `skills/setup`, `settings`, `intake`, `narrate`, `attack`, `report`, `status` | the seven skills (`/ledger:install` (the environment, the package and the template into a folder; before setup), `/ledger:setup` and so on) |
| `agents/reader.md`, `writer.md`, `finisher.md`, `builder.md`, `attacker.md`, `reviser.md` | the reading and writing agents, model `opus` and effort `high` fixed in the frontmatter |
| `agents/probe.md` | the pass-through probe for script gates and bisect-block, model `haiku` |
| `hooks/hooks.json`, `hooks/ledger_hook.py` | the verbatim check and the database build (into a check copy) after a note or part is written; the report check when an agent stops; all in Python, none fails a write |
| `scripts/lock.py`, `scripts/runlog.py` | the one-writer lock (an atomic directory create) and the run log |
| `templates/CLAUDE.md.template` | the project CLAUDE.md that setup generates from the rulings |
| `templates/answers-casebook.json` | answers for /setup against the bundle's sample database |
| `templates/briefs/` | the brief templates, their canonical source (moved here from the platform's working folder in phase 7a); the skills render them with `tools/ledger/briefs.py` |

## Installing

On a machine with no outbound access beyond the model route, from the release bundle on a mount:

1. The administrator installs the managed settings file for the OS (the bundle's `managed-settings/`), which registers the bundle's
   directory marketplace, enables `ledger@ledger-local` and fixes the provider, models and effort ceiling.
2. `claude plugin marketplace add <bundle folder>` then `claude plugin install ledger@ledger-local` (or a seed directory built from
   them, named by `CLAUDE_CODE_PLUGIN_SEED_DIR`).
3. In the project folder: `/ledger:setup`.

For development, `claude --plugin-dir <this folder>` loads it for one session.

The skills call the project's own tools (`python3 tools/ledger/setup_stages.py`, `python3 ledger.py ...` or the installed `ledger`); nothing
in this folder holds project data.
