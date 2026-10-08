---
title: "n8n Chatbot with Memory Tutorial: Build a Bot That Remembers Conversations"
slug: "n8n-chatbot-memory-tutorial"
date: 2026-10-02T12:20:55+08:00
draft: false
description: "Build an n8n chatbot with memory: attach the Simple Memory sub-node to an AI Agent, scope sessions per user, and move to Postgres Chat Memory for production."
categories: ["n8n"]
tags: ["n8n", "chatbot", "ai-agent", "memory", "openai", "workflow-automation", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Does the Simple Memory node store chat history in a database?"
    a: "No. Simple Memory keeps history inside the running n8n process, which is why the node says no credentials are required. Restart n8n and the history is gone. For persistence across restarts, switch to Postgres Chat Memory, Redis Chat Memory, or MongoDB Chat Memory."
  - q: "How many messages does the chatbot remember by default?"
    a: "Five past interactions. The Simple Memory node's Context Window Length defaults to 5 in n8n 2.41.4, and each interaction is a user message plus the model's reply, so roughly ten message turns are fed back to the model. Raise the number for longer context, at higher token cost per call."
  - q: "Can each user get a separate conversation with their own memory?"
    a: "Yes. Keep Session ID set to Connected Chat Trigger Node, the default, and n8n scopes each chat session separately. Sessions are also scoped to the memory node itself, so two memory nodes in one workflow do not share history unless you set both to Define below with the same key."
  - q: "Does chatbot memory work with models other than OpenAI?"
    a: "Yes. Any chat model sub-node works with the memory sub-node, including Anthropic Chat Model, Google Gemini Chat Model, Groq Chat Model, and the local Ollama Chat Model. Memory sits between the agent and the model, so it is model-agnostic."
  - q: "Is chatbot memory the same thing as RAG?"
    a: "No. Memory stores the conversation itself: what was said earlier in this chat. RAG retrieves external documents from a vector store and injects them as context. Combine both, as shown in our n8n vector store tutorial, when a bot needs long-term knowledge and short-term conversation memory."
  - q: "Do I need memory if my chatbot answers one question per session?"
    a: "No. A stateless question-answering bot needs no memory node at all, and skipping it saves tokens on every call. Add memory only when follow-up messages must reference earlier turns, which is exactly the support-bot and assistant use case this tutorial targets."
---

## Introduction

A chatbot without memory answers every message as if it were the first. Users repeat themselves, the bot contradicts itself, and the experience feels broken. This tutorial fixes that in n8n: you will wire a **Chat Trigger** to an **AI Agent** node, attach the **Simple Memory** sub-node, and end up with a chatbot that remembers names, preferences, and context across messages. Every node name, parameter default, and option below was verified against n8n 2.41.4's own node definitions on a lab install, so what you read is what you will see in the editor.

## Quick answer

Add a Chat Trigger, an AI Agent with a chat model, and attach the Simple Memory sub-node to keep the last five exchanges. Set Session ID to Connected Chat Trigger Node so each user gets their own conversation memory.

## Why memory changes everything: the numbers

Conversation memory is not a niche feature. n8n passed **206,477 stars on GitHub** as of October 2, 2026, measured directly from the GitHub API, which makes it one of the most-starred workflow automation projects in the world, and chatbots with memory are among its most-built AI workflows. The AI layer underneath, the LangChain family of libraries that n8n's agent nodes build on, holds **147,373 GitHub stars** as of the same date, so the memory primitives you use here are battle-tested far beyond n8n.

The defaults are small on purpose. Simple Memory ships with a **Context Window Length of 5**, verified in n8n 2.41.4's node source, and each interaction is a user message plus the model's reply. Five interactions means roughly ten message turns flow back into the model on every call, which is enough for a natural support conversation without drowning the model in tokens.

Two vendor statements anchor this tutorial. n8n's [Simple Memory documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.memorybufferwindow) warns: "Don't use this node if running n8n in queue mode. This is because n8n can't guarantee that every call to Simple Memory will go to the same worker." That single sentence decides your whole production architecture, and Step 6 below is built around it. The same documentation set defines the other half of the build: the [AI Agent node documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent) says, "The AI Agent node lets you build an AI agent in n8n. Connect a chat model and one or more tools, and the agent decides which tools to call to complete a task." Memory is what turns that agent from a question answerer into a conversationalist. For background on how the underlying memory classes work, [LangChain's documentation](https://docs.langchain.com/oss/python/langchain/overview) covers the same concepts, buffer window memory included, in framework-neutral terms.

## Prerequisites

- n8n 1.82 or newer, self-hosted or cloud. This tutorial was verified on **n8n 2.41.4**. If you have not installed n8n yet, see our guide to [deploying n8n on a VPS with Docker Compose](https://www.161808.xyz/n8n-docker-compose-setup/).
- An OpenAI API key (or any other chat model credential, the steps are identical).
- About 30 minutes and a basic grasp of the n8n editor: adding nodes, connecting them, running a test execution.

## Step 1: Add a Chat Trigger in Hosted Chat mode

Create a new workflow and add the **Chat Trigger** node as the first step. Open its settings and look at the **Mode** option, which I verified in the 2.41.4 node source: it offers **Hosted Chat** ("Chat on a page served by n8n") and **Embedded Chat** (webhook). Choose **Hosted Chat** for this tutorial. n8n serves a chat page for you, no frontend code needed, and each visitor gets their own session automatically. That automatic per-visitor session is exactly what the memory node will key on later.

## Step 2: Add the AI Agent node and connect a chat model

Add the **AI Agent** node after the Chat Trigger and connect them. Open the AI Agent node and click the plus under its model connector to attach a chat model: choose **OpenAI Chat Model**, create the credential with your API key, and pick a model such as `gpt-4o-mini`. If you built our [n8n AI agent tutorial](https://www.161808.xyz/n8n-ai-agent-tutorial/), this screen will look familiar: the agent is the same, the difference is what you attach to it next.

## Step 3: Attach the Simple Memory sub-node

This is the step that matters. With the AI Agent node selected, click the plus on its **memory** connector (the small sub-node socket beneath the agent) and add **Simple Memory**. In n8n 2.41.4 the node formerly called Window Buffer Memory is displayed as Simple Memory, and its description reads "Stores in n8n memory, so no credentials required": it needs no database and no credential, history lives inside the running n8n process.

Two parameters decide whether memory actually works for real users:

- **Session ID** defaults to **Connected Chat Trigger Node**, which "looks for an input field called 'sessionId' that is coming from a directly connected Chat Trigger", per the node source. Leave it on the default. Every hosted-chat visitor gets a separate conversation. The node source also documents that a session "is automatically scoped only to this memory node", so two memory nodes in one workflow will not leak history into each other.
- **Context Window Length** defaults to **5**, with the hint "How many past interactions the model receives as context". Leave it at 5 for now; Step 5 shows how to feel the difference when you change it.

## Step 4: Give the agent a memory-aware system prompt

Open the AI Agent node, add the **System Message** option, and write something like: "You are a helpful support assistant. The conversation history is provided as context; use it to answer follow-up questions without asking the user to repeat themselves. If the user corrects a fact, remember the correction." This is not decoration. Without an instruction, models sometimes ignore older turns even when they are in context. One sentence telling the model that history exists and should be used measurably improves follow-up answers.

## Step 5: Test with a two-turn memory check

Save, then click **Test workflow** (or open the hosted chat URL). This is the test I run every time:

1. Type: "My name is Wei and I run a bakery in Austin."
2. Type: "What is my name and what business do I run?"

A correctly wired bot answers "Wei" and "a bakery in Austin". Then open the chat in a second browser, or a private window, and ask the same question: the bot should not know the name, proving session isolation works. Finally, go back to the first chat and say "Actually my bakery is in Denver now", then ask "Where is my bakery?": the bot should say Denver, proving corrections overwrite earlier memory within the window.

If any of these fail, do not add more nodes yet. Read the Troubleshooting section first; in my experience nine out of ten memory failures are session-ID or attachment mistakes, not model problems.

## Step 6: Upgrade to persistent memory for production

Simple Memory is a development node, and the vendor says so explicitly. Remember the warning from n8n's Simple Memory documentation: do not use it in queue mode, because calls may land on different workers, and its history dies with the n8n process on restart. For anything real, replace the Simple Memory sub-node with **Postgres Chat Memory** (or **Redis Chat Memory**, both ship in the same n8n package, verified in the lab install):

1. Delete the Simple Memory sub-node from the AI Agent's memory connector.
2. Add **Postgres Chat Memory** in its place and create a Postgres credential pointing at your database.
3. Keep Session ID on Connected Chat Trigger Node. The session key logic is identical; only the storage backend changes.

History now survives restarts and works behind any number of workers. The trade: you run a database, and you should add a retention policy later so the memory table does not grow forever.

## Troubleshooting

**The bot forgets everything after an n8n restart.**
Simple Memory stores history in the n8n process memory, not in any database, which is also why it needs no credential. Every restart wipes it. If persistence matters, move to Postgres Chat Memory as in Step 6. For demos and tests, the forgetting is expected behavior, not a bug.

**Memory stops working after switching n8n to queue mode.**
This is the documented limitation quoted in the Evidence section: in queue mode n8n cannot guarantee that every call to Simple Memory reaches the same worker, and workers do not share process memory. The fix is the same as above: Redis Chat Memory or Postgres Chat Memory, both of which are external stores every worker can reach.

**Two different users see each other's conversation.**
Your Session ID is not actually per-user. The usual cause: you changed Session ID to **Define below** and entered a static key, which makes every chat share one memory. Switch it back to **Connected Chat Trigger Node**, or if you must define it manually, use an expression that is unique per user, such as `={{ $json.sessionId }}` (the default expression the node suggests for a custom key). Verify with the two-browser test from Step 5.

**The agent answers but never references earlier messages.**
The memory sub-node is not attached. It is easy to add Simple Memory as a regular step in the workflow instead of dragging it onto the AI Agent's memory connector. Check that the memory node appears as a small attached icon under the agent, not as a box between other nodes. If it is attached and still ignored, confirm your chat model call actually receives the history: open a test execution, expand the AI Agent node, and look for the memory contents in its input.

**Token costs climb as conversations get longer.**
Each message resends the whole context window to the model. Raising Context Window Length from 5 to 20 roughly quadruples the history tokens per call. Keep the default 5 for support bots, and for long sessions consider the **Chat Memory Manager** node, which can summarize or trim history instead of replaying it raw. Watch the per-execution token counts in your model provider's dashboard for a week before tuning.

## FAQ

**Does the Simple Memory node store chat history in a database?**

No. Simple Memory keeps history inside the running n8n process, which is why the node says no credentials are required. Restart n8n and the history is gone. For persistence across restarts, switch to Postgres Chat Memory, Redis Chat Memory, or MongoDB Chat Memory.

**How many messages does the chatbot remember by default?**

Five past interactions. The Simple Memory node's Context Window Length defaults to 5 in n8n 2.41.4, and each interaction is a user message plus the model's reply, so roughly ten message turns are fed back to the model. Raise the number for longer context, at higher token cost per call.

**Can each user get a separate conversation with their own memory?**

Yes. Keep Session ID set to Connected Chat Trigger Node, the default, and n8n scopes each chat session separately. Sessions are also scoped to the memory node itself, so two memory nodes in one workflow do not share history unless you set both to Define below with the same key.

**Does chatbot memory work with models other than OpenAI?**

Yes. Any chat model sub-node works with the memory sub-node, including Anthropic Chat Model, Google Gemini Chat Model, Groq Chat Model, and the local Ollama Chat Model. Memory sits between the agent and the model, so it is model-agnostic.

**Is chatbot memory the same thing as RAG?**

No. Memory stores the conversation itself: what was said earlier in this chat. RAG retrieves external documents from a vector store and injects them as context. Combine both, as shown in our n8n vector store tutorial, when a bot needs long-term knowledge and short-term conversation memory.

**Do I need memory if my chatbot answers one question per session?**

No. A stateless question-answering bot needs no memory node at all, and skipping it saves tokens on every call. Add memory only when follow-up messages must reference earlier turns, which is exactly the support-bot and assistant use case this tutorial targets.

## Conclusion

You now have a chatbot that remembers: a Chat Trigger for the conversation, an AI Agent for the reasoning, and a Simple Memory sub-node keeping the last five exchanges, with sessions scoped per user and a clear upgrade path to Postgres Chat Memory for production. The whole build took six steps and no code.

The natural next step is giving the bot knowledge it cannot fit in conversation memory. Our [n8n vector store tutorial](https://www.161808.xyz/n8n-vector-store-tutorial/) shows how to connect Pinecone or Qdrant so the same agent answers from your documents, and our [n8n error handling guide](https://www.161808.xyz/n8n-error-handling/) shows how to keep the workflow alive when a model call fails.
