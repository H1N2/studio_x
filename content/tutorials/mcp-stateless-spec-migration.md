---
title: "MCP Stateless Spec Migration Guide: Move Your Server to 2026-07-28 Without Downtime"
slug: "mcp-stateless-spec-migration"
description: "Migrate your MCP server to the 2026-07-28 stateless spec: drop Mcp-Session-Id, add server/discover, send per-request _meta, and regression-test each step."
date: 2026-10-04
draft: false
categories: ["MCP"]
tags: ["mcp", "model-context-protocol", "stateless", "migration", "spec", "server-discover", "tutorial"]
author: "ToolPilot Team"
toc: true
faq:
  - q: "When must I migrate to the 2026-07-28 stateless wire?"
    a: "You are not forced to migrate on a fixed date. The spec's deprecation policy keeps deprecated features in the specification for at least twelve months (or at least ninety days under the expedited-removal exception) before they can be removed. Roots, Sampling, Logging, and Dynamic Client Registration, all deprecated in 2026-07-28, cannot be removed before the first revision released on or after 2027-07-28. The legacy HTTP+SSE transport becomes eligible for removal three months after SEP-2596 reaches Final. New clients will increasingly expect the stateless wire, so plan the migration now even though the old wire is not dead yet."
  - q: "Does going stateless kill streaming and SSE?"
    a: "No. What disappeared is the protocol-level session and the initialize handshake, not streaming itself. Server-initiated requests were replaced by multi-round-trip requests (MRTR, SEP-2322), and notification plus subscription mechanisms remain available. Your server can still push progress updates; it just no longer needs a sticky session to do it."
  - q: "Which SDK version do I need for the stateless wire?"
    a: "All four Tier 1 SDKs, TypeScript, Python, Go, and C#, speak 2026-07-28 as of the release day, according to the official release announcement. The TypeScript SDK ships era-tagged example stories including dual-era and stateless-legacy, and the Python SDK ships stateless_legacy and dual_era stories. Use those examples as the reference for serving both wires during your transition."
  - q: "Do I need OAuth 2.1 as part of this migration?"
    a: "Only if your server is authenticated. Anonymous servers can skip authorization entirely. If you do use auth, the 2026-07-28 authorization spec is based on OAuth 2.1 draft-ietf-oauth-v2-1-13, requires you to publish RFC 9728 Protected Resource Metadata, and deprecates Dynamic Client Registration in favor of Client ID Metadata Documents. Clients must send the RFC 8707 resource parameter and you must validate a present iss claim per RFC 9207."
  - q: "What happens to my 2025-era clients after I migrate?"
    a: "They will fail at the initialize handshake because the stateless server no longer implements it. Serve both wires during the transition, measure the share of traffic still arriving without per-request _meta, and sunset the legacy wire once that share is negligible."
  - q: "Should MCP Apps be part of the same migration?"
    a: "Treat them as separate work. MCP Apps is an optional extension (io.modelcontextprotocol/ui) that lets tools return interactive HTML interfaces rendered in a sandboxed iframe. Migrate the transport first, confirm everything is stable, then add Apps, Tasks, or caching as independent upgrades."
---

## Introduction

