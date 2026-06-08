-- LeaseFlow 0002: RLS policies
-- Merchants see their own data; admins see everything.
-- Backend uses the service_role key and bypasses RLS entirely.

BEGIN;

-- ============================================================
-- Enable RLS on all tables
-- ============================================================

ALTER TABLE public.profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.merchants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loans             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dimension_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_snapshots    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.segments          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_policies     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.simah_cache       ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- profiles
-- ============================================================

DROP POLICY IF EXISTS profiles_select ON public.profiles;
CREATE POLICY profiles_select ON public.profiles
  FOR SELECT TO authenticated
  USING (id = auth.uid() OR public.is_admin());

DROP POLICY IF EXISTS profiles_update_self ON public.profiles;
CREATE POLICY profiles_update_self ON public.profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid() AND role = (SELECT role FROM public.profiles WHERE id = auth.uid()));

DROP POLICY IF EXISTS profiles_admin_all ON public.profiles;
CREATE POLICY profiles_admin_all ON public.profiles
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- merchants
-- ============================================================

DROP POLICY IF EXISTS merchants_select ON public.merchants;
CREATE POLICY merchants_select ON public.merchants
  FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR public.is_admin());

DROP POLICY IF EXISTS merchants_insert_self ON public.merchants;
CREATE POLICY merchants_insert_self ON public.merchants
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS merchants_update_self ON public.merchants;
CREATE POLICY merchants_update_self ON public.merchants
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid() OR public.is_admin())
  WITH CHECK (user_id = auth.uid() OR public.is_admin());

DROP POLICY IF EXISTS merchants_admin_delete ON public.merchants;
CREATE POLICY merchants_admin_delete ON public.merchants
  FOR DELETE TO authenticated
  USING (public.is_admin());

-- ============================================================
-- loans
-- ============================================================

DROP POLICY IF EXISTS loans_select ON public.loans;
CREATE POLICY loans_select ON public.loans
  FOR SELECT TO authenticated
  USING (
    merchant_id IN (SELECT id FROM public.merchants WHERE user_id = auth.uid())
    OR public.is_admin()
  );

-- Merchants may create their own loans but only with status='pending_analysis'
-- and only with merchant_id matching one they own. No direct writes to
-- decision_payload/approved_amount/status beyond the initial value — those
-- are owned by the backend (service_role) and admins.
DROP POLICY IF EXISTS loans_insert_merchant ON public.loans;
CREATE POLICY loans_insert_merchant ON public.loans
  FOR INSERT TO authenticated
  WITH CHECK (
    merchant_id IN (SELECT id FROM public.merchants WHERE user_id = auth.uid())
    AND status = 'pending_analysis'
    AND synthesis_status = 'pending'
    AND decision_payload IS NULL
    AND approved_amount IS NULL
  );

-- Only admins may update loans. Merchants are read-only after submit.
-- Backend uses service_role which bypasses RLS.
DROP POLICY IF EXISTS loans_admin_update ON public.loans;
CREATE POLICY loans_admin_update ON public.loans
  FOR UPDATE TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS loans_admin_delete ON public.loans;
CREATE POLICY loans_admin_delete ON public.loans
  FOR DELETE TO authenticated
  USING (public.is_admin());

-- ============================================================
-- documents
-- ============================================================

DROP POLICY IF EXISTS documents_select ON public.documents;
CREATE POLICY documents_select ON public.documents
  FOR SELECT TO authenticated
  USING (
    loan_id IN (
      SELECT l.id FROM public.loans l
      JOIN public.merchants m ON m.id = l.merchant_id
      WHERE m.user_id = auth.uid()
    )
    OR public.is_admin()
  );

DROP POLICY IF EXISTS documents_insert_merchant ON public.documents;
CREATE POLICY documents_insert_merchant ON public.documents
  FOR INSERT TO authenticated
  WITH CHECK (
    loan_id IN (
      SELECT l.id FROM public.loans l
      JOIN public.merchants m ON m.id = l.merchant_id
      WHERE m.user_id = auth.uid()
    )
  );

-- Merchants cannot update/delete documents after upload; admins can.
DROP POLICY IF EXISTS documents_admin_write ON public.documents;
CREATE POLICY documents_admin_write ON public.documents
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- dimension_results (read-only for merchants; writes via service_role)
-- ============================================================

DROP POLICY IF EXISTS dimresults_select ON public.dimension_results;
CREATE POLICY dimresults_select ON public.dimension_results
  FOR SELECT TO authenticated
  USING (
    loan_id IN (
      SELECT l.id FROM public.loans l
      JOIN public.merchants m ON m.id = l.merchant_id
      WHERE m.user_id = auth.uid()
    )
    OR public.is_admin()
  );

DROP POLICY IF EXISTS dimresults_admin_write ON public.dimension_results;
CREATE POLICY dimresults_admin_write ON public.dimension_results
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- risk_snapshots (admin-only visibility; backend writes with service_role)
-- ============================================================

DROP POLICY IF EXISTS risksnap_admin ON public.risk_snapshots;
CREATE POLICY risksnap_admin ON public.risk_snapshots
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- segments (all authenticated users can read; admins write)
-- ============================================================

DROP POLICY IF EXISTS segments_select ON public.segments;
CREATE POLICY segments_select ON public.segments
  FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS segments_admin_write ON public.segments;
CREATE POLICY segments_admin_write ON public.segments
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- risk_policies (admin-only)
-- ============================================================

DROP POLICY IF EXISTS riskpolicies_admin ON public.risk_policies;
CREATE POLICY riskpolicies_admin ON public.risk_policies
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ============================================================
-- simah_cache (admin-only; backend uses service_role)
-- ============================================================

DROP POLICY IF EXISTS simahcache_admin ON public.simah_cache;
CREATE POLICY simahcache_admin ON public.simah_cache
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

COMMIT;
