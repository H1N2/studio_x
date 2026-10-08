---
title: "n8n vs Make for AI Agents: Which One Should You Build On?"
slug: "n8n-vs-make-ai-agents"
date: 2026-09-29T21:45:00+08:00
draft: false
description: "n8n vs Make for AI agents, compared head-to-head: verified builds, per-execution vs per-operation pricing math, and model freedom. Pick the right one."
categories: ["n8n", "make"]
tags: ["n8n", "make", "ai-agent", "automation", "comparison", "langchain", "llm", "rag"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Can Make AI Agents use my own OpenAI or Anthropic API key?"
    a: "Yes, but only on paid plans. Make's official AI Agents guide states that Free plan users must select Make's built-in AI Provider; paid users can connect OpenAI, Anthropic, Gemini, or the built-in provider. On n8n there is no such restriction: chat-model sub-nodes for 25+ providers work on the free self-hosted Community edition too."
  - q: "Can I run an n8n AI agent on local models with zero API cost?"
    a: "Yes. Connect the Ollama Chat Model sub-node to the AI Agent node and run models like Llama 3 locally on your own machine or server. Combined with self-hosted n8n Community (free, unlimited executions), the only cost is your hardware and electricity."
  - q: "Which is cheaper for a high-volume AI agent, n8n or Make?"
    a: "n8n, by a wide margin at scale. n8n bills per workflow execution, one agent run counts as one execution no matter how many tool calls it makes inside. Make bills per operation, and every module execution inside the agent run (the agent module plus each tool call) consumes operations. At 10,000 agent runs a month, n8n Cloud Pro is €60/month (or free self-hosted), while Make needs tens of thousands of operations in credit packs on top of the base plan."
  - q: "Do I need to write code to build AI agents on either platform?"
    a: "No. Both core paths are visual: n8n's AI Agent node with chat-model, tool, and memory sub-nodes, and Make's AI Agents module with natural-language instructions and tools. Code is optional on both, n8n has a Code node and HTTP Request tool, Make has Make Code (Python/JavaScript) for technical users."
  - q: "Which is better for a RAG agent over my private documents?"
    a: "n8n, if you want full control. It has dedicated Vector Store nodes (Pinecone, Qdrant, and more) and can run the whole stack, embeddings, storage, and the agent, on your own infrastructure, which keeps private documents in-house. Make offers Knowledge files stored in a built-in RAG vector database, which is simpler to set up but lives on Make's cloud. Our [n8n vector store tutorial](/n8n-vector-store-tutorial/) walks through the n8n RAG setup step by step."
  - q: "Can an n8n agent and a Make scenario work together?"
    a: "Yes, through webhooks. Expose an n8n workflow with a Webhook trigger and call it from Make's HTTP module, or expose a Make Custom Webhook and call it from n8n's HTTP Request tool. This lets you keep legacy Make scenarios while moving agent logic to n8n, or vice versa."
---

## Introduction

If you're picking a platform to build AI agents in 2026, n8n and Make are the two serious contenders outside the pure-code world. Both let you give a language model tools, memory, and a job to do, but they charge differently, architect agents differently, and suit different teams. This guide compares them on the dimensions that actually decide the choice: agent architecture, model freedom, memory and knowledge, the real cost math for agent workloads, and who should pick which. The n8n side below is grounded in a build I verified on n8n 2.40.7 (see our full [n8n AI agent tutorial](/n8n-ai-agent-tutorial/)); the Make side follows Make's official AI Agents documentation.

## Quick answer

Choose n8n for AI agents if you want self-hosting, free local models, and flat per-execution pricing that scales. Choose Make for the simplest no-code setup and 2,000+ integrations. At high volume, n8n's per-execution billing beats Make's per-operation billing.

## The numbers that actually matter

Four statistics frame this whole comparison, all timestamped to September 2026:

- **n8n Cloud pricing:** Starter €24/month for 2,500 workflow executions, Pro €60/month for 10,000 executions, billed monthly; annual billing drops these to roughly €20 and €50. The self-hosted Community edition remains free with unlimited executions. Billing is per *execution*, one workflow run counts as one execution however many nodes it contains ([CloudZero's n8n pricing breakdown, updated Sept 10, 2026](https://www.cloudzero.com/blog/n8n-pricing/)).
- **Make pricing:** Free 1,000 operations/month; Core $9/month (annual) for 10,000 operations; Pro $16/month (annual) for 10,000 operations; Teams $29/month (annual) for 10,000 operations. Billing is per *operation*, every module execution counts, including the trigger ([Latenode's Make vs Zapier comparison, Sept 2026](https://latenode.com/blog/platform-comparisons-alternatives/zapier-alternatives/make-vs-zapier-similarities-and-differences-of-automation-tools)).
- **Make's scale:** "Used by more than 200,000 businesses around the world," with Make AI Agents able to draw on "over 2,000 apps and more than 30,000 actions" (Make's launch announcement, April 2025).
- **n8n's scale:** the open-source project sits at nearly 200,000 GitHub stars, n8n GmbH raised a $180M Series C in October 2025 at a $2.5B valuation, and the platform ships 400+ built-in integrations, each one a potential agent tool.

Two vendor statements are worth quoting directly. On the n8n side, the official docs describe the core building block:

> "The AI Agent node lets you build an AI agent in n8n. Connect a chat model and one or more tools, and the agent decides which tools to call to complete a task.", [docs.n8n.io, AI Agent node](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/)

On the Make side, CEO Fabian Veit framed the April 2025 launch of Make AI Agents like this:

> "With Make AI Agents, automation moves into a new realm of intelligence and flexibility. When businesses can automate without rigid rules and setups, the capabilities are endless.", [SiliconANGLE, April 2025](https://siliconangle.com/2025/04/14/make-launches-ai-agents-handle-complex-automations-real-time/)

## Prerequisites

- A free n8n account or a local n8n install if you want to follow the n8n build (the Community edition is free; I verified these steps on n8n 2.40.7).
- A free Make account if you want to follow the Make setup.
- One model-provider API key (OpenAI, Anthropic, or Google), or Ollama for a zero-cost local model on the n8n side.
- About 45 minutes to work through both builds.

## Step 1, Understand the two agent architectures

The architectural difference drives everything else.

**n8n: the agent is a node in a workflow.** The AI Agent node (`@n8n/n8n-nodes-langchain.agent`, typeVersion 3) sits on the canvas like any other node, with diamond-shaped sub-node connectors underneath it. You attach a **chat model** (required), **memory** (optional), **tools** (at least one required), and optionally an **output parser**. The model, tools, and memory are separate canvas objects wired into the agent, the LangChain-style composition is visible and inspectable. Since n8n 1.82.0, every AI Agent node runs as a Tools Agent; the old agent-type dropdown is gone. n8n can also consume external MCP servers as tools and expose its own workflows as an MCP server, so agents plug into the wider MCP ecosystem on both sides.

**Make: the agent is a module in a scenario.** Per [Make's official AI Agents guide](https://github.com/integromat/make-skills/blob/HEAD/skills/make-scenario-building/ai-agents.md) (published in Make's own `integromat/make-skills` repo), a **Make AI Agents (New)** module sits inside a scenario and provides "non-deterministic, AI-driven logic", unlike a Router or filter, the module itself decides which tools to call, how many times, and in what order, based on its instructions and the incoming bundle. You configure an AI provider, write instructions, optionally attach **Knowledge** files (stored in the agent's long-term memory as a RAG vector database), equip tools, and at runtime the module outputs a single bundle with its result.

The practical upshot: n8n's agent is a transparent composition of parts you can see and swap; Make's agent is a managed reasoning unit you configure with words. n8n gives you more control over the loop; Make gives you a shorter path from idea to running agent.

## Step 2, Run the cost math for a real agent workload

This is where the billing models collide, so let's make it concrete. Take a customer-support agent that handles 1,000 user requests a month. Each request makes the agent reason and call tools about 8 times on average (look up the order, check the knowledge base, draft the reply, log the ticket).

**On n8n:** 1,000 requests = 1,000 workflow executions. The 8 internal tool calls per run cost nothing extra, n8n counts the run, not the steps. That fits inside Cloud Starter's 2,500 included executions at €24/month, or costs nothing beyond a ~$5–20/month VPS on self-hosted Community. Your only variable cost is the model provider's token bill, which exists on both platforms.

**On Make:** 1,000 requests × ~8 module executions (the AI agent module plus each tool call) ≈ 8,000 operations. That fits inside Core's 10,000 operations at $9/month (annual billing). So at this volume, Make is actually cheaper on paper.

Now scale to 10,000 requests a month. **n8n:** 10,000 executions = Cloud Pro at €60/month, or still free self-hosted. **Make:** ~80,000 operations, which means buying credit packs (Make offers 20k/40k/80k tiers) on top of the base plan, the bill grows with every tool call the agent makes. Agents are exactly the workload that multiplies operations: more reasoning steps, more tool calls, more ops.

The rule of thumb: **Make wins on price at low volume; n8n wins decisively at high volume or high tool-call counts**, because its per-execution meter doesn't spin faster when the agent thinks harder. If you self-host n8n, the platform cost is flat regardless of volume.

## Step 3, Build the agent in n8n (verified on 2.40.7)

These steps come from a build I ran on a live n8n 2.40.7 instance, node names, options, and requirements are as the editor actually shows them. The full walkthrough with screenshots-level detail is in our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/); here's the condensed version for comparison purposes:

1. Add a **Manual Trigger** and an **AI Agent** node; connect the trigger to the agent.
2. Click the **Chat Model** connector and attach, say, **OpenAI Chat Model** with your API key. No key? The same connector offers Anthropic, Google Gemini, DeepSeek, Groq, Mistral, xAI Grok, and **Ollama** for fully local models.
3. Click the **Tools** connector and attach at least one tool, the node refuses to run without one. Built-ins include Calculator, Wikipedia, HTTP Request, Code, SerpApi, Vector Store, and Workflow (call another workflow as a tool).
4. Optionally attach **Window Buffer Memory** under the Memory connector and set a **Session ID** so each user gets their own conversation context.
5. Write the **Prompt** and **System Message** (name the tools explicitly in the system message so the agent actually uses them), enable **Return Intermediate Steps**, and execute.

Two verified behaviors worth knowing: the agent runs a visible reasoning loop you can inspect step by step, and **Max Iterations** in the node options is your cost control, it caps how many reasoning cycles one execution may take.

## Step 4, Build the agent in Make (per the official docs)

I haven't run a Make agent first-hand, so what follows is Make's documented setup, not a lab walkthrough, sourced from [Make's official AI Agents guide](https://github.com/integromat/make-skills/blob/HEAD/skills/make-scenario-building/ai-agents.md):

1. Place a **Make AI Agents (New)** module in the scenario flow.
2. **Configure an AI provider**, OpenAI, Anthropic, Gemini, or Make's built-in AI Provider. Note the plan restriction: Free plan users must use Make's built-in provider; paid plans can choose any supported provider.
3. **Write instructions** defining the agent's role, goals, constraints, and step-by-step behavior.
4. **Add Knowledge** (optional), files stored in the agent's long-term memory, kept in a RAG vector database with relevant chunks retrieved per request.
5. **Equip tools**, the agent decides at runtime which tools to call, how many times, and in what order.
6. Run and inspect the execution log; once the output matches your goal, schedule or activate the scenario.

Make also offers **Maia**, a natural-language scenario builder, and **Sub-Agents**, attach other Make agents as tools of an orchestrator agent, which mirrors n8n's "agent as tool" pattern but configured entirely in the visual builder.

## Step 5, Score your decision

| Dimension | n8n | Make |
|---|---|---|
| Agent primitive | AI Agent node with visible sub-node composition (LangChain-based) | AI Agents module with natural-language configuration |
| Model choice | 25+ providers incl. Ollama local models, no plan restrictions | OpenAI/Anthropic/Gemini/built-in; Free plan locked to built-in provider |
| Tools ecosystem | 400+ integrations + HTTP/Code + MCP tools | 2,000+ apps, 30,000+ actions |
| Memory / knowledge | Memory sub-nodes (Window Buffer, Redis, Postgres, MongoDB…) | Knowledge files in built-in RAG vector database |
| Multi-agent | Attach agents/workflows as tools; MCP interop | Sub-Agents as tools of an orchestrator |
| Self-hosting | Yes, Community edition free, unlimited executions | No, cloud only |
| Billing unit | Per workflow execution (agent's internal steps are free) | Per operation (each tool call burns ops) |
| Best at | Technical teams, private/local models, high volume, RAG on own infra | No-code teams, broad app coverage, fastest time-to-first-agent |

**Choose n8n if:** your team is technical, data must stay on your infrastructure, you want local models, your agents make many tool calls per run, or you need MCP integration in both directions. **Choose Make if:** your team is non-technical, you value the 2,000+ app catalog and 30,000+ actions, you want zero infrastructure to maintain, and your agent volume is modest. If you're migrating from another platform entirely, our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) covers the cost and rebuild math; for keeping agents healthy in production, see [n8n error handling](/n8n-error-handling/).

## Troubleshooting

**1. n8n agent never calls any tools.**
The three usual causes, all verified: no tool sub-node is actually connected (the node requires at least one and won't run without it), the System Message doesn't tell the agent when to use tools, or the prompt is phrased so the model answers from memory. Connect a tool, name it explicitly in the system message, and enable Return Intermediate Steps to watch the reasoning.

**2. n8n agent mixes up conversations between users.**
Window Buffer Memory is keyed by Session ID. If you leave the default session, every user shares one conversation context. Set the Session ID to a per-user value (user ID, chat ID) before going live, otherwise user A will see user B's history.

**3. n8n self-hosted: Ollama model won't connect from Docker.**
`localhost` inside the n8n container is the container itself, not your host. Point the Ollama base URL at `http://host.docker.internal:11434` instead of `http://localhost:11434`. This is the single most common local-model setup failure.

**4. Make agent burns through operations far faster than expected.**
Remember the meter: every tool call the agent makes is a module execution that consumes operations, and agent runs are non-deterministic, one request might use 3 tool calls, the next 15. Watch the execution log per request, set a monthly operations alert, and consider capping tool counts via tighter instructions before upgrading credit packs.

**5. Make Free plan: "provider not available" when attaching an API key.**
That's the plan restriction, not a bug. Free plan users must select Make's built-in AI Provider; connecting your own OpenAI/Anthropic/Gemini key requires a paid plan.

## FAQ

See the FAQ section in the front matter above (rendered on-page below the article).

## Conclusion

n8n and Make both build capable AI agents, but they optimize for different buyers: n8n for control, privacy, and flat costs at scale; Make for speed, simplicity, and the broadest app catalog. If your agent will handle real volume or touch private data, n8n's per-execution billing and self-hosting are hard to beat. If you want your first agent running this afternoon with no infrastructure, start with Make.

Next step: build the real thing. Our [n8n AI agent tutorial](/n8n-ai-agent-tutorial/) walks through a working tools-and-memory agent on n8n 2.40.7, node by node.
