#!/usr/bin/env python3
"""The ledger command for this project folder (tools/platform-plan.md, phase 2): `python3 ledger.py <layer> <tool> [arguments]`,
`python3 ledger.py integrate <report.json>`, `python3 ledger.py check`, `python3 ledger.py tools`. A thin entry point: the command is
tools/ledger/cli.py; every tool still runs as `python3 tools/<tool>.py`."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(HERE, "tools", "ledger")

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(HERE, "tools"))
    # the project served: $LEDGER_ROOT, else the nearest ledger.toml at or above the working folder (a second project run with these
    # tools, the pilot or a round-trip copy, is served and never this one), else this folder (2026-10-22)
    if "LEDGER_ROOT" not in os.environ:
        d = os.getcwd()
        while not os.path.isfile(os.path.join(d, "ledger.toml")) and os.path.dirname(d) != d: d = os.path.dirname(d)
        os.environ["LEDGER_ROOT"] = d if os.path.isfile(os.path.join(d, "ledger.toml")) else HERE
    from ledger.cli import main
    sys.exit(main())
else:
    # Imported as `ledger` because the project root is on sys.path (python3 -m ledger.cli, or python3 -c, run from the root): this
    # file stands in for the package tools/ledger/, so ledger.notes, ledger.paths and ledger.cli are the package's own modules.
    __path__ = [_PKG]
    _init = os.path.join(_PKG, "__init__.py")
    exec(compile(open(_init, encoding="utf-8").read(), _init, "exec"))
