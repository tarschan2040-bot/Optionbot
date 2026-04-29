"use client";

import { useState } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import Link from "next/link";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Get started with basic scanning",
    features: [
      "Previous day's top 5 results (delayed)",
      "2 tickers max",
      "Default scoring weights (read-only)",
      "Community Discord (read-only)",
    ],
    limitations: [
      "No real-time scans",
      "No custom parameters",
      "No trade workflow",
    ],
    cta: "Current Plan",
    highlighted: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: "$49",
    period: "/month",
    yearlyPrice: "$39/mo billed annually",
    description: "Full power for active options traders",
    features: [
      "Real-time scans (3 daily + manual)",
      "Unlimited tickers",
      "Full parameter customisation",
      "Custom scoring weights",
      "Trade workflow (star → confirm → track)",
      "Live portfolio with P&L tracking",
      "Email alerts (daily digest)",
      "Telegram bot integration",
      "Priority scan queue",
      "Community Discord (full access)",
    ],
    limitations: [],
    cta: "Upgrade to Pro",
    highlighted: true,
  },
];

function CheckIcon() {
  return <span className="text-emerald-400 mr-2">✓</span>;
}
function CrossIcon() {
  return <span className="text-gray-600 mr-2">✗</span>;
}

export default function PlansPage() {
  const { token } = useSession();
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-10">
          <Link href="/account" className="text-gray-400 hover:text-white text-sm mb-4 inline-block">← Back to Account</Link>
          <h2 className="text-3xl font-bold mb-3">Choose Your Plan</h2>
          <p className="text-gray-400 max-w-md mx-auto">
            OptionBot scores and ranks Covered Call and Cash-Secured Put opportunities so you can trade with confidence.
          </p>
        </div>

        {/* Billing toggle */}
        <div className="flex justify-center mb-10">
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
            <button
              onClick={() => setBilling("monthly")}
              className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${billing === "monthly" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling("annual")}
              className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${billing === "annual" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
            >
              Annual <span className="text-emerald-400 text-xs ml-1">Save 20%</span>
            </button>
          </div>
        </div>

        {/* Plans */}
        <div className="grid md:grid-cols-2 gap-6">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`rounded-2xl p-8 border ${
                plan.highlighted
                  ? "bg-gray-900 border-emerald-700 ring-1 ring-emerald-700/50"
                  : "bg-gray-900 border-gray-800"
              }`}
            >
              {plan.highlighted && (
                <span className="inline-block px-3 py-1 bg-emerald-900/50 text-emerald-400 text-xs font-bold rounded-full mb-4 uppercase tracking-wide">
                  Most Popular
                </span>
              )}
              <h3 className="text-2xl font-bold">{plan.name}</h3>
              <div className="mt-2 mb-1">
                <span className="text-4xl font-bold">
                  {billing === "annual" && plan.id === "pro" ? "$39" : plan.price}
                </span>
                <span className="text-gray-400 text-sm">
                  {plan.id === "pro" ? (billing === "annual" ? "/mo" : "/month") : ""}
                </span>
              </div>
              {plan.id === "pro" && billing === "annual" && (
                <p className="text-gray-500 text-xs mb-3">Billed annually ($468/year)</p>
              )}
              {plan.id === "pro" && billing === "monthly" && (
                <p className="text-gray-500 text-xs mb-3">Billed monthly</p>
              )}
              <p className="text-gray-400 text-sm mb-6">{plan.description}</p>

              <button
                className={`w-full py-3 rounded-lg font-semibold transition-colors mb-8 ${
                  plan.highlighted
                    ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                    : "bg-gray-800 text-gray-400 cursor-default"
                }`}
                disabled={!plan.highlighted}
              >
                {plan.cta}
              </button>

              <div className="space-y-3">
                {plan.features.map((f, i) => (
                  <div key={i} className="flex items-start text-sm">
                    <CheckIcon />
                    <span className="text-gray-300">{f}</span>
                  </div>
                ))}
                {plan.limitations.map((f, i) => (
                  <div key={i} className="flex items-start text-sm">
                    <CrossIcon />
                    <span className="text-gray-600">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* FAQ-style note */}
        <div className="mt-12 text-center">
          <p className="text-gray-500 text-sm">
            All plans include a 7-day free trial of Pro. Cancel anytime.
          </p>
          <p className="text-gray-600 text-xs mt-2">
            Stripe payments coming soon. Contact us for early access.
          </p>
        </div>
      </main>
    </div>
  );
}
