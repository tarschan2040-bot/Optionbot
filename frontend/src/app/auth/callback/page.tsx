"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { EmailOtpType } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase";

const DEFAULT_NEXT = "/portfolio";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();
  const [message, setMessage] = useState("Confirming your account...");
  const [error, setError] = useState("");

  const nextPath = useMemo(() => {
    const next = searchParams.get("next");
    return next && next.startsWith("/") ? next : DEFAULT_NEXT;
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;

    async function handleCallback() {
      try {
        const code = searchParams.get("code");
        const tokenHash = searchParams.get("token_hash");
        const rawType = searchParams.get("type");

        const hashParams = new URLSearchParams(window.location.hash.slice(1));
        const hashError = hashParams.get("error_description");

        if (hashError) {
          throw new Error(decodeURIComponent(hashError));
        }

        if (code) {
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (error) throw error;
        } else if (tokenHash && rawType) {
          const { error } = await supabase.auth.verifyOtp({
            token_hash: tokenHash,
            type: rawType as EmailOtpType,
          });
          if (error) throw error;
        }

        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (sessionError) throw sessionError;
        if (!session) {
          throw new Error(
            "Your confirmation link was processed, but no session was created. Please sign in manually."
          );
        }

        if (!cancelled) {
          setMessage("Success. Redirecting to your dashboard...");
          router.replace(nextPath);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to confirm your account.");
          setMessage("");
        }
      }
    }

    handleCallback();

    return () => {
      cancelled = true;
    };
  }, [nextPath, router, searchParams, supabase.auth]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-6">
      <div className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center shadow-xl">
        <h1 className="text-2xl font-bold text-white">
          Option<span className="text-emerald-400">Bot</span>
        </h1>
        {message && <p className="mt-4 text-sm text-gray-300">{message}</p>}
        {error && (
          <div className="mt-4 rounded-lg border border-red-700 bg-red-900/40 p-4 text-left text-sm text-red-200">
            <p className="font-medium text-red-100">Confirmation failed</p>
            <p className="mt-1">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function AuthCallbackFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-6">
      <div className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center shadow-xl">
        <h1 className="text-2xl font-bold text-white">
          Option<span className="text-emerald-400">Bot</span>
        </h1>
        <p className="mt-4 text-sm text-gray-300">Preparing confirmation...</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<AuthCallbackFallback />}>
      <AuthCallbackContent />
    </Suspense>
  );
}
