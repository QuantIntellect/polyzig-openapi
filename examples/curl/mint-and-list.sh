#!/usr/bin/env bash
# Minimal curl walkthrough:
#   1. verify the key
#   2. list open positions
#   3. paper-copy a target wallet (idempotent)
#   4. read PnL
#
# Usage:  POLYZIG_KEY=pzk_live_... ./mint-and-list.sh
set -euo pipefail

: "${POLYZIG_KEY:?set POLYZIG_KEY=pzk_live_... before running}"
BASE="${POLYZIG_BASE:-https://api.polyzig.com}"
AUTH=(-H "Authorization: Bearer ${POLYZIG_KEY}")

echo "== whoami =="
curl -sS "${AUTH[@]}" "${BASE}/api/users/me" | jq .

echo
echo "== open positions =="
curl -sS "${AUTH[@]}" "${BASE}/api/positions?limit=10" | jq '.[] | {market_slug, shares, current_value_dec, unrealized_pnl_dec}'

echo
echo "== paper-copy a target wallet =="
TARGET="${TARGET:-0x0000000000000000000000000000000000000000}"
CFG_ID=$(curl -sS "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen 2>/dev/null || python -c 'import uuid;print(uuid.uuid4())')" \
  -d "{\"target_address\":\"${TARGET}\",\"target_name\":\"curl-demo\",\"size_multiplier\":\"0.1\",\"paper_trading\":true}" \
  "${BASE}/api/configs" | tee /dev/stderr | jq -r .id)

if [[ "${CFG_ID:-}" == "null" || -z "${CFG_ID:-}" ]]; then
  echo "config create failed — see error above" >&2
  exit 1
fi

echo
echo "== pnl for ${CFG_ID} =="
curl -sS "${AUTH[@]}" "${BASE}/api/configs/${CFG_ID}/pnl" | jq .
