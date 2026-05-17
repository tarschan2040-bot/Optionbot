import asyncio
from types import SimpleNamespace

from backend.routers import billing as billing_router


class FakeSubscriptionQuery:
    def __init__(self, client):
        self.client = client
        self.operation = None
        self.payload = None
        self.filters = []

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def upsert(self, payload, **_kwargs):
        self.operation = "upsert"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        if self.operation == "select":
            user_filter = next((value for key, value in self.filters if key == "user_id"), None)
            customer_filter = next((value for key, value in self.filters if key == "stripe_customer_id"), None)
            if user_filter and user_filter in self.client.rows_by_user:
                return SimpleNamespace(data=[self.client.rows_by_user[user_filter]])
            if customer_filter and customer_filter in self.client.rows_by_customer:
                return SimpleNamespace(data=[self.client.rows_by_customer[customer_filter]])
            return SimpleNamespace(data=[])
        if self.operation == "upsert":
            self.client.upserts.append(self.payload)
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=[])


class FakeSupabaseBackend:
    def __init__(self):
        self.rows_by_user = {}
        self.rows_by_customer = {}
        self.upserts = []

    def table(self, table_name):
        assert table_name == "subscriptions"
        return FakeSubscriptionQuery(self)


class FakeSupabase:
    def __init__(self):
        self._client = FakeSupabaseBackend()

    def is_enabled(self):
        return True


class FakeStripe:
    def __init__(self):
        self.created_customers = []
        self.created_sessions = []
        self.Customer = SimpleNamespace(create=self.create_customer)
        self.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=self.create_checkout_session)
        )

    def create_customer(self, **params):
        self.created_customers.append(params)
        return {"id": "cus_test"}

    def create_checkout_session(self, **params):
        self.created_sessions.append(params)
        return {"url": "https://checkout.stripe.test/session"}


class FakeStripeObject:
    def __init__(self, data):
        self._data = data

    def to_dict_recursive(self):
        return self._data


def test_price_id_for_rejects_unconfigured_plan(monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_PRO_MONTHLY", raising=False)

    try:
        billing_router._price_id_for("pro", "monthly")
        assert False, "Expected unconfigured Stripe price to raise."
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503


def test_checkout_session_uses_customer_metadata_and_price(monkeypatch):
    fake_supabase = FakeSupabase()
    fake_stripe = FakeStripe()

    monkeypatch.setenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly")
    monkeypatch.setattr(billing_router, "_get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(billing_router, "_get_stripe", lambda: fake_stripe)

    result = asyncio.run(
        billing_router.create_checkout_session(
            billing_router.CheckoutRequest(tier="pro", billing_period="monthly"),
            claims={"sub": "user-123", "email": "user@example.com"},
        )
    )

    assert result.url == "https://checkout.stripe.test/session"
    assert fake_stripe.created_customers[0]["metadata"]["user_id"] == "user-123"
    assert fake_stripe.created_customers[0]["email"] == "user@example.com"
    session = fake_stripe.created_sessions[0]
    assert session["mode"] == "subscription"
    assert session["customer"] == "cus_test"
    assert session["line_items"] == [{"price": "price_pro_monthly", "quantity": 1}]
    assert session["client_reference_id"] == "user-123"
    assert session["subscription_data"]["metadata"] == {"user_id": "user-123", "tier": "pro"}


def test_sync_subscription_maps_price_to_tier(monkeypatch):
    fake_supabase = FakeSupabase()

    monkeypatch.setenv("STRIPE_PRICE_MAX_ANNUAL", "price_max_annual")
    monkeypatch.setattr(billing_router, "_get_supabase", lambda: fake_supabase)

    synced = billing_router._sync_subscription_from_stripe(
        {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "current_period_end": 1770000000,
            "metadata": {"user_id": "user-123"},
            "items": {"data": [{"price": {"id": "price_max_annual"}}]},
        }
    )

    assert synced is True
    row = fake_supabase._client.upserts[0]
    assert row["user_id"] == "user-123"
    assert row["stripe_customer_id"] == "cus_test"
    assert row["stripe_subscription_id"] == "sub_test"
    assert row["tier"] == "max"
    assert row["status"] == "active"
    assert row["current_period_end"].startswith("2026-02-")


def test_sync_subscription_accepts_stripe_object_metadata(monkeypatch):
    fake_supabase = FakeSupabase()

    monkeypatch.setattr(billing_router, "_get_supabase", lambda: fake_supabase)

    synced = billing_router._sync_subscription_from_stripe(
        {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "current_period_end": 1770000000,
            "metadata": FakeStripeObject({"user_id": "user-123", "tier": "pro"}),
            "items": {"data": [{"price": {"id": "unknown_price"}}]},
        }
    )

    assert synced is True
    row = fake_supabase._client.upserts[0]
    assert row["user_id"] == "user-123"
    assert row["tier"] == "pro"


def test_sync_subscription_uses_item_period_end_when_top_level_missing(monkeypatch):
    fake_supabase = FakeSupabase()

    monkeypatch.setenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly")
    monkeypatch.setattr(billing_router, "_get_supabase", lambda: fake_supabase)

    synced = billing_router._sync_subscription_from_stripe(
        {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": "user-123"},
            "items": {
                "data": [
                    {
                        "price": {"id": "price_pro_monthly"},
                        "current_period_end": 1781643463,
                    }
                ]
            },
        }
    )

    assert synced is True
    row = fake_supabase._client.upserts[0]
    assert row["tier"] == "pro"
    assert row["current_period_end"].startswith("2026-06-")
