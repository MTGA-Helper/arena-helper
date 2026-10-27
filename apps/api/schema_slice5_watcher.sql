-- Slice 5 (TURBO surge, Oct 26, 2026): Arena Watcher storage.
-- Idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS throughout):
-- safe to run repeatedly against an existing database. Mirrors what
-- Base.metadata.create_all builds for fresh databases from
-- apps/api/models.py; existing deployments run this once.
--
-- card_prints.arena_id stores Arena's grpId from the Scryfall record.
-- It is indexed but deliberately NOT unique: Scryfall's bulk data
-- carries prints that share one grpId (the re-seed that proved this
-- failed on a uniqueness violation), and resolution only needs
-- grpId -> card, which duplicates do not disturb.
-- (the seed has always received it and dropped it) so watcher deck
-- rows resolve to engine cards. user_decks / user_deck_cards hold
-- the watcher's synced deck library, one row per (user, Arena deck).

ALTER TABLE card_prints ADD COLUMN IF NOT EXISTS arena_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_card_prints_arena_id ON card_prints (arena_id);

CREATE TABLE IF NOT EXISTS user_decks (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id),
    arena_deck_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    format VARCHAR,
    CONSTRAINT uq_user_arena_deck UNIQUE (user_id, arena_deck_id)
);
CREATE INDEX IF NOT EXISTS ix_user_decks_user_id ON user_decks (user_id);
CREATE INDEX IF NOT EXISTS ix_user_decks_arena_deck_id ON user_decks (arena_deck_id);

CREATE TABLE IF NOT EXISTS user_deck_cards (
    id SERIAL PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES user_decks (id),
    grp_id INTEGER NOT NULL,
    card_id INTEGER REFERENCES cards (id),
    quantity INTEGER DEFAULT 1,
    board VARCHAR NOT NULL DEFAULT 'main'
);
CREATE INDEX IF NOT EXISTS ix_user_deck_cards_deck_id ON user_deck_cards (deck_id);
