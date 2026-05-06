"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createClient } from "@/lib/supabase";

type CategoryId =
  | "own-stock"
  | "income"
  | "bullish"
  | "bearish"
  | "neutral"
  | "protection";
type GoalId = "income" | "bullish" | "bearish" | "neutral" | "protection";
type ExperienceId = "beginner" | "some" | "advanced";
type LanguageId = "zh-CN" | "zh-TW" | "en" | "es" | "fr";

type Strategy = {
  id: string;
  name: string;
  categories: CategoryId[];
  purpose: string;
  bestWhen: string;
  risk: string;
  ownership: string;
  beginnerFriendly: string;
  beginnerRank: number;
  scannerLens: string;
  example: (ticker: string) => string;
};

const LANGUAGE_STORAGE_KEY = "optionbot-language";

const LANGUAGE_OPTIONS: Array<{
  id: LanguageId;
  name: string;
  menuName: string;
  shortLabel: string;
  flag: string;
  htmlLang: string;
}> = [
  {
    id: "zh-CN",
    name: "Simplified Chinese",
    menuName: "简体中文",
    shortLabel: "简",
    flag: "🇨🇳",
    htmlLang: "zh-CN",
  },
  {
    id: "zh-TW",
    name: "Traditional Chinese",
    menuName: "繁體中文",
    shortLabel: "繁",
    flag: "🇹🇼",
    htmlLang: "zh-TW",
  },
  {
    id: "en",
    name: "English",
    menuName: "English",
    shortLabel: "EN",
    flag: "🇺🇸",
    htmlLang: "en",
  },
  {
    id: "es",
    name: "Spanish",
    menuName: "Español",
    shortLabel: "ES",
    flag: "🇪🇸",
    htmlLang: "es",
  },
  {
    id: "fr",
    name: "French",
    menuName: "Français",
    shortLabel: "FR",
    flag: "🇫🇷",
    htmlLang: "fr",
  },
];

const LANDING_NAV_COPY: Record<
  LanguageId,
  {
    strategyChooser: string;
    strategyMap: string;
    realStockExamples: string;
    pricing: string;
    signIn: string;
    startFree: string;
    languageMenu: string;
  }
> = {
  "zh-CN": {
    strategyChooser: "策略选择",
    strategyMap: "策略地图",
    realStockExamples: "真实股票示例",
    pricing: "价格",
    signIn: "登录",
    startFree: "免费开始",
    languageMenu: "选择语言",
  },
  "zh-TW": {
    strategyChooser: "策略選擇",
    strategyMap: "策略地圖",
    realStockExamples: "真實股票範例",
    pricing: "價格",
    signIn: "登入",
    startFree: "免費開始",
    languageMenu: "選擇語言",
  },
  en: {
    strategyChooser: "Strategy Chooser",
    strategyMap: "Strategy Map",
    realStockExamples: "Real Stock Examples",
    pricing: "Pricing",
    signIn: "Sign In",
    startFree: "Start free",
    languageMenu: "Choose language",
  },
  es: {
    strategyChooser: "Estrategias",
    strategyMap: "Mapa",
    realStockExamples: "Ejemplos reales",
    pricing: "Precios",
    signIn: "Entrar",
    startFree: "Gratis",
    languageMenu: "Elegir idioma",
  },
  fr: {
    strategyChooser: "Strategies",
    strategyMap: "Carte",
    realStockExamples: "Exemples reels",
    pricing: "Tarifs",
    signIn: "Connexion",
    startFree: "Essai gratuit",
    languageMenu: "Choisir la langue",
  },
};

const LEGAL_LINKS = [
  { href: "/terms-and-conditions", label: "Terms and Conditions" },
  { href: "/terms-of-use", label: "Terms of Use" },
  { href: "/privacy-notice", label: "Privacy Notice" },
  { href: "/cookie-policy", label: "Cookie Policy" },
  { href: "/modern-slavery", label: "Modern Slavery" },
];

function isLanguageId(value: string | null): value is LanguageId {
  return LANGUAGE_OPTIONS.some((option) => option.id === value);
}

const CATEGORY_META: Record<CategoryId, { label: string; blurb: string }> = {
  "own-stock": {
    label: "Own Stock",
    blurb: "You already have shares and want income or protection around that position.",
  },
  income: {
    label: "Income",
    blurb: "You want premium income without starting from an overwhelming option chain.",
  },
  bullish: {
    label: "Bullish",
    blurb: "You think the stock can move higher and want a strategy to match that view.",
  },
  bearish: {
    label: "Bearish",
    blurb: "You expect weakness or want to fade a rally with defined trade-offs.",
  },
  neutral: {
    label: "Neutral",
    blurb: "You expect a stock to stay in a range and want strategies that fit calmer price action.",
  },
  protection: {
    label: "Protection",
    blurb: "You want downside protection for shares you already own.",
  },
};

const HERO_GOALS: Array<{
  id: GoalId;
  label: string;
  summary: string;
  coaching: string;
}> = [
  {
    id: "income",
    label: "Earn income",
    summary: "Collect premium from stocks you already own or would be happy to own.",
    coaching:
      "We start with the simplest income strategies first, then point you toward live scans when you are ready.",
  },
  {
    id: "protection",
    label: "Protect shares",
    summary: "Defend a stock position without having to become an options expert first.",
    coaching:
      "Protection-first strategies work best when you already own the stock and want calmer downside risk.",
  },
  {
    id: "bullish",
    label: "Bullish",
    summary: "Express an upside view with strategies that match how aggressive or cautious you want to be.",
    coaching:
      "We can show stock-linked income ideas, defined-risk spreads, or lower-capital stock replacements.",
  },
  {
    id: "bearish",
    label: "Bearish",
    summary: "Position for weakness with defined trade-offs instead of guessing from a raw options chain.",
    coaching:
      "Bearish strategies can be income-oriented, directional, or built to fade a rally from resistance.",
  },
  {
    id: "neutral",
    label: "Neutral",
    summary: "Use range-bound strategies when you expect a stock to stay relatively calm.",
    coaching:
      "Neutral setups can be powerful once the market view is clear and the trade structure is understood.",
  },
];

