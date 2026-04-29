"""
core/greeks.py — Black-Scholes Greeks Calculator
==================================================
Pure Python implementation (no external options library needed).
Uses scipy.stats for the normal distribution.

Greeks Reference (Seller's Perspective):
  Delta  → direction risk. Sell OTM: |delta| < 0.40 is the sweet spot.
  Theta  → YOUR FRIEND. Daily time decay earned. Maximised ~30-45 DTE.
  Vega   → IV risk. High vega = big P&L swings if IV spikes. Keep low.
  Gamma  → acceleration of delta. High near expiry. Avoid near-expiry.
  Rho    → interest rate sensitivity. Minor for short-dated options.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import math
import logging
from scipy.stats import norm

from core.models import OptionContract, GreeksResult

log = logging.getLogger(__name__)

# Risk-free rate (US 3-month T-bill approx) — update periodically
RISK_FREE_RATE = 0.053


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float):
    """
    Calculate d1 and d2 for Black-Scholes.
    S = underlying price
    K = strike price
    T = time to expiry in years
    r = risk-free rate
    sigma = implied volatility (annualised)
    """
    if T <= 0 or sigma <= 0:
        return None, None
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return d1, d2


def calculate_greeks(contract: OptionContract, r: float = RISK_FREE_RATE) -> GreeksResult:
    """
    Calculate full Greeks for an option contract.
    Returns GreeksResult with all Greeks computed.
    """
    S = contract.underlying_price
    K = contract.strike
    T = contract.dte / 365.0          # convert DTE to years
    sigma = contract.implied_vol
    is_call = contract.is_call

    d1, d2 = _d1_d2(S, K, T, r, sigma)

    if d1 is None:
        log.warning("Cannot compute Greeks for %s (T=%.4f, sigma=%.4f)", contract, T, sigma)
        return GreeksResult(0, 0, 0, 0, 0, sigma, contract.mid)

    N = norm.cdf
    n = norm.pdf
    sqrt_T = math.sqrt(T)

    # ── Theoretical Price ────────────────────────────────────
    if is_call:
        price = S * N(d1) - K * math.exp(-r * T) * N(d2)
    else:
        price = K * math.exp(-r * T) * N(-d2) - S * N(-d1)

    # ── Delta ────────────────────────────────────────────────
    # Call delta: 0 to +1  |  Put delta: -1 to 0
    delta = N(d1) if is_call else N(d1) - 1

    # ── Gamma ────────────────────────────────────────────────
    # Same for calls and puts
    gamma = n(d1) / (S * sigma * sqrt_T)

    # ── Theta ────────────────────────────────────────────────
    # Annualised, then divided by 365 for daily decay
    # NOTE: Theta is NEGATIVE for buyers (cost). For sellers it's income.
    common_theta = -(S * n(d1) * sigma) / (2 * sqrt_T)
    if is_call:
        theta_annual = common_theta - r * K * math.exp(-r * T) * N(d2)
    else:
        theta_annual = common_theta + r * K * math.exp(-r * T) * N(-d2)
    theta_daily = theta_annual / 365   # daily theta (negative number)
    # For seller's perspective, income is -theta_daily (positive)
    theta_seller = -theta_daily

    # ── Vega ─────────────────────────────────────────────────
    # Per 1% change in IV (divide annual vega by 100)
    vega = S * n(d1) * sqrt_T / 100

    # ── Rho ──────────────────────────────────────────────────
    if is_call:
        rho = K * T * math.exp(-r * T) * N(d2) / 100
    else:
        rho = -K * T * math.exp(-r * T) * N(-d2) / 100

    return GreeksResult(
        delta=round(delta, 4),
        gamma=round(gamma, 4),
        theta=round(theta_seller, 4),   # positive = daily income for seller
        vega=round(vega, 4),
        rho=round(rho, 4),
        iv=sigma,
        theoretical_price=round(price, 4),
    )


def calculate_implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    is_call: bool,
    tol: float = 1e-5,
    max_iter: int = 200,
) -> float:
    """
    Calculate implied volatility using bisection on the Black-Scholes price.

    Args:
        market_price : mid-price of the option (bid+ask)/2
        S            : underlying spot price
        K            : strike price
        T            : time to expiry in years (dte / 365)
        r            : risk-free rate (annualised)
        is_call      : True for call, False for put

    Returns:
        Annualised IV as a decimal (e.g. 0.65 = 65%).
        Returns 0.0 if the solver fails or inputs are degenerate.

    WHY THIS EXISTS
    ---------------
    Yahoo Finance's impliedVolatility column has a known data-quality problem:
    it returns per-period (often per-trading-day) vol instead of annualised vol,
    giving nonsensically low values like 0–6% for TSLA where IV should be 60–100%.
    Computing IV directly from the market price is both more accurate and immune
    to Yahoo's scaling issues.
    """
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    N = norm.cdf

    def bs_price(sigma: float) -> float:
        d1, d2 = _d1_d2(S, K, T, r, sigma)
        if d1 is None:
            return 0.0
        if is_call:
            return S * N(d1) - K * math.exp(-r * T) * N(d2)
        else:
            return K * math.exp(-r * T) * N(-d2) - S * N(-d1)

    # Intrinsic value lower bound — market price must exceed it
    if is_call:
        intrinsic = max(0.0, S - K * math.exp(-r * T))
    else:
        intrinsic = max(0.0, K * math.exp(-r * T) - S)

    if market_price <= intrinsic:
        return 0.0

    sigma_lo, sigma_hi = 1e-4, 10.0
    price_lo = bs_price(sigma_lo)
    price_hi = bs_price(sigma_hi)

    # Market price outside solvable range
    if market_price < price_lo or market_price > price_hi:
        return 0.0

    for _ in range(max_iter):
        sigma_mid = (sigma_lo + sigma_hi) / 2.0
        price_mid = bs_price(sigma_mid)
        if abs(price_mid - market_price) < tol:
            return round(sigma_mid, 6)
        if price_mid < market_price:
            sigma_lo = sigma_mid
        else:
            sigma_hi = sigma_mid

    return round((sigma_lo + sigma_hi) / 2.0, 6)


def calculate_iv_rank(current_iv: float, iv_52w_low: float, iv_52w_high: float) -> float:
    """
    IV Rank = (current_iv - 52w_low) / (52w_high - 52w_low) * 100
    Higher = options are more expensive relative to their history.
    Ideal for selling: IV Rank > 30 (IV is elevated, premium is rich).
    """
    if iv_52w_high == iv_52w_low:
        return 50.0  # can't compute, return neutral
    rank = (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
    return round(max(0.0, min(100.0, rank)), 1)


def calculate_annualised_return(premium: float, underlying_price: float, dte: int,
                                 strategy: str, strike: float = 0.0) -> float:
    """
    Annualised return on capital:
      - Covered Call:      premium / underlying_price  (per share basis)
      - Cash-Secured Put:  premium / strike price      (capital at risk)
    Annualised by: return_per_trade * (365 / dte)
    """
    if dte <= 0:
        return 0.0
    # CSP capital at risk = strike; CC capital at risk = underlying price
    if strategy.lower() == "csp" and strike > 0:
        capital = strike
    elif underlying_price > 0:
        capital = underlying_price
    else:
        return 0.0
    period_return = premium / capital
    annualised = period_return * (365 / dte)
    return round(annualised, 4)
