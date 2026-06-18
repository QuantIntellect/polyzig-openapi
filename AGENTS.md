# PolyZig Agent Integration Guide

A self-contained, human + machine-readable reference for AI agents and developers integrating with PolyZig.

- **Live OpenAPI spec**: <https://polyzig.com/openapi.json>
- **Interactive docs**: <https://api.polyzig.com/api/docs>
- **MCP manifest**: <https://polyzig.com/.well-known/mcp.json>
- **MCP endpoint**: <https://api.polyzig.com/api/mcp>
- **OAuth metadata**: <https://api.polyzig.com/.well-known/oauth-authorization-server>

## What PolyZig is

PolyZig is the worldwide Polymarket trading platform, with a sub-500ms mempool-driven copy-trading engine as its marquee feature. Users select Polymarket wallets to copy and PolyZig mirrors their trades on Polygon's CTF Exchange before the original transaction confirms on-chain.

## Authentication

Three bearer-token mechanisms are accepted, all passed as `Authorization: Bearer <token>`:

1. **Session JWT** — issued via the browser flow (`POST /api/auth/magic` or `POST /api/auth/verify-code`). Full account scope, 24h expiry. Intended for the first-party web app. **Not recommended for agents** — JWT leakage exposes the whole account.

2. **OAuth MCP access token** (`pzo_*`) — issued by PolyZig OAuth after the user signs in with Apple, email, or another enabled PolyZig identity. This is the right credential for hosted integrations such as Poke because users approve access with normal login instead of copying API keys.

3. **API key** (`pzk_*`) — minted from the dashboard at <https://polyzig.com/dashboard/keys>. Carries explicit scopes, revocable independently of the user's password, default 90-day expiry. Use this for developer-owned clients that do not support OAuth.

> Poke and other hosted MCP clients should use OAuth. Do not ask end users to paste a PolyZig API key into Poke.

## Scopes

Grant only the scopes the agent actually needs. Default to read-only.

| Scope | What it allows | Recommended for |
|---|---|---|
| `read:account` | User profile, balance, PnL summary | Every key |
| `read:positions` | List open + paper positions | Monitoring agents |
| `read:trades` | Trade history, fills | Analytics agents |
| `read:markets` | Market search, market details, depth, history, open orders, leaderboard | Discovery agents |
| `trade:execute` | Place market/limit orders. Create + start + stop copy configs. | Copy-trading agents |
| `trade:cancel` | Cancel resting CLOB orders | Market-making agents |
| `wallet:write` | Claim resolved positions, withdraw, wrap-to-pUSD | Settlement agents |

## Core agent workflows

### 1. Onboarding — first 3 calls

```http
GET  /api/users/me                  # who am I (verify the key is alive)
GET  /api/stats/platform            # public — confirms server reachable
GET  /api/wallets/balance           # do I have funds to trade?
```

### 2. Copy a top trader (the marquee feature)

```http
# Discover what the user is already copying
GET  /api/configs

# Find a target trader (or accept one as input)
# Public leaderboard JSON: https://polyzig.com/feed/leaderboard.json

# Create the copy config (INACTIVE on creation)
POST /api/configs
{
  "target_address": "0x...",
  "target_name":    "polymarket-whale",
  "copy_mode":      "multiplier",
  "size_multiplier": "0.1",            // 10% of the target's size
  "max_position_per_side": "500",      // USDC cap per outcome
  "paper_trading":  true,              // ALWAYS start in paper for new targets
  "notifications_enabled": true,
  "tp_sl_enabled": true,
  "take_profit_pct": "50",
  "stop_loss_pct":   "20"
}

# Start mirroring
POST /api/configs/{id}/start

# Watch performance
GET  /api/configs/{id}/pnl
GET  /api/configs/{id}/trades?limit=20

# Stop when done (existing positions stay open)
POST /api/configs/{id}/stop
```

### 3. Place a one-off market order

```http
POST /api/markets/order
Headers:
  Authorization: Bearer pzk_live_...
  Idempotency-Key: <uuid>            # always set for safe retries
Body:
  {
    "token_id":   "0xabc...",        // Polymarket CTF outcome token
    "side":       "buy",
    "order_type": "market",
    "amount":     50                  // USDC notional (or use "size" for shares)
  }
```

### 4. Claim winnings

