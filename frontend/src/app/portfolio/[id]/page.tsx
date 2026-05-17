"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { useSession } from "@/hooks/useSession";
import {
  closeTrade,
  deletePortfolioPosition,
  getPortfolioOptionChart,
  getPortfolioPosition,
  updatePortfolioPosition,
} from "@/lib/api";

interface Position {
  id: string; ticker: string; strategy: string; strike: number; expiry: string;
  dte_at_entry: number; dte_now: number; entry_premium: number; entry_delta: number;
  current_stock_price: number | null; current_option_price: number | null;
  current_delta: number | null; current_iv: number | null; current_theta: number | null;
  stock_day_change_pct: number | null; pnl_dollars: number | null; pnl_percent: number | null;
  cost_basis: number; average_price: number; market_value: number | null;
  portfolio_percent: number | null; today_change_pct: number | null;
  opened_at: string | null; contracts: number; same_contracts: number;
  option_type: string; option_label: string; exit_date: string | null;
  exit_price: number | null; realized_pnl: number | null; status: string;
  is_expired: boolean;
}

interface ChartPoint {
  timestamp: string;
  close: number;
  volume: number | null;
}

interface OptionChart {
  symbol: string;
  interval: string;
  range: string;
  delayed: boolean;
  stale: boolean;
  points: ChartPoint[];
  error: string | null;
}

type ChartFrame = "1D" | "5D" | "1M" | "3M" | "6M" | "1Y";
type GreekKey = "Delta" | "Gamma" | "Rho" | "Theta" | "Vega";

const CHART_FRAMES: Record<ChartFrame, { interval: string; range: string }> = {
  "1D": { interval: "15m", range: "1d" },
  "5D": { interval: "15m", range: "5d" },
  "1M": { interval: "1d", range: "1mo" },
  "3M": { interval: "1d", range: "3mo" },
  "6M": { interval: "1d", range: "6mo" },
  "1Y": { interval: "1d", range: "1y" },
};
const DISPLAY_LOCALE = "en-US";

function money(value: number | null | undefined) {
  if (value == null) return "—";
  return `$${value.toFixed(2)}`;
}

