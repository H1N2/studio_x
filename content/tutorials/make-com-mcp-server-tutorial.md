---
title: "Make.com MCP Server Tutorial: Turn Your Scenarios into AI Tools"
slug: "make-com-mcp-server-tutorial"
description: "Turn Make.com scenarios into callable MCP tools: create an MCP token, wire up OAuth or token auth, lock down access by scenario, and handle timeouts."
date: 2026-10-04
draft: false
categories: ["Automation"]
tags: ["make", "mcp", "model-context-protocol", "claude", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Does the Make MCP server work on the Free plan?"
    a: "Yes, for running scenarios. Scenario run tools are available on all plans, including Free. Management tools, which let an AI client view or modify scenarios, connections, and teams, are available on paid plans only."
  - q: "Do MCP tool calls cost extra on top of my Make subscription?"
    a: "No add-on fee, but each call burns the scenario's normal operations. A tool call that triggers a five-module scenario consumes the same ops as a manual run of that scenario, so heavy agent usage can eat your monthly ops quota."
  - q: "Should I use OAuth or an MCP token to connect?"
    a: "OAuth is simplest: paste https://mcp.make.com into your client and authorize when prompted. Use an MCP token when your client cannot do OAuth, when you need access control by organization, team, or scenario, or when you want the longer 40-second tool timeout."
  - q: "How is Make MCP billing different from Zapier MCP?"
    a: "Make bills the underlying scenario run, the same ops a manual run would consume. Zapier's MCP server instead deducts each tool call directly from your task pool, two tasks per call according to Zapier's own documentation, regardless of how complex the underlying Zap is."
  - q: "Can an AI client edit or delete my scenarios through MCP?"
    a: "Only if you grant it management scopes on a paid plan. The default mcp:use scope only lets the client list and run active, on-demand scenarios. Never hand an agent management scopes unless you specifically need it to build scenarios for you."
  - q: "Why did my tool call time out even though the scenario kept running?"
    a: "Make caps tool-call response waits at 25 seconds over OAuth and 40 seconds with an MCP token, while the scenario itself keeps running for up to 40 minutes. The timeout response includes an executionId; with the scenarios:read scope, the client can fetch the result after the run finishes."
---

## Introduction

Your Make scenarios already automate the boring parts of your business. This tutorial shows you how to expose those scenarios as tools that an AI agent can call directly from Claude, ChatGPT, or Cursor. By the end, you will have connected the Make MCP server, published a scenario as a callable tool with a well-designed input schema, locked the agent down to exactly the scenarios it needs, and handled the timeout behavior that trips up most first-time setups. It is written for Make users who already build scenarios and now want agents to run them.

## Quick answer

Connect your AI client to the Make MCP server: create an MCP token with the mcp:use scope, point your client at https://<zone>/mcp/u/<token>, set your scenarios to active and on-demand, then call them as tools.

## Evidence

Make's MCP story is generous on pricing. Scenario run tools work on every plan, including the Free tier, while management tools stay behind the paid plans, and the tool-call wait limits are short enough to matter: 25 seconds over OAuth and 40 seconds with an MCP token for scenario runs, versus 30 and 60 seconds for management tools. A timed-out scenario keeps running for up to 40 minutes, and the timeout response hands you an executionId to fetch the result later. All of these figures come straight from Make's developer documentation, which I fetched on October 4, 2026.

Cost context helps too: in September 2026 Make refreshed its subscription pricing, cutting roughly 25 percent, with the Core plan dropping from $12 to $9 per month, according to third-party pricing comparisons published that month.

The single most useful official guidance is about tool design, and Make puts it plainly: "Write detailed scenario descriptions to help MCP clients understand what each scenario does and get more reliable results." A scenario's name, description, inputs, and outputs are the entire contract the agent sees, so treat them like a public API, not internal notes.

The walkthrough below follows Make's own documentation for [creating an MCP token](https://developers.make.com/mcp-server/connect-using-mcp-token) and [restricting scenario access](https://developers.make.com/mcp-server/connect-using-mcp-token/scenarios-as-tools-access-control.md), the [scenario inputs and outputs guide](https://help.make.com/scenario-inputs-and-outputs) for tool parameter design, and Make's official [make-skills repository on GitHub](https://github.com/integromat/make-skills) for connection config shapes.

## Prerequisites

- A Make account on any plan, including Free. Know your hosting zone, for example eu2.make.com, which appears in your Make URL.
- At least one working scenario you are willing to let an agent run.
- An MCP client: Claude Code, Claude Desktop, Cursor, ChatGPT, or any client that supports remote HTTP MCP servers.
- Basic familiarity with Make scenario building: modules, filters, and scheduling.

## Step-by-step guide

### Step 1: Pick a scenario worth turning into a tool

Not every scenario makes a good tool. Good candidates are self-contained operations with clear inputs and a single clear result: look up a customer record, append a row to a sheet, or generate a report. Avoid scenarios with ambiguous side effects or ones that need a human decision in the middle, since the agent will call them blindly.

### Step 2: Set the schedule to On demand and activate the scenario

For a scenario to appear as an MCP tool, Make requires two things: the scenario must be active, and its scheduling must be set to on-demand. Open the scenario, set the scheduling option to On demand, save, and flip the scenario to active. If either condition is missing, the scenario silently stays out of the tool list, which is the most common reason for an empty tool list after connecting.

### Step 3: Define scenario inputs and outputs as the tool contract

Open the scenario's inputs and outputs settings, following the structure in Make's [scenario inputs and outputs guide](https://help.make.com/scenario-inputs-and-outputs). Inputs become the tool's parameters, the fields the agent fills in, and outputs become the tool's return values.

Design the contract like you would a function signature:

- Use clear, specific names, for example customer_email rather than input1. The agent sees only these names.
- Write a one-line description for every input explaining what it expects, including format hints like "ISO date, YYYY-MM-DD".
- Prefer concrete data types over generic Any. A text input described as "email address" beats an Any field every time.
- Keep the output focused. Return the record the agent needs, not the raw bundle of everything the scenario touched.

Also keep execution time in mind from the start: tool calls only wait 25 to 40 seconds for a response, so a scenario that polls an external API for three minutes will always return a timeout first. Design fast scenarios, and rely on the executionId pattern for long ones, covered in step 8.

### Step 4: Write a detailed scenario description

This is the step most people skip and then wonder why the agent picks the wrong tool. Make's docs are explicit: detailed descriptions get more reliable results. Write two to four sentences covering what the scenario does, when to use it, and when NOT to use it. Example: "Looks up a customer in the CRM by email and returns their plan and renewal date. Use when you need billing context before answering a support question. Do not use for creating new customers, that is a different tool." Constraints in the description are free guardrails.

### Step 5: Create an MCP token

The Make MCP server connects through OAuth or an MCP token, and the token path gives you access control and headless-client support. To get one, follow the flow documented in [Make's token guide](https://developers.make.com/mcp-server/connect-using-mcp-token):

1. In the top-right corner of your Make account, click your name.
2. Click Profile.
3. Open the API access tab.
4. In Tokens, click Add token.
5. Select your scopes, and include the mcp:use scope to expose your scenarios as tools.
6. Give the token a clear label, for example "Claude MCP run-only".
7. Click Add, then copy the token.

Treat this token as a secret from the first second. It can run your scenarios, and with broader scopes it can manage your account. Never commit it to git, never paste it into a shared doc.

### Step 6: Build the connection URL with access control

The base URL form is:

```
https://<MAKE_ZONE>/mcp/u/<MCP_TOKEN>
```

Replace MAKE_ZONE with your zone, such as eu2.make.com, and MCP_TOKEN with the token from step 5. By default, the mcp:use scope exposes every active, on-demand scenario across all of your organizations, which is far too broad for most agents. Restrict it with the query parameters from Make's [access control documentation](https://developers.make.com/mcp-server/connect-using-mcp-token/scenarios-as-tools-access-control.md):

- Organization level: `?organizationId=<id>` exposes only that organization's scenarios.
- Team level: `?teamId=<id>` exposes only that team's scenarios.
- Scenario level: `?scenarioId=<id>` exposes only that one scenario.

You can pass several scenarios with the array syntax, `?scenarioId[]=<id1>&scenarioId[]=<id2>`, but you cannot combine levels, they are mutually exclusive. For a first setup, scenario-level restriction is the right default: the agent sees exactly the tools you built for it and nothing else.

If your client supports Authorization headers, you can use `https://<MAKE_ZONE>/mcp` with `Authorization: Bearer <MCP_TOKEN>` instead of putting the token in the URL. If it does not, the URL form works everywhere. One more useful parameter: `?maxToolNameLength=` adjusts the generated tool name length cap, which defaults to 56 characters and accepts values from 32 to 160.

### Step 7: Connect your MCP client

There are two connection methods. OAuth is the one-click path: add a remote MCP server with the URL https://mcp.make.com in your client and authorize when prompted. The token path uses the URL you built in step 6. A Claude Code config entry looks like this, matching the shape in Make's [official skills repository](https://github.com/integromat/make-skills):

```json
{
  "mcpServers": {
    "make": {
      "type": "http",
      "url": "https://eu2.make.com/mcp/u/<MCP_TOKEN>?scenarioId[]=123456"
    }
  }
}
```

Replace the zone, token, and scenario ID with your own values. After saving, restart the client or reload its MCP configuration so the new server registers.

For an official conceptual grounding on how remote MCP servers work and what the stateless HTTP transport means, our [MCP server tutorial](/mcp-server-tutorial/) covers the protocol basics, and the [MCP stateless spec migration guide](/mcp-stateless-spec-migration/) explains why modern servers like Make's run over stateless Streamable HTTP instead of the old session-based wire.

### Step 8: Verify the tools and run the first call

Ask the agent something like: "What tools do you have from the Make MCP server?" It should list your scenario by its name and description. If the list is empty, go back to step 2 and confirm the scenario is active and on-demand, and that your token carries the mcp:use scope. Then give it a simple real task: "Look up the customer with email jane@example.com using the Make tool." Watch the run and confirm the output matches what a manual scenario run produces.

For setting up Claude Code's MCP side in general, our [Claude Code MCP setup guide](/claude-code-mcp-setup/) walks through the client configuration in detail.

### Step 9: Handle long-running scenarios with the executionId pattern

When a tool call exceeds the wait limit, the client receives a timeout response like this:

```json
{
  "instruction": "The Tool execution has started, but did not complete yet. Use a corresponding Tool for getting Execution Results to check for the result asynchronously.",
  "executionId": "4eb841b3fe3d48a5b2b59e2eed3f55be",
  "scenarioId": 1
}
```

This is not a failure. The scenario keeps running in Make for up to 40 minutes. The agent can poll for the result using the corresponding results tool, but only if your token also carries the scenarios:read scope. Tell the agent in its system prompt that a timeout means "check back with the executionId", and prefer token auth for the longer 40-second wait when your scenarios are slow.

## Troubleshooting

### The tool list is empty after connecting

Causes, in order of likelihood: the scenario is not active, its schedule is not On demand, the token lacks the mcp:use scope, or your access-control query parameters exclude the scenario. Fix: verify active plus on-demand in the scenario editor, regenerate the token with mcp:use selected, and test with a URL that has no query parameters before re-adding restrictions. The official [token guide](https://developers.make.com/mcp-server/connect-using-mcp-token) shows exactly where the scopes are selected.

### Scenario run tools time out on every call

The 25-second OAuth limit is easy to hit. Switch to MCP token auth for the 40-second limit, and audit the scenario for slow modules: long sleeps, polling loops, and large API pagination are the usual culprits. For scenarios that genuinely take minutes, keep the timeout response workflow from step 9: return the executionId, and have the agent fetch the result with the scenarios:read scope.

### Management tools do not appear or return permission errors

Management tools are a paid-plan feature. If you are on Free, the client only gets scenario run tools, by design. On a paid plan, the token must include the management scopes, not just mcp:use. Also remember the timeout limits are higher but still finite: 30 seconds over OAuth, 60 seconds with a token.

### Tool names get truncated or collide

Make generates tool names from scenario names and caps them at 56 characters by default. Two scenarios named "Sync customer record to CRM" and "Sync customer record to CMS" can produce identical truncated names. Fix: rename scenarios with distinct prefixes, or set `?maxToolNameLength=` higher in the URL, up to 160 characters.

### A token may have leaked

If a token was committed to git or pasted somewhere public, delete it from Profile, API access, Tokens, and create a fresh one with a narrower scope. Then rotate the connection URL everywhere. Prevention beats cleanup: scenario-level query parameters mean even a leaked token only reaches one scenario.

## FAQ

### Does the Make MCP server work on the Free plan?

Yes, for running scenarios. Scenario run tools are available on all plans, including Free. Management tools, which let an AI client view or modify scenarios, connections, and teams, are available on paid plans only.

### Do MCP tool calls cost extra on top of my Make subscription?

No add-on fee, but each call burns the scenario's normal operations. A tool call that triggers a five-module scenario consumes the same ops as a manual run of that scenario, so heavy agent usage can eat your monthly ops quota.

### Should I use OAuth or an MCP token to connect?

OAuth is simplest: paste https://mcp.make.com into your client and authorize when prompted. Use an MCP token when your client cannot do OAuth, when you need access control by organization, team, or scenario, or when you want the longer 40-second tool timeout.

### How is Make MCP billing different from Zapier MCP?

Make bills the underlying scenario run, the same ops a manual run would consume. Zapier's MCP server instead deducts each tool call directly from your task pool, two tasks per call according to Zapier's own documentation, regardless of how complex the underlying Zap is.

### Can an AI client edit or delete my scenarios through MCP?

Only if you grant it management scopes on a paid plan. The default mcp:use scope only lets the client list and run active, on-demand scenarios. Never hand an agent management scopes unless you specifically need it to build scenarios for you.

### Why did my tool call time out even though the scenario kept running?

Make caps tool-call response waits at 25 seconds over OAuth and 40 seconds with an MCP token, while the scenario itself keeps running for up to 40 minutes. The timeout response includes an executionId; with the scenarios:read scope, the client can fetch the result after the run finishes.

## Conclusion

The Make MCP server turns your best scenarios into an agent's hands: pick one good scenario, make it active and on-demand, design its inputs and outputs like an API contract, connect with a tightly scoped token, and plan for the timeout behavior instead of fighting it. If you are still choosing a platform, our [n8n versus Make comparison for AI agents](/n8n-vs-make-ai-agents/) and the [Zapier to n8n migration guide](/zapier-to-n8n-migration/) are useful companion reads. Next, connect more of your stack on the client side: our guide to [connecting MCP servers to Claude Desktop](/connect-mcp-server-to-claude-desktop/) shows the client configuration in detail.
