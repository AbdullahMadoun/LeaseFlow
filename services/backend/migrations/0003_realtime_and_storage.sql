-- LeaseFlow 0003: Realtime publications + storage RLS policies.
-- The storage bucket itself is created via the Storage API (not SQL).
-- Path convention: {merchant_id}/{loan_id}/{doc_type}/{uuid}.{ext}

BEGIN;

-- ============================================================
-- Realtime publications
-- supabase_realtime publication exists by default on Supabase.
-- Adding tables makes row changes stream to subscribed clients.
-- ============================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'loans'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.loans;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'dimension_results'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.dimension_results;
  END IF;
END $$;

-- For UPDATE-heavy realtime, send the full new row (needed so clients
-- don't need to re-SELECT after each notification).
ALTER TABLE public.loans             REPLICA IDENTITY FULL;
ALTER TABLE public.dimension_results REPLICA IDENTITY FULL;

-- ============================================================
-- Storage RLS policies on storage.objects for bucket 'loan-documents'
-- Path convention: {merchant_id}/{loan_id}/{doc_type}/{uuid}.{ext}
-- storage.foldername(name)[1] is the first path segment = merchant_id.
-- ============================================================

DROP POLICY IF EXISTS loandocs_select ON storage.objects;
CREATE POLICY loandocs_select ON storage.objects
  FOR SELECT TO authenticated
  USING (
    bucket_id = 'loan-documents'
    AND (
      (storage.foldername(name))[1]::uuid IN (
        SELECT id FROM public.merchants WHERE user_id = auth.uid()
      )
      OR public.is_admin()
    )
  );

DROP POLICY IF EXISTS loandocs_insert ON storage.objects;
CREATE POLICY loandocs_insert ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'loan-documents'
    AND (storage.foldername(name))[1]::uuid IN (
      SELECT id FROM public.merchants WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS loandocs_admin_update ON storage.objects;
CREATE POLICY loandocs_admin_update ON storage.objects
  FOR UPDATE TO authenticated
  USING (bucket_id = 'loan-documents' AND public.is_admin())
  WITH CHECK (bucket_id = 'loan-documents' AND public.is_admin());

DROP POLICY IF EXISTS loandocs_admin_delete ON storage.objects;
CREATE POLICY loandocs_admin_delete ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'loan-documents' AND public.is_admin());

COMMIT;
