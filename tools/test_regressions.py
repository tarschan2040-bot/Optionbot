import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.routers import candidates as candidates_router
from backend.routers import scan as scan_router
from core.config import ScannerConfig
from core.indicators import compute_mean_reversion_score
from core.models import GreeksResult, OptionContract, ScanOpportunity
from core.scorer import OpportunityScorer
from data.supabase_client import SupabaseClient


def make_opportunity(score: float = 75.0) -> ScanOpportunity:
    contract = OptionContract(
        ticker="TEST",
        underlying_price=100.0,
        strike=105.0,
        expiry=date.today() + timedelta(days=30),
        dte=30,
        option_type="C",
        bid=2.0,
        ask=2.2,
        last=2.1,
        volume=500,
        open_interest=2000,
        implied_vol=0.70,
    )
    greeks = GreeksResult(
        delta=0.30,
        gamma=0.01,
        theta=0.10,
        vega=0.20,
        rho=0.01,
        iv=0.70,
        theoretical_price=2.1,
    )
    return ScanOpportunity(
        contract=contract,
        greeks=greeks,
        strategy="COVERED_CALL",
        iv_rank=50,
        annualised_return=0.20,
        theta_yield=0.10 / 2.1,
        score=score,
    )


def test_missing_mean_reversion_data_scores_neutral_not_zero():
    cfg = ScannerConfig(tickers=["TEST"], use_mean_reversion=True)
    scorer = OpportunityScorer(cfg)

    missing_mr = make_opportunity()
    bad_mr = make_opportunity()
    bad_mr.mean_rev_available = True
    bad_mr.mean_rev_score = 0.0

    assert scorer.score(missing_mr) == round(scorer.score(bad_mr) + 7.5, 2)


def test_config_validate_raises_value_error_when_python_asserts_are_disabled():
    cfg = ScannerConfig(tickers=["TEST"])
    cfg.weight_iv = 0.50

    with pytest.raises(ValueError, match="Scoring weights"):
        cfg.validate()


def test_mr_timing_confirmation_caps_unconfirmed_extreme():
    prices = [100.0] * 20 + [101.0, 102.0, 104.0, 108.0, 116.0]

    result = compute_mean_reversion_score(
        prices,
        "C",
        rsi_period=2,
        z_period=3,
        roc_period=3,
        trend_guard=False,
        timing_confirmation=True,
        timing_sma_period=3,
        timing_unconfirmed_cap=0.75,
    )

    assert result.raw_score > 0.75
    assert result.score == 0.75
    assert result.timing_status == "waiting"


def test_mr_timing_confirmation_can_be_disabled():
    prices = [100.0] * 20 + [101.0, 102.0, 104.0, 108.0, 116.0]

    result = compute_mean_reversion_score(
        prices,
        "C",
        rsi_period=2,
        z_period=3,
        roc_period=3,
        trend_guard=False,
        timing_confirmation=False,
        timing_sma_period=3,
        timing_unconfirmed_cap=0.75,
    )

    assert result.score == result.raw_score
    assert result.score > 0.75
    assert result.timing_status == "disabled"


class FakeInsertTable:
    def __init__(self, parent, table_name):
        self.parent = parent
        self.table_name = table_name
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        self.parent.inserted.append((self.table_name, self.payload))
        return SimpleNamespace(data=[{"id": "row-1"}])


class FakeInsertClient:
    def __init__(self):
        self.inserted = []

    def table(self, table_name):
        return FakeInsertTable(self, table_name)


def test_write_candidates_requires_and_persists_user_id():
    fake_client = FakeInsertClient()
    sb = object.__new__(SupabaseClient)
    sb._enabled = True
    sb._client = fake_client

    opp = make_opportunity(score=90)

    assert sb.write_candidates([opp], datetime.now()) == (0, 0)
    assert fake_client.inserted == []

    assert sb.write_candidates([opp], datetime.now(), user_id="user-123") == (1, 1)
    _, row = fake_client.inserted[0]
    assert row["user_id"] == "user-123"
    assert row["status"] == "starred"


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.payload = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, *_args):
        return self

    def is_(self, *_args):
        return self

    def single(self):
        return self

    def execute(self):
        if self.table_name == "trade_candidates" and self.operation == "select":
            return SimpleNamespace(data=self.client.candidate)
        if self.table_name == "trade_log" and self.operation == "insert":
            if self.client.fail_trade_insert:
                raise RuntimeError("insert failed")
            self.client.inserts.append(self.payload)
            return SimpleNamespace(data=[{"id": "trade-1"}])
        if self.table_name == "trade_candidates" and self.operation == "update":
            self.client.updates.append(self.payload)
            return SimpleNamespace(data=[{"id": "cand-1"}])
        if self.table_name == "trade_log" and self.operation == "delete":
            self.client.deletes += 1
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[])


