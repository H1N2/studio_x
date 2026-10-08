---
title: "Claude Code MCP Setup: Connect Any MCP Server in Minutes"
slug: "claude-code-mcp-setup"
date: 2026-09-28T02:00:00+08:00
draft: false
description: "Set up MCP servers in Claude Code: the three config scopes (local, project, user), the exact claude mcp add commands for HTTP and stdio servers, and fixes for the 5 most common failures. Tested on Claude Code 2.1.283."
categories: ["mcp"]
tags: ["claude-code", "mcp", "anthropic", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "How do I add an MCP server to Claude Code?"
    a: "Run `claude mcp add` from your terminal. For a remote server: `claude mcp add --transport http notion https://mcp.notion.com/mcp`. For a local server: `claude mcp add myserver -- npx -y @example/mcp-server`. Everything after `--` is passed to the server's command untouched."
  - q: "Where does Claude Code store MCP server configuration?"
    a: "Three places, one per scope: local scope (default) and user scope both live in `~/.claude.json`, with local entries nested under your project path; project scope lives in `.mcp.json` at your repository root and is meant to be committed to git."
  - q: "What is the difference between local, project, and user MCP scope in Claude Code?"
    a: "Local scope is private to you in the current project (default). Project scope is stored in `.mcp.json` and shared with your team through version control, but Claude Code asks for approval before using those servers. User scope is private to you but available in every project on your machine."
  - q: "Why does Claude Code say my MCP server has a url but no type?"
    a: "Claude Code reads any JSON entry without a `type` field as a stdio server, so a remote entry with only a `url` is skipped with the warning: 'has a \"url\" but no \"type\"; add \"type\": \"http\"'. Fix it by adding `\"type\": \"http\"` (or \"sse\" / \"ws\") to the entry."
  - q: "Do I need to restart Claude Code after changing MCP config?"
    a: "After manual edits to `.mcp.json` or `~/.claude.json`, yes, restart the session so the new config loads. Changes made with `claude mcp add` or `claude mcp remove` take effect in new sessions; check status any time with the `/mcp` command."
  - q: "Can I import my Claude Desktop MCP servers into Claude Code?"
    a: "Yes. Run `claude mcp add-from-claude-desktop` and Claude Code imports the servers from your Claude Desktop config. Compare the setup differences in our guide to connecting an MCP server to Claude Desktop."
---

## Introduction

Claude Code is Anthropic's terminal-native coding agent, and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) is how you plug it into everything outside the terminal: issue trackers, databases, design tools, monitoring dashboards. This tutorial sets up MCP servers in Claude Code from scratch, picking the right scope, writing the exact CLI commands, and verifying the connection. Every command below was run against a real Claude Code 2.1.283 install on 2026-09-28, and the transcripts are the actual output.

## Quick answer

Run `claude mcp add` to register an MCP server: use `--transport http` with a URL for remote servers (e.g. `claude mcp add --transport http notion https://mcp.notion.com/mcp`), or put a launch command after `--` for local stdio servers (e.g. `claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem ~/projects`). Add `--scope user` for all projects or `--scope project` to share via `.mcp.json`; verify with `claude mcp list` or the `/mcp` command.

## Why MCP on Claude Code: the numbers

The Model Context Protocol ecosystem is enormous now. Community trackers reported over 10,000 active MCP servers in 2026 (via Smithery.ai), and the official `@modelcontextprotocol/sdk` npm package had crossed 20 million downloads as of February 2026 (npmjs.com figures, compiled in the Athanor ecosystem survey). That matters for a coding agent: connecting Claude Code to MCP is how it reaches the hundreds of tools where your work actually lives.

Anthropic's official Claude Code documentation frames it plainly:

> "Claude Code can connect to hundreds of external tools and data sources through the Model Context Protocol (MCP), an open source standard for AI-tool integrations. MCP servers give Claude Code access to your tools, databases, and APIs.", [Claude Code MCP docs](https://code.claude.com/docs/en/mcp.md)

And a rule of thumb from the same page shapes the whole setup below: "Connect a server when you find yourself copying data into chat from another tool, like an issue tracker or a monitoring dashboard. Once connected, Claude can read and act on that system directly instead of working from what you paste."

One warning before we touch anything, also straight from the docs:

> "Verify you trust each server before connecting it. Servers that fetch external content can expose you to [prompt injection risk](https://code.claude.com/docs/en/mcp.md)."

An MCP server runs code on your machine (stdio) or receives your requests (HTTP), treat server selection like installing software. If you want the protocol fundamentals first, our [MCP server tutorial](/mcp-server-tutorial/) walks through the JSON-RPC traces a server actually speaks; the client-side configs here mirror the ones in our [Cursor](/add-mcp-server-to-cursor/), [Windsurf](/windsurf-mcp-setup/), and [Claude Desktop](/connect-mcp-server-to-claude-desktop/) guides.

## Prerequisites

- **Claude Code installed**: `npm install -g @anthropic-ai/claude-code` (I tested on **2.1.283**; the CLI works without logging in for MCP config, `claude mcp` commands only edit local config files).
- **Node.js 18+** if you plan to add stdio servers distributed via npm (`npx -y ...` is the standard launcher).
- A terminal session opened in a project directory (the default `local` scope is per-project).

## Step 1, Understand the three scopes before you add anything

Claude Code reads MCP config at three scopes. Choosing the right one up front saves you from moving servers around later:

| Scope | Flag | Stored in | Who sees it |
|---|---|---|---|
| **local** (default) | `--scope local` | `~/.claude.json`, under your project path | Only you, current project |
| **project** | `--scope project` | `.mcp.json` at project root | Everyone (commit it to git) |
| **user** | `--scope user` | `~/.claude.json`, top level | Only you, all your projects |

The mental model: **local** for experiments and anything holding a personal secret tied to one project; **project** for team tools everyone should have (a shared Postgres or Sentry server); **user** for personal utilities you want everywhere (filesystem, memory, GitHub).

One security nuance worth knowing: for project-scoped servers, Claude Code prompts for your approval before using servers declared in `.mcp.json`, a `.mcp.json` you pulled from a teammate's branch can't silently hand your agent a malicious tool. You can reset those approvals with `claude mcp reset-project-choices`.

## Step 2, Add a local stdio server (the default case)

A stdio server runs as a local process. I'll use a real notes server from our [MCP server tutorial](/mcp-server-tutorial/) lab (a stdio server with two tools, `add_note` and `list_notes`):

```bash
claude mcp add --transport stdio notes -- node /path/to/server.mjs
```

The `--` separator is mandatory for stdio servers: everything after it is the command that starts the server, passed through untouched. Actual output from my test:

```
Added stdio MCP server notes with command: node /path/to/server.mjs to local config
File modified: /home/hatch/.claude.json [project: /home/hatch]
```

Two things to notice. First, the CLI prints a `File modified` line telling you exactly which file and project entry changed, no guessing. Second, under the hood the entry lands in `~/.claude.json` nested under `"projects"` → your project path → `"mcpServers"`:

```json
"mcpServers": {
  "notes": {
    "type": "stdio",
    "command": "node",
    "args": ["/path/to/server.mjs"],
    "env": {}
  }
}
```

Server names become part of tool names: a tool called `search` on a server named `gh` is invoked as `mcp__gh__search`. Keep names short and restricted to letters, numbers, hyphens, and underscores, keys with other characters are rejected.

## Step 3, Add a remote HTTP server (cloud services)

HTTP is the recommended transport for remote servers and the only one that supports OAuth. The syntax is `claude mcp add --transport http <name> <url>`:

```bash
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

To share one with your team, add `--scope project`, Claude Code creates or updates `.mcp.json` at your project root:

```bash
claude mcp add --transport http gh --scope project https://api.githubcopilot.com/mcp/
```

```
Added HTTP MCP server gh with URL: https://api.githubcopilot.com/mcp to project config
File modified: /home/hatch/proj/.mcp.json
```

The resulting `.mcp.json` is clean and committable:

```json
{
  "mcpServers": {
    "gh": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    }
  }
}
```

Some services still expose only the deprecated SSE transport. With Claude Code v2.1.265+, you don't need `--transport sse`: add it with `--transport http` and Claude Code tries HTTP first, then falls back to SSE automatically. Only pass `--transport sse` explicitly on older versions.

## Step 4, Add a user-scoped server (available everywhere)

For a personal utility you want in every project, scope it to `user`:

```bash
claude mcp add --scope user filesystem -- npx -y @modelcontextprotocol/server-filesystem ~/projects
```

```
Added stdio MCP server filesystem with command: npx -y @modelcontextprotocol/server-filesystem /home/user/projects to user config
File modified: /home/user/.claude.json
```

This writes a top-level `"mcpServers"` entry in `~/.claude.json` (not nested under a project). A pinned-version tip from community practice: `npx -y @scope/server` with no version resolves to latest on every session start, for servers you depend on daily, pin the version (e.g. `@modelcontextprotocol/server-filesystem@0.6.2`) so a compromised or broken future release doesn't load the next time you open a session.

## Step 5, Pass secrets safely with --env and ${VAR} expansion

Never commit secrets to `.mcp.json`. For project-scoped servers, reference environment variables and let Claude Code expand them:

```json
{
  "mcpServers": {
    "db": {
      "command": "npx",
      "args": ["-y", "@bytebase/dbhub", "--dsn", "${DB_DSN}"],
      "env": {}
    }
  }
}
```

`${VAR}` and `${VAR:-default}` are expanded from the environment at load time, so the secret never lands in the repository. For CLI-added servers, pass variables with `--env`, but note the argument-order trap the docs warn about: if the server name comes directly after `--env`, the CLI reads the name as another `KEY=value` pair and rejects it. Put at least one other option (like `--transport stdio`) between `--env` and the name:

```bash
claude mcp add --env AIRTABLE_API_KEY=<your-key> --transport stdio airtable -- npx -y airtable-mcp-server
```

I verified this works and, importantly, that secrets are protected afterward: `claude mcp get` displays stored env values as `<redacted>`, never in plain text.

For OAuth-protected remote servers you don't even need a key on the command line: after `claude mcp add --transport http <name> <url>`, run `/mcp` in a session, select the server, and sign in in the browser. Claude Code stores the token itself. For CI or headless machines, pass a static header instead: `claude mcp add --transport http secure-api https://api.example.com/mcp --header "Authorization: Bearer <your-token>"`.

## Step 6, Convert configs written for other clients

MCP servers aren't Claude Code-specific, so a server's docs may give you a Claude Desktop or Cursor config with no `claude mcp add` command. Translate the shape you have:

- **A URL** (`https://mcp.example.com/mcp`) → remote server: `claude mcp add --transport http example https://mcp.example.com/mcp`
- **A launch command** (`npx -y @example/mcp-server`) → stdio server: `claude mcp add example -- npx -y @example/mcp-server` (command goes after `--`; env vars go before it with `--env`)
- **An `mcpServers` JSON block** → pass the object *inside* `mcpServers` to `claude mcp add-json`, not the wrapper: `claude mcp add-json example '{"command":"npx","args":["-y","@example/mcp-server"]}'`

I tested `add-json` and the matching removal:

```
Added stdio MCP server jsonserver to local config
```

Two repairs are commonly needed first: an entry with a `url` but no `type` needs `"type": "http"` added (Claude Code reads a typeless entry as stdio, see Troubleshooting), and the key you pick as the server name must use only letters, numbers, hyphens, and underscores.

## Step 7, Verify and manage

Every add prints an `Added ...` line, which means the config was *written*, it doesn't prove the server *connected*. Verify with:

```bash
claude mcp list
```

Actual output from my lab (note `Checking MCP server health…` before the list):

```
Checking MCP server health…

notes: node /path/to/server.mjs - ✔ Connected
```

Statuses you'll see: `✔ Connected`, `! Needs authentication`, or `✘ Failed to connect`. A failure status means Claude Code couldn't reach that server, not that the list command broke.

For details on one server:

```bash
claude mcp get notes
```

```
notes:
  Scope: Local config (private to you in this project)
  Status: ✔ Connected
  Type: stdio
  Command: node
  Args: /path/to/server.mjs
  Environment:

To remove this server, run: claude mcp remove notes -s local
```

Removal and the rest of the lifecycle:

```bash
claude mcp remove notes -s local     # remove from a specific scope
claude mcp get filesystem            # details for one server
/mcp                                  # inside a session: interactive status view
```

Migrating from Claude Desktop? `claude mcp add-from-claude-desktop` imports your Desktop servers in one step.

## Troubleshooting

### 1. `Skipped — MCP server "x" has a "url" but no "type"`

This is the single most common failure when hand-writing `.mcp.json` or pasting configs from other clients. Claude Code reads any entry without a `type` as a stdio server, so a remote entry with only `url` gets skipped. I reproduced it: writing `{"mcpServers":{"bad":{"url":"https://mcp.example.com/mcp"}}}` produces a diagnostics block under `claude mcp list`:

```
MCP config diagnostics ⚠
[Contains warnings] Project config (shared via .mcp.json)
Location: /home/user/proj/.mcp.json
 └ [Warning] [bad] mcpServers.bad: Skipped — MCP server "bad" has a "url" but no "type"; add "type": "http" (or "sse" / "ws") to this entry
```

**Fix:** add `"type": "http"` (or `"sse"` / `"ws"`) to the entry. Note: `streamable-http` is accepted as an alias for `http` since that's the name the MCP spec itself uses.

### 2. `✘ Failed to connect` with `CONNECTION_CLOSED` for a stdio server

A stdio server is just a subprocess, if it exits instantly, Claude Code reports `CONNECTION_CLOSED: Connection closed`. I reproduced this by pointing an entry at a nonexistent file; `claude mcp get` showed the failing status and the exact command. The usual causes:

- **Wrong path or missing runtime.** Run the command yourself first: `node /path/to/server.mjs` should print JSON-RPC traffic (or at least not crash instantly) when you type `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}` into its stdin.
- **Logs on stdout.** MCP reserves stdout for the protocol; a server that `console.log`s there corrupts the JSON-RPC stream and dies. Logs must go to stderr. (We hit exactly this class of bug in our [MCP server tutorial](/mcp-server-tutorial/) lab.)
- **`npx -y` first-run downloads.** If the package isn't cached, `npx` may hang downloading on first launch; run the `npx` command once in your terminal to cache it.

### 3. Server name rejected by `claude mcp add-json`

Server names may contain only letters, numbers, hyphens, and underscores. Keys copied from other clients' configs (e.g. `"my.server"` or `"company/tools"`) are rejected, rename to something like `my-server` before importing. The server name becomes the `mcp__<server>__<tool>` prefix in tool calls, so shorter is better anyway.

### 4. Project `.mcp.json` server never activates (or asks every time)

Two separate behaviors, both by design. First, Claude Code prompts for approval before using project-scoped servers from `.mcp.json`, if you pulled a branch with a new server, expect a one-time approval. Second, if a teammate's approval choices are stale or wrong, reset them with `claude mcp reset-project-choices` and re-approve deliberately.

### 5. `claude mcp add` parses my server's flags as its own options

The classic gotcha: `claude mcp add myserver npx server --port 8080` without `--` makes Claude Code try to read `--port` as one of *its* options. Always put `--` between Claude Code's flags and the server's launch command:

```bash
claude mcp add --env KEY=value --transport stdio myserver -- python server.py --port 8080
```

Everything after `--` is passed to the server untouched. And remember the `--env` ordering trap from Step 5: keep an option between `--env` and the server name.

## FAQ

(See front matter for the full FAQ set.)

## Conclusion

Claude Code's MCP setup is three decisions: the right scope (local for experiments, project for team tools, user for personal utilities), the right transport (HTTP for remote, stdio after `--` for local), and secrets in environment variables rather than committed JSON. Once connected, verify with `claude mcp list` and manage everything without leaving the terminal.

Next steps: if you want to *build* the server you're connecting, our [MCP server tutorial](/mcp-server-tutorial/) implements a working stdio server with real protocol traces. And if you use Claude Code's browser sibling, the [Claude Desktop MCP guide](/connect-mcp-server-to-claude-desktop/) covers the GUI-side config format, most entries translate to `claude mcp add-json` with the `type` fix from Step 6. For a different angle entirely, our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/) shows how MCP servers become tools inside an n8n agent workflow.
