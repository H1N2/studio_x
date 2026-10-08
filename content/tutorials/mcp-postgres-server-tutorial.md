---
title: "MCP Postgres Server Tutorial: Safe Read-Only Database Access for AI Agents (2026)"
slug: "mcp-postgres-server-tutorial"
description: "Install Postgres MCP Pro in restricted mode behind a least-privilege read-only role: safe AI access to PostgreSQL, each step tested on a live database."
date: 2026-10-04
draft: false
categories: ["MCP"]
tags: ["mcp", "postgres", "postgresql", "claude-desktop", "ai-agents", "database", "security", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Is the official @modelcontextprotocol/server-postgres still maintained?"
    a: "No. The official reference server was moved to the modelcontextprotocol/servers-archived repository and its npm package is deprecated. It still receives hundreds of thousands of downloads a month from outdated tutorials, but it has no maintainer, so use an actively maintained server such as crystaldba/postgres-mcp instead."
  - q: "Can I point the MCP server at my production database?"
    a: "Only in restricted mode, behind a least-privilege read-only Postgres role, and ideally against a read replica rather than the primary. Unrestricted mode gives the agent full read/write access and belongs on throwaway development databases only."
  - q: "Does restricted mode guarantee the agent cannot write anything?"
    a: "Restricted mode rejects writes at the server layer by parsing SQL with pglast and wrapping statements in read-only transactions. For a hard guarantee, also create a Postgres role that only holds SELECT grants, so the database itself refuses writes even if the agent's SQL slips past the parser."
  - q: "Which Postgres versions work with Postgres MCP Pro?"
    a: "The project's FAQ states that testing focuses on Postgres 15, 16, and 17, with support for versions 13 through 17 planned. The read-only role SQL in this tutorial uses standard GRANT syntax that works on all supported versions."
  - q: "What should I do if the server says no database URL was provided?"
    a: "You forgot the connection string. Pass it as the DATABASE_URI environment variable or as the first positional argument to postgres-mcp, for example postgres-mcp --access-mode=restricted postgresql://user:pass@localhost:5432/dbname."
  - q: "Do I need Docker to run Postgres MCP Pro?"
    a: "No. Docker is one option (docker pull crystaldba/postgres-mcp), but pipx install postgres-mcp or uvx postgres-mcp work just as well. Docker is handy because the image remaps localhost to the host automatically; with a local install you connect to 127.0.0.1 directly."
---

## Introduction

Letting an AI agent touch your database is the fastest way to make it useful and the fastest way to lose data. One hallucinated `UPDATE` without a `WHERE` clause is all it takes. This tutorial shows the setup that earns both: an AI assistant that can explore schemas, run analytical queries, and explain slow query plans against PostgreSQL, while two independent layers stop it from writing anything. You will install the actively maintained Postgres MCP Pro server, create a least-privilege read-only database role, and lock the server into restricted mode. It is written for developers who already know what an MCP server is; if you do not, start with [our Model Context Protocol pillar guide](https://www.161808.xyz/mcp-server-tutorial/) first.

## Quick answer

Install crystaldba/postgres-mcp instead of the deprecated official server, create a Postgres role with only SELECT grants, and run with --access-mode=restricted. The agent can read and inspect but every write is rejected.

## Why this specific server (evidence)

The most-downloaded Postgres MCP server on the internet is one you should not install. The npm registry reports that `@modelcontextprotocol/server-postgres` was downloaded 410,147 times in the 30 days ending 2026-10-01, even though the package is deprecated and the source now lives in the [archived official reference repository](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), which receives no fixes. That download count, measured as of October 2026, is the cost of stale tutorials: hundreds of thousands of installs of an unmaintained database connector, many of them copy-pasted from guides written before the deprecation.

The maintained replacement is [Postgres MCP Pro by Crystal DBA](https://github.com/crystaldba/postgres-mcp), an open-source (MIT) MCP server with 3,365 GitHub stars and commits as recent as August 2026. Beyond plain query execution it ships deterministic database health checks, index tuning, and EXPLAIN analysis.

The security design is the reason to pick it. Crystal DBA's technical notes state the philosophy plainly:

> "We designed restricted mode to be conservative, erring on the side of safety even though it may be inconvenient."

Restricted mode wraps every statement in a read-only transaction, caps execution time, and parses each query with the [pglast](https://pglast.readthedocs.io/en/latest/) SQL parser to reject anything containing `COMMIT` or `ROLLBACK` before it ever reaches the database. That stops the classic escape where an agent issues `ROLLBACK` to drop out of the read-only transaction and then runs a write. We verified this behavior against a live database in the lab: `execute_sql` with `DROP TABLE app.products` returned `Error: Error validating query: DROP TABLE app.products`, while a plain `SELECT` returned the table's rows normally.

But the README is honest about the limits of that approach, and so is this tutorial: parser-level protection is one layer, not a guarantee. The second layer is a Postgres role that the database itself only trusts with `SELECT`, configured with the standard privilege system documented in the [PostgreSQL privileges guide](https://www.postgresql.org/docs/current/ddl-priv.html). Two layers, each able to stop a write on its own.

## Prerequisites

- Python 3.12 or higher with `pipx` or `uv` installed, or Docker if you prefer the container route
- A PostgreSQL database you can administer (local Postgres 15, 16, or 17; a Docker container works fine)
- `psql` or any SQL client, plus superuser access for the one-time role setup
- Claude Desktop (the config format below also works in Cursor, Windsurf, and Goose with small path changes)
- Basic comfort with SQL `GRANT` statements

## Step 1: Install Postgres MCP Pro, not the archived official server

The old instructions still floating around the web tell you to run `npx -y @modelcontextprotocol/server-postgres`. Do not follow them. That package is deprecated and unmaintained; the project moved on and the sensible successors are listed in the archived repository. Install the maintained server instead. With `pipx`:

```bash
pipx install postgres-mcp
```

Or with `uv`, which needs no prior installation step:

```bash
uvx postgres-mcp --help
```

Either way, verify the install by asking for the flag list. On the lab machine this printed:

```
usage: postgres-mcp [-h] [--access-mode {unrestricted,restricted}]
                    [--transport {stdio,sse}] [--sse-host SSE_HOST]
                    [--sse-port SSE_PORT]
                    [database_url]

PostgreSQL MCP Server
```

Two flags matter for this tutorial: `--access-mode`, which accepts `unrestricted` or `restricted`, and the optional positional `database_url`. If you prefer Docker, the equivalent is `docker pull crystaldba/postgres-mcp`; the image accepts the same flags.

One installation quirk we hit in the lab is worth knowing: if you install `postgres-mcp` into an existing virtual environment that already contains the MCP SDK v2, the server crashes at startup with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`. The fix is to pin the older SDK (`pip install "mcp<2"`) or, simpler, to use the isolated `pipx`/`uvx` route above, which keeps dependencies separate.

## Step 2: Create a least-privilege read-only Postgres role

This is the layer that holds even if every other protection fails. Connect as a superuser and create a dedicated role for the agent, then grant it exactly `CONNECT`, `USAGE`, and `SELECT`, and nothing else. Every statement below ran verbatim against a real Postgres in the lab:

```sql
CREATE ROLE readonly_agent LOGIN PASSWORD 'Str0ng#Test' NOSUPERUSER;
GRANT CONNECT ON DATABASE shop TO readonly_agent;
GRANT USAGE ON SCHEMA app TO readonly_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO readonly_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA app
  GRANT SELECT ON TABLES TO readonly_agent;
```

The last line matters and is easy to forget: without `ALTER DEFAULT PRIVILEGES`, tables created in the future get no grants and the agent silently loses access to new data. The `NOSUPERUSER` keyword is explicit on purpose, so a future reader of your setup script can see the role was never privileged.

Verify the role behaves the way you think before any AI touches it. Connecting as `readonly_agent`, a `SELECT` returned the expected rows, and all three write attempts failed with exact, recognizable Postgres errors:

```
SELECT count(*) FROM app.products;   -- works, returns 2
INSERT INTO app.products ...;        -- permission denied for table products
DROP TABLE app.products;             -- must be owner of table products
CREATE TABLE app.evil(id int);       -- permission denied for schema app
```

These are database-level refusals. No parser, no middleware, no prompt is involved. That is what makes this layer trustworthy.

## Step 3: Connect the server in restricted mode and confirm writes are rejected

Start the server with `--access-mode=restricted` and hand it the read-only role's connection string. Passwords with special characters must be percent-encoded in the URI, per the [PostgreSQL connection string rules](https://www.postgresql.org/docs/current/libpq-connect.html): the `#` in our test password became `%23`. Forget the connection string entirely and the server tells you exactly what is wrong:

```
ValueError: Error: No database URL provided. Please specify via
'DATABASE_URI' environment variable or command-line argument.
```

We tested the restricted server end to end over MCP's stdio transport against the database from Step 2. A `SELECT name, price FROM app.products ORDER BY price` through the `execute_sql` tool returned both rows:

```
[{'name': 'widget', 'price': Decimal('9.99')}, {'name': 'gadget', 'price': Decimal('24.50')}]
```

And `DROP TABLE app.products` through the same tool came back rejected before reaching the database:

```
Error: Error validating query: DROP TABLE app.products
```

So a malicious or confused agent now has to defeat the SQL parser, the read-only transaction wrapper, and a database role that cannot write, in that order. For an analytics or support assistant, that is the right posture: full read power, zero write power.

## Step 4: Wire it into Claude Desktop

With the server proven, add it to your assistant. The project's README documents the Claude Desktop configuration file locations as `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS and `%APPDATA%/Claude/claude_desktop_config.json` on Windows, and the entry to add under `mcpServers` is:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uvx",
      "args": [
        "postgres-mcp",
        "--access-mode=restricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://readonly_agent:Str0ng%23Test@localhost:5432/shop"
      }
    }
  }
}
```

Replace the `DATABASE_URI` value with your real connection string. If you used `pipx install`, change `command` to `postgres-mcp` and drop the `postgres-mcp` entry from `args`. If you used Docker, use `command: "docker"` with args `["run", "-i", "--rm", "-e", "DATABASE_URI", "crystaldba/postgres-mcp", "--access-mode=restricted"]`; the Docker image automatically remaps `localhost` to the host (via `host.docker.internal` on macOS/Windows), which the plain Python install does not do.

Restart Claude Desktop after saving. The postgres server should appear in the tools list. Ask it something harmless first, like "list the schemas in the shop database", and confirm the answer comes from your real tables before asking anything more ambitious. The same JSON shape works in other clients; if you want to compare client options, our [Claude Code MCP setup guide](https://www.161808.xyz/claude-code-mcp-setup/) covers scopes and CLI registration, and [connecting an MCP server to Claude Desktop](https://www.161808.xyz/connect-mcp-server-to-claude-desktop/) walks through tool debugging.

## Step 5: Use the tools that make this server worth installing

Plain query execution is table stakes. The tools that justify this server over a thinner one, all listed in its MCP API reference, are:

- `list_schemas`, `list_objects`, `get_object_details`: let the agent discover your schema itself instead of you pasting DDL into prompts. `get_object_details` returns a table's columns, constraints, and indexes.
- `explain_query`: returns the planner's execution plan for a query, and can simulate hypothetical indexes to preview the effect of adding one.
- `get_top_queries`: reports the slowest queries from `pg_stat_statements` data. This one needs the extension installed (`CREATE EXTENSION pg_stat_statements;` as a superuser); on managed providers check their docs for the equivalent toggle.
- `analyze_db_health`: runs deterministic checks for buffer cache hit rates, connection health, duplicate or unused indexes, sequence limits, vacuum health, and replication lag.

A practical first session: run `analyze_db_health`, then ask for an `explain_query` on the worst finding. When the day comes to allow writes for migrations, you will decide with evidence rather than hope.

## Troubleshooting

### `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` at startup

You installed `postgres-mcp` into a virtual environment that already has the MCP Python SDK v2, where the old `FastMCP` import path was renamed. This is a dependency conflict, not a broken install. Fix it by pinning the v1 SDK in that environment (`pip install "mcp<2"`), or avoid the problem entirely with the isolated `pipx install postgres-mcp` / `uvx postgres-mcp` route from Step 1.

### `ValueError: Error: No database URL provided`

The server found neither a `DATABASE_URI` environment variable nor a positional connection string. Set one: `export DATABASE_URI=postgresql://user:pass@host:5432/db` before launching, or pass the URI as the first argument. The exact error text is `Please specify via 'DATABASE_URI' environment variable or command-line argument`, which tells you both options.

### Connection refused when the database is definitely running

If the error mentions port 5432 and asks "Is the server running on that host and accepting TCP/IP connections?", check two things. First, the obvious: `pg_isready -h localhost -p 5432` should answer. Second, the Docker trap: inside the `crystaldba/postgres-mcp` container, `localhost` is remapped to the host automatically, but if you bypass the documented config and use a custom network, that remapping can break and the server dials a Postgres that is not there. Keep the README's Docker args verbatim.

### Password with special characters fails authentication

Connection URIs follow the [libpq connection string rules](https://www.postgresql.org/docs/current/libpq-connect.html), so `#`, `@`, `/`, and `%` in a password must be percent-encoded (`#` becomes `%23`, `@` becomes `%40`). A password that works fine in `psql`'s interactive prompt can fail inside a URI for this reason alone. In the lab, `Str0ng#Test` only connected as `Str0ng%23Test`.

### `get_top_queries` returns nothing useful

That tool reads `pg_stat_statements`, which is an extension, not a built-in. On self-managed Postgres, run `CREATE EXTENSION pg_stat_statements;` as a superuser and add `pg_stat_statements` to `shared_preload_libraries` in `postgresql.conf`, then restart. Until the extension is loaded, the tool has no data to report, and that is expected rather than a bug.

## FAQ

### Should I ever use `--access-mode=unrestricted`?

Only against a local or throwaway development database that you can rebuild from a backup in minutes. Unrestricted mode gives the agent full read/write access to data and schema. The project's own guidance reserves it for development where "the consequences of mistakes are low". Production and staging stay in restricted mode, always.

### How is this different from the old official server?

The old `@modelcontextprotocol/server-postgres` exposed a single `query` tool and is now archived without a maintainer. Postgres MCP Pro exposes nine tools and adds health checks, index tuning, and EXPLAIN analysis with documented SQL parsing protections.

### Can I use this with a managed database like RDS, Neon, or Supabase?

Yes. They are ordinary PostgreSQL servers from the connector's point of view: paste the provider's host, database, user, password, and port into `DATABASE_URI`, and set `sslmode=require` in the URI if the provider enforces TLS. Pair it with a read-only role created on the provider side, and consider pointing the agent at a read replica if the provider offers one.

### Does restricted mode slow down queries?

It adds a SQL parse step and a statement timeout cap per query, which is negligible next to network and planning time for analytical queries. The timeout exists to protect the database from runaway queries, which is a feature when the SQL author is a language model.

### Can I run the server for multiple clients at once?

Yes, with the SSE transport: start it with `--transport=sse --sse-port 8000` and point clients at `http://localhost:8000/sse`. Note that every client sharing that server shares the same `DATABASE_URI` and access mode, so do not mix restricted analytics clients and unrestricted development clients on one server instance.

## Conclusion

The safe pattern for AI database access is boring on purpose: a maintained server, a role that can only read, and restricted mode on top. From here, the natural next step is pairing this with automation: our [n8n Postgres tutorial](https://www.161808.xyz/n8n-postgres-tutorial/) wires the same database into scheduled workflows, and [how to build an MCP server in Python](https://www.161808.xyz/build-mcp-server-python/) covers building a custom server from scratch.
