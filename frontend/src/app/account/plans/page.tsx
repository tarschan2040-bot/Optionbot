"use client";

import { useState } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import Link from "next/link";

function Check() { return <span className="text-emerald-400 mr-2">✓</span>; }
function Cross() { return <span className="text-gray-600 mr-2">✗</span>; }

const PLANS = [
  {
    id: "free",
    name: "Free",
    monthlyPrice: 0,
    yearlyPrice: 0,
    description: "Get started with basic scanning",
    features: [
      { text: "3 scans per day", included: true },
      { text: "Top 3 results visible", included: true },
      { text: "Default parameters (read-only)", included: true },
      { text: "Score, delta, premium data", included: true },
      { text: "Full scan results", included: false },
      { text: "Custom parameters", included: false },
      { text: "Portfolio tracking", included: false },
      { text: "Email / Telegram alerts", included: false },
    ],
    cta: "Current Plan",
    highlighted: false,
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 19.99,
    yearlyPrice: 15.99,
    description: "Full scanning power for active traders",
    features: [
      { text: "30 scans per day", included: true },
      { text: "All scan results visible", included: true },
      { text: "Full parameter customisation", included: true },
      { text: "Portfolio tracking (10 trades)", included: true },
      { text: "Live P&L and market data", included: true },
      { text: "Trade workflow (Star → Confirm)", included: true },
      { text: "Email alerts (daily digest)", included: true },
      { text: "Unlimited portfolio", included: false },
      { text: "Priority scan queue", included: false },
    ],
    cta: "Upgrade to Pro",
    highlighted: true,
    badge: "Most Popular",
  },
  {
    id: "max",
    name: "Max",
    monthlyPrice: 49.99,
    yearlyPrice: 39.99,
    description: "Unlimited everything for serious traders",
    features: [
      { text: "Unlimited scans per day", included: true },
      { text: "All scan results visible", included: true },
      { text: "Full parameter customisation", included: true },
      { text: "Unlimited portfolio tracking", included: true },
      { text: "Live P&L and market data", included: true },
      { text: "Trade workflow (Star → Confirm)", included: true },
      { text: "Email + Telegram alerts", included: true },
      { text: "Priority scan queue", included: true },
      { text: "API access (coming soon)", included: true },
    ],
    cta: "Upgrade to Max",
    highlighted: false,
    badge: "Full Power",
  },
];

export default function PlansPage() {
  const { token } = useSession();
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-5xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <Link href="/account" className="text-gray-400 hover:text-white text-sm mb-4 inline-block">← Back to Account</Link>
          <h2 className="text-3xl font-bold mb-3">Choose Your Plan</h2>
          <p className="text-gray-400 max-w-md mx-auto">
            Scale your options scanning from casual to professional.
          </p>
        </div>

        {/* Billing toggle */}
        <div className="flex justify-center mb-10">
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
            <button onClick={() => setBilling("monthly")} className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${billing === "monthly" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}>
              Monthly
            </button>
            <button onClick={() => setBilling("annual")} className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${billing === "annual" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}>
              Annual <span className="text-emerald-400 text-xs ml-1">Save 20%</span>
            </button>
          </div>
        </div>

        {/* Plans grid */}
        <div className="grid md:grid-cols-3 gap-6">
          {PLANS.map((plan) => {
            const price = billing === "annual" ? plan.yearlyPrice : plan.monthlyPrice;
            return (
              <div
                key={plan.id}
                className={`rounded-2xl p-7 border relative ${
                  plan.highlighted
                    ? "bg-gray-900 border-emerald-700 ring-1 ring-emerald-700/50"
                    : "bg-gray-900 border-gray-800"
                }`}
              >
                {plan.badge && (
                  <span className={`absolute -top-3 left-7 px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wide ${
                    plan.highlighted
                      ? "bg-emerald-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}>
                    {plan.badge}
                  </span>
                )}
                <h3 className="text-2xl font-bold">{plan.name}</h3>
                <div className="mt-2 mb-1">
                  <span className="text-4xl font-bold">
                    ${price === 0 ? "0" : price.toFixed(2)}
                  </span>
                  {price > 0 && <span className="text-gray-400 text-sm">/mo</span>}
                </div>
                {price > 0 && billing === "annual" && (
                  <p className="text-gray-500 text-xs mb-3">Billed annually</p>
                )}
                {price === 0 && <p className="text-gray-500 text-xs mb-3">Free forever</p>}
                <p className="text-gray-400 text-sm mb-6">{plan.description}</p>

                <button
                  className={`w-full py-3 rounded-lg font-semibold transition-colors mb-7 ${
                    plan.highlighted
                      ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                      : plan.id === "free"
                      ? "bg-gray-800 text-gray-400 cursor-default"
                      : "bg-gray-800 hover:bg-gray-700 text-white border border-gray-700"
                  }`}
                  disabled={plan.id === "free"}
                >
                  {plan.cta}
                </button>

                <div className="space-y-3">
                  {plan.features.map((f, i) => (
                    <div key={i} className="flex items-start text-sm">
                      {f.included ? <Check /> : <Cross />}
                      <span className={f.included ? "text-gray-300" : "text-gray-600"}>{f.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Comparison table */}
        <div className="mt-16">
          <h3 className="text-xl font-bold text-center mb-8">Feature Comparison</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="pb-3 text-left font-medium">Feature</th>
                  <th className="pb-3 text-center font-medium">Free</th>
                  <th className="pb-3 text-center font-medium text-emerald-400">Pro</th>
                  <th className="pb-3 text-center font-medium">Max</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                <tr className="border-b border-gray-800/50"><td className="py-3">Daily scans</td><td className="py-3 text-center">3</td><td className="py-3 text-center">30</td><td className="py-3 text-center">Unlimited</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Visible results</td><td className="py-3 text-center">Top 3</td><td className="py-3 text-center">All</td><td className="py-3 text-center">All</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Custom parameters</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">✓</td><td className="py-3 text-center text-emerald-400">✓</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Portfolio tracking</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center">10 trades</td><td className="py-3 text-center">Unlimited</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Live P&L</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">✓</td><td className="py-3 text-center text-emerald-400">✓</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Email alerts</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">✓</td><td className="py-3 text-center text-emerald-400">✓</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Telegram bot</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">✓</td></tr>
                <tr className="border-b border-gray-800/50"><td className="py-3">Priority queue</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">✓</td></tr>
                <tr><td className="py-3">API access</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-gray-600">✗</td><td className="py-3 text-center text-emerald-400">Coming soon</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-12 text-center">
          <p className="text-gray-500 text-sm">7-day free trial on all paid plans. Cancel anytime.</p>
          <p className="text-gray-600 text-xs mt-2">Stripe payments coming soon.</p>
        </div>
      </main>
    </div>
  );
}
