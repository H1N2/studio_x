---
title: "n8n Docker Compose Setup: Self-Hosting with Postgres and Queue Mode (2026)"
slug: "n8n-docker-compose-setup"
date: 2026-09-30T18:30:00+08:00
draft: false
description: "Set up n8n with Docker Compose, Postgres, and queue mode with Redis workers. Complete compose file, .env template, safe upgrades, backups, and five real fixes."
categories: ["n8n", "self-hosting"]
tags: ["n8n", "docker", "docker-compose", "postgres", "redis", "queue-mode", "self-hosted", "devops"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Do I need Docker Compose, or can I run n8n with a single docker run command?"
    a: "A single container works for a quick test, but a production n8n setup needs at least n8n plus Postgres, and usually a reverse proxy, which is exactly what a compose file describes in one place. Starting with n8n 2.40.7, running outside a container prints an official deprecation warning: 'Running n8n outside a container is deprecated. Future versions will require running n8n via the official Docker image.' Compose is the install path the n8n team maintains in its official n8n-hosting repository."
  - q: "How do I upgrade n8n without losing workflows?"
    a: "Pin the image tag (for example docker.n8n.io/n8nio/n8n:2.40.7), back up the Postgres volume and the n8n storage volume, change the tag to the new version, then run docker compose pull followed by docker compose up -d. n8n applies database migrations automatically on startup. Never run the floating latest tag in production, because an unattended pull can apply a migration you cannot roll back."
  - q: "SQLite or Postgres for n8n in Docker Compose?"
    a: "SQLite only for a throwaway test. n8n's own Docker Compose documentation states: 'SQLite is fine for trying things out, but for a production instance that must handle more than a handful of users or workflows running around the clock use Postgres instead.' Postgres also unlocks queue mode with workers, which SQLite cannot do."
  - q: "What does queue mode in n8n actually buy me?"
    a: "In queue mode the main process only schedules work while separate worker containers execute it, so webhooks stay responsive during heavy runs and you can scale by adding more worker replicas. It needs Redis as the queue and EXECUTIONS_MODE=queue on every n8n service. The official n8n-hosting repository ships a withPostgresAndWorker example to copy."
  - q: "How do I back up a compose-based n8n installation?"
    a: "Back up three things: the Postgres data (docker compose exec db pg_dumpall -U n8n into a file, or tar the named volume), the n8n storage volume mounted at /home/node/.n8n, and your .env file with N8N_ENCRYPTION_KEY. Credentials are encrypted with that key, so losing it means losing every credential even if the database survives."
  - q: "Why does n8n fail to connect to Postgres with 'ENOTFOUND db'?"
    a: "That error means the n8n container cannot resolve the database service name. Inside a compose network, services reach each other by service name, so DB_POSTGRESDB_HOST must equal the database service's name (db in this guide). The usual cause is a mismatched name or n8n starting before Postgres is ready, which a healthcheck plus depends_on with condition: service_healthy fixes."
---

## Introduction

Docker Compose is the way n8n's own team ships production deployments, and it is the only install path n8n guarantees going forward. This guide builds a complete, production-ready `docker-compose.yml` for n8n: Postgres as the database, named volumes for data, a `.env` file for secrets, optional queue mode with Redis workers for heavier workloads, and a safe upgrade routine. It works on any host with Docker, from a $6 VPS to a homelab box. If you need the full VPS walkthrough with a domain and HTTPS in front of this setup, read our [guide to installing n8n on an Ubuntu VPS](/install-n8n-ubuntu-vps/) first, it ends exactly where this article begins.

## Quick answer

Put n8n and Postgres in one compose file, keep the encryption key, database settings, and webhook URL in .env, then run docker compose up -d. Pin image tags, use named volumes, and add a Redis-backed worker for queue mode.

## The numbers behind the decision

Three facts, current as of September 2026:

- **Adoption:** n8n's GitHub repository passed **205,700 stars** (awesome-list-github-stars-ranking, crawled late September 2026), making it one of the most-starred automation projects in open source. Compose-based self-hosting is its core distribution story, not a side path.
- **Pricing:** n8n Cloud's Starter plan costs **€24/month for 2,500 workflow executions**; the self-hosted Community edition is **free with unlimited executions**, you pay only for the server underneath it ([CloudZero's n8n pricing breakdown, updated September 10, 2026](https://www.cloudzero.com/blog/n8n-pricing/)). If your workflows run at any volume, the compose setup below pays for the VPS many times over.
- **Direction of the project:** when I started n8n 2.40.7 outside a container on 2026-09-30, the very first lines of output included this vendor warning: *"Running n8n outside a container is deprecated. Future versions will require running n8n via the official Docker image."* Docker is the only future-proof install method.

And the official line that settles the database question. n8n's Docker Compose documentation says: *"SQLite is fine for trying things out, but for a production instance that must handle more than a handful of users or workflows running around the clock use Postgres instead."* ([Install n8n with Docker Compose](https://docs.n8n.io/hosting/installation/server-setups/docker-compose/)). The n8n team also maintains ready-made compose examples, including one with a worker for queue mode, in its [n8n-hosting repository](https://github.com/n8n-io/n8n-hosting/tree/main/docker-compose/withPostgres). This guide follows those examples and explains every line.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2 on the host (`docker compose version` should print a version).
- A host with at least 2 vCPU and 2 GB RAM for n8n plus Postgres (4 GB if you plan to run queue-mode workers).
- A domain name if webhooks or OAuth callbacks must work over public HTTPS (the `WEBHOOK_URL` value below), plus a reverse proxy terminating TLS in front of this stack.
- Basic comfort editing YAML files, and [our n8n vs Make comparison for AI agents](/n8n-vs-make-ai-agents/) if you are still weighing whether self-hosting is worth it for agent workloads.

## Step 1, Create the project directory and the .env file

Compose reads a `.env` file next to `docker-compose.yml` automatically. Secrets live here and never in the compose file itself:

```bash
mkdir -p ~/n8n-compose && cd ~/n8n-compose
```

Now create `.env`. Generate the encryption key with `openssl rand -hex 32`:

```bash
openssl rand -hex 32
```

```
POSTGRES_USER=n8n
POSTGRES_PASSWORD=choose-a-long-random-password
POSTGRES_DB=n8n

N8N_ENCRYPTION_KEY=<paste the 64-hex-char output here>
N8N_HOST=n8n.yourdomain.com
WEBHOOK_URL=https://n8n.yourdomain.com
```

Three lines here deserve attention because they cause most support tickets. `N8N_ENCRYPTION_KEY` encrypts every credential you store in n8n; changing it after credentials exist makes them undecryptable, so generate it once and back it up with your life. `N8N_HOST` and `WEBHOOK_URL` must be the public URL your reverse proxy serves; n8n uses them to register OAuth redirect URIs and webhook URLs, and a wrong value breaks authentication silently. If you are testing without a domain, set both to `http://your-server-ip:5678` temporarily.

## Step 2, Write the compose file

This is the core of the whole setup, and it mirrors the official `withPostgres` example from the n8n-hosting repository:

```yaml
services:
  db:
    image: postgres:18
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - n8n_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  n8n:
    image: docker.n8n.io/n8nio/n8n:2.40.7
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: db
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB}
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      N8N_HOST: ${N8N_HOST}
      WEBHOOK_URL: ${WEBHOOK_URL}
      GENERIC_TIMEZONE: Asia/Shanghai
      TZ: Asia/Shanghai
    ports:
      - "5678:5678"
    volumes:
      - n8n_storage:/home/node/.n8n

volumes:
  n8n_postgres_data:
  n8n_storage:
```

Line by line, the decisions that matter: the database is `postgres:18` as a named service, and n8n reaches it at the hostname `db` because compose gives every service DNS by its name. The healthcheck plus `depends_on` with `condition: service_healthy` stops the classic race where n8n boots before Postgres accepts connections. The image is pinned to `2.40.7`, the version I verified locally, instead of the floating `latest` tag, so a surprise `docker compose pull` never migrates your database under you. Data lives in Docker named volumes, not bind mounts, which sidesteps the file-permission wars between the host user and the `postgres` user inside the container. `GENERIC_TIMEZONE` and `TZ` keep scheduled triggers running in your own timezone instead of UTC.

## Step 3, Start the stack and verify

```bash
docker compose up -d
docker compose ps
```

Wait about 30 seconds for migrations, then check the logs:

```bash
docker compose logs n8n --tail 20
```

You should see the editor starting on port 5678. Open `http://your-host:5678` (or your domain if a reverse proxy is already in front) and create the owner account. Then run a sanity workflow: an HTTP Request node hitting `https://httpbin.org/get` followed by a Set node. If it executes green, the database, encryption, and networking are all correct. This stack also pairs naturally with [our n8n AI agent tutorial](/n8n-ai-agent-tutorial/), which assumes exactly this kind of self-hosted n8n underneath.

## Step 4, Add queue mode with a Redis worker (optional, for heavy workloads)

When workflows run constantly or AI agents hold executions open for minutes, one process doing both the editor and execution chokes. Queue mode splits the roles: the main service only schedules work, worker containers execute it, and Redis carries the queue. The official `withPostgresAndWorker` example uses exactly this shape:

```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - n8n_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  n8n-worker:
    image: docker.n8n.io/n8nio/n8n:2.40.7
    restart: unless-stopped
    command: worker
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: db
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB}
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      EXECUTIONS_MODE: queue
      QUEUE_BULL_REDIS_HOST: redis
      QUEUE_BULL_REDIS_PORT: 6379
      QUEUE_BULL_REDIS_DB: 2
      N8N_CONCURRENCY_PRODUCTION_LIMIT: 20
```

And add `EXECUTIONS_MODE: queue`, `QUEUE_BULL_REDIS_HOST: redis`, `QUEUE_BULL_REDIS_PORT: 6379`, and `QUEUE_BULL_REDIS_DB: 2` to the main `n8n` service as well, so the scheduler and the workers agree on the queue. `command: worker` is the key line: the same image, but it runs the worker process instead of the editor. Scale it horizontally with `docker compose up -d --scale n8n-worker=3`, no config change needed.

## Step 5, Upgrade n8n safely

This is the routine you will run every few weeks, and the pinned tag is what makes it safe:

```bash
cd ~/n8n-compose
docker compose exec db pg_dumpall -U n8n > backup-$(date +%F).sql
docker compose down
# edit docker-compose.yml: change 2.40.7 to the new version
docker compose pull
docker compose up -d
docker compose logs n8n --tail 30
```

`pg_dumpall` gives you a logical backup you can restore anywhere, and compose `down` (not `down -v`) keeps your named volumes intact. Watch the startup logs for migration lines; n8n prints them clearly, and a failed migration is the one case where you restore from that backup instead of pushing forward. For the full version-to-version checklist, including the breaking changes that matter for AI agent workflows, see our [Zapier to n8n migration guide](/zapier-to-n8n-migration/).

## Troubleshooting

### Postgres container exits immediately with a data-directory error

The logs show something like `initdb: error: directory "/var/lib/postgresql/data" exists but is not empty` or `chown: changing ownership of '/var/lib/postgresql/data': Permission denied`. This happens with host bind mounts: the directory on the host is owned by your user or root, while the `postgres` user inside the container needs to own it, and initdb refuses a non-empty directory it did not create. The guide above uses Docker named volumes precisely to avoid this. If you already mounted a host path, switch the `db` volume to `n8n_postgres_data:/var/lib/postgresql/data` and let Docker manage ownership. If the named volume already contains an old cluster from a different Postgres major version, you must `pg_dumpall` from the old container and restore into the new one; Postgres cannot read a data directory across major versions.

### n8n logs "getaddrinfo ENOTFOUND db" or ECONNREFUSED to Postgres

This is the number-one compose mistake: `DB_POSTGRESDB_HOST` must equal the database service's name as written under `services`, here `db`. Containers reach each other by service name on the compose network, never by `localhost`, because inside the n8n container `localhost` is n8n itself. The second cause is timing: without the healthcheck and `depends_on` with `condition: service_healthy`, n8n tries to connect before Postgres finishes initializing. Verify connectivity with `docker compose exec n8n sh -c 'node -e "require(\"dns\").lookup(\"db\", console.log)"'`, or simply `docker compose logs db` to confirm it printed `database system is ready to accept connections`.

### "Mismatching encryption keys" after redeploying

n8n refuses to start, or all credentials fail with an encryption error, because the `N8N_ENCRYPTION_KEY` changed between runs. Real-world cause: someone ran `docker compose up` in a different directory or a fresh clone without copying the `.env` file, so compose substituted an empty key. The fix is prevention: keep one `.env` file per deployment, back it up alongside your database dumps, and never rotate the key without re-encrypting credentials through n8n's own export first. There is no recovery path for credentials encrypted with a lost key.

### "Bind for 0.0.0.0:5678 failed: port is already allocated"

Another n8n process, often an old `docker run` container or a second compose project, already owns the port. Find it with `docker ps | grep 5678`, stop the stale one with `docker stop <name>`, or change the mapping to `"5679:5678"` in the compose file if you genuinely need two instances. Then run `docker compose up -d` again.

### Workers sit idle while jobs pile up in queue mode

Jobs queue but no worker picks them up. The cause is almost always a mismatch: every n8n service, including the main one, must set `EXECUTIONS_MODE: queue` and identical `QUEUE_BULL_REDIS_HOST` values, and the worker must run with `command: worker`. If the main service runs in regular mode, it executes jobs locally and never writes to the queue; if Redis is unreachable, the scheduler logs `ECONNREFUSED redis`. Check with `docker compose logs n8n-worker --tail 30` and confirm you see the worker registering itself, then confirm the Redis healthcheck passes.

## FAQ

The FAQ section in the front matter above answers six questions readers actually ask: whether Compose is required, how to upgrade safely, SQLite vs Postgres, what queue mode buys you, how to back up, and the classic `ENOTFOUND db` error.

## Conclusion

A compose file turns n8n from a fragile pet container into a reproducible deployment: pinned versions, named volumes, healthchecks, and an upgrade path you can trust at 2 a.m. Start with the two-service setup here, add queue mode when executions queue up, and keep `N8N_ENCRYPTION_KEY` in your backup strategy from day one. Next steps: harden the stack the way production setups do with our [n8n error handling guide](/n8n-error-handling/), or put the whole thing behind a domain and HTTPS using our [Ubuntu VPS install guide](/install-n8n-ubuntu-vps/), then try [the vector store tutorial](/n8n-vector-store-tutorial/) to see what a self-hosted n8n can do for AI retrieval.
