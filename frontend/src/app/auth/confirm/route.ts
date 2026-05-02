import { createServerClient } from "@supabase/ssr";
import { type EmailOtpType } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";
import { NextRequest, NextResponse } from "next/server";

const DEFAULT_NEXT = "/portfolio";

function buildRedirectURL(request: NextRequest, path: string, error?: string) {
  const url = new URL(path, request.url);
  if (error) {
    url.searchParams.set("error", error);
  }
  return url;
}

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const tokenHash = requestUrl.searchParams.get("token_hash");
  const rawType = requestUrl.searchParams.get("type");
  const next = requestUrl.searchParams.get("next");
  const nextPath = next && next.startsWith("/") ? next : DEFAULT_NEXT;

  if (!tokenHash || !rawType) {
    return NextResponse.redirect(
      buildRedirectURL(request, "/auth/callback", "Missing confirmation token.")
    );
  }

  const cookieStore = await cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: Partial<ResponseCookie> }[]) {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        },
      },
    }
  );

  const { error } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type: rawType as EmailOtpType,
  });

  if (error) {
    return NextResponse.redirect(
      buildRedirectURL(request, "/auth/callback", error.message)
    );
  }

  return NextResponse.redirect(buildRedirectURL(request, nextPath));
}
