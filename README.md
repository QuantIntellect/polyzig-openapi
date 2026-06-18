# PolyZig API & MCP Server

Public mirror of the OpenAPI 3.1 specification and Model Context Protocol (MCP) server manifest for [polyzig.com](https://polyzig.com) — the worldwide Polymarket market-intelligence and copy-trading platform.

**Designed for AI agents.** Hosted clients such as Poke connect through PolyZig OAuth so users sign in with Apple/email instead of pasting keys. Developer-owned clients can still mint scoped `pzk_*` API keys from the dashboard. Agents can search localized markets, inspect CLOB depth and price history, discover top traders, manage copy configurations, monitor positions and PnL, and place preview-confirmed Polymarket orders — all with sub-500ms mempool-driven copy execution.

## What's in this repo

| File | What it is |
|---|---|
| [`openapi.json`](./openapi.json) | OpenAPI 3.1 specification for the full REST API |
| [`mcp.json`](./mcp.json) | Model Context Protocol server manifest |
| [`AGENTS.md`](./AGENTS.md) | Long-form integration guide: auth, scopes, copy-trading workflow, error codes, full MCP tool catalogue |
| [`examples/`](./examples) | Working snippets for curl, Python, TypeScript, and Claude Desktop |

## Live endpoints

- **REST API**: `https://api.polyzig.com`
- **OpenAPI spec**: `https://polyzig.com/openapi.json` (mirrored from this repo, stable hostname)
- **Swagger UI**: `https://api.polyzig.com/api/docs`
- **MCP server**: `https://api.polyzig.com/api/mcp` (JSON-RPC 2.0 over Streamable HTTP)
- **MCP manifest**: `https://polyzig.com/.well-known/mcp.json`
- **Developer landing**: `https://polyzig.com/developers`
- **OAuth metadata**: `https://api.polyzig.com/.well-known/oauth-authorization-server`
- **Mint API keys**: `https://polyzig.com/dashboard/keys`

## Quick start

### 1. Choose auth

Hosted MCP clients should use PolyZig OAuth. The user signs in to PolyZig with Apple, email, or another enabled identity and approves scopes. Do not ask Poke users to paste a PolyZig API key.

Developer-owned clients that do not support OAuth can sign in at [polyzig.com](https://polyzig.com), open `/dashboard/keys`, and create a scoped API key. The secret is shown **once**. Keys are prefixed `pzk_`.

### 2. Verify with curl

```bash
curl https://api.polyzig.com/api/users/me \
  -H "Authorization: Bearer pzk_live_..."
```

### 3. Connect Claude Desktop

Drop this into `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "polyzig": {
      "url": "https://api.polyzig.com/api/mcp",
      "headers": {
        "Authorization": "Bearer pzk_live_..."
      }
    }
  }
}
```

Restart Claude Desktop. Your agent now has access to every MCP tool whose scope your key holds.

## Scopes

Keys carry explicit scopes. Default to the minimum your agent actually needs.

| Scope | Grants |
|---|---|
| `read:account` | Profile, balance, PnL summary |
| `read:positions` | Open + paper positions |
| `read:trades` | Trade history and fills |
| `read:markets` | Market search, localized details, CLOB depth, price history, open orders, leaderboard |
| `trade:execute` | Place orders; create/start/stop copy configs |
| `trade:cancel` | Cancel resting CLOB orders |
| `wallet:write` | Claim resolved positions, withdraw, wrap-to-pUSD |

## MCP tool catalogue (v1)

The MCP server returns only the tools your credential scopes permit.

**Discovery / setup**: `get_platform_stats`, `get_trading_readiness`, `search_markets`, `get_market_details`, `get_market_depth`, `get_market_price_history`, `list_top_traders`

**Per-user reads**: `get_user_summary`, `list_open_positions`, `list_paper_positions`, `list_trades`

**Copy-trading reads**: `list_copy_configs`, `get_copy_config`, `get_config_pnl`, `get_config_trades`, `suggest_multiplier`

**Copy-trading writes**: `create_copy_config`, `start_copying`, `stop_copying`, `delete_copy_config`

**Direct trading**: `preview_market_order`, `place_market_order`, `list_open_orders`, `cancel_order`, `claim_positions`

See [AGENTS.md](./AGENTS.md) for full descriptions, required scopes, and request shapes.

## Why an MCP server for Polymarket?

PolyZig's marquee feature is **sub-500ms copy-trading**: when a target Polymarket wallet broadcasts an order to the Polygon mempool, PolyZig decodes it, applies the user's sizing and risk rules, and submits a mirror order before the original lands on-chain.

Wiring that to an MCP server means agents can:

- Search Polymarket markets in supported locales, then call `get_market_details`, `get_market_depth`, and `get_market_price_history` before previewing a trade
- Discover a target trader via `list_top_traders` or the public leaderboard feed
- Use `suggest_multiplier` to size a config to the user's actual balance
- `create_copy_config` with `paper_trading: true` and let it run for a session
- Inspect `get_config_pnl` and `get_config_trades` to evaluate performance
- Promote to live when ready — and `stop_copying` / `delete_copy_config` cleanly

The whole copy-trading lifecycle is exposed as first-party MCP tools, scope-gated and idempotent.

## Reliability primitives

Every REST write endpoint supports an `Idempotency-Key` header (24h TTL). Every MCP write tool requires an `idempotency_key` argument. A retried claim, config change, or order on a network blip never double-fires.

Every error response shares this shape:

```json
{ "error": "human readable message", "code": "machine_code" }
```

Branch on `code`, not on `error`.

## Examples

### Python

```python
# examples/python/example.py
import httpx, uuid

POLYZIG_KEY = "pzk_live_..."
HEADERS = {"Authorization": f"Bearer {POLYZIG_KEY}"}

with httpx.Client(base_url="https://api.polyzig.com", headers=HEADERS) as c:
    # who am I
    me = c.get("/api/users/me").json()
    print(me["email"])

    # start paper-copying a target wallet
    r = c.post(
        "/api/configs",
        json={
            "target_address": "0xWHALE_ADDRESS",
            "size_multiplier": "0.1",
            "paper_trading": True,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    cfg = r.json()
    c.post(f"/api/configs/{cfg['id']}/start")
```

### TypeScript

```ts
// examples/typescript/example.ts
const key = process.env.POLYZIG_KEY!;
const base = "https://api.polyzig.com";

const me = await fetch(`${base}/api/users/me`, {
  headers: { Authorization: `Bearer ${key}` },
}).then(r => r.json());

console.log(me.email);
```

See [`examples/`](./examples) for more, including curl snippets and editor configs.

## Versioning

This repo mirrors the spec deployed at `polyzig.com/openapi.json`. Breaking changes to the API contract bump the `info.version` in `openapi.json`; we tag releases (`v1.1.0`, etc.) so SDKs can pin.

## Issues, support, security

- API contract bugs or questions: open an issue here
- Account / billing: [support@polyzig.com](mailto:support@polyzig.com) or [t.me/polyzig_support](https://t.me/polyzig_support)
- Security disclosures: [polyzig.com/.well-known/security.txt](https://polyzig.com/.well-known/security.txt)

## License

MIT for everything in this repo. See [LICENSE](./LICENSE). The PolyZig platform itself, the brand, and the source code that runs the service are not covered by this license.
