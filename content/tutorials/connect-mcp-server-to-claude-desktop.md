---
title: "How to Connect an MCP Server to Claude Desktop (Step-by-Step)"
slug: "connect-mcp-server-to-claude-desktop"
description: "How to connect an MCP server to Claude Desktop: exact config paths for macOS and Windows, the mcpServers JSON schema, and fixes for the 3 most common errors."
date: 2026-09-27
draft: false
categories: ["MCP"]
tags: ["MCP", "Claude Desktop", "model context protocol", "filesystem server", "AI automation"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Where is the Claude Desktop MCP config file?"
    a: "On macOS it is ~/Library/Application Support/Claude/claude_desktop_config.json, on Windows %APPDATA%\\Claude\\claude_desktop_config.json, and on community Linux builds ~/.config/Claude/claude_desktop_config.json. The easiest way to open it is Claude Desktop's Settings → Developer → Edit Config button, which creates the file if it does not exist yet."
  - q: "Do I need to restart Claude Desktop after editing the config?"
    a: "Yes, and a full quit is required. Claude Desktop reads the config file only once, at launch. On macOS press Cmd+Q (or Claude → Quit Claude); on Windows quit from the system tray icon. Just closing the chat window leaves the app running in the background and your changes are silently ignored."
  - q: "Why does my MCP server show as 'Failed' in Claude Desktop?"
    a: "The most common cause is a PATH problem: Claude Desktop does not inherit your terminal's PATH, so commands installed via nvm or Homebrew are invisible to it. Check ~/Library/Logs/Claude/mcp-server-<name>.log (macOS) or %APPDATA%\\Claude\\logs (Windows) for the real error, then replace \"npx\" in your config with the full path from `which npx`."
  - q: "Can I connect more than one MCP server to Claude Desktop?"
    a: "Yes. Add each server as another entry under the same mcpServers object in claude_desktop_config.json, separated by commas. Each gets its own name key, command, and args. Restart Claude Desktop once after all edits."
  - q: "Is it safe to give Claude access to my filesystem?"
    a: "It is safe as long as you scope it deliberately. The official filesystem server can only touch the directories you list in the config's args, it cannot see anything else. List only the folders you actually need (e.g. a project folder), never your entire home directory, and remember Claude still asks for approval before writing."
  - q: "Does Claude Desktop support remote (HTTP) MCP servers?"
    a: "Claude Desktop natively speaks to local servers over stdio. To reach a remote HTTP MCP endpoint, route it through a local bridge: set the config command to npx with args [\"-y\", \"mcp-remote\", \"https://your-server/mcp\"]. The bridge runs locally and translates stdio to HTTP for Claude Desktop."
---

## Introduction

Connecting an MCP server to Claude Desktop turns Claude from a chatbot that only talks about files into an assistant that can actually work with them, reading folders, editing documents, querying databases, or calling APIs through tools you install. This guide is for macOS and Windows users who already have [Claude Desktop](https://claude.ai/download) installed and want a server up and running in about ten minutes. You'll add the official filesystem MCP server, the canonical first example from the [Model Context Protocol documentation](https://modelcontextprotocol.io), verify that Claude can see its tools, and learn the fixes for the three connection problems that account for nearly every "my server doesn't show up" report.

## Quick answer

Open Claude Desktop's **Settings → Developer → Edit Config** to open `claude_desktop_config.json`. Add your server under the `mcpServers` key with a `command` and `args`, save the file, then quit and relaunch Claude Desktop. Verify in Settings → Developer, where the Local MCP servers panel lists your server.

## Prerequisites

- **Claude Desktop installed** from claude.ai/download (macOS and Windows are supported; Linux is only covered by unofficial community builds).
- **Node.js 20 or newer.** The example server runs through `npx`. Verify with `node --version` in a terminal, you should see something like `v22.14.0`. If Node is missing, install it from nodejs.org.
- **About 10 minutes** and any plain-text editor. No coding required.
- **A folder you're comfortable letting Claude read**, such as your Desktop or a project folder. You'll point the server at it in Step 3.

## The 30-second mental model

Claude Desktop doesn't reach MCP servers over the network. It reads **one JSON file at startup**, `claude_desktop_config.json`, and launches each listed server as a local subprocess, talking to it over stdio (standard input/output). That single fact explains the two biggest gotchas in this guide: you must **fully quit and relaunch** Claude Desktop after editing the config (it reads the file only at launch), and the command in your config must be findable in the **PATH that Claude Desktop itself sees**, which is not the same PATH your terminal sees. Keep that in mind and the troubleshooting section will make immediate sense.

## Step 1, Confirm Node.js and npx work

Open a terminal and run:

```bash
node --version
which npx
```

On macOS you should see output like:

```
v22.14.0
/opt/homebrew/bin/npx
```

Note the exact path that `which npx` prints, `/opt/homebrew/bin/npx` on Apple-silicon Macs with Homebrew, `/usr/local/bin/npx` on Intel Macs and many Linux boxes. You'll need it if you hit the PATH problem in the troubleshooting section, so jot it down now. On Windows, open Command Prompt and run `where npx`; the official Node.js installer from nodejs.org registers it for you.

If `node --version` reports anything older than v20, update Node first, old `npx` versions don't support the `-y` flag the config below relies on, and Claude Desktop fails to start the server with a wall of npx usage text.

## Step 2, Open the MCP config file from Claude Desktop

You don't need to hunt for the file manually. In Claude Desktop:

1. Open **Settings** (via the Claude menu in the menu bar on macOS, or the app menu on Windows).
2. Go to the **Developer** tab in the left sidebar.
3. Click **Edit Config**.

This opens `claude_desktop_config.json` in your file system, creating it if it doesn't exist yet. For reference, the file lives at:

| OS | Config file location |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux (community builds) | `~/.config/Claude/claude_desktop_config.json` |

If the file already contains settings (for example from a previous server), **add** your new server to the existing `mcpServers` object rather than replacing the whole file.

## Step 3, Add the filesystem server entry

Open the config file in a text editor and paste the entry for your OS. On macOS:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yourname/Desktop",
        "/Users/yourname/Documents/projects"
      ]
    }
  }
}
```

On Windows (note the doubled backslashes, JSON requires escaped backslashes):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Users\\yourname\\Desktop",
        "C:\\Users\\yourname\\Documents\\projects"
      ]
    }
  }
}
```

