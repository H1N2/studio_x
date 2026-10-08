---
title: "How to Use n8n Workflows as MCP Tools in Claude Code"
slug: "n8n-workflows-as-mcp-tools-claude-code"
description: "Use n8n workflows as MCP tools in Claude Code: enable the MCP server, connect via OAuth or API key, expose workflows, then run them from the terminal."
date: 2026-10-07
draft: false
categories: ["n8n", "AI tools"]
tags: ["n8n", "mcp", "claude-code", "ai-agents", "workflow-automation", "self-hosted", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Does n8n's MCP server work on self-hosted instances or only n8n Cloud?"
    a: "It works on both. The official connection guide lists the exact same enabling steps for Cloud and self-hosted instances: go to Settings, then Instance-level MCP, and turn on Enable MCP access. Self-hosted owners can also manage the feature with environment variables, including N8N_DISABLED_MODULES=mcp to remove it entirely."
  - q: "What is the difference between instance-level MCP and the MCP Server Trigger node?"
    a: "Instance-level MCP creates one connection per n8n instance with centralized authentication, and you enable individual workflows for access from a single screen. The MCP Server Trigger node, in contrast, turns one specific workflow into an MCP server from inside that workflow's own node graph. Use the instance-level server when you want Claude Code to reach many workflows; use the trigger node when you want to craft a custom MCP server behavior in a single workflow."
  - q: "Can Claude Code modify or delete my workflows through the MCP server?"
    a: "Only within the permissions you grant when it connects. Each connected client keeps only the access level you approved at sign-in, and you can review those permissions at any time in Settings, then Instance-level MCP, under Connected clients. Revoking access disconnects the client immediately, and it must sign in again to regain access."
  - q: "Can Claude Code see all of my workflows, including private ones?"
    a: "It can preview them. The search_workflows tool lists every workflow your user account can view, regardless of MCP settings, but it returns previews only. Full workflow data, execution, and editing require you to enable Available in MCP for each workflow explicitly, so nothing sensitive becomes callable by accident."
  - q: "Should Claude Code run my workflow in manual or production mode?"
    a: "Production mode runs the published version of the workflow, while manual mode tests the current draft. Use production mode when you trust the active version and want real runs; use manual mode while you are iterating, or to execute workflows that only have a Manual Trigger node, which production mode does not support."
  - q: "How do I disconnect Claude Code from my n8n instance?"
    a: "Go to Settings, then Instance-level MCP, and open Connected clients. Select the Claude Code entry and choose Revoke access, which disconnects it at once. If you want the whole feature gone, turn off Enable MCP access, or on self-hosted instances set N8N_DISABLED_MODULES=mcp to remove the endpoints and hide the UI entirely."
---

## Introduction

Claude Code writes great code, but your n8n workflows already encode the automations that matter: the newsletter pipeline, the CRM sync, the deploy checks. n8n's built-in, instance-level MCP server turns those workflows into tools Claude Code can search, inspect, and execute. This tutorial covers enabling the server, connecting Claude Code with OAuth or an API key, exposing your first workflow, and running it from the terminal, on n8n Cloud and self-hosted instances alike.

## Quick answer

Enable instance-level MCP in Settings on your n8n instance, run `claude mcp add --transport http n8n https://<your-domain>/mcp-server/http`, authorize with `/mcp`, then mark workflows as Available in MCP. Claude Code can then search, inspect, and execute them as tools.

## Evidence

The vendor's own words set the frame. The official n8n MCP server guide states: "n8n's built-in MCP server lets supported clients, such as Lovable or Claude Desktop, connect securely to your n8n instance." Once connected, clients can search workflows, interact with workflows marked as available in MCP, trigger and test them, and even create and edit workflows and data tables. That list is the whole value proposition in one sentence, and it comes from the primary documentation, not a marketing page.

The scale behind the feature is easy to verify: the n8n repository held 206,788 GitHub stars as of 7 October 2026, and October 2026 announcements positioned the instance-level MCP server as the bridge letting coding agents like Claude Code work directly against an instance, including free self-hosted ones. The [official connection examples page](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-client-examples) ships copy-paste configs for nine client families, from Claude Code and Codex to Cursor, VS Code, Windsurf, and Gemini CLI: this is a first-class integration surface, not an experiment.

One security property shapes every step below. The [main MCP server guide](https://docs.n8n.io/connect/connect-to-n8n-mcp-server) is explicit: connecting the server does not expose all workflows. You enable MCP at the instance level first, then enable each workflow individually, and only `search_workflows` can list the rest, returning previews, never full data. On execution, the [tools reference](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-server-tools-reference) notes that `execute_workflow` "starts the workflow and returns immediately", so long-running workflows are fire-and-check, not blocking calls.

## Prerequisites

You need instance owner or admin rights, because enabling MCP access is a privileged action. For the guided setup, run n8n 2.33.0 or newer: that is when the Connect a client dialog started showing per-client steps for Claude Code. Older versions still connect, but you configure the client manually with the commands on the official client examples page. You also need Claude Code with the `claude` CLI in your terminal, and at least one published workflow starting with a webhook, form, schedule, or chat trigger node. Only workflows with one of those trigger types are eligible for MCP access. If your n8n runs locally, the MCP server only needs the instance URL to be reachable from where Claude Code runs, so a localhost URL works for local setups.

## Step-by-step guide

### Step 1: Enable instance-level MCP access

Sign in as an owner or admin, open **Settings**, then **Instance-level MCP**, and select **Enable MCP access**. The page reorganizes into three sections: **Connection details** (status plus a Connect button), **Access** (how many workflows are exposed), and **Connected clients** (who is connected and with what permissions). Self-hosted instances can manage this via environment variables, and `N8N_DISABLED_MODULES=mcp` removes the feature entirely. Confirm you run n8n 2.33.0 or newer for the guided Claude Code steps in the next step; if not, update first with our [n8n update guide](https://www.161808.xyz/how-to-update-n8n-self-hosted/).

### Step 2: Connect Claude Code with OAuth (recommended)

In **Connection details**, select **Connect** to open the **Connect a client** dialog and confirm you are on the **OAuth (recommended)** tab. In the **Your client** dropdown, pick **Claude Code**. n8n shows the exact install command for your instance. It looks like this, with your own domain in place of the placeholder:

```bash
claude mcp add --transport http n8n https://n8n.example.com/mcp-server/http
```

Run that command in your terminal. The server URL always ends in `/mcp-server/http`; it is not your editor address, so never paste the URL from your browser's address bar. Then open Claude Code and run `/mcp`, select **n8n** from the list, and complete the authorization in your browser. n8n redirects you to approve the client's access, and only the permissions you confirm there are granted. Once approved, the client appears under **Connected clients** in the n8n settings page. OAuth is the recommended path because the token lifecycle is managed for you, and revoking access is one click.

If you prefer the JSON route instead of the CLI, the dialog also gives you a manual configuration snippet for your `claude.json`:

```json
{
  "mcpServers": {
    "n8n": {
      "type": "http",
      "url": "https://n8n.example.com/mcp-server/http"
    }
  }
}
```

### Step 3: Connect with an API key (alternative)

Some setups, like headless servers or shared build machines, cannot complete a browser-based OAuth dance. For those, switch to the **API key** tab in the **Connect a client** dialog. n8n generates a personal access token tied to your user account the first time you open the tab. Copy the **Configuration JSON**, which already contains your server URL and an `Authorization: Bearer` header, or run:

```bash
claude mcp add --transport http n8n-mcp https://n8n.example.com/mcp-server/http \
  --header "Authorization: Bearer <your-token>"
```

Two warnings straight from the docs: the token is tied to your user account, so it inherits your workflow permissions, and once you leave the tab n8n shows only a redacted value. If you lose it, generate a new one from the same tab, which revokes the old token, and update every client that used it.

### Step 4: Verify the connection inside Claude Code

Run `/mcp` in Claude Code and confirm the **n8n** entry shows as connected. Then ask Claude Code a question that forces it to use the new tools, for example: "List the n8n workflows you can see." Behind the scenes it calls `search_workflows`, which returns previews of every workflow your account can view. This is also your first look at the permission boundary: search returns previews even for workflows you have not enabled for MCP, but Claude Code cannot read their full contents or run them until you opt each one in. If the tools list is empty, the OAuth step did not finish; run `/mcp`, re-select n8n, and approve the redirect again.

### Step 5: Expose your first workflow as a tool

This is the step that turns a workflow into something Claude Code can actually call. Open the workflow, publish it if it is not active yet, and confirm it starts with a webhook, form, schedule, or chat trigger. Eligibility is strict: the docs state you can only enable MCP access for published workflows containing one of those four trigger types. Then enable access any of three ways:

1. **Settings > Instance-level MCP > Workflows exposed**: click **Enable workflows**, search the workflow by name, and confirm.
2. In the workflow editor: open the **Workflow menu** (the `...` in the top-right corner), choose **Settings**, and toggle **Available in MCP**.
3. In the workflows list: open the menu on the workflow card and select **Enable MCP access**.

While you are here, write a real description for the workflow. The docs recommend descriptions because MCP clients use them to identify workflows, and a good one is the difference between Claude Code picking the right tool and asking which of three similar names you meant. If you always want new workflows exposed, turn on **Auto-expose new workflows** in the same settings page. For a hands-on tour of the agent features this unlocks, our [n8n Agents tutorial](https://www.161808.xyz/n8n-agents-tutorial/) is the natural follow-up.

### Step 6: Call the workflow from Claude Code

With a workflow exposed, the natural-language flow in Claude Code looks like this. Ask: "Run my changelog digest workflow for week 41." Claude Code will typically:

1. Call `search_workflows` to find the workflow by name.
2. Call `get_workflow_details` to learn its trigger type and expected inputs. For a webhook-triggered workflow, the tool returns a human-readable `triggerInfo` describing how to invoke it.
3. Call `execute_workflow` with `workflowId`, `executionMode`, and `inputs`. For a webhook workflow, inputs use the `webhook` variant with `method`, `query`, `body`, and `headers`. For a schedule-triggered workflow with no required inputs, the tool can pick the single eligible trigger automatically.

`execute_workflow` returns an `executionId` immediately without waiting; Claude Code then calls `get_workflow_execution` with that ID to read the final status and output. `executionMode: "production"` runs the published version for trusted workflows, while `"manual"` tests the current draft and is the only mode supporting Manual Trigger nodes. If the workflow has more than one eligible trigger, or its only trigger requires input data, the tool errors listing the available trigger names instead of guessing; pass `triggerNodeName` to select one.

### Step 7: Test and build workflows without leaving Claude Code

Execution is only half the story. The same MCP server gives Claude Code builder tools, which is why n8n's October 2026 announcements framed this as letting coding agents build directly on your instance. Three tools are worth knowing by name:

- **`test_workflow`**: runs a workflow with pin data you supply, so trigger nodes, credentialed nodes, and HTTP Request nodes use your simulated data while Set, If, and Code nodes execute normally. This is how Claude Code validates logic without touching production services or needing your credentials.
- **`get_workflow_execution`**: polls any execution by ID for status and data, the companion to the fire-and-forget `execute_workflow`.
- **Workflow creation and editing tools** (available from n8n 2.13.0): Claude Code can draft a workflow from your description and save it to your instance, with new workflows getting MCP access enabled automatically when created through these tools.

A realistic session: "Create a workflow that fetches the top 5 Hacker News stories and posts them to #general in Slack every weekday at 8am, then test it with pinned data." Claude Code searches for the right nodes, builds the workflow, runs `test_workflow` with simulated HTTP responses, and shows you the result. You review and publish. Our [Claude Code MCP setup guide](https://www.161808.xyz/claude-code-mcp-setup/) covers the client side of this pairing, and the [MCP server tutorial](https://www.161808.xyz/mcp-server-tutorial/) explains the protocol underneath.

### Step 8: Review permissions and keep the audit trail

The convenience comes with a responsibility, and n8n built the controls for it. Revisit **Settings > Instance-level MCP > Connected clients** periodically: it shows each connected client, its granted permissions, and when it connected. Selecting a client opens its details; **Revoke access** disconnects it immediately. A client whose permissions feel too broad should be reconnected with a narrower grant. If an API key leaks, rotate it from the **API key** tab, which revokes the old token at once, then update the affected clients. Execution history is your second audit layer: every `execute_workflow` call creates a normal n8n execution with the caller's user context, so the executions list shows exactly what Claude Code ran, when, and with what inputs. For teams on shared instances, note the docs' scoping rule: visibility is user-scoped, so each user only sees the MCP-enabled workflows they already have access to, but you cannot restrict specific workflows to specific clients.

## Troubleshooting

### Claude Code connects but the `/mcp` list shows no n8n tools

The OAuth authorization did not complete. Run `/mcp` in Claude Code, select **n8n** again, and finish the browser approval. On self-hosted instances behind a reverse proxy, check that the instance URL you registered is the public domain, not `localhost`, and that your `WEBHOOK_URL` and `N8N_HOST` environment variables match it; a mismatched host breaks the OAuth redirect. Instance owners can also inspect **Allowed callback URLs** in the MCP settings page. Our [Docker Compose setup guide](https://www.161808.xyz/n8n-docker-compose-setup/) shows the correct environment block for a public self-hosted install.

### Claude Code finds the workflow in search but cannot execute it

The workflow is not enabled for MCP access, or it is not eligible. Open **Settings > Instance-level MCP > Workflows exposed** and confirm it is listed. If it cannot be enabled, check the two eligibility rules: the workflow must be published, and it must contain a webhook, form, schedule, or chat trigger node. A draft workflow, or one that starts with a Manual Trigger only, will never appear as enableable. Publish it first, or switch the entry point to an eligible trigger.

### `execute_workflow` ran an old version of my logic

You hit the production-versus-manual distinction. Production mode executes the published version, so edits saved after your last publish are invisible to it. Either publish the workflow first, or ask Claude Code to run it with `executionMode: "manual"`, which executes the current draft. Related: if the tool errors instead of running, read the error. When a workflow has more than one eligible trigger, or its only trigger requires input data, the tool returns an error listing the available trigger names rather than guessing; pass `triggerNodeName` to select one explicitly.

### The Connect a client dialog shows no Claude Code steps

Your n8n is older than 2.33.0. The per-client interactive setup, including the Claude Code entry in the **Your client** dropdown, only exists from that version. Either update your instance, or configure manually: copy the **Server URL** ending in `/mcp-server/http` and use the exact `claude mcp add --transport http` commands from the [official client examples page](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-client-examples), which cover both OAuth and API key auth.

### `test_workflow` times out on a long workflow

The tool enforces an MCP execution timeout of five minutes by default. Pass the `timeout` parameter, up to 3600 seconds, for workflows that legitimately run longer. If the workflow waits on human input, know that multi-step forms and human-in-the-loop interactions are not supported by `execute_workflow` at all; redesign that branch to complete without approval steps before exposing it to an agent.

## FAQ

See the front matter for the full FAQ list. The short version: yes on self-hosted and Cloud, instance-level MCP is the per-instance connection while the MCP Server Trigger node is the per-workflow server, clients keep only granted permissions, search shows previews while execution needs opt-in, manual mode tests drafts while production runs the published version, and revocation is one click in Connected clients.

## Conclusion

Connecting Claude Code to n8n's built-in MCP server turns your workflow library into a toolbelt your coding agent can use: search finds workflows, `get_workflow_details` explains how to call them, `execute_workflow` runs them, and the builder tools let the agent draft and test new ones without leaving the terminal. The opt-in exposure model keeps the blast radius small, and the executions list keeps every agent run auditable. Next, build something worth exposing: our [n8n Agents tutorial](https://www.161808.xyz/n8n-agents-tutorial/) shows how to create AI agents inside n8n, and the [MCP server tutorial](https://www.161808.xyz/mcp-server-tutorial/) deepens the protocol knowledge behind it all.
