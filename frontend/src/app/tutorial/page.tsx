"use client";

import Link from "next/link";
import Nav from "@/components/Nav";
import { useSession } from "@/hooks/useSession";
import { orderedTutorialPages } from "./content";

export default function TutorialPage() {
  const { token } = useSession();

  if (!token) return null;

  const firstPages = orderedTutorialPages.slice(0, 3);
  const strategyPages = orderedTutorialPages.slice(3);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <section className="border-b border-gray-800 pb-8">
          <p className="text-sm font-medium uppercase tracking-wide text-emerald-400">
            Tutorial
          </p>
          <div className="mt-4 grid gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-3xl font-semibold tracking-normal text-white md:text-4xl">
                Learn the workflow before you rely on the score.
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-gray-300">
                These guides explain how OptionBot reviews covered calls and
                cash-secured puts, how the mean reversion filter works, and how
                to read the Greeks and scan parameters without getting lost in a
                raw option chain.
              </p>
            </div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
                Recommended order
              </h2>
              <ol className="mt-4 space-y-3 text-sm text-gray-300">
                {firstPages.map((page) => (
                  <li key={page.slug} className="flex gap-3">
                    <span className="w-6 shrink-0 font-mono text-emerald-400">
                      {page.order}
                    </span>
                    <span>{page.title}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section className="py-8">
          <h2 className="text-xl font-semibold text-white">Start Here</h2>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            {firstPages.map((page) => (
              <Link
                key={page.slug}
                href={`/tutorial/${page.slug}`}
                className="rounded-lg border border-gray-800 bg-gray-900 p-5 transition hover:border-emerald-700 hover:bg-gray-900/80"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium uppercase tracking-wide text-emerald-400">
                    {page.eyebrow}
                  </span>
                  <span className="text-xs text-gray-500">{page.readTime}</span>
                </div>
                <h3 className="mt-4 text-lg font-semibold text-white">{page.title}</h3>
                <p className="mt-3 text-sm leading-6 text-gray-400">{page.summary}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="pb-10">
          <h2 className="text-xl font-semibold text-white">Strategy And Scanner Guides</h2>
          <div className="mt-5 divide-y divide-gray-800 rounded-lg border border-gray-800 bg-gray-900">
            {strategyPages.map((page) => (
              <Link
                key={page.slug}
                href={`/tutorial/${page.slug}`}
                className="grid gap-3 px-5 py-4 transition hover:bg-gray-800/60 md:grid-cols-[7rem_1fr_auto] md:items-center"
              >
                <span className="text-sm font-mono text-gray-500">
                  {String(page.order).padStart(2, "0")}
                </span>
                <span>
                  <span className="block font-medium text-white">{page.title}</span>
                  <span className="mt-1 block text-sm text-gray-400">{page.summary}</span>
                </span>
                <span className="text-sm text-emerald-400">Read guide</span>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