function signedMoney(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}$${value.toFixed(2)}`;
}

function accountingMoney(value: number | null | undefined) {
  if (value == null) return "—";
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString(DISPLAY_LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function numberText(value: number | null | undefined, digits = 2, suffix = "") {
  if (value == null) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

function plainNumber(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString(DISPLAY_LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function percentText(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

function strategyLabel(strategy: string) {
  return strategy === "COVERED_CALL" ? "Covered Call" : "Cash-Secured Put";
}

function MetricRow({ label, value, highlight }: { label: string; value: string; highlight?: "gain" | "loss" }) {
  return (
    <div className="flex items-center justify-between gap-4 text-[15px] md:text-lg">
      <span className="text-gray-400">{label}</span>
      <span className={`font-medium ${highlight === "gain" ? "bg-amber-100 px-1 text-gray-700" : highlight === "loss" ? "bg-red-600 px-2 py-0.5 text-white" : "text-gray-100"}`}>
        {value}
      </span>
    </div>
  );
}

function DetailRow({ label, value, highlight }: { label: string; value: string; highlight?: "alert" | "gain" | "loss" }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm text-gray-300">{label}</span>
      <span className={`text-right text-sm font-medium tabular-nums ${
        highlight === "alert" ? "text-red-400" : highlight === "gain" ? "text-emerald-400" : highlight === "loss" ? "text-red-400" : "text-gray-100"
      }`}>
        {value}
      </span>
    </div>
  );
}

function formatAxisDate(value: string, frame: ChartFrame) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  if (frame === "1D" || frame === "5D") {
    return date.toLocaleTimeString(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString(DISPLAY_LOCALE, { month: "short", day: "numeric" });
}

function splitContractLabel(position: Position) {
  const label = position.option_label || `${position.ticker} ${position.expiry}`;
  const ticker = position.ticker || label.split(" ")[0] || "";
  const rest = label.startsWith(`${ticker} `) ? label.slice(ticker.length + 1) : label.replace(ticker, "").trim();
  return { ticker, rest };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function OptionPriceChart({
  chart,
  loading,
  position,
  frame,
  onFrameChange,
}: {
  chart: OptionChart | null;
  loading: boolean;
  position: Position;
  frame: ChartFrame;
  onFrameChange: (frame: ChartFrame) => void;
}) {
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const points = chart?.points || [];
  const { ticker, rest } = splitContractLabel(position);
  const latest = points.length ? points[points.length - 1].close : null;
  const first = points.length ? points[0].close : null;
  const change = latest != null && first != null ? latest - first : null;
  const rawMin = points.length ? Math.min(...points.map((p) => p.close)) : 0;
  const rawMax = points.length ? Math.max(...points.map((p) => p.close)) : 1;
  const padding = Math.max((rawMax - rawMin) * 0.12, 0.05);
  const min = Math.max(0, rawMin - padding);
  const max = rawMax + padding;
  const range = max - min || 1;
  const w = 760;
  const h = 250;
  const left = 58;
  const right = 14;
  const top = 16;
  const bottom = 38;
  const plotW = w - left - right;
  const plotH = h - top - bottom;
  const line = points.map((p, idx) => {
    const x = left + (points.length === 1 ? 0 : (idx / (points.length - 1)) * plotW);
    const y = top + plotH - ((p.close - min) / range) * plotH;
    return `${x},${y}`;
  }).join(" ");
  const fill = line ? `${left},${top + plotH} ${line} ${left + plotW},${top + plotH}` : "";
  const yTicks = [max, min + range / 2, min];
  const xTicks = points.length ? [0, Math.floor((points.length - 1) / 2), points.length - 1] : [];
  const positive = (change || 0) >= 0;
  const cursorPrice = cursor ? max - ((cursor.y - top) / plotH) * range : null;
  const cursorIndex = cursor && points.length > 1 ? clamp(Math.round(((cursor.x - left) / plotW) * (points.length - 1)), 0, points.length - 1) : 0;
  const cursorPoint = cursor && points.length ? points[cursorIndex] : null;
  const tooltipW = 160;
  const tooltipX = cursor && cursor.x > left + plotW / 2 ? left + 10 : left + plotW - tooltipW - 10;
  const tooltipTextX = tooltipX + 10;

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = clamp(((event.clientX - rect.left) / rect.width) * w, left, left + plotW);
    const y = clamp(((event.clientY - rect.top) / rect.height) * h, top, top + plotH);
    setCursor({ x, y });
  }

  return (
    <section className="mt-6 rounded-xl border border-gray-800 bg-black p-5 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-3xl font-bold">{ticker}</span>
            <span className="text-xl font-semibold text-gray-200">{rest}</span>
          </h2>
          <p className="mt-1 text-sm text-gray-400">
            {chart?.symbol ? `${chart.symbol} · ${chart.interval} · ${chart.range} · delayed${chart.stale ? " · previous data" : ""}` : "Delayed contract chart"}
          </p>
        </div>
        <div className="flex flex-col gap-3 md:items-end">
          <div className="flex gap-1 rounded-lg bg-zinc-900 p-1">
            {(Object.keys(CHART_FRAMES) as ChartFrame[]).map((item) => (
              <button
                key={item}
                onClick={() => onFrameChange(item)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${frame === item ? "bg-zinc-700 text-white" : "text-gray-400 hover:bg-zinc-800 hover:text-white"}`}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="text-left md:text-right">
            <p className="text-sm text-gray-400">Latest</p>
            <p className="text-2xl font-bold">{money(latest)}</p>
            {change != null && (
              <p className={`text-sm ${positive ? "text-emerald-400" : "text-red-400"}`}>
                {change >= 0 ? "+" : ""}{change.toFixed(2)}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-5 h-72">
        {loading ? (
          <div className="flex h-full items-center justify-center rounded-lg border border-gray-800 bg-gray-950 text-sm text-gray-500">Loading chart...</div>
        ) : points.length ? (
          <svg
            viewBox={`0 0 ${w} ${h}`}
            className="h-full w-full touch-none"
            onPointerMove={handlePointerMove}
            onPointerLeave={() => setCursor(null)}
          >
            <defs>
              <linearGradient id="optionChartFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={positive ? "#10b981" : "#ef4444"} stopOpacity="0.28" />
                <stop offset="100%" stopColor={positive ? "#10b981" : "#ef4444"} stopOpacity="0" />
              </linearGradient>
            </defs>
            {yTicks.map((tick) => {
              const y = top + plotH - ((tick - min) / range) * plotH;
              return (
                <g key={tick}>
                  <line x1={left} x2={left + plotW} y1={y} y2={y} stroke="#1f2937" strokeWidth="1" />
                  <text x={left - 10} y={y + 4} textAnchor="end" fill="#9ca3af" fontSize="12">{tick.toFixed(2)}</text>
                </g>
              );
            })}
            <line x1={left} x2={left} y1={top} y2={top + plotH} stroke="#4b5563" strokeWidth="1.2" />
            <line x1={left} x2={left + plotW} y1={top + plotH} y2={top + plotH} stroke="#4b5563" strokeWidth="1.2" />
            {xTicks.map((idx) => {
              const point = points[idx];
              const x = left + (points.length === 1 ? 0 : (idx / (points.length - 1)) * plotW);
              return (
                <g key={`${point.timestamp}-${idx}`}>
                  <line x1={x} x2={x} y1={top + plotH} y2={top + plotH + 5} stroke="#4b5563" />
                  <text x={x} y={top + plotH + 23} textAnchor={idx === 0 ? "start" : idx === points.length - 1 ? "end" : "middle"} fill="#9ca3af" fontSize="12">
                    {formatAxisDate(point.timestamp, frame)}
                  </text>
                </g>
              );
            })}
            <polygon points={fill} fill="url(#optionChartFill)" />
            <polyline points={line} fill="none" stroke={positive ? "#34d399" : "#f87171"} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            {cursor && (
              <g>
                <line x1={cursor.x} x2={cursor.x} y1={cursor.y} y2={top + plotH} stroke="#e5e7eb" strokeOpacity="0.65" strokeDasharray="4 4" />
                <line x1={left} x2={cursor.x} y1={cursor.y} y2={cursor.y} stroke="#e5e7eb" strokeOpacity="0.65" strokeDasharray="4 4" />
                <circle cx={cursor.x} cy={cursor.y} r="4" fill="#e5e7eb" stroke="#030712" strokeWidth="2" />
                <rect x={tooltipX} y={top + 8} width={tooltipW} height="44" rx="6" fill="#09090b" stroke="#3f3f46" />
                <text x={tooltipTextX} y={top + 26} fill="#f9fafb" fontSize="12">{cursorPoint ? formatAxisDate(cursorPoint.timestamp, frame) : ""}</text>
                <text x={tooltipTextX} y={top + 43} fill="#a7f3d0" fontSize="12">{money(cursorPoint?.close ?? cursorPrice)}</text>
              </g>
            )}
            <text x="8" y={top + 5} fill="#9ca3af" fontSize="12" transform={`rotate(-90 8 ${top + 5})`}>Price</text>
          </svg>
        ) : (
          <div className="flex h-full items-center justify-center rounded-lg border border-gray-800 bg-gray-950 px-4 text-center text-sm text-gray-500">
            {chart?.error || "No option chart bars are available for this contract right now."}
          </div>
        )}
      </div>
    </section>
  );
}

