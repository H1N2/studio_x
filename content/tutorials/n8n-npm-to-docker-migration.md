---
title: "How to Migrate n8n from npm to Docker Before n8n 3.0"
slug: "n8n-npm-to-docker-migration"
description: "Migrate n8n from npm to Docker before n8n 3.0 drops npm support. Back up ~/.n8n, protect the encryption key, and boot a pinned 2.x image first."
date: 2026-10-06
draft: false
categories: ["n8n", "self-hosting"]
tags: ["n8n", "npm", "docker", "migration", "self-hosted", "n8n-3.0", "upgrade", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Do I have to migrate if my npm n8n still works today?"
    a: "Yes, if you want security updates. The npm package stops at the last 2.x release, which keeps receiving security backports, but no new features, and n8n 3.0 removes npm installs entirely. Staying on npm is a deliberate freeze, not a maintenance strategy, so plan the move on your own schedule rather than during an emergency."
  - q: "Will my credentials survive the move to Docker?"
    a: "Yes, if you copy the entire ~/.n8n folder including the config file that holds the encryption key. n8n decrypts stored credentials with that key, so losing it is the one unrecoverable failure in this migration. Verify the key file exists in your backup before you shut anything down."
  - q: "Can I use a bind mount of ~/.n8n instead of a named Docker volume?"
    a: "Yes, and it is the simplest option: mount - ~/.n8n:/home/node/.n8n in your compose file. Make sure the node user inside the container (uid 1000) can read and write that folder. A named volume with an explicit copy step keeps permissions predictable on shared servers, which is why this guide uses it."
  - q: "Should I jump straight from my npm install to the n8n 3.0 image?"
    a: "No. Boot a pinned 2.x image first, matching or close to your npm version, and confirm the database migrates cleanly with everything intact. Only then move the image tag forward. Skipping a major database migration in one leap is how you turn a routine move into a restore drill."
  - q: "What happens to my old npm installation afterwards?"
    a: "Leave it installed but stopped until you are sure the Docker instance is healthy, then disable any systemd service and remove the old autostart. Keep your ~/.n8n backup folder for at least a few weeks. The npm package receives no further feature releases after the 3.0 crossover, so there is no reason to keep it running."
  - q: "Does this migration work on macOS and Windows too?"
    a: "Yes. The data folder move is identical; the only differences are how you install Docker and where ~/.n8n lives on your machine. On macOS and Windows use Docker Desktop, on a headless Linux server use Docker Engine plus the Compose plugin."
---

## Introduction

If you run n8n from `npx n8n` or a global `npm install n8n -g`, your installation has an expiry date. n8n 3.0, scheduled for October 2026, drops support for npm-based installs entirely, and the `n8n` package on npm stops at the last 2.x release. This guide migrates a working npm install to Docker Compose without losing workflows, credentials, or execution history. It is written for self-hosters on a VPS or home server who installed n8n the quick way years ago and now need the supported path. If you followed our [Ubuntu VPS install guide](https://www.161808.xyz/install-n8n-ubuntu-vps/), the backup habits from that post apply here too.

## Quick answer

Stop npm n8n, back up ~/.n8n including the encryption key, install Docker, copy the data into a volume mounted at /home/node/.n8n, and boot a pinned 2.x image once before moving to 3.0.

## Evidence

The vendor's own words leave no room for interpretation. The official [n8n 3.0 breaking changes document](https://github.com/n8n-io/n8n-docs/blob/HEAD/docs/changelog/v30-breaking-changes.md) states: "Self-hosted n8n will require a Docker-based deployment. n8n 3.0 will no longer support installations run using `npm` or `npx n8n`." The same page adds: "If you run n8n with `npm` or `npx n8n`, plan a move to a Docker-based deployment before upgrading to n8n 3.0. For local installations, Docker Compose is expected to be the easiest path." That is the whole case for this article in two sentences, straight from the n8n documentation team.

The npm package is not being deleted, but it is being frozen. Contributor Flexicon wrote in the [PR that stops publishing the n8n package to npm](https://github.com/n8n-io/n8n/pull/38278): "The package on npm stays at the last 2.x release, which keeps receiving security backports, and is deprecated manually after the v3 crossover." In other words, your npm install keeps breathing on security fixes, but every new feature, node, and AI capability from 3.0 onward only ships in the Docker image.

Two numbers show how far the ecosystem has already moved. The n8n repository held 206,739 GitHub stars as of 6 October 2026, and the official `n8nio/n8n` image had accumulated 268,155,952 pulls on Docker Hub by the same date. Docker is not an experimental path for n8n; it is where nearly all of that usage already lives. On the npm side, the current install path is already the strict one: the official [npm installation guide](https://docs.n8n.io/deploy/host-n8n/install-options/install-with-npm) requires Node.js between 20.19 and 24.x and warns that npm installs are deprecated from n8n 3.0. The official [Docker Compose installation guide](https://docs.n8n.io/deploy/host-n8n/install-options/install-using-docker-compose) is where the 3.0-era docs point every self-hoster now.

## Prerequisites

- A working npm or npx n8n install (1.x or 2.x) with access to its data folder, normally `~/.n8n`.
- Shell access to the same machine with sudo rights, so you can install Docker.
- Roughly one hour and a maintenance window: your workflows pause while you move them.
- A disk backup habit. If you have never backed up this instance, read our [n8n backup and restore guide](https://www.161808.xyz/n8n-backup-restore/) first; the migration is a terrible time to discover you cannot restore.

## Step 1: Record your current version and environment

Before touching anything, capture the baseline. On the machine running n8n:

```bash
n8n --version
node --version
ls -la ~/.n8n
```

Note the n8n version (something like `2.41.4`) and the Node version. The npm docs require Node 20.19 through 24.x for 2.x, so this output also tells you whether your npm environment was even current. The `ls` output should show `config`, `database.sqlite`, and folders like `nodes` and `storage`. Our lab npm install of n8n 2.41.4 shows exactly this layout, and its `config` file contains a single key, `encryptionKey`, which is the credential decryption key you must preserve.

If you run n8n through a systemd service or a process manager, also save how it starts. Check `systemctl cat n8n` or your `~/.profile` for environment variables like `N8N_PORT`, `N8N_HOST`, `WEBHOOK_URL`, or `N8N_ENCRYPTION_KEY`. You will translate those into the Compose file in Step 5, and forgetting `WEBHOOK_URL` is the classic reason production webhooks stop working after a move.

## Step 2: Stop n8n and make a real backup

Stop the running instance so the SQLite database is not being written while you copy it. For a foreground process, press Ctrl+C. For a background one, find and stop it:

```bash
pkill -f "n8n start"
sleep 3
pgrep -fa n8n | grep -v pkill || echo "n8n is stopped"
```

Now copy the entire data folder. The `config` file with the encryption key is small and easy to miss with a selective copy, so take everything:

```bash
cp -a ~/.n8n ~/n8n-backup-2026-10-06
ls ~/n8n-backup-2026-10-06
du -sh ~/.n8n ~/n8n-backup-2026-10-06
```

Verify two things: the backup listing contains `config` and `database.sqlite`, and the two `du` sizes match. As a second safety net, export all workflows with the CLI:

```bash
n8n export:workflow --all --output=~/n8n-backup-2026-10-06/workflows-export/
```

This export is JSON you can re-import anywhere, independent of the database. It does not include credentials, which is exactly why the full folder copy in the previous command is non-negotiable.

## Step 3: Install Docker and the Compose plugin

Follow the official [Docker Engine installation guide for Ubuntu](https://docs.docker.com/engine/install/ubuntu/) for your platform; on macOS or Windows install Docker Desktop. Verify both pieces:

```bash
docker --version
docker compose version
```

The second command must succeed. Docker Compose V2 is a plugin (`docker compose`, with a space), and the migration files in this guide assume it. Add your user to the `docker` group so you are not typing sudo for every compose command, then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

## Step 4: Create the Compose project with a pinned 2.x image

Create a project folder and a `docker-compose.yml`. The critical decision is the image tag: pin it to the 2.x line first, ideally the same version your npm install ran. If you were on npm n8n 2.41.4, use that tag for the migration:

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:2.41.4
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - GENERIC_TIMEZONE=Asia/Shanghai
      - TZ=Asia/Shanghai
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
```

Replace the tag with your own npm version if it differs, and set the timezone to yours. Translate any environment variables you recorded in Step 1 into this `environment` block: `WEBHOOK_URL`, `N8N_HOST`, and `N8N_PROTOCOL` are the ones production instances usually need. The `n8n_data:/home/node/.n8n` mount is the heart of the migration: `/home/node/.n8n` is where the containerized n8n keeps its data, the same role `~/.n8n` plays for npm installs.

## Step 5: Move your data into the Docker volume

Create the named volume and copy your backup into it, fixing ownership as you go. The n8n container runs as the `node` user with uid 1000, and files copied in as root are unreadable to it, which produces a confusing "permission denied" crash on startup. This two-line copy avoids it:

```bash
docker volume create n8n_n8n_data
docker run --rm -v n8n_n8n_data:/target -v ~/n8n-backup-2026-10-06:/source:ro \
  alpine sh -c "cp -a /source/. /target/ && chown -R 1000:1000 /target"
docker run --rm -v n8n_n8n_data:/data alpine ls -la /data | head
```

The `:ro` on the source mount protects your backup from accidents, and the final listing proves `config` and `database.sqlite` landed in the volume with `node`-readable ownership. Note that Compose prefixes the volume with the project folder name (`n8n_n8n_data`), which is why the volume in this command differs slightly from the one in the YAML; run `docker volume ls` if yours was created under a different project name.

## Step 6: Start the container and watch the database migrate

Bring the stack up and tail the logs. The first boot replays any pending database migrations for the 2.x line, so give it a minute:

```bash
cd ~/n8n-docker
docker compose up -d
docker compose logs -f n8n
```

Healthy output ends with n8n listening on port 5678 and a line about the editor being reachable. You will also see migration lines if your npm install was behind the pinned image's schema version. If the container exits immediately, the logs tell you why; the most common causes are in the troubleshooting section below.

Open `http://<your-server-ip>:5678` in a browser and log in with your existing owner account. Check three things in order: workflows are all present, credentials still test successfully (this proves the encryption key survived), and execution history shows your past runs. Run one safe workflow manually to confirm executions actually work, not just list.

## Step 7: Point traffic at Docker and retire the npm install

If you had a reverse proxy (Caddy, Nginx) or firewall rule pointing at the npm process on port 5678, it needs no change as long as the container publishes the same port; the proxy cannot tell which runtime answers. If your npm n8n ran on a different port via `N8N_PORT`, update the proxy or the compose `ports` mapping to match.

Once the Docker instance has run cleanly for a few days, disable the old autostart. For systemd:

```bash
sudo systemctl disable --now n8n
```

Keep the `~/n8n-backup-2026-10-06` folder for at least a month. When you are ready for n8n 3.0 itself, the upgrade is a one-line change of the image tag in `docker-compose.yml`; updating going forward is covered in our [n8n update guide](https://www.161808.xyz/how-to-update-n8n-self-hosted/).

## Troubleshooting

### Credentials show "couldn't decrypt" errors

Cause: the `config` file holding the encryption key did not make it into the volume. Every stored credential is encrypted with that key, and a fresh container generates a different one, so old credentials become unreadable. Fix: stop the container, re-run the copy from Step 5 using the backup that contains `config`, and start again. Verify the key file exists inside the volume with `docker run --rm -v n8n_n8n_data:/data alpine ls /data/config`. If the original `~/.n8n/config` is gone and no backup exists, the credentials are unrecoverable; you must re-create them and re-enter each secret.

### The editor shows zero workflows after migration

Cause: the container booted against an empty volume, usually because the volume name in the copy command did not match the one Compose created, so your data went to an orphan volume. Fix: run `docker volume ls` and compare with the volume Compose actually mounted (`docker compose config | grep -A2 volumes`). Copy the data into the correct volume, or set an explicit volume name in the YAML with `name: n8n_data` under the volume definition to remove the prefix guessing entirely.

### Container crash-loops with "permission denied" on /home/node/.n8n

Cause: the data files are owned by root from the copy step, but the container runs as uid 1000. Fix: stop the stack and re-run the `chown -R 1000:1000` inside the copy command from Step 5. Never "fix" this by running the container as root; the official image is designed around the `node` user and root mode is unsupported.

### Old npm 1.x install: database errors on first Docker boot

Cause: jumping from a 1.x database straight to a late 2.x or 3.0 image can hit schema migrations that expect intermediate versions. Fix: pin the compose image to an early 2.x tag first, boot once, confirm the editor loads, then step the tag forward to your target 2.x and boot again. Each boot replays that line's migrations in order. Only move to 3.0 after the 2.x line is fully healthy.

### Port 5678 is already in use

Cause: the old npm n8n process is still running, or a second container grabbed the port. Fix: `ss -ltnp | grep 5678` shows the owner; stop the stray process with `pkill -f "n8n start"` or `docker compose down` in the other project folder. Only one n8n may bind the port at a time.

## FAQ

The on-page questions above cover the decisions readers ask about most: whether the move is mandatory, how credentials survive, bind mounts versus named volumes, the 2.x-first rule, retiring the old install, and platform differences. The short version of all of them: migrate on your own schedule while npm still runs, keep the encryption key, and let each major version's migrations run in order.

## Conclusion

Moving n8n from npm to Docker is a data move with a version pin, not a reinstall. Back up the whole `~/.n8n` folder, protect the encryption key, pin the image to your current 2.x line, and verify workflows, credentials, and execution history before you retire the npm process. Done this way, the migration takes under an hour and n8n 3.0 becomes a one-tag upgrade. Next, refresh your Compose fundamentals with our [n8n Docker Compose setup guide](https://www.161808.xyz/n8n-docker-compose-setup/) and keep the instance current with the [n8n update guide](https://www.161808.xyz/how-to-update-n8n-self-hosted/).
