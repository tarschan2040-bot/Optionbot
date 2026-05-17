export type TutorialSection = {
  heading: string;
  body: string;
  bullets?: string[];
  table?: Array<{ label: string; value: string }>;
};

export type TutorialPage = {
  slug: string;
  order: number;
  title: string;
  eyebrow: string;
  summary: string;
  readTime: string;
  sections: TutorialSection[];
  takeaways: string[];
};

export const tutorialPages: TutorialPage[] = [
  {
    slug: "getting-started",
    order: 1,
    title: "Getting Started",
    eyebrow: "First pass",
    summary:
      "Understand the basic OptionBot workflow before reading individual strategy guides.",
    readTime: "5 min",
    sections: [
      {
        heading: "What OptionBot Reviews",
        body:
          "OptionBot starts with the stocks and scan settings you choose. It checks available option contracts, applies your filters, scores the results, and presents the contracts that best match the profile you selected.",
        bullets: [
          "The scanner does not place trades for you.",
          "A scan result is an idea for review, not an instruction to trade.",
          "Starred results become candidates you can revisit later.",
          "Portfolio positions help you track open, closed, expired, and manually managed trades.",
        ],
      },
      {
        heading: "The Main Workflow",
        body:
          "A practical workflow is scan, review, shortlist, decide, then track. The goal is to reduce the time spent searching through option chains while keeping the final trade decision in your hands.",
        table: [
          { label: "Scan", value: "Use your watchlist and filters to find contracts." },
          { label: "Review", value: "Check the score, strike, DTE, premium, Greeks, and chart context." },
          { label: "Star", value: "Save interesting contracts to your candidate list." },
          { label: "Act", value: "Enter, skip, close, roll, or delete based on your own decision." },
        ],
      },
      {
        heading: "How To Read A Result",
        body:
          "The most important fields are strategy, ticker, contract, DTE, premium, delta, implied volatility, annualized return, and score. Together they show how much premium is available, how close the strike is, how much time remains, and how strongly the contract matches your settings.",
      },
    ],
    takeaways: [
      "OptionBot narrows the option chain; it does not replace trade judgment.",
      "The best use is repeatable review: scan, compare, shortlist, then decide.",
      "A high score still needs risk review before action.",
    ],
  },
  {
    slug: "risk-workflow",
    order: 2,
    title: "Risk & Workflow",
    eyebrow: "Read before trading",
    summary:
      "Set expectations around risk, assignment, position review, and why OptionBot supports decisions rather than making them.",
    readTime: "6 min",
    sections: [
      {
        heading: "Option Selling Has Real Risk",
        body:
          "Covered calls and cash-secured puts can look calm because they collect premium, but the underlying stock can still move sharply. Premium can reduce cost or add income, but it does not remove market risk.",
        bullets: [
          "A covered call can cap your upside if the stock rallies above the strike.",
          "A cash-secured put can require you to buy shares if the stock falls below the strike.",
          "An option can move against you before expiration even if the final outcome is acceptable.",
          "Liquidity matters because wide bid/ask spreads can make entry and exit prices worse.",
        ],
      },
      {
        heading: "Review Before Action",
        body:
          "Before entering a trade, review the stock chart, upcoming earnings, contract liquidity, strike distance, account concentration, and your exit plan. OptionBot can show useful fields, but it cannot know your full account context.",
      },
      {
        heading: "Open Position Workflow",
        body:
          "After a trade is added to Portfolio, track it as an open position. If it expires, OptionBot highlights the DTE as Expired and leaves it in Open Positions so you can decide whether it expired worthless, was assigned, was closed earlier, or needs a roll.",
        table: [
          { label: "Expired worthless", value: "Close the trade manually with an exit price of 0." },
          { label: "Assigned", value: "Record the outcome based on your broker confirmation." },
          { label: "Closed early", value: "Enter the actual exit price so realized P&L is accurate." },
          { label: "Rolled", value: "Record the buyback price and the replacement contract." },
        ],
      },
      {
        heading: "Important Boundary",
        body:
          "OptionBot is designed to support your review process. It does not place trades, guarantee outcomes, or provide financial advice.",
      },
    ],
    takeaways: [
      "Premium is not protection from every loss.",
      "Expired positions should be reviewed instead of auto-closed blindly.",
      "The final decision stays with the user.",
    ],
  },
  {
    slug: "how-optionbot-helps",
    order: 3,
    title: "How OptionBot Helps Option Trading",
    eyebrow: "Decision support",
    summary:
      "See how scanning, scoring, candidate tracking, and portfolio review fit together.",
    readTime: "5 min",
    sections: [
      {
        heading: "It Reduces Search Time",
        body:
          "A raw option chain can contain many expirations, strikes, and prices. OptionBot turns that large list into a filtered set of contracts that match your chosen strategy and risk profile.",
      },
      {
        heading: "It Makes Results Easier To Compare",
        body:
          "The score combines several factors into one ranking so similar contracts can be compared quickly. You can still inspect the underlying fields when a score looks attractive or surprising.",
        bullets: [
          "Delta helps estimate strike distance and assignment likelihood.",
          "DTE shows how much time remains before expiration.",
          "Premium shows the credit available per share.",
          "Annualized return compares premium across different expirations.",
          "Liquidity filters help avoid contracts that are hard to trade cleanly.",
        ],
      },
      {
        heading: "It Supports A Repeatable Process",
        body:
          "The system is most useful when used the same way each time: keep a watchlist, scan with consistent settings, star contracts for review, and track what happened after entry. Over time, that creates a cleaner record than scattered notes or screenshots.",
      },
    ],
    takeaways: [
      "OptionBot helps with filtering, ranking, and tracking.",
      "The score is a review aid, not a trading signal by itself.",
      "A consistent workflow matters more than one perfect scan.",
    ],
  },
  {
    slug: "covered-calls",
    order: 4,
    title: "Covered Calls",
    eyebrow: "Income against shares",
    summary:
      "Learn how covered calls work and why the main parameters matter for stock owners.",
    readTime: "7 min",
    sections: [
      {
        heading: "What A Covered Call Is",
        body:
          "A covered call means you own shares and sell a call option against those shares. You collect premium upfront. If the stock finishes above the strike at expiration, your shares may be called away at the strike price.",
      },
      {
        heading: "When It Can Fit",
        body:
          "Covered calls are usually considered when you already own a stock, are comfortable selling it at a higher price, and want to collect premium while waiting.",
        bullets: [
          "Best fit: you are neutral to moderately bullish.",
          "Main trade-off: premium income in exchange for capped upside.",
          "Main stock risk: the stock can still fall below your cost basis.",
        ],
      },
      {
        heading: "Why Parameters Matter",
        body:
          "Covered call filters help balance premium, assignment risk, and time in the trade.",
        table: [
          { label: "DTE", value: "Controls how long your shares are committed to the contract." },
          { label: "Delta", value: "Higher call delta usually means more premium and higher assignment chance." },
          { label: "Premium", value: "Sets the minimum credit you are willing to consider." },
          { label: "Implied volatility", value: "Higher IV can mean richer premium and larger expected price movement." },
          { label: "Annualized return", value: "Helps compare short and longer expirations on a similar scale." },
        ],
      },
    ],
    takeaways: [
      "Covered calls work best when the strike is a price you are willing to sell at.",
      "Higher premium usually comes with a meaningful trade-off.",
      "Delta and DTE are two of the most important controls.",
    ],
  },
  {
    slug: "cash-secured-puts",
    order: 5,
    title: "Cash-Secured Puts",
    eyebrow: "Income with reserved cash",
    summary:
      "Learn how CSPs work and how filters help control assignment and stock-entry risk.",
    readTime: "7 min",
    sections: [
      {
        heading: "What A Cash-Secured Put Is",
        body:
          "A cash-secured put means you sell a put option and reserve enough cash to buy the shares if assigned. You collect premium upfront. If the stock finishes below the strike at expiration, you may be required to buy shares at the strike price.",
      },
      {
        heading: "When It Can Fit",
        body:
          "A CSP can fit when you are willing to own a stock at a lower effective price and want to be paid while waiting. It is not risk-free because the stock can fall far below the strike.",
      },
      {
        heading: "Why Parameters Matter",
        body:
          "CSP filters help balance income, strike distance, and the chance of assignment.",
        table: [
          { label: "DTE", value: "Controls how long cash is reserved for the trade." },
          { label: "Delta", value: "More negative put delta is usually closer to the stock price and pays more premium." },
          { label: "Premium", value: "Sets the minimum credit required before a put is considered." },
          { label: "Strike", value: "Determines the price where you may be required to buy shares." },
          { label: "Annualized return", value: "Helps compare premium to the cash reserved and time remaining." },
        ],
      },
      {
        heading: "Assignment Thinking",
        body:
          "Before selling a put, ask whether you would still want the stock if it dropped. A good-looking premium can become uncomfortable if the strike is too close or the position is too large for the account.",
      },
    ],
    takeaways: [
      "Only sell CSPs on stocks you are willing to own.",
      "Delta helps estimate how close the put is to the current stock price.",
      "Cash usage and position size matter as much as premium.",
    ],
  },
  {
    slug: "mean-reversion-filter",
    order: 6,
    title: "Mean Reversion Filter",
    eyebrow: "Timing context",
    summary:
      "Understand how the MR filter checks whether a stock looks stretched and whether that stretch is cooling.",
    readTime: "6 min",
    sections: [
      {
        heading: "Mean Reversion In Plain English",
        body:
          "Mean reversion is the idea that a stock that has moved unusually far in one direction may later cool down or move back toward a more normal range. It is not guaranteed, but it can add useful context for option selling.",
      },
      {
        heading: "How OptionBot Uses It",
        body:
          "OptionBot uses price-timing signals such as RSI, Z-score, and recent rate-of-change behavior to judge whether a move looks stretched. Covered calls can receive more credit after stretched rallies. Cash-secured puts can receive more credit after stretched selloffs.",
      },
      {
        heading: "Timing Confirmation",
        body:
          "A stock can stay stretched longer than expected. Timing confirmation waits for evidence that the move is starting to cool before giving full mean-reversion credit. This helps avoid selling options too early while momentum is still accelerating.",
      },
      {
        heading: "How To Use It",
        body:
          "Treat the MR score as context, not a trigger. A strong MR setup can make a result more interesting, but the final review should still include liquidity, earnings, trend, support/resistance, and account risk.",
      },
    ],
    takeaways: [
      "MR helps identify stretched price conditions.",
      "Timing confirmation is meant to reduce early entries into strong momentum.",
      "MR should support, not replace, the rest of the trade review.",
    ],
  },
  {
    slug: "greeks",
    order: 7,
    title: "Greeks Guide",
    eyebrow: "Option behavior",
    summary:
      "Learn the main Greeks, what they mean, and how they relate to stock price, option price, time, and volatility.",
    readTime: "8 min",
    sections: [
      {
        heading: "Delta",
        body:
          "Delta estimates how much the option price may change when the stock moves by 1 dollar. Calls usually have positive delta. Puts usually have negative delta. For option sellers, delta also gives a rough sense of how close the strike is to the current stock price.",
      },
      {
        heading: "Theta",
        body:
          "Theta estimates how much option value changes as time passes. Option sellers usually want time decay working in their favor, but theta is only one part of the trade. A large stock move can overwhelm daily time decay.",
      },
      {
        heading: "Gamma",
        body:
          "Gamma shows how quickly delta can change when the stock moves. Higher gamma means the position can become more sensitive quickly, especially near expiration and near the strike.",
      },
      {
        heading: "Vega",
        body:
          "Vega estimates how much the option price may change when implied volatility changes. When IV rises, option prices often rise. When IV falls, option prices often fall. Option sellers should pay attention to IV because rich premium can also mean higher expected movement.",
      },
      {
        heading: "Rho",
        body:
          "Rho estimates sensitivity to interest rates. It is usually less important for short-dated covered calls and cash-secured puts than delta, theta, gamma, and vega, but it can matter more for long-dated options.",
      },
      {
        heading: "How They Relate",
        body:
          "The Greeks work together. Delta changes as the stock moves. Gamma controls how fast delta changes. Theta changes as expiration approaches. Vega changes as volatility expectations rise or fall. A good option review looks at the full picture instead of one Greek alone.",
      },
    ],
    takeaways: [
      "Delta, theta, gamma, and vega are the most useful Greeks for many CC/CSP reviews.",
      "Higher theta is not automatically better if delta or gamma risk is too high.",
      "Greeks are estimates, not promises.",
    ],
  },
  {
    slug: "parameters",
    order: 8,
    title: "Parameter Guide",
    eyebrow: "Scanner controls",
    summary:
      "Understand the main scan parameters and how conservative or aggressive changes affect results.",
    readTime: "8 min",
    sections: [
      {
        heading: "DTE Range",
        body:
          "DTE means days to expiration. Shorter DTE can provide faster time decay but more concentrated gamma risk. Longer DTE can provide more premium but keeps capital committed for more time.",
      },
      {
        heading: "Delta Range",
        body:
          "Delta helps control strike distance. For covered calls, a higher call delta usually means more premium and more assignment risk. For cash-secured puts, a more negative put delta usually means more premium and more chance of assignment.",
      },
      {
        heading: "Minimum Premium",
        body:
          "Minimum premium avoids contracts where the credit is too small to justify the trade. Remember that one standard option contract usually controls 100 shares, so a 2.00 premium is about 200 dollars before commissions and slippage.",
      },
      {
        heading: "Implied Volatility",
        body:
          "Implied volatility reflects expected future movement. Higher IV can create richer premium, but it also usually means the market expects larger moves. This is why IV should be considered with delta, chart context, and earnings risk.",
      },
      {
        heading: "Annualized Return",
        body:
          "Annualized return helps compare contracts with different expirations. It can be useful, but very high annualized returns can also indicate higher risk, closer strikes, or unusual volatility.",
      },
      {
        heading: "Scoring Weights",
        body:
          "Scoring weights tell OptionBot which qualities should matter more in the final ranking. A conservative setup may reward distance and liquidity more. An income-focused setup may reward premium and annualized return more.",
      },
    ],
    takeaways: [
      "Parameters are trade-offs, not isolated switches.",
      "Conservative settings usually reduce result count but improve comfort.",
      "Aggressive settings may find richer premium with higher risk.",
    ],
  },
];

export const orderedTutorialPages = [...tutorialPages].sort((a, b) => a.order - b.order);
