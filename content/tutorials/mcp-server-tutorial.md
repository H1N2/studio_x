---
title: "MCP Server Tutorial: Build Your First MCP Server from Scratch"
slug: "mcp-server-tutorial"
date: 2026-09-27
draft: false
description: "Learn how to build an MCP server step by step with the TypeScript SDK. Real code, real protocol traces, and how to connect it to Claude Desktop."
categories: ["MCP"]
tags: ["mcp server", "model context protocol", "tutorial", "typescript", "claude desktop"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "What programming languages can I use to write an MCP server?"
    a: "The official SDKs cover TypeScript, Python, Java, Kotlin, C#, and more. Any language works as long as your program speaks JSON-RPC 2.0 over stdio or Streamable HTTP, we use TypeScript here because the SDK is the most mature."
  - q: "Do I need an API key to run my own MCP server?"
    a: "No. An MCP server is just a program running on your machine. You only need API keys if your tools call external services (like a database or a paid API)."
  - q: "Should I use stdio or HTTP for my MCP server?"
    a: "Use stdio for local servers consumed by desktop apps like Claude Desktop or Cursor, it's simpler and the client manages the process lifetime. Use Streamable HTTP when the server runs remotely or needs to be shared."
  - q: "Why don't my tools show up in Claude Desktop after adding the server?"
    a: "The usual causes: the config file is in the wrong location or has a JSON syntax error, you used a relative path instead of an absolute one, or the server crashes on startup. Check Claude Desktop's MCP logs first, they tell you exactly what failed."
  - q: "Can one MCP server expose tools, resources, and prompts at the same time?"
    a: "Yes. A single server can expose all three: tools (actions the model can call), resources (data the model can read), and prompts (reusable templates). This tutorial builds tools, the most common starting point."
  - q: "Is MCP only for Claude?"
    a: "No. MCP is an open standard. Besides Claude Desktop and the Claude API, it's supported by Cursor, Windsurf, Zed, Sourcegraph Cody, and many other AI coding tools."
---

## Introduction

[MCP (Model Context Protocol)](https://modelcontextprotocol.io) is the open standard that lets AI assistants use external tools, read your files, query your database, call your APIs. In this tutorial you'll build a real, working MCP server from scratch with the [official TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk), watch the actual protocol messages flow between client and server, and connect it to Claude Desktop. Everything below was tested hands-on; the protocol traces are copied from a live run.

## Quick answer

Install the SDK with `npm install @modelcontextprotocol/sdk`, create an `McpServer`, register tools with `server.tool()`, and connect it over stdio with `StdioServerTransport`. AI clients like Claude Desktop launch your server as a subprocess and talk to it with newline-delimited JSON-RPC 2.0 messages. The full walkthrough below takes about 20 minutes.

## Prerequisites

- Node.js 18 or newer (`node --version` to check)
- npm
- A text editor
- (Optional, for the last section) Claude Desktop installed

## How MCP fits together

Three roles, one protocol:

- **Host**, the AI app (Claude Desktop, Cursor, Windsurf). It manages connections.
- **Client**, lives inside the host; one client per server connection, speaks MCP.
- **Server**, your program. Exposes **tools** (callable functions), **resources** (readable data), and **prompts** (templates).

Transports: **stdio** (the server runs as a subprocess; simplest for local use) and **Streamable HTTP** (for remote servers). We use stdio here.

## Step 1, Scaffold the project

```bash
mkdir notes-mcp && cd notes-mcp
npm init -y
npm install @modelcontextprotocol/sdk
```

The SDK pulls in `zod` for schema validation, you'll use it to describe each tool's inputs.

## Step 2, Write the server

Create `server.mjs` (the `.mjs` extension matters, it tells Node to treat the file as an ES module, so `import` works):

```js
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "notes-server", version: "1.0.0" });
const notes = [];

server.tool(
  "add_note",
  "Save a short text note and get back its id",
  { text: z.string().describe("The note text to save") },
  async ({ text }) => {
    const id = notes.length + 1;
    notes.push({ id, text });
    return { content: [{ type: "text", text: `Saved note #${id}` }] };
  }
);

