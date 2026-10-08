---
title: "How to Use Ollama with n8n AI Agent: Run Local LLMs That Actually Call Tools"
slug: "n8n-ai-agent-ollama-tutorial"
description: "Connect Ollama to n8n's AI Agent: pick a tool-capable local model, fix skipped tool calls with Force Tool Call on First Iteration, and add a fallback model."
date: 2026-10-04
draft: false
categories: ["n8n"]
tags: ["n8n", "ollama", "ai-agent", "local-llm", "tool-calling", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Which Ollama models work best with the n8n AI Agent?"
    a: "Use a model whose Capabilities line in `ollama show` includes tools. qwen3:8b and llama3.1:8b are the most reliable small choices in 2026. Larger models follow tool schemas more accurately, but they need more VRAM. Avoid tiny or non-instruct models, they frequently ignore the tool definitions entirely."
  - q: "Do I need an API key to use Ollama in n8n?"
    a: "No. The n8n Ollama credential only asks for a Base URL, which defaults to http://localhost:11434. There is no API key because Ollama runs on your own machine. You only pay with your own hardware, not per token."
  - q: "Can I use Ollama with n8n Cloud?"
    a: "Not directly. n8n Cloud cannot reach http://localhost:11434 on your laptop. You would need to expose Ollama through a public URL or tunnel, which defeats the privacy benefit. Ollama pairs naturally with self-hosted n8n, see our install-n8n-ubuntu-vps guide."
  - q: "What does Force Tool Call on First Iteration actually do?"
    a: "It binds the model with tool_choice set to required on the first response of each run, so the model must call at least one tool before answering. Later iterations stay unrestricted. It was added in n8n 2.40 for the AI Agent node v3 and Agent Tool v3, and it is off by default."
  - q: "How much RAM do I need to run Ollama for n8n agents?"
    a: "An 8B quantized model like qwen3:8b needs roughly 6 to 8 GB of free RAM or VRAM. 70B models need 40 GB or more. If the model loads slowly or the machine swaps, pick a smaller quantization or a smaller model rather than fighting the hardware."
  - q: "Will the agent still work if Ollama crashes mid-run?"
    a: "Yes, if you enable the AI Agent's Enable Fallback Model option and wire a second chat model on the canvas. n8n switches to the fallback when the primary model fails, instead of failing the whole execution."
---

## Introduction

Running your n8n AI Agent on a cloud LLM means every run costs tokens and every prompt leaves your network. Ollama removes both problems: it serves open models on your own machine, and n8n talks to it over plain HTTP with no API key. This tutorial walks you through the full setup, from pulling a tool-capable model to fixing the one problem that breaks most Ollama agents, which is the model answering in prose and silently skipping your tools. It is written for n8n 2.40 and later, self-hosted, and assumes you already have a working n8n instance.

## Quick answer

Attach Ollama Chat Model to AI Agent node, set Base URL to Ollama host, pick a model supporting tools like qwen3:8b, and enable Force Tool Call on First Iteration so it calls tools instead of replying in prose.

## Evidence: why local agents matter in 2026

Two numbers explain the momentum. As of October 4, 2026, the Ollama repository holds 182,180 GitHub stars, and n8n holds 206,644 stars, which puts both projects among the most-starred open-source AI tools in the world. Local inference stopped being a hobbyist niche the moment those curves crossed enterprise tooling.

The tooling caught up with the demand in September 2026. n8n 2.40, released September 15, 2026, added an opt-in "Force Tool Call on First Iteration" option to the AI Agent node v3 and Agent Tool v3. The official changelog describes exactly the failure this tutorial fixes: the option helps "smaller or less compliant models (e.g. Mistral-Small on IONOS, vLLM, Ollama) that otherwise reply in prose and skip wired tools." The node itself is even blunter. Its built-in description, verified in the n8n 2.41.3 source, reads: "Useful for smaller models that otherwise skip tool calls; the model must support forced tool choice."

That last clause matters. Forcing a tool call only works if the model understands tool schemas in the first place, which is why model selection is a full step below rather than an afterthought. The [Ollama Chat Model documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmchatollama/) covers the sub-node's settings, the [AI Agent node documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/) covers agent options including fallback models, and the [Ollama documentation](https://ollama.com/docs) covers the server side. The [Ollama GitHub repository](https://github.com/ollama/ollama) is the primary source for releases and model support discussions.

## Prerequisites

- n8n 2.40 or later, self-hosted. Check yours under Settings, About n8n. If you are behind, follow our [how-to-update-n8n-self-hosted](/how-to-update-n8n-self-hosted/) guide first.
- Ollama installed on a machine n8n can reach. macOS, Windows, and Linux are all supported.
- A pulled model with tool support, for example qwen3:8b. Budget 6 to 8 GB of free RAM or VRAM for an 8B quantized model.
- Basic comfort with the n8n canvas: adding nodes, connecting sub-nodes, and opening node settings.

## Step-by-step guide

### Step 1: Install Ollama and pull a tool-capable model

Install Ollama with the official script on Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

On macOS and Windows, download the app from ollama.com and start it once. Then pull a model and confirm it is really there:

```bash
ollama pull qwen3:8b
ollama list
```

The `ollama list` output should show `qwen3:8b` with its size and modified date. Now verify the part most tutorials skip, tool support:

```bash
ollama show qwen3:8b
```

Look for the `Capabilities` line in the output. If it includes `tools`, the model can consume n8n's tool schemas. If it does not, pick a different model before you waste an hour debugging the agent. qwen3 and llama3.1 families reliably expose tool capabilities in their Ollama builds; tiny or base (non-instruct) models usually do not. This single check prevents the most common failure mode later.

Test the model once from the terminal so you know the server itself is healthy:

```bash
curl http://localhost:11434/api/tags
```

A JSON list of your models means Ollama is listening. If this fails, the problem is Ollama, not n8n, so fix it here before touching the canvas.

### Step 2: Make Ollama reachable from your n8n instance

Where n8n runs decides which Base URL you will use in Step 3.

**n8n and Ollama on the same machine.** Use the default `http://localhost:11434`. Nothing else to configure.

**n8n in Docker, Ollama on the host.** Containers cannot see the host's localhost. Point n8n at `http://host.docker.internal:11434` (Docker Desktop) or the host's LAN IP. Then make Ollama listen on more than loopback, otherwise the connection is refused at the network layer:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

You can persist this with a systemd override or an environment file depending on how you installed Ollama. Our [n8n-docker-compose-setup](/n8n-docker-compose-setup/) guide covers the Docker networking side in depth.

**n8n on a VPS, Ollama at home.** Expose Ollama through a reverse proxy with authentication, or run both on the same VPS. Never expose unauthenticated Ollama to the public internet; anyone who finds port 11434 can run models on your hardware.

### Step 3: Connect the Ollama Chat Model to the AI Agent node

In n8n, create a new workflow and add an **AI Agent** node. Under the node, in the Chat Model sub-node slot, choose **Ollama Chat Model**. The first time, n8n asks for an Ollama credential. The credential dialog asks for exactly one required field, **Base URL**, defaulting to `http://localhost:11434`, which matches the default we verified in the n8n 2.41.3 credential source. There is no API key field because Ollama needs none.

Back on the sub-node, set **Model** to `qwen3:8b` (type it exactly as `ollama list` spells it, tags included). Keep the defaults for everything else for now. If you followed our [n8n-ai-agent-tutorial](/n8n-ai-agent-tutorial/), this wiring is identical except the model vendor changed from OpenAI to Ollama.

### Step 4: Give the agent tools and memory

An agent with no tools is just a chatbot, and the whole point of this tutorial is tool calling. Add at least one real tool so you can observe the behavior:

1. Add the **Calculator** tool sub-node for deterministic arithmetic.
2. Add the **Wikipedia** tool sub-node for a retrieval-style call.
3. Add **Window Buffer Memory** so multi-turn tests keep context. The default context window length of 5 is fine for testing.

Wire a **Chat Trigger** (or the manual chat) into the AI Agent node. Your canvas should now read: Chat Trigger to AI Agent, with Ollama Chat Model, Calculator, Wikipedia, and Window Buffer Memory attached underneath.

### Step 5: Fix the skipped tool call problem

Ask the agent something that obviously needs a tool, for example: "What is 148 divided by 6, and show your working?" Watch the execution log.

With a small local model you will often see the failure the n8n changelog describes: the model answers "24.67" in prose and never touches the Calculator. The run looks successful, which is what makes this bug nasty. It fails silently.

The root cause is mechanical. The AI Agent node never sent a `tool_choice` hint, so OpenAI-compatible providers treat tool use as optional, and small models take the easy path and answer directly. n8n 2.40 fixed this with the opt-in setting. Open the AI Agent node, go to **Options**, and enable **Force Tool Call on First Iteration**. The setting's own description, taken from the n8n source, says the model "must call at least one tool on its first response of each run" while "later responses are unrestricted so the agent can answer."

Re-run the same question. This time the first model response is a Calculator call, the tool result returns, and the final answer is grounded in it. Two caveats from the vendor text deserve emphasis. First, the option is off by default, so existing workflows are unaffected until you opt in. Second, "the model must support forced tool choice," which is exactly why Step 1 verified the Capabilities line. If your model lacks tool support, this toggle cannot conjure it.

### Step 6: Add a fallback model for reliability

Local models crash, run out of memory, or get OOM-killed at the worst moment. n8n 2.40 also added a fallback path for AI nodes: in the AI Agent node's Options, enable **Enable Fallback Model**. The canvas then accepts an additional chat model sub-node, and n8n's own notice text explains the contract: "Connect an additional language model on the canvas to use it as a fallback if the main model fails."

Practical setups that work well:

- Primary `qwen3:8b`, fallback `llama3.1:8b` on the same Ollama server, which covers model-level crashes.
- Primary Ollama model, fallback a cloud model like OpenAI, which covers whole-server outages at the cost of a few paid tokens only when things break.

Do not set the fallback to a model without tool support. A fallback that cannot call tools turns a loud failure into a silent wrong answer, which is worse. If you run workers at scale, our [n8n-queue-mode-scaling](/n8n-queue-mode-scaling/) guide covers keeping model-backed executions reliable.

### Step 7: Test the full loop end to end

Send three test prompts through the chat and check the execution log each time:

1. "What is 15 percent of 240?" should produce a Calculator call.
2. "Summarize the Wikipedia article on quantization (machine learning)." should produce a Wikipedia call.
3. A follow-up like "and what did we just calculate?" should show the memory working, referencing the first answer.

If all three behave, your local agent is done. If you want retrieval over your own documents next, our [n8n-langchain-rag-tutorial](/n8n-langchain-rag-tutorial/) builds a RAG pipeline on the same agent pattern, and [n8n-agents-tutorial](/n8n-agents-tutorial/) covers the newer standalone Agents product for comparison.

## Troubleshooting

Five failure modes below, each with a cause and a fix. For n8n's general error-handling patterns beyond the agent, see our [n8n-error-handling](/n8n-error-handling/) tutorial.

**"Error: connect ECONNREFUSED" or "Failed to fetch" from the Ollama sub-node.**
n8n cannot reach the Ollama HTTP server. Confirm `curl http://localhost:11434/api/tags` works from the machine Ollama runs on, then fix the Base URL for your topology: `host.docker.internal` inside Docker Desktop, the host LAN IP for Docker on Linux, and `OLLAMA_HOST=0.0.0.0` on the Ollama side if the bind is loopback-only. This error is always networking, never the model.

**The agent answers in prose and never calls tools.**
This is the signature small-model behavior. First, re-run `ollama show <model>` and confirm the Capabilities line includes tools. Second, enable **Force Tool Call on First Iteration** in the AI Agent options as shown in Step 5. Third, if it still refuses, switch to qwen3:8b or llama3.1:8b; some experimental builds advertise tools but implement them poorly.

**"model 'qwen3:8b' not found, try pulling it first."**
The tag in the n8n sub-node does not match anything Ollama has. Run `ollama list` and copy the NAME column exactly, tag included. Model names are case-sensitive and tag-sensitive: `qwen3:8b` and `qwen3` can be different downloads.

**The first response takes minutes, or Ollama gets OOM-killed.**
The model does not fit comfortably in available memory. Check `ollama ps` while it runs to see what is loaded. Prefer a smaller quantization, close other GPU workloads, or set `OLLAMA_KEEP_ALIVE` so the model stays warm between runs instead of reloading every time. For long agent conversations, raising `num_ctx` helps context but costs memory roughly linearly, so raise it only as far as your hardware allows.

**The forced tool call picks a useless tool.**
Forcing means the model must call at least one tool, not that it picks wisely. If your agent has five tools and the task needs none of them, the first iteration still burns a call. Keep the toolset tight and relevant to the agent's job, and write the system prompt so each tool's purpose is unambiguous.

## FAQ

### Which Ollama models work best with the n8n AI Agent?
Use a model whose Capabilities line in `ollama show` includes tools. qwen3:8b and llama3.1:8b are the most reliable small choices in 2026. Larger models follow tool schemas more accurately, but they need more VRAM. Avoid tiny or non-instruct models, they frequently ignore the tool definitions entirely.

### Do I need an API key to use Ollama in n8n?
No. The n8n Ollama credential only asks for a Base URL, which defaults to http://localhost:11434. There is no API key because Ollama runs on your own machine. You only pay with your own hardware, not per token.

### Can I use Ollama with n8n Cloud?
Not directly. n8n Cloud cannot reach http://localhost:11434 on your laptop. You would need to expose Ollama through a public URL or tunnel, which defeats the privacy benefit. Ollama pairs naturally with self-hosted n8n, see our [install-n8n-ubuntu-vps](/install-n8n-ubuntu-vps/) guide.

### What does Force Tool Call on First Iteration actually do?
It binds the model with tool_choice set to required on the first response of each run, so the model must call at least one tool before answering. Later iterations stay unrestricted. It was added in n8n 2.40 for the AI Agent node v3 and Agent Tool v3, and it is off by default.

### How much RAM do I need to run Ollama for n8n agents?
An 8B quantized model like qwen3:8b needs roughly 6 to 8 GB of free RAM or VRAM. 70B models need 40 GB or more. If the model loads slowly or the machine swaps, pick a smaller quantization or a smaller model rather than fighting the hardware.

### Will the agent still work if Ollama crashes mid-run?
Yes, if you enable the AI Agent's Enable Fallback Model option and wire a second chat model on the canvas. n8n switches to the fallback when the primary model fails, instead of failing the whole execution.

## Conclusion

You now have an n8n AI Agent running on a local Ollama model: private, free per token, and, thanks to the 2.40 force-tool-call option, actually reliable at calling tools. The two settings that do the heavy lifting are Force Tool Call on First Iteration for small-model compliance and Enable Fallback Model for crash resilience. If you want the agent to remember more or read your documents, continue with our [n8n-chatbot-memory-tutorial](/n8n-chatbot-memory-tutorial/) and then the RAG tutorial linked above.
