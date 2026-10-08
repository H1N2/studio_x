---
title: "How to Add an MCP Server to Cursor"
slug: "add-mcp-server-to-cursor"
description: "Learn how to add an MCP server to Cursor with the exact mcp.json config, verified from official docs, plus three real fixes for 'failed to connect' errors."
date: 2026-09-27
draft: false
categories: ["MCP"]
tags: ["mcp", "cursor", "model-context-protocol", "ai-agents", "developer-tools"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Where is Cursor's MCP config file?"
    a: "Cursor reads two locations: .cursor/mcp.json in your project root (project-specific, can be version-controlled) and ~/.cursor/mcp.json in your home directory (global, applies to all workspaces). Both files are loaded and merged; the project-level file takes precedence when keys conflict."
  - q: "What is the JSON format for adding an MCP server to Cursor?"
    a: "A top-level mcpServers object, where each key is a server name and each value defines the transport: stdio servers use command plus args and an optional env block; SSE/Streamable HTTP servers use url plus optional headers. Cursor uses the same format as Claude Desktop, so configs are portable between the two."
  - q: "How do I know my MCP server connected in Cursor?"
    a: "Open Cursor Settings and go to the MCP page. Each server appears in the list with a status dot, green means connected, red means it failed to start. Click a server to expand its tool list; those tools then appear under Available Tools for the Agent to use."
  - q: "Why does my MCP server show 'Failed to create client' in Cursor?"
    a: "On Windows this almost always means Cursor can't find npx because the GUI app inherits a minimal PATH. Fix it by using cmd /c as the command with npx in the args, or by pointing command at the full path of npx or node. Always test the command in a terminal first."
  - q: "Do I need to restart Cursor after editing mcp.json?"
    a: "Yes, Cursor reads the config at startup. After editing mcp.json, reload the window or fully restart Cursor, then check Settings → MCP for the status dot. If the server still doesn't appear, your JSON is probably invalid; validate it before anything else."
---

## Introduction

Adding an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server to Cursor gives the AI agent access to tools outside your codebase, a filesystem reader, a database, a web fetcher, your GitHub issues. This guide walks you through the full process using a real example server, verified against the [official Cursor docs](https://cursor.com/docs), and ends with a test you can run in Agent chat to prove it works.

## Quick answer

To add an MCP server to Cursor, create a `.cursor/mcp.json` file in your project (or `~/.cursor/mcp.json` for all projects) with a top-level `{"mcpServers": {...}}` object describing each server, then restart Cursor and confirm the green status dot on Cursor Settings → MCP. The steps below show the exact JSON and how to verify the connection.

## Prerequisites

- **Cursor** installed and updated to a recent version (MCP support is built in, no extension needed).
- **Node.js 18+** with `npx` on your PATH if you run npm-published servers (check with `node --version` and `npx --version`).
- **A project folder** open in Cursor (for the project-level config; skip this if you only want a global config).
- **Comfort editing JSON**, one trailing comma breaks everything.

## Step 1: Choose project-level or global config

Cursor loads MCP configuration from two locations, and it loads *both*, merging them. From the official docs:

| Scope | Path | Use when |
|---|---|---|
| **Project** | `.cursor/mcp.json` in your project root | The server belongs to one project (e.g. a database for your app). Safe to version-control, but keep secrets out of it. |
| **Global** | `~/.cursor/mcp.json` in your home directory | You want the server everywhere (e.g. web search, GitHub tools). On Windows: `C:\Users\<You>\.cursor\mcp.json`. |

If the same server name appears in both files, the **project-level entry wins**. My rule of thumb: put personal, always-on servers in global; put anything project-specific or team-shared in the project file. For this walkthrough I'll use the project-level file.

## Step 2: Create the mcp.json file

Open a terminal at your project root and create the file:

```bash
mkdir -p .cursor
touch .cursor/mcp.json
```

Or, if you prefer the UI route: open the Command Palette (`Cmd+Shift+P` on Mac, `Ctrl+Shift+P` on Windows/Linux), search for **"MCP"**, and pick **View: Open MCP Settings**, then add the server from the settings page. Both routes edit the same JSON underneath; the file route is easier to document and version-control, so that's what we'll use.

## Step 3: Add a real MCP server, the official filesystem server

For the walkthrough we'll use the **filesystem server** from the official `modelcontextprotocol/servers` repository. It's the canonical reference server, needs no API key, and its tool calls are easy to verify (`read_file`, `write_file`, `list_directory`, `move_file`, `search_files`).

Add this to your `.cursor/mcp.json`, replacing `/Users/you/projects/myapp` with a directory you actually want the agent to access:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/you/projects/myapp"
      ]
    }
  }
}
```

A few things to note about this snippet:

- **`command` + `args`** = the **stdio** transport. Cursor spawns this process itself and talks to it over standard input/output. Local servers you run via a CLI command are always stdio.
- **`-y`** auto-accepts the npm install prompt so Cursor doesn't hang waiting for input it can't provide.
- The **last arg is the allowed directory**. The filesystem server is sandboxed to the directories you list here, it cannot touch anything else. Give it the narrowest path you need; don't pass `/` or your whole home folder.

> ⚠️ **Security note:** MCP servers run with your user privileges. A filesystem server gives the agent real read/write access to every path you list. Only allow directories you trust, and review tool calls when the agent proposes file changes.

If you need a secret (say, a GitHub token for the official `server-github`), pass it through the **`env`** block, it becomes environment variables for the server process:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

Never commit real tokens to a project-level `.cursor/mcp.json`, Cursor also supports `${env:NAME}` variable interpolation, so you can reference secrets from your shell environment instead of hardcoding them.

## Step 4: Verify the server connected

1. **Restart Cursor** (or reload the window) so it picks up the new config.
2. Open **Cursor Settings → MCP**. You should see your server listed, e.g. `filesystem`, with a **green status dot** next to it.
3. Click the server name to **expand its tool list**. For the filesystem server you should see `read_file`, `write_file`, `list_directory`, `move_file`, and `search_files`. A red dot here means the server failed to start, jump to Troubleshooting below.
4. The tools are now listed under **Available Tools** for the Composer/Agent, which will use them automatically when relevant.

## Step 5: Run a real test in Agent chat

The fastest end-to-end proof: ask the agent something only the new tool can answer. In Agent chat, type:

> List all files in the project root using the filesystem MCP tools, then tell me how many there are.

Watch the chat, you should see the agent call `list_directory` and report back real results from your allowed path. To prompt tool usage intentionally, you can name the tool directly:

> Use the `read_file` tool to show me the first 20 lines of package.json.

If the agent answers from its own knowledge instead of calling the tool, tell it explicitly to "use the filesystem MCP tool", that phrasing works reliably.

## Step 6 (optional): Connect an SSE or HTTP server

Some servers don't run as a local process, they live at a URL. Cursor supports **stdio**, **SSE**, and **Streamable HTTP** transports. For a remote server, the config uses `url` instead of `command`:

```json
{
  "mcpServers": {
    "my-remote-server": {
      "url": "http://localhost:8001/sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

The `headers` block is how you authenticate to remote servers. After adding it, restart Cursor and check Settings → MCP for the green dot exactly as before. (If you're moving the same servers between editors: the format matches Claude Desktop's config, and the steps differ mainly in file location, see our guide to [connecting the same MCP server to Claude Desktop](/connect-mcp-server-to-claude-desktop/). The [Windsurf MCP setup](/windsurf-mcp-setup/) uses the identical `mcpServers` schema, so the JSON above ports over with no changes.)

## Troubleshooting

### 1. "Failed to create client" / red status dot on Windows

**Symptom:** The server stays red in Settings → MCP, and logs or forum threads mention "Failed to create client", even though the same `npx` command works in your terminal.

**Cause:** When you launch Cursor from the Start menu or Dock, it inherits a minimal system PATH that often doesn't include Node.js. The `npx` binary exists, but Cursor's spawned process can't find it.

**Fix:** Wrap the call in `cmd /c` on Windows so the command resolves through the shell:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Users\\you\\projects\\myapp"
      ]
    }
  }
}
```

(Use double backslashes `\\` for Windows paths in JSON.) On macOS/Linux, the equivalent fix is to launch Cursor from a terminal once, or set `command` to the **full path** of npx, find it with `which npx` and paste the absolute path.

### 2. Server exits immediately, no tools, no useful error

**Symptom:** Red dot, no tool list, and Cursor's output gives you little to work with.

**Cause:** Almost always a bad `command` or a relative `args` path. If the process crashes on startup, Cursor has nothing to show.

**Fix:** Reproduce the failure outside Cursor first. Run the exact command in your terminal:

```bash
npx -y @modelcontextprotocol/server-filesystem /Users/you/projects/myapp
```

If that prints errors or exits, fix them there, wrong path, missing Node version, npm permission issues, then copy the working command back into `mcp.json`. Two specific checks:

- Paths in `args` (including any `cwd`) **must be absolute**, not relative.
- There must be **no interactive prompts** in the startup path, the `-y` flag on npx exists for exactly this reason.

### 3. Edited mcp.json but nothing changes

**Symptom:** You fixed the JSON, restarted, and the old (broken) config still shows, or nothing new appears at all.

**Cause & fix, in order:**

1. **Invalid JSON is the #1 culprit.** Trailing commas, missing quotes, a stray comment. Validate the file before anything else: paste it into a JSON linter, or run `python3 -m json.tool .cursor/mcp.json`, if that errors, your file is broken.
2. **You edited the wrong file.** Remember there are two configs and they merge: a broken entry in `~/.cursor/mcp.json` can mask a fixed `.cursor/mcp.json` entry (or vice versa). Check both.
3. **Cursor only reads config at startup.** Save the file, then fully reload the window or quit and relaunch Cursor, the settings page doesn't hot-reload `mcp.json`.

### 4. SSE/HTTP server fails to connect

**Symptom:** The server shows red, or the tool list never loads, while stdio servers work fine.

**Cause:** URL mismatch or auth failure. Two common variants:

- **Wrong endpoint path.** Some servers expect `/sse`, others `/mcp` (streamable HTTP), and the paths are not interchangeable. Check the server's own docs for the exact path.
- **Missing or expired auth.** Test the endpoint outside Cursor with curl:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8001/sse
```

**Fix:** Correct the `url` and `headers` in `mcp.json`, restart Cursor, and recheck the status dot. If curl gets a 401, the problem is your key, not Cursor.

## Conclusion

You now know how to add an MCP server to Cursor end to end: pick the right config scope, write the `mcpServers` JSON, verify the green dot in Settings → MCP, and prove it works with a real tool call in Agent chat. The filesystem server is a great first server, but the same pattern, stdio via `command`, remote via `url`, covers nearly every MCP server you'll ever add.

Next, if you use other AI editors, see our guides on [connecting the same MCP server to Claude Desktop](/connect-mcp-server-to-claude-desktop/) and the [Windsurf MCP setup](/windsurf-mcp-setup/), the JSON you just wrote transfers almost unchanged. For the full picture of what MCP servers are and how the protocol works under the hood, see our [MCP server tutorial](/mcp-server-tutorial/).
