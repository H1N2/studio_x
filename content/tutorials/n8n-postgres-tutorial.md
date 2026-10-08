---
title: "n8n Postgres Tutorial: Connect, Query, and Automate (2026)"
slug: "n8n-postgres-tutorial"
description: "Connect n8n to PostgreSQL step by step: create credentials, run Execute Query, insert, select, and update rows, and fix the five most common connection errors."
date: 2026-10-01
draft: false
categories: ["n8n"]
tags: ["n8n", "postgres", "postgresql", "database", "workflow-automation", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Does n8n work with managed Postgres providers like Supabase, Neon, or Amazon RDS?"
    a: "Yes. Managed providers are ordinary PostgreSQL servers: paste the provider's host, database, user, password, and port, and set SSL to Require. For providers with self-signed certificates, enable allowUnauthorizedCerts or switch SSL to Allow until you install the provider's CA certificate."
  - q: "Should I use the Select operation or Execute Query to read data?"
    a: "Use Select when you want a simple filter, sort, and limit without writing SQL: pick the schema and table, add Select Rows conditions, and toggle Return All or Limit. Use Execute Query when you need JOINs, aggregations, or window functions, because the Select operation only reads from one table. Anything the Select operation cannot express is an Execute Query job."
  - q: "How do I stop SQL injection in n8n Postgres queries?"
    a: "Never concatenate user input into the Query field with string interpolation. Write the query with $1, $2, $3 placeholders and pass the real values through the Query Parameters option, which makes n8n build a prepared statement. This is the same protection the official n8n documentation recommends, and it costs nothing extra at runtime."
  - q: "Is there a Postgres trigger node in n8n?"
    a: "Yes. The Postgres Trigger node polls a table on a schedule you define and emits new or changed rows as workflow items, which is the standard way to react to database changes in n8n. It does not use LISTEN/NOTIFY or logical replication, so expect polling latency of seconds to minutes."
  - q: "Which is better for syncing data: Insert, Update, or Insert or Update?"
    a: "Insert or Update (upsert) is the right choice for sync jobs: it inserts rows that do not exist and updates rows that do, keyed on the Unique Column you pick. Plain Insert fails the whole batch on the first duplicate key, and Update alone cannot create missing rows."
  - q: "Can Execute Query run DDL like CREATE TABLE?"
    a: "Yes. Execute Query sends whatever SQL you type, including CREATE TABLE, CREATE INDEX, and ALTER TABLE. Keep schema migrations in a one-off workflow rather than a scheduled one, so a rerun cannot accidentally re-apply a migration."
---

## Introduction

Sooner or later every serious n8n workflow outgrows in-memory data. You want orders stored where a crash cannot lose them, a customer table your whole team can query, or an audit log that survives a workflow rewrite. PostgreSQL is the natural home for that data, and n8n ships a first-class Postgres node for talking to it. This tutorial walks you from an empty database to a working workflow that creates tables, inserts rows, reads them back, updates them, and runs parameterized queries safely. It is written for automation builders who know their way around an n8n canvas but have never wired it to a real database, and every step was verified against n8n 2.40.7 and the node's published parameter names.

## Quick answer

Create a Postgres credential in n8n (host, database, user, password, port), add a Postgres node, and choose Execute Query, Insert, Select, or Update. Pass user input through Query Parameters ($1, $2) so n8n builds prepared statements instead of concatenating strings.

## Evidence

In the [Stack Overflow 2025 Developer Survey](https://survey.stackoverflow.co/2025/technology/), PostgreSQL was the most used database at 55.6% of respondents, and it topped both the most-admired list (66% of users want to keep using it) and the most-desired list (47% of non-users want to adopt it), marking the third consecutive year it led all three categories. On the n8n side, the [n8n repository on GitHub](https://github.com/n8n-io/n8n) passed 206,000 stars with over 60,000 forks as of October 1, 2026, so the Postgres integration you learn here sits on a very actively maintained foundation.

The official n8n documentation describes the node plainly: "Use the Postgres node to automate work in Postgres, and integrate Postgres with other applications. n8n has built-in support for a wide range of Postgres features, including executing queries, as well as inserting and updating rows in a database." The same docs page confirms the node can also be used as an AI tool inside AI agent workflows, which matters if you later combine this tutorial with our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/). One more line from the docs is worth memorizing before you write your first query: "You can use n8n expressions and tokens like `$1`, `$2`, and `$3` to build prepared statements to use with query parameters." That single sentence is the difference between a workflow that is safe and one that invites SQL injection.

## Prerequisites

- n8n 2.x, self-hosted or n8n Cloud. The screenshots below follow n8n 2.40.7; if you have not installed it yet, our [n8n Docker Compose setup guide](/n8n-docker-compose-setup/) gets you running in about ten minutes.
- A reachable PostgreSQL 14 or newer. Local, Docker, or managed (Supabase, Neon, Amazon RDS all work).
- Network connectivity from the n8n process to the database host on port 5432. If n8n runs in Docker, remember that `localhost` inside the container is the container itself, not your laptop.
- Basic SQL: `CREATE TABLE`, `INSERT`, `SELECT`, `UPDATE`. No advanced DBA skills needed.

## Step 1: Create a dedicated database role

Never give n8n your superuser account. Create a role with rights limited to one database. On the machine that hosts Postgres, open a psql session:

```bash
sudo -u postgres psql
```

Then run:

```sql
CREATE ROLE n8n_app WITH LOGIN PASSWORD 'change-me-in-production';
CREATE DATABASE n8n_data OWNER n8n_app;
GRANT ALL PRIVILEGES ON DATABASE n8n_data TO n8n_app;
```

Verify the role can connect before you touch n8n. This two-minute check saves you from debugging the wrong layer later:

```bash
pg_isready -h localhost -p 5432
```

If `pg_isready` prints `localhost:5432 - accepting connections`, your server is listening. If it times out, check `listen_addresses` in `postgresql.conf` (the default is `localhost`, which refuses remote connections) and add a `pg_hba.conf` line for the n8n host, then reload with `SELECT pg_reload_conf();` inside psql. A typical `pg_hba.conf` entry for a Docker network looks like:

```
host    n8n_data    n8n_app    172.17.0.0/16    scram-sha-256
```

This step follows the [PostgreSQL connection settings documentation](https://www.postgresql.org/docs/current/libpq-connect.html), the authoritative reference for how clients reach a server.

## Step 2: Create the Postgres credential in n8n

In n8n, open any workflow, add a **Postgres** node, and click **Create new credential** next to *Credential to connect with*. The credential form asks for exactly these fields, and each one matters:

- **Host**: the database hostname or IP as seen from the n8n process. For Docker Compose, this is the Postgres service name (for example `postgres`), never `localhost`.
- **Port**: `5432` unless your server was installed on a custom port.
- **Database**: `n8n_data`, the database you created in Step 1.
- **User**: `n8n_app`.
- **Password**: the role password.
- **SSL**: `Allow` for local or trusted networks, `Require` for managed providers and anything crossing the public internet, `Disable` only for local testing. If your server uses a self-signed certificate and `Require` fails, tick **allowUnauthorizedCerts** as a stopgap, but plan to install the real CA certificate.

Save the credential and use the **Test** button if your n8n version offers one. A green result means the network path, authentication, and SSL mode are all correct, and you can rule out connectivity for every later step. The full field reference lives in the [Postgres credentials documentation](https://docs.n8n.io/integrations/builtin/credentials/postgres/), which is worth bookmarking alongside this tutorial.

## Step 3: Create a table with Execute Query

Add a second **Postgres** node (or reuse the first), set **Operation** to **Execute Query**, and type this into the **Query** field:

```sql
CREATE TABLE IF NOT EXISTS orders (
  id            SERIAL PRIMARY KEY,
  customer_name TEXT NOT NULL,
  amount        NUMERIC(10,2) NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Execute the node. The output is a success confirmation rather than rows, because DDL statements return no data. Keep this provisioning in a workflow you run manually, not in a scheduled production workflow, so a rerun cannot surprise you.

## Step 4: Insert rows with the Insert operation

Change **Operation** to **Insert**. The node now asks for **Schema** and **Table**: choose *From list* to browse, or *By Name* and type `public` and `orders`. Next comes **Mapping Column Mode**, which controls how incoming workflow data maps to table columns:

- **Map Each Column Manually**: pick each column from a dropdown and assign a value. Best when your incoming data has different field names than the table.
- **Map Automatically**: n8n matches incoming field names to column names. Best when your data already looks like the table, for example rows coming from a webhook or a spreadsheet import.

Feed the node a sample item first with a Set node or the manual **Test step** input, for example:

```json
{
  "customer_name": "Ada Lovelace",
  "amount": 249.99,
  "status": "pending"
}
```

Execute the node. You should see the inserted row returned, including the generated `id` and `created_at`. Two options deserve attention on real workloads. **Query Batching** set to *Transaction* wraps every insert in one transaction, so if row 500 of 1000 fails, Postgres rolls back all changes instead of leaving a half-written table. **Skip on Conflict** skips rows that violate a unique constraint instead of erroring, which is handy for idempotent imports.

## Step 5: Read rows with the Select operation

Set **Operation** to **Select**, with Schema `public` and Table `orders`. The Select operation is the no-code way to read:

- **Return All**: on returns every matching row; off enables **Limit**, so you can fetch just the 10 newest rows while developing.
- **Select Rows**: add conditions as Column, Operator, Value triples, for example `status` *equals* `pending`. **Combine Conditions** chooses AND or OR when you add more than one.
- **Sort**: pick a column and direction, for example `created_at` descending to see the newest orders first.

Execute it. You get the pending orders back as n8n items, ready for the next node. Notice what Select cannot do: JOINs, GROUP BY, or subqueries. The moment you need `SELECT status, COUNT(*) FROM orders GROUP BY status`, switch back to Execute Query.

## Step 6: Update rows with the Update operation

Set **Operation** to **Update** and keep Schema `public` and Table `orders`. Update needs two things: which rows to change, and what to change them to. **Column to Match On** picks the identifying column, almost always `id`, and **Value of Column to Match On** is the value to look for. Then **Values to Send** (or **Map Each Column Manually** mode) sets the new values, for example `status` to `shipped`.

Run it against the row you inserted in Step 4, then run the Select node from Step 5 again to confirm the status changed. One Update execution changes every row matching your match column, so double-check the match value before executing against production tables.

## Step 7: Run safe parameterized queries

This is the most important step in the tutorial. When a query contains values from earlier nodes, a webhook, or user input, never interpolate them into the SQL string. Write the query with `$1`, `$2` placeholders and pass values through **Query Parameters** in the node's Options section:

```sql
SELECT id, customer_name, amount, status
FROM orders
WHERE status = $1 AND amount > $2
ORDER BY created_at DESC;
```

Set Query Parameters to `shipped, 100`. n8n sends the values separately from the SQL text, so Postgres builds a prepared statement and a malicious `status` value like `pending'; DROP TABLE orders; --` is treated as a plain string, not executable SQL. String concatenation in the Query field is the number one security mistake in n8n database workflows, and this pattern eliminates it.

## Troubleshooting

### "Connection terminated unexpectedly" or ECONNREFUSED

This is a network problem, not a SQL problem: the n8n process cannot reach the host and port in your credential. The most common cause in self-hosted setups is putting `localhost` in the Host field while n8n runs in Docker, because inside the container `localhost` is the container itself, where no database listens. Fix it by using the Postgres container's service name or its LAN IP as the Host, then confirm with `SHOW listen_addresses;` in psql and `pg_isready -h <host> -p 5432` from the n8n host.

### "password authentication failed for user n8n_app"

Either the password is wrong or `pg_hba.conf` rejects the authentication method. First retype the password into the credential, because a trailing space pasted from a password manager is the classic culprit. If it still fails, look at the `pg_hba.conf` line matching the n8n host: it should say `scram-sha-256` or `md5` for password auth, not `peer` or `trust`. After editing, reload with `SELECT pg_reload_conf();` and retest.

### 'relation "orders" does not exist'

The table is there, but not in the schema Postgres is looking at. The usual cause is that the node's **Schema** field is empty or set to something other than `public`. Set Schema explicitly to `public` instead of leaving it blank. A subtler variant is case sensitivity: Postgres folds unquoted identifiers to lowercase, so a table created as `"Orders"` with quotes is a different table from `orders`.

### "self signed certificate" when SSL is set to Require

Your server presents a self-signed certificate and n8n's driver refuses it. For local development, switch the credential's **SSL** mode to **Allow**, which still encrypts when the server offers TLS but does not validate the certificate chain. If the connection must stay in `Require` mode, enable **allowUnauthorizedCerts** temporarily, then install the server's CA certificate properly.

### Numbers with more than 16 digits come back wrong

JavaScript cannot precisely represent integers beyond 2^53, so BIGINT values like Snowflake IDs lose precision when n8n parses them as numbers. The node has a dedicated fix: in **Options**, set **Output Large-Format Numbers As** to **Text** instead of **Numbers**, and the column arrives as an exact string. This is documented behavior, not a bug, and it also applies to high-precision NUMERIC columns.

## FAQ

**Does n8n work with managed Postgres providers like Supabase, Neon, or Amazon RDS?**

Yes. Managed providers are ordinary PostgreSQL servers: paste the provider's host, database, user, password, and port, and set SSL to Require. For providers with self-signed certificates, enable allowUnauthorizedCerts or switch SSL to Allow until you install the provider's CA certificate.

**Should I use the Select operation or Execute Query to read data?**

Use Select when you want a simple filter, sort, and limit without writing SQL: pick the schema and table, add Select Rows conditions, and toggle Return All or Limit. Use Execute Query when you need JOINs, aggregations, or window functions, because the Select operation only reads from one table. Anything the Select operation cannot express is an Execute Query job.

**How do I stop SQL injection in n8n Postgres queries?**

Never concatenate user input into the Query field with string interpolation. Write the query with $1, $2, $3 placeholders and pass the real values through the Query Parameters option, which makes n8n build a prepared statement. This is the same protection the official n8n documentation recommends, and it costs nothing extra at runtime.

**Is there a Postgres trigger node in n8n?**

Yes. The Postgres Trigger node polls a table on a schedule you define and emits new or changed rows as workflow items, which is the standard way to react to database changes in n8n. It does not use LISTEN/NOTIFY or logical replication, so expect polling latency of seconds to minutes.

**Which is better for syncing data: Insert, Update, or Insert or Update?**

Insert or Update (upsert) is the right choice for sync jobs: it inserts rows that do not exist and updates rows that do, keyed on the Unique Column you pick. Plain Insert fails the whole batch on the first duplicate key, and Update alone cannot create missing rows.

**Can Execute Query run DDL like CREATE TABLE?**

Yes. Execute Query sends whatever SQL you type, including CREATE TABLE, CREATE INDEX, and ALTER TABLE. Keep schema migrations in a one-off workflow rather than a scheduled one, so a rerun cannot accidentally re-apply a migration.

## Conclusion

You now have a complete, secure pattern for using PostgreSQL from n8n: a least-privilege role, a tested credential, table provisioning with Execute Query, no-code Insert, Select, and Update operations, and parameterized queries that keep user input safe. The natural next step is making these database calls resilient: our [n8n error handling tutorial](/n8n-error-handling/) shows how to catch a failed query, retry it, and route the error to Slack or email instead of silently dropping rows. If you transform data in JavaScript before inserting it, the [n8n Code node JavaScript tutorial](/n8n-code-node-javascript/) covers the exact `{ json }` return format the Postgres node expects as input. And if you are deciding whether to stay on n8n or move elsewhere, our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) walks through a real 2026 pricing comparison.
