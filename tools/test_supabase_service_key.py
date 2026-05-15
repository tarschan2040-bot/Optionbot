from data import supabase_client


def test_supabase_client_prefers_service_role_key(monkeypatch):
    captured = {}

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return object()

    monkeypatch.setattr(supabase_client, "_SUPABASE_AVAILABLE", True)
    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    client = supabase_client.SupabaseClient()

    assert client.is_enabled()
    assert captured == {
        "url": "https://example.supabase.co",
        "key": "service-role-key",
    }


def test_supabase_client_falls_back_to_anon_key(monkeypatch):
    captured = {}

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return object()

    monkeypatch.setattr(supabase_client, "_SUPABASE_AVAILABLE", True)
    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "anon-key")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    client = supabase_client.SupabaseClient()

    assert client.is_enabled()
    assert captured == {
        "url": "https://example.supabase.co",
        "key": "anon-key",
    }
