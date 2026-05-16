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
  use_mean_reversion: boolean; mr_timing_confirmation: boolean;
  mr_timing_sma_period: number; mr_timing_unconfirmed_cap: number;
  config_hash: string; [key: string]: unknown;
}

function InfoLabel({ label, info }: { label: string; info: string }) {
  return (
    <span className="relative inline-flex items-center gap-1.5">
      <span>{label}</span>
      <span className="group relative inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full border border-gray-600 bg-gray-800 text-[10px] font-bold leading-none text-gray-300">
        !
        <span className="pointer-events-none absolute left-1/2 top-5 z-30 hidden w-72 max-w-[calc(100vw-2rem)] -translate-x-1/2 rounded-md border border-gray-700 bg-gray-950 px-3 py-2 text-left text-xs font-normal leading-relaxed text-gray-200 shadow-xl group-hover:block group-focus:block">
          {info}
        </span>
      </span>
    </span>
  );
}

function Slider({ label, value, min, max, step, suffix, onChange, info, recommendation }: {
  label: string; value: number; min: number; max: number; step: number; suffix?: string; onChange: (v: number) => void; info: string; recommendation?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-start justify-between gap-3 text-sm">
        <span className="min-w-0 text-gray-400">
          <InfoLabel label={label} info={info} />
          {recommendation && (
            <span className="ml-2 text-xs text-gray-500">{recommendation}</span>
          )}
        </span>
        <span className="text-white font-mono">{value.toFixed(step < 1 ? 2 : 0)}{suffix}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} className="w-full accent-emerald-500" />
    </div>
  );
}

