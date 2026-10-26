---
name: status
description: Rebuild and show the project's status page (sources held and queued, notes, register sizes, what the narratives rest on that is not held, the quota, open rulings and owed work, PIRs and the findings on each). Run after every hand-back.
argument-hint: ""
allowed-tools: Read, Bash(ledger *), Bash(python3 ledger.py *), Bash(python3 tools/*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runlog.py *)
---

# /status

No agent reads a brief here: you run tools and show the page.

1. `ledger build db --report` (the shared database, built only by the orchestrator, after integration; local to this machine:
   ledger.toml [database] path).
2. `ledger present status` writes the status page (research/status.md): sources held and queued (including `sources/db/<name>/queue.tsv`),
   notes, register sizes, what the narratives rest on that is not held, the quota and source balance, open rulings, PIRs and the
   findings on each.
3. Add what the page does not carry yet, from the files themselves: the open rows of `owed.md`
   (`python3 tools/ledger/settings.py owed`), the setup stages still to do (`python3 tools/ledger/setup_stages.py status --project .`), and
   the locks held (`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lock.py list`).
4. Show the page's summary to the person, with the PIRs first.

The page is a markdown file in the folder; it is published only as below.

## Publishing (the end user's choice; off by default)

The local file is always written first. Then `python3 tools/ledger/settings.py publish-check docs` (and `map` for the map page): exit 0 means the project publishes this target, the model route has artifacts and claude.ai is reachable, so publish the page with the Artifact tool and then run `python3 tools/ledger/settings.py published docs`; exit 1 prints the reason (publishing off, the target not chosen, a provider or gateway route, claude.ai unreachable): publish nothing, and tell the person that the local file is the result and why.
