# Power Platform skills (vendored)

Skills and agents from Microsoft's [power-platform-skills](https://github.com/microsoft/power-platform-skills) marketplace plus the [Dataverse-skills](https://github.com/microsoft/Dataverse-skills) plugin, vendored directly into this repo because `/plugin marketplace add` is not available in this environment (web/remote sessions don't support the plugin CLI).

Source: `main` branch as of 2026-10-15. License: MIT (Microsoft Corporation) — see `skills/LICENSE-microsoft-power-platform-skills`.

## Plugins vendored (11)

| Plugin | Skills | Agents | Source |
|--------|--------|--------|--------|
| canvas-apps | 4 | 7 | power-platform-skills |
| code-apps | 15 | 1 | power-platform-skills |
| dataverse | 9 | — | Dataverse-skills |
| mcp-apps | 3 | — | power-platform-skills |
| mobile-apps | 26 | 5 | power-platform-skills |
| model-apps | 4 | 6 | power-platform-skills |
| pcf | 3 | — | power-platform-skills |
| power-apps-mobile-extension | 12 | — | power-platform-skills |
| power-automate | 11 | — | power-platform-skills |
| power-pages | 36 | 6 | power-platform-skills |
| process-intelligence | 10 | — | power-platform-skills |

## Layout

- `agents/<plugin>/*.md` — subagent definitions (e.g. `canvas-screen-builder`, `genpage-planner`), one folder per source plugin.
- `skills/<plugin>/skills/<skill-name>/SKILL.md` — skill definitions, nested exactly as upstream so relative links to `references/` and `scripts/` resolve correctly without path rewrites.
- `skills/<plugin>/{references,scripts,hooks,shared}` — supporting material skills depend on (large vendored SDK blobs, test files, and compiled MCP server bundles were excluded).
- `skills/<plugin>/.mcp.json` — the MCP server(s) each plugin expects. Not wired into this project's MCP config automatically; reference only.

## Known limitation

Several plugins each ship a skill named `report-issue` (and a few other generic names). Outside the real plugin system there is no `plugin:skill` namespace to disambiguate them — only the directory path does. If Claude Code's skill loader keys on frontmatter `name:` rather than path, only one `report-issue` may be selectable at a time.
