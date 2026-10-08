---
title: "n8n LangChain RAG Tutorial: Build a Chatbot That Answers from Your Documents (2026)"
slug: "n8n-langchain-rag-tutorial"
date: 2026-10-02T00:20:55+08:00
draft: false
description: "Build a real RAG chatbot in n8n: chunk documents, store embeddings in Qdrant, and answer questions with the Question and Answer Chain. Tested on n8n 2.41.4."
categories: ["n8n", "ai-automation"]
tags: ["n8n", "rag", "langchain", "qdrant", "vector-database", "openai", "embeddings", "chatbot", "retrieval-augmented-generation", "ai-agent"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Do I need to write LangChain code to build RAG in n8n?"
    a: "No. n8n ships LangChain-based nodes that wrap the code for you: the Default Data Loader, Recursive Character Text Splitter, Embeddings OpenAI, Qdrant Vector Store, and Question and Answer Chain nodes are all configured in the visual editor. Every node label and parameter in this tutorial was verified against n8n 2.41.4. You only need API keys and a vector database, not a Python environment."
  - q: "Which vector store should I use for RAG in n8n?"
    a: "Start with the Simple Vector Store for a 10-minute prototype, since it needs no setup. Move to Qdrant or the Postgres PGVector Store for anything real, because the Simple Vector Store warns that data is stored in memory and is lost when n8n restarts. Qdrant runs in one Docker command and is the most popular self-hosted option in n8n templates."
  - q: "Which embedding model should I pick?"
    a: "OpenAI's text-embedding-3-small is the default in the Embeddings OpenAI node and is fine for most document collections. OpenAI bills embeddings per token, so the Batch Size parameter on the node matters when you ingest thousands of pages. If you change models later, remember that Qdrant collections have a fixed vector size, so switching models means recreating the collection and re-ingesting."
  - q: "Can the Question and Answer Chain show its sources?"
    a: "Yes. The chain is built on LangChain's retrieval chain, whose prompt template combines the retrieved context with your question, and the node output includes the retrieved context alongside the answer. That means you can inspect exactly which document chunks grounded each answer, which is the fastest way to debug bad answers."
  - q: "Can I build RAG in n8n without OpenAI?"
    a: "Yes. Swap the Embeddings OpenAI node for Embeddings Ollama and the OpenAI Chat Model for an Ollama chat model, both of which ship with n8n. The rest of the workflow, Qdrant included, stays identical. Local models are slower per token on consumer hardware but remove API costs and keep documents on your own machine."
  - q: "How is this different from giving documents to an AI Agent node?"
    a: "The Question and Answer Chain is purpose-built for RAG: retrieve, then answer in one pass. The AI Agent node is more flexible and can call a vector store as a tool among many tools, which suits multi-step work. If your only job is answering questions from documents, the chain is simpler and more predictable. Our n8n AI Agent tutorial covers the agent route."
---

## Introduction

A chatbot that answers from your own documents beats a generic chatbot for one reason: it stops hallucinating about your content. This tutorial builds a complete retrieval-augmented generation (RAG) pipeline in n8n, from raw documents to a working chat interface. You will run Qdrant in Docker, ingest documents with n8n's LangChain nodes, and serve answers through a Chat Trigger. It is written for n8n users who are comfortable building basic workflows and want their first real AI feature, and every node name below was verified in a lab install of n8n 2.41.4.

## Quick answer

Feed a Qdrant Vector Store node (Insert Documents) with a Default Data Loader, a Recursive Character Text Splitter, and Embeddings OpenAI, then attach a Qdrant retriever to a Question and Answer Chain behind a Chat Trigger.

## Why RAG, and why in n8n

n8n's own documentation puts it plainly: *"Retrieval-Augmented Generation (RAG) is a technique that improves AI responses by combining language models with external data sources."* Instead of relying on a model's training data, the system retrieves relevant document chunks and grounds each answer in them. That single mechanism solves the two problems that kill document chatbots: stale knowledge and invented facts.

Three facts, current as of October 2026:

- **n8n is the biggest workflow automation project on GitHub by a wide margin.** A live query of the GitHub API puts n8n-io/n8n at **206,436 stars**, and the project describes itself as a "Fair-code workflow automation platform with native AI capabilities" with **400+ integrations**. Its LangChain node package ships dedicated RAG building blocks, so you are not hacking a generic HTTP node into an embedding pipeline.
- **Qdrant is the most adopted self-hosted vector database in this stack.** The Qdrant repository holds **34,895 GitHub stars** (GitHub API, October 2026), and the project calls itself "an Open-Source Vector Search Engine written in Rust" that provides "fast and scalable vector similarity search service with convenient API." It runs in a single Docker command, which is why n8n's RAG templates keep choosing it.
- **Every label in this guide was verified, not remembered.** Node display names, operation names, and parameter defaults were read from the compiled `@n8n/n8n-nodes-langchain` package of n8n **2.41.4** running in our lab. The Qdrant node really does offer exactly four operations, the text splitter really does default to Chunk Size 1000, and the in-memory store really does warn that its data vanishes on restart.

The LangChain project maintains the canonical explanation of the RAG pattern in its [RAG tutorial](https://python.langchain.com/docs/tutorials/rag/), and n8n's guide to [retrieving relevant context](https://docs.n8n.io/build/integrate-ai/understand-ai-components/retrieve-relevant-context/) maps that pattern onto n8n nodes. This tutorial is the hands-on version of that mapping.

## Prerequisites

- A working n8n instance, self-hosted or cloud, version 2.x. The steps were tested on 2.41.4. If you have not installed n8n yet, our [guide to installing n8n on an Ubuntu VPS](/install-n8n-ubuntu-vps/) or the [Docker Compose setup walkthrough](/n8n-docker-compose-setup/) gets you there.
- Docker installed, for running Qdrant.
- An OpenAI API key with billing enabled, saved as an n8n OpenAI credential.
- A few sample documents. A product FAQ, an internal wiki page, or a support knowledge base works well. Plain text or Markdown is easiest.
- Basic comfort with the n8n editor: adding nodes, connecting them, and executing a workflow.

## Step 1, Run Qdrant with Docker

Qdrant needs no configuration to start. The [Qdrant quickstart](https://qdrant.tech/documentation/quickstart/) documents this single command:

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

Port 6333 serves the REST API that n8n talks to, and port 6334 serves gRPC. Open `http://localhost:6333/dashboard` in your browser. If you see the Qdrant dashboard, the database is ready. The `-v` flag persists your vectors on disk, so your documents survive container restarts. If you already run n8n with Docker Compose, add Qdrant as a service instead so both containers share a network:

```yaml
qdrant:
  image: qdrant/qdrant
  ports:
    - "6333:6333"
  volumes:
    - qdrant_storage:/qdrant/storage
```

## Step 2, Build the ingestion workflow

Ingestion turns documents into searchable vectors. Create a new workflow and add the nodes in this order. The data connection flows left to right; the AI sub-node connections (document, text splitter, embedding) attach underneath the Qdrant Vector Store node.

First, add a **Qdrant Vector Store** node. Set **Operation** to **Insert Documents**, which is one of the four operations the node documents: Get Many, Insert Documents, Retrieve Documents (As Vector Store for Chain/Tool), and Retrieve Documents (As Tool for AI Agent), per the [Qdrant Vector Store node documentation](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoreqdrant/). Set **Collection** to `support_docs`. n8n creates the collection automatically on first insert. In **Qdrant URL**, enter the address n8n can reach: `http://localhost:6333` if n8n runs on the same host outside Docker, or `http://qdrant:6333` if both run in the same Compose network.

Second, attach a **Default Data Loader** to the Qdrant node's document input. The loader's job is simple: it loads JSON data or binary files from a previous step for the vector store. Add a **Set** node before the loader and put your documents in it as a `text` field, one item per document. In the loader, **Type of Data** defaults to JSON, which is correct for Set node output. If your documents are PDFs or Word files, use a Read Binary File node and switch Type of Data to Binary instead.

Third, attach a **Recursive Character Text Splitter** to the Qdrant node's text splitter input. Chunking matters because embedding models have context limits and retrieval works better on focused passages. The node defaults to **Chunk Size** 1000 and **Chunk Overlap** 0, which are the values shipped in n8n 2.41.4. Raise Chunk Overlap to 200 so sentences split across a chunk boundary still appear whole in at least one chunk.

Fourth, attach an **Embeddings OpenAI** node to the Qdrant node's embedding input. Create an OpenAI credential with your API key. **Model** defaults to `text-embedding-3-small`, which is the right starting point: cheap, fast, and good enough for document search. OpenAI's [embeddings guide](https://platform.openai.com/docs/guides/embeddings) documents the available models and their trade-offs. Keep the default **Batch Size** unless you hit rate limits, which the troubleshooting section covers.

Execute the workflow. The Qdrant node inserts one vector per chunk, and the Qdrant dashboard's Collections view shows `support_docs` with a point count matching your chunks. If the count is zero, the loader received no items, which almost always means the Set node output field name does not match what the loader reads.

## Step 3, Build the question-answering workflow

Create a second workflow for queries. Add a **Chat Trigger** node. This gives you a hosted chat page and, once the workflow is active, a production webhook URL you can embed anywhere.

Add a **Question and Answer Chain** node and connect the Chat Trigger to it. The chain has two AI sub-node inputs. Attach an **OpenAI Chat Model** node to the model input, select a model such as `gpt-4o-mini`, and reuse your OpenAI credential. Then attach a second **Qdrant Vector Store** node to the retriever input, this time with **Operation** set to **Retrieve Documents (As Vector Store for Chain/Tool)**, the same **Collection** `support_docs`, and the same Qdrant URL. This operation is designed exactly for this wiring: it hands the chain a retriever instead of running standalone.

Open the Chat Trigger's chat URL and ask a question your documents answer, for example "What is the refund policy?" The chain retrieves the most similar chunks, stuffs them into the prompt as context, and the model answers from that context. Check the chain node's output: it returns the answer together with the retrieved context, so you can confirm the answer came from your documents and not from the model's imagination.

## Step 4, Test with adversarial questions

A RAG demo that only answers easy questions proves nothing. Run three tests:

1. Ask something your documents answer, and verify the retrieved context contains the relevant chunk.
2. Ask something your documents do not cover. A good RAG setup says it does not know, or hedges, because the retrieved chunks are irrelevant. If it answers confidently anyway, your retrieval is too permissive or your prompt needs a "say you don't know" instruction.
3. Ask a question with terms that appear in many chunks. If answers degrade, your chunks are too large or your overlap too small, and Step 2's splitter settings are the fix.

When the pipeline behaves, activate both workflows. The Chat Trigger's production URL becomes your embeddable support chatbot.

## Troubleshooting

**n8n cannot reach Qdrant: `fetch failed` or `ECONNREFUSED`.**
This is the number-one setup failure, and it is a networking mistake, not a Qdrant mistake. `http://localhost:6333` inside the n8n Docker container points at the container itself, not your host. If n8n runs in Docker, put Qdrant in the same Compose network and set Qdrant URL to `http://qdrant:6333`. If n8n runs on the host and Qdrant in Docker, `http://localhost:6333` is correct. Test from inside the n8n container with `docker exec <n8n-container> wget -qO- http://qdrant:6333/` to prove the route before touching n8n settings.

**Inserts fail after switching embedding models: vector size mismatch.**
Qdrant collections store a fixed vector size, and each embedding model produces a fixed dimension count. If you ingest with one model and query with another, Qdrant rejects the inserts. The fix is to delete the collection in the Qdrant dashboard and re-run the ingestion workflow so the collection is recreated with the new model's dimensions. Pick one embedding model per collection and stick with it.

**OpenAI 429 rate limits during bulk ingestion.**
Embedding thousands of chunks fires many API calls in a burst, and OpenAI throttles new keys aggressively. Two fixes, both in the editor: enable **Retry on Fail** in the Embeddings OpenAI node's Settings tab so transient 429s retry automatically, and lower the node's **Batch Size** parameter to shrink each request burst. For very large corpora, split ingestion across scheduled runs instead of one giant execution.

**Chat Trigger test chat works, but the production URL does nothing.**
The Test chat URL only listens while you have the workflow open with the trigger in listening mode. Activating the workflow switches the Chat Trigger to its production URL. This trips up everyone once: test in the editor, then activate, then use the production URL in your site or app.

**Vectors vanish after an n8n restart.**
You used the **Simple Vector Store** node, whose own interface warns: data is stored in memory, is lost if n8n restarts, and may be cleared if memory gets low. It is a prototyping node. Move to the Qdrant setup in this tutorial, or to the **Postgres PGVector Store** node if you already run Postgres, for anything that must survive a restart. Our [vector store tutorial](/n8n-vector-store-tutorial/) compares the options in depth.

## FAQ

**Do I need to write LangChain code to build RAG in n8n?**
No. n8n ships LangChain-based nodes that wrap the code for you: the Default Data Loader, Recursive Character Text Splitter, Embeddings OpenAI, Qdrant Vector Store, and Question and Answer Chain nodes are all configured in the visual editor. Every node label and parameter in this tutorial was verified against n8n 2.41.4. You only need API keys and a vector database, not a Python environment.

**Which vector store should I use for RAG in n8n?**
Start with the Simple Vector Store for a 10-minute prototype, since it needs no setup. Move to Qdrant or the Postgres PGVector Store for anything real, because the Simple Vector Store warns that data is stored in memory and is lost when n8n restarts. Qdrant runs in one Docker command and is the most popular self-hosted option in n8n templates.

**Which embedding model should I pick?**
OpenAI's text-embedding-3-small is the default in the Embeddings OpenAI node and is fine for most document collections. OpenAI bills embeddings per token, so the Batch Size parameter on the node matters when you ingest thousands of pages. If you change models later, remember that Qdrant collections have a fixed vector size, so switching models means recreating the collection and re-ingesting.

**Can the Question and Answer Chain show its sources?**
Yes. The chain is built on LangChain's retrieval chain, whose prompt template combines the retrieved context with your question, and the node output includes the retrieved context alongside the answer. That means you can inspect exactly which document chunks grounded each answer, which is the fastest way to debug bad answers.

**Can I build RAG in n8n without OpenAI?**
Yes. Swap the Embeddings OpenAI node for Embeddings Ollama and the OpenAI Chat Model for an Ollama chat model, both of which ship with n8n. The rest of the workflow, Qdrant included, stays identical. Local models are slower per token on consumer hardware but remove API costs and keep documents on your own machine.

**How is this different from giving documents to an AI Agent node?**
The Question and Answer Chain is purpose-built for RAG: retrieve, then answer in one pass. The AI Agent node is more flexible and can call a vector store as a tool among many tools, which suits multi-step work. If your only job is answering questions from documents, the chain is simpler and more predictable. Our [n8n AI Agent tutorial](/n8n-ai-agent-tutorial/) covers the agent route.

## Conclusion

You now have a working RAG pipeline: documents chunked and embedded into Qdrant, and a chat interface that answers from them through the Question and Answer Chain. The architecture scales further than this tutorial: add a [Code node](/n8n-code-node-javascript/) to preprocess documents, schedule re-ingestion when your knowledge base changes, or promote the chain into an [AI Agent](/n8n-ai-agent-tutorial/) that combines document retrieval with live tools. Keep n8n current with our [update runbook](/how-to-update-n8n-self-hosted/) so your LangChain nodes keep pace with upstream fixes.
