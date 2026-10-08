---
title: "n8n AI Agent Tutorial: Build Your First AI Agent with Tools and Memory"
slug: "n8n-ai-agent-tutorial"
date: 2026-09-28T09:00:00+08:00
draft: false
description: "Build a working AI agent in n8n: connect a chat model, tools, and memory to the AI Agent node. Tested on n8n 2.40.7 with real node parameters, plus troubleshooting for the 5 most common failures."
categories: ["n8n"]
tags: ["n8n", "ai-agent", "automation", "openai", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Do I need an OpenAI API key to use the n8n AI Agent node?"
    a: "No. n8n 2.x ships chat-model sub-nodes for 25+ providers, including Anthropic, Google Gemini, DeepSeek, Groq, Mistral, xAI Grok, and Ollama for fully local models. You only need a key for whichever provider you choose."
  - q: "What is the difference between the AI Agent node and a Basic LLM Chain?"
    a: "A Basic LLM Chain sends one prompt and returns one answer. The AI Agent node runs a reasoning loop: it can call tools, observe results, and decide next steps over multiple iterations, which makes it suitable for multi-step tasks."
  - q: "Why is my n8n agent not calling any tools?"
    a: "The three usual causes are: no tool sub-node is actually connected (n8n requires at least one), the System Message doesn't tell the agent when to use tools, or the task is phrased so the model answers from memory instead. Connect a tool, name it explicitly in the system message, and check Return Intermediate Steps to see the agent's reasoning."
  - q: "How much does running an AI agent in n8n cost?"
    a: "n8n itself is free when self-hosted with no execution cap. Your cost is the model provider's API usage: agent loops consume more tokens than single prompts because of intermediate reasoning steps. Set Max Iterations to bound cost, and test with a cheap model first."
  - q: "Can I build n8n AI agents without coding?"
    a: "Yes. The AI Agent node, chat models, tools, and memory are all configured through the visual editor, no code required. The Code node and HTTP Request tool are there only if you want custom logic."
  - q: "Will my v1 AI Agent workflows break?"
    a: "Not immediately. Since n8n 1.82.0 all AI Agent nodes run as Tools Agent, and v1 workflows set to Tools Agent keep working. But n8n's docs warn that the v1 node will be removed in n8n 3.0, so migrate to the current node version when you can."
---

## Introduction

The n8n AI Agent node turns a language model into something that can *do* things: look up information, calculate, call APIs, and remember earlier conversation, all inside a visual workflow. This tutorial builds a working research-assistant agent step by step, using a real n8n 2.40.7 install I ran locally to verify every node name, option, and requirement below.

## Quick answer

Add an **AI Agent** node to a workflow, connect three things to it, a **chat model** (e.g. OpenAI), at least one **tool** (e.g. Calculator, Wikipedia), and optionally **memory** (Window Buffer Memory), then write a System Message describing the agent's job. The agent reasons in a loop, calls tools as needed, and returns a final answer. You must connect at least one tool, or the node won't run.

## Why n8n for AI agents: the numbers

n8n is one of the most-adopted workflow automation projects in open source: its GitHub repository sits at nearly 200,000 stars as of 2026, and n8n GmbH raised a $180M Series C in October 2025 at a $2.5B valuation. The platform ships 400+ built-in integrations, which matters for agents, every integration is a potential tool your agent can call.

The official docs describe the node plainly:

> "The AI Agent node lets you build an AI agent in n8n. Connect a chat model and one or more tools, and the agent decides which tools to call to complete a task.", [docs.n8n.io, AI Agent node](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/)

Two facts from those docs shape everything below. First: **"You must connect at least one tool sub-node to an AI Agent node."** An agent with no tools is just an expensive chatbot. Second: since n8n 1.82.0, the old "agent type" setting is deprecated, every current AI Agent node runs as a **Tools Agent**, and the v1 node will be removed entirely in n8n 3.0. If you're following an older tutorial that talks about "Conversational Agent" vs "Tools Agent" types, that choice no longer exists.

For background on the concepts, n8n points readers to [LangChain's agent documentation](https://js.langchain.com/docs/concepts/agents/) and their own [blog introduction to AI agents](https://blog.n8n.io/). If you haven't installed n8n yet, see our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) for context on where n8n fits; for general n8n failure modes, our [n8n error handling tutorial](/n8n-error-handling/) covers the Error Trigger workflow pattern.

## Prerequisites

- n8n running (I tested on **n8n 2.40.7**, installed via `npm install n8n` and started with `npx n8n`; the editor opens at `http://localhost:5678`). Self-hosted Community edition is free with no execution cap.
- An API key from **one** model provider: OpenAI, Anthropic, Google Gemini, DeepSeek, Groq, or Mistral. For a zero-cost option, run [Ollama](https://ollama.com/) locally and use n8n's Ollama Chat Model sub-node.
- 30 minutes. No coding required.

## Step 1, Create the workflow and add the AI Agent node

1. In the n8n editor, create a new workflow.
2. Add a **Manual Trigger** node (so you can test with one click).
3. Add an **AI Agent** node and connect the trigger to it.

The current node is `@n8n/n8n-nodes-langchain.agent` at typeVersion 3, I confirmed this by creating the node through n8n's own API on a live 2.40.7 instance. In the node you'll see the main settings:

- **Prompt (User Message)**: what you want the agent to do, e.g. `Research the current n8n pricing tiers and summarize them in a table`.
- **System Message**: the agent's role and rules. This is the highest-leverage field, be specific: *"You are a research assistant. Always use the Wikipedia tool for factual claims. Show your sources. If a tool fails, say so instead of guessing."*
- **Options**: **Max Iterations** (caps the reasoning loop, your cost control), **Return Intermediate Steps** (shows the agent's tool calls in the output, turn this on while learning), **Enable Fallback Model**, and **Require Specific Output Format**.

## Step 2, Connect a chat model

Click the **Chat Model** connector under the AI Agent node and add, for example, **OpenAI Chat Model**:

1. Create credentials with your OpenAI API key.
2. Pick a model. Start cheap while testing, the agent loop burns more tokens than a single prompt because every reasoning step is another model call.

No OpenAI key? The same connector offers Anthropic, Google Gemini, DeepSeek, Groq, Mistral, xAI Grok, Azure OpenAI, and **Ollama** for local models. The agent doesn't care which provider you use.

## Step 3, Connect at least one tool

This is the step the docs insist on: an AI Agent node **requires at least one connected tool**. Click the **Tools** connector and add tools that fit your task. n8n 2.40.7 ships these built-in tool sub-nodes (verified in the installed package):

| Tool | Good for |
|---|---|
| Calculator | Arithmetic the model shouldn't do from memory |
| Wikipedia | Factual lookups with citable sources |
| HTTP Request | Any REST API |
| Code | Custom JavaScript logic |
| SerpApi / SearXng | Live web search |
| WolframAlpha | Math and curated data |
| Vector Store | Retrieval over your own documents |
| Workflow | Calling another n8n workflow as a tool |

For our research assistant, connect **Wikipedia** and **Calculator**. Give each tool a clear name and description, the agent reads tool descriptions to decide when to use them.

## Step 4, Add memory (optional but recommended)

Without memory, every execution starts fresh. Connect **Window Buffer Memory** under the Memory connector so the agent remembers the conversation within a session. Set a **Session ID** (e.g. a user ID or chat ID), memory is keyed by it, so different sessions don't leak into each other. n8n also offers Redis, Postgres, MongoDB, and other memory backends if you outgrow the in-memory window.

## Step 5, Run and watch the agent think

1. In the AI Agent node options, enable **Return Intermediate Steps**.
2. Click **Execute step** on the Manual Trigger.
3. Open the AI Agent node's output and expand the intermediate steps: you'll see the model decide to call Wikipedia, observe the result, maybe call the Calculator, then compose the final answer.

That visible reasoning loop is the whole difference between an agent and a prompt. When something goes wrong, the intermediate steps tell you exactly which step failed, which is why our [n8n error handling guide](/n8n-error-handling/) pairs well with this tutorial for production setups.

### Importable workflow skeleton

The JSON below is the real workflow I created against n8n 2.40.7's API. Import it via **⋯ → Import from JSON**, then connect the Chat Model, Tools, and Memory sub-nodes on the canvas (sub-node connections are made visually, not in JSON):

```json
{
  "name": "AI Research Agent",
  "nodes": [
    {
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1.2,
      "position": [0, 0],
      "parameters": {}
    },
    {
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 3,
      "position": [300, 0],
      "parameters": {
        "prompt": "Research the current n8n pricing tiers and summarize them in a table with sources."
      }
    }
  ],
  "connections": {}
}
```

## Troubleshooting: 5 real failures and fixes

**1. The agent answers without calling any tools.** Most common cause. Fix: verify a tool sub-node is actually connected (the docs requirement is real, no tools, no tool calls), then make the System Message explicit: *"For any factual question, you MUST call the Wikipedia tool before answering."* Enable Return Intermediate Steps to confirm.

**2. "You must connect at least one tool" / node won't execute.** You added the AI Agent node but no tool sub-node. Connect Calculator or Wikipedia under the Tools connector and run again.

**3. The run stops with a max-iterations message.** The agent looped without converging, usually a vague task or a tool returning unusable data. Fix: raise **Max Iterations** slightly, but first simplify the task and tighten the System Message. Unbounded loops are also how API bills explode, so treat this as a cost signal, not just an error.

**4. Model provider errors (401/429).** 401 means your API key is wrong or revoked, re-enter credentials. 429 means rate limit, the agent loop makes many rapid calls, so it hits limits faster than single prompts. Add retries or switch to a cheaper/faster model for testing.

**5. Memory doesn't persist between runs.** Window Buffer Memory keys conversations by Session ID. If the session key changes every execution (e.g. you mapped it to a timestamp), each run starts fresh. Set a stable session key like a user ID. This bites hardest in chat-triggered agents, see the Chat Trigger + memory pattern in n8n's Advanced AI docs.

## Going further

- **Give your agent your own tools**: the HTTP Request tool turns any API into an agent tool, and the Workflow tool lets one agent call another workflow.
- **Let agents use MCP servers**: n8n can consume [MCP servers as tools](/mcp-server-tutorial/), which means any MCP server (like the ones in our [Cursor](/add-mcp-server-to-cursor/), [Windsurf](/windsurf-mcp-setup/), and [Claude Desktop](/connect-mcp-server-to-claude-desktop/) guides) can become an n8n agent tool.
- **Productionize**: add the [Error Trigger workflow](/n8n-error-handling/) so agent failures notify you instead of failing silently, and put a cost alert on your model provider account.

## FAQ

**Do I need an OpenAI API key to use the n8n AI Agent node?**
No. n8n 2.x ships chat-model sub-nodes for 25+ providers, including Anthropic, Google Gemini, DeepSeek, Groq, Mistral, xAI Grok, and Ollama for fully local models. You only need a key for whichever provider you choose.

**What is the difference between the AI Agent node and a Basic LLM Chain?**
A Basic LLM Chain sends one prompt and returns one answer. The AI Agent node runs a reasoning loop: it can call tools, observe results, and decide next steps over multiple iterations, which makes it suitable for multi-step tasks.

**Why is my n8n agent not calling any tools?**
The three usual causes are: no tool sub-node is actually connected (n8n requires at least one), the System Message doesn't tell the agent when to use tools, or the task is phrased so the model answers from memory instead. Connect a tool, name it explicitly in the system message, and check Return Intermediate Steps to see the agent's reasoning.

**How much does running an AI agent in n8n cost?**
n8n itself is free when self-hosted with no execution cap. Your cost is the model provider's API usage: agent loops consume more tokens than single prompts because of intermediate reasoning steps. Set Max Iterations to bound cost, and test with a cheap model first.

**Can I build n8n AI agents without coding?**
Yes. The AI Agent node, chat models, tools, and memory are all configured through the visual editor, no code required. The Code node and HTTP Request tool are there only if you want custom logic.

**Will my v1 AI Agent workflows break?**
Not immediately. Since n8n 1.82.0 all AI Agent nodes run as Tools Agent, and v1 workflows set to Tools Agent keep working. But n8n's docs warn that the v1 node will be removed in n8n 3.0, so migrate to the current node version when you can.

## Conclusion

You now have a working AI agent in n8n: chat model for reasoning, tools for acting, memory for continuity, and a System Message steering the whole loop. The pattern scales, swap Wikipedia for your CRM's API, add a second agent as a tool, and you've got a real automation. Next, harden it with the [n8n error handling tutorial](/n8n-error-handling/) so failures page you instead of vanishing.
