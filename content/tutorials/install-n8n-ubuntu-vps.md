---
title: "How to Install n8n on Ubuntu VPS (2026): Docker Compose, Postgres & Free HTTPS"
slug: "install-n8n-ubuntu-vps"
date: 2026-09-30T09:45:00+08:00
draft: false
description: "Install n8n on an Ubuntu VPS with Docker Compose, Postgres 18, and free HTTPS via Caddy. Verified against n8n 2.40.7, including the new npm deprecation warning and four real-world fixes."
categories: ["n8n", "self-hosting"]
tags: ["n8n", "ubuntu", "vps", "docker", "docker-compose", "postgres", "caddy", "https", "self-hosted"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "How much RAM and CPU does a self-hosted n8n instance need?"
    a: "A 2 vCPU / 2 GB RAM VPS is comfortable for personal use and small teams, this site itself runs on that class of box. n8n's editor is a Node.js app; memory pressure only becomes real with dozens of concurrent executions or heavy AI workloads. Give Postgres its own headroom if you run both on one machine."
  - q: "Is self-hosted n8n really free?"
    a: "Yes. The self-hosted Community edition is free with unlimited workflow executions, you only pay for the VPS underneath it. n8n Cloud starts at €24/month for 2,500 executions. The trade-off is that you own maintenance: upgrades, backups, and uptime are your job."
  - q: "Can I still install n8n with npm instead of Docker?"
    a: "Technically yes, `npm install -g n8n` still works, but you shouldn't for a server. Starting n8n 2.40.7 prints an official deprecation notice: 'Running n8n outside a container is deprecated. Future versions will require running n8n via the official Docker image.' Docker is the only install path n8n guarantees going forward."
  - q: "How do I update n8n to a newer version?"
    a: "Back up first, then change the image tag in docker-compose.yml (or point it at a newer pinned version), and run `docker compose pull && docker compose up -d`. n8n runs database migrations automatically on startup. Never use the floating `latest` tag on a production instance, pin the version you tested."
  - q: "Can I run n8n on the VPS IP address without a domain name?"
    a: "For a quick test, yes: http://YOUR_SERVER_IP:5678 works. For anything real, no, get a domain. Webhook URLs, OAuth redirect URIs, and several app credentials require a stable public HTTPS URL, and browsers increasingly block the mixed-content tricks you'd need without TLS."
  - q: "Where are my workflows and credentials actually stored?"
    a: "In two places: the `n8n_storage` Docker volume (mounted at /home/node/.n8n, holds config and the encryption key state) and the Postgres database (workflows, executions, credentials, encrypted with your N8N_ENCRYPTION_KEY). Back up both: pg_dumpall for Postgres and a tarball of the volume."
---

## Introduction

Self-hosting n8n on a cheap Ubuntu VPS is the single biggest cost lever in workflow automation: the same agent workloads that cost hundreds per month on per-operation platforms run for the price of a $6 VPS. This guide walks you through the production-ready setup, Docker Compose, Postgres 18, and free HTTPS via Caddy, on Ubuntu 22.04 or 24.04. Every command below is real, the compose file follows n8n's official hosting examples, and the n8n behavior notes come from actually running n8n 2.40.7 locally.

## Quick answer

Install Docker on your Ubuntu VPS, write a `docker-compose.yml` containing n8n plus Postgres 18, set `N8N_HOST`, `WEBHOOK_URL`, and an encryption key in a `.env` file, then put Caddy in front for automatic HTTPS. Skip the npm install: n8n 2.40.7 prints a deprecation notice on startup saying future versions will require the official Docker image.

## The numbers that frame this decision

Three facts, all current as of September 2026:

- **Adoption:** n8n's GitHub repository passed **205,700 stars** (awesome-list-github-stars-ranking, data crawled late September 2026), making it one of the most-starred automation projects in open source. Self-hosting is n8n's core distribution story, not an afterthought.
- **Pricing:** n8n Cloud's Starter plan costs **€24/month for 2,500 workflow executions**; the self-hosted Community edition is **free with unlimited executions**, you pay only for the VPS underneath ([CloudZero's n8n pricing breakdown, updated Sept 10, 2026](https://www.cloudzero.com/blog/n8n-pricing/)).
- **Direction of the project:** when I started n8n 2.40.7 via npm on 2026-09-30, the very first lines of output included this vendor warning: *"Running n8n outside a container is deprecated. Future versions will require running n8n via the official Docker image."* ([n8n hosting docs](https://docs.n8n.io/deploy/host-n8n/)). Install with Docker today and you won't have to migrate tomorrow.

One more official line worth quoting before we start. n8n's Docker Compose documentation is blunt about databases: *"SQLite is fine for trying things out, but for a production instance that must handle more than a handful of users or workflows running around the clock use Postgres instead."* ([Install using Docker Compose](https://docs.n8n.io/deploy/host-n8n/install-options/install-using-docker-compose)). So this guide ships Postgres 18 from the start.

> Heads-up: n8n reorganized its docs in 2026. Old guides link to `docs.n8n.io/hosting/installation/docker/`, that path now redirects. The current canonical pages live under `docs.n8n.io/deploy/host-n8n/`.

## Prerequisites

- An Ubuntu 22.04 or 24.04 VPS with at least 2 vCPU and 2 GB RAM, with root or sudo access.
- A domain name (e.g. `n8n.yourdomain.com`) with an A record pointing at the VPS IP.
- About 15 minutes, and basic comfort with the Linux terminal.
- Docker knowledge: none required beyond copy-pasting below, but read our [n8n vs Make for AI agents](/n8n-vs-make-ai-agents/) comparison first if you're still deciding whether self-hosting is worth it. (Spoiler: for agent workloads billed per execution instead of per operation, it is.)

## Step 1, Update the server and open the firewall

SSH into your VPS and bring the system up to date:

```bash
sudo apt update && sudo apt upgrade -y
```

Lock down the firewall so only SSH, HTTP, and HTTPS are reachable. n8n itself will listen only on localhost (step 4), so it never needs a public port:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

## Step 2, Install Docker Engine from Docker's official repository

Ubuntu's default repos ship an outdated Docker. Use Docker's own apt repository ([official install guide](https://docs.docker.com/engine/install/ubuntu/)):

```bash
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

Verify the install:

```bash
docker --version
docker compose version
```

Both commands should print version numbers with no errors.

## Step 3, Create the project and generate secrets

Make a directory for the deployment and create a `.env` file holding every secret. Never commit this file anywhere:

```bash
mkdir -p ~/n8n && cd ~/n8n
openssl rand -hex 32   # copy the output -> N8N_ENCRYPTION_KEY below
openssl rand -hex 24   # copy the output -> POSTGRES_PASSWORD below
```

Create `~/n8n/.env`:

```ini
POSTGRES_USER=n8n
POSTGRES_PASSWORD=paste-the-24-byte-hex-here
POSTGRES_DB=n8n
N8N_ENCRYPTION_KEY=paste-the-32-byte-hex-here
```

The encryption key protects every credential n8n stores. If you lose it, your stored API keys and OAuth tokens become unreadable, keep a copy somewhere safe, like a password manager.

## Step 4, Write the Docker Compose file

Create `~/n8n/docker-compose.yml`. This is adapted from the official [n8n-hosting](https://github.com/n8n-io/n8n-hosting) `withPostgres` example, trimmed for a single VPS:

```yaml
services:
  postgres:
    image: postgres:18
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      # Postgres 18 changed its default data directory. Without this line,
      # the volume below misses the data dir and the DB starts empty.
      PGDATA: /var/lib/postgresql/data
    volumes:
      - db_storage:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  n8n:
    # Pin the exact version you tested; upgrade deliberately, never via :latest
    image: docker.n8n.io/n8nio/n8n:2.40.7
    restart: always
    ports:
      # Bind to localhost only — Caddy (step 6) is the only public entry point
      - "127.0.0.1:5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=${POSTGRES_DB}
      - DB_POSTGRESDB_USER=${POSTGRES_USER}
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
      - N8N_HOST=n8n.yourdomain.com
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://n8n.yourdomain.com/
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - GENERIC_TIMEZONE=UTC
    volumes:
      - n8n_storage:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  db_storage:
  n8n_storage:
```

Replace `n8n.yourdomain.com` with your real domain in both `N8N_HOST` and `WEBHOOK_URL`. The trailing slash on `WEBHOOK_URL` matters, n8n concatenates paths onto it, and a missing slash produces broken webhook URLs that fail silently.

## Step 5, Start n8n and verify it's healthy

```bash
cd ~/n8n
docker compose up -d
docker compose ps
```

Wait about 30 seconds for Postgres to pass its healthcheck and n8n to finish migrations, then verify:

```bash
curl -sf http://localhost:5678/healthz && echo "n8n is up"
docker compose logs n8n --tail 20
```

You should see n8n's startup banner including `n8n ready on`, the same output I captured when verifying 2.40.7 locally on 2026-09-30, which reported `n8n ready on ::, port 5678` and a task broker on port 5679.

## Step 6, Put Caddy in front for free HTTPS

Caddy terminates TLS automatically, no certbot, no renewal cron jobs. This exact pattern (Caddy 2.11.4 reverse-proxying a localhost app) is what serves this very site. Install Caddy from its official repo, then add a site block:

```bash
# /etc/caddy/Caddyfile
n8n.yourdomain.com {
    reverse_proxy 127.0.0.1:5678
}
```

```bash
sudo systemctl reload caddy
```

Within a minute, `https://n8n.yourdomain.com` serves n8n with a valid certificate. If you prefer Nginx, the equivalent needs `proxy_set_header Upgrade $http_upgrade;` and `proxy_set_header Connection "upgrade";`, n8n's editor streams live execution updates over a websocket, and proxies that strip the Upgrade header produce a permanent "Connection lost" banner.

## Step 7, Create your owner account and run a smoke test

Open `https://n8n.yourdomain.com`. The first visit asks you to create the owner account (name, email, password), entirely local, no n8n Cloud account involved. Then build a 30-second smoke test:

1. Create a workflow with a **Schedule Trigger** (every minute) → **Code** node containing `return [{json: {hello: "vps"}}]` → **NoOp** (or just leave the Code node last).
2. Save, activate, wait a minute, and check the **Executions** tab.

If executions appear green, your queue, database, and scheduler all work. Now you're ready for real work, our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/) builds a working AI agent on exactly this kind of instance.

## Step 8, Backups and upgrades (do this before you need it)

**Backup** (run weekly via cron, keep copies off the server):

```bash
cd ~/n8n
# 1. Database
docker compose exec -T postgres pg_dumpall -U n8n > backup-$(date +%F).sql
# 2. n8n data volume (config, keys state)
docker run --rm -v n8n_n8n_storage:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/n8n_storage-$(date +%F).tar.gz -C /data .
```

Your project directory name prefixes volume names, if `docker volume ls` shows a different name than `n8n_n8n_storage`, use the real one.

**Upgrade**:

```bash
cd ~/n8n
# backup first (see above), then:
sed -i 's/n8n:2.40.7/n8n:2.41.0/' docker-compose.yml   # example
docker compose pull n8n
docker compose up -d
docker compose logs n8n --tail 30   # watch migrations complete
```

Skim n8n's release notes before jumping major versions, breaking changes are announced there, not at upgrade time.

## Troubleshooting

### 1. n8n container exits with `password authentication failed for user "n8n"`

**Cause:** you changed `POSTGRES_PASSWORD` in `.env` after the first start. Postgres reads those variables only when it initializes a fresh data directory; afterwards the password lives inside the database, and the new value no longer matches.

**Fix:** don't rotate the password by editing `.env` alone. Either revert `.env` to the original password, or change it properly inside Postgres (`ALTER USER n8n WITH PASSWORD 'new'` via `docker compose exec postgres psql`) and then update `.env` to match.

### 2. Postgres 18 loses all data on restart, workflows gone

**Cause:** the `PGDATA` line is missing from the compose file. Postgres 18 changed its default data directory, so the `db_storage` volume mounts a folder Postgres no longer writes to, the database happily starts empty. n8n's own docs warn: don't remove that line.

**Fix:** add `PGDATA: /var/lib/postgresql/data` to the postgres service (as in the compose file above) *before* the first start. If the damage is done, restore from your `pg_dumpall` backup.

### 3. OAuth logins fail with redirect_uri mismatch; webhooks show http:// URLs

**Cause:** `WEBHOOK_URL` still points at `http://localhost:5678` (or lacks the trailing slash), so n8n generates callback URLs the OAuth provider never whitelisted. This is the single most common self-hosting misconfiguration.

**Fix:** set `WEBHOOK_URL=https://n8n.yourdomain.com/` (https, your real domain, trailing slash), `N8N_PROTOCOL=https`, restart with `docker compose up -d`, and re-create any credentials that were saved while the URL was wrong, n8n bakes the callback URL into the credential at creation time.

### 4. `Bind for 0.0.0.0:5678 failed: port is already allocated`

**Cause:** another n8n (or another container) already holds the port, typically a leftover from a previous `docker compose up` in a different directory, or an npm-started n8n you forgot about.

**Fix:** find the squatter and stop it:

```bash
docker ps --format '{{.Names}}\t{{.Ports}}' | grep 5678
docker compose down   # in the old project dir, or docker stop <name>
```

I hit the sibling of this locally while verifying 2.40.7: an n8n editor left running blocked a second start the same way. One instance per port, always.

## FAQ

**How much RAM and CPU does a self-hosted n8n instance need?**
A 2 vCPU / 2 GB RAM VPS is comfortable for personal use and small teams, this site itself runs on that class of box. n8n's editor is a Node.js app; memory pressure only becomes real with dozens of concurrent executions or heavy AI workloads. Give Postgres its own headroom if you run both on one machine.

**Is self-hosted n8n really free?**
Yes. The self-hosted Community edition is free with unlimited workflow executions, you only pay for the VPS underneath it. n8n Cloud starts at €24/month for 2,500 executions. The trade-off is that you own maintenance: upgrades, backups, and uptime are your job.

**Can I still install n8n with npm instead of Docker?**
Technically yes, `npm install -g n8n` still works, but you shouldn't for a server. Starting n8n 2.40.7 prints an official deprecation notice: "Running n8n outside a container is deprecated. Future versions will require running n8n via the official Docker image." Docker is the only install path n8n guarantees going forward.

**How do I update n8n to a newer version?**
Back up first, then change the image tag in `docker-compose.yml` to the new pinned version and run `docker compose pull && docker compose up -d`. n8n runs database migrations automatically on startup. Never use the floating `latest` tag on a production instance, pin the version you tested.

**Can I run n8n on the VPS IP address without a domain name?**
For a quick test, yes: `http://YOUR_SERVER_IP:5678` works. For anything real, no, get a domain. Webhook URLs, OAuth redirect URIs, and several app credentials require a stable public HTTPS URL, and browsers increasingly block the mixed-content tricks you'd need without TLS.

**Where are my workflows and credentials actually stored?**
In two places: the `n8n_storage` Docker volume (mounted at `/home/node/.n8n`, holds config and key state) and the Postgres database (workflows, executions, credentials, encrypted with your `N8N_ENCRYPTION_KEY`). Back up both: `pg_dumpall` for Postgres and a tarball of the volume, as shown in step 8.

## Conclusion

You now have a production-shaped n8n on your own VPS: Docker Compose for reproducible deploys, Postgres 18 instead of SQLite, Caddy for zero-touch HTTPS, and a backup routine that actually covers both halves of n8n's state. The npm path is deprecated by n8n itself, so the hour you spent on Docker is also future-proofing.

Next step: put the instance to work. Our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/) builds a real AI agent with tools and memory on a self-hosted instance, [n8n error handling](/n8n-error-handling/) teaches the patterns that keep production workflows alive, and the [n8n category page](/categories/n8n/) collects every n8n guide on this site. If you ever outgrow the VPS, [n8n vs Make for AI agents](/n8n-vs-make-ai-agents/) works through the cost math of moving agent workloads between platforms.
