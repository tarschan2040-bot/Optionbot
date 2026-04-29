"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase";
import { useRouter } from "next/navigation";
import { getConfig, updateConfig } from "@/lib/api";
import Link from "next/link";

interface ScannerConfig {
  tickers: string[];
  strategy: string;
  data_source: string;
  min_dte: number;
  max_dte: number;
  cc_delta_min: number;
  cc_delta_max: number;
  csp_delta_min: number;
  csp_delta_max: number;
  min_theta: number;
  min_iv: number;
  min_iv_rank: number;
  min_annualised_return: number;
  min_premium: number;
  max_bid_ask_spread_pct: number;
  weight_iv: number;
  weight_theta_yield: number;
  weight_delta_safety: number;
  weight_liquidity: number;
  weight_ann_return: number;
  weight_mean_reversion: number;
  use_mean_reversion: boolean;
  config_hash: string;
  [key: string]: unknown;
}

function ConfigSlider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-white font-mono">
          {value.toFixed(step < 1 ? 2 : 0)}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-emerald-500"
      />
    </div>
  );
}

export default function SettingsPage() {
  const [session, setSession] = useState<{ access_token: string } | null>(null);
  const [config, setConfig] = useState<ScannerConfig | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.push("/login");
        return;
      }
      setSession(session);
    });
  }, [router, supabase.auth]);

  const loadConfig = useCallback(async () => {
    if (!session) return;
    try {
      const data = await getConfig(session.access_token);
      setConfig(data);
      setTickerInput(data.tickers.join(", "));
    } catch (err) {
      setError("Failed to load config.");
    }
  }, [session]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  async function handleSave() {
    if (!session || !config) return;
    setSaving(true);
    setError("");
    setSaved(false);

    try {
      // Parse tickers from input
      const tickers = tickerInput
        .split(/[,\s]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);

      const updates = { ...config, tickers };
      delete (updates as Record<string, unknown>).config_hash;

      await updateConfig(session.access_token, updates);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      loadConfig();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  function updateField(field: string, value: unknown) {
    if (!config) return;
    setConfig({ ...config, [field]: value });
  }

  if (!session || !config) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/dashboard" className="text-xl font-bold">
          Option<span className="text-emerald-400">Bot</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            Dashboard
          </Link>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold mb-8">Scanner Settings</h2>

        {error && (
          <div className="mb-6 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-8">
          {/* Watchlist */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Watchlist</h3>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Tickers (comma separated)
              </label>
              <input
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value)}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                placeholder="TSLA, NVDA, AAPL, MSFT"
              />
            </div>
            <div className="mt-4">
              <label className="block text-sm text-gray-400 mb-1">Strategy</label>
              <select
                value={config.strategy}
                onChange={(e) => updateField("strategy", e.target.value)}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="both">Covered Calls + Cash-Secured Puts</option>
                <option value="cc">Covered Calls only</option>
                <option value="csp">Cash-Secured Puts only</option>
              </select>
            </div>
          </section>

          {/* Filters */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Filters</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <ConfigSlider
                  label="Min DTE"
                  value={config.min_dte}
                  min={7}
                  max={90}
                  step={1}
                  onChange={(v) => updateField("min_dte", v)}
                />
                <ConfigSlider
                  label="Max DTE"
                  value={config.max_dte}
                  min={14}
                  max={120}
                  step={1}
                  onChange={(v) => updateField("max_dte", v)}
                />
              </div>
              <ConfigSlider
                label="Min IV (raw)"
                value={config.min_iv}
                min={0}
                max={1.5}
                step={0.05}
                suffix=""
                onChange={(v) => updateField("min_iv", v)}
              />
              <ConfigSlider
                label="Min Premium"
                value={config.min_premium}
                min={0}
                max={10}
                step={0.25}
                suffix="$"
                onChange={(v) => updateField("min_premium", v)}
              />
              <ConfigSlider
                label="Min Annualised Return"
                value={config.min_annualised_return}
                min={0}
                max={0.5}
                step={0.01}
                onChange={(v) => updateField("min_annualised_return", v)}
              />
              <ConfigSlider
                label="Min Theta"
                value={config.min_theta}
                min={0}
                max={0.5}
                step={0.01}
                onChange={(v) => updateField("min_theta", v)}
              />
            </div>
          </section>

          {/* Delta Range */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Delta Range</h3>
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <ConfigSlider
                  label="CC Delta Min"
                  value={config.cc_delta_min}
                  min={0.05}
                  max={0.5}
                  step={0.01}
                  onChange={(v) => updateField("cc_delta_min", v)}
                />
                <ConfigSlider
                  label="CC Delta Max"
                  value={config.cc_delta_max}
                  min={0.1}
                  max={0.6}
                  step={0.01}
                  onChange={(v) => updateField("cc_delta_max", v)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <ConfigSlider
                  label="CSP Delta Min"
                  value={config.csp_delta_min}
                  min={-0.6}
                  max={-0.05}
                  step={0.01}
                  onChange={(v) => updateField("csp_delta_min", v)}
                />
                <ConfigSlider
                  label="CSP Delta Max"
                  value={config.csp_delta_max}
                  min={-0.5}
                  max={-0.05}
                  step={0.01}
                  onChange={(v) => updateField("csp_delta_max", v)}
                />
              </div>
            </div>
          </section>

          {/* Scoring Weights */}
          <section className="bg-gray-900 rounded-xl p-6 border border-gray-800">
            <h3 className="text-lg font-semibold mb-4">Scoring Weights</h3>
            <p className="text-gray-500 text-sm mb-4">Must sum to 1.00</p>
            <div className="space-y-4">
              <ConfigSlider
                label="IV"
                value={config.weight_iv}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_iv", v)}
              />
              <ConfigSlider
                label="Theta Yield"
                value={config.weight_theta_yield}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_theta_yield", v)}
              />
              <ConfigSlider
                label="Delta Safety"
                value={config.weight_delta_safety}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_delta_safety", v)}
              />
              <ConfigSlider
                label="Liquidity"
                value={config.weight_liquidity}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_liquidity", v)}
              />
              <ConfigSlider
                label="Annual Return"
                value={config.weight_ann_return}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_ann_return", v)}
              />
              <ConfigSlider
                label="Mean Reversion"
                value={config.weight_mean_reversion}
                min={0}
                max={0.5}
                step={0.05}
                onChange={(v) => updateField("weight_mean_reversion", v)}
              />
            </div>
            <div className="mt-4 flex items-center gap-3">
              <input
                type="checkbox"
                id="use_mr"
                checked={config.use_mean_reversion}
                onChange={(e) => updateField("use_mean_reversion", e.target.checked)}
                className="accent-emerald-500"
              />
              <label htmlFor="use_mr" className="text-sm text-gray-400">
                Enable Mean Reversion scoring
              </label>
            </div>
          </section>

          {/* Save */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-8 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white font-semibold rounded-lg transition-colors"
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
            {saved && (
              <span className="text-emerald-400 text-sm">Settings saved!</span>
            )}
            <span className="text-gray-600 text-xs ml-auto font-mono">
              Hash: {config.config_hash?.slice(0, 12)}...
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