Replace the paths with real folders on your machine. What each field means:

- **`filesystem`**, the server's display name. It's arbitrary; pick anything descriptive.
- **`command`**, the program Claude Desktop launches. `npx` is the Node.js package runner.
- **`-y`**, tells npx to download the package without asking. (First launch takes a few seconds while it downloads.)
- **`@modelcontextprotocol/server-filesystem`**, the official filesystem MCP server package from the Model Context Protocol project.
- **The remaining args**, the folders Claude is allowed to access. This list is a permission boundary: the server cannot read or write anything outside these directories.

A word of caution from our side: scope these paths tightly. Pointing the server at a project folder or your Desktop is sensible; pointing it at your entire home directory hands Claude the keys to everything, including SSH keys and browser profiles. Start narrow, you can always add folders later.

## Step 4, Save, then fully quit and relaunch Claude Desktop

Save the config file, then **quit Claude Desktop completely**. Closing the chat window is not enough, the app keeps running in the background and never re-reads the config.

- **macOS:** press **Cmd+Q**, or choose **Claude → Quit Claude** from the menu bar.
- **Windows:** right-click the Claude icon in the system tray and choose **Quit**.

Then reopen Claude Desktop. This is the step people skip most often, and it's responsible for the majority of "I edited the config and nothing happened" confusion.

## Step 5, Confirm the server connected

Go back to **Settings → Developer**. The **Local MCP servers** panel now lists `filesystem` along with its command, arguments, and current state. A healthy server shows no error; a broken one shows **Failed**, in which case jump to the troubleshooting section, don't guess, the logs will tell you the exact cause.

Then test it in chat. Ask Claude something like:

> List the files on my Desktop.

If the server is connected, Claude will call the filesystem server's `list_directory` tool (it may ask for your approval first) and answer from the actual contents. You can also ask "What tools do you have access to?", you should see the filesystem tools (`list_directory`, `read_file`, `write_file`, `search_files`, and others) in the answer.

If you'd rather use an editor-based assistant than the desktop app, the same MCP protocol works elsewhere too, see our guides on [adding an MCP server to Cursor](/add-mcp-server-to-cursor/) and the [Windsurf MCP setup](/windsurf-mcp-setup/).

## Step 6, Try a real task

To get a feel for what MCP unlocks, give Claude a task that crosses the chat/computer boundary:

> Search my project notes folder for every mention of "launch checklist" and summarize what still needs doing.

Watch what happens: Claude uses `search_files` across the allowed directories, then `read_file` on the matches, and synthesizes an answer, a task that previously required you to open each file yourself. Notice that Claude asks for approval before writes; reads are generally silent, which is another reason to keep the allowed directories narrow.