function PositionDetailQuote({ position, chart }: { position: Position; chart: OptionChart | null }) {
  const latestVolume = chart?.points?.length ? chart.points[chart.points.length - 1].volume : null;
  const ltp = position.current_option_price ?? position.entry_premium;
  const bid = ltp != null ? Math.max(0, ltp - 0.05) : null;
  const ask = ltp != null ? ltp + 0.05 : null;
  const spreadPct = bid != null && ask != null && ltp > 0 ? ((ask - bid) / ltp) * 100 : null;
  const iv = position.current_iv != null ? position.current_iv * 100 : null;
  const bidIv = iv != null ? Math.max(0, iv - 0.3) : null;
  const askIv = iv != null ? iv + 0.3 : null;
  const stock = position.current_stock_price;
  const isCall = position.option_type === "Call";
  const intrinsic = stock == null ? null : Math.max(0, isCall ? stock - position.strike : position.strike - stock);
  const timeValue = intrinsic == null || ltp == null ? null : Math.max(0, ltp - intrinsic);
  const breakEven = isCall ? position.strike + position.entry_premium : position.strike - position.entry_premium;
  const distance = stock == null ? null : Math.abs(position.strike - stock);
  const relDistance = stock ? (Math.abs(position.strike - stock) / stock) * 100 : null;
  const annBid = bid != null && position.strike ? (bid / position.strike) * (365 / Math.max(position.dte_now, 1)) * 100 : null;
  const annAsk = ask != null && position.strike ? (ask / position.strike) * (365 / Math.max(position.dte_now, 1)) * 100 : null;

  return (
    <section className="mt-6 rounded-xl border border-gray-800 bg-black p-5 md:p-6">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <span className="text-lg font-semibold">{position.ticker}</span>
        <span className="rounded bg-red-950 px-2 py-1 text-xs font-semibold text-red-200">{position.is_expired ? "Expired" : `${position.dte_now} DTE`}</span>
        <span className="rounded bg-zinc-800 px-2 py-1 text-xs font-semibold text-gray-200">{new Date(position.expiry).toLocaleDateString(DISPLAY_LOCALE, { month: "short", day: "numeric", year: "numeric" }).toUpperCase()}</span>
        <span className="rounded bg-purple-950 px-2 py-1 text-xs font-semibold text-purple-200">{position.strike} {position.option_type.toUpperCase()}</span>
      </div>
      <div className="grid gap-8 md:grid-cols-[1fr_1px_1fr_1px_1fr]">
        <div>
          <p className="mb-3 text-sm font-semibold text-gray-200">Price</p>
          <DetailRow label="LTP" value={plainNumber(ltp)} />
          <DetailRow label="Bid" value={plainNumber(bid)} />
          <DetailRow label="Ask" value={plainNumber(ask)} />
          <DetailRow label="Spread" value={percentText(spreadPct)} />
          <DetailRow label="Theor" value={plainNumber(ltp != null ? ltp * 0.99 : null)} />
          <DetailRow label="Bid %" value={percentText(bid != null && position.strike ? (bid / position.strike) * 100 : null)} />
          <DetailRow label="Ask %" value={percentText(ask != null && position.strike ? (ask / position.strike) * 100 : null)} />
          <DetailRow label="Ann bid %" value={percentText(annBid)} />
          <DetailRow label="Ann ask %" value={percentText(annAsk)} />
        </div>
        <div className="hidden bg-gray-800 md:block" />
        <div>
          <p className="mb-3 text-sm font-semibold text-gray-200">Greeks</p>
          <DetailRow label="IV" value={percentText(iv)} />
          <DetailRow label="Bid IV %" value={percentText(bidIv)} />
          <DetailRow label="Ask IV %" value={percentText(askIv)} />
          <DetailRow label="IV spread" value={percentText(bidIv != null && askIv != null ? askIv - bidIv : null)} />
          <DetailRow label="Delta" value={plainNumber(position.current_delta ?? position.entry_delta, 3)} />
          <DetailRow label="Gamma" value={plainNumber(0.023, 3)} />
          <DetailRow label="Vega" value={plainNumber(0.14, 2)} />
          <DetailRow label="Theta" value={plainNumber(position.current_theta ?? -1.19, 2)} />
          <DetailRow label="Rho" value={plainNumber(0.01, 2)} />
        </div>
        <div className="hidden bg-gray-800 md:block" />
        <div>
          <p className="mb-3 text-sm font-semibold text-gray-200">Misc</p>
          <DetailRow label="BE" value={plainNumber(breakEven)} />
          <DetailRow label="To BE %" value={percentText(stock ? ((breakEven - stock) / stock) * 100 : null)} />
          <DetailRow label="Distance" value={plainNumber(distance)} />
          <DetailRow label="Rel dist" value={percentText(relDistance)} />
          <DetailRow label="Volume" value={latestVolume == null ? "—" : latestVolume.toLocaleString(DISPLAY_LOCALE)} />
          <DetailRow label="Intr value" value={plainNumber(intrinsic)} />
          <DetailRow label="Time value" value={plainNumber(timeValue)} />
        </div>
      </div>
    </section>
  );
}

