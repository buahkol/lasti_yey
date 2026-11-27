-- Let operators record their own event kinds (kejadian_produksi.jenis was an ENUM of four values).
-- For databases created before this change; init.sql already has the new column type.
--   docker compose exec -T postgres psql -U postgres -d simonpro < database/migrations/2026-11-27-event-kinds.sql
BEGIN;
ALTER TABLE kejadian_produksi ALTER COLUMN jenis TYPE VARCHAR(40) USING jenis::text;
ALTER TABLE kejadian_produksi ADD CONSTRAINT kejadian_produksi_jenis_check CHECK (jenis ~ '^[A-Z0-9_]+$');
DROP TYPE IF EXISTS jenis_kejadian;
COMMIT;
