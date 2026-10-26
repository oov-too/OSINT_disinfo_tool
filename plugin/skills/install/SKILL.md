---
name: install
description: "Install the ledger into the current folder (the Python environment, the ledger package and its dependencies, the project template, the documents), say what the administrator must place by hand, and hand over to /ledger:setup. Run once per project, before setup."
argument-hint: "[project folder, default: the current folder] [--offline]"
allowed-tools: Read, Write, Bash(python3 *), Bash(python *), Bash(pip *), Bash(ls *), Bash(find *), Bash(cat *), Bash(uname *), Bash(node *), Bash(claude *)
---

# /ledger:install

You turn an empty folder into a ledger project. Nothing you run fetches a model; the only network use is the package index, and only
when the person is online and not `--offline`.

## 1. Find the bundle

The plugin was installed from the bundle (the release folder or the git repository), and the bundle holds the install script, the
package wheel and the template. Look for `install/install.py` at `${CLAUDE_PLUGIN_ROOT}/..`, then `${CLAUDE_PLUGIN_ROOT}/../..`; if it
is not there, ask the person for the path of their clone or their copy of the bundle, and use that. Call it BUNDLE. Read
`BUNDLE/HANDOVER.md` section 2 once, by its headings, for anything this skill does not cover.

## 2. Say what the person must do themselves, before you continue

Two things no script can do, said plainly and waited for:

1. Every member turns off, in the Claude app's settings under Privacy (or Preferences), 'Location metadata' and 'Help improve our AI
   models'. The second allows chats and coding sessions to be used to train the provider's models, and the project's sessions will
   hold their sources and notes about named people. Ask whether it is done on this account; do not go on until the answer is yes.
2. The administrator places the managed settings file for this operating system (`BUNDLE/managed-settings/<os>.json`, its README
   names each key) at the system's managed path. It needs administrator rights, so you print the path and the file's purpose and ask
   whether it is in place; if not, continue with the install and say that `/ledger:setup` stage 0 will refuse until it is.

## 3. Check the machine

`python3 --version` (3.11 or later), `node --version` (the workflow scripts need it), `uname -s` (or the Windows equivalent). Report
what is missing, with the one line that fixes it, and stop if Python is too old.

## 4. Install

In the project folder (the argument, else the current folder; it may be empty or already hold the person's files, which are never
overwritten):

- Online: create `.venv` with `python3 -m venv .venv`, then with its python: `pip install -r BUNDLE/wheels/requirements.txt`, then
  `pip install BUNDLE/wheels/ledger-*.whl`, then `python3 BUNDLE/install/install.py --apply --system --project <folder>`. The `--system`
  flag installs into the active environment, where the dependencies now are.
- Offline (`--offline`, or no package index reachable): `python3 BUNDLE/install/install.py --apply --project <folder>`, which makes
  the project's own environment and installs every wheel from `BUNDLE/wheels/` with no network. If `BUNDLE/wheels/deps/` is absent
  (a git clone carries no dependency wheels), say so and give the online command instead.

Show the install script's report in full: what it laid down, the checks it ran, and any line that says what the administrator must
stage (`BUNDLE/platform/<os>/MANIFEST.md`: the OCR and transcription pieces, needed only for scanned documents and recordings).

## 5. Hand over

Say what exists now: the project folder with its tools, the documents under `docs/`, the plugin's commands. Then: the administrator
runs `/ledger:setup` in this folder for stage 0; the project manager takes stages 1 to 8. Nothing is intaken until setup's last stage.
