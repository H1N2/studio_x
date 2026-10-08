---
title: "How to Build Multi-Agent Workflows in n8n with Sub-Agents"
slug: "n8n-multi-agent-sub-agents-tutorial"
date: 2026-10-08T18:30:00+08:00
draft: false
description: "Build multi-agent workflows in n8n with sub-agents: parent orchestrator design, nested workflow tools, session debugging, and production guardrails."
categories: ["n8n", "AI Agents"]
tags: ["n8n", "ai-agents", "sub-agents", "multi-agent", "workflow-automation"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "What is the difference between a sub-agent and the Execute Workflow node?"
    a: "The Execute Workflow node runs another workflow deterministically as a fixed step in a sequence. A sub-agent exposed through a Call n8n Workflow tool is different: the parent agent decides on its own when to call it, what input to pass, and how to use the result, based on the tool description you write."
  - q: "Do sub-agent calls consume extra workflow executions?"
    a: "No. According to the official n8n blog, one turn with an agent counts as one execution, and tool calls to your workflows and to sub-agents do not count separately. Agents share your workflow execution quota."
  - q: "How many levels of nesting should I use?"
    a: "Keep nesting to two levels: one parent orchestrator and one layer of specialist sub-agents. Every extra layer appends another full round trip to the parent's context window and adds latency, so deeper hierarchies get slower and less reliable."
  - q: "Which n8n version do I need for nested sub-agent tools?"
    a: "Use n8n 2.42.0 or later, released September 29, 2026. That release fixed nested tool execution so an AI Agent Tool can use its own tools even under a pre-v3 parent agent. On older versions, nested calls can fail at the tool boundary."
  - q: "Can a sub-agent use its own tools?"
    a: "Yes. A sub-workflow can contain its own AI Agent node with tools attached, such as web search, a vector store, or a calculator. That nested pattern is exactly what the 2.42.0 fix enables, so each specialist can be genuinely capable, not just a prompt."
  - q: "How do I see what a sub-agent actually did when something goes wrong?"
    a: "Open the Executions list, find the parent run, and follow it into the sub-workflow runs. Each sub-agent call appears as its own execution with its input, tool calls, and output. If you build on the newer Agents product instead, use its Sessions view for the same purpose."
---

## Introduction

A single AI agent with twenty tools is a generalist that does everything badly. A parent orchestrator that delegates to specialist sub-agents is a team that does a few things well. This tutorial shows you how to build that team in n8n: one parent AI Agent that plans and delegates, plus focused sub-agents wrapped as tools, each with narrow responsibilities and their own toolsets. It is written for n8n users who already built a basic agent and now hit the wall where one prompt and one tool list cannot cover the job.

## Quick answer

Give a parent AI Agent Call n8n Workflow tools pointing to sub-workflows. Each sub-workflow starts with a When Executed by Another Workflow trigger and runs its own AI Agent with narrow tools. Keep nesting to two levels, debug via sessions.

## Evidence

Multi-agent orchestration is not a niche experiment. n8n is one of the most widely deployed automation platforms in the world: the project had 206,873 GitHub stars and its official Docker image had been pulled 269,082,215 times, both measured on October 8, 2026. The platform is moving hard toward agent hierarchies. n8n 2.42.0, released September 29, 2026, shipped a targeted fix so that an AI Agent Tool can use its own tools even when the parent agent node is pre-v3, which means nested sub-agent calls now resolve inline instead of failing at the tool boundary.

The vendor frames agents as the new primitive. As the [official n8n blog](https://blog.n8n.io/introducing-n8n-agents/) put it when launching the Agents product on September 25, 2026: "n8n now has Agents. You describe what an agent should do, give it a model and the tools and workflows it can use, and it works out the steps itself." The same post answers the cost question that stops most teams from trying multi-agent designs: "One turn with an agent is one execution. Tool calls to your workflows and to sub-agents don't count separately, and agents share your workflow execution quota."

The mechanics in this tutorial rest on three documented building blocks: the [AI Agent node](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/), which is the root node that reasons and calls tools; the [Call n8n Workflow tool](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolworkflow/), which packages any workflow as a tool an agent can invoke; and the [Execute Workflow Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executeworkflowtrigger/), the trigger that lets a workflow be started by another workflow or by an agent tool.

## Prerequisites

- n8n 2.42.0 or later, self-hosted with Docker or n8n Cloud. The nested sub-agent fix landed in 2.42.0, so upgrade before you start.
- An OpenAI or Anthropic API key with a few dollars of credit, connected as a chat model credential in n8n.
- A basic agent already working. If you have never wired an agent, read our [AI Agent node tutorial](https://www.161808.xyz/n8n-ai-agent-tutorial/) first.
- Comfort with the n8n editor: adding nodes, connecting them, and opening the Executions list.

## Step 1: Design the team before you build it

Sub-agents fail most often because of org-chart problems, not technical ones. Before touching the editor, write down the split. A good rule: the parent orchestrator plans and delegates but never does specialist work itself, and each sub-agent owns exactly one job with a crisp input contract.

For this tutorial we will build a small research team with three members. The parent orchestrator takes a user question, decides what needs researching and what needs writing, and merges the results. The researcher sub-agent answers one focused factual question using its Wikipedia tool and returns only sourced facts. The writer sub-agent turns facts into a polished briefing and never browses. Two levels, three agents, no overlap. If you cannot state a sub-agent's job in one sentence, the split is wrong.

## Step 2: Build the researcher sub-agent workflow

Create a new workflow named `subagent-researcher`. Its first node must be the When Executed by Another Workflow trigger, which is the documented entry point for any workflow that will be called as a tool. Connect it to an AI Agent node. Attach two sub-nodes to that agent: a chat model (your OpenAI or Anthropic credential) and the Wikipedia tool from the AI Agent Tools category. Optionally attach Simple Memory so follow-up questions in one session keep context.

Give the researcher a strict system prompt. This prompt is the sub-agent's entire job description, and the parent will never see it, so make it self-contained:

```text
You are a research specialist. Answer ONLY the single factual question you receive.
Use the Wikipedia tool for every claim. Return a bullet list of facts, each with
its source article title. Return facts only, no introduction, no conclusion,
no reasoning trace.
```

Save the workflow. The workflow must be saved before another workflow can reference it as a tool, so do not skip this. Test it once with the manual trigger path if your version offers one, or move on and test through the parent later.

## Step 3: Build the writer sub-agent workflow

Create a second workflow named `subagent-writer` with the same structure: When Executed by Another Workflow trigger, then an AI Agent node with a chat model and Simple Memory, but no search tools. The writer's system prompt makes its contract explicit:

```text
You are a briefing writer. You receive a bullet list of facts. Turn it into a
clear 150-word briefing with a headline. Do not add facts that are not in the
input. Do not browse or speculate. Return only the briefing.
```

Notice the pattern: each sub-agent is deliberately crippled. The researcher cannot write prose, the writer cannot browse. Narrow tools are what make sub-agents reliable, because the model has fewer ways to go wrong. Save this workflow too.

## Step 4: Build the parent orchestrator

Create the main workflow, for example `agent-team-briefing`. Start it with a Chat Trigger node so you can talk to the team. Connect it to an AI Agent node with your chat model and Simple Memory attached. This is the orchestrator, and its system prompt should describe delegation, not execution:

```text
You are an orchestrator. You never answer factual questions yourself.
For research, call the researcher tool with one focused question.
For writing, call the writer tool with the facts you received.
Then present the final briefing to the user.
```

Now attach the sub-agents as tools. On the parent AI Agent node, add two tools of type Call n8n Workflow from the AI Agent Tools category. In each tool's settings, pick one of the saved sub-workflows from the workflow picker. This is the documented mechanism for [using another n8n workflow as a tool](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolworkflow/): the parent agent sees the tool, decides when to call it, and the sub-workflow runs with its own agent inside.

## Step 5: Write tool descriptions as contracts

This step decides whether your team works. The parent model chooses tools using only their names and descriptions, so each description must read like a contract with three clauses: when to call it, what input to pass, and what comes back. Vague descriptions are the number one cause of sub-agents that never get called.

Good researcher description:

```text
Call this when the user asks a factual question that needs sourced information.
Input: ONE focused factual question as plain text, for example "What year was
the n8n Agents product launched?" Returns: a bullet list of facts with source
titles. Do not pass multi-part requests; split them into separate calls.
```

Good writer description:

```text
Call this after you have collected all facts. Input: the complete bullet list
of facts exactly as the researcher returned it. Returns: a 150-word briefing
with a headline. Never call this before research is done.
```

These two paragraphs encode your entire orchestration policy. The parent does not need complex instructions because the tools tell it what to do.

## Step 6: Run the team and inspect what happened

Open the chat, ask something like "Brief me on the n8n Agents product launch," and watch the execution. Then open the Executions list. You will see the parent run, and under it the sub-workflow runs for the researcher and writer calls, each with its own input, tool calls, and output. Click into a sub-agent execution when the answer looks wrong: nine times out of ten the problem is visible there, either a bad question passed down or a weak tool description.

If you build on the newer Agents product rather than the classic AI Agent node, the same debugging idea applies through its Sessions view, which keeps the conversation history per agent. Our [n8n Agents product walkthrough](https://www.161808.xyz/n8n-agents-tutorial/) covers that surface in detail.

Expect the first run to be imperfect. Common first-run symptom: the parent answers directly instead of delegating. The fix is almost always in Step 5, not in the model. Strengthen the "never answer factual questions yourself" line and make the tool descriptions more commanding until delegation happens reliably across three test questions.

## Step 7: Back up the team and harden it for production

An agent team is three workflows that must stay in sync, so treat them like code. Export all three with the n8n CLI, which we verified on a lab instance running n8n 2.41.4:

```bash
n8n export:workflow --all --output=agent-team-backup/
```

Run this before every change and keep the directory in version control. If you ever need to roll back a prompt edit that made the team worse, the exported JSON is your undo button.

Three production guardrails are worth adding now. First, pin your n8n version and upgrade deliberately, because agent behavior changes between releases and 2.42.0 is the floor for reliable nesting. Second, cap the team's autonomy the same way you would a junior employee: keep approval on any sub-agent whose tools can send messages, spend money, or modify data. Third, when the team moves past experiments, run it on [queue mode](https://www.161808.xyz/n8n-queue-mode-scaling/) so concurrent chat sessions do not block each other, and reuse the [error handling patterns](https://www.161808.xyz/n8n-error-handling/) from single-agent workflows for the parent orchestrator.

## Troubleshooting

**The sub-workflow does not appear in the Call n8n Workflow picker.**
The picker lists saved workflows, and only workflows that start with the When Executed by Another Workflow trigger can serve as agent tools. Save the sub-workflow, confirm its first node is that trigger, then reopen the tool node on the parent. The workflow appears after saving.

**The parent agent never calls the sub-agent tools.**
The model selects tools from name and description alone. A description like "helper workflow" gives it nothing to match against the user's request. Rewrite each description as a contract with when-to-call, exact input format, and return format, as shown in Step 5. Test with three different questions before concluding the model is at fault.

**Nested tool calls fail with an error at the tool boundary.**
This is the exact bug fixed in n8n 2.42.0: previously an AI Agent Tool could not use its own tools under a pre-v3 parent agent. Check your version in the editor footer or with the CLI, and upgrade to 2.42.0 or later. If you must stay on an older version, flatten the hierarchy so no tool-carrying agent sits under another agent.

**Answers get worse as I add more sub-agents.**
Every sub-agent round trip appends its full output to the parent's context window, so deep nesting burns context and adds latency with each layer. Keep the hierarchy at two levels, and instruct each sub-agent to return only its final answer with no reasoning trace, as the example prompts in Steps 2 and 3 do.

**The sub-agent runs but complains about its input.**
The workflow tool passes whatever text the parent model puts into the call, so a mismatch between what the parent sends and what the sub-workflow reads breaks the run. Keep the contract to one text field, read it from the trigger's JSON at the top of the sub-workflow, and document the exact input format in the tool description.

## FAQ

**What is the difference between a sub-agent and the Execute Workflow node?**
The Execute Workflow node runs another workflow deterministically as a fixed step in a sequence. A sub-agent exposed through a Call n8n Workflow tool is different: the parent agent decides on its own when to call it, what input to pass, and how to use the result, based on the tool description you write.

**Do sub-agent calls consume extra workflow executions?**
No. According to the official n8n blog, one turn with an agent counts as one execution, and tool calls to your workflows and to sub-agents do not count separately. Agents share your workflow execution quota.

**How many levels of nesting should I use?**
Keep nesting to two levels: one parent orchestrator and one layer of specialist sub-agents. Every extra layer appends another full round trip to the parent's context window and adds latency, so deeper hierarchies get slower and less reliable.

**Which n8n version do I need for nested sub-agent tools?**
Use n8n 2.42.0 or later, released September 29, 2026. That release fixed nested tool execution so an AI Agent Tool can use its own tools even under a pre-v3 parent agent. On older versions, nested calls can fail at the tool boundary.

**Can a sub-agent use its own tools?**
Yes. A sub-workflow can contain its own AI Agent node with tools attached, such as web search, a vector store, or a calculator. That nested pattern is exactly what the 2.42.0 fix enables, so each specialist can be genuinely capable, not just a prompt.

**How do I see what a sub-agent actually did when something goes wrong?**
Open the Executions list, find the parent run, and follow it into the sub-workflow runs. Each sub-agent call appears as its own execution with its input, tool calls, and output. If you build on the newer Agents product instead, use its Sessions view for the same purpose.

## Conclusion

A parent orchestrator plus narrow specialist sub-agents is the simplest multi-agent architecture that actually works in n8n: design the split on paper, wrap each specialist in a workflow with the Execute Workflow Trigger, expose them through Call n8n Workflow tools with contractual descriptions, and debug through executions. Keep the hierarchy two levels deep and back up the team with the export CLI before every change.

When your specialists need reusable behavior across projects, the next step is packaging that behavior as skills: our [agent skills guide](https://www.161808.xyz/n8n-agent-skills-tutorial/) shows how to write a SKILL.md that lets coding agents generate correct n8n workflows.