```http
POST /api/positions/claim
Headers:
  Idempotency-Key: <uuid>
Body:
  {
    "condition_id": "0x..."           # optional — omit to claim all
  }
```

### 5. Withdraw funds

```http
POST /api/trading-wallet/withdraw
Headers:
  Authorization: Bearer pzk_live_...
  Idempotency-Key: <uuid>
Body:
  {
    "to_address": "0x...",            # destination Polygon address
    "amount":     "100.0",            # decimal-string
    "token":      "usdc"              # "usdc" (pUSD) | "usdc_e" | "matic"
  }
```

## Idempotency

Most state-changing endpoints accept an `Idempotency-Key` request header. Re-submitting the same key within 24 hours returns the cached response instead of re-executing. Generate a fresh UUID per logical operation; retry with the same key on transport failure.

```http
POST /api/positions/claim
Idempotency-Key: 5b6f2c4a-...        # safe to retry until 200 lands
```

Replayed responses include `Idempotent-Replay: true`.

**Exceptions — these routes are *not* cached even if you send the header:**

- `POST /api/keys` — the response body contains the one-time `pzk_*` secret. Caching it would defeat the "shown once, never stored" contract. Each retry mints a **new** key, so don't retry blindly; surface the failure to the user and let them re-issue from the dashboard.
- `POST /api/mcp` — JSON-RPC errors travel inside an HTTP 200 envelope. Caching them by status would memoize transient tool failures for 24h. MCP retries should rely on the JSON-RPC `id` field instead.

**In-flight collision**: if two requests with the same key arrive concurrently, exactly one runs the handler; the others get `409 Conflict` + `Retry-After` until the first completes. Retry with the same key after the hinted delay to either replay the cached response or get a clean run if the first attempt failed.

## Rate limits

Default: **60 requests/sec, 500 burst, per client IP.**

Every response carries:

```
X-RateLimit-Limit:   500
X-RateLimit-Policy:  60;w=1;burst=500
```

On 429/503:

```
Retry-After: 1
```

## Pagination

List endpoints return a bare JSON array; pagination metadata is in headers (non-breaking):

```
X-Pagination-Limit:    50
X-Pagination-Offset:   0
X-Pagination-Count:    50
X-Pagination-Has-Next: true
```

Loop until `X-Pagination-Has-Next: false`.

## Errors

Every error response shares this shape:

```json
{ "error": "human readable message", "code": "machine_code" }
```

**Branch on `code`, not on `error`.** The `error` string may be localized or rephrased. The `code` is part of the contract.

| `code` | HTTP | Meaning |
|---|---|---|
| `unauthorized` | 401 | Missing or invalid bearer token |
| `invalid_token` | 401 | JWT signature / expiry |
| `tier_limit_exceeded` | 403 | Action requires a higher subscription tier |
| `not_found` | 404 | No resource at that ID |
| `bad_request` | 400 | Malformed input |
| `validation_failed` | 400 | Field-level constraint violation |
| `insufficient_balance` | 402 | Not enough pUSD/USDC on the trading wallet |
| `feature_not_enabled` | 501 | API surface exists but not active in this deployment |
| `polymarket_unavailable` | 503 | Upstream Polymarket flow failed (retry with backoff) |
| `rate_limited` | 429 | Slow down; consult `Retry-After` |
| `scope_required` | 403 | Scoped credential missing the required scope |

## Money

Floating-point fields like `current_value`, `unrealized_pnl`, `claimable_value`, and `total_usdc` have **decimal-string mirror fields** suffixed `_dec`:

```json
{
  "current_value": 1234.56,
  "current_value_dec": "1234.56"
}
```

**Use the `_dec` field** for arithmetic and comparisons — `parseFloat` loses cents on large balances.

## Model Context Protocol (MCP)

Connect any MCP-compatible client to PolyZig:

```
Endpoint:  https://api.polyzig.com/api/mcp
Transport: Streamable HTTP (single POST per JSON-RPC request)
Auth:      Poke/hosted clients: OAuth pzo_* access token
           Developer clients: Authorization: Bearer pzk_*
```

The MCP server returns only the tools your credential's scopes permit. **Every tool except `get_platform_stats` requires a matching scope** — `tools/list` filters by scope server-side, so a credential with only `read:account` will not see `search_markets` (which needs `read:markets`) in its tool catalog. Grant the union of scopes for every tool you intend to call.

