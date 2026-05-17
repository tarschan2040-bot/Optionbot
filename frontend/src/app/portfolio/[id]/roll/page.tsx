"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { useSession } from "@/hooks/useSession";
import { getPortfolioPosition, rollPortfolioPosition } from "@/lib/api";

interface Position {
  id: string; ticker: string; strategy: string; strike: number; expiry: string;
  contracts: number; entry_delta: number; option_label: string;
}

export default function RollPositionPage() {
  const { token } = useSession();
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [position, setPosition] = useState<Position | null>(null);
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    buyback_price: "",
    ticker: "",
    strategy: "COVERED_CALL",
    strike: "",
    expiry: "",
    entry_price: "",
    contracts: "1",
    entry_delta: "",
  });

  const loadPosition = useCallback(async () => {
    if (!token || !id) return;
    try {
      const data = await getPortfolioPosition(token, id);
      setPosition(data);
      setForm((current) => ({
        ...current,
        ticker: data.ticker,
        strategy: data.strategy,
        contracts: String(data.contracts || 1),
      }));
    } catch {
      setMsg("Position not found.");
    }
  }, [token, id]);

  useEffect(() => {
    queueMicrotask(() => void loadPosition());
  }, [loadPosition]);

  function updateField(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit() {
    if (!token || !position) return;
    const buybackPrice = Number(form.buyback_price);
    const strike = Number(form.strike);
    const entryPrice = Number(form.entry_price);
    const contracts = Number(form.contracts);
    const entryDelta = form.entry_delta.trim() ? Number(form.entry_delta) : undefined;

    if (
      !Number.isFinite(buybackPrice) || buybackPrice < 0 ||
      !Number.isFinite(strike) || strike <= 0 ||
      !Number.isFinite(entryPrice) || entryPrice < 0 ||
      !Number.isInteger(contracts) || contracts < 1 ||
      !form.ticker.trim() || !form.expiry
    ) {
      setMsg("Fill in a valid buyback price and new contract.");
      return;
    }

    setSaving(true);
    try {
      const response = await rollPortfolioPosition(token, position.id, {
        buyback_price: buybackPrice,
        ticker: form.ticker.trim().toUpperCase(),
        strategy: form.strategy,
        strike,
        expiry: form.expiry,
        entry_price: entryPrice,
        contracts,
        entry_delta: entryDelta,
      });
      setMsg(response.message);
      router.push("/portfolio");
    } catch {
      setMsg("Failed to roll position.");
    } finally {
      setSaving(false);
    }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Link href={`/portfolio/${id}`} className="text-sm text-gray-400 transition-colors hover:text-white">&larr; Back to position</Link>
        <div className="mt-6 border-b border-gray-800 pb-6">
          <p className="text-sm uppercase tracking-wide text-gray-500">Roll Position</p>
          <h1 className="mt-2 text-3xl font-bold">{position?.option_label || "Open Position"}</h1>
        </div>

        {msg && <div className="mt-4 rounded-lg border border-emerald-700 bg-emerald-900/30 p-3 text-sm text-emerald-300">{msg}</div>}

        <section className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-lg font-semibold">Close Existing Leg</h2>
          <label className="mt-4 block text-sm text-gray-400">
            Buy Back Price
            <input value={form.buyback_price} onChange={(e) => updateField("buyback_price", e.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
          </label>
        </section>

        <section className="mt-6 rounded-lg border border-gray-800 bg-gray-900 p-5">
          <h2 className="text-lg font-semibold">New Contract</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-gray-400">
              Ticker
              <input value={form.ticker} onChange={(e) => updateField("ticker", e.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
            <label className="block text-sm text-gray-400">
              Strategy
              <select value={form.strategy} onChange={(e) => updateField("strategy", e.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white">
                <option value="COVERED_CALL">Covered Call</option>
                <option value="CASH_SECURED_PUT">Cash-Secured Put</option>
              </select>
            </label>
            <label className="block text-sm text-gray-400">
              Expiry
              <input type="date" value={form.expiry} onChange={(e) => updateField("expiry", e.target.value)} className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
            <label className="block text-sm text-gray-400">
              Strike
              <input value={form.strike} onChange={(e) => updateField("strike", e.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
            <label className="block text-sm text-gray-400">
              Entry Price
              <input value={form.entry_price} onChange={(e) => updateField("entry_price", e.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
            <label className="block text-sm text-gray-400">
              Quantity
              <input value={form.contracts} onChange={(e) => updateField("contracts", e.target.value)} inputMode="numeric" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
            <label className="block text-sm text-gray-400 md:col-span-2">
              Entry Delta
              <input value={form.entry_delta} onChange={(e) => updateField("entry_delta", e.target.value)} inputMode="decimal" placeholder="Optional" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
            </label>
          </div>
          <button onClick={handleSubmit} disabled={saving || !position} className="mt-6 w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-50">
            Roll Position
          </button>
        </section>
      </main>
    </div>
  );
}