## What to connect next

The pattern is identical for every stdio MCP server, only the command and args change. Two common follow-ups:

- **SQLite server** (`@modelcontextprotocol/server-sqlite`) lets Claude query a database file: `"args": ["-y", "@modelcontextprotocol/server-sqlite", "/path/to/database.db"]`.
- **Servers that need API keys** add an `env` object: `"env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }`. You can also reference your shell's environment with `"${env:MY_TOKEN}"` instead of hardcoding secrets into the file.

Each new entry goes under the same `mcpServers` object, separated by commas. After editing, repeat Step 4: full quit, relaunch, verify in the Developer panel.

## Troubleshooting

### 1. Server shows "Failed", `npx: command not found` in the logs

**This is the #1 MCP setup problem on macOS, and it's a PATH issue.** Claude Desktop is a GUI app: it doesn't source your `~/.zshrc` or `~/.bashrc`, so tools installed via nvm, Homebrew, or Volta are invisible to it even though they work fine in your terminal.

**How to confirm:** open the server's log and look for the spawn error:

```bash
# macOS
tail -n 40 ~/Library/Logs/Claude/mcp-server-filesystem.log

# Windows (PowerShell)
Get-Content "$env:APPDATA\Claude\logs\mcp-server-filesystem.log" -Tail 40
```

If the log says `command not found` (or shows the wrong `npx` path in `mcp.log`, which prints the exact `npx` path Claude chose), this is your problem.

**Fix, use the absolute path to npx.** Replace `"command": "npx"` with the path you noted in Step 1:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/yourname/Desktop"]
    }
  }
}
```

On Windows, where `npx` is a `.cmd` shim that needs a shell, the reliable fix is the `cmd` wrapper:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\yourname\\Desktop"]
    }
  }
}
```

Then fully quit and relaunch Claude Desktop (Step 4).

### 2. I edited the config but nothing changed

**Cause:** Claude Desktop reads `claude_desktop_config.json` exactly once, at launch. Editing it while the app is running, or merely closing the chat window, changes nothing. This also applies when you add a second server or fix a typo: every config edit needs a full restart.

**Fix:** on macOS press **Cmd+Q** (or Claude → Quit Claude); on Windows quit from the system tray icon. Then reopen and check Settings → Developer → Local MCP servers. If the panel now lists your server, the config was fine all along, it just hadn't been loaded.

### 3. The config file seems to be ignored entirely

**Cause:** invalid JSON. A single trailing comma, a missing closing brace, or Windows paths written with single backslashes (`C:\Users\...`) silently breaks the whole file, Claude Desktop won't load any server and won't show a helpful error in the UI.

**Fix:** validate the file before restarting:

```bash
# macOS / Linux
python3 -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

If the command prints your config back formatted, the JSON is valid. If it throws an error, it points at the exact line. Common culprits when adding a second server: a missing comma between server entries, or a trailing comma after the last entry. Also double-check Windows paths use `\\` in JSON.

### 4. Log shows a wall of npx usage text, then the server exits

**Cause:** the `npx` that Claude Desktop found is too old to understand the `-y` flag. Instead of downloading the package, it prints its help text and exits, so the server dies before the MCP handshake completes.

**Fix:** install Node.js 20 or newer from nodejs.org (the system-wide installer, not just nvm), then point the config at the new `npx` with an absolute path as in problem 1, e.g. `"command": "/usr/local/bin/npx"`. Verify with `/usr/local/bin/npx --version` first. Full quit and relaunch after the change.

## Conclusion

That's the whole process: install Node, open the config from Settings → Developer → Edit Config, paste the filesystem server entry under `mcpServers` with the folders you want Claude to access, save, fully quit, relaunch, and confirm in the Local MCP servers panel. If something fails, the logs at `~/Library/Logs/Claude/` (macOS) or `%APPDATA%\Claude\logs` (Windows) name the exact cause, work from there instead of guessing.

Once you're comfortable with the filesystem server, the natural next step is connecting servers that need API keys, like GitHub or a database, the config pattern is identical, just with an `env` block. And if you use a code editor as your AI assistant, [our guide to adding an MCP server to Cursor](/add-mcp-server-to-cursor/) covers the same protocol in that client. Curious what happens under the hood when a client talks to a server? Our [MCP server tutorial](/mcp-server-tutorial/) builds one from scratch and shows the real protocol messages. For more hands-on walkthroughs in this niche, browse [all ToolPilot tutorials](/tutorials/).
