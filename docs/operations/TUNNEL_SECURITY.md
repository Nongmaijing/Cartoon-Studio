# Tunnel Security — Current State and Plan

## Why this matters

The Cartoon Studio MCP can start agents and mutate production data. A public
no-auth Cloudflare tunnel therefore grants anyone with the URL the same power as
the local user until the tunnel is stopped.

## Live state (before controlled restart)

| Surface | Port | Auth | Expiry | Notes |
|---|---|---|---|---|
| Cartoon Studio MCP tunnel | 8020 | none | legacy none | Started before TTL hardening |
| Standalone OpenCode bridge | 8031 | none | legacy none | Adopted legacy tunnel |
| Local bearer MCP | 8030 | bearer | n/a | Not tunnelled |

Existing ChatGPT connectors use the no-auth URLs. They must keep working until a
replacement is verified.

## Code changes in this pass

### Cartoon Studio tunnel

`backend/app/services/mcp_tunnel_service.py`

- `normalize_ttl_minutes` no longer returns `0`.
- Zero, negative and invalid values fall back to 30 minutes.
- Minimum 5 minutes, maximum 480 minutes.
- Legacy tunnels without `expires_at` are adopted with a bounded expiry the next
  time status is read by the new code.
- The existing expiry task stops the tunnel and restores the local bearer MCP.

### Standalone OpenCode bridge

`bridge/tunnel.py`

- Default TTL 60 minutes, hard maximum 480 minutes.
- `start_tunnel` accepts `ttl_minutes`; zero is treated as the default.
- `/api/tunnel/start` accepts `{"ttl_minutes": ...}`.
- Legacy tunnels without expiry are adopted with a bounded expiry.
- The UI offers 30 min to 8 h and no longer offers "Never auto-stop".

## Auth model

ChatGPT custom MCP connectors cannot send a static bearer token. The current
no-auth mode is therefore kept **only** for short, explicit ChatGPT sessions.

- Bearer-capable local clients should use port 8030.
- Do not set `BRIDGE_TOKEN` while the ChatGPT tunnel is expected to work.
- The tunnel is a temporary session, not a permanent deployment.

## Controlled rollout

1. Finish the current character generation batch.
2. Stop the studio and bridge tunnels from the UI.
3. Restart the backend and bridge so the TTL code is live.
4. Verify:
   - studio status reports `ttl_minutes` and `remaining_seconds`;
   - starting with `ttl_minutes: 0` returns the default, not an infinite tunnel;
   - disconnecting stops the public URL and restores the bearer MCP;
   - the MCP exposes the expected 58 studio tools.
5. Reconnect ChatGPT with a 30–60 minute session.
6. Only then consider OAuth / Cloudflare Access if the connector supports it.

## Do not do

- Do not revoke active MCP tokens or shut down the public URL before the
  replacement connector is verified.
- Do not expose 8030 (bearer) through a tunnel.
- Do not leave a tunnel running overnight.
