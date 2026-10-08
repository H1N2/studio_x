---
title: "Meta WhatsApp Business MCP Server Setup: Let an AI Agent Onboard Your Business Number"
slug: "meta-whatsapp-mcp-server-setup"
date: 2026-10-06T06:30:00+08:00
draft: false
description: "Set up Meta's WhatsApp Business Tools MCP server: connect Claude, Codex, or ChatGPT via OAuth and onboard numbers, templates, and webhooks by chat."
categories: ["MCP", "AI Agents"]
tags: ["whatsapp", "mcp", "model-context-protocol", "meta", "claude", "codex", "ai agents", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "Is the WhatsApp Business Tools MCP server free to use?"
    a: "Meta has not announced separate pricing for the MCP server itself. It connects to the WhatsApp Business Platform, where messages remain billable under Meta's per-message pricing. The server is in beta and rolling out gradually, so availability varies by account."
  - q: "Can the AI agent read my existing customer conversations?"
    a: "The server acts on the businesses and apps you select during OAuth consent, with scopes business_management, whatsapp_business_management, and whatsapp_business_messaging. It manages setup and configuration, not your chat history. You can review or revoke its access at any time at facebook.com > Settings > Business Integrations."
  - q: "Does it work with Cursor as well as Claude and ChatGPT?"
    a: "Meta's announcement names Claude, Cursor, Codex, and ChatGPT as compatible agents. Any client that supports remote MCP servers over Streamable HTTP can connect to https://mcp.facebook.com/whatsapp_business_tools; clients that only support local stdio servers can use the mcp-remote bridge."
  - q: "What should I do if the server is not available on my account yet?"
    a: "Meta says the server is rolling out gradually and may not be available to everyone yet. Keep using the manual Cloud API onboarding in the meantime, and re-check the official documentation page, since the beta tool set can change without notice."
  - q: "Can I use it for production messaging at scale?"
    a: "It is an onboarding and management interface, not a messaging pipeline. For production traffic, ask the agent for a system user token link via whatsapp_biz_system_user_token, generate a permanent token in Business Settings, and call the WhatsApp Cloud API directly from your own code."
  - q: "How do I revoke the agent's access?"
    a: "Open facebook.com > Settings > Business Integrations and remove the WhatsApp Business Tools integration. Revoking stops all tool access immediately, because every call authenticates through your Meta developer account over OAuth."
---

## Introduction

Setting up WhatsApp Business messaging used to mean four open tabs: the Meta Developer Console, Business Manager, the API reference, and your code editor. On September 15, 2026, Meta shipped the WhatsApp Business Tools MCP server, which hands that entire sequence to an AI agent. This tutorial shows you how to connect the server to Claude Code, Claude Desktop, Codex, or ChatGPT, authenticate with OAuth, and onboard a phone number, create templates, and configure webhooks by describing what you want in chat.

## Quick answer

Add Meta's WhatsApp Business Tools MCP server (https://mcp.facebook.com/whatsapp_business_tools) to Claude, Codex, or ChatGPT, sign in with your Meta developer account over OAuth, then ask the agent to onboard numbers, verify them, and manage templates.

## Evidence

The scale of the platform explains why Meta built this. WhatsApp has more than 3 billion monthly active users, a figure CEO Mark Zuckerberg confirmed on Meta's Q1 2025 earnings call in April 2025, putting it alongside Facebook as one of the only apps ever to reach that scale. Meta also said in June 2023 that the standalone WhatsApp Business app had passed 200 million monthly users, so the business messaging surface the agent manages is enormous.

Meta's Product Marketing Manager Zoë Lieberman framed the shift in the official announcement: "You describe what you want; your agent handles the accounts, numbers, templates, and API calls." She also stressed the guardrail that matters most to administrators: "Before any tool runs, the server confirms you're an admin of the app, resolves the attached business, and verifies your Terms of Service are signed."

Two facts from Meta's own documentation shape how you should treat this server. First, it is in beta and rolling out gradually, and Meta warns that the interface and tool set may change. Second, every tool acts as you, on the apps and businesses you administer, which is why the prerequisites below are not optional. The setup reference for this tutorial is the [official WhatsApp Business Tools MCP documentation](https://developers.facebook.com/documentation/mcp/whatsapp-business-tools-mcp), and the webhook steps follow Meta's [webhooks configuration guide](https://developers.facebook.com/docs/graph-api/webhooks/getting-started).

## Prerequisites

- A Meta developer account with admin access to a business (the MANAGE role) that you want to onboard.
- A WhatsApp-enabled app that you administer, connected to that business. The app needs the WhatsApp Business Messaging use case, or the WhatsApp product on an older app.
- Accepted WhatsApp Business Cloud API Terms of Service for that business. Messaging and phone-number registration stay blocked until an admin accepts them.
- One AI agent client that supports remote MCP servers: Claude Code, Claude Desktop, Codex, or ChatGPT. Clients that only speak local stdio need the `mcp-remote` bridge.
- A phone number that can receive an SMS or voice call and is not already registered on consumer WhatsApp. The verification code goes to this number.

## Step 1: Confirm the three prerequisites before touching the agent

Open the Meta Developer Console and check three things in this order: you hold the MANAGE role on the business, you are an admin of a WhatsApp-enabled app attached to that business, and the business has accepted the WhatsApp Business Cloud API Terms of Service. The MCP server checks these before almost every tool, and when one is missing the tool returns an actionable error that names the missing item and links to the page where you fix it. Doing this check manually first saves you a round trip through the agent.

## Step 2: Add the remote server to your agent client

The server is remote, so there is nothing to install. Use the section for your client.

**Claude Code** runs one command:

```bash
claude mcp add --transport http whatsapp_business_tools https://mcp.facebook.com/whatsapp_business_tools
```

Then open a session, run `/mcp`, and select `whatsapp_business_tools` to authenticate.

**Claude Desktop** opens Settings, then Connectors, then Add custom connector, with Name `WhatsApp Business Tools` and URL `https://mcp.facebook.com/whatsapp_business_tools`.

**Codex App** opens Settings (the gear icon, bottom left), then MCP Servers, then Add servers. Choose Streamable HTTP and set Name to `WhatsApp Business Tools`, URL to `https://mcp.facebook.com/whatsapp_business_tools`, and Authentication to OAuth. Click Authenticate and complete the OAuth sign-in.

**ChatGPT** opens Settings, then Plugins, then Browse plugins. Click the + in the top right to add a new plugin, set Name to `WhatsApp Business Tools`, URL to `https://mcp.facebook.com/whatsapp_business_tools`, and Authentication to OAuth. Save the plugin and complete the OAuth sign-in.

If your client only supports local stdio servers, run the `mcp-remote` bridge, which proxies this remote server over stdio. The OAuth flow is identical afterwards.

## Step 3: Complete the OAuth sign-in and grant scoped consent

Many clients start the OAuth flow automatically when the server is added; others need a Connect or Authenticate click first. Your browser opens to sign in with your Meta account. If it does not open, copy the link your client prints and open it manually.

On the consent screen, select exactly the businesses and WhatsApp-enabled apps you want the agent to touch. The server requests three scopes: `business_management` to discover and act on your selected businesses, `whatsapp_business_management` to manage accounts, numbers, templates, and webhooks, and `whatsapp_business_messaging` to send messages from registered numbers. Granting the narrowest set that covers your task is good practice; you can re-run consent later to widen it.

Two things to remember. First, you must repeat the sign-in flow every time you restart the client, because the session does not persist across restarts. Second, you can review or revoke access at any time at facebook.com, under Settings and then Business Integrations.

## Step 4: Verify the agent can see the tools

Restart your IDE or agent client, then ask the agent to list the tools it has from the `whatsapp_business_tools` server. Every tool carries the `whatsapp_biz_` prefix. Confirm with a low-risk read: ask it to list the businesses you administer with `whatsapp_biz_businesses`. If the agent reports no tools or an authentication error, re-check the endpoint URL and confirm you finished the sign-in flow in step 3. A typical healthy session starts by listing businesses and picking one, since most tools are scoped to a business you administer.

## Step 5: Onboard and verify a phone number by chat

This is the sequence the announcement was built around. Give the agent one instruction at a time so you can confirm each result:

1. "Add the phone number +1 555 010 1234 to my WhatsApp account." The agent calls `whatsapp_biz_add_phone_number`.
2. "Send a verification code by SMS to this number." The agent calls `whatsapp_biz_send_verification_code`.
3. Read the code from the phone, then tell the agent: "Verify this number with code 482916." The agent calls `whatsapp_biz_verify_phone_number`.
4. "Register this number for messaging." The agent calls `whatsapp_biz_register_phone_number`, which registers the verified number so it can send and receive.

Ask the agent to list the numbers and their status with `whatsapp_biz_phone_numbers` afterwards. The status column shows the onboarding state, which is the fastest way to confirm the number is fully registered before you move on.

## Step 6: Create and inspect message templates

Outside the 24-hour customer service window, businesses may only send approved templates, so templates are the next thing to set up. Ask the agent to list what exists with `whatsapp_biz_list_templates`, then create one: "Create a marketing template named order_update in en_US." The agent calls `whatsapp_biz_create_template` and returns the approval status. Template approval is a Meta review step, not instant, so ask the agent to check the status again with `whatsapp_biz_get_template` before you rely on the template. Update and delete work the same way through `whatsapp_biz_update_template` and `whatsapp_biz_delete_template`.

## Step 7: Configure webhooks for inbound events

Webhooks deliver inbound messages and status updates to your server. Tell the agent: "Configure webhooks for this business with callback https://example.com/webhook." The agent calls `whatsapp_biz_configure_webhooks`, which sets the callback URL and verify token for the WhatsApp topic and subscribes the allowed fields. Then ask it to subscribe the account: "Subscribe this WhatsApp account to webhooks," which calls `whatsapp_biz_subscribe_webhook` so the account's events actually flow to your app.

Your callback URL must be public HTTPS, and the verify token is a secret string you choose. During setup Meta sends a GET request to your callback with `hub.verify_token`; your endpoint must echo back `hub.challenge` only when the token matches. If verification fails, the agent's configure call succeeds but no events arrive, which is the classic silent failure to check first.

## Step 8: Send a test message and confirm delivery rules

Ask the agent: "Send the order_update template to +1 555 010 9999 from this number." The agent calls `whatsapp_biz_send_message` and, per the documented behavior, confirms the target with you before sending. Two delivery rules govern what happens next. Free-form text is only delivered inside the 24-hour customer service window after the customer's last message; outside that window you must use an approved template. Billable messages also require a payment method on the account, which the agent can set up with `whatsapp_biz_configure_payments`.

## Step 9: Generate a permanent token link for direct API use

The MCP server is an onboarding interface, not a production pipeline. When you are ready to call the Cloud API from your own code, ask the agent: "Give me a link to create a system user access token for this business." The agent calls `whatsapp_biz_system_user_token` and returns a deep link to the System Users page in Business Settings, where token generation happens securely. Select a system user, generate the token, and store it server-side. Also ask the agent to check business verification with `whatsapp_biz_verify_business`, since unverified businesses face messaging limits.

## Troubleshooting

**The agent reports no tools, or every call fails with an authentication error.** The usual cause is an incomplete OAuth flow, or a client restart after which the session expired. Re-check the endpoint URL character by character, then redo the sign-in from step 3. In Claude Code, run `/mcp` and select `whatsapp_business_tools` again. If the browser never opened during the first attempt, copy the link the client prints and open it manually.

**A tool returns a prerequisite error naming admin access, the app, or Terms of Service.** This is the server doing its job. The error names the missing item and links to the page that fixes it. Open the link, grant yourself the MANAGE role on the business, confirm you are an admin of the WhatsApp-enabled app rather than only the business, and have a business admin accept the Cloud API Terms of Service. Messaging and phone-number registration stay blocked until the ToS step is done.

**The server does not appear, or the tool set looks different from this tutorial.** The server is in beta and rolling out gradually, and Meta warns the interface and tool set may change. Your account may simply not be in the rollout yet. Keep using the manual onboarding path from the [Cloud API get-started guide](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) and re-check the MCP documentation page later.

**The verification code never arrives at the phone.** The number must be able to receive SMS or a voice call, and it must not already be registered on consumer WhatsApp or another Cloud API account. Virtual numbers from some providers are silently filtered. Move the SIM to a real handset, request the code again with `whatsapp_biz_send_verification_code`, and enter it promptly, because codes expire.

**Webhooks are configured but no events arrive.** First check the callback verification handshake: your endpoint must return `hub.challenge` when `hub.verify_token` matches the token you set. Then confirm the account subscription with `whatsapp_biz_subscribe_webhook`; configuring the business callback alone does not deliver an account's events. Finally, confirm the callback URL is public HTTPS, since Meta will not call plain HTTP or localhost.

**A tool returns a rate-limit error.** Requests are rate limited per user per tool to protect the platform. Wait a short time and retry rather than hammering the call. If you hit limits during bulk template creation, space the creates out or batch them.

## Conclusion

The WhatsApp Business Tools MCP server turns a four-tab onboarding slog into a conversation: connect once over OAuth, then let the agent add numbers, verify them, build templates, and wire webhooks while you supervide. Keep the beta status in mind, grant the narrowest consent that covers the task, and revoke access from Business Integrations when the work is done. If you want the agent to run the finished integration instead of just setting it up, read the [n8n AI agent tutorial](https://www.161808.xyz/n8n-ai-agent-tutorial/) next, and the [MCP server tutorial](https://www.161808.xyz/mcp-server-tutorial/) if you plan to expose your own tools over the same protocol.
