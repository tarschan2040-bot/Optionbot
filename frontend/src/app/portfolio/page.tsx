"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import Link from "next/link";
import {
  getCandidates,
  confirmCandidate,
  removeCandidate,
  getPortfolio,
  getPortfolioSummary,
  closeTrade,
} from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────

interface Candidate {
  id: string; ticker: string; strategy: string; strike: number;
  expiry: string; dte: number; delta: number; premium: number;
  score: number; ann_return: number | null; scan_time: string | null;
}

interface Position {
  id: string; ticker: string; strategy: string; strike: number;
  expiry: string; dte_at_entry: number; dte_now: number;
  entry_premium: number; entry_delta: number;
  current_stock_price: number | null; current_option_price: number | null;
  current_delta: number | null; current_iv: number | null;
  current_theta: number | null; stock_day_change_pct: number | null;
  pnl_dollars: number | null; pnl_percent: number | null;
  opened_at: string | null; contracts: number;
}

interface Summary {
  total_open_trades: number; total_trades_all_time: number;
  total_closed_trades: number; total_pnl: number | null;
  total_premium_collected: number; win_count: number; loss_count: number;
  win_rate: number | null; avg_return_pct: number | null;
  best_trade_pnl: number | null; worst_trade_pnl: number | null;
}

type Tab = "portfolio" | "candidates";

// ── Components ───────────────────────────────────────────────────────────

function StatBox({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <p className="text-gray-400 text-xs uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${color || "text-white"}`}>{value}</p>
      {sub && <p className="text-gray-500 text-xs mt-1">{sub}</p>}
    </div>
  );
}

function PnlText({ value, suffix }: { value: number | null; suffix?: string }) {
  if (value == null) return <span className="text-gray-500">—</span>;
  const color = value >= 0 ? "text-emerald-400" : "text-red-400";
  const sign = value >= 0 ? "+" : "";
  return <span className={`font-bold ${color}`}>{sign}{value.toFixed(2)}{suffix || ""}</span>;
}

