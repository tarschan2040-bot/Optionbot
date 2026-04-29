"use client";

import { useEffect, useState } from "react";
import { useSession } from "@/hooks/useSession";
import Nav from "@/components/Nav";
import { createClient } from "@/lib/supabase";
import Link from "next/link";

export default function AccountPage() {
  const { token } = useSession();
  const [email, setEmail] = useState("");
  const [currentTier, setCurrentTier] = useState("free");
  const [changingPw, setChangingPw] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) setEmail(user.email || "");
    });
  }, [supabase.auth]);

  async function handleChangePassword() {
    if (!newPassword || newPassword.length < 6) {
      setPwMsg("Password must be at least 6 characters.");
      return;
    }
    setChangingPw(true);
    setPwMsg("");
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      setPwMsg("Password updated successfully.");
      setNewPassword("");
    } catch (err: unknown) {
      setPwMsg(err instanceof Error ? err.message : "Failed to update password.");
    } finally {
      setChangingPw(false);
    }
  }

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold mb-8">Account</h2>

        {/* Profile */}
        <section className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6">
          <h3 className="text-lg font-semibold mb-4">Profile</h3>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-400">Email</label>
              <p className="text-white font-mono mt-1">{email}</p>
            </div>
          </div>
        </section>

        {/* Change Password */}
        <section className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6">
          <h3 className="text-lg font-semibold mb-4">Change Password</h3>
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 6 characters"
                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <button
              onClick={handleChangePassword}
              disabled={changingPw}
              className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg border border-gray-700 transition-colors"
            >
              {changingPw ? "..." : "Update"}
            </button>
          </div>
          {pwMsg && (
            <p className={`mt-3 text-sm ${pwMsg.includes("success") ? "text-emerald-400" : "text-red-400"}`}>
              {pwMsg}
            </p>
          )}
        </section>

        {/* Current Plan */}
        <section className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Subscription</h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide ${
              currentTier === "pro" ? "bg-emerald-900/50 text-emerald-400 border border-emerald-700" : "bg-gray-800 text-gray-400 border border-gray-700"
            }`}>
              {currentTier}
            </span>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            {currentTier === "free"
              ? "You're on the Free plan. Upgrade to Pro for real-time scans, unlimited tickers, and full customisation."
              : "You're on the Pro plan. Full access to all features."}
          </p>
          <Link
            href="/account/plans"
            className="inline-block px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors"
          >
            {currentTier === "free" ? "Upgrade to Pro" : "Manage Plan"}
          </Link>
        </section>
      </main>
    </div>
  );
}