const HELP = {
  watchlist: "The stocks or ETFs you want the scanner to examine. Each ticker has its own price, volatility, option volume, and premium level, so your watchlist affects which filters and score weights make sense.",
  strategy: "The option-selling approach to scan. Covered calls sell call options against shares you own. Cash-secured puts sell put options while reserving cash in case you must buy shares at the strike price. This choice affects the delta ranges, risk, and timing settings below.",
  minDte: "DTE means days to expiration, or how many calendar days remain before the option expires. Shorter expirations can decay faster but can also move sharply. Recommended default: 21.",
  maxDte: "The longest expiration window the scanner will accept. Longer-dated options usually collect more premium, but they keep capital tied up longer and react more to volatility changes. Recommended default: 42.",
  minIv: "Implied volatility is the market's estimate of how much the stock may move in the future. Higher IV usually means richer option premium and higher expected risk. Recommended default: 0.40 for high-beta stocks; 0 disables this filter.",
  minPremium: "The minimum option credit received per share before a trade is considered. One option contract usually covers 100 shares, so a 2.00 premium is about $200 before costs. Recommended default: 2.00.",
  minReturn: "Annualized return estimates option income as a yearly percentage of the capital required. It helps compare trades with different expirations, but very high values can signal extra risk. Recommended default: 0.15, or 15%.",
  minTheta: "Theta estimates how much option value disappears each day from time passing. Option sellers generally benefit from positive theta because the option they sold loses time value. Recommended default: 0.08.",
  ccDeltaMin: "For covered calls, delta estimates how much the call price may move when the stock moves $1. Lower delta usually means the strike is farther above the stock price and less likely to be reached. Recommended default: 0.20.",
  ccDeltaMax: "The highest covered-call delta allowed. Higher delta usually pays more premium, but it also raises the chance you must sell your shares at the option's strike price and give up further upside. Recommended default: 0.35.",
  cspDeltaMin: "For cash-secured puts, delta is negative. A more negative delta is closer to the current stock price and usually pays more premium, but it raises the chance you must buy shares at the strike price. Recommended default: -0.35.",
  cspDeltaMax: "The least negative cash-secured-put delta allowed. Values closer to zero are farther below the stock price and usually safer, but they pay less premium. Recommended default: -0.20.",
  weightIv: "How much the final score rewards options with higher implied volatility, which is the market's expectation for future stock movement. A higher weight favors richer premium. Recommended default: 0.15.",
  weightTheta: "How much the final score rewards daily time decay. A higher weight favors trades where the option seller is being paid more for each day that passes. Recommended default: 0.15.",
  weightDelta: "How much the final score rewards distance from the current stock price. A higher weight favors safer, farther-out-of-the-money contracts over higher-premium contracts near the stock price. Recommended default: 0.20.",
  weightLiquidity: "How much the final score rewards options that are easier to enter and exit. It favors higher open interest and tighter bid/ask spreads, which can reduce trading friction. Recommended default: 0.10.",
  weightReturn: "How much the final score rewards annualized return on capital. A higher weight favors bigger yield, but high yield often comes with higher price or assignment risk. Recommended default: 0.25.",
  weightMr: "How much the final score rewards mean reversion, the idea that an unusually stretched price often moves back toward a more normal level. A higher weight favors covered calls after stretched rallies and puts after stretched selloffs. Recommended default: 0.15.",
  useMr: "Turns on the price-timing model. It uses RSI, Z-score, and rate-of-change rank to judge whether the stock has moved unusually far and may be ready to cool down or bounce. Recommended default: on.",
  mrTiming: "Requires the stretched price condition to begin cooling before giving full mean-reversion credit. This helps avoid selling options too early while a strong move is still accelerating. Recommended default: on.",
  mrTimingSma: "The number of recent daily mean-reversion scores used to judge whether the setup is cooling. A shorter value reacts faster; a longer value waits for more confirmation. Recommended default: 3.",
  mrCap: "The maximum mean-reversion score allowed before timing confirms. Lower values make the scanner more cautious; higher values allow earlier signals to rank higher. Recommended default: 0.75.",
};

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

  useEffect(() => { queueMicrotask(() => { void loadConfig(); }); }, [loadConfig]);

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
            <label className="mb-2 block text-sm text-gray-400">
              <InfoLabel label="Tickers" info={HELP.watchlist} />
            </label>
            <input type="text" value={tickerInput} onChange={(e) => setTickerInput(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500" placeholder="TSLA, NVDA, AAPL" />
            <label className="mb-2 mt-4 block text-sm text-gray-400">
              <InfoLabel label="Strategy" info={HELP.strategy} />
            </label>
            <select value={config.strategy} onChange={(e) => set("strategy", e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500">
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
                <Slider label="Min DTE" value={config.min_dte} min={7} max={90} step={1} info={HELP.minDte} onChange={(v) => set("min_dte", v)} />
                <Slider label="Max DTE" value={config.max_dte} min={14} max={120} step={1} info={HELP.maxDte} onChange={(v) => set("max_dte", v)} />
              </div>
              <Slider label="Min IV (raw)" value={config.min_iv} min={0} max={1.5} step={0.05} info={HELP.minIv} onChange={(v) => set("min_iv", v)} />
              <Slider label="Min Premium" value={config.min_premium} min={0} max={10} step={0.25} suffix="$" info={HELP.minPremium} onChange={(v) => set("min_premium", v)} />
              <Slider label="Min Ann. Return" value={config.min_annualised_return} min={0} max={0.5} step={0.01} info={HELP.minReturn} onChange={(v) => set("min_annualised_return", v)} />
              <Slider label="Min Theta" value={config.min_theta} min={0} max={0.5} step={0.01} info={HELP.minTheta} onChange={(v) => set("min_theta", v)} />
            </div>
          </section>

          {/* Delta */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Delta Range</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <Slider label="CC Delta Min" value={config.cc_delta_min} min={0.05} max={0.5} step={0.01} info={HELP.ccDeltaMin} onChange={(v) => set("cc_delta_min", v)} />
                <Slider label="CC Delta Max" value={config.cc_delta_max} min={0.1} max={0.6} step={0.01} info={HELP.ccDeltaMax} onChange={(v) => set("cc_delta_max", v)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Slider label="CSP Delta Min" value={config.csp_delta_min} min={-0.6} max={-0.05} step={0.01} info={HELP.cspDeltaMin} onChange={(v) => set("csp_delta_min", v)} />
                <Slider label="CSP Delta Max" value={config.csp_delta_max} min={-0.5} max={-0.05} step={0.01} info={HELP.cspDeltaMax} onChange={(v) => set("csp_delta_max", v)} />
              </div>
            </div>
          </section>

          {/* Weights */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Scoring Weights</h3>
            <p className="text-gray-500 text-sm mb-4">Must sum to 1.00</p>
            <div className="space-y-4">
              <Slider label="IV" value={config.weight_iv} min={0} max={0.5} step={0.05} info={HELP.weightIv} onChange={(v) => set("weight_iv", v)} />
              <Slider label="Theta Yield" value={config.weight_theta_yield} min={0} max={0.5} step={0.05} info={HELP.weightTheta} onChange={(v) => set("weight_theta_yield", v)} />
              <Slider label="Delta Safety" value={config.weight_delta_safety} min={0} max={0.5} step={0.05} info={HELP.weightDelta} onChange={(v) => set("weight_delta_safety", v)} />
              <Slider label="Liquidity" value={config.weight_liquidity} min={0} max={0.5} step={0.05} info={HELP.weightLiquidity} onChange={(v) => set("weight_liquidity", v)} />
              <Slider label="Annual Return" value={config.weight_ann_return} min={0} max={0.5} step={0.05} info={HELP.weightReturn} onChange={(v) => set("weight_ann_return", v)} />
              <Slider label="Mean Reversion" value={config.weight_mean_reversion} min={0} max={0.5} step={0.05} info={HELP.weightMr} onChange={(v) => set("weight_mean_reversion", v)} />
            </div>
            <div className="mt-4 flex items-center gap-3">
              <input type="checkbox" id="use_mr" checked={config.use_mean_reversion} onChange={(e) => set("use_mean_reversion", e.target.checked)} className="accent-emerald-500" />
              <label htmlFor="use_mr" className="text-sm text-gray-400">
                <InfoLabel label="Enable Mean Reversion" info={HELP.useMr} />
              </label>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <input
                type="checkbox"
                id="mr_timing_confirmation"
                checked={config.mr_timing_confirmation ?? true}
                disabled={!config.use_mean_reversion}
                onChange={(e) => set("mr_timing_confirmation", e.target.checked)}
                className="accent-emerald-500 disabled:opacity-50"
              />
              <label htmlFor="mr_timing_confirmation" className="text-sm text-gray-400">
                <InfoLabel label="Require MR timing confirmation" info={HELP.mrTiming} />
                <span className="ml-2 text-xs text-gray-500">Recommended default: on</span>
              </label>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-4">
              <Slider label="MR Timing SMA" value={config.mr_timing_sma_period ?? 3} min={2} max={10} step={1} info={HELP.mrTimingSma} recommendation="Recommended default: 3" onChange={(v) => set("mr_timing_sma_period", v)} />
              <Slider label="Unconfirmed MR Cap" value={config.mr_timing_unconfirmed_cap ?? 0.75} min={0.5} max={1} step={0.05} info={HELP.mrCap} recommendation="Recommended default: 0.75" onChange={(v) => set("mr_timing_unconfirmed_cap", v)} />
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
