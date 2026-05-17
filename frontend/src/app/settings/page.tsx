"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Nav from "@/components/Nav";
import { useSession } from "@/hooks/useSession";
import { getConfig, updateConfig } from "@/lib/api";

interface ScannerConfig {
  tickers: string[];
  strategy: string;
  config_hash?: string;
  [key: string]: unknown;
}

type AppearanceMode = "dark" | "light" | "auto";
type LanguageId = "en" | "zh-TW" | "zh-CN" | "es" | "fr";
type AutoScanSchedule = "off" | "daily" | "weekly" | "market-open";
type MarketId = "US" | "UK" | "JP" | "HK" | "CA" | "AU";
type ChartTimeframe = "1D" | "5D" | "1M" | "3M" | "6M" | "1Y";

interface LocalPreferences {
  appearance: AppearanceMode;
  language: LanguageId;
  autoScanSchedule: AutoScanSchedule;
  autoScanTime: string;
  autoStarEnabled: boolean;
  autoStarScore: number;
  emailScanResults: boolean;
  saveScanParameters: boolean;
  stockMarkets: MarketId[];
  expiredPositionReminders: boolean;
  showClosedPositionsDefault: boolean;
  defaultChartTimeframe: ChartTimeframe;
}

const SETTINGS_STORAGE_KEY = "optionbot-settings-preferences";
const LANGUAGE_STORAGE_KEY = "optionbot-language";

const DEFAULT_PREFERENCES: LocalPreferences = {
  appearance: "dark",
  language: "en",
  autoScanSchedule: "off",
  autoScanTime: "08:30",
  autoStarEnabled: false,
  autoStarScore: 80,
  emailScanResults: false,
  saveScanParameters: true,
  stockMarkets: ["US"],
  expiredPositionReminders: true,
  showClosedPositionsDefault: true,
  defaultChartTimeframe: "1M",
};

const LANGUAGE_OPTIONS: Array<{ id: LanguageId; label: string; note: string }> = [
  { id: "en", label: "English", note: "Default app language" },
  { id: "zh-TW", label: "Traditional Chinese", note: "Planned full translation" },
  { id: "zh-CN", label: "Simplified Chinese", note: "Planned full translation" },
  { id: "es", label: "Spanish", note: "Planned full translation" },
  { id: "fr", label: "French", note: "Planned full translation" },
];

const MARKET_OPTIONS: Array<{ id: MarketId; label: string; note: string }> = [
  { id: "US", label: "USA", note: "US-listed equities and options" },
  { id: "UK", label: "UK", note: "UK market support" },
  { id: "JP", label: "Japan", note: "Japan market support" },
  { id: "HK", label: "Hong Kong", note: "Hong Kong market support" },
  { id: "CA", label: "Canada", note: "Canada market support" },
  { id: "AU", label: "Australia", note: "Australia market support" },
];

function loadPreferences(): LocalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const stored = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!stored) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function applyAppearance(mode: AppearanceMode) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.appearance = mode;
  if (mode === "auto") {
    const isLight = window.matchMedia("(prefers-color-scheme: light)").matches;
    document.documentElement.dataset.theme = isLight ? "light" : "dark";
  } else {
    document.documentElement.dataset.theme = mode;
  }
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-gray-800 bg-gray-900 p-6">
      <div className="grid gap-5 lg:grid-cols-[16rem_1fr]">
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-gray-400">{description}</p>
        </div>
        <div>{children}</div>
      </div>
    </section>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-lg border border-gray-800 bg-gray-950 px-4 py-3">
      <span>
        <span className="block text-sm font-medium text-white">{label}</span>
        <span className="mt-1 block text-sm leading-6 text-gray-500">{description}</span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 shrink-0 accent-emerald-500"
      />
    </label>
  );
}