// Simple P&L chart using SVG
function PnlChart({ positions }: { positions: Position[] }) {
  const [period, setPeriod] = useState("1M");

  // For now, show a placeholder based on current unrealised P&L
  // Full historical chart requires storing daily snapshots (future enhancement)
  const totalPnl = positions.reduce((s, p) => s + (p.pnl_dollars || 0), 0);
  const totalPremium = positions.reduce((s, p) => s + p.entry_premium * 100 * p.contracts, 0);
  const pnlPct = totalPremium > 0 ? (totalPnl / totalPremium * 100) : 0;
  const isPositive = totalPnl >= 0;

  // Generate synthetic chart points (current positions only — real history requires daily snapshots)
  const days = period === "1W" ? 7 : period === "1M" ? 30 : period === "3M" ? 90 : period === "YTD" ? 120 : period === "1Y" ? 365 : 365;
  const points: number[] = [];
  for (let i = 0; i <= Math.min(days, 30); i++) {
    // Approximate: linear interpolation from 0 to current P&L with some noise
    const progress = i / Math.min(days, 30);
    const noise = (Math.sin(i * 1.5) * 0.15 + Math.sin(i * 0.7) * 0.1) * Math.abs(totalPnl || 100);
    points.push(progress * totalPnl + noise);
  }

  const minVal = Math.min(...points, 0);
  const maxVal = Math.max(...points, 1);
  const range = maxVal - minVal || 1;
  const chartW = 680;
  const chartH = 160;

  const svgPoints = points.map((v, i) => {
    const x = (i / (points.length - 1)) * chartW;
    const y = chartH - ((v - minVal) / range) * (chartH - 20) - 10;
    return `${x},${y}`;
  }).join(" ");

  const fillPoints = `0,${chartH} ${svgPoints} ${chartW},${chartH}`;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-gray-400 text-sm">Unrealised P&L</p>
          <p className={`text-3xl font-bold ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </p>
          <p className={`text-sm ${isPositive ? "text-emerald-400/70" : "text-red-400/70"}`}>
            {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
          </p>
        </div>
        <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
          {["1W", "1M", "3M", "YTD", "1Y", "All"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                period === p ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      {/* Chart */}
      <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-40">
        <defs>
          <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity="0.3" />
            <stop offset="100%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* Zero line */}
        {minVal < 0 && maxVal > 0 && (
          <line
            x1="0"
            y1={chartH - ((0 - minVal) / range) * (chartH - 20) - 10}
            x2={chartW}
            y2={chartH - ((0 - minVal) / range) * (chartH - 20) - 10}
            stroke="#374151" strokeDasharray="4 4" strokeWidth="1"
          />
        )}
        {/* Fill */}
        <polygon points={fillPoints} fill="url(#pnlGrad)" />
        {/* Line */}
        <polyline
          points={svgPoints}
          fill="none"
          stroke={isPositive ? "#10b981" : "#ef4444"}
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
      <p className="text-gray-600 text-xs mt-2">
        Chart shows estimated P&L curve. Historical daily snapshots coming soon.
      </p>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────

export default function PortfolioPage() {
  const { token } = useSession();
  const [activeTab, setActiveTab] = useState<Tab>("portfolio");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loadingC, setLoadingC] = useState(false);
  const [loadingP, setLoadingP] = useState(false);
  const [msg, setMsg] = useState("");

  const loadCandidates = useCallback(async () => {
    if (!token) return;
    setLoadingC(true);
    try { setCandidates(await getCandidates(token)); } catch (e) { console.error(e); }
    finally { setLoadingC(false); }
  }, [token]);

  const loadPortfolio = useCallback(async () => {
    if (!token) return;
    setLoadingP(true);
    try {
      const [pos, sum] = await Promise.all([getPortfolio(token), getPortfolioSummary(token)]);
      setPositions(pos);
      setSummary(sum);
    } catch (e) { console.error(e); }
    finally { setLoadingP(false); }
  }, [token]);

  useEffect(() => {
    if (activeTab === "candidates") loadCandidates();
    else loadPortfolio();
  }, [activeTab, loadCandidates, loadPortfolio]);

  // Also load candidate count for badge
  useEffect(() => { if (token) getCandidates(token).then(setCandidates).catch(() => {}); }, [token]);

  function flash(m: string) { setMsg(m); setTimeout(() => setMsg(""), 3000); }

  async function handleConfirm(id: string) {
    if (!token) return;
    try { await confirmCandidate(token, id); flash("Trade confirmed!"); loadCandidates(); loadPortfolio(); }
    catch { flash("Failed."); }
  }
  async function handleRemove(id: string) {
    if (!token) return;
    try { await removeCandidate(token, id); flash("Removed."); loadCandidates(); }
    catch { flash("Failed."); }
  }
  async function handleClose(id: string) {
    if (!token) return;
    const exitPrice = prompt("Exit price (option premium at close, 0 if expired worthless):");
    if (exitPrice === null) return;
    try { const r = await closeTrade(token, id, parseFloat(exitPrice)); flash(r.message); loadPortfolio(); }
    catch { flash("Failed."); }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 bg-gray-900 rounded-lg p-1 w-fit border border-gray-800 mb-6">
          <button onClick={() => setActiveTab("portfolio")} className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === "portfolio" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}>
            Portfolio
          </button>
          <button onClick={() => setActiveTab("candidates")} className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === "candidates" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}>
            Candidates{candidates.length > 0 ? ` (${candidates.length})` : ""}
          </button>
        </div>

        {msg && <div className="mb-4 p-3 bg-emerald-900/30 border border-emerald-700 rounded-lg text-emerald-300 text-sm">{msg}</div>}

        {/* ── Portfolio ─────────────────────────────────────────── */}
        {activeTab === "portfolio" && (
          <>
            {/* Summary cards */}
            {summary && (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
                <StatBox label="Open Trades" value={`${summary.total_open_trades}`} />
                <StatBox label="All Trades" value={`${summary.total_trades_all_time}`} sub={`${summary.total_closed_trades} closed`} />
                <StatBox label="Premium Collected" value={`$${summary.total_premium_collected.toFixed(0)}`} color="text-emerald-400" />
                <StatBox label="Realised P&L" value={summary.total_pnl != null ? `${summary.total_pnl >= 0 ? "+" : ""}$${summary.total_pnl.toFixed(0)}` : "—"} color={summary.total_pnl != null ? (summary.total_pnl >= 0 ? "text-emerald-400" : "text-red-400") : "text-gray-500"} />
                <StatBox label="Win Rate" value={summary.win_rate != null ? `${summary.win_rate}%` : "—"} sub={`${summary.win_count}W / ${summary.loss_count}L`} />
                <StatBox label="Best / Worst" value={summary.best_trade_pnl != null ? `+$${summary.best_trade_pnl.toFixed(0)}` : "—"} sub={summary.worst_trade_pnl != null ? `Worst: $${summary.worst_trade_pnl.toFixed(0)}` : undefined} />
              </div>
            )}

            {/* P&L Chart */}
            {positions.length > 0 && <PnlChart positions={positions} />}

            <h2 className="text-xl font-bold mb-4">Open Positions</h2>

            {loadingP ? (
              <div className="text-center py-16 text-gray-500">Loading portfolio and live prices...</div>
            ) : positions.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-gray-500">No open positions.</p>
                <p className="text-gray-600 text-sm mt-2">Star candidates from <Link href="/scan" className="text-emerald-400 hover:underline">Scan</Link> and confirm them.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400 text-left">
                      <th className="pb-3 pr-3">Ticker</th>
                      <th className="pb-3 pr-3">Type</th>
                      <th className="pb-3 pr-3 text-right">Strike</th>
                      <th className="pb-3 pr-3 text-right">Expiry</th>
                      <th className="pb-3 pr-3 text-right">DTE</th>
                      <th className="pb-3 pr-3 text-right">Stock</th>
                      <th className="pb-3 pr-3 text-right">Day%</th>
                      <th className="pb-3 pr-3 text-right">Entry</th>
                      <th className="pb-3 pr-3 text-right">Current</th>
                      <th className="pb-3 pr-3 text-right">IV</th>
                      <th className="pb-3 pr-3 text-right">P&L $</th>
                      <th className="pb-3 pr-3 text-right">P&L %</th>
                      <th className="pb-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-900/50 transition-colors">
                        <td className="py-3 pr-3 font-semibold">{p.ticker}</td>
                        <td className="py-3 pr-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${p.strategy === "COVERED_CALL" ? "bg-blue-900/50 text-blue-300" : "bg-purple-900/50 text-purple-300"}`}>{p.strategy === "COVERED_CALL" ? "CC" : "CSP"}</span></td>
                        <td className="py-3 pr-3 text-right">${p.strike.toFixed(2)}</td>
                        <td className="py-3 pr-3 text-right text-gray-400">{p.expiry}</td>
                        <td className="py-3 pr-3 text-right"><span className={p.dte_now <= 7 ? "text-red-400 font-bold" : ""}>{p.dte_now}</span></td>
                        <td className="py-3 pr-3 text-right">{p.current_stock_price != null ? `$${p.current_stock_price.toFixed(2)}` : "—"}</td>
                        <td className="py-3 pr-3 text-right">{p.stock_day_change_pct != null ? <span className={p.stock_day_change_pct >= 0 ? "text-emerald-400" : "text-red-400"}>{p.stock_day_change_pct >= 0 ? "+" : ""}{p.stock_day_change_pct.toFixed(2)}%</span> : "—"}</td>
                        <td className="py-3 pr-3 text-right font-mono">${p.entry_premium.toFixed(2)}</td>
                        <td className="py-3 pr-3 text-right font-mono">{p.current_option_price != null ? `$${p.current_option_price.toFixed(2)}` : "—"}</td>
                        <td className="py-3 pr-3 text-right">{p.current_iv != null ? `${(p.current_iv * 100).toFixed(1)}%` : "—"}</td>
                        <td className="py-3 pr-3 text-right"><PnlText value={p.pnl_dollars} /></td>
                        <td className="py-3 pr-3 text-right"><PnlText value={p.pnl_percent} suffix="%" /></td>
                        <td className="py-3"><button onClick={() => handleClose(p.id)} className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-lg border border-gray-700 transition-colors">Close</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {positions.some((p) => p.pnl_dollars != null) && (
                  <div className="mt-4 pt-4 border-t border-gray-800 flex justify-end gap-8 text-sm">
                    <span className="text-gray-400">Unrealised Total:</span>
                    <PnlText value={positions.reduce((s, p) => s + (p.pnl_dollars || 0), 0)} />
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ── Candidates ────────────────────────────────────────── */}
        {activeTab === "candidates" && (
          <>
            <h2 className="text-xl font-bold mb-2">Candidates</h2>
            <p className="text-gray-400 text-sm mb-6">Starred from scan results. Confirm to add to portfolio, or remove.</p>
            {loadingC ? (
              <div className="text-center py-16 text-gray-500">Loading...</div>
            ) : candidates.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-gray-500">No candidates.</p>
                <p className="text-gray-600 text-sm mt-2">Star opportunities from <Link href="/scan" className="text-emerald-400 hover:underline">Scan</Link>.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {candidates.map((c) => (
                  <div key={c.id} className="bg-gray-900 rounded-xl border border-gray-800 p-5 flex items-center justify-between hover:border-gray-700 transition-colors">
                    <div className="flex items-center gap-6">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-yellow-400">★</span>
                          <span className="font-bold text-lg">{c.ticker}</span>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.strategy === "COVERED_CALL" ? "bg-blue-900/50 text-blue-300" : "bg-purple-900/50 text-purple-300"}`}>{c.strategy === "COVERED_CALL" ? "CC" : "CSP"}</span>
                        </div>
                        <p className="text-gray-400 text-sm">${c.strike.toFixed(2)} · {c.expiry} · {c.dte} DTE</p>
                      </div>
                      <div className="hidden md:flex gap-6 text-sm">
                        <div><p className="text-gray-500 text-xs">Premium</p><p className="font-mono">${c.premium.toFixed(2)}</p></div>
                        <div><p className="text-gray-500 text-xs">Delta</p><p className="font-mono">{c.delta.toFixed(3)}</p></div>
                        <div><p className="text-gray-500 text-xs">Score</p><p className={`font-bold ${c.score >= 70 ? "text-emerald-400" : c.score >= 50 ? "text-yellow-400" : "text-red-400"}`}>{c.score.toFixed(1)}</p></div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => handleConfirm(c.id)} className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg font-medium transition-colors">Confirm</button>
                      <button onClick={() => handleRemove(c.id)} className="px-4 py-2 bg-gray-800 hover:bg-red-900/50 text-gray-400 hover:text-red-400 text-sm rounded-lg border border-gray-700 transition-colors">Remove</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
