"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import { useRouter } from "next/navigation";
import { getConfig, updateConfig, getScanResults, triggerScan, getScanStatus, starCandidate } from "@/lib/api";
import Link from "next/link";

interface ScanResult {
  rank: number; ticker: string; strategy: string; strike: number;
  expiry: string; dte: number; premium: number; delta: number;
  theta: number; iv: number; ann_return: number; score: number;
}

interface ScanData {
  scan_time: string | null; slot_label: string | null;
  config_hash: string | null; result_count: number; results: ScanResult[];
  tier: string | null; visible_results: number | null;
  scans_remaining: number | null; scans_per_day: number | null; can_scan: boolean;
}

interface ScannerConfig {
  tickers: string[];
  strategy: string;
  min_dte: number;
  max_dte: number;
  min_premium: number;
  min_annualised_return: number;
  cc_delta_min: number;
  cc_delta_max: number;
  csp_delta_min: number;
  csp_delta_max: number;
  config_hash?: string;
  [key: string]: unknown;
}

type SortKey = keyof ScanResult;
type SortDir = "asc" | "desc";

export default function ScanPage() {
  const { token } = useSession();
  const [scanData, setScanData] = useState<ScanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [minScore, setMinScore] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [starred, setStarred] = useState<Set<string>>(new Set());
  const [config, setConfig] = useState<ScannerConfig | null>(null);
  const [tickerInput, setTickerInput] = useState("");
  const [savingConfig, setSavingConfig] = useState(false);
  const [configError, setConfigError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const router = useRouter();

  const loadResults = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try { setScanData(await getScanResults(token)); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token]);

  const loadConfig = useCallback(async () => {
    if (!token) return;
    try {
      const d = await getConfig(token);
      setConfig(d);
      setTickerInput((d.tickers || []).join(", "));
      setConfigError("");
    } catch (err: unknown) {
      setConfigError(err instanceof Error ? err.message : "Failed to load scan parameters.");
    }
  }, [token]);

  useEffect(() => { queueMicrotask(() => { void loadResults(); }); }, [loadResults]);
  useEffect(() => { queueMicrotask(() => { void loadConfig(); }); }, [loadConfig]);
  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); if (timerRef.current) clearInterval(timerRef.current); }; }, []);

  // Tier info
  const tier = scanData?.tier || "free";
  const visibleLimit = scanData?.visible_results;  // null = all visible
  const canScan = scanData?.can_scan ?? true;
  const scansRemaining = scanData?.scans_remaining;
  const scansPerDay = scanData?.scans_per_day;

  const displayResults = useMemo(() => {
    if (!scanData?.results) return [];
    const filtered = scanData.results.filter((r) => r.score >= minScore);
    filtered.sort((a, b) => {
      const aV = a[sortKey] ?? 0, bV = b[sortKey] ?? 0;
      if (typeof aV === "string" && typeof bV === "string") return sortDir === "asc" ? aV.localeCompare(bV) : bV.localeCompare(aV);
      return sortDir === "asc" ? (aV as number) - (bV as number) : (bV as number) - (aV as number);
    });
    return filtered;
  }, [scanData, minScore, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  }
  function si(key: SortKey) { return sortKey !== key ? "" : sortDir === "asc" ? " ▲" : " ▼"; }
  function setConfigField(field: keyof ScannerConfig, value: unknown) {
    if (config) setConfig({ ...config, [field]: value });
  }
  function quickConfigPayload() {
    if (!config) return null;
    const tickers = tickerInput.split(/[,\s]+/).map((t) => t.trim().toUpperCase()).filter(Boolean);
    const updates = { ...config, tickers };
    delete (updates as Record<string, unknown>).config_hash;
    return updates;
  }
  async function saveQuickConfig(showMessage = true) {
    if (!token || !config) return;
    setSavingConfig(true);
    setConfigError("");
    try {
      const updates = quickConfigPayload();
      if (!updates) return;
      await updateConfig(token, updates);
      setConfig({ ...config, tickers: updates.tickers as string[] });
      if (showMessage) {
        setScanMessage("Parameters saved.");
        setTimeout(() => setScanMessage(""), 2500);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save scan parameters.";
      setConfigError(msg);
      throw err;
    } finally {
      setSavingConfig(false);
    }
  }

  function startPolling() {
    if (!token) return;
    timerRef.current = setInterval(() => setElapsed((current) => current + 1), 1000);
    pollRef.current = setInterval(async () => {
      try { const s = await getScanStatus(token); if (!s.running) { stopPolling(); setScanning(false); setScanMessage("Scan complete!"); loadResults(); setTimeout(() => setScanMessage(""), 3000); } } catch {}
    }, 5000);
  }
  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setElapsed(0);
  }

  async function handleScan() {
    if (!token || !canScan) return;
    setScanning(true); setScanMessage(""); setElapsed(0);
    try {
      await saveQuickConfig(false);
      const r = await triggerScan(token);
      setScanMessage(r.message);
      startPolling();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start scan.";
      if (msg.includes("429") || msg.includes("limit")) {
        setScanMessage("Daily scan limit reached. Upgrade for more scans.");
      } else {
        setScanMessage(msg);
      }
      setScanning(false);
    }
  }

  async function handleStar(r: ScanResult, e: React.MouseEvent) {
    e.stopPropagation();
    if (!token) return;
    const key = `${r.ticker}-${r.strike}-${r.expiry}-${r.strategy}`;
    if (starred.has(key)) return;
    try {
      await starCandidate(token, { ticker: r.ticker, strategy: r.strategy, strike: r.strike, expiry: r.expiry, dte: r.dte, delta: r.delta, theta: r.theta, premium: r.premium, score: r.score, iv: r.iv, ann_return: r.ann_return });
      setStarred(new Set([...starred, key]));
    } catch (err) { console.error(err); }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <section className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-5">
          <h1 className="text-lg font-semibold text-white">How The Scan Works</h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-gray-300">
            OptionBot reviews the stocks and strategy settings you select, then screens available option contracts against your filters, including expiry range, strike, premium, delta, implied volatility, expected return, and risk limits.
          </p>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-gray-300">
            Each result is scored and ranked so you can focus on the contracts that best match your criteria. You can star any contract you want to review later; starred ideas are saved to your portfolio candidate list, where you can take further action when ready.
          </p>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-gray-400">
            The scan is designed to support your review process. It does not place trades or provide financial advice.
          </p>
        </section>

        <section className="mb-6 rounded-xl border border-gray-800 bg-gray-900 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Current Scan Conditions</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-400">
                Adjust the most common filters here, then start a scan with the same settings.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {scansPerDay != null && (
                <div className="text-sm text-gray-400">
                  <span className={scansRemaining === 0 ? "font-medium text-red-400" : "font-medium text-emerald-400"}>
                    {scansRemaining}
                  </span>
                  <span>/{scansPerDay} scans left today</span>
                </div>
              )}
              {scansPerDay == null && tier === "max" && (
                <div className="text-sm text-gray-400">Unlimited scans</div>
              )}
              <Link
                href="/scan/parameters"
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:border-gray-600 hover:bg-gray-800"
              >
                Parameter
              </Link>
              <button
                onClick={handleScan}
                disabled={scanning || savingConfig || !canScan}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  !canScan
                    ? "cursor-not-allowed border border-gray-700 bg-gray-800 text-gray-500"
                    : scanning || savingConfig
                    ? "bg-gray-700 text-gray-300"
                    : "bg-emerald-600 text-white hover:bg-emerald-500"
                }`}
              >
                {scanning ? (
                  <>Scanning... {elapsed > 0 && `${elapsed}s`}</>
                ) : savingConfig ? (
                  "Saving..."
                ) : !canScan ? (
                  "Limit Reached"
                ) : (
                  "Start Scan"
                )}
              </button>
            </div>
          </div>

          {configError && (
            <div className="mt-4 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {configError}
            </div>
          )}

          {config ? (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Tickers</span>
                <input
                  type="text"
                  value={tickerInput}
                  onChange={(e) => setTickerInput(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  placeholder="TSLA, NVDA, AAPL"
                />
              </label>

              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Strategy</span>
                <select
                  value={config.strategy}
                  onChange={(e) => setConfigField("strategy", e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="both">Covered Calls + Cash-Secured Puts</option>
                  <option value="cc">Covered Calls only</option>
                  <option value="csp">Cash-Secured Puts only</option>
                </select>
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Min DTE</span>
                  <input
                    type="number"
                    min={0}
                    value={config.min_dte}
                    onChange={(e) => setConfigField("min_dte", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Max DTE</span>
                  <input
                    type="number"
                    min={0}
                    value={config.max_dte}
                    onChange={(e) => setConfigField("max_dte", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Min Premium</span>
                  <input
                    type="number"
                    min={0}
                    step={0.25}
                    value={config.min_premium}
                    onChange={(e) => setConfigField("min_premium", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Min Ann. Return %</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={Number((config.min_annualised_return * 100).toFixed(1))}
                    onChange={(e) => setConfigField("min_annualised_return", Number(e.target.value) / 100)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">CC Delta Min</span>
                  <input
                    type="number"
                    step={0.01}
                    value={config.cc_delta_min}
                    onChange={(e) => setConfigField("cc_delta_min", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">CC Delta Max</span>
                  <input
                    type="number"
                    step={0.01}
                    value={config.cc_delta_max}
                    onChange={(e) => setConfigField("cc_delta_max", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">CSP Delta Min</span>
                  <input
                    type="number"
                    step={0.01}
                    value={config.csp_delta_min}
                    onChange={(e) => setConfigField("csp_delta_min", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500">CSP Delta Max</span>
                  <input
                    type="number"
                    step={0.01}
                    value={config.csp_delta_max}
                    onChange={(e) => setConfigField("csp_delta_max", Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </label>
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-lg border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-500">
              Loading current scan conditions...
            </div>
          )}
        </section>

        {/* Limit reached upgrade prompt */}
        {!canScan && (
          <div className="mb-6 p-4 bg-gray-900 border border-gray-800 rounded-xl flex items-center justify-between">
            <div>
              <p className="text-white font-medium">Daily scan limit reached</p>
              <p className="text-gray-400 text-sm mt-1">
                {tier === "free" ? "Free plan: 3 scans/day. " : "Pro plan: 30 scans/day. "}
                Upgrade for more scans.
              </p>
            </div>
            <Link href="/account/plans" className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors">
              Upgrade
            </Link>
          </div>
        )}

        {scanData?.scan_time && (
          <p className="text-gray-400 text-sm mb-4">
            Last scan: {new Date(scanData.scan_time).toLocaleString()}
            {scanData.slot_label && ` (${scanData.slot_label})`}
            {scanData.result_count > 0 && ` · ${scanData.result_count} opportunities`}
          </p>
        )}

        {scanMessage && <div className="mb-4 p-3 bg-blue-900/30 border border-blue-700 rounded-lg text-blue-300 text-sm">{scanMessage}</div>}

        {/* Filter */}
        {scanData && scanData.result_count > 0 && (
          <div className="flex items-center gap-6 mb-6 p-4 bg-gray-900 rounded-xl border border-gray-800">
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-400">Min Score:</label>
              <input type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(parseInt(e.target.value))} className="w-32 accent-emerald-500" />
              <span className="text-sm font-mono text-white w-8">{minScore}</span>
            </div>
            <span className="text-gray-600 text-sm">Showing {displayResults.length} of {scanData.result_count}</span>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="text-center py-20 text-gray-500">Loading results...</div>
        ) : !scanData || scanData.result_count === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500 text-lg">No scan results yet.</p>
            <p className="text-gray-600 text-sm mt-2">Click &quot;Start Scan&quot; to find opportunities.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-left">
                  <th className="pb-3 pr-2 w-8"></th>
                  <th className="pb-3 pr-3 cursor-pointer hover:text-white" onClick={() => handleSort("rank")}>#{si("rank")}</th>
                  <th className="pb-3 pr-3 cursor-pointer hover:text-white" onClick={() => handleSort("ticker")}>Ticker{si("ticker")}</th>
                  <th className="pb-3 pr-3">Strategy</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("strike")}>Strike{si("strike")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("expiry")}>Expiry{si("expiry")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("dte")}>DTE{si("dte")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("premium")}>Premium{si("premium")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("delta")}>Delta{si("delta")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("theta")}>Theta{si("theta")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("iv")}>IV{si("iv")}</th>
                  <th className="pb-3 pr-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("ann_return")}>Ann%{si("ann_return")}</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("score")}>Score{si("score")}</th>
                </tr>
              </thead>
              <tbody>
                {displayResults.map((r, idx) => {
                  const key = `${r.ticker}-${r.strike}-${r.expiry}-${r.strategy}`;
                  const isStar = starred.has(key);
                  const isBlurred = visibleLimit != null && idx >= visibleLimit;

                  return (
                    <tr
                      key={key}
                      onClick={() => !isBlurred && router.push(`/scan/detail/${r.rank}`)}
                      className={`border-b border-gray-800/50 transition-colors ${
                        isBlurred
                          ? "cursor-default"
                          : "hover:bg-gray-900/50 cursor-pointer"
                      }`}
                    >
                      <td className="py-3 pr-2">
                        {!isBlurred && (
                          <button onClick={(e) => handleStar(r, e)} className={`text-lg transition-colors ${isStar ? "text-yellow-400" : "text-gray-600 hover:text-yellow-400"}`}>{isStar ? "★" : "☆"}</button>
                        )}
                      </td>
                      <td className="py-3 pr-3 text-gray-500">{r.rank}</td>
                      <td className={`py-3 pr-3 font-semibold ${isBlurred ? "blur-sm select-none" : ""}`}>{r.ticker}</td>
                      <td className="py-3 pr-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.strategy === "COVERED_CALL" ? "bg-blue-900/50 text-blue-300" : "bg-purple-900/50 text-purple-300"} ${isBlurred ? "blur-sm" : ""}`}>
                          {r.strategy === "COVERED_CALL" ? "CC" : "CSP"}
                        </span>
                      </td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>${r.strike.toFixed(2)}</td>
                      <td className={`py-3 pr-3 text-right text-gray-400 ${isBlurred ? "blur-sm select-none" : ""}`}>{r.expiry}</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>{r.dte}</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>${r.premium.toFixed(2)}</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>{r.delta.toFixed(3)}</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>${r.theta.toFixed(3)}</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>{(r.iv * 100).toFixed(1)}%</td>
                      <td className={`py-3 pr-3 text-right ${isBlurred ? "blur-sm select-none" : ""}`}>{(r.ann_return * 100).toFixed(1)}%</td>
                      <td className="py-3 text-right">
                        <span className={`font-bold ${r.score >= 70 ? "text-emerald-400" : r.score >= 50 ? "text-yellow-400" : "text-red-400"} ${isBlurred ? "blur-sm" : ""}`}>
                          {r.score.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Upgrade prompt below blurred results */}
            {visibleLimit != null && displayResults.length > visibleLimit && (
              <div className="mt-6 p-6 bg-gray-900 border border-gray-800 rounded-xl text-center">
                <p className="text-white font-medium mb-2">
                  {displayResults.length - visibleLimit} more opportunities hidden
                </p>
                <p className="text-gray-400 text-sm mb-4">
                  Upgrade to Pro or Max to see all scan results with full details.
                </p>
                <Link href="/account/plans" className="inline-block px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors">
                  View Plans
                </Link>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
