"""Test hygiene (2026-10-26): every test starts in the folder pytest was started from, with the ledger's environment variables as they
were, whatever an earlier test or an in-process tool changed. The three setup tests that failed only in a one-process run were started
from a working folder an earlier test had deleted (the child died at os.getcwd()); the per-file runner never saw it."""
import os, pytest
_START = os.getcwd()
_VARS = ("LEDGER_ROOT", "LEDGER_PLUGIN_ROOT", "LEDGER_MANAGED_SETTINGS", "LEDGER_USER", "LEDGER_EXAMPLE_PACK")

@pytest.fixture(autouse=True)
def _restore_cwd_and_env():
    saved = {v: os.environ.get(v) for v in _VARS}
    yield
    try: os.chdir(_START)
    except FileNotFoundError: pass
    for v, val in saved.items():
        if val is None: os.environ.pop(v, None)
        else: os.environ[v] = val
