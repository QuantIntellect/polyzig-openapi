"""
Minimal Python example of using the PolyZig API.

Run with:  POLYZIG_KEY=pzk_live_... python example.py

The key needs read:account + read:positions + trade:execute to exercise
the full path below (it ends by creating a paper-trading copy config).
Mint at https://polyzig.com/dashboard/keys.
"""

import os
import uuid

import httpx

BASE = "https://api.polyzig.com"
KEY = os.environ["POLYZIG_KEY"]

headers = {"Authorization": f"Bearer {KEY}"}

with httpx.Client(base_url=BASE, headers=headers, timeout=10.0) as c:
    me = c.get("/api/users/me").json()
    print(f"signed in as {me['email']}")

    positions = c.get("/api/positions", params={"limit": 20}).json()
    print(f"open positions: {len(positions)}")
    for p in positions[:3]:
        # Use the decimal-string *_dec mirrors for arithmetic — the f64
        # fields can lose cents on large balances.
        print(
            f"  - {p.get('market_slug') or p['token_id']}  "
            f"value=${p.get('current_value_dec') or '?'}  "
            f"pnl=${p.get('unrealized_pnl_dec') or '?'}"
        )

    # Demo: create (but don't activate) a paper-trading copy config.
    # Replace TARGET with a real Polymarket wallet you want to mirror.
    TARGET = "0x0000000000000000000000000000000000000000"
    resp = c.post(
        "/api/configs",
        json={
            "target_address": TARGET,
            "target_name": "python-demo",
            "size_multiplier": "0.1",
            "paper_trading": True,
        },
        # Always set Idempotency-Key on writes. Retry-safe by contract.
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    if resp.is_success:
        cfg = resp.json()
        print(f"created paper config {cfg['id']} for {TARGET}")
        # c.post(f"/api/configs/{cfg['id']}/start")  # uncomment to activate
    else:
        body = resp.json()
        print(f"create failed: code={body.get('code')!r} error={body.get('error')!r}")