const EXPERIENCE_LEVELS: Array<{
  id: ExperienceId;
  label: string;
  summary: string;
}> = [
  {
    id: "beginner",
    label: "Beginner",
    summary: "Show simpler, clearer strategies first.",
  },
  {
    id: "some",
    label: "Some experience",
    summary: "Blend simpler ideas with straightforward spreads.",
  },
  {
    id: "advanced",
    label: "Advanced",
    summary: "Include multi-leg structures and capital-efficient variations.",
  },
];

const CATEGORY_ORDER: CategoryId[] = [
  "own-stock",
  "income",
  "bullish",
  "bearish",
  "neutral",
  "protection",
];

const STRATEGIES: Strategy[] = [
  {
    id: "covered-call",
    name: "Covered Call",
    categories: ["own-stock", "income", "neutral"],
    purpose: "Generate income from shares you already own.",
    bestWhen:
      "You already own 100 shares, want extra income, and would be okay selling those shares at a higher price.",
    risk:
      "You still keep most of the stock downside, and a sharp rally can force you to sell sooner than planned.",
    ownership: "Yes. Usually 100 shares per contract.",
    beginnerFriendly: "Yes. Often one of the easiest stock-linked options strategies.",
    beginnerRank: 1,
    scannerLens:
      "OptionBot can look for liquid calls with worthwhile premium, sensible delta, and expiries that fit your pace.",
    example: (ticker) =>
      `Own 100 shares of ${ticker}? A Covered Call can turn that holding into an income-producing trade while you wait.`,
  },
  {
    id: "cash-secured-put",
    name: "Cash-Secured Put",
    categories: ["income", "bullish"],
    purpose: "Get paid while waiting to buy a stock at a lower price.",
    bestWhen:
      "You are bullish or neutral and would genuinely be happy owning the stock if assignment happens.",
    risk:
      "You can still end up owning the stock through a drop, so the downside after assignment can be meaningful.",
    ownership: "No shares required, but you need enough cash to buy the stock if assigned.",
    beginnerFriendly: "Yes. Good once you understand how assignment works.",
    beginnerRank: 1,
    scannerLens:
      "Best for finding puts on stocks you want to own, with premium that matches a real target entry price.",
    example: (ticker) =>
      `If ${ticker} feels attractive at a lower price, a Cash-Secured Put lets you get paid while waiting for that entry.`,
  },
  {
    id: "protective-put",
    name: "Protective Put",
    categories: ["own-stock", "protection"],
    purpose: "Put a downside floor under shares you already own.",
    bestWhen:
      "You want to stay long the stock but need short-term downside insurance into volatility or an uncertain event.",
    risk:
      "The hedge costs money, so too much protection can weigh on returns if the stock stays calm or rises.",
    ownership: "Yes. You typically own the shares first.",
    beginnerFriendly: "Yes, if you already understand buying and holding stock.",
    beginnerRank: 1,
    scannerLens:
      "Useful when your next step is not income first, but reducing downside risk on a stock you want to keep.",
    example: (ticker) =>
      `If you own ${ticker} and want insurance into a volatile stretch, a Protective Put can define your floor.`,
  },
  {
    id: "collar",
    name: "Collar",
    categories: ["own-stock", "protection", "neutral", "income"],
    purpose: "Protect owned shares while helping offset hedge cost with call income.",
    bestWhen:
      "You own the stock, want downside protection, and are comfortable capping some of your upside.",
    risk:
      "The short call limits how much of a rally you keep, and the trade still needs careful strike selection.",
    ownership: "Yes. Built around shares you already own.",
    beginnerFriendly: "Yes, with a little structure help.",
    beginnerRank: 2,
    scannerLens:
      "A good fit when protection matters, but you also want a practical way to reduce the cost of that protection.",
    example: (ticker) =>
      `On ${ticker}, a Collar can combine a Covered Call and a Protective Put when you want a steadier risk profile.`,
  },
  {
    id: "bull-put-spread",
    name: "Bull Put Spread",
    categories: ["bullish", "income"],
    purpose: "Collect premium with defined risk when you are moderately bullish.",
    bestWhen:
      "You think the stock stays above support and want less capital at risk than a Cash-Secured Put.",
    risk:
      "Losses are capped, but the trade still loses if the stock breaks down through the spread.",
    ownership: "No stock ownership required.",
    beginnerFriendly: "Yes, after you understand simple vertical spreads.",
    beginnerRank: 2,
    scannerLens:
      "Good for bullish premium trades where you want a clearer max loss instead of full cash-secured assignment risk.",
    example: (ticker) =>
      `If you think ${ticker} holds above support, a Bull Put Spread can express that view with defined risk and income potential.`,
  },
  {
    id: "bear-call-spread",
    name: "Bear Call Spread",
    categories: ["bearish", "income"],
    purpose: "Collect premium with defined risk when you are bearish or expect the stock to stall.",
    bestWhen:
      "You think the stock stays below resistance or drifts sideways after a strong move.",
    risk:
      "Losses are capped but real if the stock pushes higher through the short call strike.",
    ownership: "No stock ownership required.",
    beginnerFriendly: "Moderately. Better after you understand vertical spreads.",
    beginnerRank: 3,
    scannerLens:
      "Useful when you want a bearish or fade-the-rally income setup with defined trade-offs.",
    example: (ticker) =>
      `If ${ticker} looks stretched and likely to stall, a Bear Call Spread turns that bearish view into a capped-risk income trade.`,
  },
  {
    id: "bull-call-spread",
    name: "Bull Call Spread",
    categories: ["bullish"],
    purpose: "Target upside with defined risk and lower cost than a plain long call.",
    bestWhen:
      "You are bullish and expect a meaningful move higher, but want to control the upfront cost.",
    risk:
      "The trade can still expire worthless, and profits are capped once the stock moves through your target zone.",
    ownership: "No stock ownership required.",
    beginnerFriendly: "Moderately. Good once vertical spreads feel familiar.",
    beginnerRank: 2,
    scannerLens:
      "A cleaner directional choice when you want bullish exposure instead of premium selling.",
    example: (ticker) =>
      `If you expect ${ticker} to climb but want defined cost, a Bull Call Spread can give upside without paying for unlimited optionality.`,
  },
  {
    id: "bear-put-spread",
    name: "Bear Put Spread",
    categories: ["bearish"],
    purpose: "Target downside with defined risk and lower cost than a plain long put.",
    bestWhen:
      "You are bearish and expect a move down, not just a slow drift or a stalled rally.",
    risk:
      "The premium paid can be lost if the move does not happen in time, and gains are capped.",
    ownership: "No stock ownership required.",
    beginnerFriendly: "Moderately. Easier after some basic options practice.",
    beginnerRank: 2,
    scannerLens:
      "A scanner-friendly bearish setup when you want direction, timing, and defined risk to stay aligned.",
    example: (ticker) =>
      `If you expect ${ticker} to weaken, a Bear Put Spread gives bearish exposure while keeping the maximum loss defined up front.`,
  },
  {
    id: "iron-condor",
    name: "Iron Condor",
    categories: ["neutral", "income"],
    purpose: "Collect premium when you expect the stock to stay inside a range.",
    bestWhen:
      "Implied volatility is healthy and you do not expect a large move before expiration.",
    risk:
      "Risk is defined on both sides, but a fast move can pressure the position quickly.",
    ownership: "No stock ownership required.",
    beginnerFriendly: "Not first-step beginner. Better after spreads feel comfortable.",
    beginnerRank: 4,
    scannerLens:
      "Best when you want range-bound premium selling and enough liquidity to manage both sides confidently.",
    example: (ticker) =>
      `If you expect ${ticker} to stay in a range, an Iron Condor sells premium on both sides with capped risk.`,
  },
  {
    id: "poor-mans-covered-call",
    name: "Poor Man's Covered Call / Diagonal Call",
    categories: ["bullish", "income"],
    purpose: "Create a covered-call-like income trade without buying 100 shares outright.",
    bestWhen:
      "You are bullish longer term, want lower capital than stock ownership, and understand long-dated calls.",
    risk:
      "The long call behaves differently from stock, so time decay and volatility can make management trickier.",
    ownership: "No shares required, but it uses a longer-dated call instead.",
    beginnerFriendly: "Not first-step beginner. Best once the basics are solid.",
    beginnerRank: 4,
    scannerLens:
      "Helpful when you want stock-like bullish exposure plus short-call income with less upfront capital.",
    example: (ticker) =>
      `If you like ${ticker} long term but do not want to tie up full share capital, a Diagonal Call can mimic part of a covered-call playbook.`,
  },
];

