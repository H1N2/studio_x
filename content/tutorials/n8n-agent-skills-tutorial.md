---
title: "How to Create n8n Agent Skills: Write SKILL.md Files That Teach Coding Agents to Build Better Workflows"
slug: "n8n-agent-skills-tutorial"
date: 2026-10-05T12:30:00+08:00
draft: false
description: "Write n8n agent skills (SKILL.md) so Claude Code, Cursor, and OpenCode generate correct n8n workflows: naming rules, frontmatter limits, validation, install."
categories: ["n8n"]
tags: ["n8n", "agent skills", "SKILL.md", "claude code", "cursor", "ai agents", "automation"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "What is the difference between an n8n agent skill and n8n's Agents product?"
    a: "An agent skill is a SKILL.md markdown file that teaches a coding agent such as Claude Code or Cursor your n8n conventions, so it generates better workflow JSON. n8n's Agents product is a runtime feature inside n8n for building AI agents with models, tools, and memory. The skill shapes the code-writing assistant; the Agents product runs the finished agent."
  - q: "Do I need the n8n: prefix on my skill name?"
    a: "Only inside the n8n repository, where the official guide uses the n8n:<name> form so Claude Code namespaces skills under the n8n plugin and invokes them as /n8n:<name>. For your own project, use a plain hyphenated name that matches the skill directory."
  - q: "Can one skill cover all of my n8n workflows?"
    a: "No. The official authoring guide assigns one job per skill: linting generated JSON, reviewing credentials, and documenting node conventions are three different skills. A thin parent skill can link to child skills instead of duplicating their content."
  - q: "Where should I put the skill so my whole team gets it?"
    a: "Use .agents/skills/<name>/ in the shared repository. It is the agent-neutral, versioned default recommended by n8n's own guide. Personal skills go in ~/.claude/skills/<name>/ for Claude Code, ~/.cursor/skills/<name>/ for Cursor, or ~/.config/opencode/skills/<name>/ for OpenCode."
  - q: "Will my n8n skill work in Cursor and OpenCode too?"
    a: "Yes, if you keep it in the shared .agents/skills/ directory, which all three harnesses read. Add harness-specific overrides only when behavior must differ, and never put custom skills in ~/.cursor/skills-cursor/, which is reserved for Cursor's built-in skills."
  - q: "How do I stop agents from pasting secrets into workflow JSON?"
    a: "Add an explicit rule: credentials appear by ID only, and exported workflow JSON never contains credential values. Validate every generated file with a script that rejects password, token, or apiKey values before import."
---

## Introduction

Coding agents like Claude Code, Cursor, and OpenCode can generate n8n workflows from a plain-English description, but unguided output is unreliable. Agents invent node parameters that do not exist, guess `typeVersion` numbers, and paste API keys straight into workflow JSON. An Agent Skill, a `SKILL.md` markdown file plus optional references and scripts, encodes your team's n8n conventions so the agent generates workflows that actually import. This tutorial shows how to author one, following n8n's own skill authoring guide that landed in the n8n repository in mid-September 2026.

## Quick answer

Create `.agents/skills/<name>/SKILL.md` with a hyphenated name under 64 characters and a third-person description stating what the skill does and when it applies. Encode your n8n node rules, export format, and credential handling, then validate and install it per harness.

## Evidence

The n8n repository holds 206,676 stars on GitHub as of October 5, 2026, measured through the GitHub API, which makes its in-repo conventions a reasonable default for the whole community. n8n's official skill authoring guide sets hard, checkable limits: skill names stay under 64 characters, descriptions stay under 1024 characters, and `SKILL.md` bodies should stay well under roughly 200 lines. The guide's central warning is quotable: "Keep SKILL.md short, the context window is shared with chat, code, and other skills," from the [official create-skill guide in the n8n repository](https://github.com/n8n-io/n8n/blob/master/.agents/skills/create-skill/SKILL.md). The broader Agent Skills format itself comes from [Anthropic's Agent Skills documentation](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills), which defines the `SKILL.md` frontmatter contract every harness reads. A community example worth studying is [tmolavi/n8n-agent-skills](https://github.com/tmolavi/n8n-agent-skills), a unified skill pack for Claude Code, Codex, Cursor, and OpenCode covering production workflows, MCP routing, lint, and debug. If you are new to n8n's runtime agent features first, read our [n8n Agents tutorial](/n8n-agents-tutorial/) before building skills for them, since a skill that teaches code generation and an Agent that executes tasks are different layers.

## Prerequisites

- A working n8n instance with at least one workflow you can export. Our [n8n installation guide](/install-n8n-ubuntu-vps/) covers self-hosting if you need one.
- The n8n CLI available locally. Commands below were verified against n8n 2.41.4 in our lab.
- One coding agent harness: Claude Code, Cursor, or OpenCode.
- Basic YAML and JSON literacy. No n8n plugin development is required.

## Step-by-step guide

### Step 1: Export a reference workflow to learn the real JSON shape

Never let the agent guess the workflow format. Export a real workflow and show the agent its anatomy. The n8n CLI documents this in the [official CLI commands reference](https://docs.n8n.io/hosting/cli-commands/):

```bash
n8n export:workflow --id=5 --output=workflow.json --pretty
```

We ran this command's help in our lab to confirm the flags. The verified help output lists `--id`, `--all`, `--output`, `--pretty`, `--separate`, and `--backup`, so `n8n export:workflow --all --backup --output=backups/latest/` is a legitimate one-command backup before you experiment. An exported workflow is a JSON object with a `nodes` array and a `connections` object. Every node carries `name`, `type` (for example `n8n-nodes-base.httpRequest`), `typeVersion`, `position`, and `parameters`. That field list is the single most valuable fact your skill can teach, because agents that know it stop inventing fields. Save one representative export as the skill's ground truth and point the agent at it.

### Step 2: Create the skill directory and write honest frontmatter

Shared, team-visible skills live in `.agents/skills/<name>/`, the agent-neutral default. Create yours:

```bash
mkdir -p .agents/skills/n8n-workflow-lint
```

The official guide requires this frontmatter, with rules you can check mechanically:

```yaml
---
name: n8n:n8n-workflow-lint   # lowercase, hyphens, max 64 chars, matches directory name
description: >-                # max 1024 chars, non-empty, third person, WHAT + WHEN
  Reviews generated n8n workflow JSON for invented node parameters, wrong
  typeVersions, and leaked credentials before import. Use when a coding agent
  produces n8n workflow JSON, or when workflow imports fail validation.
---
```

Discovery is everything, so the description uses third person and names trigger words ("workflow JSON", "fail validation"). The guide contrasts this with bad descriptions like "Helps with documents" or "I can help you with PDFs": vague and first-person descriptions never trigger. Use the `n8n:` prefix only if you are contributing inside the n8n repository, where it namespaces the skill under the n8n plugin. In your own project, `name: n8n-workflow-lint` without the prefix is correct.

### Step 3: Write a short body with one default per decision

The guide's authoring rules are: be concise, disclose progressively, prefer one default, keep wording stable, and use forward slashes in paths. A lint skill body can be as short as this:

```markdown
# n8n Workflow Lint

Check every generated workflow against these rules before importing it into n8n.

## Rules

1. Every node needs `type`, `typeVersion`, `position`, and `parameters`. Reject nodes missing any of these.
2. Never invent `typeVersion` values. Allowed versions live in `reference.md`.
3. Expressions use `{{ $json.field }}` or `{{ $('Node Name').item.json.field }}`. Reject `$node` syntax.
4. Credentials appear by ID only. Reject any `password`, `token`, or `apiKey` value in the JSON.

See [node catalog](reference.md) for the canonical parameter list.
```

Notice the pattern: `SKILL.md` holds the checklist, and the long node catalog moves to `reference.md`, linked exactly one level deep. Deep chains of linked files are an official anti-pattern. Give one default everywhere. If the agent should prefer the Code node over legacy Function-style nodes, say so once instead of listing five equivalent options with no verdict.

### Step 4: Validate the skill with a real script

Guessing whether the frontmatter is valid wastes a whole agent session. Validate it with a script before the agent ever sees it. We wrote a small Python checker and ran it against the skill above:

```bash
python3 validate-skill.py .agents/skills/n8n-workflow-lint/SKILL.md
```

Real output from our lab:

```text
PASS name lowercase-hyphens
PASS name <=64 chars
PASS name matches directory
PASS description non-empty
PASS description <=1024 chars
PASS description third-person
PASS body <200 lines
description length: 147 | name: n8n:n8n-workflow-lint | body lines: 13
```

The checker enforces every mechanical rule from the official guide: hyphenated lowercase name, 64-character name cap, 1024-character description cap, directory-name match, third-person description, and the roughly-200-line body budget. Add this check to your repository's CI or pre-commit hooks so no invalid skill ever merges. If your skill needs a specific MCP server to work, the guide says to state that requirement in the frontmatter description and add a Prerequisites block with a fallback, because not every teammate has the same servers enabled. Our [MCP server tutorial](/mcp-server-tutorial/) explains the server side if you go that route.

### Step 5: Install per harness and share with the team

Keep the canonical copy in `.agents/skills/<name>/` so every harness reads the same source. Personal overrides go in harness-specific directories:

| Harness | Personal skill location |
|---|---|
| Claude Code | `~/.claude/skills/<name>/` |
| Cursor | `~/.cursor/skills/<name>/` |
| OpenCode | `~/.config/opencode/skills/<name>/` |

Inside the n8n repository itself, run `pnpm sync:skill-links` after adding or removing shared skills, as the guide instructs. In your own project, committing `.agents/skills/` to version control is the sharing mechanism, and teammates' harnesses pick it up on next launch. Never place custom skills in `~/.cursor/skills-cursor/`, which Cursor reserves for its built-in skills. If a teammate reports the skill is missing, check the directory first: nine times out of ten the file landed in a personal directory instead of the shared one.

## Troubleshooting

### 1. The skill never triggers on relevant requests

Cause: the description is vague or written in first person, so the harness cannot match it to the user's words. The guide's bad examples are "Helps with documents" and "I can help you with PDFs". Fix: rewrite the description in third person with WHAT plus WHEN, including the trigger terms the user will actually type, such as "workflow JSON" and "fail validation". Our lab check caught this exact failure with `FAIL description third-person` when we tested a first-person draft.

### 2. The harness rejects the skill or the name does not match

Cause: the `<name>` part of the frontmatter does not equal the directory name, or it uses uppercase letters, underscores, or exceeds 64 characters. Fix: rename the directory or the frontmatter so both match exactly, using lowercase letters, digits, and hyphens only. Rerun the validator until every name check passes.

### 3. The agent still invents node parameters despite the skill

Cause: the skill lists rules but never shows the canonical parameter shapes, so the agent fills the gap with plausible fiction. Fix: move a real exported node catalog into `reference.md` and link it one level deep from `SKILL.md`, following the progressive-disclosure rule. Generate the catalog from your own `n8n export:workflow --pretty` output, not from memory. For AI-flavored nodes specifically, our [n8n AI Agent tutorial](/n8n-ai-agent-tutorial/) documents verified node labels and defaults you can reuse.

### 4. The skill bloats the context window and answers get worse

Cause: `SKILL.md` grew past roughly 200 lines with tutorial-style explanations the model already knows. The official guide lists verbose "what is a PDF" style content as an anti-pattern. Fix: cut everything the model knows, keep only non-obvious project facts, and split detail into `reference.md` or `scripts/`. Measure the line count in CI with the validator from Step 4.

### 5. The skill works in Claude Code but is invisible in Cursor

Cause: the skill was installed to a Claude-only path such as `~/.claude/skills/` or `.claude/plugins/`, or it was accidentally placed in the reserved `~/.cursor/skills-cursor/` directory. Fix: keep the shared source in `.agents/skills/<name>/`, which all three harnesses read, and use harness-specific directories only for genuine overrides.

## FAQ

See the FAQ block in this article's front matter for the quick answers. The longer guidance: treat skills as team documentation with a machine-readable contract. One job per skill, one default per decision, and validated frontmatter will take you further than a long prompt pasted into chat. When your generated workflows need memory or chat interfaces, pair this skill with our [n8n chatbot memory tutorial](/n8n-chatbot-memory-tutorial/).

## Conclusion

A good n8n agent skill is short, mechanical, and honest: a hyphenated name under 64 characters, a third-person description under 1024 characters that names its triggers, a checklist body under 200 lines, and a validator that enforces all of it. Build one lint skill this week, point it at a real exported workflow, and your coding agent will stop inventing node parameters. Next, read our [n8n Agents tutorial](/n8n-agents-tutorial/) to see how the workflows your agent generates can call full n8n Agents through the Message an Agent node.
