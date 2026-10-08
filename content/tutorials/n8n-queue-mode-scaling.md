---
title: "n8n Queue Mode Scaling Tutorial: Run Worker Processes with Redis (2026)"
slug: "n8n-queue-mode-scaling"
date: 2026-10-04
draft: false
description: "Run n8n in queue mode: a main instance plus Redis-backed worker processes for parallel executions. Docker Compose setup guide, verified on n8n 2.41.4."
categories: ["n8n"]
tags: ["n8n", "queue-mode", "scaling", "redis", "docker-compose", "workers", "self-hosted", "performance", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "How many n8n workers do I need in queue mode?"
    a: "Start with two workers and watch your execution queue. Each worker runs up to 10 jobs in parallel by default (the --concurrency flag), so two workers already handle roughly 20 concurrent executions. Scale up with docker compose up -d --scale when executions start waiting."
  - q: "Can n8n workers run on separate machines?"
    a: "Yes. The official docs confirm workers can live on other machines as long as every worker can reach the same Redis instance and the same n8n database. The encryption key must also match the main instance on every machine."
  - q: "Do I need Postgres to use n8n queue mode?"
    a: "Postgres is strongly recommended. The n8n docs explicitly say running queue mode with an SQLite database is not recommended, because every worker reads workflow definitions and writes results through the shared database."
  - q: "How do I monitor whether my n8n workers are healthy?"
    a: "Set QUEUE_HEALTH_CHECK_ACTIVE=true on the workers. Each worker then exposes /healthz (is the worker up) and /healthz/readiness (are its database and Redis connections ready), which load balancers and uptime monitors can poll."
  - q: "Does the main n8n instance still execute workflows in queue mode?"
    a: "No. In queue mode the main instance handles triggers, timers, and webhook calls, then hands each execution ID to Redis. Worker processes pick up the jobs and run them. The main instance never executes workflow logic itself."
  - q: "Will queue mode make one slow workflow run faster?"
    a: "No. Queue mode parallelizes across executions, not within a single execution. One workflow with a 60-second API call still takes 60 seconds. Queue mode helps when many executions pile up at once, for example hundreds of webhook calls arriving together."
---

## Introduction

This tutorial is for self-hosters whose n8n instance has started to groan: webhook calls timing out, scheduled runs piling up behind each other, the editor freezing while a big execution churns. You will convert a standard single-process n8n install into a queue-mode cluster: one main instance that receives triggers, a Redis-backed job queue, and a pool of worker processes that run executions in parallel, all wired together with Docker Compose.

## Quick answer

Set EXECUTIONS_MODE=queue on the main n8n instance and every worker, share one N8N_ENCRYPTION_KEY, point QUEUE_BULL_REDIS_HOST at Redis, and launch workers with `n8n worker`. Use Postgres, not SQLite, for the n8n database.

## Evidence

Scaling claims are easy to make and hard to verify, so here is what is actually documented and measured, timestamped October 2026.

First, the demand is real: as of October 4, 2026, the n8n repository has **206,587 stars on GitHub** (verified directly against the GitHub API), making it one of the most-starred automation projects in the world. A large share of those users eventually self-host, which is exactly when scaling questions appear.

Second, n8n publishes its own benchmark numbers. The [official performance documentation](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/measure-performance/) states that a single n8n instance can handle **up to 220 workflow executions per second**, "with the ability to scale up further by adding more instances." That second clause is the entire point of queue mode: throughput grows by adding workers, not by buying a bigger single server.

Third, the vendor's own guidance is unambiguous. The [queue mode documentation](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode/) opens with this verdict: "The queue mode provides the best scalability." When the team that built the software tells you which mode scales best, that settles the architecture choice.

The [n8n GitHub repository](https://github.com/n8n-io/n8n) also ships a benchmarking framework under `packages/@n8n/benchmark`, so you can reproduce throughput numbers on your own hardware instead of trusting anyone's blog post, including this one.

## Prerequisites

- A server or local machine with Docker Engine and Docker Compose v2 installed.
- A Postgres database for n8n (version 13 or newer; the docs list supported versions, and queue mode with SQLite is explicitly not recommended).
- Redis 6 or newer, reachable from every n8n container.
- n8n 2.x (this guide was verified against n8n 2.41.4, including the real `n8n worker --help` output).
- Comfort editing a `docker-compose.yml` file and reading container logs.
- If you have not self-hosted n8n before, read our [n8n Docker Compose setup guide](https://www.161808.xyz/n8n-docker-compose-setup/) first; this tutorial builds directly on that single-instance layout.

## Step-by-step guide

### Step 1. Understand what queue mode changes

In the default `main` mode, one n8n process does everything: it serves the editor, fires schedule triggers, receives webhooks, and executes workflows. Under load, executions compete with the editor and with each other inside that single Node.js process.

Queue mode splits the job. The [official queue mode flow](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode/) works like this: the main instance still handles timers and webhook calls, but instead of running the workflow it drops the execution ID into Redis. Worker processes, each running `n8n worker`, pick jobs off the Redis queue, fetch the workflow definition from the shared database, run it, write results back to the database, and tell Redis the job is done. You scale throughput by adding workers, and you scale down by removing them, without touching the main instance.

### Step 2. Start Redis

Redis is the message broker between the main instance and the workers. The official docs start it with a single Docker command:

```bash
docker run --name some-redis -p 6379:6379 -d redis
```

By default Redis listens on port 6379 with no password, which is fine for a first test on a private network. For the full cluster below, Redis runs as a Compose service instead, so skip the standalone container if you follow Step 4. If you run Redis on a separate machine, make sure every n8n host can reach it over the network; Redis itself does not need to be on the same box as n8n.

### Step 3. Put n8n on Postgres before you scale

Every worker reads workflow definitions from the database and writes execution results back to it, so the database becomes shared infrastructure. n8n's docs warn directly: "Running n8n with execution mode set to queue with an SQLite database isn't recommended." SQLite is a single file with coarse locking, and concurrent workers will fight over it.

If you are still on SQLite, migrate first. Our [n8n Postgres tutorial](https://www.161808.xyz/n8n-postgres-tutorial/) walks through connecting n8n to Postgres step by step, including the exact `DB_POSTGRESDB_*` variables used below. Queue mode only starts paying off once the database can handle concurrent writers.

### Step 4. Write the Docker Compose file

Create a project directory and save this as `docker-compose.yml`. It defines four roles: Postgres, Redis, the main n8n instance, and a worker service you can scale to any replica count.

```yaml
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: change-this-password
      POSTGRES_DB: n8n
    volumes:
      - n8n_postgres:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - n8n_redis:/data

  n8n-main:
    image: n8nio/n8n:2.41.4
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=change-this-password
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=redis
      - QUEUE_BULL_REDIS_PORT=6379
      - N8N_ENCRYPTION_KEY=replace-with-output-of-openssl-below
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres
      - redis

  n8n-worker:
    image: n8nio/n8n:2.41.4
    restart: unless-stopped
    command: worker --concurrency=10
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=change-this-password
      - EXECUTIONS_MODE=queue
      - QUEUE_BULL_REDIS_HOST=redis
      - QUEUE_BULL_REDIS_PORT=6379
      - N8N_ENCRYPTION_KEY=replace-with-output-of-openssl-below
    depends_on:
      - postgres
      - redis

volumes:
  n8n_postgres:
  n8n_redis:
  n8n_data:
```

Three details in this file come straight from the official docs. First, `EXECUTIONS_MODE=queue` is the single switch that puts both the main instance and the workers into queue mode. Second, `QUEUE_BULL_REDIS_HOST` and `QUEUE_BULL_REDIS_PORT` tell n8n where Redis lives; inside Compose, the hostname is the service name `redis`, not `localhost`. Third, the worker container overrides the default start command with `worker --concurrency=10`, which matches the real CLI verified on n8n 2.41.4 (`n8n worker --help` shows `--concurrency` defaulting to 10).

### Step 5. Generate and share one encryption key

n8n encrypts credentials in its database. The docs require the main instance's encryption key to be shared with every worker, or workers cannot decrypt credentials when they run workflows. Generate a key once:

```bash
openssl rand -base64 32
```

Paste the output as `N8N_ENCRYPTION_KEY` in both the `n8n-main` and `n8n-worker` services. Every worker must carry the identical value. If you already have an n8n instance with existing credentials, reuse its current key instead of generating a new one, or the workers will fail to decrypt everything the main instance encrypted.

### Step 6. Launch the cluster

```bash
docker compose up -d
docker compose ps
```

`docker compose ps` should show all four services running. Now scale the workers to two:

```bash
docker compose up -d --scale n8n-worker=2
```

Note that `--scale` works with plain `docker compose up`; the `deploy.replicas` key in a compose file only applies to Swarm mode, so the command-line flag is the correct approach here.

### Step 7. Verify that workers are picking up jobs

Open the editor at `http://<your-server>:5678` and run any workflow manually, then open the Executions list. The execution should complete normally even though the main instance never runs workflow code itself in queue mode.

For stronger proof, fire several webhook executions at once and watch the worker logs:

```bash
docker compose logs -f n8n-worker
```

With two workers at the default concurrency of 10, the cluster can run roughly 20 executions simultaneously. If you previously followed our [Ubuntu VPS install guide](https://www.161808.xyz/install-n8n-ubuntu-vps/), this is the moment the single-process ceiling disappears: adding a third worker is one `--scale` flag away, no migration needed.

### Step 8. Set up health checks for production

Each worker can expose health endpoints for your load balancer or uptime monitor. Add this to the worker's environment:

```yaml
- QUEUE_HEALTH_CHECK_ACTIVE=true
```

The docs list what each endpoint returns: `/healthz` reports whether the worker is up, and `/healthz/readiness` reports whether its database and Redis connections are ready. Point your monitoring at the readiness endpoint so an unhealthy worker gets replaced instead of silently receiving jobs it cannot run.

## Troubleshooting

### Workers fail with credential decryption errors

**Symptom:** workflows run fine when triggered on the main instance in regular mode, but fail on workers with errors about being unable to decrypt credentials.

**Cause:** the `N8N_ENCRYPTION_KEY` on the workers does not match the key the main instance used to encrypt the credentials. The docs state the main instance's key "must be shared with all worker and webhook processor nodes."

**Fix:** copy the exact `N8N_ENCRYPTION_KEY` value from the main instance into every worker's environment and recreate the worker containers with `docker compose up -d --force-recreate n8n-worker`. Do not generate a fresh key on an instance that already holds encrypted credentials.

### Executions stall or the database locks up under load

**Symptom:** everything works with one worker, but adding workers makes executions hang or the database throws locking errors.

**Cause:** you are running queue mode against SQLite. The official docs explicitly say queue mode with SQLite "isn't recommended," because concurrent workers contend on a single database file.

**Fix:** move n8n to Postgres using the `DB_POSTGRESDB_*` variables from Step 4, following our [n8n Postgres tutorial](https://www.161808.xyz/n8n-postgres-tutorial/) for the migration. Postgres handles concurrent readers and writers, which is exactly what a worker pool needs.

### Workflows that handle files fail in queue mode

**Symptom:** workflows using binary data (file downloads, attachments, images) worked in regular mode but break once queue mode is enabled.

**Cause:** n8n does not support queue mode with binary data stored on the filesystem. A worker on one machine cannot read a temp file written by a worker on another, and even on one machine the filesystem handoff is unsupported.

**Fix:** switch binary data to external S3-compatible storage, as the docs recommend. Set the S3 storage variables on the main instance and every worker so all processes read and write the same object store.

### Workers crash-loop with Redis connection refused

**Symptom:** worker containers restart continuously, and the logs mention being unable to connect to Redis at `localhost:6379`.

**Cause:** `QUEUE_BULL_REDIS_HOST` is set to `localhost`. Inside a container, `localhost` means the container itself, not your Redis service.

**Fix:** set `QUEUE_BULL_REDIS_HOST` to the Compose service name (`redis` in the file above) or to the real hostname/IP of your Redis server. Verify from inside the worker container with `docker compose exec n8n-worker sh -c 'getent hosts redis'` or simply check that the value is not `localhost`.

### Workers exit when Redis restarts

**Symptom:** a brief Redis restart takes down all workers, and they do not come back on their own.

**Cause:** n8n waits `QUEUE_BULL_REDIS_TIMEOUT_THRESHOLD` milliseconds (default 10 seconds) for Redis before exiting. If Redis is down longer than that during a restart, workers shut down.

**Fix:** keep `restart: unless-stopped` on the worker service so Compose brings them back, and consider raising `QUEUE_BULL_REDIS_TIMEOUT_THRESHOLD` if your Redis restarts slowly. The related `N8N_GRACEFUL_SHUTDOWN_TIMEOUT` (default 30 seconds) controls how long workers get to finish in-flight jobs before terminating.

## FAQ

### How many n8n workers do I need in queue mode?

Start with two workers and watch your execution queue. Each worker runs up to 10 jobs in parallel by default (the --concurrency flag), so two workers already handle roughly 20 concurrent executions. Scale up with docker compose up -d --scale when executions start waiting.

### Can n8n workers run on separate machines?

Yes. The official docs confirm workers can live on other machines as long as every worker can reach the same Redis instance and the same n8n database. The encryption key must also match the main instance on every machine.

### Do I need Postgres to use n8n queue mode?

Postgres is strongly recommended. The n8n docs explicitly say running queue mode with an SQLite database is not recommended, because every worker reads workflow definitions and writes results through the shared database.

### How do I monitor whether my n8n workers are healthy?

Set QUEUE_HEALTH_CHECK_ACTIVE=true on the workers. Each worker then exposes /healthz (is the worker up) and /healthz/readiness (are its database and Redis connections ready), which load balancers and uptime monitors can poll.

### Does the main n8n instance still execute workflows in queue mode?

No. In queue mode the main instance handles triggers, timers, and webhook calls, then hands each execution ID to Redis. Worker processes pick up the jobs and run them. The main instance never executes workflow logic itself.

### Will queue mode make one slow workflow run faster?

No. Queue mode parallelizes across executions, not within a single execution. One workflow with a 60-second API call still takes 60 seconds. Queue mode helps when many executions pile up at once, for example hundreds of webhook calls arriving together.

## Conclusion

Queue mode turns n8n from a single process into a small cluster: the main instance takes triggers, Redis holds the job queue, and worker processes execute in parallel against a shared Postgres database. The whole setup is a handful of environment variables plus one `n8n worker` command, and scaling is a `--scale` flag.

Once your cluster is running, the next bottleneck is usually visibility into failures, so read our [n8n error handling tutorial](https://www.161808.xyz/n8n-error-handling/) next. And when n8n ships updates, our [guide to updating self-hosted n8n](https://www.161808.xyz/how-to-update-n8n-self-hosted/) covers rolling the new image across the main instance and every worker without losing queued jobs.
