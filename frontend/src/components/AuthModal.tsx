"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase";

type AuthMode = "login" | "signup";

type AuthModalProps = {
  open: boolean;
  initialMode?: AuthMode;
  onClose: () => void;
};

const TERMS_VERSION = "2026-05-17";

export default function AuthModal({
  open,
  initialMode = "login",
  onClose,
}: AuthModalProps) {
  const router = useRouter();
  const supabase = createClient();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [mobileNo, setMobileNo] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const isSignup = mode === "signup";

  function clearStatus() {
    setError("");
    setMessage("");
  }

  function authRedirectUrl() {
    return typeof window === "undefined"
      ? undefined
      : `${window.location.origin}/auth/callback`;
  }

  async function handleGoogle() {
    clearStatus();
    if (isSignup && !termsAccepted) {
      setError("Please agree to the Terms of Service before signing up.");
      return;
    }

    setLoading(true);
    try {
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: authRedirectUrl(),
          queryParams: {
            access_type: "offline",
            prompt: "consent",
          },
        },
      });
      if (oauthError) throw oauthError;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Google login failed.");
      setLoading(false);
    }
  }

  async function handlePasswordReset() {
    clearStatus();
    if (!email.trim()) {
      setError("Enter your email first, then request a password reset.");
      return;
    }

    setLoading(true);
    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        email.trim(),
        { redirectTo: authRedirectUrl() },
      );
      if (resetError) throw resetError;
      setMessage("Password reset email sent.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to send reset email.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearStatus();

    if (isSignup) {
      if (!firstName.trim() || !lastName.trim()) {
        setError("First name and last name are required.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Password and confirm password do not match.");
        return;
      }
      if (!termsAccepted) {
        setError("Please agree to the Terms of Service before signing up.");
        return;
      }
    }

    setLoading(true);
    try {
      if (isSignup) {
        const { error: signUpError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            emailRedirectTo: authRedirectUrl(),
            data: {
              first_name: firstName.trim(),
              last_name: lastName.trim(),
              mobile_no: mobileNo.trim() || null,
              terms_accepted: true,
              terms_accepted_at: new Date().toISOString(),
              terms_version: TERMS_VERSION,
            },
          },
        });
        if (signUpError) throw signUpError;
        setMessage("Check your email for a confirmation link.");
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (signInError) throw signInError;
        onClose();
        router.push("/portfolio");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 px-4 py-8 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={isSignup ? "Sign up" : "Login"}
    >
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-white/10 bg-gray-950 shadow-2xl">
        <div className="grid grid-cols-2 border-b border-white/10">
          {(["login", "signup"] as AuthMode[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setMode(item);
                clearStatus();
              }}
              className={`px-5 py-4 text-lg font-semibold transition-colors ${
                mode === item
                  ? "bg-gray-900 text-emerald-300"
                  : "bg-gray-950 text-gray-400 hover:bg-gray-900 hover:text-white"
              }`}
            >
              {item === "login" ? "Login" : "Sign Up"}
            </button>
          ))}
        </div>

        <div className="max-h-[82vh] overflow-y-auto px-6 py-6 sm:px-8">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold text-white">
              Option<span className="text-emerald-400">Bot</span>
            </h2>
            <p className="mt-2 text-sm text-gray-400">
              {isSignup
                ? "Create your account and start with the Free plan."
                : "Sign in to review scans, candidates, and portfolio work."}
            </p>
          </div>

          <button
            type="button"
            onClick={handleGoogle}
            disabled={loading}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500 px-4 py-3 text-base font-semibold text-gray-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-300"
          >
            <span className="grid h-7 w-7 place-items-center rounded-full bg-white text-base font-bold text-gray-900">
              G
            </span>
            Continue with Google
          </button>

          <div className="my-6 flex items-center gap-4 text-sm text-gray-500">
            <div className="h-px flex-1 bg-white/10" />
            <span>or</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-sm text-gray-400">First name</span>
                  <input
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                    required
                    className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                    placeholder="First name"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm text-gray-400">Last name</span>
                  <input
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                    required
                    className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                    placeholder="Last name"
                  />
                </label>
              </div>
            )}

            <label className="block">
              <span className="mb-1 block text-sm text-gray-400">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                placeholder="you@example.com"
              />
            </label>

            {isSignup && (
              <label className="block">
                <span className="mb-1 block text-sm text-gray-400">
                  Mobile number <span className="text-gray-600">(optional)</span>
                </span>
                <input
                  type="tel"
                  value={mobileNo}
                  onChange={(event) => setMobileNo(event.target.value)}
                  className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                  placeholder="+1 555 123 4567"
                />
              </label>
            )}

            <label className="block">
              <span className="mb-1 block text-sm text-gray-400">Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={6}
                className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                placeholder="Password"
              />
            </label>

            {isSignup && (
              <>
                <label className="block">
                  <span className="mb-1 block text-sm text-gray-400">
                    Confirm password
                  </span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                    minLength={6}
                    className="w-full rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-white outline-none focus:border-emerald-400"
                    placeholder="Confirm password"
                  />
                </label>

                <label className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm leading-6 text-gray-300">
                  <input
                    type="checkbox"
                    checked={termsAccepted}
                    onChange={(event) => setTermsAccepted(event.target.checked)}
                    className="mt-1 h-4 w-4 accent-emerald-500"
                    required
                  />
                  <span>
                    I agree to the{" "}
                    <Link
                      href="/terms-of-service"
                      target="_blank"
                      className="font-semibold text-emerald-300 hover:text-emerald-200"
                    >
                      Terms of Service
                    </Link>
                    .
                  </span>
                </label>
              </>
            )}

            {error && (
              <div className="rounded-xl border border-red-700 bg-red-950/50 p-3 text-sm text-red-200">
                {error}
              </div>
            )}
            {message && (
              <div className="rounded-xl border border-emerald-700 bg-emerald-950/50 p-3 text-sm text-emerald-200">
                {message}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-gray-700"
            >
              {loading ? "Please wait..." : isSignup ? "Create Account" : "Login"}
            </button>
          </form>

          {!isSignup && (
            <button
              type="button"
              onClick={handlePasswordReset}
              disabled={loading}
              className="mt-4 w-full text-center text-sm font-medium text-emerald-300 hover:text-emerald-200"
            >
              Forgot password
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="mt-6 w-full rounded-xl border border-gray-700 px-4 py-3 font-medium text-gray-200 transition-colors hover:bg-gray-900 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
