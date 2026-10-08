---
title: "n8n 3.0 Upgrade Guide: The Breaking Changes Checklist Before You Update"
slug: "n8n-3-0-upgrade-guide"
description: "Upgrading to n8n 3.0? This checklist covers every breaking change: Docker-only deployment, 35+ removed nodes, security defaults, and a staged upgrade path."
date: 2026-10-06
draft: false
categories: ["n8n", "self-hosting"]
tags: ["n8n", "n8n-3.0", "upgrade", "breaking-changes", "docker", "self-hosted", "migration", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "When is n8n 3.0 released?"
    a: "n8n 3.0 is scheduled for October 2026, according to the official breaking changes document. The exact release date can still shift, so check the n8n GitHub releases page before planning a maintenance window. Everything in this checklist is based on the documented breaking changes, which are already final."
  - q: "Can I keep running n8n with npm after 3.0?"
    a: "No. n8n 3.0 will no longer support installations run using npm or npx n8n, and the 3.0 line does not publish a runnable n8n package to npm. Migrate to a Docker-based deployment before you upgrade. Our npm to Docker migration guide walks through the move, including the encryption key backup that keeps your credentials intact."
  - q: "Do I have to migrate my Function nodes by hand?"
    a: "Yes. The legacy Function and Function Item nodes are removed in 3.0, so each one must be rebuilt as a Code node before you upgrade. Use Run Once for All Items mode in place of Function and Run Once for Each Item mode in place of Function Item. The code usually carries over unchanged, but test every execution afterwards."
  - q: "Will the Settings > Migration Report catch every problem?"
    a: "It catches the structural problems: affected nodes such as Execute Sub-workflow with Local File or URL sources, Chat Hub usage, and removed environment variables. It does not rewrite your workflows. Pair it with an exported-JSON inventory of node types and walk the removed-node list in this guide, so nothing slips through unnoticed."
  - q: "What happens to Chat Hub in n8n 3.0?"
    a: "Chat Hub is turned off by default. The Chat section disappears from the navigation and the Chat Hub endpoints stop responding, but your chat sessions, agents, and messages stay in the database. To keep it, add chat-hub to N8N_ENABLED_MODULES, and plan a migration before n8n 4.0 removes the feature entirely."
  - q: "Is there anything that migrates automatically?"
    a: "Only AI Transform nodes. n8n automatically migrates them to Code nodes on upgrade, keeping the same generated JavaScript, so those workflows keep working without changes. Every other removed node in this guide needs a manual replacement before you upgrade."
---

## Introduction

n8n 3.0, scheduled for October 2026, is the most disruptive release in the project's recent history. It ends npm and npx installs for self-hosters, removes more than 35 legacy nodes and helpers, retires Chat Hub, and tightens security defaults that change how Code nodes, community packages, and webhooks behave. This guide is the pre-upgrade checklist for anyone running a production 2.x instance, on Docker or npm, who owns workflows that must keep working the morning after the upgrade. If you have not yet moved off npm, read our [npm to Docker migration guide](https://www.161808.xyz/n8n-npm-to-docker-migration/) alongside this one, because that move is now mandatory.

## Quick answer

Back up workflows and credentials, move off npm/npx to Docker, replace legacy nodes like Function and Item Lists with the Code node, and read Settings > Migration Report before upgrading to n8n 3.0; upgrade in stages and test each phase.

## Evidence

The vendor's own words frame the whole release. The official [n8n 3.0 breaking changes document](https://github.com/n8n-io/n8n-docs/blob/HEAD/docs/changelog/v30-breaking-changes.md) states: "n8n 3.0 will no longer support installations run using `npm` or `npx n8n`." The same page opens with the project's stated goal: "The release of n8n 3.0 continues n8n's commitment to providing a secure, reliable, and production-ready automation platform." This is not a feature update with a few deprecations. It is a deliberate cleanup of years of accumulated legacy, and the documentation says so plainly.

The scale matters. n8n's repository held 206,739 GitHub stars as of 6 October 2026, and the official `n8nio/n8n` image had accumulated 268,155,952 pulls on Docker Hub by the same date. When a project of that size removes its npm install path and more than 35 legacy node types in one release, the only safe response is preparation. The pull number also explains why Docker-only is survivable: the image already hosts the overwhelming majority of real usage, and the official [Docker Compose installation guide](https://docs.n8n.io/deploy/host-n8n/install-options/install-using-docker-compose) is now the single supported self-host path.

## Prerequisites

You need admin access to the n8n instance, comfort editing workflows and a `docker-compose.yml` file, and a maintenance window of at least two hours. First, make a full backup: export every workflow and credential with the CLI, and copy the entire `~/.n8n` data folder, because its `config` file holds the encryption key that decrypts every stored credential. Our [backup and restore tutorial](https://www.161808.xyz/n8n-backup-restore/) covers the export commands; our lab npm install of n8n 2.41.4 confirmed the `config` file contains exactly one key, `encryptionKey`. Losing that file is the one unrecoverable failure here. You also need Docker Engine with the Compose plugin, and a list of every environment variable your instance sets.

## Step-by-step guide

### Step 0: If you install with npm or npx, migrate to Docker first

This step is non-negotiable. The official document says: "If you run n8n with `npm` or `npx n8n`, plan a move to a Docker-based deployment before upgrading to n8n 3.0. For local installations, Docker Compose is expected to be the easiest path." There is no upgrade path from npm to 3.0, because 3.0 does not publish a runnable package to npm. Follow our [npm to Docker migration guide](https://www.161808.xyz/n8n-npm-to-docker-migration/) end to end: back up `~/.n8n` including the `config` file with the encryption key, mount the data into a Docker volume at `/home/node/.n8n`, boot a pinned 2.x image first, and confirm everything works there. Do the migration and the 3.0 upgrade as two separate maintenance windows.

### Step 1: Run the Migration Report and the startup warnings

On your 2.x instance, open **Settings > Migration Report**. The official document names this report as the place where affected nodes and instances are listed before you update: Execute Sub-workflow nodes still using the Local File or URL source, instances where Chat Hub is in use, and removed environment variables like `N8N_PRE_EXECUTE_ERROR_CREATES_EXECUTION`. Fix every row before you touch the image tag. Also watch the container logs at startup: n8n 2.x logs a deprecation warning for each configuration 3.0 will change, so one startup log scan is a free audit of your environment variables.

### Step 2: Inventory every workflow for removed nodes

The removal list is long, and memory is unreliable, so inventory mechanically. Export everything with the CLI:

```bash
mkdir -p ~/n8n-30-backup/workflows ~/n8n-30-backup/credentials
n8n export:workflow --all --output=~/n8n-30-backup/workflows/
n8n export:credentials --all --output=~/n8n-30-backup/credentials/
cp -r ~/.n8n ~/n8n-30-backup/n8n-data-folder
```

Then list every node type used across your exported workflows:

```bash
cd ~/n8n-30-backup/workflows
grep -rho '"type": "[^"]*"' . | sort | uniq -c | sort -rn
```

Compare that inventory against the removed list below. Any workflow containing a removed node must be edited before upgrading. Save this export permanently; it is also your rollback package.

### Step 3: Replace every removed node

The list below pairs each removal with its official replacement. Work down your inventory and migrate each one while still on 2.x, testing the new node on the old version.

**Code and list operations.** Replace the legacy **Function** and **Function Item** nodes with the Code node: **Run Once for All Items** in place of Function, **Run Once for Each Item** in place of Function Item. The JavaScript usually carries over unchanged. Replace **Item Lists** with the node matching the operation you use: Split Out, Aggregate, Sort, Limit, Remove Duplicates, or Summarize. Our [Code node tutorial](https://www.161808.xyz/n8n-code-node-javascript/) walks through both run modes with real examples. Note that `$evaluateExpression()` is removed from the Code node, affecting only insecure task runners; evaluate the expression in a node field instead, for example in an Edit Fields (Set) node before the Code node.

**Triggers, files, and scheduling.** Replace **Cron** and **Interval** with the Schedule Trigger node, and **Workflow Trigger** with the n8n Trigger node. Replace **HTML Extract** with the HTML node's Extract HTML Content operation, **iCalendar** with Convert to File's Convert to ICS operation, **Convert to/from binary data** with Convert to File or Extract from File, **Read Binary File(s)** and **Write Binary File** with Read/Write Files from Disk, and **Read PDF** with Extract from File's Extract From PDF operation.

**AI and LangChain nodes.** Replace the legacy **OpenAI** node and **OpenAI Assistant** node with the current OpenAI node (Assistant resource for assistant use cases), **OpenAI Model** with the OpenAI Chat Model node, and the legacy **HTTP Request Tool** with the HTTP Request node connected to the AI Agent node's Tool input. Replace **Manual Chat Trigger** with the Chat Trigger node and **Chat Messages Retriever** with the Chat Memory Manager node. Replace the **Binary Input Loader**, **JSON Input Loader**, and **GitHub Document Loader** with the Default Data Loader node; for GitHub content, fetch it with the GitHub node first. Replace the old vector store **Insert** and **Load** node pairs with the single node for that store (Simple Vector Store, Pinecone Vector Store, or Supabase Vector Store), choosing the operation in the node. **AI Transform** nodes need no action: n8n automatically migrates them to Code nodes on upgrade, keeping the same generated JavaScript.

**Nodes with no replacement.** Motorhead and Zep memory nodes, the Zep Vector Store nodes, and SerpApi have no direct replacement. Move Motorhead and Zep memory to another supported memory or vector store node. For SerpApi, call its REST API with the HTTP Request node connected as a tool, or use a verified community node. The Orbit node is gone because the Orbit service itself shut down.

**AI Agent v1.** n8n 3.0 removes version 1 of the AI Agent node, along with the SQL Agent, Conversational Agent, OpenAI Functions Agent, Plan and Execute Agent, and ReAct Agent modes. Update every workflow that uses AI Agent v1 to the latest version; workflows already set to Tools Agent continue to behave the same. For SQL Agent use cases, use a Postgres or MySQL tool sub-node paired with a recent AI Agent node. Our [n8n AI Agent tutorial](https://www.161808.xyz/n8n-ai-agent-tutorial/) documents the current node setup, which is the target state.

**Expression helpers.** n8n 3.0 removes the deprecated `$getPairedItem` expression helper. Use n8n's standard item linking instead, for example the `pairedItem` property or `$("<node-name>").item`.

### Step 4: Fix removed and re-defaulted configuration

The breaking changes hit configuration as well as nodes. Go through your environment variable list against these changes while still on 2.x, where the startup deprecation warnings confirm what the instance actually sets.

- **Remove `N8N_PRE_EXECUTE_ERROR_CREATES_EXECUTION`.** 3.0 removes the variable entirely. If a `workflow.preExecute` external hook throws, n8n never creates an execution record, so the run never starts and does not count toward Insights or license usage. Remove the variable before upgrading.
- **Rename the storage directory.** On first start, 3.0 renames `~/.n8n/binaryData` to `~/.n8n/storage`, and `N8N_MIGRATE_FS_STORAGE_PATH` is removed. If you mount a volume at the old path, mount it at `~/.n8n/storage` instead, or set `N8N_STORAGE_PATH` to the old path. If both directories exist, n8n does not start: move the contents of `binaryData` into `storage` and remove `binaryData` first.
- **Set a valid binary data mode.** `N8N_DEFAULT_BINARY_DATA_MODE=default` is no longer valid; instances that still use it switch to `filesystem` on upgrade. Set it explicitly to `filesystem`, `s3`, `azure`, or `database`, and check that your container's mounted disk has room for binary data.
- **Decide on unverified community packages.** The default for `N8N_UNVERIFIED_PACKAGES_ENABLED` changes from `true` to `false`. If you install unverified community nodes from npm, set it to `true` to keep installing them, or switch to verified packages first.
- **Restore the task runner timeout if you need it.** The default for `N8N_RUNNERS_TASK_TIMEOUT` drops from 300 seconds to 60. Any Code node task that runs longer than a minute fails, so set the variable explicitly if your tasks need more time.
- **Remove `OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS`.** Manual executions always run on workers in queue mode now. Remove the variable and review worker memory, since workers now also handle manual executions.
- **Replace `N8N_DB_PING_TIMEOUT`.** 3.0 no longer falls back to it; set `DB_PING_TIMEOUT_MS` instead.
- **Fix Execute Sub-workflow sources.** 3.0 removes the Local File and URL options from the Source parameter; nodes that still use them fail with an error. Import the sub-workflow into your instance and use the Database source, or paste its JSON with the Define Below source.

### Step 5: Decide what to do about Chat Hub

n8n 3.0 turns off the Chat Hub module by default: the Chat section disappears from the navigation and the endpoints stop responding, while sessions, agents, and messages stay in the database. If you still need it, add `chat-hub` to `N8N_ENABLED_MODULES` (for example `N8N_ENABLED_MODULES=agents,chat-hub`), keeping the modules you already enable. This keeps Chat Hub for the 3.x line only, with a deprecation warning at startup; n8n 4.0 removes the feature, so treat the variable as a bridge and plan the migration now.

### Step 6: Review the quieter behavioral changes

These changes do not throw errors at upgrade time, which makes them easy to miss. The highlights are:

- **Gmail Trigger.** Old node versions run as version 1.4. Max Emails per Poll now applies to every poll (default 10, up to 50), drafts are skipped unless Include Drafts is on, and sent emails outside the inbox plus scheduled emails no longer trigger the workflow. If a flow relies on sent or scheduled emails, replace the trigger with a Schedule Trigger plus the Gmail node's Get Many messages operation.
- **Always Output Data.** On multi-output nodes like If and Switch, an empty item is now added only when every output is empty. Previously each empty output got its own empty item, so branches could run when they should not have. Review flagged nodes and adjust the setting to match your intent.
- **Security hardening.** Key rotation is on by default, the SSRF block list grows to cover `100.64.0.0/10` and IPv6 transition ranges, and the Compression node limits drop from 2 GiB to 256 MiB and from 5,000 to 1,000 zip entries. If your workflows call hosts in those ranges or decompress large archives, allowlist them or restore the old limits explicitly before upgrading. Our [security patch tutorial](https://www.161808.xyz/n8n-security-patch-self-hosted/) explains the self-hosted security posture these defaults are tightening.

### Step 7: Upgrade in stages, not in one leap

The [official update guide](https://docs.n8n.io/deploy/host-n8n/keep-n8n-running/update-n8n) is the reference for the mechanics; the staged approach is what keeps you safe. Update to the latest 2.x first, with your full backup in hand. Then pin the Docker image to the 3.0 tag and upgrade a staging instance before touching production. In queue mode, upgrade the main instance and every worker to the same tag together; manual executions now run on workers, so a version-skewed fleet produces confusing failures. Run each migrated workflow at least once and watch for silent behavior changes, not just errors.

### Step 8: Verify before closing the window

Confirm every workflow loads and executes without removed-node errors, and that credentials decrypt, which proves the `config` file with the encryption key survived. Confirm binary data is readable from the renamed `storage` directory and that startup logs show no deprecation warnings, the signal that your configuration is fully on 3.0 semantics. Our [update walkthrough](https://www.161808.xyz/how-to-update-n8n-self-hosted/) covers the standard self-hosted update mechanics this checklist builds on.

## Troubleshooting

### n8n refuses to start after the upgrade

Cause: both `~/.n8n/binaryData` and `~/.n8n/storage` exist, and n8n will not start in that state. Fix: stop the container, move the contents of `binaryData` into `storage`, delete the empty `binaryData` directory, and start again. If you mounted a volume at the old path, remount it at `~/.n8n/storage` or set `N8N_STORAGE_PATH` to the old path.

### Code node executions fail after about 60 seconds

Cause: `N8N_RUNNERS_TASK_TIMEOUT` dropped from 300 seconds to 60 by default in 3.0. Fix: set the variable explicitly to your old value, for example `N8N_RUNNERS_TASK_TIMEOUT=300`, in the compose environment. This is easy to misread as a broken Code node, because the failure looks like a task error rather than a configuration change.

### Gmail workflows stop firing on drafts

Cause: old Gmail Trigger versions run as version 1.4 in 3.0. Drafts are skipped unless Include Drafts is on, and sent emails outside the inbox plus scheduled emails no longer trigger the workflow at all. Fix: turn on the Include Drafts filter where the flow relies on drafts, and replace sent-or-scheduled-email triggers with a Schedule Trigger followed by the Gmail node's Get Many messages operation.

### Credentials show as broken after the move

Cause: the `config` file holding the encryption key did not survive the backup or volume move. Every stored credential is encrypted with that key, and a fresh instance generates a different one, so old credentials become unreadable. Fix: restore the backup containing `config` and restart. Without the original key and no backup, the credentials are unrecoverable; you must re-create them and re-enter each secret.

## Conclusion

n8n 3.0 is a cleanup release wearing a major version number. The checklist is mechanical: get off npm and onto Docker, inventory and replace every removed node, fix the renamed and re-defaulted configuration, decide on Chat Hub, and upgrade in stages with a tested backup. Do that work on 2.x while the Migration Report and startup warnings still tell you what will break, and the 3.0 upgrade becomes a routine deployment. Next, walk through our [npm to Docker migration](https://www.161808.xyz/n8n-npm-to-docker-migration/) to complete Step 0, or our [Docker Compose setup guide](https://www.161808.xyz/n8n-docker-compose-setup/) if your compose file predates current best practices.
