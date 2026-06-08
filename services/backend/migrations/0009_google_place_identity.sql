-- LeaseFlow 0008: persist exact Google place identity for review scraping.

BEGIN;

ALTER TABLE public.merchants
  ADD COLUMN IF NOT EXISTS google_place_id text,
  ADD COLUMN IF NOT EXISTS google_place_url text,
  ADD COLUMN IF NOT EXISTS google_place_title text,
  ADD COLUMN IF NOT EXISTS google_place_address text,
  ADD COLUMN IF NOT EXISTS google_place_resolved_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_merchants_google_place_id
  ON public.merchants(google_place_id)
  WHERE google_place_id IS NOT NULL;

COMMIT;

