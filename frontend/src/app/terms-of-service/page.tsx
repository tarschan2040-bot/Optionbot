import Link from "next/link";

const sections = [
  {
    title: "1. Acceptance of these Terms",
    body: [
      "By creating an account, signing in, or using OptionBot, you agree to these Terms of Service. If you do not agree, do not use the platform.",
      "If you use OptionBot for a business or another person, you confirm that you have authority to accept these Terms for that person or business.",
    ],
  },
  {
    title: "2. What OptionBot provides",
    body: [
      "OptionBot provides options education, scanning tools, strategy explanations, portfolio workflow tools, alerts, and related market information.",
      "The platform is designed to help users review possible option setups. It does not place trades for you, manage your brokerage account, or guarantee that any setup is suitable for you.",
    ],
  },
  {
    title: "3. No financial, investment, tax, or legal advice",
    body: [
      "OptionBot is an educational and research tool. It is not a broker-dealer, investment adviser, tax adviser, legal adviser, or fiduciary.",
      "Information shown by OptionBot is not personalized financial advice. You are responsible for deciding whether any trade, strategy, or risk level is suitable for your objectives, experience, account size, and financial situation.",
      "You should consult a qualified professional before making financial, tax, or legal decisions.",
    ],
  },
  {
    title: "4. Options trading risk",
    body: [
      "Options involve significant risk and are not suitable for all investors. You can lose money, including more than the premium received or paid depending on the strategy used.",
      "Covered calls, cash-secured puts, spreads, rolls, and other strategies each have different risks. Market prices, volatility, liquidity, assignment risk, early exercise risk, and data delays can affect actual results.",
      "Past examples, backtests, screenshots, scores, or displayed opportunities do not guarantee future performance.",
    ],
  },
  {
    title: "5. User accounts and security",
    body: [
      "You must provide accurate account information and keep your login credentials secure.",
      "You are responsible for activity under your account. Tell us promptly if you believe your account has been accessed without permission.",
      "We may refuse, suspend, or terminate accounts that provide false information, misuse the platform, or create risk for OptionBot or other users.",
    ],
  },
  {
    title: "6. Market data and third-party services",
    body: [
      "OptionBot may use market data, analytics, authentication, payment, email, hosting, and infrastructure services from third parties.",
      "Market data may be delayed, incomplete, unavailable, or inaccurate. You should verify prices, option chains, and order details directly with your broker before trading.",
      "Third-party services may have their own terms and privacy practices. OptionBot is not responsible for third-party outages, errors, or actions outside our reasonable control.",
    ],
  },
  {
    title: "7. Subscriptions, billing, and free access",
    body: [
      "Some features may be free and some may require a paid subscription. Plan benefits, prices, limits, and trial availability may change over time.",
      "When paid billing is enabled, payments will be processed through the payment provider shown at checkout. By starting a paid plan, you authorize recurring billing according to the plan selected.",
      "Unless a checkout page or written policy says otherwise, fees are non-refundable except where required by law.",
    ],
  },
  {
    title: "8. Acceptable use",
    body: [
      "You may not misuse OptionBot, interfere with the platform, scrape or resell data without permission, attempt unauthorized access, reverse engineer protected parts of the service, or use the platform for unlawful activity.",
      "You may not present OptionBot output as guaranteed trading advice or use it to mislead another person about risk or expected returns.",
    ],
  },
  {
    title: "9. Intellectual property",
    body: [
      "OptionBot, including its software, design, content, strategy explanations, scoring logic, and branding, belongs to OptionBot or its licensors.",
      "You may use the platform for your personal or internal business use, but you may not copy, sell, distribute, or create competing services from OptionBot materials without written permission.",
    ],
  },
  {
    title: "10. Disclaimers and limitation of liability",
    body: [
      "OptionBot is provided on an as-is and as-available basis. We do not promise uninterrupted service, error-free data, profitable trades, or that any scan result will meet your needs.",
      "To the maximum extent allowed by law, OptionBot will not be liable for trading losses, lost profits, lost data, indirect damages, special damages, consequential damages, or losses caused by reliance on platform output.",
    ],
  },
  {
    title: "11. Changes to these Terms",
    body: [
      "We may update these Terms as the platform, law, or business changes. If changes are material, we will take reasonable steps to notify users.",
      "Continuing to use OptionBot after updated Terms are posted means you accept the updated Terms.",
    ],
  },
  {
    title: "12. Contact",
    body: [
      "Questions about these Terms can be sent through the Contact Us form on the OptionBot website.",
      "Before public launch, company legal name, registered address, governing law, and required consumer notices should be completed by counsel.",
    ],
  },
];

export default function TermsOfServicePage() {
  return (
    <main className="min-h-screen bg-gray-950 px-6 py-10 text-white">
      <div className="mx-auto max-w-4xl">
        <Link href="/" className="text-sm font-medium text-emerald-300 hover:text-emerald-200">
          Back to OptionBot
        </Link>
        <div className="mt-6 rounded-2xl border border-gray-800 bg-gray-900 p-6 shadow-xl sm:p-10">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-emerald-300">
            OptionBot Legal
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Terms of Service</h1>
          <p className="mt-3 text-sm text-gray-400">Last updated: May 17, 2026</p>
          <p className="mt-6 text-base leading-7 text-gray-300">
            These Terms are a practical launch draft for an options education and
            scanning platform. They should be reviewed by a qualified lawyer before
            public launch or before charging users.
          </p>

          <div className="mt-8 space-y-8">
            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-xl font-semibold text-white">{section.title}</h2>
                <div className="mt-3 space-y-3">
                  {section.body.map((paragraph) => (
                    <p key={paragraph} className="text-sm leading-7 text-gray-300">
                      {paragraph}
                    </p>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
