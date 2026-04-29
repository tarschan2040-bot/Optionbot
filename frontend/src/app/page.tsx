"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase";
import { useRouter } from "next/navigation";
import Link from "next/link";

// ── Icons (inline SVG) ────────────────────────────────────────────────

function ScanIcon() {
  return (
    <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg className="w-8 h-8 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
    </svg>
  );
}
function ChartIcon() {
  return (
    <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  );
}
function ShieldIcon() {
  return (
    <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}
function BoltIcon() {
  return (
    <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function CheckMark() {
  return <span className="text-emerald-400 mr-2">✓</span>;
}
function CrossMark() {
  return <span className="text-gray-600 mr-2">✗</span>;
}

// ── Main Landing Page ─────────────────────────────────────────────────

export default function LandingPage() {
  const [checking, setChecking] = useState(true);
  const router = useRouter();
  const supabase = createClient();

  // Redirect logged-in users to portfolio
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        router.push("/portfolio");
      } else {
        setChecking(false);
      }
    });
  }, [router, supabase.auth]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* ── Navbar ──────────────────────────────────────────────── */}
      <nav className="border-b border-gray-800/50 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <span className="text-xl font-bold">
            Option<span className="text-emerald-400">Bot</span>
          </span>
          <div className="flex items-center gap-4">
            <a href="#pricing" className="text-gray-400 hover:text-white text-sm transition-colors">
              Pricing
            </a>
            <Link
              href="/login"
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/login"
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Get Started Free
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="px-6 pt-20 pb-16">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-block px-4 py-1.5 bg-emerald-900/30 border border-emerald-700/50 rounded-full text-emerald-400 text-sm font-medium mb-6">
            The Wheel Strategy, Automated
          </div>
          <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
            Generate Passive Income
            <br />
            <span className="text-emerald-400">From Your Stock Portfolio</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            OptionBot scans thousands of options contracts, scores them on 6 factors,
            and finds the best Covered Call and Cash-Secured Put opportunities —
            so you can collect premium consistently with confidence.
          </p>
          <div className="flex items-center justify-center gap-4 mb-16">
            <Link
              href="/login"
              className="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 text-white text-lg font-semibold rounded-xl transition-colors"
            >
              Start Scanning Free
            </Link>
            <a
              href="#how-it-works"
              className="px-8 py-4 bg-gray-800 hover:bg-gray-700 text-gray-300 text-lg font-medium rounded-xl border border-gray-700 transition-colors"
            >
              How It Works
            </a>
          </div>

          {/* Product screenshot mockup */}
          <div className="relative max-w-5xl mx-auto">
            <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 shadow-2xl shadow-emerald-900/10">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                <span className="text-gray-500 text-xs ml-2">OptionBot Scanner</span>
              </div>
              <div className="bg-gray-950 rounded-xl p-4 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 text-left border-b border-gray-800">
                      <th className="pb-2 pr-4">#</th>
                      <th className="pb-2 pr-4">Ticker</th>
                      <th className="pb-2 pr-4">Strategy</th>
                      <th className="pb-2 pr-4 text-right">Strike</th>
                      <th className="pb-2 pr-4 text-right">Premium</th>
                      <th className="pb-2 pr-4 text-right">Delta</th>
                      <th className="pb-2 pr-4 text-right">Ann%</th>
                      <th className="pb-2 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody className="text-gray-300">
                    <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-gray-500">1</td><td className="py-2 pr-4 font-semibold">TSLA</td><td className="py-2 pr-4"><span className="px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs">CSP</span></td><td className="py-2 pr-4 text-right">$181.40</td><td className="py-2 pr-4 text-right">$12.02</td><td className="py-2 pr-4 text-right">-0.27</td><td className="py-2 pr-4 text-right">115.1%</td><td className="py-2 text-right font-bold text-emerald-400">69.6</td></tr>
                    <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-gray-500">2</td><td className="py-2 pr-4 font-semibold">NVDA</td><td className="py-2 pr-4"><span className="px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs">CC</span></td><td className="py-2 pr-4 text-right">$135.00</td><td className="py-2 pr-4 text-right">$8.45</td><td className="py-2 pr-4 text-right">+0.31</td><td className="py-2 pr-4 text-right">89.3%</td><td className="py-2 text-right font-bold text-emerald-400">67.2</td></tr>
                    <tr className="border-b border-gray-800/50"><td className="py-2 pr-4 text-gray-500">3</td><td className="py-2 pr-4 font-semibold">AAPL</td><td className="py-2 pr-4"><span className="px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs">CSP</span></td><td className="py-2 pr-4 text-right">$205.00</td><td className="py-2 pr-4 text-right">$6.80</td><td className="py-2 pr-4 text-right">-0.24</td><td className="py-2 pr-4 text-right">72.1%</td><td className="py-2 text-right font-bold text-yellow-400">62.8</td></tr>
                    <tr><td className="py-2 pr-4 text-gray-500">4</td><td className="py-2 pr-4 font-semibold">MSFT</td><td className="py-2 pr-4"><span className="px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs">CC</span></td><td className="py-2 pr-4 text-right">$440.00</td><td className="py-2 pr-4 text-right">$9.25</td><td className="py-2 pr-4 text-right">+0.28</td><td className="py-2 pr-4 text-right">68.5%</td><td className="py-2 text-right font-bold text-yellow-400">59.4</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust Bar ───────────────────────────────────────────── */}
      <section className="px-6 py-12 border-y border-gray-800/50">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <p className="text-3xl font-bold text-emerald-400">81%</p>
            <p className="text-gray-400 text-sm mt-1">Win Rate</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-white">6</p>
            <p className="text-gray-400 text-sm mt-1">Scoring Factors</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-white">3x</p>
            <p className="text-gray-400 text-sm mt-1">Daily Auto-Scans</p>
          </div>
          <div>
            <p className="text-3xl font-bold text-white">$0</p>
            <p className="text-gray-400 text-sm mt-1">To Get Started</p>
          </div>
        </div>
      </section>

      {/* ── How It Works ────────────────────────────────────────── */}
      <section id="how-it-works" className="px-6 py-20">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">How It Works</h2>
          <p className="text-gray-400 text-center mb-14 max-w-xl mx-auto">
            Three steps to consistent premium income using the Wheel Strategy
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800 text-center">
              <div className="w-14 h-14 bg-emerald-900/30 rounded-xl flex items-center justify-center mx-auto mb-5">
                <ScanIcon />
              </div>
              <div className="text-emerald-400 text-sm font-bold mb-2">STEP 1</div>
              <h3 className="text-xl font-bold mb-3">Scan</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                OptionBot scans your watchlist across thousands of option contracts,
                filtering by delta, IV, theta, and premium quality.
              </p>
            </div>
            <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800 text-center">
              <div className="w-14 h-14 bg-yellow-900/30 rounded-xl flex items-center justify-center mx-auto mb-5">
                <StarIcon />
              </div>
              <div className="text-emerald-400 text-sm font-bold mb-2">STEP 2</div>
              <h3 className="text-xl font-bold mb-3">Select</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Each opportunity is scored 0–100 on 6 factors. Star the best ones,
                review the Greeks breakdown, and confirm when ready to trade.
              </p>
            </div>
            <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800 text-center">
              <div className="w-14 h-14 bg-emerald-900/30 rounded-xl flex items-center justify-center mx-auto mb-5">
                <ChartIcon />
              </div>
              <div className="text-emerald-400 text-sm font-bold mb-2">STEP 3</div>
              <h3 className="text-xl font-bold mb-3">Collect</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Track your positions with live P&L, current prices, and portfolio
                performance. Collect premium as time decay works in your favour.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────── */}
      <section className="px-6 py-20 bg-gray-900/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Built for the Wheel Strategy</h2>
          <p className="text-gray-400 text-center mb-14 max-w-xl mx-auto">
            Everything you need to run Covered Calls and Cash-Secured Puts profitably
          </p>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="flex gap-5">
              <div className="shrink-0"><ShieldIcon /></div>
              <div>
                <h3 className="text-lg font-bold mb-2">6-Factor Scoring</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Every opportunity is scored on IV, theta yield, delta safety, liquidity,
                  annualised return, and mean reversion timing. No guesswork — data-driven decisions.
                </p>
              </div>
            </div>
            <div className="flex gap-5">
              <div className="shrink-0"><BoltIcon /></div>
              <div>
                <h3 className="text-lg font-bold mb-2">Automated Daily Scans</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Three scans per trading day at market open, midday, and pre-close.
                  Results delivered to your dashboard automatically — scan while you sleep.
                </p>
              </div>
            </div>
            <div className="flex gap-5">
              <div className="shrink-0"><ChartIcon /></div>
              <div>
                <h3 className="text-lg font-bold mb-2">Live Portfolio Tracking</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Track open positions with real-time stock prices, current option values,
                  P&L per trade, and portfolio-level performance summaries.
                </p>
              </div>
            </div>
            <div className="flex gap-5">
              <div className="shrink-0"><ClockIcon /></div>
              <div>
                <h3 className="text-lg font-bold mb-2">Full Parameter Control</h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Customise every filter: DTE range, delta bounds, IV floors, premium minimums,
                  and scoring weights. Your strategy, your rules.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Why Wheel Strategy ──────────────────────────────────── */}
      <section className="px-6 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Why the Wheel Strategy?</h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            The Wheel is the most reliable options income strategy for stock investors.
            You sell premium on stocks you&apos;d happily own, collect income while waiting,
            and let time decay do the work.
          </p>
          <div className="grid md:grid-cols-3 gap-6 text-left">
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <p className="text-2xl font-bold text-emerald-400 mb-2">Passive</p>
              <p className="text-gray-400 text-sm">
                Sell options, collect premium, repeat. No day trading, no chart watching.
                OptionBot finds the best contracts so you don&apos;t have to.
              </p>
            </div>
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <p className="text-2xl font-bold text-emerald-400 mb-2">Consistent</p>
              <p className="text-gray-400 text-sm">
                Theta decay is mathematically predictable. With proper delta selection,
                you keep full premium 70-80% of the time.
              </p>
            </div>
            <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
              <p className="text-2xl font-bold text-emerald-400 mb-2">Controlled</p>
              <p className="text-gray-400 text-sm">
                You choose the stocks, the strikes, and the risk level. Every parameter
                is tunable. You&apos;re always in control.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ─────────────────────────────────────────────── */}
      <section id="pricing" className="px-6 py-20 bg-gray-900/30">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-4">Simple, Transparent Pricing</h2>
          <p className="text-gray-400 text-center mb-14">
            Start free. Upgrade when you&apos;re ready for full power.
          </p>
          <div className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">
            {/* Free */}
            <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800">
              <h3 className="text-2xl font-bold">Free</h3>
              <div className="mt-2 mb-1">
                <span className="text-4xl font-bold">$0</span>
              </div>
              <p className="text-gray-500 text-sm mb-6">Free forever</p>
              <p className="text-gray-400 text-sm mb-8">Get started with basic scanning</p>
              <Link
                href="/login"
                className="block w-full py-3 bg-gray-800 text-center text-gray-300 font-semibold rounded-lg mb-8"
              >
                Get Started
              </Link>
              <div className="space-y-3 text-sm">
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Daily top 5 results (delayed)</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">2 tickers</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Default scoring parameters</span></div>
                <div className="flex items-start"><CrossMark /><span className="text-gray-600">Real-time scans</span></div>
                <div className="flex items-start"><CrossMark /><span className="text-gray-600">Custom parameters</span></div>
                <div className="flex items-start"><CrossMark /><span className="text-gray-600">Portfolio tracking</span></div>
                <div className="flex items-start"><CrossMark /><span className="text-gray-600">Email / Telegram alerts</span></div>
              </div>
            </div>
            {/* Pro */}
            <div className="bg-gray-900 rounded-2xl p-8 border border-emerald-700 ring-1 ring-emerald-700/50 relative">
              <span className="absolute -top-3 left-8 px-3 py-1 bg-emerald-600 text-white text-xs font-bold rounded-full uppercase tracking-wide">
                Most Popular
              </span>
              <h3 className="text-2xl font-bold">Pro</h3>
              <div className="mt-2 mb-1">
                <span className="text-4xl font-bold">$49</span>
                <span className="text-gray-400 text-sm">/month</span>
              </div>
              <p className="text-gray-500 text-sm mb-6">$39/mo billed annually</p>
              <p className="text-gray-400 text-sm mb-8">Full power for active traders</p>
              <Link
                href="/login"
                className="block w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-center text-white font-semibold rounded-lg transition-colors mb-8"
              >
                Start Free Trial
              </Link>
              <div className="space-y-3 text-sm">
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Real-time scans (3 daily + manual)</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Unlimited tickers</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Full parameter customisation</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Custom scoring weights</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Trade workflow (Star → Confirm → Track)</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Live portfolio with P&L</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Email alerts (daily digest)</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Telegram bot integration</span></div>
                <div className="flex items-start"><CheckMark /><span className="text-gray-300">Priority scan queue</span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────────────────────── */}
      <section className="px-6 py-20">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">
            Stop Guessing. Start Scanning.
          </h2>
          <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
            Join traders who use data-driven scoring to find the best option premium
            opportunities every single day.
          </p>
          <Link
            href="/login"
            className="inline-block px-10 py-4 bg-emerald-600 hover:bg-emerald-500 text-white text-lg font-semibold rounded-xl transition-colors"
          >
            Get Started Free
          </Link>
          <p className="text-gray-600 text-sm mt-4">No credit card required</p>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-gray-800/50 px-6 py-10">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-gray-500 text-sm">
            &copy; 2026 OptionBot. All rights reserved.
          </span>
          <div className="flex gap-6 text-gray-500 text-sm">
            <span>Options involve risk. Past performance does not guarantee future results.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
