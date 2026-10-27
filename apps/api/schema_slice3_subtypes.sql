-- Slice 3 (TURBO surge, Oct 26, 2026): card subtype storage — KB gap #7.
--
-- seed_cards.py discarded everything right of the type line's em-dash,
-- so subtypes (Dinosaur, Elf, Cat Soldier...) never reached the
-- database and tribal analysis was unrepresentable.
--
-- Fresh databases get these columns from apps/api/models.py via
-- init_db.py (create_all). Existing databases run this file ONCE,
-- then re-run seed_cards.py to backfill. Idempotent: safe to re-run.
ALTER TABLE cards ADD COLUMN IF NOT EXISTS type_line VARCHAR;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS subtypes VARCHAR[] DEFAULT '{}';