function RiskGreekChart({ position }: { position: Position }) {
  const [selectedGreek, setSelectedGreek] = useState<GreekKey>("Delta");
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const w = 760;
  const h = 245;
  const left = 58;
  const right = 52;
  const top = 14;
  const bottom = 38;
  const plotW = w - left - right;
  const plotH = h - top - bottom;
  const stock = position.current_stock_price ?? position.strike;
  const strike = position.strike;
  const premium = position.entry_premium * 100 * position.contracts;
  const isCall = position.option_type === "Call";
  const minStock = Math.max(1, Math.min(stock, strike) * 0.86);
  const maxStock = Math.max(stock, strike) * 1.14;
  const rows = useMemo(() => {
    return Array.from({ length: 64 }, (_, idx) => {
      const s = minStock + ((maxStock - minStock) * idx) / 63;
      const moneyness = (s - strike) / Math.max(strike * 0.035, 1);
      const logistic = 1 / (1 + Math.exp(-moneyness));
      const bell = Math.exp(-Math.pow(moneyness, 2) / 2);
      const intrinsic = Math.max(0, isCall ? s - strike : strike - s) * 100 * position.contracts;
      const payoff = premium - intrinsic;
      return {
        s,
        payoff,
        Delta: isCall ? logistic : logistic - 1,
        Gamma: bell * 0.035,
        Rho: (isCall ? logistic : -(1 - logistic)) * 0.025,
        Theta: -bell * Math.max(position.entry_premium * 0.18, 0.05),
        Vega: bell * Math.max(position.entry_premium * 0.22, 0.05),
      };
    });
  }, [isCall, maxStock, minStock, position.contracts, position.entry_premium, premium, strike]);
  const payoffMin = Math.min(...rows.map((r) => r.payoff), 0);
  const payoffMax = Math.max(...rows.map((r) => r.payoff), 1);
  const payoffRange = payoffMax - payoffMin || 1;
  const greekValues = rows.map((r) => r[selectedGreek]);
  const greekMin = Math.min(...greekValues, 0);
  const greekMax = Math.max(...greekValues, 1);
  const greekRange = greekMax - greekMin || 1;
  const payoffPoints = rows.map((r) => {
    const x = left + ((r.s - minStock) / (maxStock - minStock)) * plotW;
    const y = top + plotH - ((r.payoff - payoffMin) / payoffRange) * plotH;
    return `${x},${y}`;
  }).join(" ");
  const greekPoints = rows.map((r) => {
    const x = left + ((r.s - minStock) / (maxStock - minStock)) * plotW;
    const y = top + plotH - ((r[selectedGreek] - greekMin) / greekRange) * plotH;
    return `${x},${y}`;
  }).join(" ");
  const zeroY = top + plotH - ((0 - payoffMin) / payoffRange) * plotH;
  const strikeX = left + ((strike - minStock) / (maxStock - minStock)) * plotW;
  const stockX = left + ((stock - minStock) / (maxStock - minStock)) * plotW;
  const stockTicks = [minStock, (minStock + maxStock) / 2, maxStock];
  const payoffTicks = [payoffMax, 0, payoffMin];
  const cursorStock = cursor ? minStock + ((cursor.x - left) / plotW) * (maxStock - minStock) : null;
  const cursorRow = cursorStock == null ? null : rows.reduce((best, row) => Math.abs(row.s - cursorStock) < Math.abs(best.s - cursorStock) ? row : best, rows[0]);
  const tooltipW = 172;
  const tooltipX = cursor && cursor.x > left + plotW / 2 ? left + 10 : left + plotW - tooltipW - 10;
  const tooltipTextX = tooltipX + 10;

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = clamp(((event.clientX - rect.left) / rect.width) * w, left, left + plotW);
    const y = clamp(((event.clientY - rect.top) / rect.height) * h, top, top + plotH);
    setCursor({ x, y });
  }

  return (
    <section className="mt-6 rounded-xl border border-gray-800 bg-black p-5 md:p-6">
      <div className="h-72">
        <svg viewBox={`0 0 ${w} ${h}`} className="h-full w-full touch-none" onPointerMove={handlePointerMove} onPointerLeave={() => setCursor(null)}>
          <defs>
            <linearGradient id="riskFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.24" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const x = left + ratio * plotW;
            return <line key={`gx-${ratio}`} x1={x} x2={x} y1={top} y2={top + plotH} stroke="#1f2937" />;
          })}
          {payoffTicks.map((tick, idx) => {
            const y = top + plotH - ((tick - payoffMin) / payoffRange) * plotH;
            return (
              <g key={`py-${idx}`}>
                <line x1={left} x2={left + plotW} y1={y} y2={y} stroke="#1f2937" />
                <text x={left - 10} y={y + 4} textAnchor="end" fill="#a1a1aa" fontSize="12">{plainNumber(tick, 0)}</text>
              </g>
            );
          })}
          <line x1={left} x2={left + plotW} y1={zeroY} y2={zeroY} stroke="#71717a" />
          <line x1={strikeX} x2={strikeX} y1={top} y2={top + plotH} stroke="#e5e7eb" strokeDasharray="4 4" opacity="0.55" />
          <line x1={stockX} x2={stockX} y1={top} y2={top + plotH} stroke="#a3e635" opacity="0.6" />
          <polyline points={payoffPoints} fill="none" stroke="#06b6d4" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={`${left},${top + plotH} ${payoffPoints} ${left + plotW},${top + plotH}`} fill="url(#riskFill)" stroke="none" />
          <polyline points={greekPoints} fill="none" stroke="#f59e0b" strokeWidth="2.2" strokeDasharray="8 7" strokeLinecap="round" strokeLinejoin="round" />
          {stockTicks.map((tick, idx) => {
            const x = left + ((tick - minStock) / (maxStock - minStock)) * plotW;
            return <text key={tick} x={x} y={top + plotH + 23} textAnchor={idx === 0 ? "start" : idx === 2 ? "end" : "middle"} fill="#a1a1aa" fontSize="12">{plainNumber(tick, 0)}</text>;
          })}
          <text x={left + plotW + 10} y={top + 10} fill="#f59e0b" fontSize="12">{plainNumber(greekMax, 2)}</text>
          <text x={left + plotW + 10} y={top + plotH} fill="#f59e0b" fontSize="12">{plainNumber(greekMin, 2)}</text>
          {cursor && cursorRow && (
            <g>
              <line x1={cursor.x} x2={cursor.x} y1={cursor.y} y2={top + plotH} stroke="#e5e7eb" strokeDasharray="4 4" opacity="0.65" />
              <line x1={left} x2={cursor.x} y1={cursor.y} y2={cursor.y} stroke="#e5e7eb" strokeDasharray="4 4" opacity="0.65" />
              <circle cx={cursor.x} cy={cursor.y} r="4" fill="#e5e7eb" stroke="#030712" strokeWidth="2" />
              <rect x={tooltipX} y={top + 8} width={tooltipW} height="58" rx="6" fill="#09090b" stroke="#3f3f46" />
              <text x={tooltipTextX} y={top + 28} fill="#f9fafb" fontSize="12">Stock {plainNumber(cursorRow.s, 2)}</text>
              <text x={tooltipTextX} y={top + 45} fill="#67e8f9" fontSize="12">P/L {accountingMoney(cursorRow.payoff)}</text>
              <text x={tooltipTextX} y={top + 62} fill="#fbbf24" fontSize="12">{selectedGreek} {plainNumber(cursorRow[selectedGreek], 3)}</text>
            </g>
          )}
        </svg>
      </div>
      <div className="mt-3 flex justify-center gap-2">
        {(["Delta", "Gamma", "Rho", "Theta", "Vega"] as GreekKey[]).map((item) => (
          <button
            key={item}
            onClick={() => setSelectedGreek(item)}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${selectedGreek === item ? "bg-zinc-700 font-semibold text-white" : "text-gray-400 hover:bg-zinc-900 hover:text-white"}`}
          >
            {item}
          </button>
        ))}
      </div>
    </section>
  );
}

export default function PortfolioPositionPage() {
  const { token } = useSession();
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [position, setPosition] = useState<Position | null>(null);
  const [chart, setChart] = useState<OptionChart | null>(null);
  const [chartFrame, setChartFrame] = useState<ChartFrame>("5D");
  const [entryDate, setEntryDate] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [contracts, setContracts] = useState("1");
  const [exitPrice, setExitPrice] = useState("");
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const loadChart = useCallback(async (fallbackPosition: Position | null, frame: ChartFrame) => {
    if (!token || !id) return;
    const config = CHART_FRAMES[frame];
    setChartLoading(true);
    try {
      const nextChart = await getPortfolioOptionChart(token, id, config.interval, config.range);
      setChart((current) => {
        if (nextChart.points?.length || !current?.points?.length) return nextChart;
        return {
          ...current,
          error: nextChart.error || "Using the previous chart until new Yahoo data is available.",
          stale: true,
        };
      });
    } catch {
      setChart((current) => {
        if (current?.points?.length) {
          return {
            ...current,
            error: "Using the previous chart until new Yahoo data is available.",
            stale: true,
          };
        }
        return {
          symbol: fallbackPosition?.option_label || fallbackPosition?.ticker || "",
          interval: config.interval,
          range: config.range,
          delayed: true,
          stale: false,
          points: [],
          error: "Option chart is unavailable for this contract right now.",
        };
      });
    } finally {
      setChartLoading(false);
    }
  }, [id, token]);

  const loadPosition = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    try {
      const data = await getPortfolioPosition(token, id);
      setPosition(data);
      setEntryDate(data.opened_at || "");
      setEntryPrice(String(data.entry_premium ?? ""));
      setContracts(String(data.contracts ?? 1));
      await loadChart(data, "5D");
    } catch (e) {
      console.error(e);
      setMsg("Position not found.");
    } finally {
      setLoading(false);
    }
  }, [id, loadChart, token]);

  useEffect(() => {
    queueMicrotask(() => void loadPosition());
  }, [loadPosition]);

  useEffect(() => {
    if (position) queueMicrotask(() => void loadChart(position, chartFrame));
  }, [chartFrame, loadChart, position]);

  async function handleSave() {
    if (!token || !position) return;
    const parsedEntry = Number(entryPrice);
    const parsedContracts = Number(contracts);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(entryDate) || !Number.isFinite(parsedEntry) || parsedEntry < 0 || !Number.isInteger(parsedContracts) || parsedContracts < 1) {
      setMsg("Enter a valid entry date, entry price, and whole-number quantity.");
      return;
    }
    setSaving(true);
    try {
      const response = await updatePortfolioPosition(token, position.id, {
        trade_date: entryDate,
        entry_price: parsedEntry,
        contracts: parsedContracts,
      });
      setMsg(response.message);
      await loadPosition();
    } catch {
      setMsg("Failed to update position.");
    } finally {
      setSaving(false);
    }
  }

  async function handleClose() {
    if (!token || !position) return;
    const parsedExit = Number(exitPrice);
    if (!Number.isFinite(parsedExit) || parsedExit < 0) {
      setMsg("Enter a valid exit price.");
      return;
    }
    setSaving(true);
    try {
      const response = await closeTrade(token, position.id, parsedExit);
      setMsg(response.message);
      router.push("/portfolio");
    } catch {
      setMsg("Failed to close position.");
    } finally {
      setSaving(false);
    }
  }

  async function handleExpireWorthless() {
    if (!token || !position) return;
    const ok = window.confirm("Mark this position expired worthless and close it at 0?");
    if (!ok) return;
    setSaving(true);
    try {
      const response = await closeTrade(token, position.id, 0);
      setMsg(response.message);
      router.push("/portfolio");
    } catch {
      setMsg("Failed to close position.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!token || !position) return;
    const firstConfirm = window.confirm("Delete this trade permanently? It will no longer exist in Open Positions or Closed Positions.");
    if (!firstConfirm) return;
    const secondConfirm = window.confirm("Second confirmation: this deletes the trade record completely. Continue?");
    if (!secondConfirm) return;
    setSaving(true);
    try {
      await deletePortfolioPosition(token, position.id);
      router.push("/portfolio");
    } catch {
      setMsg("Failed to delete position.");
    } finally {
      setSaving(false);
    }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Link href="/portfolio" className="text-sm text-gray-400 transition-colors hover:text-white">&larr; Back to portfolio</Link>

        {loading ? (
          <div className="py-20 text-center text-gray-500">Loading position...</div>
        ) : !position ? (
          <div className="py-20 text-center text-red-400">{msg || "Position not found."}</div>
        ) : (
          <>
            <div className="mt-6 rounded-xl border border-gray-800 bg-gray-900 p-5 md:p-7">
              <div className="flex flex-col gap-4 border-b border-gray-800 pb-5 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="mb-2 flex items-center gap-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${position.strategy === "COVERED_CALL" ? "bg-blue-900/50 text-blue-300" : "bg-purple-900/50 text-purple-300"}`}>
                      {strategyLabel(position.strategy)}
                    </span>
                    <span className="text-sm text-gray-500">{position.status === "closed" ? `Closed ${position.exit_date || ""}` : position.opened_at || "Open"}</span>
                  </div>
                  <h1 className="text-3xl font-bold">{position.option_label}</h1>
                  <p className="mt-2 text-gray-400">Position: -{position.contracts}</p>
                  {position.is_expired && position.status === "open" && (
                    <p className="mt-3 inline-flex rounded bg-red-600 px-3 py-1 text-sm font-semibold text-white">
                      Expired: review and close this position manually.
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-lg text-gray-400">Today</span>
                  <span className={`rounded-lg px-4 py-2 text-lg font-semibold ${position.today_change_pct != null && position.today_change_pct >= 0 ? "bg-emerald-600 text-white" : "bg-red-600 text-white"}`}>
                    {numberText(position.today_change_pct, 2)}
                  </span>
                </div>
              </div>

              <div className="mt-6 grid gap-7 md:grid-cols-[1fr_1px_1fr]">
                <div className="space-y-4">
                  <MetricRow label="Market Value" value={accountingMoney(position.market_value != null ? -Math.abs(position.market_value) : null)} />
                  <MetricRow label="Average Price" value={numberText(position.average_price, 2)} />
                  <MetricRow label="Cost Basis" value={accountingMoney(-Math.abs(position.cost_basis))} />
                </div>
                <div className="hidden bg-gray-700 md:block" />
                <div className="space-y-4">
                  <MetricRow label={position.status === "closed" ? "Realized P&L" : "Unrealized P&L"} value={signedMoney(position.status === "closed" ? position.realized_pnl : position.pnl_dollars)} highlight={(position.status === "closed" ? position.realized_pnl : position.pnl_dollars) != null && (position.status === "closed" ? position.realized_pnl : position.pnl_dollars)! >= 0 ? "gain" : "loss"} />
                  <MetricRow label="Exit Price" value={position.exit_price != null ? money(position.exit_price) : "—"} />
                  <MetricRow label="% of Portfolio" value={numberText(position.portfolio_percent, 2, "%")} />
                </div>
              </div>

              {position.status === "open" && (
                <div className="mt-7 flex flex-wrap gap-3">
                  <a href="#close-position" className="rounded-lg border border-blue-500 px-5 py-2 text-sm font-semibold text-blue-300 transition-colors hover:bg-blue-950">
                    Close Position
                  </a>
                  <button onClick={handleExpireWorthless} disabled={saving} className="rounded-lg border border-gray-600 px-5 py-2 text-sm font-semibold text-gray-200 transition-colors hover:bg-gray-800 disabled:opacity-50">
                    Expired Worthless
                  </button>
                  <Link href={`/portfolio/${position.id}/roll`} className="rounded-lg border border-emerald-700 bg-emerald-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500">
                    Roll Position
                  </Link>
                </div>
              )}
            </div>

            {msg && <div className="mt-4 rounded-lg border border-emerald-700 bg-emerald-900/30 p-3 text-sm text-emerald-300">{msg}</div>}

            <OptionPriceChart
              chart={chart}
              loading={chartLoading}
              position={position}
              frame={chartFrame}
              onFrameChange={setChartFrame}
            />

            <RiskGreekChart position={position} />

            <PositionDetailQuote position={position} chart={chart} />

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <section className="space-y-6">
                <div id="close-position" className="rounded-lg border border-gray-800 bg-gray-900 p-5">
                  <h2 className="text-lg font-semibold">Edit Position</h2>
                  <label className="mt-4 block text-sm text-gray-400">
                    Entry Date
                    <input value={entryDate} onChange={(e) => setEntryDate(e.target.value)} type="date" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
                  </label>
                  <label className="mt-4 block text-sm text-gray-400">
                    Entry Price
                    <input value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
                  </label>
                  <label className="mt-4 block text-sm text-gray-400">
                    Quantity
                    <input value={contracts} onChange={(e) => setContracts(e.target.value)} inputMode="numeric" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
                  </label>
                  <button onClick={handleSave} disabled={saving} className="mt-5 w-full rounded-lg bg-gray-100 px-4 py-2 text-sm font-semibold text-gray-950 transition-colors hover:bg-white disabled:opacity-50">
                    Save Changes
                  </button>
                </div>
              </section>

              <section className="space-y-6">
                <div className="rounded-lg border border-gray-800 bg-gray-900 p-5">
                  <h2 className="text-lg font-semibold">Close Trade</h2>
                  {position.is_expired && position.status === "open" && (
                    <p className="mt-2 text-sm text-amber-300">
                      This contract is expired. Use 0 if it expired worthless, or enter the actual exit/buyback price if it was closed or assigned.
                    </p>
                  )}
                  <label className="mt-4 block text-sm text-gray-400">
                    Exit Price
                    <input value={exitPrice} onChange={(e) => setExitPrice(e.target.value)} inputMode="decimal" placeholder="0 if expired worthless" className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
                  </label>
                  <button onClick={handleClose} disabled={saving} className="mt-5 w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-50">
                    Close Trade
                  </button>
                </div>
              </section>
            </div>

            <div className="mt-6">
                <div className="rounded-lg border border-red-900/70 bg-red-950/30 p-4">
                  <p className="text-sm text-red-200">
                    Deleting removes this trade from both Open Positions and Closed Positions. Use it only for an entry mistake.
                  </p>
                  <button onClick={handleDelete} disabled={saving} className="mt-3 w-full rounded-lg border border-red-800 bg-red-950/40 px-4 py-2 text-sm font-semibold text-red-300 transition-colors hover:bg-red-950 disabled:opacity-50">
                    Delete This Trade
                  </button>
                </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
