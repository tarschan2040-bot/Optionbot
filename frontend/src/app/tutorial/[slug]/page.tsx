"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import Nav from "@/components/Nav";
import { useSession } from "@/hooks/useSession";
import { orderedTutorialPages } from "../content";

export default function TutorialDetailPage() {
  const { token } = useSession();
  const params = useParams<{ slug: string }>();
  const page = orderedTutorialPages.find((item) => item.slug === params.slug);

  if (!token) return null;

  if (!page) {
    return (
      <div className="min-h-screen bg-gray-950 text-white">
        <Nav />
        <main className="mx-auto max-w-3xl px-6 py-16">
          <h1 className="text-2xl font-semibold">Tutorial not found</h1>
          <Link href="/tutorial" className="mt-6 inline-block text-sm text-emerald-400">
            Back to Tutorial
          </Link>
        </main>
      </div>
    );
  }

  const previous = orderedTutorialPages.find((item) => item.order === page.order - 1);
  const next = orderedTutorialPages.find((item) => item.order === page.order + 1);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid gap-8 lg:grid-cols-[16rem_1fr]">
          <aside className="lg:sticky lg:top-6 lg:self-start">
            <Link href="/tutorial" className="text-sm text-emerald-400 hover:text-emerald-300">
              Back to Tutorial
            </Link>
            <nav className="mt-5 divide-y divide-gray-800 rounded-lg border border-gray-800 bg-gray-900">
              {orderedTutorialPages.map((item) => {
                const active = item.slug === page.slug;
                return (
                  <Link
                    key={item.slug}
                    href={`/tutorial/${item.slug}`}
                    className={`block px-4 py-3 text-sm transition ${
                      active
                        ? "bg-gray-800 text-white"
                        : "text-gray-400 hover:bg-gray-800/60 hover:text-white"
                    }`}
                  >
                    <span className="mr-3 font-mono text-xs text-gray-500">
                      {String(item.order).padStart(2, "0")}
                    </span>
                    {item.title}
                  </Link>
                );
              })}
            </nav>
          </aside>

          <article>
            <header className="border-b border-gray-800 pb-8">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="rounded-md bg-emerald-950 px-2 py-1 font-medium text-emerald-300">
                  {page.eyebrow}
                </span>
                <span className="text-gray-500">{page.readTime}</span>
              </div>
              <h1 className="mt-5 max-w-4xl text-3xl font-semibold tracking-normal text-white md:text-4xl">
                {page.title}
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-gray-300">
                {page.summary}
              </p>
            </header>

            <div className="divide-y divide-gray-800">
              {page.sections.map((section) => (
                <section key={section.heading} className="py-7">
                  <h2 className="text-xl font-semibold text-white">{section.heading}</h2>
                  <p className="mt-3 max-w-4xl text-sm leading-7 text-gray-300">
                    {section.body}
                  </p>
                  {section.bullets && (
                    <ul className="mt-4 grid gap-3 md:grid-cols-2">
                      {section.bullets.map((bullet) => (
                        <li
                          key={bullet}
                          className="rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-sm leading-6 text-gray-300"
                        >
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  )}
                  {section.table && (
                    <div className="mt-4 overflow-hidden rounded-lg border border-gray-800">
                      {section.table.map((row) => (
                        <div
                          key={row.label}
                          className="grid gap-2 border-b border-gray-800 bg-gray-900 px-4 py-3 last:border-b-0 md:grid-cols-[12rem_1fr]"
                        >
                          <div className="text-sm font-medium text-white">{row.label}</div>
                          <div className="text-sm leading-6 text-gray-400">{row.value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>

            <section className="mt-2 rounded-lg border border-gray-800 bg-gray-900 p-5">
              <h2 className="text-lg font-semibold text-white">Key Takeaways</h2>
              <ul className="mt-4 space-y-3">
                {page.takeaways.map((takeaway) => (
                  <li key={takeaway} className="text-sm leading-6 text-gray-300">
                    {takeaway}
                  </li>
                ))}
              </ul>
            </section>

            <div className="mt-8 grid gap-3 md:grid-cols-2">
              {previous ? (
                <Link
                  href={`/tutorial/${previous.slug}`}
                  className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm transition hover:border-gray-700 hover:bg-gray-800"
                >
                  <span className="block text-gray-500">Previous</span>
                  <span className="mt-1 block font-medium text-white">{previous.title}</span>
                </Link>
              ) : (
                <div />
              )}
              {next && (
                <Link
                  href={`/tutorial/${next.slug}`}
                  className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm transition hover:border-gray-700 hover:bg-gray-800 md:text-right"
                >
                  <span className="block text-gray-500">Next</span>
                  <span className="mt-1 block font-medium text-white">{next.title}</span>
                </Link>
              )}
            </div>
          </article>
        </div>
      </main>
    </div>
  );
}
