// Minimal TypeScript example of using the PolyZig API.
//
// Run with:  POLYZIG_KEY=pzk_live_... bun run example.ts
// (or node ≥ 22 with --experimental-strip-types)
//
// The key needs read:account + read:positions to exercise the path below.
// Mint at https://polyzig.com/dashboard/keys.

const BASE = "https://api.polyzig.com";
const KEY = process.env.POLYZIG_KEY;
if (!KEY) throw new Error("set POLYZIG_KEY");

const auth = { Authorization: `Bearer ${KEY}` };

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...auth, ...(init.headers ?? {}), "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string; code?: string };
    throw new Error(`${path} → ${res.status} ${body.code ?? ""} ${body.error ?? ""}`);
  }
  return (await res.json()) as T;
}

type Me = { id: string; email: string };
type Position = {
  token_id: string;
  market_slug: string | null;
  shares: string;
  current_value_dec: string | null;
  unrealized_pnl_dec: string | null;
};

const me = await api<Me>("/api/users/me");
console.log(`signed in as ${me.email}`);

const positions = await api<Position[]>("/api/positions?limit=20");
console.log(`open positions: ${positions.length}`);
for (const p of positions.slice(0, 3)) {
  // Prefer the decimal-string `*_dec` mirrors over the float fields for any
  // arithmetic or comparisons — they're lossless.
  console.log(
    `  - ${p.market_slug ?? p.token_id}  value=$${p.current_value_dec ?? "?"}  pnl=$${p.unrealized_pnl_dec ?? "?"}`,
  );
}
