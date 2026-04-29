"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

const NAV_ITEMS = [
  { href: "/portfolio", label: "Portfolio" },
  { href: "/scan", label: "Scan" },
  { href: "/account", label: "Account" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <nav className="border-b border-gray-800 px-6 py-3 flex items-center justify-between bg-gray-950">
      <div className="flex items-center gap-8">
        <Link href="/portfolio" className="text-xl font-bold">
          Option<span className="text-emerald-400">Bot</span>
        </Link>
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
      <button
        onClick={handleSignOut}
        className="text-gray-500 hover:text-gray-300 text-sm transition-colors"
      >
        Sign Out
      </button>
    </nav>
  );
}