const STRATEGY_MAP: Array<{
  category: CategoryId;
  title: string;
  description: string;
  strategies: string[];
}> = [
  {
    category: "own-stock",
    title: "Own stock",
    description: "Use stock-linked options when you already have shares and want income or downside guardrails.",
    strategies: ["Covered Call", "Protective Put", "Collar"],
  },
  {
    category: "income",
    title: "Income",
    description: "Premium-first ideas for traders who want options to produce cash flow instead of pure direction.",
    strategies: ["Covered Call", "Cash-Secured Put", "Iron Condor"],
  },
  {
    category: "bullish",
    title: "Bullish",
    description: "Choose whether you want assignment-friendly income, defined-risk direction, or lower-capital exposure.",
    strategies: [
      "Cash-Secured Put",
      "Bull Call Spread",
      "Bull Put Spread",
      "Poor Man's Covered Call / Diagonal Call",
    ],
  },
  {
    category: "bearish",
    title: "Bearish",
    description: "Bearish ideas can lean income-oriented or directional depending on how strong your view is.",
    strategies: ["Bear Put Spread", "Bear Call Spread"],
  },
  {
    category: "neutral",
    title: "Neutral",
    description: "If you expect range-bound action, focus on strategies that get paid when nothing dramatic happens.",
    strategies: ["Iron Condor"],
  },
  {
    category: "protection",
    title: "Protection",
    description: "These are about calming downside risk on shares you intend to keep.",
    strategies: ["Protective Put", "Collar"],
  },
];

const PRESET_TICKERS = ["AAPL", "TSLA", "NVDA", "SPY"];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="landing-section-label">{children}</div>;
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      className="mt-0.5 h-5 w-5 text-emerald-300"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 17 17 7M7 7h10v10" />
    </svg>
  );
}

