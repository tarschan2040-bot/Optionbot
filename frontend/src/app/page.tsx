"use client";

import { useEffect } from "react";
import { createClient } from "@/lib/supabase";
import { useRouter } from "next/navigation";

/**
 * Root page — redirects to /portfolio if logged in, /login if not.
 */
export default function Home() {
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      router.push(session ? "/portfolio" : "/login");
    });
  }, [router, supabase.auth]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <p className="text-gray-500 text-lg">Loading...</p>
    </div>
  );
}
