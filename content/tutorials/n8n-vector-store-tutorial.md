---
title: "n8n Vector Store Tutorial: Store and Retrieve Embeddings with Pinecone and Qdrant"
slug: "n8n-vector-store-tutorial"
date: 2026-09-29T09:45:00+08:00
draft: false
description: "Connect a vector database to n8n: insert documents into Pinecone or Qdrant with the Vector Store node, match embedding dimensions, and let an AI agent retrieve your own documents. Verified against n8n 2.40.7's node definitions and Pinecone's official n8n skill."
categories: ["n8n"]
tags: ["n8n", "vector-store", "pinecone", "qdrant", "rag", "embeddings", "ai-agent", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Which vector databases can n8n connect to?"
    a: "n8n 2.40.7 ships vector store nodes for Pinecone, Qdrant, Supabase, Weaviate, Milvus, Chroma, pgvector, Redis, Azure AI Search, MongoDB Atlas, Oracle, Zep, and an In-Memory store, 24 vector-store node packages in total. Pinecone and Qdrant are the most documented pair for RAG workflows."
  - q: "What are the operation modes of the n8n Vector Store node?"
    a: "Most vector store nodes offer Get Many, Insert Documents, Retrieve Documents (As Vector Store for Chain/Tool), and Retrieve Documents (As Tool for AI Agent). Pinecone and Supabase add an Update Documents mode. Insert mode feeds documents in; retrieve modes hand matched documents to a chain or an AI agent."
  - q: "Why does my n8n vector store insert fail with a dimension error?"
    a: "Your vector database index was created with a different dimension count than your embedding model produces. A Pinecone index built for 3072-dimensional vectors rejects 1536-dimensional vectors from text-embedding-3-small. Create the index with the exact dimension count of your embedding model before inserting."
  - q: "Do I need Pinecone to use vector search in n8n?"
    a: "No. Qdrant is a self-hosted, open-source alternative, and n8n also ships an In-Memory Simple Vector Store for zero-cost testing. Pinecone's managed Assistant node is the lowest-effort managed option since it handles chunking, embedding, and indexing automatically."
  - q: "How do I make an n8n AI agent use my vector store?"
    a: "Add a second instance of your Vector Store node in Retrieve Documents (As Tool for AI Agent) mode and connect it to the AI Agent's tools connector. Write a specific tool name and description, n8n's docs say the agent uses the vector store when the name and description match the question details."
  - q: "What chunk size should I use when loading documents into n8n?"
    a: "Pinecone's official guidance for n8n: 3000 characters with 500 overlap as the default for long documents, or 500–1000 characters with 100–200 overlap for Q&A-style retrieval over short, dense content."
---

## Introduction

A vector store is the memory layer of a RAG (retrieval-augmented generation) pipeline: you convert documents into embeddings, long lists of numbers that capture meaning, store them in a vector database, and at query time pull back only the chunks relevant to the question. This tutorial wires that whole loop into n8n: ingest documents into Pinecone or Qdrant with the Vector Store node, then let an n8n AI agent retrieve your own documents as a tool. Every node name, mode, and parameter below was verified against n8n 2.40.7's own node definitions, cross-checked with Pinecone's official n8n skill published by Pinecone's developer relations team.

## Quick answer

In n8n, add a **Pinecone Vector Store** (or **Qdrant Vector Store**) node in **Insert Documents** mode, attach an **Embeddings** sub-node, a **Default Data Loader**, and a **Recursive Character Text Splitter** to feed documents in, then add a second instance of the same node in **Retrieve Documents (As Tool for AI Agent)** mode, connected to an AI Agent's tools connector, so the agent can search your documents. The embedding model and vector dimensions must match in both phases.

## Why vector stores matter in n8n: the numbers

n8n 2.40.7 ships **24 vector-store node packages**, I counted them in the installed `@n8n/n8n-nodes-langchain` package in September 2026, covering Pinecone, Qdrant, Supabase, Weaviate, Milvus, Chroma, pgvector, Redis, Azure AI Search, MongoDB Atlas, Oracle Database, Zep, and an In-Memory store. Agents without retrieval hallucinate; agents with a vector store answer from your data.

The cost of getting embeddings is small enough that it rarely blocks anyone. OpenAI's `text-embedding-3-small`, the default embedding model Pinecone recommends for n8n, produces **1536-dimensional vectors at $0.02 per million tokens** as of September 2026. The larger `text-embedding-3-large` produces 3072-dimensional vectors at $0.13 per million tokens, and the legacy `text-embedding-ada-002` produces 1536-dimensional vectors at $0.10 per million. Embedding a 300-page manual once costs well under a dollar; the expensive part of a bad setup is a wrong dimension count, which fails loudly (see Troubleshooting).

Two vendor quotes anchor the whole tutorial.

> "Use Retrieve Documents (As Tool for AI Agent) mode to use the vector store as a tool resource when answering queries. When formulating responses, the agent uses the vector store when the vector store name and description match the question details.", [docs.n8n.io, Pinecone Vector Store](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstorepinecone?ref=blog.n8n.io)

Second, the hard rule from [Pinecone's official n8n skill](https://github.com/pinecone-io/skills/blob/HEAD/skills/pinecone-n8n/SKILL.md):

> "The SAME embedding model and dimensions MUST be used in both insert and retrieve-as-tool nodes, they share a single Embeddings OpenAI node."

That one sentence, ignored, is the root cause of most "my RAG returns garbage" threads. For the agent side of this architecture, see our [n8n AI Agent tutorial](/n8n-ai-agent-tutorial/).

## Which backend should you pick?

| Backend | Cost | Hosting | n8n node modes | Best for |
|---|---|---|---|---|
| Pinecone (serverless) | Free tier + usage | Managed | Get Many, Insert, Retrieve (chain/tool), Retrieve (agent tool), Update | Zero-ops start, managed scaling |
| Qdrant | Free (self-hosted) | Self-hosted or cloud | Get Many, Insert, Retrieve (chain/tool), Retrieve (agent tool) | Full control, no vendor lock-in |
| In-Memory (Simple Vector Store) | Free | Inside n8n | Get Many, Insert, Retrieve (chain/tool), Retrieve (agent tool) | Testing the workflow shape before paying |

The steps below use Pinecone first, then show the Qdrant self-hosted equivalent.

## Prerequisites

- n8n running (node definitions verified on **n8n 2.40.7**; the Vector Store nodes exist in n8n 1.x too, but the five-mode layout is current in 2.x).
- A **Pinecone account** with an API key ([Pinecone console](https://app.pinecone.io)) for the managed path, or **Qdrant** running locally (`docker run -p 6333:6333 qdrant/qdrant`) for the self-hosted path.
- An **OpenAI API key** for the Embeddings OpenAI sub-node (n8n also ships embedding sub-nodes for Azure OpenAI, Cohere, Google Gemini, Mistral, and Ollama if you prefer a local model).
- A few documents to index: PDFs or text files served over HTTPS work with the download pattern below.

## Step 1, Create the vector index (Pinecone)

Before n8n touches anything, create the index in the Pinecone console:

1. Go to the Pinecone console's index list and create an index named e.g. `n8n-docs`.
2. Set the **dimension to 1536**, the exact dimension count of `text-embedding-3-small`. Pinecone enforces this: an index created with any other dimension count rejects every vector your Embeddings node produces.
3. Note the index name exactly; you will pick it in the n8n node's `pineconeIndex` field.

Pinecone's skill is blunt about this ordering: create the index with the correct name and dimensions *before* running the workflow.

## Step 2, Build the ingestion workflow (Pinecone)

Pinecone's official skill prescribes a two-phase architecture: one ingestion workflow (run once or on a schedule) and one chat workflow. The ingestion phase looks like this:

```
Manual Trigger → Set file URLs → Split Out → HTTP Request (download)
  → Pinecone Vector Store (Insert Documents mode)
       ↑ Default Data Loader ← Recursive Character Text Splitter
       ↑ Embeddings OpenAI
```

Build it node by node:

1. **Manual Trigger**, so you can run ingestion on demand.
2. **Set**, assign a `urls` array field with the HTTPS URLs of the documents to index.
3. **Split Out**, split the `urls` field so each document flows through the pipeline as its own item.
4. **HTTP Request**, `GET ={{ $json.urls }}`, with the response set to return a **file**. This downloads each document as binary data.
5. **Pinecone Vector Store**, set **Operation Mode** to **Insert Documents**, pick your `n8n-docs` index, and create **Pinecone API** credentials with your API key.
6. Attach the **Embeddings OpenAI** sub-node to the vector store node: pick `text-embedding-3-small` and set **Dimensions** to 1536 so they match the index.
7. Attach a **Default Data Loader** sub-node: set **Data Type** to **Binary** and **Text Splitting Mode** to **Custom**.
8. Attach a **Recursive Character Text Splitter** to the data loader: **Chunk Size 3000**, **Chunk Overlap 500**, Pinecone's recommended default for long documents. For Q&A-style retrieval over short dense content, use 500–1000 chunk size with 100–200 overlap instead. The [Pinecone chunking guide](https://www.pinecone.io/learn/chunking-strategies/) explains why these numbers behave differently.

When you execute this workflow, each chunk is embedded and upserted into your Pinecone index. Run it once per document set; rerunning re-inserts the same chunks (see Troubleshooting #4).

### Importable ingestion skeleton

The JSON below follows Pinecone's official reference configuration (parameter values like `"mode": "insert"`, the `pineconeIndex` resource locator, and `topK` are taken from Pinecone's own skill). Import via **⋯ → Import from JSON**, add the Set/Split Out/HTTP Request nodes for your documents, then attach the sub-nodes visually in the editor:

```json
{
  "name": "Pinecone Document Ingestion",
  "nodes": [
    {
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [-512, 0],
      "parameters": {}
    },
    {
      "name": "Pinecone Vector Store",
      "type": "@n8n/n8n-nodes-langchain.vectorStorePinecone",
      "typeVersion": 1.3,
      "position": [224, 0],
      "parameters": {
        "mode": "insert",
        "pineconeIndex": {
          "__rl": true,
          "value": "n8n-docs",
          "mode": "list",
          "cachedResultName": "n8n-docs"
        },
        "options": {}
      }
    },
    {
      "name": "Embeddings OpenAI",
      "type": "@n8n/n8n-nodes-langchain.embeddingsOpenAi",
      "typeVersion": 1.2,
      "position": [336, 608],
      "parameters": {
        "model": {
          "__rl": true,
          "mode": "list",
          "value": "text-embedding-3-small",
          "cachedResultName": "text-embedding-3-small"
        },
        "options": { "dimensions": 1536 }
      }
    },
    {
      "name": "Recursive Character Text Splitter",
      "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
      "typeVersion": 1,
      "position": [416, 352],
      "parameters": { "chunkSize": 3000, "chunkOverlap": 500, "options": {} }
    }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Pinecone Vector Store", "type": "main", "index": 0 }]] }
  }
}
```

## Step 3, Chat with your documents (AI Agent + retrieve-as-tool)

The chat phase is a separate workflow:

```
Chat Trigger → AI Agent ← Pinecone Vector Store (Retrieve Documents (As Tool for AI Agent))
                                 ↑ Embeddings OpenAI (SAME model as insert)
                          ← OpenAI Chat Model
```

1. Add a **Chat Trigger** node, this gives you the hosted chat UI to test retrieval.
2. Add an **AI Agent** node with an **OpenAI Chat Model** sub-node (any model; a cheap one is fine for testing).
3. Add a **second Pinecone Vector Store node**, not the insert one, a new instance, and set its mode to **Retrieve Documents (As Tool for AI Agent)**. Connect it to the AI Agent's **tools** connector.
4. Give this node a sharp **Name** and **Description**, e.g. Name: `ProductDocs`, Description: `Searches the indexed product documentation for troubleshooting procedures and API details`. Per n8n's docs, the agent consults the vector store when the name and description match the question, vague descriptions are why agents "forget" to use the tool.
5. Attach the **same Embeddings OpenAI node** (text-embedding-3-small, 1536 dims) to the retrieval node. This is Pinecone's core rule restated: insert and retrieve must embed with the identical model and dimensions, or similarity search silently compares incompatible vector spaces.
6. Set **Top K** (Pinecone's default recommendation is 20), more hits for broader recall, fewer to save tokens.

Ask the chat something only your documents can answer. If the answer reflects your content, the loop works end to end: query → embedding → similarity search → chunks injected as tool output → agent composes the answer. For agent-side details (System Message, Max Iterations, Return Intermediate Steps), our [n8n AI Agent tutorial](/n8n-ai-agent-tutorial/) covers the full node reference.

## Step 4, The self-hosted alternative: Qdrant

If you don't want a managed vector database, Qdrant runs anywhere Docker runs:

```bash
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Then create a collection whose vector size matches your embedding model, this is the Qdrant equivalent of the Pinecone index-dimension rule:

```bash
curl -X PUT http://localhost:6333/collections/n8n-docs \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

In n8n, the **Qdrant Vector Store** node offers the same four modes (Get Many, Insert Documents, Retrieve Documents as Chain/Tool, Retrieve Documents as AI Agent Tool, verified in n8n 2.40.7's node definition). Create **Qdrant API** credentials with the URL and API key, pick the `n8n-docs` collection, and run the same ingestion architecture from Step 2, then a second Qdrant node in retrieve-as-tool mode on the AI Agent.

## Step 5, Test for free first: the In-Memory store

Not ready to create accounts? n8n ships a **Simple Vector Store** that lives entirely inside the workflow, plus legacy **In Memory Vector Store Insert** and **Load** nodes that share state through a `memoryKey`. Validate your chunking, splitter, and embedding settings against it at zero cost, then swap in Pinecone or Qdrant for persistence. In-memory vectors vanish when the workflow data clears, so it's a test bench, not a database.

## Going further

- **Skip the plumbing entirely**: Pinecone's own recommendation for most n8n users is their community **Pinecone Assistant** node (`@pinecone-database/n8n-nodes-pinecone-assistant`), a fully managed RAG where Pinecone handles chunking, embedding, and indexing automatically, with built-in citations. Use the Vector Store path from this tutorial when you need custom embeddings, metadata filtering, or an existing index.
- **Chain-based retrieval**: connect the vector store node in **Retrieve Documents (As Vector Store for Chain/Tool)** mode behind a **Vector Store Retriever** sub-node on a **Question and Answer Chain**, deterministic, no agent loop, cheaper per query.
- **Productionize**: add the [Error Trigger workflow](/n8n-error-handling/) so ingestion failures notify you, and check our [Zapier to n8n migration guide](/zapier-to-n8n-migration/) if this RAG pipeline is replacing a Zapier-hosted chatbot.

## Troubleshooting: 5 real failures and fixes

**1. Insert fails with a dimension mismatch error.** You created the Pinecone index (or Qdrant collection) with a different dimension count than your embedding model produces, e.g. a 3072-dim index with `text-embedding-3-small`'s 1536-dim vectors. Fix: recreate the index/collection with the exact dimension count of your model. You cannot change an index's dimensions after creation.

**2. "Index not found" / empty retrieval results.** The Vector Store node never creates indexes or collections, that is a deliberate manual step. Fix: create the index in the Pinecone console or the collection via the Qdrant REST API first, and double-check the name matches the node's `pineconeIndex` / `qdrantCollection` field character for character.

**3. The agent answers without ever querying the vector store.** Usually a vague tool name/description, n8n's docs say the agent uses the vector store when the name and description match the question details. Fix: name the node after its content (`ProductDocs`, `SupportKB`), describe exactly what it contains, and enable **Return Intermediate Steps** on the AI Agent to see whether the tool was even considered.

**4. Re-running ingestion duplicates chunks.** Insert mode upserts; it is not idempotent like Pinecone Assistant's `updateFile` operation, which deletes by `externalFileId` before re-uploading. Fix: run ingestion once per document set, or use the Pinecone node's **Namespace** / **Clear Namespace** options (on the legacy Pinecone: Insert node) to partition and wipe namespaces between runs.

**5. Retrieval returns irrelevant chunks.** Usually one of three things: chunks too large (drop toward 500–1000 chars for Q&A content), Top K too high (try 5–10 instead of 20), or, worst case, insert and retrieve used different embedding models. Fix: verify both nodes point at the same Embeddings sub-node with the same model and dimensions.

## FAQ

**Which vector databases can n8n connect to?**
n8n 2.40.7 ships vector store nodes for Pinecone, Qdrant, Supabase, Weaviate, Milvus, Chroma, pgvector, Redis, Azure AI Search, MongoDB Atlas, Oracle, Zep, and an In-Memory store, 24 vector-store node packages in total. Pinecone and Qdrant are the most documented pair for RAG workflows.

**What are the operation modes of the n8n Vector Store node?**
Most vector store nodes offer Get Many, Insert Documents, Retrieve Documents (As Vector Store for Chain/Tool), and Retrieve Documents (As Tool for AI Agent). Pinecone and Supabase add an Update Documents mode. Insert mode feeds documents in; retrieve modes hand matched documents to a chain or an AI agent.

**Why does my n8n vector store insert fail with a dimension error?**
Your vector database index was created with a different dimension count than your embedding model produces. A Pinecone index built for 3072-dimensional vectors rejects 1536-dimensional vectors from text-embedding-3-small. Create the index with the exact dimension count of your embedding model before inserting.

**Do I need Pinecone to use vector search in n8n?**
No. Qdrant is a self-hosted, open-source alternative, and n8n also ships an In-Memory Simple Vector Store for zero-cost testing. Pinecone's managed Assistant node is the lowest-effort managed option since it handles chunking, embedding, and indexing automatically.

**How do I make an n8n AI agent use my vector store?**
Add a second instance of your Vector Store node in Retrieve Documents (As Tool for AI Agent) mode and connect it to the AI Agent's tools connector. Write a specific tool name and description, n8n's docs say the agent uses the vector store when the name and description match the question details.

**What chunk size should I use when loading documents into n8n?**
Pinecone's official guidance for n8n: 3000 characters with 500 overlap as the default for long documents, or 500–1000 characters with 100–200 overlap for Q&A-style retrieval over short, dense content.

## Conclusion

You now have the full RAG loop in n8n: documents chunked and embedded into Pinecone or Qdrant, and an AI agent that retrieves them as a tool. The two rules that decide whether this works are the ones the vendors themselves stress, create the index with the embedding model's exact dimensions, and use the identical embedding model on both the insert and retrieve sides. Next, give that agent [memory and tools](/n8n-ai-agent-tutorial/) for full conversations, or harden the ingestion pipeline with the [n8n error handling tutorial](/n8n-error-handling/).