function LanguagePicker({
  language,
  onSelect,
  menuLabel,
  menuPlacement = "bottom",
}: {
  language: LanguageId;
  onSelect: (language: LanguageId) => void;
  menuLabel: string;
  menuPlacement?: "top" | "bottom";
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedLanguage =
    LANGUAGE_OPTIONS.find((option) => option.id === language) ??
    LANGUAGE_OPTIONS[2];
  const menuPosition =
    menuPlacement === "top" ? "bottom-12 right-0" : "right-0 top-12";

  return (
    <div
      className="relative flex shrink-0"
      onBlur={(event) => {
        const nextFocus = event.relatedTarget;
        if (!(nextFocus instanceof Node) || !event.currentTarget.contains(nextFocus)) {
          setIsOpen(false);
        }
      }}
    >
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="inline-flex h-10 items-center gap-2 text-sm font-semibold text-slate-200 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-emerald-300/70"
        aria-label={`${menuLabel}: ${selectedLanguage.name}`}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        title={selectedLanguage.name}
      >
        <span
          aria-hidden="true"
          className="grid h-7 w-7 place-items-center text-base leading-none"
        >
          <span className="leading-none">{selectedLanguage.flag}</span>
        </span>
        <span className="min-w-5 text-center leading-none">
          {selectedLanguage.shortLabel}
        </span>
        <span aria-hidden="true" className="text-xs leading-none text-slate-400">
          {isOpen ? "⌃" : "⌄"}
        </span>
      </button>

      {isOpen ? (
        <div
          role="listbox"
          aria-label={menuLabel}
          className={`absolute ${menuPosition} z-50 w-56 overflow-hidden rounded-2xl border border-white/15 bg-slate-950/95 py-2 shadow-2xl shadow-black/40 backdrop-blur`}
        >
          {LANGUAGE_OPTIONS.map((option) => {
            const isSelected = option.id === language;

            return (
              <button
                key={option.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                aria-label={option.name}
                title={option.name}
                onClick={() => {
                  onSelect(option.id);
                  setIsOpen(false);
                }}
                className={`flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition focus:outline-none focus:ring-2 focus:ring-inset focus:ring-emerald-300/70 ${
                  isSelected
                    ? "bg-white text-slate-950"
                    : "text-slate-200 hover:bg-white/10"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-base leading-none ${
                    isSelected ? "bg-slate-950" : "bg-white"
                  }`}
                >
                  <span className="leading-none">{option.flag}</span>
                </span>
                <span className="min-w-0 flex-1 truncate">{option.menuName}</span>
                {isSelected ? (
                  <span className="text-xs font-semibold uppercase tracking-wide">
                    {option.shortLabel}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function StrategyCard({
  strategy,
  ticker,
}: {
  strategy: Strategy;
  ticker: string;
}) {
  const loginHref = `/login?strategy=${encodeURIComponent(strategy.id)}&ticker=${encodeURIComponent(
    ticker,
  )}`;

  return (
    <article className="landing-panel landing-card-hover rounded-[1.75rem] p-6">
      <div className="flex flex-wrap items-center gap-2">
        {strategy.categories.slice(0, 3).map((category) => (
          <span
            key={`${strategy.id}-${category}`}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300"
          >
            {CATEGORY_META[category].label}
          </span>
        ))}
      </div>

      <div className="mt-5 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-2xl font-semibold text-white">{strategy.name}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">{strategy.purpose}</p>
        </div>
        <div className="rounded-2xl border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.2em] text-amber-100">
          Strategy fit
        </div>
      </div>

      <dl className="mt-6 grid gap-4 text-sm">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            What it&apos;s for
          </dt>
          <dd className="mt-1 text-slate-200">{strategy.purpose}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            When it works best
          </dt>
          <dd className="mt-1 text-slate-200">{strategy.bestWhen}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
            Risk
          </dt>
          <dd className="mt-1 text-slate-200">{strategy.risk}</dd>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              Stock ownership
            </dt>
            <dd className="mt-1 text-slate-200">{strategy.ownership}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              Beginner-friendly
            </dt>
            <dd className="mt-1 text-slate-200">{strategy.beginnerFriendly}</dd>
          </div>
        </div>
      </dl>

      <div className="mt-6 rounded-[1.5rem] border border-white/10 bg-black/15 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
          Example on {ticker}
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-200">{strategy.example(ticker)}</p>
        <p className="mt-3 text-sm leading-6 text-slate-400">{strategy.scannerLens}</p>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href="#options-made-simple"
          className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-slate-100"
        >
          Learn this strategy
          <ArrowIcon />
        </a>
        <Link
          href={loginHref}
          className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
        >
          Scan live setups
          <ArrowIcon />
        </Link>
        <a
          href="#real-stock-examples"
          className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-slate-100"
        >
          See opportunities for this strategy
          <ArrowIcon />
        </a>
      </div>
    </article>
  );
}

export default function LandingPage() {
  const router = useRouter();
  const [supabase] = useState(() => createClient());
  const [checking, setChecking] = useState(true);
  const [ticker, setTicker] = useState("AAPL");
  const [selectedGoal, setSelectedGoal] = useState<GoalId>("income");
  const [selectedCategory, setSelectedCategory] = useState<CategoryId>("income");
  const [experienceLevel, setExperienceLevel] =
    useState<ExperienceId>("beginner");
  const [language, setLanguage] = useState<LanguageId>("en");

  useEffect(() => {
    let isActive = true;

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!isActive) return;

      if (session) {
        router.push("/portfolio");
        return;
      }

      setChecking(false);
    });

    return () => {
      isActive = false;
    };
  }, [router, supabase]);

  useEffect(() => {
    const savedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLanguageId(savedLanguage)) {
      setLanguage(savedLanguage);
    }
  }, []);

  useEffect(() => {
    const selectedLanguage =
      LANGUAGE_OPTIONS.find((option) => option.id === language) ??
      LANGUAGE_OPTIONS[2];
    document.documentElement.lang = selectedLanguage.htmlLang;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  const displayTicker = (ticker.trim() || "AAPL").toUpperCase();
  const goalMeta = HERO_GOALS.find((goal) => goal.id === selectedGoal) ?? HERO_GOALS[0];
  const experienceMeta =
    EXPERIENCE_LEVELS.find((level) => level.id === experienceLevel) ??
    EXPERIENCE_LEVELS[0];
  const navCopy = LANDING_NAV_COPY[language];

  const recommendedStrategies = useMemo(() => {
    const matched = STRATEGIES.filter((strategy) =>
      strategy.categories.includes(selectedGoal),
    );

    return [...matched]
      .sort((left, right) => {
        if (experienceLevel === "beginner") {
          return left.beginnerRank - right.beginnerRank;
        }

        if (experienceLevel === "some") {
          return (
            Math.abs(left.beginnerRank - 2) - Math.abs(right.beginnerRank - 2)
          );
        }

        return right.beginnerRank - left.beginnerRank;
      })
      .slice(0, 3);
  }, [experienceLevel, selectedGoal]);

  const visibleStrategies = useMemo(
    () =>
      STRATEGIES.filter((strategy) =>
        strategy.categories.includes(selectedCategory),
      ),
    [selectedCategory],
  );

  const exampleStrategies = useMemo(() => {
    const chosen: Strategy[] = [];
    const seen = new Set<string>();

    for (const strategy of [...visibleStrategies, ...recommendedStrategies, ...STRATEGIES]) {
      if (seen.has(strategy.id)) continue;
      chosen.push(strategy);
      seen.add(strategy.id);
      if (chosen.length === 3) break;
    }

    return chosen;
  }, [recommendedStrategies, visibleStrategies]);

  function handleGoalChange(goal: GoalId) {
    setSelectedGoal(goal);
    setSelectedCategory(goal);
  }

  if (checking) {
    return (
      <div className="landing-shell flex min-h-screen items-center justify-center text-white">
        <div className="landing-panel rounded-[2rem] px-8 py-6 text-center">
          <p className="text-sm uppercase tracking-[0.22em] text-slate-400">
            Loading strategy guide
          </p>
          <p className="mt-3 text-lg text-slate-100">
            Opening the goal-first experience...
          </p>
        </div>
      </div>
    );
  }

  const primaryRecommendation = recommendedStrategies[0];

  return (
    <div className="landing-shell min-h-screen text-white">
      <div className="landing-orb landing-orb-one" />
      <div className="landing-orb landing-orb-two" />
      <div className="landing-orb landing-orb-three" />

      <header className="fixed inset-x-0 top-0 z-50 px-3 pt-3 sm:px-6">
        <div className="landing-panel mx-auto flex max-w-6xl items-center gap-2 rounded-[1.4rem] px-3 py-2 sm:gap-4 sm:rounded-full sm:px-5 sm:py-3">
          <Link
            href="/"
            className="shrink-0 text-base font-semibold tracking-tight text-white sm:text-lg"
          >
            Option<span className="text-emerald-300">Bot</span>
          </Link>

          <nav
            aria-label="Landing page sections"
            className="landing-nav-scroll flex min-w-0 flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap px-1 text-xs text-slate-300 sm:gap-4 sm:text-sm md:justify-center"
          >
            <a href="#strategy-chooser" className="rounded-full px-2 py-2 hover:text-white sm:px-3">
              {navCopy.strategyChooser}
            </a>
            <a href="#strategy-map" className="rounded-full px-2 py-2 hover:text-white sm:px-3">
              {navCopy.strategyMap}
            </a>
            <a
              href="#real-stock-examples"
              className="rounded-full px-2 py-2 hover:text-white sm:px-3"
            >
              {navCopy.realStockExamples}
            </a>
            <a href="#pricing" className="rounded-full px-2 py-2 hover:text-white sm:px-3">
              {navCopy.pricing}
            </a>
          </nav>

          <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className="hidden text-sm text-slate-300 transition-colors hover:text-white sm:inline"
            >
              {navCopy.signIn}
            </Link>
            <Link
              href="/login"
              className="landing-primary-button hidden items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-slate-950 sm:inline-flex lg:px-4"
            >
              {navCopy.startFree}
              <ArrowIcon />
            </Link>
          </div>
        </div>
      </header>

      <main className="pt-24 sm:pt-28">
        <section className="px-6 pb-14 pt-8 sm:pt-12">
          <div className="mx-auto max-w-6xl">
            <div className="landing-panel overflow-hidden rounded-[2rem]">
              <div className="grid gap-10 px-6 py-8 lg:grid-cols-[1.05fr_0.95fr] lg:px-10 lg:py-12">
                <div>
                  <SectionLabel>Goal-first hero</SectionLabel>
                  <h1 className="mt-4 max-w-3xl text-5xl font-semibold leading-[0.98] tracking-tight text-white md:text-6xl">
                    Start with what you want this stock to do.
                    <span className="landing-display block text-amber-100">
                      Find the strategy after that.
                    </span>
                  </h1>
                  <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
                    OptionBot is not a generic options encyclopedia and not only a
                    Wheel strategy pitch. It is a guided strategy discovery and
                    scanning product that helps you move from a stock, a goal, and
                    a comfort level into plain-English strategy choices and live
                    setups.
                  </p>

                  <div className="mt-8 flex flex-wrap gap-3">
                    {[
                      "Earn income",
                      "Protect shares",
                      "Bullish",
                      "Bearish",
                      "Neutral",
                    ].map((item) => (
                      <span
                        key={item}
                        className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200"
                      >
                        {item}
                      </span>
                    ))}
                  </div>

                  <div className="mt-10 grid gap-4 md:grid-cols-3">
                    <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-semibold text-white">
                        Goal-first discovery
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        Begin with a stock, a goal, and your experience level rather
                        than jumping straight into jargon.
                      </p>
                    </div>
                    <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-semibold text-white">
                        Plain-English strategy cards
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        See what a strategy is for, when it works best, how risky it
                        is, and whether stock ownership is required.
                      </p>
                    </div>
                    <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-semibold text-white">
                        Education into live scans
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-300">
                        Learn the setup first, then move straight into the scanner
                        when you are ready to see live opportunities.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="landing-panel rounded-[1.75rem] border border-white/12 p-6 lg:p-7">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-200">
                        Guided input flow
                      </p>
                      <h2 className="mt-3 text-2xl font-semibold text-white">
                        Tell us the stock, the goal, and your experience.
                      </h2>
                    </div>
                    <div className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100">
                      No jargon first
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4">
                    <label className="block">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                        Stock ticker
                      </span>
                      <input
                        type="text"
                        value={ticker}
                        onChange={(event) =>
                          setTicker(event.target.value.replace(/[^a-zA-Z]/g, "").slice(0, 5))
                        }
                        placeholder="AAPL"
                        className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-base text-white outline-none transition focus:border-emerald-300/50"
                      />
                    </label>

                    <label className="block">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                        Goal
                      </span>
                      <select
                        value={selectedGoal}
                        onChange={(event) =>
                          handleGoalChange(event.target.value as GoalId)
                        }
                        className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-base text-white outline-none transition focus:border-emerald-300/50"
                      >
                        {HERO_GOALS.map((goal) => (
                          <option key={goal.id} value={goal.id}>
                            {goal.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                        Experience level
                      </span>
                      <select
                        value={experienceLevel}
                        onChange={(event) =>
                          setExperienceLevel(event.target.value as ExperienceId)
                        }
                        className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-base text-white outline-none transition focus:border-emerald-300/50"
                      >
                        {EXPERIENCE_LEVELS.map((level) => (
                          <option key={level.id} value={level.id}>
                            {level.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-emerald-300/15 bg-emerald-300/10 p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-100">
                      Recommended starting point for {displayTicker}
                    </p>
                    <h3 className="mt-3 text-2xl font-semibold text-white">
                      {primaryRecommendation?.name ?? "Strategy finder loading"}
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-emerald-50/90">
                      {goalMeta.summary} {goalMeta.coaching}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-emerald-50/90">
                      Because you selected <strong>{goalMeta.label}</strong> and{" "}
                      <strong>{experienceMeta.label}</strong>, we would start by
                      showing you these matches:
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {recommendedStrategies.map((strategy) => (
                        <span
                          key={strategy.id}
                          className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-sm text-white"
                        >
                          {strategy.name}
                        </span>
                      ))}
                    </div>
                    <div className="mt-5 flex flex-wrap gap-3">
                      <a
                        href="#strategy-chooser"
                        className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white"
                      >
                        View matching strategies
                        <ArrowIcon />
                      </a>
                      <Link
                        href={`/login?ticker=${encodeURIComponent(displayTicker)}`}
                        className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
                      >
                        Scan live setups
                        <ArrowIcon />
                      </Link>
                    </div>
                  </div>

                  <p className="mt-4 text-sm leading-6 text-slate-400">
                    {experienceMeta.summary} Try a real ticker like AAPL or TSLA to
                    make the examples concrete.
                  </p>
                </div>
              </div>

              <div className="landing-stat-line grid gap-4 px-6 py-6 md:grid-cols-3 lg:px-10">
                <div>
                  <p className="text-sm font-semibold text-white">
                    Start from your goal
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Income, protection, bullish, bearish, or neutral. The page
                    narrows the choices before it asks you to think about strategy
                    names.
                  </p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">
                    Learn only the strategies that fit
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Instead of dumping every option structure at once, we reveal the
                    relevant set and explain each one in plain English.
                  </p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">
                    Move into the scanner when ready
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Every strategy block keeps a path open to live setups and real
                    opportunities without making pricing the hero.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="options-made-simple" className="px-6 py-14">
          <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <SectionLabel>Beginner-friendly by design</SectionLabel>
              <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl">
                Options are easier than they look when the starting point is the outcome.
              </h2>
              <p className="mt-5 max-w-xl text-lg leading-8 text-slate-300">
                You do not need to memorize delta, theta, or multi-leg jargon before
                you begin. Start with what you want from the stock, and OptionBot
                helps narrow the strategy, explain the trade-off, and show where the
                live scanner fits.
              </p>
              <div className="mt-8 space-y-4">
                {[
                  "You can start from a goal even if you have never placed an options trade before.",
                  "Plain-English strategy cards replace abstract theory with direct answers.",
                  "The scanner becomes useful faster because the strategy fit is already narrowed.",
                ].map((line) => (
                  <div
                    key={line}
                    className="flex items-start gap-3 rounded-[1.25rem] border border-white/10 bg-white/5 px-4 py-4"
                  >
                    <CheckIcon />
                    <p className="text-sm leading-6 text-slate-200">{line}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {[
                {
                  step: "01",
                  title: "Pick the goal",
                  body: "Earn income, protect shares, lean bullish, position bearish, or stay neutral.",
                },
                {
                  step: "02",
                  title: "See the matching strategies",
                  body: "The chooser reveals only the setups that fit that goal instead of showing everything at once.",
                },
                {
                  step: "03",
                  title: "Scan live opportunities",
                  body: "Once the strategy makes sense, jump straight into live scanner setups for the stock you care about.",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="landing-panel landing-card-hover rounded-[1.5rem] p-5"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.22em] text-emerald-200">
                    {item.step}
                  </p>
                  <h3 className="mt-3 text-xl font-semibold text-white">{item.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-300">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="strategy-chooser" className="px-6 py-14">
          <div className="mx-auto max-w-6xl">
            <SectionLabel>Strategy chooser</SectionLabel>
            <div className="mt-4 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
                  Choose a category and only see the strategies that fit.
                </h2>
                <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-300">
                  This is the heart of the upgraded landing page. Pick whether you
                  own stock, want income, lean bullish, lean bearish, want neutral
                  range setups, or need protection. We filter the strategy set for
                  you and explain each one in plain English.
                </p>
              </div>
              <div className="rounded-[1.25rem] border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                Showing {visibleStrategies.length} strategy
                {visibleStrategies.length === 1 ? "" : "ies"} for{" "}
                <span className="font-semibold text-white">
                  {CATEGORY_META[selectedCategory].label}
                </span>
              </div>
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              {CATEGORY_ORDER.map((category) => {
                const isActive = category === selectedCategory;

                return (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setSelectedCategory(category)}
                    className={`landing-chip rounded-full px-4 py-2 text-sm font-medium ${
                      isActive
                        ? "landing-chip-active text-white"
                        : "text-slate-300"
                    }`}
                  >
                    {CATEGORY_META[category].label}
                  </button>
                );
              })}
            </div>

            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
              {CATEGORY_META[selectedCategory].blurb}
            </p>

            <div className="mt-8 grid gap-6 xl:grid-cols-2">
              {visibleStrategies.map((strategy) => (
                <StrategyCard
                  key={strategy.id}
                  strategy={strategy}
                  ticker={displayTicker}
                />
              ))}
            </div>
          </div>
        </section>

        <section id="strategy-map" className="px-6 py-14">
          <div className="mx-auto max-w-6xl">
            <SectionLabel>Strategy map</SectionLabel>
            <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl">
              Broader than the Wheel, but still practical.
            </h2>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-300">
              The point is not to dump every strategy ever invented onto the page.
              It is to map real goals to a focused strategy set so users can move
              from confusion to clarity faster.
            </p>

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {STRATEGY_MAP.map((entry) => (
                <article
                  key={entry.category}
                  className="landing-panel landing-card-hover rounded-[1.5rem] p-5"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
                    {entry.title}
                  </p>
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    {entry.description}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {entry.strategies.map((strategyName) => (
                      <span
                        key={`${entry.category}-${strategyName}`}
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-200"
                      >
                        {strategyName}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="real-stock-examples" className="px-6 py-14">
          <div className="mx-auto max-w-6xl">
            <SectionLabel>Real stock examples</SectionLabel>
            <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
                  Make the learning concrete with a real ticker.
                </h2>
                <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-300">
                  Abstract option talk gets overwhelming fast. Enter a stock you
                  already watch, then see how matching strategies apply to that
                  specific name instead of to a vague example.
                </p>
              </div>

              <div className="landing-panel rounded-[1.5rem] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Try a familiar ticker
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {PRESET_TICKERS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setTicker(preset)}
                      className={`landing-chip rounded-full px-4 py-2 text-sm ${
                        displayTicker === preset
                          ? "landing-chip-active text-white"
                          : "text-slate-300"
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
              <div className="landing-panel rounded-[1.75rem] p-6">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
                  Current example path
                </p>
                <h3 className="mt-3 text-3xl font-semibold text-white">
                  {displayTicker} for a {CATEGORY_META[selectedCategory].label.toLowerCase()} goal
                </h3>
                <p className="mt-4 text-sm leading-7 text-slate-300">
                  Use the strategy chooser above to change the category. Then use
                  this section to picture how those strategies might be explained
                  on a real stock instead of as an abstract textbook example.
                </p>

                <div className="mt-6 space-y-4">
                  {[
                    `Start with the stock you actually care about: ${displayTicker}.`,
                    `Pick the goal that best matches the situation: ${CATEGORY_META[selectedCategory].label}.`,
                    "Use the strategy cards to decide which trade structure deserves a live scan next.",
                  ].map((line) => (
                    <div key={line} className="flex items-start gap-3">
                      <CheckIcon />
                      <p className="text-sm leading-6 text-slate-200">{line}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-8 flex flex-wrap gap-3">
                  <Link
                    href={`/login?ticker=${encodeURIComponent(displayTicker)}`}
                    className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
                  >
                    See opportunities for {displayTicker}
                    <ArrowIcon />
                  </Link>
                  <a
                    href="#strategy-chooser"
                    className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white"
                  >
                    Refine the strategy fit
                    <ArrowIcon />
                  </a>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {exampleStrategies.map((strategy) => (
                  <article
                    key={`example-${strategy.id}`}
                    className="landing-panel landing-card-hover rounded-[1.5rem] p-5"
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {strategy.name}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-slate-200">
                      {strategy.example(displayTicker)}
                    </p>
                    <p className="mt-4 text-sm leading-6 text-slate-400">
                      Best when: {strategy.bestWhen}
                    </p>
                    <div className="mt-5 flex flex-wrap gap-3">
                      <Link
                        href={`/login?strategy=${encodeURIComponent(strategy.id)}&ticker=${encodeURIComponent(
                          displayTicker,
                        )}`}
                        className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
                      >
                        Scan live setups
                        <ArrowIcon />
                      </Link>
                      <a
                        href="#options-made-simple"
                        className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white"
                      >
                        Learn this strategy
                        <ArrowIcon />
                      </a>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="px-6 py-14">
          <div className="mx-auto max-w-6xl">
            <div className="landing-panel rounded-[2rem] p-6 md:p-8">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <SectionLabel>Education into scanner</SectionLabel>
                  <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white md:text-5xl">
                    The page teaches just enough, then gets out of the way.
                  </h2>
                  <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-300">
                    Every major strategy block points back to the same product
                    promise: understand the trade, scan live setups, and only then
                    decide whether it belongs in your workflow.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <a
                    href="#strategy-chooser"
                    className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white"
                  >
                    Learn this strategy
                    <ArrowIcon />
                  </a>
                  <Link
                    href={`/login?ticker=${encodeURIComponent(displayTicker)}`}
                    className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
                  >
                    Scan live setups
                    <ArrowIcon />
                  </Link>
                  <a
                    href="#real-stock-examples"
                    className="landing-outline-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-white"
                  >
                    See opportunities for this strategy
                    <ArrowIcon />
                  </a>
                </div>
              </div>

              <div className="mt-8 grid gap-4 md:grid-cols-3">
                {[
                  {
                    title: "1. Learn what the strategy is for",
                    body: "Every card starts with the outcome, not the jargon, so the user understands the point before the mechanics.",
                  },
                  {
                    title: "2. Match it to a real stock",
                    body: `Use ${displayTicker} or another familiar ticker to make the strategy feel concrete instead of abstract.`,
                  },
                  {
                    title: "3. See live setups when ready",
                    body: "Once the fit is clear, the next step is scanning live opportunities rather than reading another wall of theory.",
                  },
                ].map((item) => (
                  <div
                    key={item.title}
                    className="rounded-[1.5rem] border border-white/10 bg-white/5 p-5"
                  >
                    <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{item.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="px-6 py-14">
          <div className="mx-auto max-w-6xl">
            <SectionLabel>Cleaner persuasion</SectionLabel>
            <div className="mt-4 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
              <div>
                <h2 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
                  Pricing stays on the page, but it does not dominate the story.
                </h2>
                <p className="mt-4 text-lg leading-8 text-slate-300">
                  Strategy education and guided discovery should do the selling
                  first. Pricing sits lower on the page as the next practical step,
                  not as the entire pitch.
                </p>
                <p className="mt-4 text-sm leading-6 text-slate-400">
                  The repository docs still describe billing as partial, so this
                  section stays honest: start free now, then expect deeper paid
                  access to expand as billing rollout finishes.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <article className="landing-panel rounded-[1.75rem] p-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
                    Start free
                  </p>
                  <h3 className="mt-3 text-2xl font-semibold text-white">
                    Learn the fit before you pay for complexity.
                  </h3>
                  <div className="mt-5 space-y-3">
                    {[
                      "Goal-first strategy discovery",
                      "Beginner-friendly strategy explanations",
                      "A guided path from learning to scanner usage",
                    ].map((line) => (
                      <div key={line} className="flex items-start gap-3">
                        <CheckIcon />
                        <p className="text-sm leading-6 text-slate-200">{line}</p>
                      </div>
                    ))}
                  </div>
                  <Link
                    href="/login"
                    className="landing-primary-button mt-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
                  >
                    Create a free account
                    <ArrowIcon />
                  </Link>
                </article>

                <article className="landing-panel rounded-[1.75rem] p-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-200">
                    Paid access rolling out
                  </p>
                  <h3 className="mt-3 text-2xl font-semibold text-white">
                    More scans, deeper filters, and richer workflow layers.
                  </h3>
                  <div className="mt-5 space-y-3">
                    {[
                      "Expanded scan access and parameter control",
                      "Deeper portfolio and live opportunity workflows",
                      "Premium alerts and advanced strategy coverage as billing goes live",
                    ].map((line) => (
                      <div key={line} className="flex items-start gap-3">
                        <CheckIcon />
                        <p className="text-sm leading-6 text-slate-200">{line}</p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-6 text-sm leading-6 text-slate-400">
                    Early access is the current emphasis. The strategy journey comes
                    first; the billing layer follows cleanly behind it.
                  </p>
                </article>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="px-6 pb-0 pt-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 border-t border-white/10 pb-8 pt-8 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-slate-400">
              OptionBot is positioned here as a guided strategy discovery and
              scanning product, not a generic encyclopedia and not only a Wheel
              strategy pitch.
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Options involve risk. Educational content is not a guarantee of
              results or individualized trade advice.
            </p>
          </div>
          <Link
            href="/login"
            className="landing-primary-button inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-slate-950"
          >
            Start with a stock and a goal
            <ArrowIcon />
          </Link>
        </div>

        <div className="relative z-10 -mx-6 border-t border-white/10 bg-white/[0.03] px-6 py-3">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 text-xs text-slate-400 lg:flex-row lg:items-center lg:justify-between">
            <p>
              © 2026 | OptionBot | All Rights Reserved.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:justify-end">
              <nav
                aria-label="Legal links"
                className="flex flex-wrap items-center gap-x-4 gap-y-2 font-semibold text-slate-300"
              >
                {LEGAL_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="transition-colors hover:text-white"
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>

              <div className="hidden h-7 w-px bg-white/15 sm:block" />

              <LanguagePicker
                language={language}
                onSelect={setLanguage}
                menuLabel={navCopy.languageMenu}
                menuPlacement="top"
              />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