If you run an MCP server built on the 2025-era Streamable HTTP transport, your request lifecycle starts with an `initialize` handshake and depends on a sticky `Mcp-Session-Id` header for everything that follows. On 28 July 2026 the Model Context Protocol shipped revision 2026-07-28, which deletes both of those concepts and makes every request self-describing. MCP co-creator David Soria Parra calls it "[MCP's] most important [release] since remote MCP first launched." This guide migrates your server to the new stateless wire: what to delete, what to implement (`server/discover`, per-request `_meta`, the new headers), how to keep 2025-era clients working during the transition, and how to regression-test the whole thing. It is written for developers who already operate an MCP server over Streamable HTTP. If you have never built one, start with [our Model Context Protocol pillar guide](https://www.161808.xyz/mcp-server-tutorial/) first.

## Quick answer

Migrate your MCP server to the 2026-07-28 stateless spec by deleting Mcp-Session-Id handling, implementing the mandatory server/discover RPC, attaching protocolVersion and clientCapabilities in every request's _meta, and regression-testing old clients with dual-era serving.

## Why the change happened (evidence)

The scale of MCP adoption is what made sticky sessions untenable. The official release announcement for 2026-07-28 reports that the Tier 1 SDKs see "close to half-a-billion downloads a month," with both the TypeScript and Python SDKs crossing the 1 billion total downloads threshold, as of July 2026. Agent traffic is no longer a side channel either: Honeycomb's Director of AI Strategy Austin Parker reports that "nearly 20% of all monthly interactive queries are now made by agents," and Figma and Cloudflare are shipping day-zero support. Cloudflare's Senior Director of Product Management Brendan Irvine-Broque puts it plainly: "Cloudflare's Agents SDK supports the spec from day zero."

The performance argument comes from early migrators. Manufact's CTO Enrico Toniato reports that the new SDK v2 "helped us cut the package size by around 83% while making it 25% faster." That matches the engineering logic of the revision: a stateless request can be routed to any replica, cached by intermediaries, and retried without session recovery. SEP-2567 removes protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP transport, and SEP-2575 removes the `initialize` and `notifications/initialized` handshake, replacing it with per-request `_meta` carrying the protocol version and client capabilities. The full list of changes is published in the [official 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), and the revision lifecycle is documented on the [official versioning page](https://modelcontextprotocol.io/specification/versioning).

## Prerequisites

- An MCP server speaking the 2025-era Streamable HTTP wire (protocol revisions 2025-06-18 or 2025-11-25), with a staging instance you can break.
- A Tier 1 SDK that speaks 2026-07-28 (TypeScript, Python, Go, or C#), or a raw HTTP handler you control. All four Tier 1 SDKs support the revision as of release day.
- A test client that can send raw JSON-RPC over HTTP with custom headers (curl is enough).
- Familiarity with your current session storage, your auth setup if any, and your load balancer's sticky-session configuration.

## Step 0: Map the old wire to the new wire

Before touching code, map every stateful assumption in your server to its stateless replacement. The table below is the migration in one glance.

| Old wire (2025-06-18 / 2025-11-25) | New wire (2026-07-28) |
|---|---|
| `initialize` then `notifications/initialized` handshake | Handshake removed (SEP-2575); no per-connection setup at all |
| `Mcp-Session-Id` header returned at initialize, required on every later request | Header removed (SEP-2567); ignore it if clients still send it |
| Protocol version negotiated once during initialize | Every request carries `_meta` with `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities` |
| Client identified implicitly by its session | Optional self-identification via `_meta` key `io.modelcontextprotocol/clientInfo` |
| Server identity announced in the initialize result | Server identity echoed in every result's `_meta` key `io.modelcontextprotocol/serverInfo` |
| Session state in Redis or memory keyed by session id | Delete it; any replica can serve any request |
| Server-initiated requests over the session | Replaced by multi-round-trip requests (MRTR, SEP-2322) |
| `tools/list`, `resources/list`, `prompts/list` could vary per connection | List endpoints no longer vary per connection; add caching with `ttlMs` and `cacheScope` (SEP-2549) |

The audit is mechanical: search your codebase for `session`, `initialize`, `Mcp-Session-Id`, and `notifications/initialized`. Every hit is either deleted or replaced by the steps below.

## Step 1: Implement the mandatory `server/discover` RPC

The new handshake-free world still needs one capability exchange, and that is `server/discover`. It is a mandatory RPC: your server must implement it, and it returns the server's supported protocol versions, capabilities, and identity in a single request. Calling it is optional for clients. On Streamable HTTP, the negotiated version is also mirrored in the `MCP-Protocol-Version` response header.

A discovery call looks like this on the wire:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: server/discover
Mcp-Name: discover

{"jsonrpc": "2.0", "id": 1, "method": "server/discover"}
```

The response carries your supported protocol versions (serve the new wire and, during transition, the old one), your capabilities, and your server identity. A client that does not recognize a version you list can use this response to negotiate down instead of failing blindly. Note the two request headers `Mcp-Method` and `Mcp-Name`: SEP-2243 requires them on Streamable HTTP requests, and they give your routing and observability a free gift, because you can route and log without parsing the JSON body.

## Step 2: Read `_meta` on every request, echo `serverInfo` in every result

This is the heart of the migration. Where the old server trusted the session, the new server reads the request. Every JSON-RPC request now carries a `_meta` object whose keys are namespaced exactly like this:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "search_docs",
    "arguments": {"q": "stateless transport"},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": ["io.modelcontextprotocol/tasks"]
      },
      "io.modelcontextprotocol/clientInfo": {"name": "acme-agent", "version": "2.3.0"}
    }
  }
}
```

Three things changed in this one payload. First, the protocol version travels with the request instead of being negotiated once per connection. Second, client capabilities, including which extensions the client speaks, travel with the request, which is how your server learns the client supports the [Tasks extension](https://modelcontextprotocol.io/extensions/tasks/overview) without any earlier exchange. Third, `clientInfo` is optional self-identification, useful for analytics and rate limiting now that there is no session to key on.

Your request handler needs a version gate at its top. Read `io.modelcontextprotocol/protocolVersion` from `_meta` (falling back to the `MCP-Protocol-Version` header if a proxy stripped it is a mistake, so fix the proxy instead, see Troubleshooting). If the requested version is one you serve, proceed. If it is not, return a JSON-RPC error that names the versions you do serve, so the client can retry against your `server/discover` response instead of guessing.

On the response side, attach your server identity to every result's `_meta` under `io.modelcontextprotocol/serverInfo`. Clients use this to attribute capabilities to a specific server instance in multi-server setups, the job the old initialize result used to do.

## Step 3: Delete session state

This step is deletion, and deletion is the feature. Remove:

- Issuance and parsing of the `Mcp-Session-Id` header. Old clients may still send it; ignore it rather than rejecting the request.
- The session store itself: the Redis map or in-memory dictionary keyed by session id, its TTL refresh logic, and its eviction code.
- Sticky-session configuration on your load balancer. A stateless request carries everything the server needs, so round-robin across replicas is now correct by construction. Verify your LB is not still pinning clients, or you will pay for affinity you no longer need.
- Any per-connection SSE subscription map tied to sessions. Progress and notification delivery moves to the subscription model described in the Tasks and MRTR material, not to a socket held open per client.

The practical test that you are done: kill any single replica mid-traffic and confirm no client notices. If any client holds a session reference, the deletion is incomplete.

## Step 4: Serve the new required headers

On every Streamable HTTP response, set `MCP-Protocol-Version` to the negotiated version (for 2026-07-28 requests, that is `2026-07-28`). This header is how intermediaries, caches, and debugging tools see the wire version without parsing bodies. On the request side, enforce SEP-2243: expect `Mcp-Method` and `Mcp-Name` headers. Log them; they turn your access logs into an MCP-aware audit trail with zero body parsing.

A minimal smoke test with curl exercises the whole new contract:

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: server/discover" \
  -H "Mcp-Name: discover" \
  -d '{"jsonrpc":"2.0","id":1,"method":"server/discover"}' | head -c 600
```

A 2026-07-28 server answers with its supported versions, capabilities, and identity. A legacy-only server answers with an error, which is also the signal your dual-era routing needs in Step 6.

## Step 5: Update authorization if you use it

If your server is anonymous, skip this step. If it is authenticated, the 2026-07-28 revision moves authorization to OAuth 2.1. The [official authorization spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) bases the mechanism on OAuth 2.1 IETF draft-ietf-oauth-v2-1-13, and the concrete requirements are: publish RFC 9728 Protected Resource Metadata so clients can discover your authorization server; expect clients to send the RFC 8707 `resource` parameter; move off Dynamic Client Registration, which is deprecated, onto Client ID Metadata Documents; and validate a present `iss` claim against the recorded issuer per RFC 9207. Do this as part of the same migration, because auth metadata is served from the same HTTP surface you are already rewriting.

## Step 6: Serve both wires during the transition

You cannot migrate every client at once, and the spec does not ask you to. The recommended pattern is dual-era serving: one deployment that speaks the 2025-era stateful wire to old clients and the 2026-07-28 stateless wire to new ones, distinguished by the request's `_meta` and headers. The SDKs ship reference material for exactly this. The TypeScript SDK's example stories include `dual-era/` and `stateless-legacy/`; the Python SDK ships `dual_era/` and `stateless_legacy/` stories, and the Python story notes that the stateless side is a one-liner: `streamable_http_app(stateless_http=True)`.

Run the dual-era deployment for at least one full client release cycle and log the share of requests arriving without per-request `_meta`, which is your legacy-traffic metric. When that share rounds to zero for a sustained period, remove the legacy path. The deprecation policy gives you cover: deprecated features remain in the specification for at least twelve months, or at least ninety days under the expedited-removal exception, before they become eligible for removal, and the deprecated-features registry pins Roots, Sampling, Logging, and Dynamic Client Registration to earliest removal in the first revision released on or after 2027-07-28. The legacy HTTP+SSE transport becomes eligible for removal three months after SEP-2596 reaches Final. Nothing in the old wire vanishes overnight; your schedule can be driven by your traffic data, not by fear.

## Step 7: Add the new capabilities as independent upgrades

Once the stateless transport is stable, three optional upgrades become cheap because the protocol now supports them natively.

First, Tasks (SEP-2663, extension id `io.modelcontextprotocol/tasks`). Tools that take minutes, video generation, bulk queries, long analyses, can now return a task handle instead of blocking. The lifecycle is `working` (in progress), `input_required` (the server needs client input, enabling human-in-the-loop), then a terminal state: `completed` with the result, `failed` with a JSON-RPC error, or `cancelled`. Clients poll `tasks/get`, send input with `tasks/update`, cancel with `tasks/cancel`, and receive status pushes over `notifications/tasks` with `subscriptions/listen`. Negotiation rides the existing per-request `_meta` you built in Step 2, with servers advertising support in `server/discover`.

Second, caching (SEP-2549): list endpoints can declare `ttlMs` and `cacheScope`, so intermediaries can finally cache `tools/list` responses that no longer vary per connection.

Third, [MCP Apps](https://modelcontextprotocol.io/extensions/apps/overview) (extension id `io.modelcontextprotocol/ui`): tools can return interactive HTML interfaces, dashboards, forms, data visualizations, that render directly in the chat inside a host-controlled sandboxed iframe. The tool declares `_meta.ui.resourceUri` pointing at a `ui://` resource, the host fetches the HTML, and the app talks to the host over `postMessage`. The sandbox guarantees the app cannot access the parent page, steal cookies, or escape its container. Host support already includes Claude, Claude Desktop, VS Code GitHub Copilot, Microsoft 365 Copilot, Goose, Postman, MCPJam, and Archestra.AI, with an `@modelcontextprotocol/ext-apps` npm package for builders.

Do these one at a time. A migration that changes the transport, adds Tasks, and ships interactive UIs in the same deploy is how you get a rollback with three suspects.

## Troubleshooting

**Legacy clients fail immediately after cutover with initialize errors.** You migrated the server but not the fleet. Keep a dual-era deployment serving the 2025-era wire alongside the stateless wire, keyed on the presence of per-request `_meta`, and track the legacy-traffic share in your logs. Reference the SDK example stories (`dual-era/` and `stateless-legacy/` in the TypeScript SDK, `dual_era/` and `stateless_legacy/` in the Python SDK) instead of hand-rolling the routing. Sunset the legacy path only when legacy traffic is negligible for a full release cycle.

**Requests arrive without `MCP-Protocol-Version` even though clients send it.** A proxy, CDN, or API gateway between the client and your server is stripping non-standard headers. Allowlist `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` on every intermediary, and do not silently fall back to the `_meta` protocol version as a permanent fix; the header is part of the contract and intermediaries need it for caching and debugging.

**Push updates stopped working after you deleted sessions.** Server-initiated requests over a session were removed from the protocol; the replacement is multi-round-trip requests (MRTR, SEP-2322), and status push uses `notifications/tasks` with `subscriptions/listen`. If your tool relied on pushing progress down a held-open SSE connection, rewrite it against Tasks or the subscription model rather than reintroducing session state through the back door.

**Memory or Redis usage keeps growing from the old session map.** The deletion in Step 3 was incomplete: a TTL refresh path, an eviction worker, or a middleware still references the session store. Search for `Mcp-Session-Id` case-insensitively across the whole codebase and the deployment config. Meanwhile, old clients may still send the header; ignore it, do not reject the request, and let dual-era routing handle those clients.

**Authenticated clients break with token errors after the migration.** You are likely still on Dynamic Client Registration, which the 2026-07-28 revision deprecates. Publish RFC 9728 Protected Resource Metadata, migrate to Client ID Metadata Documents, require the RFC 8707 `resource` parameter from clients, and validate a present `iss` claim per RFC 9207. If you need a reference implementation checklist, the patterns in [our Claude Code MCP setup guide](https://www.161808.xyz/claude-code-mcp-setup/) show authenticated server wiring on a real host; you will update the auth layer to the OAuth 2.1 profile.

## FAQ

See the FAQ in the page front matter; it is rendered as the page's FAQ section for readers and AI citations.

## Conclusion

The 2026-07-28 migration is mostly deletion: the initialize handshake, the session store, and the sticky load-balancer rules go away, replaced by per-request `_meta`, the `MCP-Protocol-Version` header, and the mandatory `server/discover` RPC. Serve both wires while your clients catch up, then layer on Tasks, caching, and MCP Apps. The deprecation policy gives you at least twelve months of runway, so set the schedule from your traffic data. Building a fresh server instead? Work through [our Python MCP server tutorial](https://www.161808.xyz/build-mcp-server-python/) next, then connect it to real hosts with [our Claude Desktop guide](https://www.161808.xyz/connect-mcp-server-to-claude-desktop/).
