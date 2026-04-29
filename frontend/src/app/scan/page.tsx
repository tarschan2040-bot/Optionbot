"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import { useRouter } from "next/navigation";
import { getScanResults, triggerScan, getScanStatus, starCandidate } from "@/lib/api";
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

  useEffect(() => { loadResults(); }, [loadResults]);
  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); if (timerRef.current) clearInterval(timerRef.current); }; }, []);

  // Tier info
  const tier = scanData?.tier || "free";
  const visibleLimit = scanData?.visible_results;  // null = all visible
  const canScan = scanData?.can_scan ?? true;
  const scansRemaining = scanData?.scans_remaining;
  const scansPerDay = scanData?.scans_per_day;

  const displayResults = useMemo(() => {
    if (!scanData?.results) return [];
    let filtered = scanData.results.filter((r) => r.score >= minScore);
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

  function startPolling() {
    if (!token) return;
    const t0 = Date.now();
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
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
        {/* Sub-nav + Scan button */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
            <span className="px-4 py-2 rounded-md text-sm font-medium bg-gray-800 text-white">Results</span>
            <Link href="/scan/parameters" className="px-4 py-2 rounded-md text-sm font-medium text-gray-400 hover:text-white transition-colors">Parameters</Link>
          </div>
          <div className="flex items-center gap-3">
            {/* Scan counter */}
            {scansPerDay != null && (
              <div className="text-sm text-gray-400">
                <span className={scansRemaining === 0 ? "text-red-400 font-medium" : "text-emerald-400 font-medium"}>
                  {scansRemaining}
                </span>
                <span>/{scansPerDay} scans left today</span>
              </div>
            )}
            {scansPerDay == null && tier === "max" && (
              <div className="text-sm text-gray-400">Unlimited scans</div>
            )}
            <button
              onClick={handleScan}
              disabled={scanning || !canScan}
              className={`px-6 py-2.5 font-medium rounded-lg transition-colors flex items-center gap-2 ${
                !canScan
                  ? "bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700"
                  : scanning
                  ? "bg-gray-700 text-gray-300"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white"
              }`}
            >
              {scanning ? (
                <><span className="inline-block animate-spin">⟳</span> Scanning... {elapsed > 0 && `${elapsed}s`}</>
              ) : !canScan ? (
                "Limit Reached"
              ) : (
                "Run Scan"
              )}
            </button>
          </div>
        </div>

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
            <p className="text-gray-600 text-sm mt-2">Click &quot;Run Scan&quot; to find opportunities.</p>
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
