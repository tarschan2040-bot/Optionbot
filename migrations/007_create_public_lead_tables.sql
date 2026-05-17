-- Migration 007: Create public lead capture tables
-- Used by the landing page newsletter signup and Contact Us form.
-- Apply to shadow first. Production requires separate approval.

CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL UNIQUE,
    source      TEXT DEFAULT 'landing_page',
    status      TEXT DEFAULT 'active',
    ip_address  TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS update_newsletter_subscribers_updated_at
    ON newsletter_subscribers;

CREATE TRIGGER update_newsletter_subscribers_updated_at
    BEFORE UPDATE ON newsletter_subscribers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE newsletter_subscribers ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS contact_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL,
    message     TEXT NOT NULL,
    status      TEXT DEFAULT 'new',
    ip_address  TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS update_contact_messages_updated_at
    ON contact_messages;

CREATE TRIGGER update_contact_messages_updated_at
    BEFORE UPDATE ON contact_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE contact_messages ENABLE ROW LEVEL SECURITY;
