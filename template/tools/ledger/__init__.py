"""The ledger package (phase 2 of tools/platform-plan.md, 2026-10-22): the parser library (ledger.notes), the project's paths and
the sources/ alias table (ledger.paths), and the one command (ledger.cli) over the tools in tools/.

Imported by the tools as `from ledger import notes` (tools/ is the first entry of sys.path when a tool runs as
`python3 tools/<tool>.py`), and by the command through the thin ledger.py at the project root."""
__version__ = "0.2.0"
