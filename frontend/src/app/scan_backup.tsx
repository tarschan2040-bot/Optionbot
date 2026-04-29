"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { createClient } from "@/lib/supabase";
import { useRouter } from "next/navigation";
import { getScanResults, triggerScan, getScanStatus, starCandidate } from "@/lib/api";
import Link from "next/link";

interface ScanResult {
  rank: number;
  ticker: string;
  strategy: string;
  strike: number;
  expiry: string;
  dte: number;
  premium: number;
  delta: number;
  theta: number;
  iv: number;
  ann_return: number;
  score: number;
}

interface ScanData {
  scan_time: string | null;
  slot_label: string | null;
  config_hash: string | null;
  result_count: number;
  results: ScanResult[];
}

type SortKey = keyof ScanResult;
type SortDir = "asc" | "desc";

export default function DashboardPage() {
  const [session, setSession] = useState<{ access_token: string } | null>(null);
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
  const supabase = createClient();

  // Check auth
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.push("/login");
        return;
      }
      setSession(session);
    });
  }, [router, supabase.auth]);

  // Load results
  const loadResults = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    try {
      const data = await getScanResults(session.access_token);
      setScanData(data);
    } catch (err) {
      console.error("Failed to load results:", err);
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Filtered + sorted results
  const displayResults = useMemo(() => {
    if (!scanData?.results) return [];
    let filtered = scanData.results.filter((r) => r.score >= minScore);
    filtered.sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      return sortDir === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
    return filtered;
  }, [scanData, minScore, sortKey, sortDir]);

  // Sort handler
  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  }

  // Polling
  function startPolling() {
    if (!session) return;
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    pollRef.current = setInterval(async () => {
      try {
        const status = await getScanStatus(session.access_token);
        if (!status.running) {
          stopPolling();
          setScanning(false);
          setScanMessage("Scan complete!");
          loadResults();
          setTimeout(() => setScanMessage(""), 3000);
        }
      } catch {
        /* keep polling */
      }
    }, 5000);
  }

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setElapsed(0);
  }

  async function handleScan() {
    if (!session) return;
    setScanning(true);
    setScanMessage("");
    setElapsed(0);
    try {
      const res = await triggerScan(session.access_token);
      setScanMessage(res.message);
      startPolling();
    } catch {
      setScanMessage("Failed to start scan.");
      setScanning(false);
    }
  }

  // Star a candidate
  async function handleStar(r: ScanResult, e: React.MouseEvent) {
    e.stopPropagation(); // don't navigate to detail
    if (!session) return;
    const key = `${r.ticker}-${r.strike}-${r.expiry}-${r.strategy}`;
    if (starred.has(key)) return;
    try {
      await starCandidate(session.access_token, {
        ticker: r.ticker,
        strategy: r.strategy,
        strike: r.strike,
        expiry: r.expiry,
        dte: r.dte,
        delta: r.delta,
        theta: r.theta,
        premium: r.premium,
        score: r.score,
        iv: r.iv,
        ann_return: r.ann_return,
      });
      setStarred(new Set([...starred, key]));
    } catch (err) {
      console.error("Star failed:", err);
    }
  }

  async function handleSignOut() {
    stopPolling();
    await supabase.auth.signOut();
    router.push("/login");
  }

  if (!session) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">
          Option<span className="text-emerald-400">Bot</span>
        </h1>
        <div className="flex items-center gap-4">
          <Link href="/portfolio" className="text-gray-400 hover:text-white text-sm transition-colors">
            Portfolio
          </Link>
          <Link href="/settings" className="text-gray-400 hover:text-white text-sm transition-colors">
            Settings
          </Link>
          <button onClick={handleSignOut} className="text-gray-400 hover:text-white text-sm transition-colors">
            Sign Out
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold">Scan Results</h2>
            {scanData?.scan_time && (
              <p className="text-gray-400 text-sm mt-1">
                Last scan: {new Date(scanData.scan_time).toLocaleString()}
                {scanData.slot_label && ` (${scanData.slot_label})`}
                {scanData.result_count > 0 && ` · ${scanData.result_count} opportunities`}
              </p>
            )}
          </div>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
          >
            {scanning ? (
              <>
                <span className="inline-block animate-spin">⟳</span>
                Scanning... {elapsed > 0 && `${elapsed}s`}
              </>
            ) : (
              "Run Scan"
            )}
          </button>
        </div>

        {scanMessage && (
          <div className="mb-6 p-3 bg-blue-900/30 border border-blue-700 rounded-lg text-blue-300 text-sm">
            {scanMessage}
          </div>
        )}

        {/* Filter bar */}
        {scanData && scanData.result_count > 0 && (
          <div className="flex items-center gap-6 mb-6 p-4 bg-gray-900 rounded-xl border border-gray-800">
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-400">Min Score:</label>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={minScore}
                onChange={(e) => setMinScore(parseInt(e.target.value))}
                className="w-32 accent-emerald-500"
              />
              <span className="text-sm font-mono text-white w-8">{minScore}</span>
            </div>
            <span className="text-gray-600 text-sm">
              Showing {displayResults.length} of {scanData.result_count}
            </span>
          </div>
        )}

        {/* Results table */}
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
                  <th className="pb-3 pr-4 cursor-pointer hover:text-white" onClick={() => handleSort("rank")}>#{sortIndicator("rank")}</th>
                  <th className="pb-3 pr-4 cursor-pointer hover:text-white" onClick={() => handleSort("ticker")}>Ticker{sortIndicator("ticker")}</th>
                  <th className="pb-3 pr-4">Strategy</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("strike")}>Strike{sortIndicator("strike")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("expiry")}>Expiry{sortIndicator("expiry")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("dte")}>DTE{sortIndicator("dte")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("premium")}>Premium{sortIndicator("premium")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("delta")}>Delta{sortIndicator("delta")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("theta")}>Theta{sortIndicator("theta")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("iv")}>IV{sortIndicator("iv")}</th>
                  <th className="pb-3 pr-4 text-right cursor-pointer hover:text-white" onClick={() => handleSort("ann_return")}>Ann%{sortIndicator("ann_return")}</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => handleSort("score")}>Score{sortIndicator("score")}</th>
                </tr>
              </thead>
              <tbody>
                {displayResults.map((r) => {
                  const key = `${r.ticker}-${r.strike}-${r.expiry}-${r.strategy}`;
                  const isStarred = starred.has(key);
                  return (
                    <tr
                      key={key}
                      onClick={() => router.push(`/dashboard/detail/${r.rank}`)}
                      className="border-b border-gray-800/50 hover:bg-gray-900/50 transition-colors cursor-pointer"
                    >
                      <td className="py-3 pr-2">
                        <button
                          onClick={(e) => handleStar(r, e)}
                          className={`text-lg transition-colors ${isStarred ? "text-yellow-400" : "text-gray-600 hover:text-yellow-400"}`}
                          title={isStarred ? "Starred" : "Star this candidate"}
                        >
                          {isStarred ? "★" : "☆"}
                        </button>
                      </td>
                      <td className="py-3 pr-4 text-gray-500">{r.rank}</td>
                      <td className="py-3 pr-4 font-semibold">{r.ticker}</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.strategy === "COVERED_CALL" ? "bg-blue-900/50 text-blue-300" : "bg-purple-900/50 text-purple-300"}`}>
                          {r.strategy === "COVERED_CALL" ? "CC" : "CSP"}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-right">${r.strike.toFixed(2)}</td>
                      <td className="py-3 pr-4 text-right text-gray-400">{r.expiry}</td>
                      <td className="py-3 pr-4 text-right">{r.dte}</td>
                      <td className="py-3 pr-4 text-right">${r.premium.toFixed(2)}</td>
                      <td className="py-3 pr-4 text-right">{r.delta.toFixed(3)}</td>
                      <td className="py-3 pr-4 text-right">${r.theta.toFixed(3)}</td>
                      <td className="py-3 pr-4 text-right">{(r.iv * 100).toFixed(1)}%</td>
                      <td className="py-3 pr-4 text-right">{(r.ann_return * 100).toFixed(1)}%</td>
                      <td className="py-3 text-right">
                        <span className={`font-bold ${r.score >= 70 ? "text-emerald-400" : r.score >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                          {r.score.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
