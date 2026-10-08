---
title: "Windsurf MCP Setup: Connect MCP Servers to Windsurf"
slug: windsurf-mcp-setup
description: "Windsurf MCP setup, step by step: find the mcp_config.json file, write the mcpServers JSON, add a real fetch MCP server, and fix 5 Cascade connection errors."
date: 2026-09-27
draft: false
categories: ["MCP"]
tags: ["windsurf", "mcp", "cascade", "ai-coding", "devin"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Where is the MCP config file in Windsurf?"
    a: "Current official docs (read September 2026) place it at ~/.config/devin/mcp_config.json on macOS and Linux, or %APPDATA%\\devin\\mcp_config.json on Windows. Older Windsurf builds and community guides reference ~/.codeium/windsurf/mcp_config.json instead. You can also open whichever file your build uses from the Cascade panel's '...' (Actions) menu via the Open MCP config file icon in the MCPs section."
  - q: "How many MCP servers and tools can Windsurf's Cascade use?"
    a: "There is no published server count limit, but Cascade has a hard limit of 100 total tools at any given time across all configured servers, according to the official docs. If your tool list looks truncated, disable whole servers with the toggle in the MCPs section, or disable individual tools with a disabledTools array in mcp_config.json."
  - q: "Do I need to restart Windsurf after editing mcp_config.json?"
    a: "Yes. Windsurf does not hot-reload the file. Fully quit the app (Cmd+Q on macOS, Alt+F4 on Windows), relaunch it, then open the Cascade panel. MCP servers initialize when your first Cascade conversation starts, so begin a chat before checking the MCPs section."
  - q: "What is the difference between stdio and serverUrl entries in mcp_config.json?"
    a: "Entries with command and args run a local server process over stdio. Entries with serverUrl (or url) connect to a remote server over Streamable HTTP or SSE. For HTTP servers the URL should look like https://<your-server-url>/mcp. OAuth is supported for every transport type."
  - q: "Can I keep API keys out of the Windsurf MCP config file?"
    a: "Yes. The official docs support config interpolation in the command, args, env, serverUrl, url, and headers fields: ${env:VAR_NAME} is replaced with the value of an environment variable, and ${file:/path/to/file} is replaced with the trimmed contents of a file. Use this for tokens instead of hardcoding secrets."
  - q: "Is Windsurf's MCP setup the same as Cursor's?"
    a: "The JSON shape is nearly identical, which is handy if you use both editors: both use a top-level mcpServers key with command, args, and env for local servers. The config file location and how each editor exposes MCP controls differ. See our guide on adding an MCP server to Cursor for the side-by-side details."
---

## Introduction

Windsurf's Cascade agent becomes dramatically more useful once you connect [MCP](https://modelcontextprotocol.io) servers: instead of only seeing your local files, Cascade can fetch web pages, query databases, and call external APIs through tools that MCP servers provide. This tutorial walks you through the complete Windsurf MCP setup, finding the right config file, writing valid JSON, adding a real working server, and fixing the errors that trip up most first-time setups. It is written for developers who already use Windsurf (or the newer Devin Desktop builds) and are comfortable editing a JSON file and running a terminal command.

One thing to know up front: Windsurf's documentation has moved under the Devin umbrella after the acquisition, and the MCP docs now describe Cascade as the "legacy Cascade agent" alongside a newer Devin Local agent. The current official docs (read September 2026 at [docs.windsurf.com/windsurf/cascade/mcp](https://docs.windsurf.com/windsurf/cascade/mcp)) give a **new config file path** that differs from what most community guides still show. This tutorial follows the official docs and flags where older builds diverge, so you don't waste an hour editing a file your editor never reads.

## Quick answer

How do I set up MCP in Windsurf? Edit `~/.config/devin/mcp_config.json` (macOS/Linux) or `%APPDATA%\devin\mcp_config.json` (Windows), add your server under a top-level `mcpServers` key using `command`/`args`/`env` for local servers or `serverUrl` for remote ones, fully quit and relaunch Windsurf, then open Cascade, your servers initialize on the first conversation and appear in the MCPs section of the `...` (Actions) menu.

## Prerequisites

- Windsurf (or a current Devin Desktop build) installed and signed in, with the Cascade panel working
- Node.js 18 or newer installed (`node --version` in a terminal), because most example servers run via `npx`
- Basic comfort editing JSON, one misplaced comma invalidates the entire config file
- About 15 minutes; no API keys needed for the walkthrough example

## Step 1, Find your MCP config file

Windsurf reads all MCP configuration from a single JSON file. According to the current official documentation:

| Platform | Config file path |
|---|---|
| macOS / Linux | `~/.config/devin/mcp_config.json` (or `$XDG_CONFIG_HOME/devin/mcp_config.json` if that variable is set) |
| Windows | `%APPDATA%\devin\mcp_config.json` |

**Heads-up for existing Windsurf users:** most community guides written for earlier Windsurf builds reference `~/.codeium/windsurf/mcp_config.json` (Windows: `%USERPROFILE%\.codeium\windsurf\mcp_config.json`). If that `.codeium/windsurf` directory already exists on your machine from an older install, check which file your running build actually reads before editing, the safest way is to open it from inside the editor.

You don't have to hunt through folders. In Windsurf, click the `...` (Actions) menu in the top right of the Cascade panel, then click the **Open MCP config file** icon in the MCPs section. That opens exactly the file your build uses. If the file doesn't exist yet, create it along with its parent directory:

```bash
mkdir -p ~/.config/devin
touch ~/.config/devin/mcp_config.json
```

## Step 2, Add your first MCP server

For this walkthrough we use the official **fetch** MCP server from the Model Context Protocol reference repository, it is the simplest real server that demonstrates the whole pipeline. It runs locally via `npx`, needs no API key, and gives Cascade a `fetch` tool that downloads a web page and returns it as markdown.

Add this to your `mcp_config.json` (if the file is new, paste it as the entire contents):

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    }
  }
}
```

The schema is straightforward:

- The top-level key is always `mcpServers`.
- Each server gets a name you choose (`"fetch"` here), Cascade shows this name in the MCPs section.
- Local servers use `command`, `args`, and optionally `env`. Windsurf launches the command as a subprocess and talks to it over **stdio**.
- Remote servers skip the process entirely: give a `serverUrl` (or `url`) field instead, pointing at an HTTP endpoint. Per the official docs, the URL for HTTP servers should resemble `https://<your-server-url>/mcp`.

