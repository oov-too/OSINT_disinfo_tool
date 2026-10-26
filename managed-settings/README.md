# Managed settings templates

One file per OS. The administrator edits it and installs it at the OS's managed path (Claude Code reads only that path; the
documentation page `managed-settings`, checked 2026-10-22):

| OS | Install at |
|---|---|
| macOS | `/Library/Application Support/ClaudeCode/managed-settings.json` |
| Linux, WSL | `/etc/claude-code/managed-settings.json` |
| Windows | `C:\Program Files\ClaudeCode\managed-settings.json` (the legacy `C:\ProgramData\...` path is not read) |

On a provider or gateway route, server-managed settings are bypassed, so this file is the policy. Edit before installing:

- **The route.** The template is written for Amazon Bedrock (`allowedProviders` `bedrock`, `CLAUDE_CODE_USE_BEDROCK`, `AWS_REGION`,
  the Bedrock runtime host in `sandbox.network.allowedDomains`). For another route set `allowedProviders` to one of `vertex`,
  `foundry`, `anthropicAws`, `anthropic`, `gateway` (or `customEndpoint`, `mantle`), replace the env selector
  (`CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_USE_FOUNDRY`, `CLAUDE_CODE_USE_ANTHROPIC_AWS`; a gateway's `ANTHROPIC_BASE_URL`) and the
  allowed domain. A proxy goes in `env` as `HTTPS_PROXY` (plain HTTPS proxies only), a CA bundle as `NODE_EXTRA_CA_CERTS`.
- **The bundle's path** on the mount, in `extraKnownMarketplaces` and `strictKnownMarketplaces` (absolute).
- **Models and effort.** `availableModels` must allow Opus (every reading and writing agent) and Haiku (the probes);
  `maxEffortLevel` must be `high` or above (the agents run at high effort). Leave `CLAUDE_CODE_SUBAGENT_MODEL`,
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and `CLAUDE_CODE_EFFORT_LEVEL` unset: they override the agents' fixed model and effort.
- **Hooks.** `allowManagedHooksOnly` blocks every hook except those of plugins force-enabled here, so `enabledPlugins` must name
  `ledger@ledger-local` or the ledger's checks will not run.
- **Traffic.** `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` (any non-empty value disables it) and
  `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL` keep the only outbound connection the model route.

Setup stage 0 refuses to continue when this file is missing, and reports any setting above that would stop the agents.
