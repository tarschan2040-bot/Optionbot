"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase";
import { useRouter, useParams } from "next/navigation";
import { getScanResultDetail, starCandidate } from "@/lib/api";
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

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <p className="text-gray-400 text-xs uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color || "text-white"}`}>
        {value}
      </p>
      {sub && <p className="text-gray-500 text-xs mt-1">{sub}</p>}
    </div>
  );
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-900/30 border-emerald-700";
  if (score >= 50) return "bg-yellow-900/30 border-yellow-700";
  return "bg-red-900/30 border-red-700";
}

export default function DetailPage() {
  const [session, setSession] = useState<{ access_token: string } | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isStarred, setIsStarred] = useState(false);
  const [starring, setStarring] = useState(false);
  const router = useRouter();
  const params = useParams();
  const rank = parseInt(params.rank as string, 10);
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

  useEffect(() => {
    if (!session || isNaN(rank)) return;
    setLoading(true);
    getScanResultDetail(session.access_token, rank)
      .then((data) => setResult(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [session, rank]);

  async function handleStar() {
    if (!session || !result || starring || isStarred) return;
    setStarring(true);
    try {
      await starCandidate(session.access_token, {
        ticker: result.ticker,
        strategy: result.strategy,
        strike: result.strike,
        expiry: result.expiry,
        dte: result.dte,
        delta: result.delta,
        theta: result.theta,
        premium: result.premium,
        score: result.score,
        iv: result.iv,
        ann_return: result.ann_return,
      });
      setIsStarred(true);
    } catch (err) {
      console.error("Star failed:", err);
    } finally {
      setStarring(false);
    }
  }

  if (!session) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/dashboard" className="text-xl font-bold">
          Option<span className="text-emerald-400">Bot</span>
        </Link>
        <button
          onClick={() => router.back()}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors flex items-center gap-2"
        >
          ← Back
        </button>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {loading ? (
          <div className="text-center py-20 text-gray-500">Loading...</div>
        ) : error ? (
          <div className="text-center py-20 text-red-400">{error}</div>
        ) : result ? (
          <>
            {/* Header */}
            <div className="flex items-start justify-between mb-8">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-gray-500 text-lg">#{result.rank}</span>
                  <h2 className="text-3xl font-bold">{result.ticker}</h2>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      result.strategy === "COVERED_CALL"
                        ? "bg-blue-900/50 text-blue-300 border border-blue-700"
                        : "bg-purple-900/50 text-purple-300 border border-purple-700"
                    }`}
                  >
                    {result.strategy === "COVERED_CALL"
                      ? "Covered Call"
                      : "Cash-Secured Put"}
                  </span>
                </div>
                <p className="text-gray-400">
                  ${result.strike.toFixed(2)} strike · Expires {result.expiry} ·{" "}
                  {result.dte} DTE
                </p>
              </div>
              <div
                className={`text-center px-6 py-4 rounded-xl border ${scoreBg(
                  result.score
                )}`}
              >
                <p className="text-gray-400 text-xs uppercase">Score</p>
                <p
                  className={`text-4xl font-bold ${scoreColor(result.score)}`}
                >
                  {result.score.toFixed(1)}
                </p>
              </div>
            </div>

            {/* Contract Details */}
            <section className="mb-8">
              <h3 className="text-lg font-semibold mb-4 text-gray-300">
                Contract Details
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  label="Strike"
                  value={`$${result.strike.toFixed(2)}`}
                />
                <StatCard label="Expiry" value={result.expiry} />
                <StatCard label="DTE" value={`${result.dte} days`} />
                <StatCard
                  label="Premium"
                  value={`$${result.premium.toFixed(2)}`}
                  sub={`$${(result.premium * 100).toFixed(0)} per contract`}
                />
              </div>
            </section>

            {/* Greeks */}
            <section className="mb-8">
              <h3 className="text-lg font-semibold mb-4 text-gray-300">
                Greeks
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  label="Delta"
                  value={result.delta.toFixed(3)}
                  sub={
                    result.delta > 0
                      ? `${((1 - result.delta) * 100).toFixed(0)}% prob OTM`
                      : `${((1 + result.delta) * 100).toFixed(0)}% prob OTM`
                  }
                  color={
                    Math.abs(result.delta) <= 0.3
                      ? "text-emerald-400"
                      : "text-yellow-400"
                  }
                />
                <StatCard
                  label="Theta"
                  value={`$${result.theta.toFixed(3)}`}
                  sub="Daily time decay"
                  color="text-emerald-400"
                />
                <StatCard
                  label="IV"
                  value={`${(result.iv * 100).toFixed(1)}%`}
                  sub="Implied volatility"
                />
                <StatCard
                  label="Ann. Return"
                  value={`${(result.ann_return * 100).toFixed(1)}%`}
                  sub="Annualised if OTM"
                  color={
                    result.ann_return >= 0.2
                      ? "text-emerald-400"
                      : result.ann_return >= 0.15
                      ? "text-yellow-400"
                      : "text-red-400"
                  }
                />
              </div>
            </section>

            {/* Actions */}
            <section className="mb-8 flex gap-4">
              <button
                onClick={handleStar}
                disabled={isStarred || starring}
                className={`px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                  isStarred
                    ? "bg-yellow-900/30 border border-yellow-700 text-yellow-400"
                    : "bg-gray-800 hover:bg-yellow-900/30 border border-gray-700 hover:border-yellow-700 text-gray-300 hover:text-yellow-400"
                }`}
              >
                {isStarred ? "★ Starred" : starring ? "..." : "☆ Star Candidate"}
              </button>
              <Link
                href="/portfolio"
                className="px-6 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-lg font-medium transition-colors"
              >
                View Portfolio
              </Link>
            </section>

            {/* Quick Assessment */}
            <section className="mb-8">
              <h3 className="text-lg font-semibold mb-4 text-gray-300">
                Quick Assessment
              </h3>
              <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-3">
                <AssessRow
                  label="Delta Safety"
                  good={Math.abs(result.delta) <= 0.3}
                  text={
                    Math.abs(result.delta) <= 0.3
                      ? `Safe — ${Math.abs(result.delta).toFixed(2)} delta is within 0.20–0.30 comfort zone`
                      : `Moderate — ${Math.abs(result.delta).toFixed(2)} delta is on the aggressive side`
                  }
                />
                <AssessRow
                  label="Premium Quality"
                  good={result.premium >= 2.0}
                  text={
                    result.premium >= 5.0
                      ? `Strong — $${result.premium.toFixed(2)} premium is well worth the risk`
                      : result.premium >= 2.0
                      ? `Decent — $${result.premium.toFixed(2)} covers commissions and provides profit`
                      : `Thin — $${result.premium.toFixed(2)} may not justify the trade`
                  }
                />
                <AssessRow
                  label="Time Decay"
                  good={result.theta >= 0.08}
                  text={`$${result.theta.toFixed(3)}/day theta = $${(
                    result.theta * result.dte
                  ).toFixed(2)} total decay over ${result.dte} days`}
                />
                <AssessRow
                  label="Return"
                  good={result.ann_return >= 0.15}
                  text={`${(result.ann_return * 100).toFixed(1)}% annualised ${
                    result.ann_return >= 0.15
                      ? "meets the 15% Wheel Strategy benchmark"
                      : "is below the 15% target"
                  }`}
                />
              </div>
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}

function AssessRow({
  label,
  good,
  text,
}: {
  label: string;
  good: boolean;
  text: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className={`mt-0.5 ${good ? "text-emerald-400" : "text-yellow-400"}`}>
        {good ? "●" : "○"}
      </span>
      <div>
        <span className="text-white font-medium">{label}:</span>{" "}
        <span className="text-gray-400">{text}</span>
      </div>
    </div>
  );
}