Windsurf supports three transports: `stdio`, **Streamable HTTP**, and **SSE**, plus OAuth for each transport type.

Here's what a remote entry looks like, using the documented secret interpolation so the token never sits in the file:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    },
    "docs-remote": {
      "serverUrl": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:DOCS_MCP_TOKEN}"
      }
    }
  }
}
```

The `${env:DOCS_MCP_TOKEN}` pattern is replaced with the value of that environment variable (an empty string if unset). There is also `${file:/path/to/file}`, which inserts the trimmed contents of a file, tilde paths like `~/secrets/key.txt` work. Interpolation is supported in the `command`, `args`, `env`, `serverUrl`, `url`, and `headers` fields.

If you use both editors, note that this JSON shape is nearly identical to the one used when [adding an MCP server to Cursor](/add-mcp-server-to-cursor/), both use a top-level `mcpServers` key with `command`, `args`, and `env` for local servers.

## Step 3, Fully quit and relaunch Windsurf

This is the step everyone skips, and it is the number-one reason "my server doesn't show up." **Windsurf does not hot-reload `mcp_config.json`.** Saving the file is not enough.

1. Fully quit Windsurf, `Cmd+Q` on macOS, `Alt+F4` on Windows. Closing the window is not the same as quitting.
2. Relaunch Windsurf.
3. Open the Cascade panel and start a conversation. MCP servers initialize when the first Cascade conversation begins, not at app launch.

## Step 4, Verify the server is connected in Cascade

Open the `...` (Actions) menu in the top right of the Cascade panel and look at the **MCPs section**. The official docs say this section lists your configured servers and how many tools each one has enabled, this is your source of truth.

What to look for:

- Your server name (`fetch`) appears in the list.
- A **green dot** next to the server name means the process is alive and connected. Community guides consistently report a **red dot** means the server crashed at startup, if you see red, jump to the troubleshooting section.
- A toggle next to each server lets you enable or disable it without editing the file.

Now test it end to end. In a Cascade conversation, type something the fetch tool must handle:

> Fetch https://modelcontextprotocol.io and summarize what MCP is in two sentences.

If Cascade calls the `fetch` tool and returns a summary, your Windsurf MCP setup is working. You can also ask "What MCP tools do you have?" and Cascade will list them.

## Step 5, Manage your tool budget

Cascade has a limit of **100 total tools** available at any given time across all configured MCP servers, per the official docs. A handful of servers with many tools each can hit that ceiling fast, and when it does the tool list gets truncated, servers silently stop contributing tools.

Two controls, both documented:

- **Toggle servers on/off** in the MCPs section of the Cascade panel's `...` (Actions) menu for a quick fix.
- **Disable individual tools** by listing their names in the server's `disabledTools` array in `mcp_config.json`:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"],
      "disabledTools": []
    }
  }
}
```