class FakeWorkflowClient:
    def __init__(self, fail_trade_insert=False):
        self.fail_trade_insert = fail_trade_insert
        self.inserts = []
        self.updates = []
        self.deletes = 0
        self.candidate = {
            "id": "cand-1",
            "user_id": "user-1",
            "ticker": "TEST",
            "strategy": "COVERED_CALL",
            "strike": 105.0,
            "expiry": "2026-06-19",
            "dte": 30,
            "premium": 2.1,
            "contracts": 1,
            "delta": 0.30,
            "iv_rank": 50,
            "status": "starred",
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_confirm_candidate_does_not_mark_placed_when_trade_insert_fails(monkeypatch):
    fake_client = FakeWorkflowClient(fail_trade_insert=True)
    fake_supabase = SimpleNamespace(_client=fake_client)
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: fake_supabase)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(candidates_router.confirm_candidate("cand-1", user_id="user-1"))

    assert exc.value.status_code == 500
    assert fake_client.inserts == []
    assert fake_client.updates == []
    assert fake_client.deletes == 0


class RecordingQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.payload = None
        self.filters = []
        self.is_filters = []
        self.orders = []
        self.limit_value = None
        self.single_called = False

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.is_filters.append(("is", column, value))
        return self

    def order(self, column, **kwargs):
        self.orders.append((column, kwargs))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def single(self):
        self.single_called = True
        return self

    def execute(self):
        self.client.queries.append(self)
        data = self.client.responses.get((self.table_name, self.operation), [])
        if self.single_called and isinstance(data, list):
            data = data[0] if data else None
        return SimpleNamespace(data=data, count=len(data) if isinstance(data, list) else 0)


class RecordingClient:
    def __init__(self, responses=None):
        self.queries = []
        self.responses = responses or {}

    def table(self, table_name):
        return RecordingQuery(self, table_name)


def _fake_supabase(recording_client):
    return SimpleNamespace(_client=recording_client)


def _queries_for(client, table_name, operation=None):
    return [
        q for q in client.queries
        if q.table_name == table_name and (operation is None or q.operation == operation)
    ]


def _assert_user_filter(query, user_id):
    assert ("eq", "user_id", user_id) in query.filters


def test_scan_result_reads_are_scoped_to_authenticated_user(monkeypatch):
    fake_client = RecordingClient({("scan_results", "select"): []})
    monkeypatch.setattr(scan_router, "_get_supabase", lambda: _fake_supabase(fake_client))

    tier_info = {
        "user_id": "user-b",
        "tier": "max",
        "visible_results": None,
        "scans_remaining": None,
        "scans_per_day": None,
        "can_scan": True,
    }

    response = asyncio.run(scan_router.get_scan_results(tier_info=tier_info))
    assert response.results == []

    history = asyncio.run(scan_router.get_scan_history(user_id="user-b"))
    assert history == []

    with pytest.raises(HTTPException) as exc:
        asyncio.run(scan_router.get_scan_result_detail(1, user_id="user-b"))
    assert exc.value.status_code == 404

    scan_queries = _queries_for(fake_client, "scan_results", "select")
    assert len(scan_queries) == 3
    for query in scan_queries:
        _assert_user_filter(query, "user-b")


class FakeManualScanFetcher:
    def __init__(self):
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True


class FakeManualScanScanner:
    fetchers = []

    def __init__(self, _config):
        self.fetcher = FakeManualScanFetcher()
        self.fetchers.append(self.fetcher)

    def run(self):
        return [make_opportunity(score=88.0)]


class FakeManualScanSupabase:
    instances = []

    def __init__(self):
        self._enabled = True
        self._client = RecordingClient()
        self.saved_history = []
        self.instances.append(self)

    def is_enabled(self):
        return self._enabled

    def save_scan_history(self, **kwargs):
        self.saved_history.append(kwargs)
        return True


def test_manual_scan_saves_user_owned_scan_results_without_trade_candidates(monkeypatch):
    FakeManualScanScanner.fetchers = []
    FakeManualScanSupabase.instances = []
    monkeypatch.setattr(scan_router, "OptionScanner", FakeManualScanScanner)
    monkeypatch.setattr(scan_router, "SupabaseClient", FakeManualScanSupabase)

    config = ScannerConfig(tickers=["TEST"], strategy="COVERED_CALL")
    scan_router._run_scan_background("user-web", config)

    supabase = FakeManualScanSupabase.instances[0]
    scan_insert = _queries_for(supabase._client, "scan_results", "insert")[0]

    assert scan_insert.payload["user_id"] == "user-web"
    assert scan_insert.payload["slot_label"] == "Manual"
    assert scan_insert.payload["opportunity_count"] == 1
    assert scan_insert.payload["results"][0]["ticker"] == "TEST"
    assert _queries_for(supabase._client, "trade_candidates") == []
    assert supabase.saved_history[0]["result_count"] == 1
    assert FakeManualScanScanner.fetchers[0].disconnected is True


