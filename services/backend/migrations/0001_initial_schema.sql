-- LeaseFlow 0001: core schema
-- Enums, tables, indexes, updated_at triggers, helper functions.

BEGIN;

-- ============================================================
-- Enums
-- ============================================================

DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('merchant', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE loan_status AS ENUM (
    'pending_analysis', 'analyzing', 'manual_review', 'approved', 'denied'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE synthesis_status AS ENUM ('pending', 'running', 'done', 'error');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE doc_type AS ENUM (
    'bank_statement', 'pos_data', 'financial_statement', 'invoice'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE document_analysis_status AS ENUM (
    'pending', 'processing', 'done', 'error'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE dimension_name AS ENUM (
    'pos', 'financial_docs', 'simah', 'sentiment', 'industry', 'expert_synthesis'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE dimension_status AS ENUM (
    'queued', 'processing', 'done', 'error', 'skipped'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE market_status AS ENUM ('low_risk', 'medium_risk', 'high_risk');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE risk_appetite AS ENUM ('conservative', 'moderate', 'aggressive');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================
-- Generic helper: updated_at trigger function (no table refs)
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ============================================================
-- Tables (created before any functions that reference them)
-- ============================================================

-- profiles (linked 1:1 to auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role         user_role NOT NULL DEFAULT 'merchant',
  display_name text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS profiles_set_updated_at ON public.profiles;
CREATE TRIGGER profiles_set_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- merchants
CREATE TABLE IF NOT EXISTS public.merchants (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE RESTRICT,
  business_name   text NOT NULL,
  cr_number       text NOT NULL,
  google_maps_url text,
  phone           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_merchants_user_id ON public.merchants(user_id);
CREATE INDEX IF NOT EXISTS idx_merchants_cr_number ON public.merchants(cr_number);

DROP TRIGGER IF EXISTS merchants_set_updated_at ON public.merchants;
CREATE TRIGGER merchants_set_updated_at
  BEFORE UPDATE ON public.merchants
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- loans
CREATE TABLE IF NOT EXISTS public.loans (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id            uuid NOT NULL REFERENCES public.merchants(id) ON DELETE RESTRICT,
  amount_requested       numeric NOT NULL CHECK (amount_requested > 0),
  item_description       text NOT NULL,
  invoice_url            text,
  status                 loan_status NOT NULL DEFAULT 'pending_analysis',
  synthesis_status       synthesis_status NOT NULL DEFAULT 'pending',
  registered_dimensions  text[] NOT NULL DEFAULT ARRAY[]::text[],
  analyst_jobs           jsonb NOT NULL DEFAULT '{}'::jsonb,
  affordability          jsonb,
  decision_payload       jsonb,
  approved_amount        numeric,
  profit_rate            numeric NOT NULL DEFAULT 0.15,
  repayment_months       integer NOT NULL DEFAULT 12,
  monthly_payment        numeric,
  amount_paid            numeric NOT NULL DEFAULT 0,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_loans_merchant_id ON public.loans(merchant_id);
CREATE INDEX IF NOT EXISTS idx_loans_status ON public.loans(status);
CREATE INDEX IF NOT EXISTS idx_loans_created_at_desc ON public.loans(created_at DESC);

DROP TRIGGER IF EXISTS loans_set_updated_at ON public.loans;
CREATE TRIGGER loans_set_updated_at
  BEFORE UPDATE ON public.loans
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- documents
CREATE TABLE IF NOT EXISTS public.documents (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loan_id           uuid NOT NULL REFERENCES public.loans(id) ON DELETE CASCADE,
  doc_type          doc_type NOT NULL,
  storage_path      text NOT NULL,
  content_hash      text,
  extractor_version text,
  analysis_status   document_analysis_status NOT NULL DEFAULT 'pending',
  analysis_report   jsonb,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_loan_id ON public.documents(loan_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON public.documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON public.documents(content_hash);

-- dimension_results
CREATE TABLE IF NOT EXISTS public.dimension_results (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loan_id           uuid NOT NULL REFERENCES public.loans(id) ON DELETE CASCADE,
  dimension         dimension_name NOT NULL,
  status            dimension_status NOT NULL DEFAULT 'queued',
  score             numeric,
  confidence        numeric,
  dimension_version text,
  narrative         text,
  result            jsonb,
  error_message     text,
  analyst_job_id    text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (loan_id, dimension)
);

CREATE INDEX IF NOT EXISTS idx_dimresults_loan_id ON public.dimension_results(loan_id);
CREATE INDEX IF NOT EXISTS idx_dimresults_status ON public.dimension_results(status);

DROP TRIGGER IF EXISTS dimresults_set_updated_at ON public.dimension_results;
CREATE TRIGGER dimresults_set_updated_at
  BEFORE UPDATE ON public.dimension_results
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- risk_snapshots
CREATE TABLE IF NOT EXISTS public.risk_snapshots (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  captured_at    timestamptz NOT NULL DEFAULT now(),
  market_status  market_status NOT NULL,
  market_notes   text,
  cashflow_score numeric,
  risk_appetite  risk_appetite NOT NULL,
  raw_data       jsonb NOT NULL DEFAULT '{}'::jsonb,
  policy_id      uuid
);

CREATE INDEX IF NOT EXISTS idx_risk_snapshots_captured_desc
  ON public.risk_snapshots(captured_at DESC);

-- segments (F&B benchmarks, seeded separately)
CREATE TABLE IF NOT EXISTS public.segments (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text UNIQUE NOT NULL,
  label      text,
  benchmarks jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS segments_set_updated_at ON public.segments;
CREATE TRIGGER segments_set_updated_at
  BEFORE UPDATE ON public.segments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- risk_policies
CREATE TABLE IF NOT EXISTS public.risk_policies (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  effective_from timestamptz NOT NULL DEFAULT now(),
  rules          jsonb NOT NULL,
  created_by     uuid REFERENCES auth.users(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_policies_effective_desc
  ON public.risk_policies(effective_from DESC);

-- simah_cache (stub cache keyed by cr_number)
CREATE TABLE IF NOT EXISTS public.simah_cache (
  cr_number    text PRIMARY KEY,
  result       jsonb NOT NULL,
  cached_until timestamptz NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_simah_cache_until ON public.simah_cache(cached_until);

-- ============================================================
-- Helper functions that reference tables (must come AFTER tables)
-- ============================================================

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin'
  );
$$;

CREATE OR REPLACE FUNCTION public.my_merchant_ids()
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id FROM public.merchants WHERE user_id = auth.uid();
$$;

-- Auto-create a profile row when a new auth.users row is inserted.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, role, display_name)
  VALUES (
    NEW.id,
    'merchant',
    COALESCE(NEW.raw_user_meta_data ->> 'display_name', NEW.email)
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMIT;