### Tool catalogue (v1)

**Public / no scope required:**

- `get_platform_stats` — median/p95 latency, fill volume, detection breakdown. Callable by any authenticated key.

**Discovery (requires `read:markets`):**

- `search_markets` — active market cards with emoji/category badges, images/logos, outcome choices, token IDs, prices, links, and iMessage action hints
- `get_market_details` — localized context, Gamma status, condition ID, outcome token IDs, prices, volume/liquidity, bounded live snapshots, choices, and next-step actions
- `get_market_depth` — CLOB best bid/ask, spread, top levels, cumulative liquidity, depth within 1c/2c/5c, and depth-card actions
- `get_market_price_history` — sampled CLOB history with open/latest/high/low/change and chart/depth/trade-preview actions
- `list_top_traders` — copyable leaderboard cards with avatars, verified badges, and preview-copy actions

**Per-user reads:**

- `get_trading_readiness` — `read:account` — scopes, balance, trading wallet status, setup blockers
- `get_user_summary` — `read:account` — trade count, fees paid
- `list_open_positions` — `read:positions` — current holdings + unrealized PnL
- `list_paper_positions` — `read:positions` — paper-trading positions
- `list_trades` — `read:trades` — fill history with latency

### Poke / iMessage presentation

MCP results include raw data plus compact display fields. For Messages, render from these first and keep raw JSON hidden unless the user asks for technical details:

- `title`, `emoji`, `badge`, `subtitle`, `lines`
- `primary_url` and `image_url` for iMessage link previews
- `presentation` for surface/style/accent/hero-image hints
- `choices` for outcome or confirm/edit/cancel options
- `actions` for next MCP tool hints such as inspect details, show depth, show history, preview an order, create a copy config, or open PolyZig
- `tap_prompt`, `risk_note`, and `confirmation_text`

Poke public docs do not publish a separate custom attachment schema, so treat these fields as rendering hints and safety metadata, not as authorization. All writes still require OAuth/API-key scopes, exact preview ownership, and `idempotency_key`.

**Copy-trading reads:**

- `list_copy_configs` — `read:account` — every copy config the user owns
- `get_copy_config` — `read:account` — single config
- `get_config_pnl` — `read:account` — config-level PnL breakdown
- `get_config_trades` — `read:trades` — trades attributed to one config
- `suggest_multiplier` — `read:markets` — recommended sizing for current balance
- `preview_copy_config` — `trade:execute` — summarize target, sizing, caps, TP/SL, live/paper mode

**Copy-trading writes:**

- `create_copy_config` — `trade:execute` — create an inactive config from `preview_copy_config.preview_id`
- `start_copying` — `trade:execute` — activate mirroring; requires `idempotency_key`
- `stop_copying` — `trade:execute` — deactivate (positions stay open); requires `idempotency_key`
- `delete_copy_config` — `trade:execute` — permanent delete; requires `idempotency_key`

**Direct trading:**

- `preview_market_order` — `trade:execute` — exact order preview with token, price, estimated shares, slippage, and confirmation text
- `place_market_order` — `trade:execute` — live order from `preview_market_order.preview_id`; requires `idempotency_key`
- `list_open_orders` — `read:markets`
- `cancel_order` — `trade:cancel`; requires `idempotency_key`
- `claim_positions` — `wallet:write`; requires `idempotency_key`

## Operational best practices for agents

1. **Always paper-trade a new target.** Set `paper_trading: true` on the first copy config for any new wallet. Run it for at least a session, look at PnL, then promote.
2. **Set `idempotency_key` on every MCP write.** Network blips are the normal failure mode at 500ms latency.
3. **Watch `tier_limit_exceeded`.** Some features require HFT Elite tier. Surface the upgrade link to the user, don't retry.
4. **Respect `Retry-After`.** 429s rarely happen but when they do, back off — don't burst-retry.
5. **Grant scoped access.** Don't give a monitoring agent `trade:execute`. Don't give a copy-trading agent `wallet:write` unless it will claim positions.

## Feedback / support

- Bug or contract question: `support@polyzig.com`
- Security disclosures: see <https://polyzig.com/.well-known/security.txt>
- Status: <https://polyzig.com/dashboard/transparency>
