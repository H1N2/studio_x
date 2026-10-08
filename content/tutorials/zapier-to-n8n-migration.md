---
title: "How to Migrate from Zapier to n8n"
slug: "zapier-to-n8n-migration"
description: "How to migrate from Zapier to n8n: export Zaps, map triggers and actions to n8n nodes, rebuild a real Gmail-to-Trello workflow, and compare costs."
date: 2026-09-27
draft: false
categories: ["n8n"]
tags: ["n8n", "zapier", "migration", "workflow-automation", "self-hosted", "automation"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Is there an automatic tool to import Zaps into n8n?"
    a: "No. n8n has no native Zapier importer, and its 'Import from File' option only reads n8n's own workflow JSON. Migration means manually rebuilding each Zap as n8n nodes. On Zapier Team and Enterprise plans you can export your Zaps as JSON (Settings → Security and data → Data management) to use as a reference while rebuilding."
  - q: "How does n8n pricing compare to Zapier?"
    a: "Zapier bills per task, every successful action step in a Zap counts, so a 4-action Zap firing 1,000 times a month uses 4,000 tasks. n8n bills per execution: one workflow run counts as one execution no matter how many nodes it has, so the same workload is 1,000 executions, inside n8n Cloud Starter's 2,500 included executions (€24/month), or free on self-hosted n8n."
  - q: "Do I have to self-host n8n to migrate from Zapier?"
    a: "No. n8n Cloud is a fully managed option (Starter €24/month, Pro €60/month) with a 14-day trial. Self-hosting the free Community edition is what removes per-execution billing entirely, but it's optional, migrate on Cloud first, self-host later if the math justifies it."
  - q: "What happens to my Zap history and data when I cancel Zapier?"
    a: "Export it first. Zapier lets you download your Zap run history as CSV or JSON (Zap History → select runs → Download), and Team/Enterprise owners can export all Zap workflow definitions as JSON. Do both before downgrading or canceling, because historical run data disappears with the account."
  - q: "Will my automations behave exactly the same in n8n?"
    a: "Mostly, but watch the triggers. Many Zapier 'instant' triggers use webhooks, while n8n's app triggers (like the Gmail Trigger) poll on an interval, expect a small delay. Also, n8n nodes run once per data item, so one email automatically creates one Trello card. Test every rebuilt workflow against real data before switching off the Zap."
  - q: "Can I run Zapier and n8n in parallel during migration?"
    a: "Yes, and you should. Migrate one Zap at a time, starting with the simplest and least critical. Keep the original Zap on until the n8n version has run correctly in production for a few days, then turn the Zap off."
---

## Quick answer

How do I migrate from Zapier to n8n? There is no automatic importer, you rebuild each Zap as an n8n workflow, mapping Zapier triggers to n8n trigger nodes and actions to n8n nodes. Inventory your Zaps, export what you can, rebuild one workflow at a time starting with the simplest, reconnect your app credentials in n8n, test with real data, then switch off the Zap.

## Introduction

The most common reason people migrate from Zapier to n8n is the bill. Zapier charges per **task**, every successful action step in a Zap counts separately, so costs grow with both volume *and* complexity. n8n charges per **execution**: one workflow run counts as one execution whether the workflow has 3 nodes or 30. A 5-action Zap firing 1,000 times a month consumes 5,000 Zapier tasks but only 1,000 n8n executions. On self-hosted n8n, it consumes nothing at all beyond the server you already pay for.

This tutorial walks through the full migration: auditing your Zaps, exporting what Zapier lets you export, the concept-by-concept mapping, a complete worked rebuild of a real Zap (Gmail → Trello), credential migration, testing, and the pricing math. All pricing and export options below were verified against the [official Zapier](https://help.zapier.com) and [n8n](https://docs.n8n.io) pages on September 27, 2026.

## Step 1, Inventory your Zaps and export what you can

Before touching n8n, list every Zap you run: trigger app, number of action steps, whether it uses Filters, Paths, Formatter, Delays, or Code steps, and roughly how often it fires. Rank them by simplicity, you will migrate the simplest first.

Now export. Be aware of what Zapier actually lets you take with you (verified from [Zapier's help center](https://help.zapier.com/hc/en-us/articles/8496308481933-Import-and-export-Zap-workflows-in-your-Team-or-Enterprise-account)):

- **Zap workflow definitions (JSON):** available on Team and Enterprise plans only. Account owners go to Settings → Security and data → Data management → *Download private and shared Zap workflows*, and Zapier emails a JSON file. Individual Zaps can also be exported from the editor by clicking the Zap name → *Export a JSON data file of your Zap* (owner only).
- **Zap run history (CSV/JSON):** available on all plans. Go to Zap History, select runs, click Download. This is run *data*, not the workflow definition, useful as a reference and an archive, not as something n8n can import.
- **Free, Starter, and Professional plans:** there is no self-serve Zap export. Your migration reference will be screenshots and notes of each Zap's setup.

On the n8n side, there is **no Zapier import tool**. n8n's "Import from File" menu only reads n8n's own workflow JSON format. Every community guide and n8n's own documentation agree: migration is a manual rebuild, which is also an opportunity to clean up years of accumulated Zap cruft.

One thing to do right now, whatever your plan: download your Zap history. If you later cancel Zapier, historical run data goes with the account.

## Step 2, Learn the concept mapping

Zapier and n8n share the same mental model but different vocabulary. This table covers the mappings you'll use in nearly every migration:

| Zapier concept | n8n equivalent |
|---|---|
| Zap | Workflow |
| Trigger (e.g. New Email in Gmail) | Trigger node (Gmail Trigger, Webhook, Schedule Trigger…) |
| Action step | Node (Gmail, Trello, Slack, HTTP Request…) |
| Task (billing unit) | Execution, one full workflow run = 1 execution |
| Filter | IF node (routes items down true/false branches) |
| Paths | Switch node (multiple conditional branches) |
| Formatter | Edit Fields node (formerly called Set) or Code node |
| Delay | Wait node |
| Webhooks by Zapier (Catch Hook) | Webhook node |
| Schedule by Zapier | Schedule Trigger node |
| Looping by Zapier | Loop Over Items node |
| Code by Zapier (JS/Python) | Code node (JavaScript or Python) |
| Connected account | Credential (stored per app in n8n) |

Two billing facts from Zapier's official pricing page that shape the whole migration: **triggers never count as tasks**, and **polling for new data never uses tasks**, only successful actions do. Also free of charge: Filter, Formatter, Paths, Delay, Looping, and Sub-Zap steps. So a Zap with a trigger + filter + formatter + 2 actions consumes 2 tasks per run, not 5. Know your real task count before doing the pricing math, check it in Zapier's usage dashboard, not by counting steps.

## Step 3, Rebuild a real Zap: Gmail → Trello

Let's migrate the canonical example Zap: **when a new email arrives in Gmail, create a card in Trello** (with a filter so only relevant emails create cards). This exact integration is documented on both sides, Zapier's Gmail+Trello integration page describes the "New Email" trigger with a "Create Card" action, and n8n's template library has the same pattern.

### The Zap we're replacing

1. **Trigger:** Gmail, New Email (optionally "New Labeled Email")
2. **Filter:** only continue if the subject contains "Invoice" (or from a specific sender)
3. **Action:** Trello, Create Card (board + list + name + description mapped from the email)

### The n8n workflow

Create a new workflow in n8n and add three nodes:

**Node 1, Gmail Trigger.** Add a trigger node, choose **Gmail Trigger**, operation **Watch for New Mails**, and point it at your Inbox (or a label). Connect your Google account when prompted, n8n will ask you to create a credential. Note this is a *polling* trigger: it checks Gmail on an interval rather than receiving instant push notifications. n8n is efficient about it, when a poll finds nothing new, no execution is recorded, but expect a delay of up to the poll interval rather than Zapier-instant delivery.

**Node 2, IF node (replaces the Filter).** Add an **IF** node and set the condition to match your old Zapier filter, e.g. *Subject contains "Invoice"*. In n8n you reference the email's data with expressions like `{{ $json.subject }}`. The IF node sends matching emails down the *true* branch and everything else down *false* (which you simply leave unconnected, those items stop there).

**Node 3, Trello (replaces the action).** Add a **Trello** node, operation **Create Card**. Fill in:

- **Board ID** and **List ID**, select your board and the target list (e.g. "Incoming")
- **Name**, an expression built from the email, e.g. `={{ $json.subject }}`
- **Description**, e.g. `From: {{ $json.from }} — {{ $json.text }}`

Connect a Trello credential (API key + token) when prompted. Because n8n nodes run once per data item, each email that passes the IF node automatically creates exactly one card, no loop step needed.

### Mapping the data (Zapier pills → n8n expressions)

In Zapier you map fields by picking "pills" from a dropdown. In n8n you write **expressions**, or drag and drop: the **Edit Fields** node's Manual Mapping mode lets you drag a value from the input panel into a field, and n8n writes the expression for you (toggle between Fixed and Expression per field). The syntax you'll use constantly:

- `{{ $json.subject }}`, a field from the current item
- `{{ $json.from }}`, the sender address
- `{{ $('Gmail Trigger').first().json.body }}`, reach back to a specific earlier node

Click **Execute step** on each node as you build to see real data flowing through, n8n shows the actual email JSON from your test run, which makes mapping far less guesswork than Zapier's sample-data picker.

## Step 4, Migrate your credentials

Every app connection must be re-authorized in n8n, credentials don't transfer from Zapier. For each node, click the credential dropdown and create a new credential:

- **Gmail / Google apps:** n8n uses OAuth2. On **n8n Cloud**, Google OAuth is pre-configured, you just sign in. On **self-hosted** n8n, you need to create your own OAuth client in the Google Cloud Console and paste the client ID/secret into the n8n credential. This is the single biggest setup hurdle for self-hosters; budget 15 minutes for it.
- **Trello:** API key + token, generated from Trello's developer portal, straightforward on both Cloud and self-hosted.
- **API-key apps (Slack, OpenAI, etc.):** paste the key. Same as Zapier.

Security hygiene while you're at it: Zapier's export files can contain connection details, so don't commit exported Zap JSON to a public repo, and rotate any API keys that were sitting in old Zaps.

## Step 5, Test, run in parallel, then cut over

1. **Test each node** with the Execute step button, then run the whole workflow with **Test workflow** and send yourself a real email.
2. **Activate** the workflow (toggle in the top right, inactive workflows never fire, which surprises every Zapier migrant once).
3. **Run both systems in parallel** for a few days. Keep the Zap on while the n8n workflow handles the same emails; compare the Trello cards.
4. **Turn off the Zap** only after the n8n version has run cleanly in production. Migrate Zaps one at a time, simplest first.

If your end goal goes beyond linear automations into AI agents, note that n8n also ships MCP Server Trigger and MCP Client nodes, your migrated workflows can become tools an AI agent calls. Our [MCP server tutorial](/mcp-server-tutorial/) explains the protocol those nodes speak.

## Cost comparison: tasks vs executions

Current pricing, verified September 27, 2026:

| | Zapier (official zapier.com/pricing) | n8n (official n8n.io/pricing) |
|---|---|---|
| Billing unit | Task = each successful action | Execution = one full workflow run |
| Free tier | $0, 100 tasks/month | Self-hosted Community, $0, unlimited executions |
| Entry paid | Professional from $19.99/month | Cloud Starter €24/month (€20 annual), 2,500 executions |
| Mid tier | Team from $69/month | Cloud Pro €60/month (€50 annual), 10,000 executions |
| Scale | Task tiers up to 2M/month | Business ~€800/month, 40,000 executions; Enterprise custom |

Worked example: a 4-action Zap firing 1,000 times a month uses 4,000 Zapier tasks (the trigger doesn't count), pushing you from the 2K task tier into the 10K tier on a paid plan. The same automation in n8n is **1,000 executions**, comfortably inside the €24/month Starter plan's 2,500, or $0 on self-hosted Community beyond server costs (a small VPS runs roughly $5–10/month).

The honest caveat: if you run two simple single-action Zaps a few times a week, Zapier's free 100 tasks/month is cheaper than any paid n8n plan. Migration pays off when volume, step count, or both are non-trivial, which is exactly when Zapier's per-task meter hurts most.

## Common migration pitfalls

- **Polling vs instant triggers.** Zapier labels some triggers "instant" (webhook-backed). n8n's app triggers like Gmail Trigger poll on an interval. If sub-minute latency matters, check whether the app offers a webhook you can catch with n8n's Webhook node instead.
- **One trigger, many items.** The Gmail Trigger can return multiple emails per poll. n8n handles this gracefully (one card per email), but if your downstream logic assumes a single item, e.g. an aggregation, add the appropriate node rather than assuming Zapier's one-at-a-time behavior.
- **Error handling works differently.** Zapier's Professional plan offers auto-replay of failed runs. In n8n, configure error handling per node (continue on error, retry, or route failures to an error workflow), don't leave it at defaults for anything business-critical. Our [n8n error handling tutorial](/n8n-error-handling/) walks through all three strategies with a real failing workflow.
- **Line items and loops.** Zapier's Looping step becomes n8n's **Loop Over Items** node. Audit any Zap that processes lists before migrating; this is where manual rebuilds most often go wrong.
- **Timezone on schedules.** Schedule by Zapier → Schedule Trigger: set the workflow timezone explicitly, or your 9 AM digest fires at 9 AM UTC.
- **Don't cancel Zapier on day one.** Export your history, migrate gradually, and keep the old Zaps as a rollback plan for at least one billing cycle.

## Conclusion

Migrating from Zapier to n8n is a manual rebuild, not an import, but it's a straightforward one: map each trigger and action to its n8n node, reconnect credentials, and test against real data before cutting over. The payoff is structural: per-execution instead of per-task billing means complex, high-volume automations stop getting more expensive the moment they get more useful. Start with your simplest Zap this week, keep both platforms running in parallel, and let the usage dashboard tell you when the math has won.