def test_candidate_and_portfolio_reads_are_scoped_to_authenticated_user(monkeypatch):
    fake_client = RecordingClient({
        ("trade_candidates", "select"): [],
        ("trade_log", "select"): [],
    })
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))

    candidates = asyncio.run(candidates_router.list_candidates(user_id="user-b"))
    portfolio = asyncio.run(candidates_router.get_portfolio(user_id="user-b"))
    summary = asyncio.run(candidates_router.get_portfolio_summary(user_id="user-b"))

    assert candidates == []
    assert portfolio == []
    assert summary.total_open_trades == 0
    assert summary.total_trades_all_time == 0

    candidate_query = _queries_for(fake_client, "trade_candidates", "select")[0]
    _assert_user_filter(candidate_query, "user-b")
    assert ("eq", "status", "starred") in candidate_query.filters

    trade_queries = _queries_for(fake_client, "trade_log", "select")
    assert len(trade_queries) >= 3
    for query in trade_queries:
        _assert_user_filter(query, "user-b")
    assert any(("is", "exit_date", "null") in query.is_filters for query in trade_queries)


def test_portfolio_live_data_pnl_uses_active_candidate_route(monkeypatch):
    expiry = (date.today() + timedelta(days=10)).isoformat()
    fake_client = RecordingClient({
        ("trade_log", "select"): [{
            "id": "trade-1",
            "user_id": "user-b",
            "trade_date": "2026-05-15",
            "ticker": "TEST",
            "strategy": "COVERED_CALL",
            "strike": 105.0,
            "expiry": expiry,
            "dte_at_entry": 30,
            "entry_price": 2.10,
            "contracts": 2,
            "entry_delta": 0.30,
            "exit_date": None,
        }],
    })
    captured_positions = []

    def fake_live_data(positions):
        captured_positions.extend(positions)
        return {
            "TEST": {
                "price": 100.50,
                "day_change_pct": 1.25,
                "options": {
                    f"105.0-{expiry}": {
                        "mid": 1.10,
                        "iv": 0.44,
                        "delta": None,
                        "theta": None,
                    }
                },
            }
        }

    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))
    monkeypatch.setattr(candidates_router, "_fetch_live_data", fake_live_data)

    positions = asyncio.run(candidates_router.get_portfolio(user_id="user-b"))

    assert captured_positions == [{
        "ticker": "TEST",
        "strategy": "COVERED_CALL",
        "strike": 105.0,
        "expiry": expiry,
    }]
    assert len(positions) == 1
    position = positions[0]
    assert position.id == "trade-1"
    assert position.current_stock_price == 100.50
    assert position.current_option_price == 1.10
    assert position.current_iv == 0.44
    assert position.stock_day_change_pct == 1.25
    assert position.pnl_dollars == 200.0
    assert position.pnl_percent == 47.62

    portfolio_query = _queries_for(fake_client, "trade_log", "select")[0]
    _assert_user_filter(portfolio_query, "user-b")
    assert ("is", "exit_date", "null") in portfolio_query.is_filters


def test_candidate_and_portfolio_writes_are_scoped_to_authenticated_user(monkeypatch):
    fake_client = RecordingClient({
        ("trade_candidates", "select"): [],
        ("trade_candidates", "insert"): [{"id": "cand-b"}],
    })
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))

    body = candidates_router.StarRequest(
        ticker="TEST",
        strategy="COVERED_CALL",
        strike=105.0,
        expiry="2026-06-19",
        dte=30,
        delta=0.30,
        theta=0.10,
        premium=2.10,
        score=90.0,
        iv=0.70,
        iv_rank=50.0,
        ann_return=0.20,
    )
    response = asyncio.run(candidates_router.star_candidate(body, user_id="user-b"))
    assert response.success is True

    insert_query = _queries_for(fake_client, "trade_candidates", "insert")[0]
    assert insert_query.payload["user_id"] == "user-b"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(candidates_router.confirm_candidate("cand-owned-by-a", user_id="user-b"))
    assert exc.value.status_code == 404

    confirm_select = _queries_for(fake_client, "trade_candidates", "select")[0]
    assert ("eq", "id", "cand-owned-by-a") in confirm_select.filters
    _assert_user_filter(confirm_select, "user-b")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(candidates_router.close_trade("trade-owned-by-a", user_id="user-b"))
    assert exc.value.status_code == 404

    close_select = _queries_for(fake_client, "trade_log", "select")[0]
    assert ("eq", "id", "trade-owned-by-a") in close_select.filters
    _assert_user_filter(close_select, "user-b")
    assert ("is", "exit_date", "null") in close_select.is_filters


