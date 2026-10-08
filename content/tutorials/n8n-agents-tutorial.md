---
title: "n8n Agents Tutorial: Build a Telegram AI Agent from Scratch (2026)"
slug: "n8n-agents-tutorial"
date: 2026-10-04
draft: false
description: "Build a Telegram AI agent with n8n Agents: an OpenRouter model, Todoist and Gmail tools, reusable skills, schedules, and workflow calls. Hands-on guide."
categories: ["n8n", "AI Agents"]
tags: ["n8n agents", "telegram bot", "ai agent", "openrouter", "automation", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "What is the difference between n8n Agents and the n8n AI Agent node?"
    a: "The AI Agent node builds an agent inside a single workflow canvas. n8n Agents is a first-class artifact that sits beside your workflows with its own model, instructions, tools, memory, sessions, draft and published versions, channels, and schedules. The official launch blog confirms that existing AI Agent node workflows keep working unchanged."
  - q: "How much do n8n Agents cost to run?"
    a: "One agent turn, meaning one message in and one response out, counts as one execution. Calls the agent makes to workflow tools or sub-agents inside that turn do not count separately. Agent executions share the same quota as workflow executions on your plan. New agent models also start with $2 of free n8n gateway credits."
  - q: "Can I run n8n Agents on a self-hosted instance?"
    a: "Yes, from n8n 2.32.3, except on self-hosted Enterprise where support is coming soon. You enable the agents module with N8N_ENABLED_MODULES=agents. Knowledge bases need a Daytona sandbox on self-hosted, channels need a public WEBHOOK_URL, and queue mode is not supported for agents yet, so run them in regular mode."
  - q: "Are n8n Agents ready for production use?"
    a: "Agents are in Preview, so n8n warns they can make mistakes and their behavior may change during development. Test every agent with Preview before publishing, require approval on tools that write to your systems, and keep editing in the draft while the published version serves users."
  - q: "Which chat channels can an n8n agent connect to?"
    a: "The official docs list Slack, Telegram, and Linear as agent channels, and the launch announcement adds Discord. WhatsApp and Microsoft Teams are not supported as agent channels. For an unsupported platform, bridge it with a workflow: a trigger node for that platform feeding into the Message an Agent node."
  - q: "Can an n8n agent use my existing workflows?"
    a: "Yes, and this is one of the strongest patterns. In the Tools section you add workflows from the same project as tools. The agent decides when to run them, and each workflow runs exactly as you built it, with its own credentials. For example, an agent can add a note to your CRM through a workflow without ever holding write access to the CRM itself."
---

## Introduction

On September 25, 2026, n8n launched Agents, a building block that lives next to your workflows instead of inside them. If you have wired a Chat Trigger to an AI Agent node and wished the result had its own identity, history, channels, and schedules, this is it. You will build a personal Telegram assistant: an OpenRouter model, Todoist and Gmail tools, a reusable skill, a daily schedule, and a workflow that calls the agent back. Facts come from n8n's official docs and video walkthrough; node parameters and the self-hosted setup were verified against n8n 2.41.4 in our lab.

## Quick answer

n8n Agents are first-class AI assistants built beside your workflows. Pick a model, write instructions, attach tools like Todoist or Gmail, connect Telegram, then publish. The same agent can chat, run on schedule, or be called from a workflow.

## Evidence

Because Agents launched days ago, most blog coverage is speculation. Here is what is actually documented, timestamped October 2026.

First, the launch scope. The [n8n Agents documentation](https://docs.n8n.io/build/build-and-manage-agents) states agents are available on n8n Cloud on all plans, and on self-hosted n8n from version 2.32.3 with extra setup, except self-hosted Enterprise where support is coming soon. Agents are in Preview: they can make mistakes, and their behavior may change during development.

Second, the pricing unit. The same docs page says one turn with an agent counts as one execution, a turn being one exchange of your message and the agent's response. Calls the agent makes to workflow tools or sub-agents inside that turn do not count separately, and agent executions share the same quota as workflow executions on your plan. For the model, n8n's [official Telegram agent video walkthrough](https://github.com/n8n-io/video-resources/blob/HEAD/videos/2026-09-22-telegram-personal-agent/README.md) notes agent models start with $2 of free gateway credits, and OpenRouter unlocks nearly any model with per-token billing.

Third, the vendor's own framing. The [launch announcement](https://blog.n8n.io/introducing-n8n-agents/) positions agents for open-ended work: "With agents, it's easier to handle open-ended or back-and-forth jobs that could get complicated to build as a fixed workflow." It also draws a compatibility line that matters if you already automate with n8n: "If you use the AI Agent node today, nothing about it has changed. Everything you've built keeps working." The n8n docs changelog adds the operational rule this tutorial follows: "Test before you publish, and require approval on tools that write to your systems."

## Prerequisites

- An n8n account on n8n Cloud (any plan), or a self-hosted n8n instance on version 2.32.3 or newer with the agents module enabled.
- A Telegram account, for creating the bot the agent will talk through.
- An OpenRouter account with an API key, or any other model provider credential n8n supports.
- Todoist and Gmail accounts, for the two tools in the walkthrough.
- Basic comfort with n8n credentials and workflows; if the AI Agent node pattern is new, read our [n8n AI Agent node tutorial](/n8n-ai-agent-tutorial/) first.

## Step-by-step guide

### Step 1: Create the agent

Open your project in n8n and navigate to the **Agents** tab, which sits next to Workflows. Select **Create Agent** to open the Agent Builder with a blank draft. In the **Agent** tab, name it "Personal Assistant" and pick an icon with the icon picker. Everything you configure is saved to the draft automatically. If you prefer a head start, describe the agent to the n8n Assistant instead; it suggests instructions, tools, and skills for you to refine.

### Step 2: Choose a model

In the **Agent** tab, open the **Model** field and pick a provider and model, adding credentials when prompted. The default runs on n8n gateway credits, which include $2 free, the fastest way to get talking. OpenRouter is the flexible alternative: one API key unlocks nearly any model with per-token billing. When you create the OpenRouter key, set a monthly spend limit on it; the official n8n walkthrough used $5 for a personal assistant.

Model choice matters visibly. In the official walkthrough, the builder started on a cheap model and switched to Claude Sonnet 5 when the agent could not see images. If your assistant will read photos of receipts or sticky notes, pick a vision-capable model from the start.

### Step 3: Write instructions

In the **Instructions** field, describe the agent's role, tone, response format, what it should and should not do, and which tools or skills it should prefer. The docs advise keeping instructions specific and refining them first, before adding more tools, when behavior is off. An example to adapt:

```text
You are my personal productivity assistant. You manage my Todoist tasks
and read my Gmail. Tone: concise and friendly, one short paragraph per
answer unless I ask for detail. Always confirm before deleting anything.
Prefer the Todoist tools for task questions and the Gmail tools for email
questions. Never invent task IDs; only use IDs returned by the tools.
```

### Step 4: Add tools, including your own workflows

In the **Tools** section, select **Add tool**. The picker offers built-in n8n integrations (Todoist, Gmail, Slack), workflows in the same project, custom tools defined by a JSON schema, and external [MCP servers](https://docs.n8n.io/build/build-and-manage-agents). For this build, add the Todoist and Gmail integrations and attach their credentials. If you have never wired an MCP server into n8n, our [MCP server tutorial](/mcp-server-tutorial/) covers the setup.

Two details matter. First, the agent chooses tools from your instructions, so vague instructions produce vague tool choices. Second, sensitive tools can require approval before running. Enable it for anything that writes, such as creating tasks or sending email: the agent pauses, you approve or reject in chat, and it resumes.

Workflows as tools deserve a note: this is what separates a toy agent from a useful one. The agent decides when the workflow runs, and the workflow runs exactly as you built it, with its own credentials. The security win is real: an agent can add a note to your CRM through a workflow without ever holding write access to the CRM itself. You define a narrow contract, named inputs in, a controlled credential, a known output out, and the agent never sees the raw credentials.

### Step 5: Bundle behavior into a skill

A skill packages instructions with the tools needed for a specific task. Use skills when the agent handles several distinct tasks, each with its own steps, so the main instructions stay readable. Open the **Skills** section, select **Add skill**, give it a name and a short description, pick the tools it may use, and write the instructions the agent follows when it runs the skill. The agent picks the right skill from the description and the current request.

Example: a "Receipt logging" skill limited to the Gmail tool, instructed to find emailed receipts and report merchant, date, and total as a small table. The description ("Use when the user mentions receipts, invoices, or expenses") is what steers the agent to it.

### Step 6: Connect the Telegram channel

Open the **Channels** section and follow the Telegram setup. Create a bot token first: chat with `@BotFather`, send `/newbot`, answer the prompts, and paste the returned HTTP API token into n8n.

Two self-hosted caveats come straight from the docs. Connecting channels needs a public `WEBHOOK_URL`, because Telegram must reach your instance. And queue mode is not supported for agents yet: the docs warn connecting channels such as Telegram can fail in queue mode, so run agents in regular mode for now. If you run n8n in Docker, our [Docker Compose self-hosting guide](/n8n-docker-compose-setup/) shows how to set the webhook URL.

### Step 7: Preview and debug with sessions

Select **Preview** in the header to test without publishing: n8n starts a chat session with the current draft. If **Preview** is disabled, the draft has configuration errors, and n8n lists the items to resolve.

Every conversation becomes a **session**, which n8n stores so you can resume it later and the agent can recall context through memory. The **Sessions** tab shows past conversations with the messages exchanged, the tools used, and pending approvals. This is your debugger: when the agent picks the wrong tool, the session shows exactly what it called and with which inputs. The official walkthrough leaned on sessions and traces this way while fixing model and data policy errors in its Telegram build.

### Step 8: Publish the agent

Publishing snapshots the draft, so the running agent does not change while you keep editing. Check for errors (if **Publish** is disabled, n8n lists the items to resolve), then select **Publish**. The published version is what runs when someone chats, a channel triggers, or a schedule fires. Every publish adds a version to the publish history for restore or revert; **Revert changes** in the publish menu discards draft edits to match the published version, and **Unpublish** takes the agent offline while keeping the draft.

### Step 9: Add a schedule

Schedules let the agent run on its own, and they run only against the published version. In the **Schedules** section, describe the task and pick a frequency: hourly, daily, weekly, monthly, or custom cron. n8n shows the next and last run times plus the last outcome per schedule. The canonical example from the official walkthrough: a daily schedule that turns email action items into Todoist tasks, with the agent reading the inbox, extracting action items, and creating tasks untouched by human hands.

### Step 10: Call the agent from a workflow

Workflows use agents two ways: an inline agent node, or messaging a published agent. Both go through the **Message an Agent** node, verified in n8n 2.41.4 in our lab. Choose the agent in the required **Agent** field, write the **Message**, and the agent runs its reasoning loop and returns a reply for downstream nodes.

Three options matter, all confirmed in the lab install. **Require Specific Output Format** constrains the reply to a JSON schema, from a JSON example or defined directly, so later nodes get predictable fields. The Advanced collection holds **sessionId** and **session** for reusing a session across executions. **enableStreaming** streams the reply through connected Chat and Webhook triggers. Each message counts as one execution.

### Step 11: Enable agents on self-hosted n8n

From version 2.32.3, self-hosted n8n needs one environment variable: add `agents` to `N8N_ENABLED_MODULES`. That is all it takes to build and run agents. The full experience additionally sets up the n8n Assistant, where you describe an agent and n8n scaffolds it.

Lab-verified on n8n 2.41.4: the `agents` module ships in the install, its initializer loads the backend controllers for agents, skills, sessions, schedules, publishing, and channel integrations, and `N8N_ENABLED_MODULES=agents` is the documented switch. Two documented limits still apply on self-hosted: knowledge bases need a Daytona sandbox, and channels need a public `WEBHOOK_URL`. On an older install, see our guide to [keeping a self-hosted n8n instance updated](/how-to-update-n8n-self-hosted/) first.

## Troubleshooting

### Preview or Publish is disabled

The draft has configuration errors, and the Builder is refusing to run a broken agent. Read the error list next to the disabled button: usually a missing model, a tool without its credential, or an empty required field. Resolve every item and the button enables.

### The Telegram channel connects but never replies

On self-hosted n8n this almost always means Telegram cannot reach your instance. Set a public `WEBHOOK_URL` to the HTTPS address Telegram can call, then reconnect the channel. Also confirm you are not running queue mode: the docs warn it is not supported for agents yet and that connecting channels such as Telegram can fail in it.

### The agent cannot see images

This is a model capability problem. In the official walkthrough the builder hit this exact wall and switched to Claude Sonnet 5, after which image input worked. Open the **Model** field in the **Agent** tab and choose a vision-capable model if the assistant will read photos of receipts, sticky notes, or screenshots.

### Model or data policy errors during preview

These come from the model provider, not n8n: a region restriction, a content filter, or a key without the right permissions. Check the provider's key settings, verify the key has a funded billing method where required, and use the **Sessions** tab to see which call actually failed before changing anything. For systematic debugging of failed runs, see our [n8n error handling guide](/n8n-error-handling/).

### Episodic memory does nothing

Session memory, the memory of the current conversation, is on by default and needs no setup. Episodic memory, which recalls context from earlier sessions, is a separate toggle in the **Memory** tab and needs an OpenAI credential to store and retrieve memories. If earlier sessions feel forgotten, the toggle is probably on without the credential attached.

### WhatsApp or Microsoft Teams is not in the channel list

It is not missing; it is unsupported. n8n's agent channel integrations cover Slack, Telegram, Linear, and Discord, and explicitly exclude WhatsApp and Microsoft Teams. The workaround is a workflow bridge: use the platform's trigger node in a normal workflow and feed it into the **Message an Agent** node, which gives you an agent-backed bot on any platform n8n can receive messages from.
## FAQ

**What is the difference between n8n Agents and the n8n AI Agent node?**
The AI Agent node builds an agent inside one workflow canvas. n8n Agents is a first-class artifact beside your workflows, with its own model, instructions, tools, skills, memory, sessions, versions, channels, and schedules. Existing AI Agent node workflows keep working unchanged.

**How much do n8n Agents cost to run?**
One turn, one message in and one response out, counts as one execution. Tool and sub-agent calls inside the turn do not count separately, and agent executions share your plan's quota with workflows. Model costs are separate: agent models start with $2 of free n8n gateway credits, or bring an OpenRouter key with a monthly spend limit.

**Can I run n8n Agents on a self-hosted instance?**
Yes, from n8n 2.32.3, on every self-hosted plan except Enterprise, where support is coming soon. Add `agents` to `N8N_ENABLED_MODULES`. Knowledge bases need a Daytona sandbox, channels need a public `WEBHOOK_URL`, and queue mode is not supported for agents yet.

**Are n8n Agents ready for production?**
They are in Preview: test before publishing and require approval on tools that write to your systems. The draft and published version split exists for exactly this, letting you iterate in the draft while users run the last published snapshot.

**Which chat channels can an agent connect to?**
Slack, Telegram, and Linear per the docs, plus Discord per the launch announcement. WhatsApp and Microsoft Teams are not supported; bridge them with a workflow trigger feeding the Message an Agent node.

**Can an n8n agent use my existing workflows?**
Yes. Add any workflow in the same project as a tool and the agent decides when to run it, each run using the workflow's own credentials. For the memory side of the older node pattern, see our [chatbot memory tutorial](/n8n-chatbot-memory-tutorial/).

## Conclusion

n8n Agents moves the durable parts of an assistant, identity, memory, sessions, channels, schedules, versions, out of the workflow canvas into an artifact of its own, while workflows become the bounded, credential-safe tools the agent calls. The Telegram assistant above gives you the full loop: a chosen model, tools with approval boundaries, a skill that keeps instructions tidy, a schedule that works while you sleep, and a Message an Agent node that lets any workflow borrow the agent's judgment. Next, go deeper on retrieval with our [LangChain RAG tutorial](/n8n-langchain-rag-tutorial/), or see the full support-bot pattern in the [AI support chatbot walkthrough](/build-ai-support-chatbot-n8n/).