export default function SettingsPage() {
  const { token } = useSession();
  const [config, setConfig] = useState<ScannerConfig | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [preferences, setPreferences] = useState<LocalPreferences>(() => loadPreferences());
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    applyAppearance(preferences.appearance);
    document.documentElement.lang = preferences.language;
  }, [preferences.appearance, preferences.language]);

  const loadConfig = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getConfig(token);
      setConfig(data);
      setTickerInput((data.tickers || []).join(", "));
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load settings.");
    }
  }, [token]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadConfig();
    });
  }, [loadConfig]);

  function updatePreference<K extends keyof LocalPreferences>(
    field: K,
    value: LocalPreferences[K]
  ) {
    const next = { ...preferences, [field]: value };
    setPreferences(next);
  }

  function toggleMarket(market: MarketId) {
    const exists = preferences.stockMarkets.includes(market);
    const nextMarkets = exists
      ? preferences.stockMarkets.filter((item) => item !== market)
      : [...preferences.stockMarkets, market];
    updatePreference("stockMarkets", nextMarkets.length ? nextMarkets : ["US"]);
  }

  async function handleSave() {
    if (!token || !config) return;
    setSaving(true);
    setSaved(false);
    setError("");

    try {
      const tickers = tickerInput
        .split(/[,\s]+/)
        .map((ticker) => ticker.trim().toUpperCase())
        .filter(Boolean);

      const updates = { ...config, tickers };
      delete (updates as Record<string, unknown>).config_hash;

      await updateConfig(token, updates);
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(preferences));
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, preferences.language);
      applyAppearance(preferences.appearance);
      document.documentElement.lang = preferences.language;
      setConfig({ ...config, tickers });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-8 border-b border-gray-800 pb-6">
          <p className="text-sm font-medium uppercase tracking-wide text-emerald-400">
            Settings
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-normal text-white">
            Personalize review, scan, and portfolio preferences.
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-gray-400">
            This page groups the main controls users expect before public launch:
            appearance, language, scan behavior, markets, and portfolio review
            defaults.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        {!config ? (
          <div className="rounded-xl border border-gray-800 bg-gray-900 px-6 py-12 text-center text-gray-500">
            Loading settings...
          </div>
        ) : (
          <div className="space-y-6">
            <Section
              title="Appearance"
              description="Choose how the app should present visual mode. Full light-mode polish can be expanded across the whole app after this shadow review."
            >
              <div className="grid gap-3 md:grid-cols-3">
                {(["dark", "light", "auto"] as AppearanceMode[]).map((mode) => {
                  const active = preferences.appearance === mode;
                  return (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => updatePreference("appearance", mode)}
                      className={`rounded-lg border px-4 py-3 text-left transition ${
                        active
                          ? "border-emerald-600 bg-emerald-950/40 text-white"
                          : "border-gray-800 bg-gray-950 text-gray-400 hover:border-gray-700 hover:text-white"
                      }`}
                    >
                      <span className="block text-sm font-semibold capitalize">{mode}</span>
                      <span className="mt-1 block text-xs leading-5 text-gray-500">
                        {mode === "auto"
                          ? "Follow system preference"
                          : `${mode.charAt(0).toUpperCase()}${mode.slice(1)} interface mode`}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Section>

            <Section
              title="Language"
              description="Keep the app language consistent. English remains the complete interface while additional translations are prepared."
            >
              <div className="grid gap-3 md:grid-cols-2">
                {LANGUAGE_OPTIONS.map((language) => {
                  const active = preferences.language === language.id;
                  return (
                    <button
                      key={language.id}
                      type="button"
                      onClick={() => updatePreference("language", language.id)}
                      className={`rounded-lg border px-4 py-3 text-left transition ${
                        active
                          ? "border-emerald-600 bg-emerald-950/40"
                          : "border-gray-800 bg-gray-950 hover:border-gray-700"
                      }`}
                    >
                      <span className="block text-sm font-medium text-white">
                        {language.label}
                      </span>
                      <span className="mt-1 block text-xs text-gray-500">
                        {language.note}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Section>

            <Section
              title="Scan Preferences"
              description="Set the common behaviors around scan timing, saved parameters, automatic shortlisting, email sharing, and market coverage."
            >
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-sm font-medium text-gray-300">Auto scan schedule</span>
                    <select
                      value={preferences.autoScanSchedule}
                      onChange={(e) =>
                        updatePreference("autoScanSchedule", e.target.value as AutoScanSchedule)
                      }
                      className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    >
                      <option value="off">Off</option>
                      <option value="market-open">Market open</option>
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-sm font-medium text-gray-300">Preferred scan time</span>
                    <input
                      type="time"
                      value={preferences.autoScanTime}
                      disabled={preferences.autoScanSchedule === "off"}
                      onChange={(e) => updatePreference("autoScanTime", e.target.value)}
                      className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                    />
                  </label>
                </div>

                <Toggle
                  checked={preferences.saveScanParameters}
                  onChange={(checked) => updatePreference("saveScanParameters", checked)}
                  label="Keep last adjusted scan parameters"
                  description="The Scan page keeps the latest saved scan settings so the next review starts from the same profile."
                />
                <Toggle
                  checked={preferences.emailScanResults}
                  onChange={(checked) => updatePreference("emailScanResults", checked)}
                  label="Email scan results"
                  description="Store the preference for sending scan summaries by email when the backend notification step is wired."
                />
                <div className="rounded-lg border border-gray-800 bg-gray-950 px-4 py-3">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-sm font-medium text-white">Auto-star high scoring contracts</p>
                      <p className="mt-1 text-sm leading-6 text-gray-500">
                        Save a preferred score threshold for future automatic candidate shortlisting.
                      </p>
                    </div>
                    <label className="flex items-center gap-2 text-sm text-gray-300">
                      <input
                        type="checkbox"
                        checked={preferences.autoStarEnabled}
                        onChange={(e) => updatePreference("autoStarEnabled", e.target.checked)}
                        className="accent-emerald-500"
                      />
                      Enable
                    </label>
                  </div>
                  <div className="mt-4 flex items-center gap-4">
                    <input
                      type="range"
                      min={50}
                      max={100}
                      step={5}
                      value={preferences.autoStarScore}
                      disabled={!preferences.autoStarEnabled}
                      onChange={(e) =>
                        updatePreference("autoStarScore", Number(e.target.value))
                      }
                      className="w-full accent-emerald-500 disabled:opacity-40"
                    />
                    <span className="w-10 text-right font-mono text-sm text-white">
                      {preferences.autoStarScore}
                    </span>
                  </div>
                </div>

                <div>
                  <p className="mb-3 text-sm font-medium text-gray-300">Stock markets</p>
                  <div className="grid gap-3 md:grid-cols-3">
                    {MARKET_OPTIONS.map((market) => {
                      const active = preferences.stockMarkets.includes(market.id);
                      return (
                        <button
                          key={market.id}
                          type="button"
                          onClick={() => toggleMarket(market.id)}
                          className={`rounded-lg border px-4 py-3 text-left transition ${
                            active
                              ? "border-emerald-600 bg-emerald-950/40"
                              : "border-gray-800 bg-gray-950 hover:border-gray-700"
                          }`}
                        >
                          <span className="block text-sm font-medium text-white">
                            {market.label}
                          </span>
                          <span className="mt-1 block text-xs text-gray-500">
                            {market.note}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </Section>

            <Section
              title="Default Scan Profile"
              description="Keep the most common scan profile close by. Detailed scoring and Greek filters remain in the full parameter page."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-gray-300">Tickers</span>
                  <input
                    type="text"
                    value={tickerInput}
                    onChange={(e) => setTickerInput(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    placeholder="TSLA, NVDA, AAPL"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-medium text-gray-300">Strategy</span>
                  <select
                    value={config.strategy}
                    onChange={(e) => setConfig({ ...config, strategy: e.target.value })}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  >
                    <option value="both">Covered Calls + Cash-Secured Puts</option>
                    <option value="cc">Covered Calls only</option>
                    <option value="csp">Cash-Secured Puts only</option>
                  </select>
                </label>
              </div>
              <div className="mt-4">
                <Link
                  href="/scan/parameters"
                  className="inline-flex rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-gray-600 hover:bg-gray-800"
                >
                  Open full scan parameters
                </Link>
              </div>
            </Section>

            <Section
              title="Portfolio Preferences"
              description="Set review defaults for positions that need attention after entry."
            >
              <div className="space-y-4">
                <Toggle
                  checked={preferences.expiredPositionReminders}
                  onChange={(checked) =>
                    updatePreference("expiredPositionReminders", checked)
                  }
                  label="Highlight expired open positions"
                  description="Keep expired trades visible in Open Positions until the user records the actual outcome."
                />
                <Toggle
                  checked={preferences.showClosedPositionsDefault}
                  onChange={(checked) =>
                    updatePreference("showClosedPositionsDefault", checked)
                  }
                  label="Show closed positions by default"
                  description="Keep closed and manually resolved trades easy to review."
                />
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-gray-300">
                    Default chart timeframe
                  </span>
                  <select
                    value={preferences.defaultChartTimeframe}
                    onChange={(e) =>
                      updatePreference(
                        "defaultChartTimeframe",
                        e.target.value as ChartTimeframe
                      )
                    }
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 md:max-w-xs"
                  >
                    <option value="1D">1D</option>
                    <option value="5D">5D</option>
                    <option value="1M">1M</option>
                    <option value="3M">3M</option>
                    <option value="6M">6M</option>
                    <option value="1Y">1Y</option>
                  </select>
                </label>
              </div>
            </Section>

            <div className="flex flex-wrap items-center gap-4 pb-4">
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:bg-gray-700"
              >
                {saving ? "Saving..." : "Save Settings"}
              </button>
              {saved && <span className="text-sm text-emerald-400">Settings saved.</span>}
              {config.config_hash && (
                <span className="ml-auto text-xs font-mono text-gray-600">
                  Config: {config.config_hash.slice(0, 12)}...
                </span>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
