-- LeaseFlow 0007: repayment installments.
-- Created on loan approval. One row per scheduled payment.
-- Stream payment links stored per-installment so the UI can render
-- "Pay now" buttons and webhooks can update a single row on payment.

BEGIN;

-- Repayment cadence — chosen at loan submission time, overridable by admin
DO $$ BEGIN
  CREATE TYPE repayment_frequency AS ENUM ('daily', 'weekly', 'biweekly', 'monthly');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE installment_status AS ENUM ('pending', 'paid', 'overdue', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

ALTER TABLE public.loans
  ADD COLUMN IF NOT EXISTS repayment_frequency repayment_frequency NOT NULL DEFAULT 'monthly';

CREATE TABLE IF NOT EXISTS public.installments (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loan_id                  uuid NOT NULL REFERENCES public.loans(id) ON DELETE CASCADE,
  installment_number       integer NOT NULL CHECK (installment_number > 0),
  due_date                 date NOT NULL,
  amount_sar               numeric NOT NULL CHECK (amount_sar > 0),
  status                   installment_status NOT NULL DEFAULT 'pending',
  stream_payment_link_id   text,
  stream_payment_url       text,
  stream_link_expires_at   timestamptz,
  paid_at                  timestamptz,
  paid_amount_sar          numeric,
  payment_method           text,
  transaction_ref          text,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (loan_id, installment_number)
);

CREATE INDEX IF NOT EXISTS idx_installments_loan     ON public.installments(loan_id);
CREATE INDEX IF NOT EXISTS idx_installments_status   ON public.installments(status);
CREATE INDEX IF NOT EXISTS idx_installments_due      ON public.installments(due_date) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_installments_link_id  ON public.installments(stream_payment_link_id)
  WHERE stream_payment_link_id IS NOT NULL;

DROP TRIGGER IF EXISTS installments_set_updated_at ON public.installments;
CREATE TRIGGER installments_set_updated_at
  BEFORE UPDATE ON public.installments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Realtime so merchants can see status flip when Stream confirms payment
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'installments'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.installments;
  END IF;
END $$;
ALTER TABLE public.installments REPLICA IDENTITY FULL;

-- RLS — merchant sees own via loan ownership, admin sees all
ALTER TABLE public.installments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS installments_select ON public.installments;
CREATE POLICY installments_select ON public.installments
  FOR SELECT TO authenticated
  USING (
    loan_id IN (
      SELECT l.id FROM public.loans l
      JOIN public.merchants m ON m.id = l.merchant_id
      WHERE m.user_id = auth.uid()
    )
    OR public.is_admin()
  );

-- No merchant INSERT/UPDATE/DELETE — backend writes via service_role key;
-- admin can override via policy below.
DROP POLICY IF EXISTS installments_admin_write ON public.installments;
CREATE POLICY installments_admin_write ON public.installments
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

COMMIT;
