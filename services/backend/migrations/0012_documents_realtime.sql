-- Adds `documents` to the Supabase Realtime publication so the merchant
-- loan-detail page can live-flip document analysis_status (pending → done)
-- during the pipeline run.
--
-- Why this wasn't covered by 0002_core_tables (which sets loans/dimension_results/
-- installments to REPLICA IDENTITY FULL + publishes them): documents was never
-- added. Frontend subscribes to it and silently no-ops today.
--
-- This is additive and safe to apply to a live database — no locks that aren't
-- already held by an ALTER TABLE, no data shape changes.

BEGIN;

-- payload.new must contain the full row (esp. analysis_status) for the UI to
-- render the right chip without a re-SELECT.
ALTER TABLE public.documents REPLICA IDENTITY FULL;

-- Add to the realtime publication if not already a member.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'documents'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.documents;
  END IF;
END $$;

COMMIT;
