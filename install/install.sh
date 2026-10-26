#!/bin/sh
# The ledger bundle's install entry point on macOS and Linux: runs install/install.py with this machine's Python 3 (3.11 or later).
# Nothing is fetched. See install.py --help.
here="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$here/install.py" "$@"
