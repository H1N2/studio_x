---
title: "n8n Error Handling Tutorial: Retries, Error Outputs & Error Workflows"
slug: "n8n-error-handling"
description: "n8n error handling tutorial: master retries, per-node error outputs, and a global Error Trigger workflow with a hands-on failing-API example."
date: 2026-09-27
draft: false
categories: ["n8n"]
tags: ["n8n", "error-handling", "workflow-automation", "error-trigger", "retry", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "What happens by default when an n8n node fails?"
    a: "The entire execution stops immediately and is marked as failed in the Executions list. This is the 'Stop Workflow' setting, every node's default. You can see exactly which node failed and why by opening the failed execution and clicking the red node."
  - q: "What is the difference between 'Continue' and 'Continue (using error output)' in n8n?"
    a: "'Continue' lets the workflow proceed on the node's normal output using the last valid data, effectively swallowing the error. 'Continue (using error output)' instead routes the failure to a second, dedicated error output, so you can wire explicit error-handling logic, logging, alerts, or fallback branches, while the success path stays clean."
  - q: "How do I automatically retry a failed node in n8n?"
    a: "Open the node, switch to the Settings tab, and turn on 'Retry On Fail'. This reveals two fields: the maximum number of retry attempts and the wait between tries. It is ideal for flaky external APIs that fail intermittently with rate limits or timeouts."
  - q: "Why isn't my n8n error workflow firing?"
    a: "The most common cause is testing with a manual execution. Per the official n8n docs, the Error Trigger only fires when an automatic (active) workflow errors, never on manual runs. Also check the workflow is assigned under Options ⋮ > Settings > Error workflow, and that the error workflow itself is saved."
  - q: "What data does the n8n Error Trigger receive?"
    a: "A JSON payload with an 'execution' object (execution id and URL, the error message and stack trace, the name of the last node executed, and the run mode) and a 'workflow' object (the failed workflow's id and name). You reference these with expressions like {{ $json.execution.error.message }} to build alerts."
  - q: "Can one error workflow cover all my n8n workflows?"
    a: "Yes. Assign it per workflow under Options ⋮ > Settings > Error workflow, or set it as the instance-wide default under Settings → General → Error Workflow. A single 'Global Error Alerter' workflow that posts to Slack or email is the standard setup for unattended automations."
---

## Introduction

You build a workflow that syncs orders from an API into a spreadsheet. It runs fine for three weeks, then the API has a bad night, and you find out from a customer, because the failure happened silently.

n8n's default on node failure is blunt: **stop the entire workflow** and mark the execution failed. Fine while building, but production automations, anything running on a schedule or webhook while you sleep, need a failure plan. Here are its three layers, smallest to largest:

1. **[Retry On Fail](https://docs.n8n.io/flow-logic/error-handling/)**, automatically retry flaky nodes (rate limits, timeouts).
2. **Per-node error outputs**, route one node's failure into an explicit error branch.
3. **[Error Trigger](https://docs.n8n.io/flow-logic/error-handling/#create-and-set-an-error-workflow) workflows**, a global catch-all that alerts you when anything unhandled fails.

By the end you'll have a working example: a workflow that calls an API, retries on transient errors, logs persistent failures to a dead-letter branch, and pages you through a global error workflow when something truly unexpected breaks. New to n8n entirely? If you're arriving from Zapier, read our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) first, this tutorial assumes you can create a workflow and add nodes.

## Quick answer

Handle n8n errors in three layers: enable Retry On Fail on flaky nodes; set On Error → Continue (using error output) to route failures into a dedicated branch; and build an Error Trigger workflow, assigned under Options ⋮ > Settings > Error workflow, as a global catch-all.

## Prerequisites

- An n8n instance you can edit (self-hosted or n8n Cloud, the settings are identical).
- A test workflow you don't mind breaking. We'll build one from scratch below.
- About 30 minutes. No credentials needed for the walkthrough, we'll simulate the failing API.

## What happens when a node fails (the default)

Before adding handling, watch the default behavior once so you recognize it later:

1. Create a new workflow and add a **Manual Trigger**.
2. Add an **HTTP Request** node. Set Method to `GET` and URL to `https://api.example.com/v1/orders`, a reserved example domain that won't resolve, which simulates a dead API. (Point it at your real endpoint later; for practice, an unresolvable domain guarantees a failure on demand.)
3. Execute the workflow.

The HTTP Request node turns red, execution halts, and the run is recorded as failed. Open **Executions** in the left sidebar, click the failed run, and click the red node: you'll see the exact error (something like `ENOTFOUND` or a connect timeout). That execution log is your ground truth for everything below, every strategy we add changes what this log looks like.

**Key insight:** n8n marks an execution failed only when an error is *unhandled*. Route it into a branch and the run shows as successful, which is why every strategy below pairs routing with something observable: a log row or an alert.

## Strategy 1, Retry On Fail (for flaky APIs)

Most API failures are transient: a 429 rate limit, a 30-second timeout, a deploy happening on the other end. Retrying the same request a few seconds later succeeds surprisingly often. Don't build retry loops by hand, n8n has it built in:

1. Open the **HTTP Request** node and switch to the **Settings** tab (next to Parameters).
2. Turn on **Retry On Fail**. Two fields appear:
   - **Max retries**, additional attempts before giving up; `3` is a sane default.
   - **Wait between tries**, delay before each retry, in milliseconds; `5000` waits five seconds.
3. Save and execute.

With our dead example domain, all retries fail, but watch the execution timing: the node takes ~15+ seconds working through its retries. Against a real flaky API, the second or third attempt usually succeeds and the workflow continues as if nothing happened.

**When to use it:** any node that talks to an external service, HTTP Request, database nodes, SaaS app nodes. **When not to:** deterministic failures. Retrying a request with a bad API key or a malformed payload three times just wastes time; those need Strategy 2 or 3.

## Strategy 2, Continue (using error output) with an IF branch

Retries handle the transient. For persistent failures you need a *decision*: log it, alert someone, use fallback data, or stop loudly. That's what the error output is for, and it requires a two-step setup that trips up almost everyone the first time.

### The two steps

**Step 1, enable the error output on the node.** Open the HTTP Request node → **Settings** tab → **On Error** dropdown. The three options, per the official n8n docs:

- **Stop Workflow** (default), halt everything on error.
- **Continue**, proceed on the node's normal output using the last valid data. The error is swallowed.
- **Continue (using error output)**, the failure is routed to a *second* output connector on the node, carrying the error details.

Select **Continue (using error output)** and save. You'll see a second output dot appear on the node, that's the error path.

**Step 2, wire the error output to a handler.** Drag from the node's second (error) output to the next node. Skip this and the error data is silently discarded while the run shows *successful*; wire it without Step 1 and the wire never fires. Both halves are required.

### Build the dead-letter branch

Give the failure somewhere useful to go. From the HTTP Request node's **error output**, connect an **Edit Fields** node building a dead-letter record:
   - `failed_at` → expression `{{ $now.toISO() }}`
   - `source` → string `orders-api`
   - `error` → expression `{{ $json.error.message }}`
2. Connect that to a **Slack** node (or Email, or Google Sheets, whatever your team actually reads) posting: `Orders sync failed: {{ $json.error }}`.
3. From the HTTP Request node's **normal output** (first connector), continue your happy path, e.g. an Edit Fields node that processes the orders.

Execute with the dead domain: the error output fires and your alert node receives the error details. Open the Edit Fields node's OUTPUT panel after a run to see the exact shape, the message is always there, plus the error name and, for HTTP errors, the status code. Write downstream conditions against what you actually see.

### Branch on the error type (optional but powerful)

Not all failures deserve the same response. Insert an **IF** node on the error branch:

- Condition: `{{ $json.error.message }}` contains `rate limit` (or check a status-code field equals `429`) → true branch → **Wait** node (60 seconds) → loop back to retry the HTTP Request.
- False branch → the Slack alert from above.

This is the production pattern: transient-looking errors get a delayed retry, everything else pages a human. Keep any retry loop bounded, or a permanently failing API loops forever.

## Strategy 3, A global Error Trigger workflow

Per-node handling covers the nodes you wired. It misses the node you forgot, workflow timeouts, and trigger failures. For those, n8n has workflow-level error workflows, every unattended automation should have one.

### Build the error workflow

1. Create a **new workflow** and name it `Global Error Alerter`.
2. As the first node, add an **Error Trigger**. (Search "Error Trigger" in the node panel, it's under trigger nodes.)
3. Add an **Edit Fields** node that builds the alert from the trigger's payload. The Error Trigger receives a JSON payload shaped like this (per the official n8n docs):

```json
{
  "execution": {
    "id": "231",
    "url": "https://your-n8n-host/execution/231",
    "error": {
      "message": "Example Error Message",
      "stack": "Stacktrace"
    },
    "lastNodeExecuted": "HTTP Request",
    "mode": "trigger"
  },
  "workflow": {
    "id": "1",
    "name": "Sync orders to Sheets"
  }
}
```

Map the fields that matter for a 2 a.m. alert:

- `text` → expression:
  `Workflow failure: {{ $json.workflow.name }} — node "{{ $json.execution.lastNodeExecuted }}" failed with: {{ $json.execution.error.message }}. Execution: {{ $json.execution.url }}`

4. Connect it to a **Slack** node posting to your `#incidents` channel.

Two fields earn their keep in every alert: the **workflow name** (which automation broke) and the **execution URL** (one click to the exact failed run). "Workflow failed" with no links costs your on-call ten minutes of clicking.

### Assign it to your workflows

In the workflow to cover: **⋮ Options menu** → **Settings** → **Error workflow** dropdown → select `Global Error Alerter` → **Save**.

To cover the whole instance at once, set it as the default under **Settings → General → Error Workflow**, every workflow without its own assignment inherits it.

### Test it (the right way)

The catch, straight from the official docs: **you cannot test error workflows with a manual execution**, the Error Trigger only fires when an *automatic* (active) workflow errors. So build a throwaway test workflow (Schedule Trigger → HTTP Request to the dead example domain, no error handling), **activate** it, let it run, and watch `#incidents`.

If the alert arrives, your safety net works. If not, check: is the error workflow saved? Is it assigned in the failing workflow's settings? Is the Slack credential valid *in the error workflow* (credentials don't always carry over)?

### Keep the error workflow boring

Two rules from n8n's own guidance and hard-won community experience:

- **Keep it fast and simple: parse, notify, return.** If your error workflow itself fails, a bad expression, an expired Slack token, the original error silently disappears. n8n won't re-trigger on the error workflow's own failure (no infinite loop), but the failure goes nowhere.
- **Don't alert through the channel you're monitoring.** If your workflows notify via Slack, the error workflow should use email, and vice versa. Add a fallback, if the Slack node errors, write to a sheet, so there's always a trail.

Also note the **Stop And Error** node: drop it anywhere to halt with a custom message that flows into the Error Trigger payload, handy for "this should never happen" assertions, e.g. `Order total is negative — aborting sync` after a validation IF.

## Reading the execution log like a debugger

Strategy recap changes what you'll see in **Executions**:

| Setup | What the log shows |
|---|---|
| Default (Stop Workflow) | Red execution, red node, error message on the node |
| Retry On Fail, eventually succeeds | Green execution; node took longer (retries visible in timing) |
| Error output wired + handled | **Green execution**, the failure is "handled." Find what happened on the error branch, not in the failure list |
| Error output enabled, nothing wired | Green execution, error silently discarded, the worst outcome |
| Unhandled failure + error workflow assigned | Red execution on the main workflow, plus a separate green execution of `Global Error Alerter` |

That fourth row is the silent killer. If you ever see a workflow succeeding but producing no output, check for nodes with the error output enabled and no wire, or **Continue** swallowing errors on the normal path.

## Troubleshooting

**My error output is wired but the handler never fires.**
You did step 2 without step 1: confirm **On Error** is set to **Continue (using error output)** in the node's Settings tab. The wire alone does nothing.

**My error workflow never fires when I test it.**
Manual executions don't trigger it, official n8n behavior. Activate the workflow and let it run automatically, then check again.

**The error workflow fires but no alert arrives.**
The error workflow is failing itself. Open its executions: usually a bad expression (note `execution.url` is missing when the main workflow's *trigger* node failed, the payload shape differs), or an invalid credential on the Slack/Email node. Simplify the message first, then add fields back.

**A workflow shows success but downstream data is wrong.**
Something is swallowing errors: **Continue** (not the error-output variant) on a node, or an error output wired to a no-op. Temporarily set it back to Stop Workflow to make failures loud, find the culprit, then re-wire.

**Retries aren't helping and just slow everything down.**
You're retrying a deterministic failure, bad credentials, a 404 on a wrong URL, invalid JSON. Retries are for transient failures (429s, timeouts, 5xx). Fix the cause, don't retry it.

## Conclusion

That's the full stack: **Retry On Fail** for the flaky, **Continue (using error output)** plus a branch for expected failures, and a **Global Error Alerter** for the unexpected. The rule: every failure lands somewhere observable, a retried success, a dead-letter row, or an alert with the workflow name and execution link. Silent green checkmarks are the enemy.

Where to go next: our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) walks through moving automations onto n8n, bring these error-handling patterns with you, since Zapier handles errors differently. And if you're wiring workflows into AI agents, our [MCP server tutorial](/mcp-server-tutorial/) explains the protocol those integrations run on.
