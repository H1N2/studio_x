---
title: "How to Build AI Agents with the n8n Agent Builder: From Zero to a Working Agent"
slug: "n8n-agent-builder-tutorial"
date: 2026-10-07T18:30:00+08:00
draft: false
description: "Build AI agents with the n8n Agent Builder: define the agent, attach workflows as tools, configure memory, and gate risky actions with human approval."
categories: ["n8n"]
tags: ["n8n", "ai agent", "agent builder", "human-in-the-loop", "mcp", "sub-agents", "automation"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Is the n8n Agent Builder available on self-hosted n8n?"
    a: "The Agents surface launched as a preview on n8n Cloud for the latest stable version, so self-hosted users may not see it yet. If it is missing on your instance, keep using the in-workflow AI Agent node pattern, which still works, and upgrade when the feature reaches your edition."
  - q: "What is the difference between the Agent Builder and the classic AI Agent node?"
    a: "The classic pattern assembles an agent inside one workflow canvas from a Chat Trigger, memory, an AI Agent node, a model, and tools. The Agent Builder moves the durable agent identity, sessions, draft and published versions, and multiple entry points into a shared artifact that sits beside workflows instead of inside one."
  - q: "Can my agent call workflows I already built?"
    a: "Yes. Existing workflows can be exposed as tools, which is one of the four documented tool types alongside built-in n8n integrations, MCP servers, and sub-agents. Give each tool workflow a narrow contract with named inputs and its own credential so the agent gets only the access it needs."
  - q: "How does human approval work for agent tool calls?"
    a: "You add a human review step on the connection between the agent and the tool. When the agent tries to call a gated tool, the run pauses and waits for a person to approve or deny. Approval runs the tool with the parameters the AI chose, and denial cancels the action."
  - q: "Agent Builder vs the n8n AI Assistant: which one do I use?"
    a: "They do different jobs. The AI Assistant generates workflows from a natural-language prompt, while the Agent Builder defines the agent itself: its instructions, model, tools, memory, channels, and approval rules. Use the Assistant to draft workflows, then expose the finished ones as tools to your agent."
  - q: "Do I need to rewrite my old AI Agent workflows?"
    a: "No. The old in-workflow agent pattern still works, and the Message an Agent node lets a workflow call a published agent, so old and new patterns interoperate. Migrate a workflow to the builder only when it needs shared sessions, channels, or draft and published versions."
---

## Introduction

For years, building an AI agent in n8n meant assembling one inside a workflow canvas: a Chat Trigger, a memory node, an AI Agent node, a language model, and a pile of tools wired together by hand. That pattern still works, but n8n now offers a dedicated Agent Builder, a separate surface where the agent itself is the artifact. You describe the agent's purpose in plain language, choose its model, attach tools, configure memory, connect channels such as Slack or Telegram, and publish it. This tutorial walks you through that full flow, from an empty builder to a working agent with workflows mounted as tools and human approval guarding the risky steps.

## Quick answer

Open the Agent Builder, name the agent and write its instructions, pick a model, attach tools including existing workflows, configure memory, connect a channel, test, then publish. Gate destructive tools with human review.

## Evidence

Two facts frame why this matters now. First, on September 25, 2026, n8n introduced the Agents surface, making an Agent a first-class project artifact with its own model, instructions, tools, memory, sessions, draft, published version, channels, and schedules, sitting beside workflows rather than inside one canvas. The current n8n Agents documentation describes it as the place for work that is too open-ended for a fixed workflow, a characterization confirmed by an independent review of the docs on September 26, 2026. Second, four days later, n8n 2.42.0 (released September 29, 2026) gave the Agent Builder a system-level UX overhaul: a redesigned agent layout, clearer sub-agent guidance, a more compact configuration header, better activity and message visibility, capability chips, and project breadcrumbs.

On safety, n8n's own release notes state the design principle directly: "A gated tool cannot execute unless a human explicitly approves the action, giving you deterministic control over high-impact operations like deleting records, writing to production systems, or sending high-impact emails." That principle is implemented as [human-in-the-loop review for AI tool calls](https://docs.n8n.io/build/integrate-ai/ai-examples/human-in-the-loop-for-tools), which pauses the run until a person approves or denies the call. For the broader picture of how agents, models, and tools fit together in n8n, the [AI integration documentation hub](https://docs.n8n.io/build/integrate-ai) is the official starting point.

## Prerequisites

- An n8n instance on the latest stable version (the Agents surface launched as a preview on n8n Cloud; if you are self-hosted, see the [self-hosted install guide](/install-n8n-ubuntu-vps/) and the troubleshooting section below).
- An API key for at least one language model provider, such as OpenAI or Anthropic, stored as an n8n credential.
- One or two existing n8n workflows you want the agent to call as tools (a lookup workflow and a notification workflow are ideal first candidates).
- Basic familiarity with the classic [AI Agent node pattern](/n8n-ai-agent-tutorial/), so the differences are clear.

## Step-by-step guide

### Step 1: Create the agent and write its instructions

Open n8n and create a new Agent from the Agents surface. Give it a specific name, such as "Support Triage Agent", and write its instructions in plain language. The instructions are the agent's system prompt, so be concrete about the job, the tools it may use, and the boundaries it must respect. A good starting template:

> You are a support triage agent. When a message arrives, classify it as billing, technical, or general. Use the lookup tool to fetch account details, then draft a reply. Never issue refunds or delete records without human approval. If you are unsure which tool fits, ask the user instead of guessing.

Every sentence here survives on its own: the model sees the instructions and the tool list, not your canvas wiring, so tool names and descriptions carry the real design weight. If you have worked with [n8n agent skills](/n8n-agent-skills-tutorial/), the same discipline applies: verb-first tool names and specific descriptions beat clever prompting.

### Step 2: Choose the language model

Attach a language model to the agent and connect the credential you prepared. For a first build, a mid-tier chat model keeps iteration cheap while you debug tool selection. If your provider offers both chat and reasoning models, start with chat for responsiveness and reserve reasoning models for agents that plan multi-step work.

### Step 3: Attach tools, including your existing workflows as tools

This is where the builder earns its keep. An agent can use four kinds of tools: built-in n8n integrations, MCP servers, existing workflows exposed as tools, and sub-agents for delegated work. Start with one workflow tool.

Prepare a minimal tool workflow first. The example below is a real n8n workflow JSON skeleton: a Webhook trigger feeding a Set node. Save it as its own workflow before attaching it, since the agent references the saved workflow as a tool.

```json
{
  "name": "Account lookup tool",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "account-lookup",
        "responseMode": "responseNode"
      },
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [240, 300]
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            {
              "id": "lookup-result",
              "name": "accountStatus",
              "value": "={{ $json.accountId ? 'active' : 'unknown' }}",
              "type": "string"
            }
          ]
        }
      },
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "name": "Set",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [460, 300]
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{ "node": "Set", "type": "main", "index": 0 }]]
    }
  }
}
```

In production this workflow would query your CRM or database; the shape is what matters. When you expose it as a tool, give it a narrow contract: named inputs, a controlled credential owned by the workflow, a known output, and, for anything destructive, an approval boundary (covered in Step 5). A workflow tool gives the agent one safe action instead of broad access to every system, which is exactly the point.

Repeat for a second tool, such as a notification workflow that posts to Slack. Two tools are enough to see real tool selection behavior in the test chat. If your agent needs to reach external tool servers, MCP servers attach as tools the same way; n8n's MCP support keeps maturing with each release.

### Step 4: Configure memory, sessions, and knowledge

Agents ship with memory and sessions so context survives across interactions. Open the agent's memory settings and set a session key derived from something stable, like the channel plus the user ID, rather than a single shared default. Then raise the context window beyond the small default so multi-turn troubleshooting does not lose the thread. The Sessions tab records the conversation, the tools called, outputs, errors, and pending approvals, which makes it your primary debugging surface later.

If the agent needs grounding in your own documents, attach knowledge files such as CSVs or PDFs, and keep them current. For long-running support agents, memory is not optional; it is what turns a stateless chatbot into an assistant that remembers the open ticket.

### Step 5: Gate sensitive tools with human approval

Now the safety work. Decide which tools may run autonomously and which require a person. Lookups and drafts are usually safe to automate; refunds, deletions, production writes, and outbound customer messages are not.

In the builder, find the connection from the agent to the tool you want to gate, click the **+** icon on that connection, and choose **Add human review step** (hovering shows the tooltip). The Tools panel opens with nodes you can use to handle the review step; pick the channel your reviewers actually watch. Approval and denial have precise semantics: approval lets the tool run with the parameters the AI selected, while denial cancels the action. Because the review step uses standard n8n integrations, approvals are not limited to one interface: you can route a Slack-initiated action to a manager for approval by email, for example.

One subtlety worth designing for: how the agent is told about a denial determines whether it recovers gracefully or gets confused, so say it in the instructions. Add a line like "If a tool call is denied, explain what was blocked and offer a safe alternative." That single sentence prevents the most common approval-loop failure, where the agent retries the blocked action with slightly different parameters.

### Step 6: Connect a channel, test, and publish

Assign the agent a channel, such as Slack, Telegram, Discord, or Linear, so it can receive real messages. Before publishing, test in the builder chat: send a message that should trigger the lookup tool, then one that should hit the gated tool, and watch the Sessions tab to confirm the tool call, the approval pause, and the resumed run.

Publishing creates a versioned release. Editing the draft afterwards does not silently change the published agent, so iterate freely in draft and publish deliberately. The same published agent can then answer in a channel, run on a schedule, or receive a message from another workflow. n8n describes three ways agents and workflows combine: the agent in charge (the agent interprets requests and workflows serve as tools), the workflow in charge (the workflow controls the sequence and calls agents for AI-driven tasks), and a mixed model where each handles what it does best. The [Message an Agent node](/n8n-agents-tutorial/) is the link for workflow-led designs, and the mixed model is where most production setups land.

### Step 7: Upgrade path for self-hosted builders

If you run n8n yourself with Docker Compose and want the newest Agent Builder UX, upgrade to at least 2.42.0:

```bash
docker pull n8nio/n8n:2.42.0
docker compose up -d
docker compose logs -f n8n
```

Wait for the startup logs to settle, then open the editor and confirm the version in the UI. Back up your database volume before any major upgrade, and test the agent in draft before republishing, since node behavior occasionally shifts between versions.

## Troubleshooting

**The Agents surface is missing on my self-hosted instance.**
The Agents feature launched as a preview on n8n Cloud for the latest stable version, so older or self-hosted installs may simply not have it. First confirm you are on the latest stable; if the surface is still absent, stay on the classic in-workflow AI Agent node pattern, which n8n continues to support. The two patterns interoperate through the Message an Agent node, so nothing you build now is wasted.

**A sub-agent's tools fail when it runs under an older parent agent.**
This was a real compatibility bug: an AI Agent Tool could not use its own tools when operating under a pre-v3 parent agent, which broke nested and hierarchical agent designs. n8n fixed it in 2.42.0. Upgrade both the parent and the sub-agent workflows to 2.42.0 or later, then re-run the nested call and check the Sessions tab for the tool execution.

**The agent keeps retrying an action a reviewer denied.**
Denial cancels the tool call, but the agent only recovers gracefully if its instructions say what to do next. Add an explicit instruction: when a tool call is denied, explain the block and offer a safe alternative instead of retrying. Also route the approval to the right person through a channel they actually monitor; an approval request nobody sees is functionally a denial with extra latency.

**The agent calls a workflow tool and gets an access error.**
Workflow tools respect n8n's sharing and permission model, so an agent running under one user may not be able to invoke a workflow owned by another. n8n 2.42.0 improved these errors to link directly to the relevant workflow settings, so follow that link and check sharing first. As a rule, give tool workflows their own service-owned credentials rather than borrowing a personal one, so permissions do not break when someone leaves the team.

**The agent forgets earlier conversation turns.**
Check the Sessions tab and the memory configuration. The usual causes are a session key that collides across users (everyone sharing one default session) or a context window left at the small default. Key memory on a stable identifier from the trigger, such as channel plus user ID, and raise the context window length for support-style agents.

## FAQ

**Is the n8n Agent Builder available on self-hosted n8n?**
The Agents surface launched as a preview on n8n Cloud for the latest stable version, so self-hosted users may not see it yet. If it is missing on your instance, keep using the in-workflow AI Agent node pattern, which still works, and upgrade when the feature reaches your edition.

**What is the difference between the Agent Builder and the classic AI Agent node?**
The classic pattern assembles an agent inside one workflow canvas from a Chat Trigger, memory, an AI Agent node, a model, and tools. The Agent Builder moves the durable agent identity, sessions, draft and published versions, and multiple entry points into a shared artifact that sits beside workflows instead of inside one.

**Can my agent call workflows I already built?**
Yes. Existing workflows can be exposed as tools, which is one of the four documented tool types alongside built-in n8n integrations, MCP servers, and sub-agents. Give each tool workflow a narrow contract with named inputs and its own credential so the agent gets only the access it needs.

**How does human approval work for agent tool calls?**
You add a human review step on the connection between the agent and the tool. When the agent tries to call a gated tool, the run pauses and waits for a person to approve or deny. Approval runs the tool with the parameters the AI chose, and denial cancels the action.

**Agent Builder vs the n8n AI Assistant: which one do I use?**
They do different jobs. The AI Assistant generates workflows from a natural-language prompt, while the Agent Builder defines the agent itself: its instructions, model, tools, memory, channels, and approval rules. Use the Assistant to draft workflows, then expose the finished ones as tools to your agent.

**Do I need to rewrite my old AI Agent workflows?**
No. The old in-workflow agent pattern still works, and the Message an Agent node lets a workflow call a published agent, so old and new patterns interoperate. Migrate a workflow to the builder only when it needs shared sessions, channels, or draft and published versions.

## Conclusion

The n8n Agent Builder turns agent construction from node plumbing into system design: you define the agent's purpose, attach narrowly scoped tools including your existing workflows, configure memory and sessions, and gate the dangerous actions behind human approval. Build the draft, test the approval path in the Sessions tab, and publish deliberately. If you want to deepen the design discipline behind tool naming and descriptions, read our [n8n agent skills tutorial](/n8n-agent-skills-tutorial/) next; and for the workflow-led side of the same architecture, our [n8n Agents overview](/n8n-agents-tutorial/) covers the Message an Agent pattern.
