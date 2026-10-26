# Setting up with Claude: paste this into Claude Code

Open Claude Code in an empty folder on the machine that will hold the project, and paste everything below the line as your first
message. Claude does the rest and tells you the two things only you can do.

---

You are setting up the OSINT ledger for me from its private repository, `oov-too/OSINT_disinfo_tool` on GitHub, which this machine can reach.

1. First, before any command, tell me the two account settings I must turn off in the Claude app (Settings, Privacy: 'Location
   metadata' and 'Help improve our AI models'), say in one sentence why, and wait for me to confirm.
2. Install the plugin from the repository: run `claude plugin marketplace add oov-too/OSINT_disinfo_tool` and then
   `claude plugin install ledger@ledger-local`. If I have already cloned the repository, `claude plugin marketplace add <the clone's
   folder>` works instead. If the `claude` command is not available to you, show me the two commands to run in my terminal and wait
   until I say they are done.
3. Run `/ledger:install` in this folder. Follow its steps, show me its report, and tell me what the administrator must place by hand
   (the managed settings file for this operating system).
4. When the install is complete, tell me to run `/ledger:setup`, which the administrator starts (stage 0) and the project manager
   continues (stages 1 to 8), and stop there.

Do not fetch anything but the repository and the Python package index, do not intake any source, and ask me before any step that
needs administrator rights.
