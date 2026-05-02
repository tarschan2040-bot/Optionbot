"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import { getConfig, updateConfig } from "@/lib/api";
import Link from "next/link";

interface ScannerConfig {
  tickers: string[]; strategy: string; data_source: string;
  min_dte: number; max_dte: number; cc_delta_min: number; cc_delta_max: number;
  csp_delta_min: number; csp_delta_max: number; min_theta: number;
  min_iv: number; min_iv_rank: number; min_annualised_return: number;
  min_premium: number; max_bid_ask_spread_pct: number;
  weight_iv: number; weight_theta_yield: number; weight_delta_safety: number;
  weight_liquidity: number; weight_ann_return: number; weight_mean_reversion: number;
  use_mean_reversion: boolean; config_hash: string; [key: string]: unknown;
}

function Slider({ label, value, min, max, step, suffix, onChange }: {
  label: string; value: number; min: number; max: number; step: number; suffix?: string; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-white font-mono">{value.toFixed(step < 1 ? 2 : 0)}{suffix}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} className="w-full accent-emerald-500" />
    </div>
  );
}

export default function ParametersPage() {
  const { token } = useSession();
  const [config, setConfig] = useState<ScannerConfig | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadConfig = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const d = await getConfig(token);
      setConfig(d);
      setTickerInput(d.tickers.join(", "));
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load config.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  async function handleSave() {
    if (!token || !config) return;
    setSaving(true); setError(""); setSaved(false);
    try {
      const tickers = tickerInput.split(/[,\s]+/).map((t) => t.trim().toUpperCase()).filter(Boolean);
      const updates = { ...config, tickers };
      delete (updates as Record<string, unknown>).config_hash;
      await updateConfig(token, updates);
      setSaved(true); setTimeout(() => setSaved(false), 3000); loadConfig();
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Failed to save."); }
    finally { setSaving(false); }
  }

  function set(field: string, value: unknown) { if (config) setConfig({ ...config, [field]: value }); }

  if (!token) return null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white">
        <Nav />
        <main className="max-w-3xl mx-auto px-6 py-8">
          <div className="text-center py-20 text-gray-500">Loading parameters...</div>
        </main>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="min-h-screen bg-gray-950 text-white">
        <Nav />
        <main className="max-w-3xl mx-auto px-6 py-8">
          <div className="flex items-center gap-4 mb-8">
            <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
              <Link href="/scan" className="px-4 py-2 rounded-md text-sm font-medium text-gray-400 hover:text-white transition-colors">Results</Link>
              <span className="px-4 py-2 rounded-md text-sm font-medium bg-gray-800 text-white">Parameters</span>
            </div>
          </div>
          <div className="rounded-xl border border-red-700 bg-red-900/30 p-6">
            <h2 className="text-lg font-semibold text-red-200">Unable to load parameters</h2>
            <p className="mt-2 text-sm text-red-100/90">
              {error || "The app could not reach the backend API."}
            </p>
            <p className="mt-3 text-sm text-gray-300">
              Check that `NEXT_PUBLIC_API_URL` in Vercel points to your Railway backend and that Railway allows requests from `https://app.optionbot.org`.
            </p>
            <button
              onClick={loadConfig}
              className="mt-5 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            >
              Retry
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Sub-nav */}
        <div className="flex items-center gap-4 mb-8">
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
            <Link href="/scan" className="px-4 py-2 rounded-md text-sm font-medium text-gray-400 hover:text-white transition-colors">Results</Link>
            <span className="px-4 py-2 rounded-md text-sm font-medium bg-gray-800 text-white">Parameters</span>
          </div>
        </div>

        <h2 className="text-2xl font-bold mb-6">Scan Parameters</h2>
        {error && <div className="mb-6 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>}

        <div className="space-y-6">
          {/* Watchlist */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Watchlist</h3>
            <input type="text" value={tickerInput} onChange={(e) => setTickerInput(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500" placeholder="TSLA, NVDA, AAPL" />
            <select value={config.strategy} onChange={(e) => set("strategy", e.target.value)}
              className="w-full mt-3 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500">
              <option value="both">Covered Calls + Cash-Secured Puts</option>
              <option value="cc">Covered Calls only</option>
              <option value="csp">Cash-Secured Puts only</option>
            </select>
          </section>

          {/* Filters */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Filters</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <Slider label="Min DTE" value={config.min_dte} min={7} max={90} step={1} onChange={(v) => set("min_dte", v)} />
                <Slider label="Max DTE" value={config.max_dte} min={14} max={120} step={1} onChange={(v) => set("max_dte", v)} />
              </div>
              <Slider label="Min IV (raw)" value={config.min_iv} min={0} max={1.5} step={0.05} onChange={(v) => set("min_iv", v)} />
              <Slider label="Min Premium" value={config.min_premium} min={0} max={10} step={0.25} suffix="$" onChange={(v) => set("min_premium", v)} />
              <Slider label="Min Ann. Return" value={config.min_annualised_return} min={0} max={0.5} step={0.01} onChange={(v) => set("min_annualised_return", v)} />
              <Slider label="Min Theta" value={config.min_theta} min={0} max={0.5} step={0.01} onChange={(v) => set("min_theta", v)} />
            </div>
          </section>

          {/* Delta */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Delta Range</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <Slider label="CC Delta Min" value={config.cc_delta_min} min={0.05} max={0.5} step={0.01} onChange={(v) => set("cc_delta_min", v)} />
                <Slider label="CC Delta Max" value={config.cc_delta_max} min={0.1} max={0.6} step={0.01} onChange={(v) => set("cc_delta_max", v)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Slider label="CSP Delta Min" value={config.csp_delta_min} min={-0.6} max={-0.05} step={0.01} onChange={(v) => set("csp_delta_min", v)} />
                <Slider label="CSP Delta Max" value={config.csp_delta_max} min={-0.5} max={-0.05} step={0.01} onChange={(v) => set("csp_delta_max", v)} />
              </div>
            </div>
          </section>

          {/* Weights */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Scoring Weights</h3>
            <p className="text-gray-500 text-sm mb-4">Must sum to 1.00</p>
            <div className="space-y-4">
              <Slider label="IV" value={config.weight_iv} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_iv", v)} />
              <Slider label="Theta Yield" value={config.weight_theta_yield} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_theta_yield", v)} />
              <Slider label="Delta Safety" value={config.weight_delta_safety} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_delta_safety", v)} />
              <Slider label="Liquidity" value={config.weight_liquidity} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_liquidity", v)} />
              <Slider label="Annual Return" value={config.weight_ann_return} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_ann_return", v)} />
              <Slider label="Mean Reversion" value={config.weight_mean_reversion} min={0} max={0.5} step={0.05} onChange={(v) => set("weight_mean_reversion", v)} />
            </div>
            <div className="mt-4 flex items-center gap-3">
              <input type="checkbox" id="use_mr" checked={config.use_mean_reversion} onChange={(e) => set("use_mean_reversion", e.target.checked)} className="accent-emerald-500" />
              <label htmlFor="use_mr" className="text-sm text-gray-400">Enable Mean Reversion</label>
            </div>
          </section>

          {/* Save */}
          <div className="flex items-center gap-4">
            <button onClick={handleSave} disabled={saving} className="px-8 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white font-semibold rounded-lg transition-colors">
              {saving ? "Saving..." : "Save Parameters"}
            </button>
            {saved && <span className="text-emerald-400 text-sm">Saved!</span>}
            <span className="text-gray-600 text-xs ml-auto font-mono">Hash: {config.config_hash?.slice(0, 12)}...</span>
          </div>
        </div>
      </main>
    </div>
  );
}