def test_close_trade_rejects_negative_exit_price(monkeypatch):
    fake_client = RecordingClient({
        ("trade_log", "select"): [{
            "id": "trade-1",
            "user_id": "user-b",
            "entry_price": 2.10,
            "contracts": 1,
            "exit_date": None,
        }],
    })
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(candidates_router.close_trade(
            "trade-1",
            body=candidates_router.CloseRequest(exit_price=-0.01),
            user_id="user-b",
        ))

    assert exc.value.status_code == 422
    assert _queries_for(fake_client, "trade_log", "update") == []


def test_expired_position_stays_open_and_flags_review_needed(monkeypatch):
    expiry = (date.today() - timedelta(days=1)).isoformat()
    fake_client = RecordingClient({
        ("trade_log", "select"): [{
            "id": "trade-expired",
            "user_id": "user-b",
            "trade_date": "2026-05-01",
            "ticker": "TEST",
            "strategy": "COVERED_CALL",
            "strike": 105.0,
            "expiry": expiry,
            "dte_at_entry": 30,
            "entry_price": 2.10,
            "contracts": 2,
            "entry_delta": 0.30,
            "exit_date": None,
        }],
    })
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))
    monkeypatch.setattr(candidates_router, "_fetch_live_data", lambda positions: {})

    positions = asyncio.run(candidates_router.get_portfolio(user_id="user-b"))

    assert len(positions) == 1
    assert positions[0].status == "open"
    assert positions[0].dte_now == 0
    assert positions[0].is_expired is True
    assert _queries_for(fake_client, "trade_log", "update") == []


def test_update_position_allows_entry_date(monkeypatch):
    fake_client = RecordingClient({
        ("trade_log", "select"): [{
            "entry_price": 2.10,
            "contracts": 1,
        }],
        ("trade_log", "update"): [],
    })
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))

    response = asyncio.run(candidates_router.update_portfolio_position(
        "trade-1",
        body=candidates_router.UpdateTradeRequest(
            trade_date="2026-05-16",
            entry_price=2.25,
            contracts=2,
        ),
        user_id="user-b",
    ))

    assert response.success is True
    update_query = _queries_for(fake_client, "trade_log", "update")[0]
    assert update_query.payload == {
        "trade_date": "2026-05-16",
        "entry_price": 2.25,
        "contracts": 2,
        "net_premium": 450.0,
    }
    assert ("eq", "id", "trade-1") in update_query.filters
    _assert_user_filter(update_query, "user-b")
    assert ("is", "exit_date", "null") in update_query.is_filters


def test_option_chart_uses_cached_points_when_yahoo_returns_empty(monkeypatch):
    fake_client = RecordingClient({
        ("trade_log", "select"): [{
            "ticker": "TEST",
            "strategy": "COVERED_CALL",
            "strike": 105.0,
            "expiry": "2026-06-19",
        }],
    })
    symbol = candidates_router._yahoo_option_symbol("TEST", "2026-06-19", 105.0, "COVERED_CALL")
    cache_key = (symbol, "15m", "5d")
    cached_points = [
        candidates_router.OptionChartPoint(timestamp="2026-05-16T14:30:00+00:00", close=1.25, volume=10)
    ]
    candidates_router._OPTION_CHART_CACHE[cache_key] = cached_points
    monkeypatch.setattr(candidates_router, "_get_supabase", lambda: _fake_supabase(fake_client))
    monkeypatch.setattr(candidates_router, "_fetch_option_chart", lambda *_args: [])

    chart = asyncio.run(candidates_router.get_portfolio_option_chart(
        "trade-1",
        interval="15m",
        range="5d",
        user_id="user-b",
    ))

    assert chart.points == cached_points
    assert chart.stale is True
    assert "last available chart" in (chart.error or "")
    candidates_router._OPTION_CHART_CACHE.pop(cache_key, None)


def test_user_config_crud_is_scoped_to_authenticated_user():
    fake_client = RecordingClient({
        ("user_configs", "select"): [],
        ("user_configs", "upsert"): [{"id": "cfg-b"}],
        ("user_configs", "delete"): [],
    })
    sb = object.__new__(SupabaseClient)
    sb._enabled = True
    sb._client = fake_client

    assert sb.load_user_config("user-b") is None
    assert sb.save_user_config("user-b", ScannerConfig(tickers=["TEST"])) is True
    assert sb.delete_user_config("user-b") is True

    select_query = _queries_for(fake_client, "user_configs", "select")[0]
    _assert_user_filter(select_query, "user-b")

    upsert_query = _queries_for(fake_client, "user_configs", "upsert")[0]
    assert upsert_query.payload["user_id"] == "user-b"

    delete_query = _queries_for(fake_client, "user_configs", "delete")[0]
    _assert_user_filter(delete_query, "user-b")