server.tool(
  "list_notes",
  "List all saved notes",
  {},
  async () => ({
    content: [{ type: "text", text: JSON.stringify(notes) }],
  })
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

Three things to notice:

1. `server.tool(name, description, schema, handler)`, the description is what the AI model reads to decide when to call your tool. Write it carefully.
2. The zod schema becomes a JSON Schema `inputSchema` automatically, the model uses it to format arguments correctly.
3. Every tool returns `content`, an array of typed blocks (`text`, `image`, etc.).

## Step 3, Run it and watch the real protocol traffic

An MCP server over stdio just reads JSON-RPC messages from stdin and writes responses to stdout. You can talk to it by hand. Pipe these four messages in:

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"lab-client","version":"1.0"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add_note","arguments":{"text":"MCP lab test note"}}}' \
| node server.mjs
```

Here's what actually came back in our test run (formatted for readability):

**Handshake**, the server answers `initialize` with its identity:

```json
{"result":{"protocolVersion":"2025-06-18",
 "capabilities":{"tools":{"listChanged":true}},
 "serverInfo":{"name":"notes-server","version":"1.0.0"}},
 "jsonrpc":"2.0","id":1}
```

**Tool discovery**, `tools/list` returns each tool's name, description, and input schema (this is what the AI model sees):

```json
{"result":{"tools":[
  {"name":"add_note",
   "description":"Save a short text note and get back its id",
   "inputSchema":{"type":"object",
     "properties":{"text":{"type":"string","description":"The note text to save"}},
     "required":["text"]}},
  {"name":"list_notes",
   "description":"List all saved notes",
   "inputSchema":{"type":"object","properties":{}}}]},
 "jsonrpc":"2.0","id":2}
```

**Tool call**, `tools/call` with arguments returns content blocks:

```json
{"result":{"content":[{"type":"text","text":"Saved note #1"}]},
 "jsonrpc":"2.0","id":3}
```

That's the whole protocol: handshake, discover, call. Every MCP client, Claude Desktop, Cursor, Windsurf, does exactly this under the hood.

## Step 4, Connect it to Claude Desktop

Claude Desktop launches MCP servers as subprocesses based on a JSON config file. Add an entry pointing at your server with an **absolute path**:

```json
{
  "mcpServers": {
    "notes": {
      "command": "node",
      "args": ["/absolute/path/to/notes-mcp/server.mjs"]
    }
  }
}
```

The config file location depends on your OS:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop after editing. Open a chat and ask "what tools do you have?", you should see `add_note` and `list_notes` available. Try: "Save a note saying MCP actually works" and watch it call your server.

For the full client-by-client setup (including screenshots of where to verify the connection), see our guides: [how to connect an MCP server to Claude Desktop](/connect-mcp-server-to-claude-desktop/), [how to add an MCP server to Cursor](/add-mcp-server-to-cursor/), and [Windsurf MCP setup](/windsurf-mcp-setup/).

## Troubleshooting

### The server starts but the client hangs with no response

You probably skipped `notifications/initialized` after `initialize`. The handshake is two steps: the server answers `initialize`, then the client **must** send the `notifications/initialized` notification before calling anything else. Real MCP clients do this automatically, but if you're testing by hand and forget it, `tools/list` will never answer.

### `SyntaxError: Cannot use import statement outside a module`

Node treated your file as CommonJS. Fixes, pick one: rename the file to `.mjs`, or add `"type": "module"` to `package.json`. This bites everyone exactly once.

### Tools don't appear in Claude Desktop

Check in order: (1) JSON syntax of `claude_desktop_config.json`, one trailing comma kills it; validate with `python3 -m json.tool`; (2) the path in `args` is absolute, not `~/...`; (3) `node` is on the PATH of GUI apps, on macOS, apps launched from Finder don't inherit your shell's PATH. If in doubt, use the absolute node path (find it with `which node`).

### `console.log` debugging breaks everything

On stdio transport, **stdout is the protocol channel**. A single `console.log("debug")` corrupts the JSON-RPC stream and the client will report a parse error. Log to stderr instead: `console.error(...)`. The SDK itself follows this rule.

## FAQ

See the frequently asked questions at the top of this article for quick answers on languages, transports, API keys, and multi-capability servers.

## Conclusion

You now have a working MCP server, you've seen the raw JSON-RPC messages it exchanges, and you know how to plug it into Claude Desktop. The pattern scales: swap the in-memory array for a database, a REST API, or your company's internal tools, and the AI client doesn't need to change at all.

Next steps: learn [how to add an MCP server to Cursor](/add-mcp-server-to-cursor/) to use tools while coding, or set up [MCP in Windsurf](/windsurf-mcp-setup/) if that's your editor.
