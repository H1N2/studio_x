---
title: "n8n Code Node JavaScript Tutorial: Run Modes, $input, Data Transforms & Debugging"
slug: "n8n-code-node-javascript"
description: "n8n Code node JavaScript tutorial: master run modes, $input.all(), the { json } return format, dates, and debugging, with real errors and fixes."
date: 2026-10-01
draft: false
categories: ["n8n"]
tags: ["n8n", "code-node", "javascript", "workflow-automation", "data-transformation", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "When should I use the Code node instead of n8n's no-code nodes?"
    a: "Use the Code node when a transformation needs loops, conditionals, regex, or math that would take five no-code nodes to express. For simple field renames or single filters, the Edit Fields or Filter nodes are faster to build and easier for teammates to read. A good rule: if you can describe the transform in one sentence, use no-code; if you need a paragraph, use the Code node."
  - q: "What is the difference between Run Once for All Items and Run Once for Each Item?"
    a: "Run Once for All Items executes your code a single time and hands you every input item at once via $input.all(), which is ideal for aggregations, sorting, and filtering whole datasets. Run Once for Each Item executes your code once per input item with the current item available as $json, which is ideal for per-record enrichment. The default is Run Once for All Items."
  - q: "Why does my Code node show 'Code doesn't return items properly'?"
    a: "n8n passes data between nodes as an array of objects, and each object must wrap your data in a json key, like [{ json: { name: 'Ada' } }]. This error means your return value broke that contract: you returned nothing, returned undefined, or returned raw data without the json wrapper. Wrap every output item as { json: yourData } and return an array of those items."
  - q: "Can I use import statements or npm packages in the Code node?"
    a: "No import or export statements: n8n's JavaScript sandbox rejects them, so use require() instead. On self-hosted n8n you can unlock built-in and external modules with the NODE_FUNCTION_ALLOW_BUILTIN and NODE_FUNCTION_ALLOW_EXTERNAL environment variables. On n8n Cloud, external npm modules are not allowed, but the crypto module and the moment package are available."
  - q: "Can the Code node make HTTP requests or read files from disk?"
    a: "No. The Code node cannot access the file system or make HTTP requests, even with fetch or require('https'). Use the HTTP Request node for API calls and the Read/Write Files from Disk node for file access, then do your data transformation in the Code node. Splitting transport and transformation this way also makes workflows easier to debug."
  - q: "How do I debug JavaScript inside the Code node?"
    a: "Use console.log(). When you run the workflow manually, console.log output appears in your browser's developer console, so keep DevTools open while building. Log $input.all() first to see the exact shape of your data before you transform it, and log intermediate values when a transform misbehaves."
---

## Introduction

Every n8n user hits the same wall: the no-code nodes cover 80 percent of the work, and the remaining 20 percent is a data transformation that would need a Rube Goldberg chain of Set, Filter, and Merge nodes. That is exactly what the Code node is for. It is the escape hatch that keeps you inside n8n instead of reaching for an external script, and it is the skill that separates n8n beginners from n8n builders.

This tutorial takes you from zero to productive with the Code node's JavaScript mode: the two run modes, reading input with `$input.all()` and `$json`, returning data in the format n8n expects, working with dates, and debugging with `console.log`. Every pattern below follows the official n8n documentation, and the troubleshooting section covers the four errors every Code node user meets in their first week, with the exact fixes. If you are still setting up n8n, start with our [n8n Docker Compose setup guide](/n8n-docker-compose-setup/) first.

## Quick answer

Use n8n's Code node to run custom JavaScript in a workflow: choose Run Once for All Items or Run Once for Each Item, read input with $input.all() or $json, and return an array of { json: {...} } objects.

## Evidence

The Code node is not a niche feature. The n8n repository has passed 206,382 stars with 60,958 forks on GitHub as of October 2026, and the n8n npm package was downloaded 423,235 times in the 30 days ending September 28, 2026, which makes n8n one of the most deployed workflow engines in the self-hosted world. A large share of real-world n8n workflows include at least one Code node, because APIs rarely return data in exactly the shape the next node wants.

The official n8n documentation defines the node plainly: "Use the Code node to write custom JavaScript or Python and run it as a step in your workflow." That single sentence is the whole mental model. The Code node is a step like any other: it receives items from the previous node, runs your code, and passes items to the next node. Everything tricky about it comes from two facts documented on the [Using the Code node](https://docs.n8n.io/build/code-in-n8n/using-the-code-node/) page: the node has two run modes with different input variables, and it runs plain JavaScript against native Luxon rather than n8n's expression engine, so some expression-only helpers do not exist here. The [built-in methods and variables reference](https://docs.n8n.io/build/code-in-n8n/use-built-in-shortcuts/) spells out exactly which shortcuts work where, which saves hours of "is not a function" confusion.

## Prerequisites

- An n8n instance you can edit (self-hosted or n8n Cloud, the Code node works identically in both for everything in this tutorial except external modules).
- A workflow with at least one node producing items before the Code node. A Manual Trigger plus a Set node with two or three sample items is enough.
- Basic JavaScript: variables, arrow functions, `map`/`filter`, and template literals.
- About 30 minutes.

## Step 1: Add the Code node and choose a run mode

Add a **Code** node after any node that outputs items. Open it and look at the **Mode** dropdown at the top. There are exactly two options, and picking the wrong one is the most common beginner mistake:

- **Run Once for All Items** (default): your code executes a single time no matter how many items arrive. You receive all items at once and return all output items at once. Use this for aggregations, sorting, filtering, deduplication, and reshaping whole datasets.
- **Run Once for Each Item**: your code executes once per input item. Inside the code, the current item's data is available as `$json`. Use this for per-record logic where each item is independent, like computing a field from other fields of the same record.

A practical rule: if your code needs to compare items with each other (totals, sorting, dedupe), you need All Items mode. If each item can be processed in isolation, Each Item mode gives simpler code. Leave the default (All Items) for now.

## Step 2: Read input data with $input.all()

In All Items mode, `$input.all()` returns every item from the previous node. Each item is an object with a `json` key holding the actual data, plus metadata n8n uses for item linking. This snippet normalizes a messy contact list:

```javascript
const items = $input.all();

const cleaned = items.map((item) => {
  const data = item.json;
  return {
    json: {
      name: String(data.name || '').trim(),
      email: String(data.email || '').toLowerCase().trim(),
      signupDate: data.created_at,
    },
  };
});

return cleaned;
```

Three things to notice. First, we read from `item.json`, never from `item` directly. Second, we build brand-new objects instead of mutating the input, which keeps the workflow's data lineage clean. Third, `String(data.name || '')` guards against missing fields: real API data always has nulls where you least expect them.

## Step 3: Return data in the format n8n expects

This is the step the official docs' [common issues page](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/common-issues/) spends the most ink on, because it causes the most errors. n8n passes data between nodes as **an array of objects, where each object wraps your data in a `json` key**:

```javascript
// Correct: an array of items, each with a json key
return [
  { json: { name: 'Ada', role: 'admin' } },
  { json: { name: 'Grace', role: 'editor' } },
];
```

These all fail:

```javascript
return { name: 'Ada' };              // not an array of items
return [{ name: 'Ada' }];            // missing the json wrapper
return [{ json: ['Ada', 'Grace'] }]; // json must be an object, not an array
// no return statement at all       // returns undefined
```

The error messages n8n shows for these are literal: "Code doesn't return items properly", "A 'json' property isn't an object", and "Code doesn't return an object". When you see any of them, check your return statement first. It is the return statement 90 percent of the time.

## Step 4: Process one item at a time with $json

Switch the node to **Run Once for Each Item** mode. Now the code runs once per input item, and the current item's data is available as `$json`. This example adds tax calculations to order line items:

```javascript
const price = Number($json.price) || 0;
const taxRate = 0.2;

return {
  json: {
    product: $json.product,
    price: price,
    tax: Math.round(price * taxRate * 100) / 100,
    total: Math.round(price * (1 + taxRate) * 100) / 100,
  },
};
```

In Each Item mode you return the single item object for the current item, and n8n collects one output item per execution. A classic mistake is using `$json` while still in All Items mode, where it does not exist, or using `$input.all()` inside Each Item mode and then wondering why every run returns the full dataset. Match the variable to the mode: `$input.all()` for All Items, `$json` for Each Item.

## Step 5: Reach back to earlier nodes with $('NodeName')

Workflows often need data from two branches at once, for example enriching orders from a "Fetch Orders" node with customer details from a "Fetch Customers" node. Inside the Code node you can pull any earlier node's output by name:

```javascript
const orders = $input.all();
const customers = $('Fetch Customers').all();

const byId = new Map(customers.map((c) => [c.json.customer_id, c.json]));

return orders.map((order) => ({
  json: {
    ...order.json,
    customerName: byId.get(order.json.customer_id)?.name || 'Unknown',
  },
}));
```

`$('Fetch Customers').all()` returns that node's items for the current run, in the same `{ json }` format. This is documented in n8n's cookbook under the `$("<node-name>").all()` recipe. Two cautions: the name must match the node's display name exactly, including spaces and capitalization, and renaming the node later silently breaks the reference, so prefer stable, descriptive node names.

## Step 6: Work with dates using native Luxon

The Code node runs plain JavaScript against native Luxon, not n8n's expression engine. In practice that means `DateTime` is available directly in the Code node, but n8n-only extensions from the expressions editor do not exist here. The [built-in methods reference](https://docs.n8n.io/build/code-in-n8n/use-built-in-shortcuts/) calls this out explicitly: if code throws "... is not a function", check whether the method is tagged as custom n8n functionality and use the native equivalent instead.

```javascript
const items = $input.all();

return items.map((item) => {
  const created = DateTime.fromISO(item.json.created_at, { zone: 'utc' });
  return {
    json: {
      ...item.json,
      createdLocal: created.setZone('Asia/Shanghai').toFormat('yyyy-MM-dd HH:mm'),
      ageDays: Math.floor(DateTime.now().diff(created, 'days').days),
    },
  };
});
```

Two native-Luxon details that bite people migrating from expressions: use `toFormat()` instead of the expression-only `DateTime.format()`, and `DateTime.plus()`/`minus()` accept a single duration object like `{ days: 7 }`, not the expression-style `(7, 'days')` signature. The expression-style call will not throw, it will just silently produce the wrong result, which is worse.

## Step 7: Debug with console.log and promises

When a transform misbehaves, `console.log` is your debugger. Run the workflow manually with your browser's developer console open: `console.log` output from the Code node appears in the browser console. Log the input shape before you transform it:

```javascript
const items = $input.all();
console.log('INPUT COUNT:', items.length);
console.log('FIRST ITEM:', JSON.stringify(items[0].json, null, 2));
// ... your transform here ...
```

The Code node also supports promises: instead of returning items directly, you can return a promise that resolves to the items. This is handy for paced or retrying logic:

```javascript
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

return (async () => {
  const items = $input.all();
  const results = [];
  for (const item of items) {
    await wait(200); // be polite to the downstream API
    results.push({ json: { ...item.json, processed: true } });
  }
  return results;
})();
```

Note what is deliberately absent: HTTP calls. The Code node cannot access the file system or make HTTP requests, so there is no `fetch` here. For API calls use the [HTTP Request node](/n8n-error-handling/) pattern from our error-handling tutorial, then transform its output in the Code node. Keeping transport and transformation in separate nodes makes failures far easier to diagnose.

## Troubleshooting

### 1. "Code doesn't return items properly"

The single most common Code node error. n8n expected an array of `{ json }` items and got something else. Almost always the fix is in the return statement: you returned a bare object, forgot the `json` wrapper, or have a code path that returns nothing. Add a final `return` that always produces the array, and watch out for early `return;` statements inside conditionals.

### 2. "'import' and 'export' may only appear at the top level"

n8n's JavaScript sandbox does not support `import`/`export` syntax at all. Rewrite imports with `require()`:

```javascript
// Fails in the Code node
import _ from 'lodash';

// Use this instead (self-hosted, with modules enabled)
const _ = require('lodash');
```

On n8n Cloud, external npm modules are unavailable entirely, and only the `crypto` built-in module and the `moment` package are provided. On self-hosted n8n, enable modules with environment variables before starting n8n: `NODE_FUNCTION_ALLOW_BUILTIN=crypto` for built-ins, or `NODE_FUNCTION_ALLOW_EXTERNAL=lodash,moment` for npm packages installed under n8n's `node_modules` directory. Our [n8n Docker Compose guide](/n8n-docker-compose-setup/) shows where to put environment variables.

### 3. "$json is not defined" or expression helpers "is not a function"

Two different causes, one theme: wrong context. `$json` exists only in Run Once for Each Item mode; in All Items mode use `$input.all()`. And helpers like `$jmespath()` or `$if()` are expressions-editor-only, they do not exist in the Code node at all. The Code node runs plain JavaScript, so reach for native JS (`Array.filter`, optional chaining) instead of expression helpers.

### 4. Dates come out wrong but nothing throws

You used an expression-style Luxon call in the Code node. `DateTime.plus(7, 'days')` is valid in n8n expressions but in the Code node's native Luxon it silently ignores the arguments. Use `DateTime.now().plus({ days: 7 })` and `toFormat()` instead of `DateTime.format()`. When a date looks "almost right", compare against the native Luxon docs before blaming your data.

## Conclusion

The Code node earns its place in every serious n8n setup: pick the right run mode, read with `$input.all()` or `$json`, always return an array of `{ json }` items, remember it is plain JavaScript with native Luxon rather than the expression engine, and debug with `console.log`. Those five habits prevent nearly every Code node problem documented in n8n's common issues.

Next, learn the failure-handling side: our [n8n error handling tutorial](/n8n-error-handling/) shows how retries, error outputs, and Error Trigger workflows keep Code-node-powered automations alive in production. And if your workflows are growing into AI territory, the [n8n AI agent tutorial](/n8n-ai-agent-tutorial/) puts Code nodes to work inside agent tool calls.
