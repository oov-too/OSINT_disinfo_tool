# Installing from this repository (a machine with network access)

The removable-media bundle carries every dependency wheel for macOS, Linux and Windows under `wheels/deps/` and installs with no
network. This repository is the same bundle without those dependency wheels (415 MB), so a machine that can reach the Python package
index installs them itself. Read `HANDOVER.md` first; then:

1. Python 3.11 or later. Create the project's folder and a virtual environment in it, and activate it.
2. `pip install -r wheels/requirements.txt` (the dependency list the bundle was built with; fetched from the package index).
3. `pip install wheels/ledger-*.whl` (the ledger package itself, first-party, carried here).
4. With that environment still active: `python3 install/install.py --apply --system --project <the project folder>`. The `--system`
   flag installs the ledger package into the active Python (where step 2 put the dependencies) instead of building the bundle's own
   offline environment, which would look for dependency wheels this repository does not carry. The install then lays the template, the
   plugin and the documents into the project folder; it fetches nothing.
5. Register the plugin with Claude Code from this clone: `claude plugin marketplace add <this folder>` and
   `claude plugin install ledger@ledger-local`. Then the administrator's checklist (`HANDOVER.md` section 3) and
   `/ledger:setup`; or run `/ledger:install` first and let it do steps 1 to 4 for you.

A machine with no network uses the media bundle instead; the two install the same files, and `CHECKSUMS.sha256` here covers every
file of this repository (the media bundle's checksum file also covers the dependency wheels).
