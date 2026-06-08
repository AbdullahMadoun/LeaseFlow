-- LeaseFlow 0005: ai_traces — full audit trail of the decision pipeline.
-- Every LLM call, rule fire, aggregation, and reconciliation gets a row.
-- Admin-only via RLS (contains raw LLM reasoning — not for merchant eyes).

BEGIN;

DO $$ BEGIN
  CREATE TYPE trace_kind AS ENUM ('llm_call', 'rule', 'aggregation', 'reconcile', 'extraction');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS public.ai_traces (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loan_id      uuid NOT NULL REFERENCES public.loans(id) ON DELETE CASCADE,
  document_id  uuid REFERENCES public.documents(id) ON DELETE CASCADE,
  stage        text NOT NULL,
  dimension    text,
  kind         trace_kind NOT NULL,
  prompt       jsonb,
  response_raw jsonb,
  parsed       jsonb,
  model        text,
  duration_ms  integer,
  error        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_traces_loan_time
  ON public.ai_traces(loan_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_traces_stage
  ON public.ai_traces(stage);
CREATE INDEX IF NOT EXISTS idx_ai_traces_document
  ON public.ai_traces(document_id) WHERE document_id IS NOT NULL;

ALTER TABLE public.ai_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_traces_admin ON public.ai_traces;
CREATE POLICY ai_traces_admin ON public.ai_traces
  FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- Keep the existing documents.analysis_report jsonb — we'll enforce
-- shape via application code, not at the DB level (flexibility for
-- schema evolution). Add a version hint for future migrations.
ALTER TABLE public.documents
  ADD COLUMN IF NOT EXISTS extractor_schema_version text;

COMMIT;
