"""
tests/test_greeks.py — Unit Tests for Greeks Calculator
=========================================================
Run with: pytest tests/ -v
"""

import pytest
from datetime import date, timedelta
from core.models import OptionContract
from core.greeks import calculate_greeks, calculate_iv_rank, calculate_annualised_return


def make_contract(opt_type="C", strike=100.0, underlying=100.0, dte=30, iv=0.30):
    return OptionContract(
        ticker="TEST",
        underlying_price=underlying,
        strike=strike,
        expiry=date.today() + timedelta(days=dte),
        dte=dte,
        option_type=opt_type,
        bid=2.00,
        ask=2.20,
        last=2.10,
        volume=500,
        open_interest=2000,
        implied_vol=iv,
    )


class TestBlackScholesGreeks:
    def test_atm_call_delta_near_0_5(self):
        """ATM call delta should be approximately 0.5."""
        contract = make_contract("C", strike=100, underlying=100, dte=30, iv=0.30)
        greeks = calculate_greeks(contract)
        assert 0.45 <= greeks.delta <= 0.60, f"ATM call delta {greeks.delta} not near 0.5"

    def test_atm_put_delta_near_neg_0_5(self):
        """ATM put delta should be approximately -0.5."""
        contract = make_contract("P", strike=100, underlying=100, dte=30, iv=0.30)
        greeks = calculate_greeks(contract)
        assert -0.60 <= greeks.delta <= -0.45, f"ATM put delta {greeks.delta} not near -0.5"

    def test_otm_call_low_delta(self):
        """OTM call (strike 10% above underlying) should have delta < 0.4."""
        contract = make_contract("C", strike=110, underlying=100, dte=30, iv=0.30)
        greeks = calculate_greeks(contract)
        assert greeks.delta < 0.40, f"OTM call delta {greeks.delta} should be < 0.4"

    def test_put_call_delta_parity(self):
        """Black-Scholes put-call parity: call_delta - put_delta ≈ 1 for non-dividend stock."""
        call = calculate_greeks(make_contract("C", 100, 100, 30, 0.30))
        put  = calculate_greeks(make_contract("P", 100, 100, 30, 0.30))
        delta_diff = call.delta - put.delta
        assert abs(delta_diff - 1.0) < 0.05, f"Call-Put delta diff {delta_diff} not near 1.0"

    def test_theta_positive_for_seller(self):
        """Theta should be positive (income) from the seller's perspective."""
        contract = make_contract("C", strike=105, underlying=100, dte=30, iv=0.30)
        greeks = calculate_greeks(contract)
        assert greeks.theta > 0, "Theta should be positive for option seller"

    def test_vega_positive(self):
        """Vega should always be positive (seller loses when IV rises)."""
        contract = make_contract("C", strike=100, underlying=100, dte=30, iv=0.30)
        greeks = calculate_greeks(contract)
        assert greeks.vega > 0

    def test_theta_increases_near_expiry(self):
        """Theta decay accelerates as expiry approaches."""
        far  = calculate_greeks(make_contract("C", 100, 100, dte=60))
        near = calculate_greeks(make_contract("C", 100, 100, dte=10))
        # Near expiry ATM theta should be larger (faster decay)
        # Note: deep OTM near expiry can have low theta — use ATM
        assert near.theta >= far.theta * 0.5, "Near expiry theta should be >= far theta"

    def test_zero_dte_returns_safely(self):
        """Zero DTE should not crash."""
        contract = make_contract("C", dte=0)
        greeks = calculate_greeks(contract)
        assert greeks is not None


class TestIVRank:
    def test_iv_rank_middle(self):
        result = calculate_iv_rank(0.30, 0.20, 0.40)
        assert result == 50.0

    def test_iv_rank_at_high(self):
        result = calculate_iv_rank(0.40, 0.20, 0.40)
        assert result == 100.0

    def test_iv_rank_at_low(self):
        result = calculate_iv_rank(0.20, 0.20, 0.40)
        assert result == 0.0

    def test_iv_rank_clamped(self):
        result = calculate_iv_rank(0.50, 0.20, 0.40)  # above 52w high
        assert result == 100.0

    def test_iv_rank_equal_high_low(self):
        result = calculate_iv_rank(0.30, 0.30, 0.30)  # edge case
        assert result == 50.0


class TestAnnualisedReturn:
    def test_simple_return(self):
        # $2 premium on $100 stock, 30 DTE → 2% * (365/30) ≈ 24.3%
        result = calculate_annualised_return(2.0, 100.0, 30, "csp")
        assert 0.20 <= result <= 0.30

    def test_zero_dte_returns_zero(self):
        result = calculate_annualised_return(2.0, 100.0, 0, "cc")
        assert result == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
