---
title: "{{ replace .Name "-" " " | title }}"
slug: ""
date: {{ .Date }}
draft: true
description: ""
categories: []
tags: []
author: "ToolPilot Team"
toc: true
faq: []
---

Write a 1500-2500 word hands-on tutorial. Structure:

## Introduction
One paragraph: what the reader will achieve and who it's for.

## Quick answer
Right after the intro, answer the article's core question in ~40 words,
then expand with steps below. (This wins featured snippets and AI citations.)

## Evidence density (GEO requirement — peer-reviewed, Princeton KDD 2024)
Every tutorial MUST include:
- At least 2 real, named statistics with their source (e.g. pricing
  numbers from the vendor's own page, adoption figures from a named
  report, your own measured timings). Timestamp them: "as of Sept 2026".
- At least 1 direct expert or vendor quotation (docs, changelog, release
  notes, official blog) that supports a key claim.
- At least 2 outbound citations to DIFFERENT URLs of primary documentation
  (docs.n8n.io, modelcontextprotocol.io, vendor docs, official GitHub repos)
  for non-obvious factual claims. Link with descriptive anchors, woven into
  the relevant paragraph (not dumped at the end). Verify each URL returns
  HTTP 200 with curl before publishing.
These are the only content interventions with causal evidence of boosting
AI-engine citations (+30-40% visibility; biggest gains for non-top-ranked sites).
Keyword stuffing demonstrably hurts — don't do it.

SEO hygiene (jev-seo checklist):
- description: 120-160 characters, keyword-inclusive, natural sentence.
- em-dash (—) density ≤ 2 per 500 words in prose; use commas for asides.
  Never put em-dashes inside code spans (they're literal content there).

Write self-contained sentences: each claim should survive being quoted
alone, without relying on surrounding paragraphs for meaning.

## Prerequisites
Bulleted list: accounts, software versions, skill level.

## Step-by-step guide
Numbered H2/H3 steps. Every step must be something actually tested:
include real commands, real config snippets, real output, and real
error messages with fixes. No invented UI labels — only describe
screens you (or the lab notes) actually walked through.
Add first-hand specifics AI can't replicate: your own screenshots,
exact settings, measured numbers, opinionated verdicts.

## Troubleshooting
At least 3 real problems with causes and fixes.

## FAQ
4-6 questions readers actually ask. Keep the FAQ section on the page
(on-page FAQ helps readers and AI citations; no FAQ schema needed).

## Conclusion
One paragraph + suggested next tutorial.

Internal linking: include 3-5 internal links per 1000 words to other
ToolPilot tutorials (use descriptive anchor text, not "click here").
Every article must link to at least one pillar page (n8n, MCP, or
automation comparisons) and one related tutorial. No orphan pages.