Add the tool names you never use (Cascade shows the names in the MCPs section) to keep the count under 100. This is also how teams tame the limit when many shared servers are configured.

## Troubleshooting

### 1. The server doesn't appear after I save the config

**Cause:** Windsurf never re-read the file. It does not watch `mcp_config.json` for changes, and MCP servers initialize lazily on the first Cascade conversation, several community setup guides (e.g. the Palinode MCP install recipes) document both behaviors.

**Fix:** Fully quit Windsurf (`Cmd+Q` / `Alt+F4`), relaunch, open the Cascade panel, and start a conversation. Then check the MCPs section of the `...` (Actions) menu. If the server still isn't listed, re-check that you edited the file your build actually reads (see Step 1, old vs. new paths).

### 2. Red dot next to the server, it crashes at startup

**Cause:** The server process exits immediately. The most common specific cause, documented in MCP server troubleshooting guides, is that Windsurf launches server processes with a much more restricted `PATH` than your login shell, so `npx` or `node` resolves fine in your terminal but is not found by Windsurf.

**Fix:** Use an absolute path in the `command` field. Find yours first:

```bash
which npx
```

Then use the result, for example on macOS with Homebrew:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    }
  }
}
```

Also verify the key casing is exactly `mcpServers` (camelCase) and restart Windsurf after the change. Windsurf's logs (community guides for the Codeium-era builds point to `~/.codeium/windsurf/logs`) can show the server's stderr if it still fails.

### 3. Invalid JSON breaks every server, not just the new one

**Cause:** The config file is parsed as a whole. A missing comma, an extra bracket, or a trailing comma (illegal in JSON) anywhere in `mcp_config.json` invalidates the entire file, so even previously working servers disappear. This is the most reported "server not appearing" cause in server-side troubleshooting docs (e.g. the Devopness Windsurf guide).

**Fix:** Paste the file into a JSON linter (jsonlint.com) before saving, or validate locally:

```bash
python3 -m json.tool ~/.config/devin/mcp_config.json > /dev/null && echo "valid JSON"
```

Remember: `env` values must be strings, wrap numbers in quotes.

### 4. Tools are truncated, "too many tools" behavior

**Cause:** You hit Cascade's 100-tool limit. The official docs state the cap explicitly; community recipes add that with several servers registered, the tool list may be truncated without an obvious error.

**Fix:** Open the MCPs section of the Cascade panel's `...` (Actions) menu, it shows each server's enabled tool count. Toggle off servers you don't need right now, or add a `disabledTools` array to slim down the noisiest servers (see Step 5). Keep the total under 100.

### 5. A remote HTTP server won't connect

**Cause:** Usually one of three things: the field is misspelled (`url` vs `serverUrl`, the official docs accept both but show `serverUrl`, and some community recipes warn that misspelling silently breaks the connection), the endpoint path is wrong (per the official docs, HTTP endpoints should resemble `https://<your-server-url>/mcp`), or the server simply isn't reachable.

**Fix:** Confirm the field is `serverUrl`, confirm the URL ends in `/mcp` (or whatever path your server documents), and test reachability from your terminal:

```bash
curl -i https://mcp.example.com/mcp
```

If curl can't reach it, Windsurf can't either, fix the network/firewall issue first. For authenticated servers, double-check the `Authorization` header and that any `${env:...}` variable is actually set in the environment Windsurf inherits.

## Conclusion

That is the complete Windsurf MCP setup: locate the config file (current official path `~/.config/devin/mcp_config.json`, with older builds using `~/.codeium/windsurf/mcp_config.json`), add servers under `mcpServers` using `command`/`args`/`env` for local stdio servers or `serverUrl` for remote HTTP ones, fully quit and relaunch, then verify in the Cascade panel's MCPs section. The fetch server walkthrough gives you a working baseline you can extend with database, GitHub, or browser MCP servers from the official MCP server reference repository.

Want to understand what actually happens under the hood? Our [MCP server tutorial](/mcp-server-tutorial/) builds a working server from scratch and shows the real protocol messages flowing between client and server.

A good next step is to compare editors: follow our guide to [adding an MCP server to Cursor](/add-mcp-server-to-cursor/) and notice how the same `mcpServers` JSON moves between the two, or, if you also use Anthropic's standalone app, our guide to [connecting an MCP server to Claude Desktop](/connect-mcp-server-to-claude-desktop/) covers its per-OS config paths.
