---
title: "How to Build an MCP Server in Python (2026): Tools, Resources, and Claude Desktop Setup"
slug: "build-mcp-server-python"
date: 2026-10-01T00:40:00+08:00
draft: false
description: "Build an MCP server in Python with the v2 SDK: typed tools, resources, Inspector testing, and Claude Desktop setup. Verified against the current SDK release."
categories: ["mcp", "python"]
tags: ["mcp", "python", "fastmcp", "claude-desktop", "ai-tools", "sdk", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Should I use FastMCP or MCPServer in 2026?"
    a: "Use MCPServer. The official MCP Python SDK v2 (the current stable line, installed by `pip install mcp`) renamed the high-level class: you now write `from mcp.server import MCPServer`. FastMCP was the v1 name and lives on the SDK's `v1.x` branch. Old tutorials that import `from mcp.server.fastmcp import FastMCP` will raise ImportError on v2; pin `mcp>=1.28,<2` if you are not ready to migrate."
  - q: "Can I use pip instead of uv?"
    a: "Yes. The SDK docs show `uv add \"mcp[cli]\"`, but `pip install \"mcp[cli]\"` installs the same package. uv is recommended because `uv run` automatically uses the project's virtual environment, which avoids the classic 'module not found' errors. With pip, create and activate a venv first (`python -m venv .venv`, then activate it) before installing."
  - q: "Which transport should my Python MCP server use, stdio or Streamable HTTP?"
    a: "Use stdio for local desktop hosts like Claude Desktop: the host launches your server as a subprocess and talks to it over standard input/output, with nothing to configure and no ports to manage. Use Streamable HTTP (`mcp run server.py --transport streamable-http`) when the server runs on a machine of its own and remote clients connect over the network, for example a shared team server."
  - q: "Why doesn't my server show up in Claude Desktop after editing the config?"
    a: "Three usual causes: the JSON is invalid (a trailing comma is the classic), a path in the config is relative instead of absolute, or Claude Desktop was not fully restarted after the change. Fix the JSON, use absolute paths everywhere, quit Claude Desktop completely, and reopen it. You can verify the server itself is healthy first with `mcp dev server.py` in the Inspector."
  - q: "Can the same server expose resources and prompts, not just tools?"
    a: "Yes. Tools are for actions the model can take (`@mcp.tool()`), resources expose data the model can read (`@mcp.resource(\"notes://{title}\")` for a single note or a templated URI), and prompts are reusable instruction templates. A practical server usually mixes all three: tools that change state, resources that expose state, and prompts that package the workflow."
  - q: "How do I see what my server actually sends over the wire?"
    a: "Run `mcp dev server.py` to open the MCP Inspector, which lists your tools, resources, and prompts and lets you call tools with real arguments. For automated checks, the SDK docs show an in-memory test pattern: `async with Client(mcp) as client:` connects directly to your server object with no subprocess and no port, so you can assert on `call_tool` results in a plain script."
---

## Introduction

Building an MCP server in Python is the fastest way to give an AI assistant access to your own data and actions: your notes, your database, your internal APIs. The official Python SDK does almost all the protocol work for you. You write small, type-hinted Python functions, and the SDK turns them into tools with JSON schemas, validates every call, and speaks the Model Context Protocol to any host. This tutorial walks through the current SDK (v2, which supports the 2026-07-28 MCP specification) from an empty folder to a working server connected to Claude Desktop, with testing and the five mistakes everyone makes.

## Quick answer

Install the MCP Python SDK v2 (`pip install "mcp[cli]"`), define tools with `@mcp.tool()` on an `MCPServer` object, test with the MCP Inspector, then connect it to Claude Desktop via stdio. You write typed Python functions; the SDK handles the protocol.

## Why the SDK changed, and why this guide targets v2

Two facts frame everything below, both current as of October 2026:

- **The SDK is at v2 and `pip install mcp` now installs 2.x.** The Python SDK's own README states: "This is v2 of the MCP Python SDK, the current stable release line. It is a major rework of the SDK, both to support the 2026-07-28 MCP specification (and every earlier revision) and to fix long-standing architectural issues." The high-level class is now `MCPServer` (`from mcp.server import MCPServer`); the old `FastMCP` name from v1 lives on the `v1.x` branch, which still gets critical fixes. If you follow a 2025-era tutorial that imports `from mcp.server.fastmcp import FastMCP`, it will fail on a fresh install. Pin `mcp>=1.28,<2` only if you deliberately want to stay on v1 ([modelcontextprotocol/python-sdk on GitHub](https://github.com/modelcontextprotocol/python-sdk)).
- **The ecosystem is large enough that hand-rolled protocol code is a waste.** The python-sdk repository alone has 24,442 GitHub stars as of October 1, 2026, and the SDK's docs put it bluntly: for the canonical two-function example, "Notice what you did *not* write: no JSON Schema (`a: int, b: int` *is* the schema), no request parsing, no validation code, no protocol handling. Two type-hinted Python functions and a docstring." That is the whole pitch: your type hints become the tool schema, your docstring becomes the tool description the model reads. The [official get-started guide](https://py.sdk.modelcontextprotocol.io/get-started/) goes further, every example in the docs is a complete file in the SDK's own repository, exercised by the test suite, so the code you read is the code that runs.

If you are new to the protocol itself, our [MCP server tutorial](/mcp-server-tutorial/) explains what servers, tools, and transports are before you write code.

## Prerequisites

- Python 3.10 or newer (the SDK's minimum; check with `python3 --version`).
- `uv` installed (recommended), or pip with a virtual environment. Install uv from [docs.astral.sh](https://docs.astral.sh/uv/) if you do not have it.
- Claude Desktop if you want to do the final connection step (any MCP host works, the config pattern is the same).
- About 30 minutes.

## Step 1, Set up the project

Create a folder and a project environment. With uv this is two commands:

```bash
mkdir notes-mcp && cd notes-mcp
uv init --bare
uv add "mcp[cli]"
```

`uv add "mcp[cli]"` installs the SDK plus the `mcp` command-line tool, which gives you `mcp dev` (Inspector), `mcp run` (run a server file), and `mcp install` (register with a desktop host). With pip, the equivalent is:

```bash
mkdir notes-mcp && cd notes-mcp
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install "mcp[cli]"
```

From here on, run everything through the project environment: `uv run ...` if you used uv, or with the venv activated if you used pip. This is the single biggest source of "it works in the tutorial but not on my machine" (see Troubleshooting).

## Step 2, Write the server

Create `server.py`. We will build a small notes server: tools to save, list, and read notes, plus a resource that exposes each note for reading. Every handler is a plain typed function:

```python
from mcp.server import MCPServer

mcp = MCPServer("Notes")

NOTES: dict[str, str] = {}


@mcp.tool()
def add_note(title: str, body: str) -> str:
    """Save a note under a title."""
    NOTES[title] = body
    return f"Saved note '{title}'."


@mcp.tool()
def list_notes() -> list[str]:
    """List all saved note titles."""
    return sorted(NOTES)


@mcp.tool()
def read_note(title: str) -> str:
    """Read the body of a note by its title."""
    if title not in NOTES:
        raise ValueError(f"No note titled '{title}'.")
    return NOTES[title]


@mcp.resource("notes://{title}")
def note_resource(title: str) -> str:
    """Expose a single note as a readable resource."""
    return NOTES.get(title, f"No note titled '{title}'.")
```

What the SDK derives from this, with no extra code from you:

- Each `@mcp.tool()` function becomes a tool. The parameter types (`title: str`, `body: str`) become the JSON input schema, and the docstring ("Save a note under a title.") becomes the description the model uses to decide when to call it. Write docstrings like the model is your reader, because it is.
- `@mcp.resource("notes://{title}")` registers a *templated* resource. When a host reads `notes://shopping`, the SDK extracts `title="shopping"` and calls your function. Resources are for data the model reads; tools are for actions it takes.

Type hints are not decoration here. A wrong hint (say, `title: int` when callers pass strings) produces a schema the model will dutifully follow into validation errors, so keep hints honest.

## Step 3, Test in the Inspector

Before any host is involved, open the server in the MCP Inspector:

```bash
uv run mcp dev server.py
```

The Inspector shows your three tools and the `notes://` resource template, and lets you call `add_note` with real arguments (`title`: "shopping", `body`: "oat milk, eggs") and then `read_note` with `title`: "shopping". This is where you catch the silly bugs: a typo in a URI template, a missing docstring, a handler that raises on empty input. Fix them here, where the feedback loop is seconds.

For a repeatable check you can keep, the SDK supports an in-memory client: no subprocess, no port, no transport. Put this in `smoke_test.py` in the same folder:

```python
import asyncio

from mcp import Client
from server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("add_note", {"title": "t", "body": "b"})
        print(result.structured_content)
        listed = await client.call_tool("list_notes", {})
        print(listed.structured_content)


asyncio.run(main())
```

Run it with `uv run python smoke_test.py`. `Client(mcp)` connects directly to your server object, so this tests the real tool handlers through the real protocol stack, without launching anything else.

## Step 4, Run it over Streamable HTTP (optional, for remote clients)

Desktop hosts use stdio, but if your server should live on a server of its own and serve remote clients, run it over Streamable HTTP:

```bash
uv run mcp run server.py --transport streamable-http
```

Then point any client at `http://localhost:8000/mcp`:

```python
import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("list_notes", {})
        print(result.structured_content)


asyncio.run(main())
```

A URL means Streamable HTTP, the transport you deploy; the same `Client` also launches local servers as stdio subprocesses. You do not need this step for Claude Desktop, which launches your `server.py` itself.

## Step 5, Connect it to Claude Desktop

Claude Desktop launches MCP servers as local subprocesses over stdio. The fastest registration is the SDK's own command:

```bash
uv run mcp install server.py
```

This writes your server into Claude Desktop's configuration file. If you prefer to edit the file by hand, or the automatic install does not pick it up, open the config directly. In Claude Desktop, go to Settings, the Developer tab, and click Edit Config, or open the file yourself:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add an entry under `mcpServers` (create the file with `{ "mcpServers": {} }` if it does not exist yet):

```json
{
  "mcpServers": {
    "notes": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/notes-mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

Replace `/ABSOLUTE/PATH/TO/notes-mcp` with the real absolute path (run `pwd` in the project folder). Then **fully quit and reopen Claude Desktop**; it only reads this file at startup. Open a new chat and ask "save a note titled ideas with the body test MCP server", then "list my notes". If the tools run, the whole chain works: Claude Desktop, stdio transport, your Python code.

The same pattern connects the server to other hosts: our [connect an MCP server to Claude Desktop](/connect-mcp-server-to-claude-desktop/) guide covers the general config shape, and [Claude Code MCP setup](/claude-code-mcp-setup/) shows the terminal-based variant.

## Troubleshooting

**1. `ModuleNotFoundError: No module named 'mcp'` when running `server.py`.**
You ran it with a Python that does not have the SDK. If you used uv, always launch through the project: `uv run python server.py` or `uv run mcp dev server.py`. If you used pip, make sure the venv is activated in that terminal (`source .venv/bin/activate`). Installing with plain `pip install` outside any venv while your editor uses a different interpreter is the classic version of this bug.

**2. Claude Desktop does not list the server after editing the config.**
Three usual causes, in order of frequency: the JSON is invalid (a trailing comma after the last entry breaks the whole file, validate it with `python -m json.tool claude_desktop_config.json`), a path is relative instead of absolute, or Claude Desktop was not fully restarted. Note that on macOS, closing the window does not quit the app; use Claude, Quit Claude from the menu bar.

**3. `ImportError: cannot import name 'FastMCP'` (or `No module named 'mcp.server.fastmcp'`).**
You are following a v1-era tutorial on a v2 install. Replace `from mcp.server.fastmcp import FastMCP` with `from mcp.server import MCPServer` and rename the class in your code. If the project genuinely cannot migrate yet, pin the old line with `uv add "mcp>=1.28,<2"` (or the pip equivalent) until it can. The v1 line lives on the SDK's `v1.x` branch and still receives critical fixes.

**4. The Inspector works, but the desktop host gets no response or garbage.**
A stray `print()` in your server breaks stdio. The stdio transport speaks JSON-RPC over standard output, so anything you print to stdout corrupts the protocol stream. Remove debugging prints, or log to standard error instead (`print(..., file=sys.stderr)`), which the transport ignores.

**5. `mcp run --transport streamable-http` starts, but the client cannot connect.**
Check that you are pointing the client at the `/mcp` path (`http://localhost:8000/mcp`, not the bare host), and that nothing else already holds port 8000 (`lsof -i :8000` on macOS/Linux). If you changed the port, the client URL must match.

## FAQ

See the FAQ section in the front matter above (rendered on-page below the article).

## Conclusion

A Python MCP server in 2026 is a project folder, one dependency, and a file of typed functions: `@mcp.tool()` for actions, `@mcp.resource()` for readable data, the Inspector for fast iteration, and a few lines of JSON to hand it to Claude Desktop. The v2 SDK's contract is simple, honest type hints and docstrings in, a working protocol server out.

Next step: make the server do something only your machine can do. Point a tool at your real notes folder, your task tracker, or an internal API, then read our [MCP server tutorial](/mcp-server-tutorial/) for the protocol concepts (resources vs tools vs prompts, and when to use each) that turn a demo into infrastructure.
